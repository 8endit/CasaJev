"""Bounded pure-Python worker. OS restrictions are additional to source validation."""
import ast
import json
import os
import platform
import selectors
import signal
import subprocess
import tempfile
import threading
import time
from .contracts import canonical, digest, validate, contract_id

ALLOWED_IMPORTS = {'csv', 'io', 'json', 'math', 'statistics', 'collections', 'itertools',
                   'functools', 'decimal', 'datetime', 're', 'operator', 'string'}
FORBIDDEN = {'open', 'exec', 'eval', 'compile', '__import__', 'globals', 'locals', 'vars',
             'getattr', 'setattr', 'delattr', 'breakpoint', 'input', 'help', 'dir', 'memoryview'}
WORKER_PYTHON = '/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python'
PROFILE = '''(version 1)
(allow default)
(deny mach-lookup)
(deny network*)
(deny file-write*)
(deny signal)
(deny process-fork)
(deny process-exec)
(allow process-exec (literal "WORKER_PYTHON"))
(deny file-read* (subpath "/Users") (subpath "/Volumes")
 (subpath "/private/var/folders") (subpath "/private/tmp") (subpath "/private/var/root"))
'''.replace('WORKER_PYTHON', WORKER_PYTHON)
WORKER = '''import json,sys,resource
resource.setrlimit(resource.RLIMIT_CPU, (3,3))
resource.setrlimit(resource.RLIMIT_FSIZE, (1048576,1048576))
resource.setrlimit(resource.RLIMIT_NOFILE, (32,32))
try:
 resource.setrlimit(resource.RLIMIT_AS, (536870912,536870912))
except (ValueError,OSError):
 pass
packet=json.load(sys.stdin)
namespace={"__name__":"casajev_tool"}
exec(compile(packet["source"],"<tool>","exec"),namespace)
try:
 result=namespace["main"](packet["input"])
 print(json.dumps({"ok":True,"result":result},allow_nan=False))
except Exception as exc:
 print(json.dumps({"ok":False,"error":type(exc).__name__+": "+str(exc)[:500]}))
'''

ACTIVE_PROCESSES = set()
PROCESS_LOCK = threading.Lock()


def terminate_workers():
    with PROCESS_LOCK:
        for pid in ACTIVE_PROCESSES:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def review_source(source):
    if not isinstance(source, str) or len(source) > 40000:
        raise ValueError('Source size limit')
    tree = ast.parse(source)
    if not any(isinstance(n, ast.FunctionDef) and n.name == 'main' for n in tree.body):
        raise ValueError('Tool must define main(payload)')
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or '']
            if any(n not in ALLOWED_IMPORTS for n in names) or getattr(node, 'level', 0):
                raise ValueError('Import not allowed')
        if isinstance(node, ast.Name) and (node.id in FORBIDDEN or node.id.startswith('_')):
            raise ValueError('Unsafe name in source')
        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise ValueError('Private attribute access is not allowed')
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef)):
            raise ValueError('Use plain synchronous functions')
    return True


def bounded_process(command, payload, timeout=8, max_output=1000000, env=None, cwd=None):
    """No shell; process group cleanup on timeout, cancellation and oversized output."""
    with tempfile.TemporaryFile() as stdin:
        stdin.write(payload)
        stdin.seek(0)
        proc = subprocess.Popen(command, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, cwd=cwd, start_new_session=True)
        with PROCESS_LOCK:
            ACTIVE_PROCESSES.add(proc.pid)
        selector = selectors.DefaultSelector()
        streams = {proc.stdout: bytearray(), proc.stderr: bytearray()}
        for stream in streams:
            selector.register(stream, selectors.EVENT_READ)
        start = time.monotonic()
        try:
            while selector.get_map():
                if time.monotonic() - start > timeout:
                    raise TimeoutError('Process time budget exceeded')
                for key, _ in selector.select(.1):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        streams[key.fileobj].extend(chunk)
                        if sum(map(len, streams.values())) > max_output:
                            raise ValueError('Process output budget exceeded')
            proc.wait(timeout=max(.1, timeout - (time.monotonic() - start)))
            return proc.returncode, bytes(streams[proc.stdout]), bytes(streams[proc.stderr])
        finally:
            # Descendants may still exist even if the group leader exited.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            with PROCESS_LOCK:
                ACTIVE_PROCESSES.discard(proc.pid)
            selector.close()
            proc.stdout.close()
            proc.stderr.close()


class Runner:
    def __init__(self, timeout=8):
        self.timeout = timeout
        if platform.system() != 'Darwin' or not os.path.exists('/usr/bin/sandbox-exec') or not os.path.exists(WORKER_PYTHON):
            raise RuntimeError('This release requires macOS sandbox-exec and Command Line Tools Python 3.9; no unsandboxed fallback')

    def run(self, source, value):
        review_source(source)
        command = ['/usr/bin/sandbox-exec', '-p', PROFILE, WORKER_PYTHON, '-I', '-B', '-c', WORKER]
        packet = canonical({'source': source, 'input': value}).encode()
        if len(packet) > 400000:
            raise ValueError('Worker input budget exceeded')
        code, stdout, stderr = bounded_process(command, packet, self.timeout, env={'PATH': '/usr/bin:/bin'})
        if code:
            raise RuntimeError(f'Isolated tool exited with code {code}')
        try:
            response = json.loads(stdout)
        except ValueError:
            raise ValueError('Tool did not return exactly one JSON result') from None
        if not response.get('ok'):
            raise ValueError(response.get('error', 'Tool error'))
        return response['result']

    def verify(self, spec, source):
        review_source(source)
        results = []
        for example in spec['examples']:
            actual = self.run(source, example['input'])
            validate(actual, spec['output_schema'])
            if canonical(actual) != canonical(example['output']):
                raise ValueError('Acceptance example failed: ' + canonical({'input': example['input'],
                                 'expected': example['output'], 'actual': actual})[:2500])
            results.append({'input_hash': digest(example['input']), 'output_hash': digest(actual)})
        return {'passed': True, 'source_hash': digest(source), 'contract_hash': contract_id(spec),
                'checks': results, 'sandbox': 'macOS Seatbelt: home/temp read, write and network restrictions',
                'assurance': 'Contract examples and AST review; not proof of general correctness'}

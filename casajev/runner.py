"""Bounded pure-Python worker. OS restrictions are additional to source validation."""
import ast
import json
import os
import platform
import signal
import subprocess
import tempfile
import threading
import time
import errno
import shutil
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


class TransientWorkerError(RuntimeError):
    """Temporary infrastructure failure, distinct from defective tool code."""


def terminate_workers():
    with PROCESS_LOCK:
        for pid in list(ACTIVE_PROCESSES):
            if os.name == 'nt':
                try:
                    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
                except (OSError, subprocess.SubprocessError):
                    pass
            else:
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


def _terminate_process(proc):
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        except (OSError, subprocess.SubprocessError):
            proc.kill()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def bounded_process(command, payload, timeout=8, max_output=1000000, env=None, cwd=None, cancel_event=None):
    """No shell; portable bounded reads and process-tree cleanup."""
    with tempfile.TemporaryFile() as stdin:
        stdin.write(payload)
        stdin.seek(0)
        try:
            proc = subprocess.Popen(command, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    env=env, cwd=cwd, start_new_session=os.name != 'nt',
                                    creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0))
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EBUSY, errno.ENOMEM, errno.ETXTBSY):
                raise TransientWorkerError('Worker is temporarily unavailable') from exc
            raise
        with PROCESS_LOCK:
            ACTIVE_PROCESSES.add(proc.pid)
        streams = {proc.stdout: bytearray(), proc.stderr: bytearray()}
        lock, overflow = threading.Lock(), threading.Event()
        def read_stream(stream):
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                with lock:
                    streams[stream].extend(chunk)
                    if sum(map(len, streams.values())) > max_output:
                        overflow.set()
                        return
        readers = [threading.Thread(target=read_stream, args=(stream,), daemon=True) for stream in streams]
        for reader in readers: reader.start()
        start = time.monotonic()
        try:
            while proc.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError('Auftrag angehalten. Der Arbeitsstand bleibt gespeichert.')
                if time.monotonic() - start > timeout:
                    raise TimeoutError('Process time budget exceeded')
                if overflow.is_set():
                    raise ValueError('Process output budget exceeded')
                time.sleep(.05)
            for reader in readers: reader.join(timeout=1)
            if overflow.is_set(): raise ValueError('Process output budget exceeded')
            return proc.returncode, bytes(streams[proc.stdout]), bytes(streams[proc.stderr])
        finally:
            _terminate_process(proc)
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
            with PROCESS_LOCK:
                ACTIVE_PROCESSES.discard(proc.pid)
            proc.stdout.close()
            proc.stderr.close()


class Runner:
    def __init__(self, timeout=8):
        self.timeout = timeout
        self.cancel_event = None
        if platform.system() == 'Darwin' and os.path.exists('/usr/bin/sandbox-exec') and os.path.exists(WORKER_PYTHON):
            self.backend = 'macOS Seatbelt'
        elif shutil.which('docker'):
            self.backend = 'Docker'
        else:
            raise RuntimeError('Keine sichere Worker-Sandbox gefunden. Auf macOS werden Command Line Tools benötigt; auf Windows/Linux Docker Desktop oder Docker Engine.')

    def command(self):
        if self.backend == 'macOS Seatbelt':
            return ['/usr/bin/sandbox-exec', '-p', PROFILE, WORKER_PYTHON, '-I', '-B', '-c', WORKER]
        image = os.environ.get('CASAJEV_WORKER_IMAGE', 'python:3.11-slim')
        return ['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '32',
                '--memory', '512m', '--memory-swap', '512m', '--cpus', '1', '--user', '65534:65534',
                '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m', image, 'python', '-I', '-B', '-c', WORKER]

    def run(self, source, value):
        review_source(source)
        command = self.command()
        packet = canonical({'source': source, 'input': value}).encode()
        if len(packet) > 400000:
            raise ValueError('Worker input budget exceeded')
        env = {'PATH': '/usr/bin:/bin'} if self.backend == 'macOS Seatbelt' else None
        code, stdout, stderr = bounded_process(command, packet, self.timeout, env=env, cancel_event=self.cancel_event)
        if code:
            detail = stderr.decode(errors='replace')[:300].strip()
            raise RuntimeError(f'Isolated tool exited with code {code}' + (f': {detail}' if detail else ''))
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
                'checks': results, 'sandbox': self.backend + ': no network, bounded CPU/memory/process/output',
                'assurance': 'Contract examples and AST review; not proof of general correctness'}

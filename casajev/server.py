"""Local UI/API with one durable worker and an explicit administration boundary."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import queue
import threading
import importlib.util
import platform
from urllib.parse import urlparse, parse_qs
from .contracts import canonical, validate_task
from .cli import make_harness
from .runner import terminate_workers, bounded_process
from .browser import BrowserSessions, DesktopBrowserBridge
from .chat import Chat
from .assistant import Assistant
from .builder import CodexBuilder
from .settings import settings, save_settings, save_secret
from .controller import DecisionController
from .policies import decision_policy


class Application:
    def __init__(self, harness, browser, assistant=None):
        self.harness, self.browser, self.assistant = harness, browser, assistant
        self.chat = Chat(harness, browser, assistant=assistant)
        self.library = self.chat.library
        self.jobs = queue.Queue(maxsize=20)
        self.gate = threading.RLock()
        self.active = None
        self.closed = threading.Event()
        self.account_check = {}
        self.laya_probe = None
        if assistant:
            assistant.model.cancel_event = harness.cancel_event
            assistant.model.skills_provider = self.library.enabled_skills
        # Chat owns its task: never enqueue both independently after a restart.
        pending = self.chat.pending()
        owned = {self.chat.read(cid)['messages'][-1].get('task_id') for cid in pending}
        for state in reversed(harness.store.tasks()):
            if state['status'] in ('queued', 'running') and state['id'] not in owned and not self.jobs.full():
                self.jobs.put_nowait(('task', state['id']))
        for cid in pending:
            if not self.jobs.full(): self.jobs.put_nowait(('chat', cid))
        self.thread = threading.Thread(target=self.worker, daemon=True)

    def start(self):
        self.thread.start()

    def worker(self):
        while not self.closed.is_set():
            try: job = self.jobs.get(timeout=.2)
            except queue.Empty: continue
            with self.gate:
                self.active = job
                self.harness.cancel_event.clear()
            try:
                if job[0] == 'chat': self.chat.process(job[1])
                else: self.harness.run(job[1])
            except Exception as exc:
                if job[0] == 'task':
                    self.harness.pause(self.harness.store.get(job[1]), str(exc), 'failed')
            finally:
                with self.gate: self.active = None
                self.jobs.task_done()

    def close(self):
        self.closed.set()
        self.harness.cancel_event.set()
        if self.harness.connectors: self.harness.connectors.close()
        if self.thread.is_alive(): self.thread.join(timeout=3)
        self.browser.close()

    def manage(self):
        h = self.harness
        options = settings(h.store.root)
        return {'settings': options, 'busy': bool(self.active or not self.jobs.empty()),
            'platform': {'system': platform.system(), 'machine': platform.machine(),
                         'worker_backend': getattr(h.runner, 'backend', 'unavailable'),
                         'laya_installed': importlib.util.find_spec('laya') is not None},
            'skills': self.library.list('skills'), 'connectors': h.connectors.list() if h.connectors else [],
            'tools': [{'id': k, 'spec': v['spec'], 'active': bool(v['active']), 'evidence': v['evidence']}
                      for k, v in h.store.tools(active_only=False).items()],
            'accounts': {'jev': {'configured': bool(getattr(h.jev, 'key', None)), 'mode': h.jev.mode,
                                  'check': self.account_check.get('jev')},
                         'laya': {'active': 'laya' in (options['general_decision_provider'], options['realtime_decision_provider']),
                                  'model': options['laya_model'],
                                  'warmed': bool(getattr(self.laya_probe or h.decision_policy, '_router', None)),
                                  'check': self.account_check.get('laya')},
                         'codex': {'installed': bool(self.assistant and self.assistant.model.binary),
                                   'check': self.account_check.get('codex')},
                         'browser': {'saved': bool(getattr(self.browser,'saved',False))}}}

    def post(self, path, body):
        if not isinstance(body, dict): raise ValueError('JSON-Objekt erwartet.')
        h, chat = self.harness, self.chat
        if path == '/api/browser':
            if body.get('action') in ('close', 'forget'): raise ValueError('Bitte die Kontoverwaltung verwenden.')
            return self.browser.for_chat(body.get('conversation')).call(body.get('action'), body)
        with self.gate:
            if path == '/api/chat/stop':
                cid = body['id']
                if self.active == ('chat', cid):
                    h.cancel_event.set()
                    return {'stopping': True}
                convo = chat.read(cid)
                if convo['messages'] and convo['messages'][-1].get('status') == 'working':
                    convo['messages'][-1].update(status='paused', text='Angehalten. Der Auftrag bleibt gespeichert.')
                    chat.save(convo)
                return {'stopping': False}
            if path == '/api/chats/meta':
                chat.update_meta(body['id'], body['changes']); return {'saved': True}
            if path == '/api/chat':
                if self.jobs.full(): raise ValueError('Die Warteschlange ist voll.')
                cid = chat.submit(body)
                self.jobs.put_nowait(('chat', cid)); return {'conversation': cid}
            if path == '/api/tasks':
                if self.jobs.full(): raise ValueError('Die Warteschlange ist voll.')
                state = h.create(body)
                self.jobs.put_nowait(('task', state['id'])); return {'id': state['id']}
            # A running job retains its configuration, libraries and execution policy.
            if self.active or not self.jobs.empty():
                raise BlockingIOError('Bitte den laufenden Auftrag zuerst anhalten oder abschließen lassen.')
            h.cancel_event.clear()
            if path == '/api/chat/resume':
                chat.resume(body['id']); self.jobs.put_nowait(('chat', body['id'])); return {'resumed': True}
            if path == '/api/resume':
                with h.store.lock():
                    state = h.store.get(body['id'])
                    if state['status'] in ('running', 'queued', 'completed', 'budget_exhausted'):
                        raise ValueError('Task cannot be resumed in its current state')
                    if not isinstance(body.get('clarification'), str) or not body['clarification'].strip():
                        raise ValueError('Clarification is required')
                    validate_task({'goal': body['clarification']})
                    state.update(clarification=body['clarification'], phase='decide', status='queued')
                    state.pop('proposals', None)
                    h.store.save(state, 'user_clarification', {'text': body['clarification']})
                self.jobs.put_nowait(('task', state['id'])); return {'id': state['id']}
            if path in ('/api/settings', '/api/onboarding'):
                if path == '/api/onboarding':
                    allowed = {'general_decision_provider', 'realtime_decision_provider'}
                    if set(body) != allowed:
                        raise ValueError('Bitte beide Entscheidungswege auswählen.')
                    body = {**body, 'onboarding_complete': True}
                options = save_settings(h.store.root, body)
                h.limits['steps'], h.max_seconds = options['max_steps'], options['max_seconds']
                h.max_tool_retries = options['max_tool_retries']
                self.browser.remember = options['remember_browser']
                selected = decision_policy(options['general_decision_provider'], jev=h.jev,
                                           laya_model=options['laya_model'])
                h.decision_policy = selected
                h.controller = DecisionController(selected)
                if h.builder:
                    h.builder.model, h.builder.escalation_model = options['builder_model'], options['escalation_model']
                if self.assistant: self.assistant.model.model = options['chat_model']
                return options
            if path == '/api/skills/save': return self.library.save_skill(body)
            if path == '/api/skills/delete':
                self.library.remove('skills', body['id']); return {'removed': True}
            if path in ('/api/tools/toggle', '/api/tools/verify'):
                tool = h.store.tools(active_only=False)[body['id']]
                if path.endswith('toggle') and body.get('active') is False:
                    h.store.revoke(body['id']); return {'active': False}
                evidence = h.runner.verify(tool['spec'], tool['source'])
                if path.endswith('toggle'): h.store.register(tool['spec'], tool['source'], evidence)
                return {'passed': True, 'evidence': evidence}
            if path == '/api/accounts/jev':
                if h.jev.mode != 'live': raise ValueError('Im Demo-Modus werden keine Zugangsdaten gespeichert.')
                save_secret(h.store.root, 'typesafe', body['key'])
                h.jev.key = body['key'].strip()
                self.account_check.pop('jev', None)
                return {'saved': True}
            if path == '/api/accounts/check':
                provider = body['provider']
                if provider == 'laya':
                    self.laya_probe = (h.decision_policy if hasattr(h.decision_policy, 'warmup') else
                                       decision_policy('laya', jev=h.jev,
                                                       laya_model=settings(h.store.root)['laya_model']))
                    self.laya_probe.warmup()
                    self.account_check['laya'] = 'connected'
                elif provider == 'codex':
                    if not self.assistant or not self.assistant.model.binary: raise ValueError('Codex CLI fehlt.')
                    code, _, _ = bounded_process([self.assistant.model.binary, 'login', 'status'], b'', timeout=10, max_output=20000)
                    self.account_check['codex'] = 'connected' if code == 0 else 'disconnected'
                elif provider == 'jev':
                    if h.jev.mode != 'live': raise ValueError('Im Demo-Modus ist keine echte Jev-Verbindung aktiv.')
                    from .jev import choice
                    answer = h.jev.ask({'instruction': 'Choose ready.'}, {'status': choice('Connection test', {'ready': 'Ready'})})
                    self.account_check['jev'] = 'connected' if answer.get('status') == 'ready' else 'unconfirmed'
                else: raise ValueError('Unbekanntes Konto.')
                return {'status': self.account_check[provider]}
            if path == '/api/browser/forget': self.browser.forget_all(); return {'forgotten': True}
            if path == '/api/connectors/save': return {'id': h.connectors.save(body)}
            if path == '/api/connectors/inspect': return h.connectors.inspect(body['id'])
            if path == '/api/connectors/delete':
                connection = h.connectors.connections.pop(body['id'], None)
                if connection: connection.close()
                self.library.remove('connectors', body['id']); return {'removed': True}
            raise KeyError('Endpunkt nicht gefunden.')


def create_server(app, port):
    origin = 'http://127.0.0.1:' + str(port)
    static = Path(__file__).parent / 'static'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def respond(self, code, value, content_type='application/json'):
            body = value.encode() if isinstance(value, str) else canonical(value).encode()
            self.send_response(code)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            try: self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError): pass

        def valid_host(self):
            actual = self.server.server_port
            return self.headers.get('Host') in ('127.0.0.1:' + str(actual), 'localhost:' + str(actual))

        def desktop_authorized(self):
            return (isinstance(app.browser, DesktopBrowserBridge) and
                    self.headers.get('X-CasaJev-Desktop-Token') == app.browser.token)

        def do_GET(self):
            if not self.valid_host(): self.respond(403, {'error': 'Invalid host'}); return
            parsed = urlparse(self.path)
            path, query = parsed.path, parse_qs(parsed.query)
            try:
                if path == '/': self.respond(200, (static / 'index.html').read_text(), 'text/html')
                elif path in ('/static/manage.js', '/static/manage.css'):
                    self.respond(200, (static / path.rsplit('/', 1)[1]).read_text(), 'text/javascript' if path.endswith('.js') else 'text/css')
                elif path == '/api/manage': self.respond(200, app.manage())
                elif path == '/api/desktop/next':
                    if not self.desktop_authorized(): self.respond(403, {'error':'Desktop authorization required'}); return
                    self.respond(200, {'command':app.browser.next(app.browser.token, query.get('timeout',['.8'])[0])})
                elif path == '/api/state':
                    from . import __version__
                    options = settings(app.harness.store.root)
                    self.respond(200, {'app':'CasaJev','version':__version__,'mode':app.harness.policy_mode(),
                        'onboarding_required': not options['onboarding_complete'],
                        'tasks':app.harness.store.tasks(), 'tools':app.manage()['tools'], 'busy': bool(app.active or not app.jobs.empty())})
                elif path.startswith('/api/events/'): self.respond(200, app.harness.store.events(path.rsplit('/',1)[1]))
                elif path == '/api/chats': self.respond(200, {'conversations': app.chat.history(query.get('q',[''])[0], query.get('archived',['0'])[0]=='1')})
                elif path.startswith('/api/chat/'): self.respond(200, app.chat.public_read(path.rsplit('/',1)[1]))
                else: self.respond(404, {'error':'Not found'})
            except (ValueError, KeyError) as exc: self.respond(400, {'error':str(exc)})

        def do_POST(self):
            path = urlparse(self.path).path
            if path == '/api/desktop/result':
                if not self.valid_host() or not self.desktop_authorized():
                    self.respond(403, {'error':'Desktop authorization required'}); return
                if self.headers.get('Content-Type') != 'application/json': self.respond(415, {'error':'JSON required'}); return
                try:
                    size=int(self.headers.get('Content-Length',0))
                    if not 0 < size <= 300000: raise ValueError('Request size limit')
                    self.respond(200, app.browser.resolve(app.browser.token,json.loads(self.rfile.read(size))))
                except (ValueError,KeyError,RuntimeError,TypeError,PermissionError) as exc:
                    self.respond(400, {'error':str(exc)[:1000]})
                return
            actual_origin = 'http://127.0.0.1:' + str(self.server.server_port)
            if not self.valid_host() or self.headers.get('Origin') not in (actual_origin, actual_origin.replace('127.0.0.1','localhost')):
                self.respond(403, {'error':'Same-origin browser request required'}); return
            if self.headers.get('Content-Type') != 'application/json': self.respond(415, {'error':'JSON required'}); return
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 300000: raise ValueError('Request size limit')
                body = json.loads(self.rfile.read(size))
                self.respond(201 if path in ('/api/chat', '/api/tasks') else 200, app.post(path, body))
            except BlockingIOError as exc: self.respond(409, {'error':str(exc)})
            except (ValueError, KeyError, RuntimeError, OSError, TypeError, queue.Full) as exc:
                # Connector failures never echo environment variables or raw subprocess stderr.
                self.respond(400, {'error':str(exc)[:1000]})
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server


def serve(args):
    harness = make_harness(args, demo=args.demo)
    options = settings(harness.store.root)
    desktop_token=os.environ.get('CASAJEV_DESKTOP_TOKEN')
    browser = (DesktopBrowserBridge(harness.store.root,desktop_token,options['remember_browser'])
               if desktop_token else BrowserSessions(harness.store.root, options['remember_browser']))
    assistant = None if args.demo else Assistant(CodexBuilder(harness.store.root / 'conversations',
        model=os.environ.get('CASAJEV_CHAT_MODEL') or options['chat_model'], reasoning='low', timeout=150))
    app = Application(harness, browser, assistant)
    server = create_server(app, args.port)
    app.start()
    print('CasaJev: http://127.0.0.1:' + str(server.server_port) + ' | ' + harness.policy_mode(), flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        app.close()
        terminate_workers()
        server.server_close()

"""Explicitly configured stdio MCP tools. No shell, implicit tools or provider fallback."""
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
from .contracts import canonical, check_schema, digest, validate
from .runner import _terminate_process

class MCPConnection:
    def __init__(self, config, cwd, cancel_event=None):
        self.config, self.cwd, self.cancel_event = config, str(cwd), cancel_event
        self.proc = None
        self.messages = queue.Queue(maxsize=100)
        self.lock = threading.Lock()
        self.serial = 0

    def close(self):
        proc, self.proc = self.proc, None
        if proc:
            _terminate_process(proc)
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: pass
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream: stream.close()

    def _reader(self, stream, messages):
        try:
            while True:
                line = stream.readline(1_000_001)
                if not line: raise RuntimeError('MCP-Verbindung wurde geschlossen.')
                if len(line) > 1_000_000: raise ValueError('MCP-Antwort ist zu groß.')
                value = json.loads(line)
                if not isinstance(value, dict): raise ValueError('Ungültige MCP-Antwort.')
                messages.put(value, timeout=1)
        except Exception:
            try: messages.put_nowait({'transport_error': True})
            except queue.Full: pass

    @staticmethod
    def _discard_errors(stream):
        try:
            while stream.read(4096): pass
        except (OSError, ValueError): pass

    def _write(self, message):
        self.proc.stdin.write((canonical(message)+'\n').encode())
        self.proc.stdin.flush()

    def _request(self, method, params, timeout=25):
        self.serial += 1
        identity = self.serial
        self._write({'jsonrpc':'2.0','id':identity,'method':method,'params':params})
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            if self.cancel_event is not None and self.cancel_event.is_set():
                raise InterruptedError('Auftrag angehalten.')
            try: message = self.messages.get(timeout=.1)
            except queue.Empty: continue
            if message.get('transport_error'): raise RuntimeError('MCP-Verbindung beendet oder Antwort ungültig.')
            if 'method' in message:
                if 'id' in message:
                    # This client does not grant server-initiated sampling or filesystem roots.
                    self._write({'jsonrpc':'2.0','id':message['id'],'error':{'code':-32601,'message':'Client capability unavailable'}})
                continue
            if message.get('id') != identity: continue
            if 'error' in message: raise RuntimeError('Der MCP-Server hat die Anfrage abgelehnt.')
            if 'result' not in message: raise ValueError('MCP-Antwort ohne Ergebnis.')
            return message['result']
        raise TimeoutError('MCP-Zeitlimit erreicht. Es wurde kein Erfolg bestätigt.')

    def request(self, method, params):
        with self.lock:
            try:
                if not self.proc or self.proc.poll() is not None:
                    self.close()
                    self.messages = queue.Queue(maxsize=100)
                    env = {k:v for k,v in os.environ.items() if k in ('HOME','PATH','LANG','TMPDIR')}
                    env.update(self.config.get('env',{}))
                    self.proc = subprocess.Popen([self.config['command'], *self.config['args']],
                        cwd=self.cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, start_new_session=os.name != 'nt',
                        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0))
                    threading.Thread(target=self._reader,args=(self.proc.stdout,self.messages),daemon=True).start()
                    threading.Thread(target=self._discard_errors,args=(self.proc.stderr,),daemon=True).start()
                    from . import __version__
                    result = self._request('initialize',{'protocolVersion':'2025-03-26','capabilities':{},
                        'clientInfo':{'name':'CasaJev','version':__version__}})
                    if not isinstance(result,dict) or not result.get('protocolVersion'):
                        raise ValueError('MCP-Initialisierung fehlgeschlagen.')
                    self._write({'jsonrpc':'2.0','method':'notifications/initialized'})
                return self._request(method, params)
            except Exception:
                self.close()
                raise

class Connectors:
    def __init__(self, library, cancel_event=None):
        self.library, self.cancel_event = library, cancel_event
        self.connections = {}
        self.root = library.store.root / 'connectors'
        self.root.mkdir(exist_ok=True, mode=0o700)

    def close(self):
        for connection in self.connections.values(): connection.close()
        self.connections.clear()

    def list(self):
        return [{k:v for k,v in c.items() if k not in ('env',)} | {'env_names':list(c.get('env',{}))}
                for c in self.library.list('connectors')]

    def get(self, identity):
        item = next((c for c in self.library.list('connectors') if c['id']==identity),None)
        if not item: raise ValueError('Verbindung nicht gefunden.')
        return item

    def save(self, body):
        existing = self.get(body['id']) if body.get('id') else {}
        item = {**existing, **body}
        if not isinstance(item.get('name'),str) or not 1 <= len(item['name'].strip()) <= 80: raise ValueError('Verbindungsname fehlt.')
        if not isinstance(item.get('command'),str) or not item['command'].strip() or len(item['command'])>1000: raise ValueError('Programm fehlt.')
        if not isinstance(item.get('args'),list) or len(item['args'])>40 or any(not isinstance(x,str) or len(x)>4000 for x in item['args']): raise ValueError('Argumente müssen eine JSON-Liste von Texten sein.')
        env = item.get('env',{})
        if not isinstance(env,dict) or len(env)>30 or any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}',k) or not isinstance(v,str) or len(v)>8000 for k,v in env.items()):
            raise ValueError('Ungültige Zugangsdaten/Umgebungsvariablen.')
        for k in ('enabled','read_only'):
            if type(item.get(k,False)) is not bool: raise ValueError('Ungültiger Verbindungsstatus.')
        allowed = item.get('allowed_tools',[])
        if not isinstance(allowed,list) or len(allowed)>80 or any(not isinstance(x,str) for x in allowed): raise ValueError('Ungültige Werkzeugauswahl.')
        # Changing executable/arguments/secrets invalidates the previously inspected catalogue.
        changed = any(item.get(k)!=existing.get(k) for k in ('command','args','env'))
        if changed:
            item.update(tools=[],checked_at=None,enabled=False,allowed_tools=[])
        known = {t['name'] for t in item.get('tools',[]) if t.get('supported')}
        if set(item.get('allowed_tools',[]))-known: raise ValueError('Bitte die Verbindung zuerst prüfen und unterstützte Werkzeuge wählen.')
        if item.get('enabled') and not item.get('read_only'):
            raise ValueError('Aktuell unterstützt CasaJev nur ausdrücklich freigegebene lesende MCP-Werkzeuge.')
        result = self.library.put('connectors',{k:item[k] for k in ('id','name','command','args','env','enabled','read_only','allowed_tools','tools','checked_at') if k in item})
        old = self.connections.pop(result['id'],None)
        if old: old.close()
        return result['id']

    def connection(self, config):
        identity = config['id']
        if identity not in self.connections:
            folder = self.root / identity
            folder.mkdir(exist_ok=True,mode=0o700)
            self.connections[identity] = MCPConnection(config,folder,self.cancel_event)
        return self.connections[identity]

    def inspect(self, identity):
        config = self.get(identity)
        found, cursor = [], None
        for _ in range(10):
            result = self.connection(config).request('tools/list',{'cursor':cursor} if cursor else {})
            if not isinstance(result,dict) or not isinstance(result.get('tools'),list): raise ValueError('Ungültiger MCP-Werkzeugkatalog.')
            for tool in result['tools']:
                if not isinstance(tool,dict) or not isinstance(tool.get('name'),str): raise ValueError('Ungültiger Werkzeugname.')
                schema = tool.get('inputSchema',{'type':'object','properties':{}})
                supported = True
                try: check_schema(schema)
                except Exception: supported = False
                found.append({'name':tool['name'],'description':str(tool.get('description',''))[:4000],
                    'input_schema':schema,'supported':supported,'schema_hash':digest(schema)})
                if len(found)>200: raise ValueError('Bitte einen kleineren MCP-Werkzeugkatalog konfigurieren.')
            cursor = result.get('nextCursor')
            if not cursor: break
        else: raise ValueError('MCP-Katalog enthält zu viele Seiten.')
        if len({t['name'] for t in found}) != len(found): raise ValueError('Doppelte MCP-Werkzeugnamen.')
        # Any changed descriptor requires explicit selection again.
        if digest(found)!=digest(config.get('tools',[])):
            config.update(enabled=False,allowed_tools=[])
        config.update(tools=found,checked_at=time.time())
        self.library.put('connectors',config)
        return next(c for c in self.list() if c['id']==identity)

    def tools(self):
        tools = {}
        for config in self.library.list('connectors'):
            if not config.get('enabled') or not config.get('read_only'): continue
            for tool in config.get('tools',[]):
                if not tool.get('supported') or tool['name'] not in config.get('allowed_tools',[]): continue
                identity = 'mcp:'+config['id']+':'+tool['name']
                tools[identity] = {**tool,'connector':config['id'],'connector_name':config['name']}
        return tools

    def call(self, identity, arguments, schema_hash):
        tool = self.tools().get(identity)
        if not tool or tool['schema_hash'] != schema_hash: raise ValueError('Werkzeug wurde verändert oder nicht freigegeben.')
        validate(arguments,tool['input_schema'])
        config = self.get(tool['connector'])
        result = self.connection(config).request('tools/call',{'name':tool['name'],'arguments':arguments})
        if not isinstance(result,dict) or result.get('isError'): raise RuntimeError('Das externe Werkzeug hat keinen erfolgreichen Aufruf bestätigt.')
        if 'structuredContent' in result: return result['structuredContent']
        blocks = result.get('content')
        if not isinstance(blocks,list): raise ValueError('MCP-Ergebnis enthält keine unterstützten Inhalte.')
        texts = [b['text'] for b in blocks if isinstance(b,dict) and b.get('type')=='text' and isinstance(b.get('text'),str)]
        if not texts: raise ValueError('Dieser Connector liefert kein Text-/JSON-Ergebnis.')
        text = '\n'.join(texts)
        try: return json.loads(text)
        except ValueError: return text

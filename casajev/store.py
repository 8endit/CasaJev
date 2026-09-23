import contextlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid
from .contracts import canonical, contract_id, digest

if os.name == 'nt':
    import msvcrt
else:
    import fcntl


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = self.root / 'state.sqlite3'
        with self.connection() as conn:
            conn.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, body TEXT NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, at REAL, kind TEXT, body TEXT);
            CREATE TABLE IF NOT EXISTS tools(id TEXT PRIMARY KEY, spec TEXT, source TEXT, source_hash TEXT, evidence TEXT, active INTEGER NOT NULL DEFAULT 1);
            ''')
        os.chmod(self.db, 0o600)

    @contextlib.contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @contextlib.contextmanager
    def lock(self):
        # One worker across UI + CLI. SQLite alone would not protect external calls.
        with (self.root / 'worker.lock').open('a+b') as handle:
            try:
                if os.name == 'nt':
                    if handle.tell() == 0:
                        handle.write(b'\0'); handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError):
                raise RuntimeError('Another CasaJev worker is running') from None
            try:
                yield
            finally:
                if os.name == 'nt':
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    def create(self, body):
        task_id = uuid.uuid4().hex[:16]
        state = {'id': task_id, 'goal': body['goal'], 'objects': body.get('objects', {}),
                 'permissions': body.get('permissions', ['compute']), 'acceptance': body.get('acceptance'),
                 'status': 'queued', 'phase': 'decide', 'steps': 0, 'builds': 0, 'jev_calls': 0,
                 'builder_calls': 0, 'elapsed_seconds': 0, 'observations': [], 'seen_calls': [],
                 'result': None, 'created': time.time()}
        self.save(state, 'task_created', {'goal': state['goal']})
        return state

    def save(self, state, kind=None, data=None):
        with self.connection() as conn:
            conn.execute('INSERT OR REPLACE INTO tasks VALUES(?,?,?)',
                         (state['id'], canonical(state), time.time()))
            if kind:
                conn.execute('INSERT INTO events(task_id,at,kind,body) VALUES(?,?,?,?)',
                             (state['id'], time.time(), kind, canonical(data or {})))

    def event(self, task_id, kind, data):
        with self.connection() as conn:
            conn.execute('INSERT INTO events(task_id,at,kind,body) VALUES(?,?,?,?)',
                         (task_id, time.time(), kind, canonical(data)))

    def get(self, task_id):
        with self.connection() as conn:
            row = conn.execute('SELECT body FROM tasks WHERE id=?', (task_id,)).fetchone()
        if row is None:
            raise KeyError('Unknown task')
        return json.loads(row['body'])

    def tasks(self):
        with self.connection() as conn:
            return [json.loads(r['body']) for r in conn.execute('SELECT body FROM tasks ORDER BY updated DESC LIMIT 100')]

    def events(self, task_id):
        with self.connection() as conn:
            return [{**dict(r), 'body': json.loads(r['body'])} for r in conn.execute(
                'SELECT * FROM events WHERE task_id=? ORDER BY seq', (task_id,))]

    def tools(self, active_only=True):
        with self.connection() as conn:
            return {r['id']: {**dict(r), 'spec': json.loads(r['spec']), 'evidence': json.loads(r['evidence'])}
                    for r in conn.execute('SELECT * FROM tools' + (' WHERE active=1' if active_only else ''))}

    def register(self, spec, source, evidence):
        if evidence.get('passed') is not True or evidence.get('source_hash') != digest(source) or evidence.get('contract_hash') != contract_id(spec):
            raise ValueError('Registration needs matching verifier evidence')
        tool_id = spec['name'] + '_' + contract_id(spec)[:10] + '_' + digest(source)[:8]
        with self.connection() as conn:
            # Keep prior versions for inspection, but only one active version per exact contract.
            for r in conn.execute('SELECT id,spec FROM tools WHERE active=1'):
                if contract_id(json.loads(r['spec'])) == contract_id(spec):
                    conn.execute('UPDATE tools SET active=0 WHERE id=?', (r['id'],))
            conn.execute('INSERT OR REPLACE INTO tools VALUES(?,?,?,?,?,1)',
                         (tool_id, canonical(spec), source, digest(source), canonical(evidence)))
        return tool_id

    def revoke(self, tool_id):
        with self.connection() as conn:
            conn.execute('UPDATE tools SET active=0 WHERE id=?', (tool_id,))

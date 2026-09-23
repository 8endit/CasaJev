"""User-managed instructions and external connector definitions in the existing SQLite DB."""
import json
import re
import time
import uuid
from .contracts import canonical

class Library:
    def __init__(self, store):
        self.store = store
        with store.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS skills(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS connectors(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS conversation_meta(id TEXT PRIMARY KEY, title TEXT, archived INTEGER NOT NULL DEFAULT 0, pinned INTEGER NOT NULL DEFAULT 0);
                CREATE VIRTUAL TABLE IF NOT EXISTS conversation_search USING fts5(id UNINDEXED, content, tokenize='unicode61');
            ''')

    def list(self, table):
        if table not in ('skills', 'connectors'): raise ValueError('Unknown library')
        with self.store.connection() as db:
            return [json.loads(row['body']) for row in db.execute('SELECT body FROM '+table+' ORDER BY rowid')]

    def put(self, table, body):
        if table not in ('skills', 'connectors'): raise ValueError('Unknown library')
        body = dict(body)
        body['id'] = body.get('id') or uuid.uuid4().hex[:16]
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', body['id']): raise ValueError('Ungültige Kennung.')
        body['updated_at'] = time.time()
        with self.store.connection() as db:
            db.execute('INSERT OR REPLACE INTO '+table+' VALUES(?,?)', (body['id'], canonical(body)))
        return body

    def save_skill(self, body):
        if not isinstance(body, dict): raise ValueError('Ungültiger Skill.')
        existing = next((s for s in self.list('skills') if s['id'] == body.get('id')), {})
        item = {**existing, **body}
        for key, limit in [('name', 80), ('description', 300), ('instructions', 8000)]:
            if not isinstance(item.get(key), str) or not item[key].strip() or len(item[key]) > limit:
                raise ValueError(f'Skill: {key} fehlt oder ist zu lang.')
        if type(item.get('enabled', True)) is not bool: raise ValueError('Ungültiger Skill-Status.')
        item['enabled'] = item.get('enabled', True)
        others = [s for s in self.list('skills') if s['id'] != item.get('id') and s.get('enabled')]
        if item['enabled'] and (len(others) >= 8 or sum(len(s['instructions']) for s in others) + len(item['instructions']) > 16000):
            raise ValueError('Maximal acht aktive Skills mit zusammen 16.000 Zeichen.')
        return self.put('skills', {k: item[k] for k in ('id', 'name', 'description', 'instructions', 'enabled') if k in item})

    def enabled_skills(self):
        return [{'name': s['name'], 'description': s['description'], 'instructions': s['instructions']}
                for s in self.list('skills') if s.get('enabled')]

    def remove(self, table, identity):
        if table not in ('skills', 'connectors'): raise ValueError('Unknown library')
        with self.store.connection() as db:
            db.execute('DELETE FROM '+table+' WHERE id=?', (identity,))

    def chat_meta(self, identity, changes):
        if set(changes) - {'title', 'archived', 'pinned'}: raise ValueError('Ungültige Chat-Einstellung.')
        if 'title' in changes and (not isinstance(changes['title'], str) or not 1 <= len(changes['title'].strip()) <= 120):
            raise ValueError('Der Titel benötigt 1–120 Zeichen.')
        for key in ('archived', 'pinned'):
            if key in changes and type(changes[key]) is not bool: raise ValueError('Ungültiger Status.')
        with self.store.connection() as db:
            if not db.execute('SELECT 1 FROM conversations WHERE id=?', (identity,)).fetchone(): raise KeyError('Chat nicht gefunden.')
            db.execute('INSERT OR IGNORE INTO conversation_meta(id) VALUES(?)', (identity,))
            for key, value in changes.items():
                db.execute('UPDATE conversation_meta SET '+key+'=? WHERE id=?', (value.strip() if isinstance(value, str) else int(value), identity))

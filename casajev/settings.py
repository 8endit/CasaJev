"""Small persistent settings surface; secrets never enter the public settings response."""
import json
import os
from pathlib import Path
import re
import tempfile

DEFAULTS = {
    'chat_model': 'gpt-5.6-terra', 'builder_model': 'gpt-5.6-terra',
    'escalation_model': 'gpt-5.6-sol', 'max_steps': 24, 'max_seconds': 600,
    'max_tool_retries': 2, 'remember_browser': True,
    'general_decision_provider': 'jev', 'realtime_decision_provider': 'laya',
    'laya_model': 'multilingual', 'onboarding_complete': False,
    'realtime_deadline_ms': 750, 'realtime_max_age_ms': 300,
}

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix='.save-', dir=path.parent)
    try:
        if hasattr(os, 'fchmod'):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def configuration(root):
    path = Path(root) / 'config.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

def settings(root):
    config = configuration(root)
    # 0.5.0 used one global provider. Preserve that choice for the general
    # pipeline while introducing a separate real-time pipeline.
    if 'general_decision_provider' not in config and config.get('decision_provider') in ('jev', 'laya'):
        config['general_decision_provider'] = config['decision_provider']
    return {key: config.get(key, default) for key, default in DEFAULTS.items()}

def save_settings(root, changes):
    if not isinstance(changes, dict) or set(changes) - DEFAULTS.keys():
        raise ValueError('Unbekannte Einstellung.')
    for key, value in changes.items():
        if key.endswith('_model'):
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:-]{0,119}', value):
                raise ValueError('Ungültige Modellkennung.')
            if key == 'laya_model' and value not in ('english', 'multilingual', 'typed-decisions'):
                raise ValueError('Unbekanntes Laya-Modell.')
        elif key in ('general_decision_provider', 'realtime_decision_provider'):
            if value not in ('laya', 'jev'):
                raise ValueError('Ungültiger Entscheidungsanbieter.')
        elif key in ('remember_browser', 'onboarding_complete'):
            if type(value) is not bool: raise ValueError('Ungültige Ein/Aus-Einstellung.')
        else:
            limits = {'max_steps': (4, 100), 'max_seconds': (30, 3600), 'max_tool_retries': (0, 3),
                      'realtime_deadline_ms': (50, 10000), 'realtime_max_age_ms': (10, 10000)}
            low, high = limits[key]
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{key}: erlaubter Bereich {low}–{high}.')
    config = configuration(root)
    config.update(changes)
    atomic_json(Path(root) / 'config.json', config)
    return settings(root)

def secret(root, name):
    path = Path(root) / 'credentials.json'
    values = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    return values.get(name)

def save_secret(root, name, value):
    if name != 'typesafe' or not isinstance(value, str) or not 8 <= len(value.strip()) <= 4096:
        raise ValueError('Bitte einen gültigen TypeSafe-Schlüssel eingeben.')
    path = Path(root) / 'credentials.json'
    values = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    values[name] = value.strip()
    atomic_json(path, values)

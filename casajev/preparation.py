"""Ground numeric transcription in source text before it can become a tool input."""
from collections import Counter
from decimal import Decimal
import re

class PreparationError(ValueError):
    pass

WORDS = {'null': 0, 'eins': 1, 'ein': 1, 'eine': 1, 'zwei': 2, 'drei': 3, 'vier': 4,
         'fünf': 5, 'sechs': 6, 'sieben': 7, 'acht': 8, 'neun': 9, 'zehn': 10,
         'elf': 11, 'zwölf': 12, 'dreizehn': 13, 'vierzehn': 14, 'fünfzehn': 15,
         'sechzehn': 16, 'siebzehn': 17, 'achtzehn': 18, 'neunzehn': 19, 'zwanzig': 20}
NUMBERS = re.compile(r'(?<![\w.])(?:[+−-]\s*|minus\s+)?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?(?!\w|[.,]\d)', re.I)
WORD_NUMBERS = re.compile(r'\b(?:(minus)\s+)?('+'|'.join(sorted(WORDS, key=len, reverse=True))+r')\b', re.I)

def numbers_in(text):
    found = []
    for m in NUMBERS.finditer(text):
        raw = m.group()
        value = re.sub(r'\s+', '', raw.lower().replace('minus', '-').replace('−', '-'))
        # Thousands vs decimal separators need an explicit data format rather than a guess.
        if re.search(r'\d+[.,]\d{3}$', value):
            raise PreparationError('Die Schreibweise mit drei Nachkommastellen ist mehrdeutig. Bitte die Werte als JSON angeben, z. B. [1250, 2.5].')
        found.append((m.start(), Decimal(value.replace(',', '.')), raw))
    for m in WORD_NUMBERS.finditer(text):
        word = m.group(2).lower()
        # Articles are not reliable numeric evidence in ordinary German prose.
        if word in ('ein', 'eine'): continue
        found.append((m.start(), Decimal(WORDS[word]) * (-1 if m.group(1) else 1), m.group()))
    return sorted(found)

def numeric_leaves(value):
    if type(value) in (int, float): return [Decimal(str(value))]
    if isinstance(value, list): return [n for v in value for n in numeric_leaves(v)]
    if isinstance(value, dict): return [n for v in value.values() for n in numeric_leaves(v)]
    return []

def validate_preparation(context, objects):
    """Conservative check: only attest supported numeric transcription, never general semantics."""
    goal = context.get('trusted_goal', '')
    source = numbers_in(goal)
    # Attached prose is source data too; preserve its full numeric sequence.
    for obj in context.get('objects', {}).values():
        if obj.get('kind') == 'text' and isinstance(obj.get('value'), str):
            source.extend(numbers_in(obj['value']))
    proposed = [n for obj in objects.values() for n in numeric_leaves(obj.get('value'))]
    if source and proposed:
        expected = [value for _, value, _ in source]
        if Counter(expected) != Counter(proposed):
            raise PreparationError('Die aufbereiteten Zahlen stimmen nicht vollständig mit deiner Nachricht überein. Bitte gib die vollständigen Werte als Liste oder JSON an; ich rechne nicht mit veränderten Eingaben weiter.')
        values = list(objects.values())
        if len(values) == 1 and isinstance(values[0].get('value'), list) and all(type(v) in (int, float) for v in values[0]['value']):
            if expected != proposed:
                raise PreparationError('Die Aufbereitung hat die Reihenfolge deiner Zahlen verändert. Bitte gib sie als JSON an; Sortieren übernimmt das Werkzeug.')
        return {'method': 'numeric_source_multiset', 'count': len(expected),
                'sources': [{'offset': offset, 'text': raw} for offset, _, raw in source]}
    if proposed and not source:
        existing = [n for obj in context.get('objects', {}).values() for n in numeric_leaves(obj.get('value'))]
        if not existing or Counter(existing) != Counter(proposed):
            raise PreparationError('Die Zahlen lassen sich nicht eindeutig auf deine Angaben zurückführen. Bitte die Werte als Zahlenliste oder JSON ergänzen.')
        return {'method': 'existing_numeric_objects', 'count': len(proposed)}
    return {'method': 'schema_only', 'note': 'Keine unabhängige Prüfung nichtnumerischer Bedeutung.'}

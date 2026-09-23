import hashlib
import json
import re
from jsonschema import Draft202012Validator


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def check_schema(schema):
    Draft202012Validator.check_schema(schema)
    def walk(item):
        if isinstance(item, dict):
            if any(key in item for key in ('$ref', '$dynamicRef', '$id')):
                raise ValueError('Schema references are not supported; use self-contained schemas')
            for value in item.values():
                walk(value)
        elif isinstance(item, list):
            for value in item:
                walk(value)
    walk(schema)


def validate(value, schema):
    Draft202012Validator(schema).validate(value)


def contract(raw):
    required = {'name', 'description', 'operation', 'input_kind', 'output_kind', 'semantics',
                'permissions', 'input_schema', 'output_schema', 'examples'}
    if set(raw) != required:
        raise ValueError('Contract fields do not match protocol')
    for field in ('name', 'description', 'operation', 'input_kind', 'output_kind', 'semantics'):
        if not isinstance(raw[field], str) or not raw[field].strip() or len(raw[field]) > 4000:
            raise ValueError('Invalid contract text')
    if not re.fullmatch('[a-z][a-z0-9_]{0,63}', raw['name']):
        raise ValueError('Invalid tool name')
    if raw['permissions'] != ['compute']:
        raise ValueError('This release executes pure data transformations only')
    for key in ('input_schema', 'output_schema'):
        check_schema(raw[key])
    if not isinstance(raw['examples'], list) or not 2 <= len(raw['examples']) <= 20:
        raise ValueError('At least two acceptance examples are required')
    for case in raw['examples']:
        if set(case) != {'input', 'output'}:
            raise ValueError('Invalid acceptance example')
        validate(case['input'], raw['input_schema'])
        validate(case['output'], raw['output_schema'])
    return raw


def contract_id(spec):
    # Names/descriptions/example ordering are not identity; semantics and schemas are.
    return digest({k: spec[k] for k in ('operation', 'input_kind', 'output_kind', 'semantics',
                                       'permissions', 'input_schema', 'output_schema')})


def validate_task(task):
    if not isinstance(task, dict) or not isinstance(task.get('goal'), str) or not task['goal'].strip():
        raise ValueError('A non-empty goal is required')
    if len(task['goal']) > 12000 or len(canonical(task)) > 300000:
        raise ValueError('Task too large for this local release')
    objects = task.get('objects', {})
    if not isinstance(objects, dict) or len(objects) > 30:
        raise ValueError('Expected at most 30 data objects')
    for key, obj in objects.items():
        if not re.fullmatch('[a-zA-Z][a-zA-Z0-9_]{0,63}', key):
            raise ValueError('Invalid object reference')
        if set(obj) != {'kind', 'description', 'value'}:
            raise ValueError('Objects require kind, description and value')
        if not all(isinstance(obj[k], str) and obj[k] for k in ('kind', 'description')):
            raise ValueError('Invalid object metadata')
    permissions = task.get('permissions', ['compute'])
    if not isinstance(permissions, list) or not permissions or any(p not in ('compute','external_read') for p in permissions):
        raise ValueError('External writes are not supported; reads need an explicitly configured connector')
    return task

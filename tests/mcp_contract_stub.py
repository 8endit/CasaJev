"""Controlled stdio MCP server for the frozen API-boundary acceptance run."""
import json
import sys
from pathlib import Path


scenario_path = Path(sys.argv[1])
log_path = Path(sys.argv[2])

for line in sys.stdin:
    message = json.loads(line)
    if 'id' not in message:
        continue
    scenario = json.loads(scenario_path.read_text())
    method = message['method']
    if method == 'initialize':
        result = {'protocolVersion': '2025-03-26', 'capabilities': {'tools': {}},
                  'serverInfo': {'name': 'controlled-boundary-stub', 'version': '1'}}
    elif method == 'tools/list':
        result = {'tools': [scenario['descriptor']]}
    elif method == 'tools/call':
        arguments = message['params']['arguments']
        if scenario.get('reject_missing') and 'query' not in arguments:
            result = {'isError': True, 'content': [{'type': 'text', 'text': 'query required'}]}
        elif scenario.get('reject_new_field') and 'scope' not in arguments:
            result = {'isError': True, 'content': [{'type': 'text', 'text': 'scope required'}]}
        else:
            result = {'structuredContent': scenario['response']}
    else:
        result = {}
    response = {'jsonrpc': '2.0', 'id': message['id'], 'result': result}
    with log_path.open('a') as log:
        log.write(json.dumps({'request': message, 'response': response}, sort_keys=True) + '\n')
    print(json.dumps(response, sort_keys=True), flush=True)

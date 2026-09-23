"""Benchmark-only stdio MCP: the same four pure tools, no filesystem/network tools."""
import json
import sys
from .contracts import contract_id, validate, canonical
from .runner import Runner
from .templates import TEMPLATES,SOURCES


def handle(request):
    method=request.get('method')
    if method=='initialize':
        return {'protocolVersion':request.get('params',{}).get('protocolVersion','2024-11-05'),
                'capabilities':{'tools':{}},'serverInfo':{'name':'casajev-benchmark','version':'1.0.0'}}
    if method=='ping': return {}
    if method=='tools/list':
        return {'tools':[{'name':s['name'],'description':s['description']+' '+s['semantics'],
                         'inputSchema':{'type':'object','properties':{'payload':s['input_schema']},
                                        'required':['payload'],'additionalProperties':False},
                         'annotations':{'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False}}
                        for s in TEMPLATES]}
    if method=='tools/call':
        try:
            params=request['params'];spec=next(s for s in TEMPLATES if s['name']==params['name'])
            value=params['arguments']['payload']
            validate(value,spec['input_schema'])
            output=Runner().run(SOURCES[contract_id(spec)],value)
            validate(output,spec['output_schema'])
            return {'content':[{'type':'text','text':canonical(output)}],'isError':False}
        except Exception as exc:
            return {'content':[{'type':'text','text':str(exc)[:300]}],'isError':True}
    if method in ('resources/list','resources/templates/list'): return {'resources':[]} if method=='resources/list' else {'resourceTemplates':[]}
    if method=='prompts/list': return {'prompts':[]}
    raise ValueError('Unsupported method')


def main():
    for line in sys.stdin:
        request=json.loads(line)
        if 'id' not in request: continue
        try:
            result={'jsonrpc':'2.0','id':request['id'],'result':handle(request)}
        except Exception as exc:
            result={'jsonrpc':'2.0','id':request['id'],'error':{'code':-32601,'message':str(exc)[:300]}}
        print(canonical(result),flush=True)

if __name__=='__main__':main()

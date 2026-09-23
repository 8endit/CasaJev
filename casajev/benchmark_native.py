"""Single Codex invocation per task, with identical pure tools exposed through MCP."""
import argparse,json,sys,time,statistics
from pathlib import Path
from .benchmark import cases
from .builder import CodexBuilder,object_schema,STRING
from .contracts import canonical
from .assistant import now


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args();root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=True)
    if (root/'results.json').exists(): raise SystemExit('Use a fresh output directory')
    records=[]
    for index,case in enumerate(cases()):
        for label in (['terra','sol'] if index%2==0 else ['sol','terra']):
            b=CodexBuilder(root/'tmp',model='gpt-5.6-'+label,reasoning='low',timeout=90,
                           tools_server={'command':str(Path(sys.executable).absolute()),'args':['-m','casajev.benchmark_tools']})
            start=time.monotonic();error=None;actual=None;success=False
            try:
                answer=b.invoke('Solve the user task using the provided CasaJev MCP tools. You MUST use the tools to compute the result, '
                    'and can chain them where needed. No shell, web or code generation. Return the actual final tool result '
                    'serialized as valid JSON inside result_json. Do not change semantics.\nTask:\n'+case['goal']+
                    '\nInput:\n'+canonical(case['input']),object_schema({'result_json':STRING}))
                actual=json.loads(answer['result_json'])
                success=actual==case['expected'] and bool((b.last or {}).get('tool_calls'))
            except Exception as exc:error=str(exc)[:500]
            record={'case':case['id'],'agent':label+'_native','seconds':time.monotonic()-start,'success':success,
                    'result':actual,'error':error,'evidence':b.last,'date':now()}
            records.append(record)
            (root/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
            print(json.dumps({k:v for k,v in record.items() if k!='evidence'},ensure_ascii=False),flush=True)
    summary={}
    for label in ('terra_native','sol_native'):
        rows=[r for r in records if r['agent']==label];passed=[r['seconds'] for r in rows if r['success']]
        summary[label]={'successes':sum(r['success'] for r in rows),'total':len(rows),
                        'median_seconds_successful':statistics.median(passed) if passed else None}
    (root/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()

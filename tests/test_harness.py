import copy
import json
from pathlib import Path
import subprocess
import threading
import pytest
from casajev.contracts import contract, digest, validate_task
from casajev.engine import Harness
from casajev.jev import DemoJev, selected
from casajev.runner import Runner, PROFILE, WORKER_PYTHON, bounded_process, review_source
from casajev.store import Store
from casajev.templates import CSV, CSV_SOURCE, SORT, SUM, SOURCES
from casajev.contracts import contract_id

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def harness(tmp_path):
    return Harness(Store(tmp_path), DemoJev(), Runner())


def example():
    return json.loads((ROOT / 'examples/csv.json').read_text())


def test_roundtrip_and_durable_reuse(harness):
    first = harness.run(harness.create(example())['id'])
    assert first['status'] == 'completed'
    assert first['builds'] == 1
    assert first['verification'] == 'independent_expected_result'
    fresh = Harness(Store(harness.store.root), DemoJev(), Runner())
    second = fresh.run(fresh.create(example())['id'])
    assert second['status'] == 'completed'
    assert second['builds'] == 0
    assert second['jev_calls'] == 2
    assert len(fresh.store.tools()) == 1


def test_resume_from_verification(harness):
    state = harness.create(example())
    state.update(phase='verify', pending_spec=CSV, pending_source=CSV_SOURCE, builds=1, status='running')
    harness.store.save(state)
    result = harness.run(state['id'])
    assert result['status'] == 'completed'
    assert result['builds'] == 1


def test_no_false_completion_without_observation(harness):
    harness.jev.ask = lambda *a: {'action': 'done'}
    result = harness.run(harness.create(example())['id'])
    assert result['status'] == 'needs_review'


def test_independent_oracle_not_given_to_jev(harness):
    seen = []
    original = harness.jev.ask
    def record(state, questions):
        seen.append(state)
        return original(state, questions)
    harness.jev.ask = record
    task = example()
    task['acceptance']['expected'] = 'wrong'
    result = harness.run(harness.create(task)['id'])
    assert result['status'] == 'needs_review'
    assert all('acceptance' not in context for context in seen)


def test_budget_survives_resume(harness):
    harness.limits['jev_calls'] = 1
    task_id = harness.create(example())['id']
    first = harness.run(task_id)
    second = harness.run(task_id)
    assert first['status'] == second['status'] == 'budget_exhausted'
    assert second['jev_calls'] == 1
    assert not harness.store.tools()


def test_failed_test_never_registers(harness):
    state = harness.create(example())
    state.update(phase='verify', pending_spec=CSV, pending_source='def main(payload):\n    return {}', builds=2)
    harness.store.save(state)
    result = harness.run(state['id'])
    assert result['status'] == 'budget_exhausted'
    assert not harness.store.tools()
    assert any(e['kind'] == 'verification_failed' for e in harness.store.events(state['id']))


def test_stale_state_rejected(harness):
    def mutate(*args):
        state = harness.store.tasks()[0]
        state['goal'] = 'changed'
        harness.store.save(state)
        return {'action': 'done'}
    harness.jev.ask = mutate
    result = harness.run(harness.create(example())['id'])
    assert result['status'] == 'failed'
    assert 'State changed' in result['message']
    assert result['goal'] == 'changed'


def test_worker_lock_is_exclusive(tmp_path):
    a, b = Store(tmp_path), Store(tmp_path)
    with a.lock():
        with pytest.raises(RuntimeError):
            with b.lock():
                pass


def test_permission_request_does_not_build(harness):
    harness.jev.ask = lambda *a: {'action': 'need_permission'}
    state = harness.run(harness.create(example())['id'])
    assert state['status'] == 'needs_permission'
    assert state['builds'] == 0


@pytest.mark.parametrize('field,value', [('permissions', ['write']), ('input_schema', {'$ref':'https://example.org/x'}), ('name', '../../escape')])
def test_contract_rejects_invalid_fields(field, value):
    spec = copy.deepcopy(CSV)
    spec[field] = value
    with pytest.raises(Exception):
        contract(spec)


@pytest.mark.parametrize('source', ['import os\ndef main(x): return os.environ',
                                  'def main(x): return open("secret").read()',
                                  'def main(x): return x.__class__',
                                  'def main(x): return getattr(x,"a")'])
def test_source_review_rejects_dangerous_code(source):
    with pytest.raises(ValueError):
        review_source(source)


def test_timeout_kills_tool():
    with pytest.raises(TimeoutError):
        Runner(timeout=.5).run('def main(payload):\n    while True: pass', None)


def test_output_size_bounded():
    with pytest.raises(ValueError, match='output budget'):
        Runner().run('def main(payload):\n    return "x" * 2000000', None)


def test_csv_exact_semantics_and_malformed_input():
    runner = Runner()
    result = runner.run(CSV_SOURCE, 'name,n\nA,01\na,01\n A,01\nA,1\nA,01\n')
    assert result == {'groups': [[1,5]], 'records': 5, 'extra_duplicates': 1}
    with pytest.raises(ValueError):
        runner.run(CSV_SOURCE, 'a,b\nonly-one\n')


def test_registry_requires_verification_and_versions(harness):
    with pytest.raises(ValueError):
        harness.store.register(CSV, CSV_SOURCE, {'passed': True})
    ev = harness.runner.verify(CSV, CSV_SOURCE)
    first = harness.store.register(CSV, CSV_SOURCE, ev)
    source = CSV_SOURCE + '\n# second implementation version\n'
    second = harness.store.register(CSV, source, harness.runner.verify(CSV, source))
    assert first != second
    assert list(harness.store.tools()) == [second]


def test_corrupted_tool_is_revoked(harness):
    harness.run(harness.create(example())['id'])
    with harness.store.connection() as db:
        db.execute('UPDATE tools SET source=?', ('def main(x): return None',))
    state = harness.run(harness.create(example())['id'])
    assert state['status'] == 'failed'
    assert not harness.store.tools()


def test_invalid_choice_fails_closed():
    with pytest.raises(ValueError):
        selected({'type':'choice','choice':'a','probabilities':{'a':float('nan')},'confidence':1}, {'a':'A'})
    with pytest.raises(ValueError):
        selected({'type':'choice','choice':'a','probabilities':{'a':.2,'b':.8},'confidence':1}, {'a':'A','b':'B'})
    assert selected({'type':'choice','choice':'a','probabilities':{'a':.51,'b':.49},'confidence':.1}, {'a':'A','b':'B'}) is None


def test_real_os_restrictions(tmp_path):
    secret = tmp_path / 'secret.txt'
    secret.write_text('canary')
    target = tmp_path / 'write.txt'
    # Bypass AST review deliberately: check OS enforcement independently of source filtering.
    code = '''import json,socket
result={}
for name,operation in [('read',lambda:open(PATH).read()),('write',lambda:open(TARGET,'w').write('x')),('network',lambda:socket.create_connection(('127.0.0.1',9),timeout=1))]:
 try:
  operation(); result[name]='allowed'
 except PermissionError:
  result[name]='denied'
print(json.dumps(result))
'''.replace('PATH',repr(str(secret))).replace('TARGET',repr(str(target)))
    rc, out, err = bounded_process(['/usr/bin/sandbox-exec','-p',PROFILE,WORKER_PYTHON,'-I','-B','-c',code], b'', 8, env={'PATH':'/usr/bin:/bin'})
    assert rc == 0
    assert json.loads(out) == {'read':'denied','write':'denied','network':'denied'}
    assert not target.exists()


def test_composition_uses_actual_previous_output(harness):
    for spec in (SORT, SUM):
        source = SOURCES[contract_id(spec)]
        harness.store.register(spec, source, harness.runner.verify(spec, source))
    calls = []
    def select(state, questions):
        options = questions['action']['criteria']
        if len(calls) == 0:
            action = next(k for k,v in options.items() if isinstance(v,dict) and 'sort_numbers' in v['tool'])
        elif len(calls) == 1:
            action = next(k for k,v in options.items() if isinstance(v,dict) and 'sum_numbers' in v['tool'] and v['input_ref']=='result_1')
        else:
            action = 'done'
        calls.append(action)
        return {'action':action}
    harness.jev.ask = select
    task = {'goal':'Sort numbers then sum the sorted list.', 'objects':{'numbers':{'kind':'numbers','description':'numbers','value':[3,1,2]}},'acceptance':{'expected':6}}
    result = harness.run(harness.create(task)['id'])
    assert result['status'] == 'completed'
    assert result['observations'][1]['input_ref'] == 'result_1'
    assert result['builds'] == 0


def test_repair_then_register(harness):
    class Builder:
        last = {'backend':'test'}
        def build(self,spec,error=None,escalate=False):
            assert error and escalate
            return CSV_SOURCE
    harness.builder = Builder()
    state = harness.create(example())
    state.update(phase='verify',pending_spec=CSV,pending_source='def main(x): return {}',builds=1)
    harness.store.save(state)
    result = harness.run(state['id'])
    assert result['status'] == 'completed'
    assert result['builds'] == 2
    assert result['builder_calls'] == 1


def test_invalid_unused_hint_does_not_erase_valid_action(monkeypatch):
    import io
    import urllib.request
    from casajev.jev import Jev, choice
    response = {'model':'test','answers':{
        'action':{'type':'choice','choice':'done','confidence':1,'probabilities':{'done':1,'ask':0}},
        'operation':{'type':'choice','choice':'other','confidence':.8,'probabilities':{'other':.1,'group':.9}}}}
    class Opener:
        def open(self,*args,**kwargs):
            return io.BytesIO(json.dumps(response).encode())
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    model = Jev('synthetic-test-value')
    result = model.ask({}, {'action':choice('next',{'done':'done','ask':'ask'}),
                            'operation':choice('hint',{'other':'other','group':'group'})})
    assert result == {'action':'done','operation':None}
    assert 'operation' in model.last['validation_errors']


def test_invalid_primary_answer_is_preserved_as_evidence(harness):
    class Broken:
        mode = 'test'
        last = {'response':{'invalid':True}}
        def ask(self,*args):
            raise ValueError('invalid main answer')
    harness.jev = Broken()
    state = harness.run(harness.create(example())['id'])
    assert state['status'] == 'failed'
    event = next(e for e in harness.store.events(state['id']) if e['kind']=='jev_invalid_response')
    assert event['body']['evidence']['response'] == {'invalid':True}


def test_uncertain_decision_has_only_one_bounded_review(tmp_path):
    from casajev.builder import object_schema
    from casajev.jev import choice
    class Uncertain:
        mode='live';last={}
        def ask(self,*a):return {'action':None}
    class Reviewer:
        last={}
        calls=0
        def invoke(self,*a):
            self.calls+=1
            return {'choice':'ask_user','reason':'Input is actually missing.'}
    store=Store(tmp_path);reviewer=Reviewer()
    h=Harness(store,Uncertain(),Runner(),reviewer)
    task=h.create({'goal':'Do something','objects':{}})
    q={'action':choice('Pick',{'ask_user':'Need actual input','done':'Finished'})}
    assert h.ask(task,h.context(task),q)['action']=='ask_user'
    assert h.ask(task,h.context(task),q)['action'] is None
    assert reviewer.calls==1 and task['builder_calls']==1
    kinds=[event['kind'] for event in store.events(task['id'])]
    assert 'supervisor_escalated' in kinds and 'supervisor_decision' in kinds


def test_decision_review_cannot_fake_completion(tmp_path):
    class Uncertain:
        mode='live';last={}
        def ask(self,*a):return {'action':None}
    class Reviewer:
        last={}
        def invoke(self,*a):return {'choice':'done','reason':'Claim'}
    h=Harness(Store(tmp_path),Uncertain(),Runner(),Reviewer())
    task=h.create({'goal':'Compute a result','objects':{}})
    assert h.run(task['id'])['status']=='needs_review'

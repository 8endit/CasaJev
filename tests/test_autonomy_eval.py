import pytest
from casajev.autonomy_eval import cases,evaluate,FaultRunner
from casajev.engine import Harness
from casajev.jev import DemoJev
from casajev.runner import Runner
from casajev.store import Store


class ForbiddenBuilder:
    def invoke(self,*a,**kw):raise AssertionError('GPT must never be called')
    def propose(self,*a,**kw):raise AssertionError('Tool generation must never be called')


def test_strict_policy_survives_restart_and_blocks_review(tmp_path):
    h=Harness(Store(tmp_path),DemoJev(),Runner(),ForbiddenBuilder(),execution_mode='jev_only')
    task=h.create({'goal':'Test','objects':{}})
    restored=Harness(Store(tmp_path),DemoJev(),Runner(),ForbiddenBuilder())
    restored.jev.ask=lambda *a:{'action':None}
    result=restored.run(task['id'])
    assert result['status']=='needs_input' and result['builder_calls']==0
    with pytest.raises(RuntimeError,match='disabled'):
        restored.builder_call(result,'invoke','prompt',{})


@pytest.mark.parametrize('mode',['jev_only','review_only'])
def test_existing_tool_policy_does_not_build_or_use_templates(tmp_path,mode):
    h=Harness(Store(tmp_path),DemoJev(),Runner(),ForbiddenBuilder(),execution_mode=mode)
    task=h.create({'goal':'Find CSV duplicates','objects':{'input':{'kind':'csv','description':'CSV','value':'a\n1\n1\n'}}})
    result=h.run(task['id'])
    assert result['status']=='needs_capability'
    assert result['builds']==result['builder_calls']==0
    assert not h.store.tools()


def test_evaluator_does_not_count_generic_uncertainty_as_correct_question():
    case=next(c for c in cases() if c['id']=='missing_values')
    state={'status':'needs_input','observations':[]}
    events=[{'kind':'jev_decision','body':{'answers':{'action':None}}}]
    assert not evaluate(case,state,events)['passed']
    events[0]['body']['answers']['action']='need_data'
    assert evaluate(case,state,events)['passed']


def test_recovery_halt_is_not_scored_as_recovery_success():
    case=next(c for c in cases() if c['id']=='transient_worker_failure')
    assert not evaluate(case,{'status':'failed','result':None},[])['passed']
    assert evaluate(case,{'status':'completed','result':18},[])['passed']


def test_false_done_is_visible_and_expected_values_are_separate():
    case=cases()[0]
    assert evaluate(case,{'status':'completed','result':999},[])['false_completion']
    assert 'expected' not in case['objects']
    assert len(cases())==12 and len({c['id'] for c in cases()})==12


def test_injected_failure_occurs_once_before_execution():
    class Fake:
        def run(self,source,value):return value
    worker=FaultRunner(Fake(),True)
    with pytest.raises(RuntimeError,match='Synthetic transient'):
        worker.run('source',18)
    assert worker.run('source',18)==18
    assert worker.injected==1


def test_evaluator_uses_latest_decision_not_an_older_review():
    case=next(c for c in cases() if c['id']=='missing_tool')
    events=[{'kind':'decision_review','body':{'choice':'use:0'}},
            {'kind':'jev_decision','body':{'answers':{'action':'need_capability'}}}]
    assert evaluate(case,{'status':'needs_capability'},events)['passed']

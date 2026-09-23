from casajev.workflows import graph,hints,export
from casajev.store import Store
from casajev.runner import Runner
from casajev.templates import SORT,SUM,POSITIVE,SOURCES
from casajev.contracts import contract_id


def prepared(tmp_path):
    store=Store(tmp_path);runner=Runner();ids=[]
    for spec in (POSITIVE,SUM):
        source=SOURCES[contract_id(spec)]
        ids.append(store.register(spec,source,runner.verify(spec,source)))
    return store,ids


def test_type_match_is_not_claimed_as_observed_workflow(tmp_path):
    store,ids=prepared(tmp_path)
    data=graph(store)
    matching=[e for e in data['links'] if e['source']==ids[0] and e['target']==ids[1]]
    assert matching[0]['relation']=='may_feed' and matching[0]['confidence']=='INFERRED'
    assert not [n for n in data['nodes'] if n['type']=='workflow']
    assert hints(store,'Summiere positive Zahlen',{'numbers'})['possible_compositions']


def test_only_successful_actual_data_flow_is_observed(tmp_path):
    store,ids=prepared(tmp_path)
    task=store.create({'goal':'Summiere positive Zahlen','objects':{}})
    task.update(status='completed',verification='independent_expected_result',observations=[
        {'tool':ids[0],'input_ref':'input','output_ref':'r1'},
        {'tool':ids[1],'input_ref':'r1','output_ref':'r2'}])
    store.save(task)
    data=graph(store)
    assert len([e for e in data['links'] if e['relation']=='observed_flow'])==1
    assert hints(store,'Summiere positive Zahlen',{'numbers'})['observed_workflows'][0]['steps']==ids
    task['observations'][1]['input_ref']='different_input'
    store.save(task)
    assert not [e for e in graph(store)['links'] if e['relation']=='observed_flow']
    task['status']='needs_review';store.save(task)
    assert not [n for n in graph(store)['nodes'] if n['type']=='workflow']


def test_revoked_or_changed_source_cannot_enter_graph(tmp_path):
    store,ids=prepared(tmp_path)
    store.revoke(ids[0])
    with store.connection() as conn:
        conn.execute('UPDATE tools SET source=? WHERE id=?',('changed source',ids[1]))
    assert not graph(store)['nodes']
    assert export(store).exists()

import json
from pathlib import Path
import sys
import threading
import time
import urllib.request
import urllib.error
from types import SimpleNamespace
import pytest
from casajev.store import Store
from casajev.engine import Harness
from casajev.jev import DemoJev
from casajev.runner import Runner, TransientWorkerError, bounded_process
from casajev.templates import SUM, SOURCES
from casajev.contracts import contract_id
from casajev.chat import Chat
from casajev.library import Library
from casajev.connectors import Connectors
from casajev.preparation import validate_preparation, PreparationError
from casajev.settings import settings, save_settings, save_secret
from casajev.server import Application, create_server


def test_numeric_bridge_rejects_filtered_and_changed_inputs():
    ctx = {'trusted_goal':'Behalte nur positive Zahlen aus minus 2, 0, 4 und 4.'}
    def obj(v): return {'input': {'value': v}}
    assert validate_preparation(ctx,obj([-2,0,4,4]))['count']==4
    for values in ([4,4],[-2,0,4],[2,0,4,4],[-2,0,4,5]):
        with pytest.raises(PreparationError): validate_preparation(ctx,obj(values))
    assert validate_preparation({'trusted_goal':'acht und neun'},obj([8,9]))['count']==2


def test_numeric_bridge_uses_existing_data_without_inventing():
    ctx={'trusted_goal':'Addiere sie','objects':{'old':{'value':[2,2,-4]}}}
    assert validate_preparation(ctx,{'input':{'value':[2,2,-4]}})['method']=='existing_numeric_objects'
    with pytest.raises(PreparationError): validate_preparation(ctx,{'input':{'value':[2,4]}})


class RetryJev(DemoJev):
    def ask(self,state,questions):
        if 'retry' in questions.get('action',{}).get('criteria',{}): return {'action':'retry'}
        return super().ask(state,questions)


class Flaky:
    def __init__(self, failures=1, error=TransientWorkerError): self.calls=0;self.failures=failures;self.error=error
    def run(self,source,value):
        self.calls+=1
        if self.calls<=self.failures: raise self.error('temporary resource unavailable')
        return sum(value)


def prepared_harness(tmp_path, runner):
    store=Store(tmp_path);real=Runner();source=SOURCES[contract_id(SUM)]
    identity=store.register(SUM,source,real.verify(SUM,source))
    h=Harness(store,RetryJev(),runner,execution_mode='jev_only',use_graph=False)
    state=h.create({'goal':'Summe','objects':{'input':{'kind':'numbers','description':'Zahlen','value':[2,3]}}})
    return h,state,identity


def test_transient_retry_completes_without_builder(tmp_path):
    runner=Flaky();h,state,identity=prepared_harness(tmp_path,runner)
    result=h.run(state['id'])
    assert result['status']=='completed' and result['result']==5
    assert result['builder_calls']==0 and runner.calls==2 and identity in h.store.tools()
    assert 'tool_transient_failure' in [e['kind'] for e in h.store.events(state['id'])]


def test_retry_limit_persists_after_restart(tmp_path):
    runner=Flaky(20);h,state,identity=prepared_harness(tmp_path,runner)
    assert h.run(state['id'])['status']=='failed' and runner.calls==3
    fresh=Harness(Store(tmp_path),RetryJev(),runner,execution_mode='jev_only',use_graph=False)
    assert fresh.run(state['id'])['status']=='failed' and runner.calls==3
    assert identity in fresh.store.tools()


def test_defective_tool_is_not_retried_as_transient(tmp_path):
    runner=Flaky(error=ValueError);h,state,identity=prepared_harness(tmp_path,runner)
    assert h.run(state['id'])['status']=='failed' and runner.calls==1
    assert identity not in h.store.tools()


def test_interrupt_saves_and_resumes_without_gpt(tmp_path):
    runner=Flaky(failures=0);h,state,_=prepared_harness(tmp_path,runner)
    h.cancel_event.set()
    assert h.run(state['id'])['status']=='paused' and runner.calls==0
    h.cancel_event.clear()
    assert h.run(state['id'])['status']=='completed'


def test_subprocess_can_be_interrupted():
    event=threading.Event();timer=threading.Timer(.2,event.set);timer.start()
    with pytest.raises(InterruptedError):
        bounded_process([sys.executable,'-c','import time; time.sleep(10)'],b'',timeout=15,max_output=100,cancel_event=event)
    timer.join()


def test_chat_metadata_search_and_legacy_migration(tmp_path):
    chat=Chat(Harness(Store(tmp_path),DemoJev(),Runner()),None)
    cid=chat.submit({'message':'Meine Birnenlieferung'})
    stale=chat.read(cid)
    chat.update_meta(cid,{'title':'Obst','pinned':True,'archived':True})
    chat.save(stale)  # A late worker write must not erase user metadata.
    new=Chat(Harness(Store(tmp_path),DemoJev(),Runner()),None)
    assert not new.history('Birnenlieferung')
    found=new.history('Birnenlieferung',archived=True)
    assert found[0]['title']=='Obst' and found[0]['pinned']
    assert new.history('Obst',archived=True)[0]['id']==cid
    new.update_meta(cid,{'archived':False})
    assert new.history()[0]['id']==cid


def test_skills_and_settings_persist_privately(tmp_path):
    library=Library(Store(tmp_path));skill=library.save_skill({'name':'Kurz','description':'Stil','instructions':'Antworte knapp.'})
    assert Library(Store(tmp_path)).enabled_skills()[0]['instructions']=='Antworte knapp.'
    library.save_skill({'id':skill['id'],'enabled':False})
    assert library.enabled_skills()==[]
    save_settings(tmp_path,{'max_tool_retries':1,'remember_browser':False})
    assert settings(tmp_path)['max_tool_retries']==1
    with pytest.raises(ValueError): save_settings(tmp_path,{'max_tool_retries':99})
    save_secret(tmp_path,'typesafe','private-test-secret')
    assert (tmp_path/'credentials.json').stat().st_mode&0o777==0o600
    assert 'private-test-secret' not in json.dumps(settings(tmp_path))


def test_pipeline_settings_migrate_old_provider_and_validate_independently(tmp_path):
    (tmp_path/'config.json').write_text(json.dumps({'decision_provider':'laya'}))
    options=settings(tmp_path)
    assert options['general_decision_provider']=='laya'
    assert options['realtime_decision_provider']=='laya'
    assert options['onboarding_complete'] is False
    saved=save_settings(tmp_path,{'general_decision_provider':'jev',
                                  'realtime_decision_provider':'laya',
                                  'onboarding_complete':True})
    assert saved['general_decision_provider']=='jev' and saved['onboarding_complete']
    with pytest.raises(ValueError): save_settings(tmp_path,{'realtime_decision_provider':'unknown'})


FAKE_MCP = '''import sys,json
for line in sys.stdin:
 m=json.loads(line)
 if 'id' not in m: continue
 method=m['method']
 if method=='initialize': result={'protocolVersion':'2025-03-26','capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':'1'}}
 elif method=='tools/list': result={'tools':[{'name':'lookup','description':'Read fixture','inputSchema':{'type':'object','properties':{'query':{'type':'string'}},'required':['query'],'additionalProperties':False}}]}
 elif method=='tools/call': result={'content':[{'type':'text','text':json.dumps({'found':m['params']['arguments']['query']})}]}
 else: result={}
 print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':result}),flush=True)
'''

def connector_fixture(tmp_path):
    script=tmp_path/'mcp_fixture.py';script.write_text(FAKE_MCP)
    store=Store(tmp_path/'state');manager=Connectors(Library(store))
    identity=manager.save({'name':'Fixture','command':sys.executable,'args':[str(script)],'env':{'FIXTURE_SECRET':'hidden-fixture-value'}})
    return manager,identity


def test_stdio_mcp_discovery_allowlist_and_real_execution(tmp_path):
    manager,identity=connector_fixture(tmp_path)
    try:
        assert manager.tools()=={}
        inspected=manager.inspect(identity)
        assert inspected['tools'][0]['supported']
        assert 'hidden-fixture-value' not in json.dumps(manager.list())
        manager.save({'id':identity,'allowed_tools':['lookup'],'enabled':True,'read_only':True})
        tool_id,tool=next(iter(manager.tools().items()))
        assert manager.call(tool_id,{'query':'pear'},tool['schema_hash'])=={'found':'pear'}
        with pytest.raises(Exception): manager.call(tool_id,{'unknown':'x'},tool['schema_hash'])
        manager.save({'id':identity,'enabled':False})
        with pytest.raises(ValueError): manager.call(tool_id,{'query':'x'},tool['schema_hash'])
        manager.save({'id':identity,'args':['changed']})
        assert manager.get(identity)['tools']==[]
    finally: manager.close()


def test_jev_can_drive_enabled_mcp_without_builder(tmp_path):
    manager,identity=connector_fixture(tmp_path)
    class ExternalJev:
        mode='demo';last=None
        def ask(self,state,questions):
            if state['observations']: return {'action':'done'}
            return {'action':next(k for k in questions['action']['criteria'] if k.startswith('external:'))}
    try:
        manager.inspect(identity);manager.save({'id':identity,'allowed_tools':['lookup'],'enabled':True,'read_only':True})
        h=Harness(manager.library.store,ExternalJev(),Runner(),connectors=manager,execution_mode='jev_only',use_graph=False)
        task=h.create({'goal':'Look up pear','objects':{'args':{'kind':'json','description':'query','value':{'query':'pear'}}},'permissions':['external_read']})
        result=h.run(task['id'])
        assert result['status']=='completed' and result['result']=={'found':'pear'} and result['builder_calls']==0
        assert result['verification'].startswith('external_source') and result['observations'][0]['validated'] is False
    finally: manager.close()


class QuietBrowser:
    state_file=None;remember=True
    def close(self): pass


def app_fixture(tmp_path):
    h=Harness(Store(tmp_path),DemoJev(),Runner())
    h.connectors=Connectors(Library(h.store),h.cancel_event)
    return Application(h,QuietBrowser())


def test_management_busy_guard_and_queued_stop(tmp_path):
    app=app_fixture(tmp_path)
    cid=app.post('/api/chat',{'message':'Sortiere [2,1]'})['conversation']
    with pytest.raises(BlockingIOError): app.post('/api/settings',{'max_steps':20})
    app.post('/api/chat/stop',{'id':cid})
    assert app.chat.read(cid)['messages'][-1]['status']=='paused'
    app.chat.process(cid)
    assert app.chat.read(cid)['messages'][-1]['status']=='paused'


def test_onboarding_persists_both_pipelines_and_hot_switches_general_policy(tmp_path):
    app=app_fixture(tmp_path)
    result=app.post('/api/onboarding',{'general_decision_provider':'laya',
                                       'realtime_decision_provider':'jev'})
    assert result['onboarding_complete'] is True
    assert settings(tmp_path)['realtime_decision_provider']=='jev'
    assert app.harness.policy_mode()=='laya-local'
    app.post('/api/settings',{'general_decision_provider':'jev'})
    assert app.harness.policy_mode()=='demo'


def test_http_origin_guard_and_private_management(tmp_path):
    app=app_fixture(tmp_path);server=create_server(app,0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_port)
    try:
        with urllib.request.urlopen(base+'/api/manage') as res:
            public=json.load(res);assert 'settings' in public and 'key' not in public['accounts']['jev']
        request=urllib.request.Request(base+'/api/settings',data=b'{"max_steps":22}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as err: urllib.request.urlopen(request)
        assert err.value.code==403
        request.add_header('Origin',base)
        with urllib.request.urlopen(request) as res: assert json.load(res)['max_steps']==22
    finally: server.shutdown();server.server_close();app.close();thread.join()


def test_numeric_bridge_rejects_pre_sorted_prose():
    with pytest.raises(PreparationError):
        validate_preparation({'trusted_goal':'Sortiere 9, 2 und 5.'},{'input':{'value':[2,5,9]}})


def test_stop_active_chat_and_resume_saved_request(tmp_path):
    entered=threading.Event()
    class SlowModel:
        last=None
    class SlowAssistant:
        model=SlowModel()
        def plan(self,context):
            entered.set()
            self.model.cancel_event.wait(timeout=2)
            if self.model.cancel_event.is_set(): raise InterruptedError('stopped')
            return {'action':'reply','goal':'','reply':'Wieder aufgenommen.','url':'','objects':{}}
    app=app_fixture(tmp_path)
    app.assistant=SlowAssistant();app.chat.assistant=app.assistant
    app.assistant.model.cancel_event=app.harness.cancel_event
    app.start()
    try:
        cid=app.post('/api/chat',{'message':'Hallo'})['conversation']
        assert entered.wait(3)
        assert app.post('/api/chat/stop',{'id':cid})['stopping']
        deadline=time.monotonic()+3
        while app.active and time.monotonic()<deadline: time.sleep(.02)
        assert app.chat.read(cid)['messages'][-1]['status']=='paused'
        app.post('/api/chat/resume',{'id':cid})
        deadline=time.monotonic()+4
        while app.chat.read(cid)['messages'][-1]['status']=='working' and time.monotonic()<deadline: time.sleep(.02)
        assert app.chat.read(cid)['messages'][-1]['text']=='Wieder aufgenommen.'
        assert len(app.chat.read(cid)['messages'])==2
    finally: app.close()


def test_browser_session_survives_restart_and_can_be_forgotten(tmp_path):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from casajev.browser import BrowserSession
    class Page(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            content=b'<html><body><script>document.body.innerText="value="+(localStorage.getItem("fixture")||"empty");if(location.pathname==="/save"){localStorage.setItem("fixture","pear");document.cookie="fixture=pear;path=/"}</script></body></html>'
            self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(content)
    server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
    base='http://127.0.0.1:'+str(server.server_port)
    browser=BrowserSession(tmp_path, allow_private=True)
    try:
        browser.call('navigate',{'url':base+'/save'})
        browser.close();browser=BrowserSession(tmp_path, allow_private=True)
        assert 'value=pear' in browser.call('read_page',{'url':base+'/'})['text']
        assert browser.state_file.stat().st_mode&0o777==0o600
        browser.call('forget')
        assert not browser.state_file.exists()
        assert 'value=empty' in browser.call('read_page',{'url':base+'/'})['text']
    finally: browser.close();server.shutdown();server.server_close()


def test_skills_reach_bounded_builder_prompt(tmp_path,monkeypatch):
    import casajev.builder as module
    from casajev.builder import CodexBuilder, object_schema, STRING
    library=Library(Store(tmp_path/'state'))
    library.save_skill({'name':'Evidence','description':'User style','instructions':'Unique skill instruction.'})
    builder=CodexBuilder(tmp_path/'builder');builder.binary='/fake/codex';builder.skills_provider=library.enabled_skills
    prompts=[]
    def fake(command,payload,*args,**kwargs):
        prompts.append(payload.decode())
        output=Path(command[command.index('-o')+1]);output.write_text('{"reply":"ok"}')
        return 0,b'',b''
    monkeypatch.setattr(module,'bounded_process',fake)
    assert builder.invoke('Task',object_schema({'reply':STRING}))['reply']=='ok'
    assert 'Unique skill instruction.' in prompts[0]


def test_attached_prose_preserves_all_values():
    context={'trusted_goal':'Summiere nur die positiven Messwerte aus der Notiz.',
             'objects':{'note':{'kind':'text','value':'Messwerte: minus sechs; elf; null; vier; minus zwei.'}}}
    objects={'input':{'kind':'numbers','value':[-6,11,0,4,-2]}}
    assert validate_preparation(context,objects)['count']==5
    with pytest.raises(PreparationError): validate_preparation(context,{'input':{'value':[11,4]}})

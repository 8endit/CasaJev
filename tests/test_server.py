import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import pytest


def test_desktop_browser_bridge_roundtrip_and_token(tmp_path):
    from casajev.browser import DesktopBrowserBridge
    token='desktop-test-token-1234567890'
    bridge=DesktopBrowserBridge(tmp_path,token)
    with ThreadPoolExecutor(max_workers=1) as pool:
        waiting=pool.submit(bridge.for_chat('chat_a').call,'state')
        command=bridge.next(token)
        assert command['action']=='state' and command['conversation']=='chat_a'
        with pytest.raises(PermissionError): bridge.next('wrong')
        bridge.resolve(token,{'id':command['id'],'conversation':'chat_a',
            'result':{'url':'about:blank','title':'','width':900,'height':700,'image':''}})
        assert waiting.result()['width']==900
    bridge.close()


def test_desktop_browser_bridge_rejects_cross_chat_response(tmp_path):
    from casajev.browser import DesktopBrowserBridge
    bridge=DesktopBrowserBridge(tmp_path,'desktop-test-token-1234567890')
    with ThreadPoolExecutor(max_workers=1) as pool:
        waiting=pool.submit(bridge.for_chat('chat_a').call,'state')
        command=bridge.next(bridge.token)
        with pytest.raises(PermissionError):
            bridge.resolve(bridge.token,{'id':command['id'],'conversation':'chat_b','result':{}})
        with pytest.raises(PermissionError): waiting.result()
    bridge.close()


def test_local_server_guards_and_roundtrip(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port = sock.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    proc = subprocess.Popen([sys.executable,'-m','casajev.cli','--home',str(tmp_path),'serve','--demo','--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    def request(path, body=None, headers=None):
        req = urllib.request.Request(origin+path, data=None if body is None else json.dumps(body).encode(), headers=headers or {})
        try:
            with urllib.request.urlopen(req,timeout=2) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code,json.load(exc)
    try:
        for _ in range(60):
            try:
                code, state = request('/api/state')
                break
            except OSError:
                time.sleep(.1)
        else:
            raise AssertionError('Server did not start')
        assert code == 200 and state['mode']=='demo'
        assert request('/api/chats')==(200,{'conversations':[]})
        assert request('/api/state',headers={'Host':'evil.example'})[0] == 403
        task={'goal':'Find exact duplicates','objects':{'csv':{'kind':'csv','description':'synthetic','value':'a\nx\nx\n'}}}
        assert request('/api/tasks',task,{'Content-Type':'application/json'})[0] == 403
        headers={'Content-Type':'application/json','Origin':origin}
        code, conversation = request('/api/chat',{'message':'Hallo gespeicherter Verlauf'},headers)
        assert code == 201
        history=request('/api/chats')[1]['conversations']
        assert history[0]['id']==conversation['conversation']
        assert history[0]['title']=='Hallo gespeicherter Verlauf'
        assert request('/api/chat/'+history[0]['id'])[1]['messages'][0]['text']=='Hallo gespeicherter Verlauf'
        assert request('/api/tasks',{'goal':'','objects':{}},headers)[0] == 400
        code, created = request('/api/tasks',task,headers)
        assert code == 201
        for _ in range(100):
            task_state=request('/api/state')[1]['tasks'][0]
            if task_state['status'] not in ('queued','running'):
                break
            time.sleep(.1)
        assert task_state['status']=='completed'
        assert task_state['result']=={'groups':[[1,2]],'records':2,'extra_duplicates':1}
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait()
        proc.stderr.close()

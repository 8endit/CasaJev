from pathlib import Path

import pytest


def test_headless_browser_sessions_are_isolated_by_chat(tmp_path, monkeypatch):
    import casajev.browser as module

    created=[]
    class FakeSession:
        def __init__(self, root, remember, allow_private):
            self.root=Path(root);self.remember=remember;self.calls=[];created.append(self)
        def call(self, action, data=None):
            self.calls.append((action,data));return {'owner':self.root.name}
        def close(self): pass

    monkeypatch.setattr(module, 'BrowserSession', FakeSession)
    pool=module.BrowserSessions(tmp_path)
    first=pool.for_chat('chat_a')
    second=pool.for_chat('chat_b')
    assert first.call('state')['owner']=='chat_a'
    assert second.call('state')['owner']=='chat_b'
    assert len(created)==2 and created[0] is not created[1]
    assert pool.for_chat('chat_a').call('status')['owner']=='chat_a'
    assert len(created)==2


@pytest.mark.parametrize('identity',[None,'','../other','chat/a','x'*65])
def test_browser_binding_rejects_invalid_chat_ids(tmp_path, identity):
    from casajev.browser import BrowserSessions
    with pytest.raises(ValueError): BrowserSessions(tmp_path).for_chat(identity)


def test_frontend_and_electron_forward_chat_identity():
    root=Path(__file__).parents[1]
    page=(root/'casajev/static/index.html').read_text()
    preload=(root/'desktop/preload.cjs').read_text()
    main=(root/'desktop/main.cjs').read_text()
    assert "api('/api/browser',{action,conversation,...data})" in page
    assert 'conversation:cid' in page
    assert 'clean.conversation = value.conversation' in preload
    assert "partition='persist:casajev-chat-'+conversation" in main
    assert 'command.conversation' in main
    assert "const includeImage=action==='action_state'&&data.include_image!==false" in main
    assert "withTimeout(contents.capturePage(),5000" in main
    assert "error?.code==='ERR_ABORTED'" in main


def test_desktop_bridge_gives_a_useful_timeout_error(tmp_path, monkeypatch):
    import casajev.browser as module

    class ImmediateTimeoutFuture:
        def result(self, timeout):
            raise module.FutureTimeoutError()

    monkeypatch.setattr(module, 'Future', ImmediateTimeoutFuture)
    bridge=module.DesktopBrowserBridge(tmp_path, 'desktop-timeout-token-123456')
    with pytest.raises(RuntimeError, match='Desktop-Browser.*45 Sekunden'):
        bridge.for_chat('chat_a').call('status')

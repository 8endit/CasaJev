"""An actual Chromium session, rendered into the local UI; never a website proxy."""
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
import base64
import queue
import threading
from urllib.parse import urlparse
from pathlib import Path
import ipaddress
import json
import socket
import time
import uuid
import re
from .settings import atomic_json


def browser_identity(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',value):
        raise ValueError('Ungültige Browser-Zuordnung.')
    return value


class BoundBrowser:
    """A browser handle that cannot address any chat except its owner."""
    def __init__(self, parent, identity):
        self.parent = parent
        self.identity = browser_identity(identity)

    def call(self, action, data=None):
        return self.parent.call(action, data, identity=self.identity)


def web_url(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ValueError('Bitte eine Webadresse eingeben.')
    value = value.strip()
    if '://' not in value:
        value = 'https://' + value
    parsed = urlparse(value)
    try:
        parsed.port
    except ValueError:
        raise ValueError('Ungültige Webadresse.') from None
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Nur normale HTTP-/HTTPS-Webadressen sind erlaubt.')
    return value


def public_web_url(value, resolver=socket.getaddrinfo):
    """Reject local/private destinations, including names that resolve to them."""
    value = web_url(value)
    parsed = urlparse(value)
    host = (parsed.hostname or '').rstrip('.').lower()
    if host == 'localhost' or host.endswith('.localhost'):
        raise ValueError('Lokale oder private Netzwerkadressen sind im integrierten Browser gesperrt.')
    try:
        addresses = {row[4][0].split('%', 1)[0] for row in resolver(
            host, parsed.port or 443, type=socket.SOCK_STREAM)}
    except socket.gaierror:
        raise ValueError('Die Webadresse konnte nicht sicher aufgelöst werden.') from None
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError('Lokale oder private Netzwerkadressen sind im integrierten Browser gesperrt.')
    return value


class DesktopBrowserBridge:
    """Thread-safe multiplexed bridge to one isolated Electron view per chat."""
    def __init__(self, root, token, remember=True):
        if not isinstance(token,str) or len(token) < 24:
            raise ValueError('Ungültige Desktop-Sitzung.')
        self.root, self.token, self.remember = Path(root), token, remember
        self.state_file = self.root / 'browser/desktop-sessions'
        self.commands = queue.Queue(maxsize=30)
        self.pending = {}
        self.identities = set()
        self.gate = threading.Lock()

    def for_chat(self, identity):
        return BoundBrowser(self, identity)

    @property
    def saved(self):
        return self.state_file.exists() and any(self.state_file.glob('*.json'))

    def call(self, action, data=None, identity=None):
        identity = browser_identity(identity)
        if action == 'close':
            return {'closed':True}
        payload=dict(data or {})
        payload.pop('conversation', None)
        if action in ('navigate','read_page') and (action == 'navigate' or payload.get('url')):
            payload['url']=public_web_url(payload.get('url'))
        request_id=uuid.uuid4().hex
        future=Future()
        with self.gate:
            self.pending[request_id]=(future,identity)
            self.identities.add(identity)
        try:
            self.commands.put_nowait({'id':request_id,'conversation':identity,'action':action,'data':payload})
            try:
                return future.result(timeout=45)
            except FutureTimeoutError:
                raise RuntimeError(
                    'Der Desktop-Browser hat innerhalb von 45 Sekunden nicht geantwortet. '
                    'Bitte CasaJev neu starten und den Auftrag erneut versuchen.'
                ) from None
        except Exception:
            with self.gate: self.pending.pop(request_id,None)
            raise

    def next(self, token, timeout=.8):
        if token != self.token: raise PermissionError('Ungültige Desktop-Sitzung.')
        try: return self.commands.get(timeout=max(0,min(2,float(timeout))))
        except queue.Empty: return None

    def resolve(self, token, body):
        if token != self.token: raise PermissionError('Ungültige Desktop-Sitzung.')
        if not isinstance(body,dict) or not isinstance(body.get('id'),str):
            raise ValueError('Ungültige Desktop-Antwort.')
        with self.gate: pending=self.pending.pop(body['id'],None)
        if pending is None: raise KeyError('Desktop-Befehl ist nicht mehr aktiv.')
        future,identity=pending
        if body.get('conversation') != identity:
            future.set_exception(PermissionError('Browser-Antwort gehört zu einem anderen Chat.'))
            raise PermissionError('Browser-Antwort gehört zu einem anderen Chat.')
        if body.get('error'):
            future.set_exception(RuntimeError(str(body['error'])[:500]))
        else:
            result=body.get('result')
            if not isinstance(result,dict): raise ValueError('Desktop-Ergebnis fehlt.')
            if self.remember and body.get('persisted'):
                self.state_file.mkdir(parents=True,exist_ok=True)
                atomic_json(self.state_file / (identity + '.json'), {'saved':True})
            if body.get('forgotten'):
                (self.state_file / (identity + '.json')).unlink(missing_ok=True)
            future.set_result(result)
        return {'accepted':True}

    def forget_all(self):
        saved={path.stem for path in self.state_file.glob('*.json')} if self.state_file.exists() else set()
        for identity in sorted(self.identities | saved):
            self.call('forget', identity=identity)

    def close(self):
        with self.gate:
            waiting=list(self.pending.values());self.pending.clear()
        for future in waiting:
            target=future[0] if isinstance(future,tuple) else future
            if not target.done(): target.set_exception(InterruptedError('Desktop geschlossen.'))


class BrowserSession:
    def __init__(self, root=None, remember=True, allow_private=False):
        self.state_file = Path(root) / 'browser/session.json' if root else None
        self.remember = remember
        self.allow_private = allow_private
        self.queue = queue.Queue(maxsize=20)
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()

    def call(self, action, data=None):
        future = Future()
        self.queue.put_nowait((action, data or {}, future))
        return future.result(timeout=35)

    def close(self):
        try:
            self.call('close')
        except Exception:
            pass

    def worker(self):
        playwright = browser = context = page = None
        while True:
            action, data, future = self.queue.get()
            try:
                if action == 'close':
                    if browser:
                        browser.close()
                    if playwright:
                        playwright.stop()
                    future.set_result({'closed': True})
                    return
                if action == 'forget':
                    if self.state_file: self.state_file.unlink(missing_ok=True)
                    if context: context.close()
                    page = context = None
                    future.set_result({'forgotten': True})
                    continue
                if page is None:
                    from playwright.sync_api import sync_playwright
                    if playwright is None:
                        playwright = sync_playwright().start()
                        browser = playwright.chromium.launch(headless=True, chromium_sandbox=True)
                    options = {'viewport':{'width':1100,'height':800}, 'accept_downloads':False, 'locale':'de-DE'}
                    if self.remember and self.state_file and self.state_file.exists():
                        options['storage_state'] = json.loads(self.state_file.read_text())
                    context = browser.new_context(**options)
                    if not self.allow_private:
                        def route_request(route):
                            request_url = route.request.url
                            if urlparse(request_url).scheme in ('http', 'https'):
                                try:
                                    public_web_url(request_url)
                                except ValueError:
                                    route.abort('blockedbyclient')
                                    return
                            route.continue_()
                        context.route('**/*', route_request)
                    page = context.new_page()
                    page.set_default_timeout(15000)
                    # A normal link that opens a new tab becomes the visible page.
                    def popup(new_page):
                        nonlocal page
                        page = new_page
                        page.set_default_timeout(15000)
                    context.on('page', popup)
                if action == 'status':
                    future.set_result({'url':page.url,'title':page.title()})
                    continue
                if action in ('navigate','read_page') and (action == 'navigate' or data.get('url')):
                    target = web_url(data.get('url')) if self.allow_private else public_web_url(data.get('url'))
                    page.goto(target, wait_until='domcontentloaded', timeout=20000)
                elif action == 'back':
                    page.go_back(wait_until='domcontentloaded',timeout=15000)
                elif action == 'forward':
                    page.go_forward(wait_until='domcontentloaded',timeout=15000)
                elif action == 'reload':
                    page.reload(wait_until='domcontentloaded',timeout=15000)
                elif action == 'click':
                    x, y = float(data['x']), float(data['y'])
                    size = page.viewport_size
                    if data.get('basis_width') and data.get('basis_height'):
                        x *= size['width'] / float(data['basis_width'])
                        y *= size['height'] / float(data['basis_height'])
                    if not 0 <= x <= size['width'] or not 0 <= y <= size['height']:
                        raise ValueError('Ungültige Browserposition.')
                    page.mouse.click(x,y)
                elif action == 'move':
                    x, y = float(data['x']), float(data['y'])
                    size = page.viewport_size
                    if data.get('basis_width') and data.get('basis_height'):
                        x *= size['width'] / float(data['basis_width'])
                        y *= size['height'] / float(data['basis_height'])
                    if not 0 <= x <= size['width'] or not 0 <= y <= size['height']:
                        raise ValueError('Ungültige Browserposition.')
                    page.mouse.move(x,y,steps=max(1,min(30,int(data.get('steps',1)))))
                elif action == 'mouse_down':
                    page.mouse.down()
                elif action == 'mouse_up':
                    page.mouse.up()
                elif action == 'scroll':
                    page.mouse.wheel(0,max(-1500,min(1500,float(data['delta']))))
                elif action == 'text':
                    value = data.get('text','')
                    if not isinstance(value,str) or len(value)>12000:
                        raise ValueError('Eingabe zu lang.')
                    page.keyboard.insert_text(value)
                elif action == 'key':
                    keys={'Enter','Backspace','Delete','Tab','Escape','Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End','PageUp','PageDown','ControlOrMeta+A','z','x','c'}
                    if data.get('key') not in keys:
                        raise ValueError('Taste nicht unterstützt.')
                    page.keyboard.press(data['key'])
                elif action == 'control_batch':
                    kind=data.get('kind')
                    if kind == 'clicks':
                        points=data.get('points',[])
                        if not isinstance(points,list) or not 2<=len(points)<=8:
                            raise ValueError('Ungültige lokale Klickfolge.')
                        size=page.viewport_size
                        width=float(data.get('basis_width') or size['width']);height=float(data.get('basis_height') or size['height'])
                        interval=max(.02,min(.5,float(data.get('interval',.12))))
                        for point in points:
                            x=float(point['x'])*size['width']/width;y=float(point['y'])*size['height']/height
                            if not 0<=x<=size['width'] or not 0<=y<=size['height']:
                                raise ValueError('Ungültige Browserposition in Klickfolge.')
                            page.mouse.click(x,y);time.sleep(interval)
                    elif kind == 'keys':
                        keys=data.get('keys',[])
                        allowed={'Enter','Backspace','Delete','Tab','Escape','Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End','PageUp','PageDown','ControlOrMeta+A','z','x','c'}
                        if not isinstance(keys,list) or not 1<=len(keys)<=40 or any(key not in allowed for key in keys):
                            raise ValueError('Ungültige lokale Tastenfolge.')
                        interval=max(.02,min(.5,float(data.get('interval',.08))))
                        for key in keys:
                            page.keyboard.press(key);time.sleep(interval)
                    elif kind == 'pointer_path':
                        points=data.get('points',[])
                        if not isinstance(points,list) or not 2<=len(points)<=16:
                            raise ValueError('Ungültiger lokaler Steuerpfad.')
                        size=page.viewport_size
                        width=float(data.get('basis_width') or size['width']);height=float(data.get('basis_height') or size['height'])
                        scaled=[(float(point['x'])*size['width']/width,float(point['y'])*size['height']/height) for point in points]
                        if any(not 0<=x<=size['width'] or not 0<=y<=size['height'] for x,y in scaled):
                            raise ValueError('Ungültige Browserposition im Steuerpfad.')
                        repeat=max(1,min(4,int(data.get('repeat',1))));path=scaled*repeat
                        duration=max(.25,min(12,float(data.get('duration',3))));segments=max(1,len(path)-1)
                        for start,end in zip(path,path[1:]):
                            steps=max(2,int(duration*20/segments))
                            for index in range(1,steps+1):
                                ratio=index/steps
                                page.mouse.move(start[0]+(end[0]-start[0])*ratio,start[1]+(end[1]-start[1])*ratio)
                                time.sleep(duration/(segments*steps))
                    else:
                        raise ValueError('Unbekannte lokale Steuerfolge.')
                elif action == 'resize':
                    page.set_viewport_size({'width':max(500,min(1600,int(data['width']))),
                                            'height':max(350,min(1200,int(data['height'])))})
                elif action == 'wait':
                    time.sleep(max(0,min(2,float(data.get('seconds',.25)))))
                elif action not in ('state','action_state','content','read_page','search_results'):
                    raise ValueError('Unknown browser action')
                if action in ('content','read_page','search_results'):
                    if page.url == 'about:blank':
                        raise ValueError('Es ist noch keine Seite geöffnet. Bitte eine Webadresse angeben.')
                    result={'url':page.url, 'title':page.title(),
                            'text':page.locator('body').inner_text(timeout=5000)[:40000]}
                    if action == 'search_results':
                        # Heading-bearing result links, not arbitrary buttons or page instructions.
                        raw=page.locator('a').evaluate_all('''anchors => anchors.filter(a => a.querySelector('h3'))
                            .map(a => ({title:a.querySelector('h3').innerText, url:a.href})).slice(0,30)''')
                        links=[]
                        for item in raw:
                            try:
                                url=web_url(item['url']) if self.allow_private else public_web_url(item['url'])
                            except ValueError:
                                continue
                            host=urlparse(url).hostname or ''
                            if host=='google.com' or host.endswith('.google.com') or not item['title'].strip():
                                continue
                            if url not in [x['url'] for x in links]:
                                links.append({'title':item['title'][:300],'url':url})
                        result['links']=links[:10]
                else:
                    result={'url':page.url,'title':page.title(),'width':page.viewport_size['width'],
                            'height':page.viewport_size['height'],'image':''}
                    if action != 'action_state' or data.get('include_image', True):
                        result['image']=base64.b64encode(
                            page.screenshot(type='jpeg',quality=80,timeout=10000)).decode()
                    if action == 'action_state':
                        result['text'] = page.locator('body').inner_text(timeout=5000)[:12000] if page.url != 'about:blank' else ''
                        result['elements'] = page.locator('a,button,input,textarea,select,[role="button"],[tabindex]').evaluate_all('''nodes => nodes
                            .filter(node => { const r=node.getBoundingClientRect(); const s=getComputedStyle(node);
                                return r.width>2 && r.height>2 && s.visibility!=="hidden" && s.display!=="none"; })
                            .slice(0,80).map((node,index) => { const r=node.getBoundingClientRect();
                                const labels=[...(node.labels||[])].map(label=>label.innerText).join(" ");
                                const contextual=node.closest("label")?.innerText||(node.nextElementSibling?.matches("label")?node.nextElementSibling.innerText:"")||node.closest("li,tr")?.querySelector("label")?.innerText||"";
                                const aria=node.getAttribute("aria-label")||"";
                                const label=(node.type==="checkbox"||node.type==="radio")?(labels||contextual||aria):(aria||labels||contextual);
                                return {
                                index, tag:node.tagName.toLowerCase(), role:node.getAttribute("role")||"",
                                type:(node.getAttribute("type")||"").toLowerCase(),
                                href:node.tagName.toLowerCase()==="a"?(node.getAttribute("href")||"").slice(0,500):"",
                                name:(label||node.getAttribute("placeholder")||node.innerText||(node.type!=="password"?node.value:"")||node.getAttribute("title")||"").trim().slice(0,160),
                                value:node.type==="password"?"":String(node.value||"").slice(0,300),
                                checked:("checked" in node)?Boolean(node.checked):null,
                                selected:("selected" in node)?Boolean(node.selected):null,
                                disabled:Boolean(node.disabled), focused:document.activeElement===node,
                                x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2),
                                width:Math.round(r.width), height:Math.round(r.height)}; })''')
                        result['surfaces'] = page.locator('canvas,iframe,video').evaluate_all('''nodes => nodes.map(node => ({
                            tag:node.tagName.toLowerCase(), title:(node.title||node.getAttribute("aria-label")||"").slice(0,160)
                        })).slice(0,20)''')
                if self.remember and self.state_file and action != 'state':
                    atomic_json(self.state_file, context.storage_state(indexed_db=True))
                future.set_result(result)
            except Exception as exc:
                message=str(exc).split('Call log:')[0][:500]
                if 'Executable doesn' in message:
                    message='Der Browser muss einmal installiert werden: uv run playwright install chromium'
                future.set_exception(RuntimeError(message))
            finally:
                self.queue.task_done()


class BrowserSessions:
    """Lazy pool of fully isolated Playwright contexts, keyed by chat id."""
    def __init__(self, root, remember=True, allow_private=False):
        self.root=Path(root)
        self.state_file=self.root / 'browser/chats'
        self._remember=remember
        self.allow_private=allow_private
        self.sessions={}
        self.gate=threading.Lock()

    @property
    def remember(self):
        return self._remember

    @property
    def saved(self):
        return self.state_file.exists() and any(self.state_file.glob('*/browser/session.json'))

    @remember.setter
    def remember(self, value):
        self._remember=bool(value)
        with self.gate:
            for session in self.sessions.values(): session.remember=self._remember

    def for_chat(self, identity):
        return BoundBrowser(self, identity)

    def call(self, action, data=None, identity=None):
        identity=browser_identity(identity)
        with self.gate:
            session=self.sessions.get(identity)
            if session is None:
                session=BrowserSession(self.state_file / identity, self._remember, self.allow_private)
                self.sessions[identity]=session
        payload=dict(data or {})
        payload.pop('conversation',None)
        return session.call(action,payload)

    def forget_all(self):
        saved={path.name for path in self.state_file.iterdir() if path.is_dir()} if self.state_file.exists() else set()
        with self.gate: identities=set(self.sessions) | saved
        for identity in sorted(identities): self.call('forget',identity=identity)

    def close(self):
        with self.gate:
            sessions=list(self.sessions.values());self.sessions.clear()
        for session in sessions: session.close()

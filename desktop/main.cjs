const { app, BrowserWindow, WebContentsView, ipcMain, session, dialog } = require('electron');
const { spawn, spawnSync } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const dns = require('node:dns').promises;
const net = require('node:net');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

app.setName('CasaJev');
app.enableSandbox();
let windowRef, backend, baseUrl;
let closing = false;
let staticWatcher = null;
const desktopToken = randomBytes(32).toString('hex');
const hostCache = new Map();
const browserViews = new Map();
const configuredPartitions = new Set();

function privateAddress(address) {
  if (net.isIP(address) === 4) {
    const p = address.split('.').map(Number);
    return p[0] === 10 || p[0] === 127 || p[0] === 0 ||
      (p[0] === 169 && p[1] === 254) || (p[0] === 172 && p[1] >= 16 && p[1] <= 31) ||
      (p[0] === 192 && p[1] === 168) || p[0] >= 224;
  }
  if (net.isIP(address) === 6) {
    const value = address.toLowerCase().split('%')[0];
    return value === '::1' || value === '::' || value.startsWith('fc') || value.startsWith('fd') ||
      value.startsWith('fe8') || value.startsWith('fe9') || value.startsWith('fea') || value.startsWith('feb');
  }
  return true;
}

async function publicRemoteUrl(value) {
  let parsed;
  try { parsed = new URL(value); } catch { return false; }
  if (!['http:','https:'].includes(parsed.protocol) || parsed.username || parsed.password) return false;
  const host = parsed.hostname.replace(/\.$/,'').toLowerCase();
  if (host === 'localhost' || host.endsWith('.localhost')) return false;
  if (net.isIP(host)) return !privateAddress(host);
  const cached = hostCache.get(host);
  if (cached && cached.until > Date.now()) return cached.allowed;
  try {
    const answers = await dns.lookup(host,{all:true});
    const allowed = answers.length > 0 && answers.every(item => !privateAddress(item.address));
    hostCache.set(host,{allowed,until:Date.now()+60000});
    return allowed;
  } catch {
    hostCache.set(host,{allowed:false,until:Date.now()+10000});
    return false;
  }
}

function findUv() {
  const candidates = [process.env.CASAJEV_UV, path.join(os.homedir(),'.local/bin/uv'),
    '/opt/homebrew/bin/uv','/usr/local/bin/uv','uv'].filter(Boolean);
  return candidates.find(candidate => candidate === 'uv' || fs.existsSync(candidate)) || 'uv';
}

function packagedPython(projectRoot) {
  const environment=path.join(app.getPath('userData'),'python-env');
  const marker=path.join(environment,'.casajev-version');
  const python=path.join(environment,'bin','python');
  const executable=path.join(environment,'bin','casajev');
  if (fs.existsSync(marker) && fs.readFileSync(marker,'utf8').trim()==='0.5.1-desktop-2' && fs.existsSync(executable))
    return executable;
  fs.rmSync(environment,{recursive:true,force:true});
  let result=spawnSync(findUv(),['venv','--python','3.11',environment],{encoding:'utf8'});
  if (result.status!==0) throw new Error('Die lokale Python-Umgebung konnte nicht erstellt werden. '+(result.stderr||''));
  const wheel=fs.readdirSync(path.join(projectRoot,'dist')).find(name=>name.startsWith('casajev-0.5.1-')&&name.endsWith('.whl'));
  if (!wheel) throw new Error('Das CasaJev-Wheel fehlt im App-Bundle.');
  result=spawnSync(findUv(),['pip','install','--python',python,path.join(projectRoot,'dist',wheel),
    'laya==0.3.4','numpy>=1.26,<2','transformers>=4.45,<5','torch==2.2.2'],{encoding:'utf8'});
  if (result.status!==0) throw new Error('Die lokalen CasaJev-Abhängigkeiten konnten nicht eingerichtet werden. '+(result.stderr||''));
  fs.writeFileSync(marker,'0.5.1-desktop-2\n',{mode:0o600});
  return executable;
}

function startBackend() {
  const projectRoot = app.isPackaged ? path.join(process.resourcesPath,'casajev') : path.resolve(__dirname,'..');
  const stateHome = process.env.CASAJEV_HOME || path.join(app.getPath('userData'),'state');
  fs.mkdirSync(stateHome,{recursive:true,mode:0o700});
  const environment = {...process.env,
    CASAJEV_DESKTOP_TOKEN:desktopToken,
    PYTHONDONTWRITEBYTECODE:'1',
    PATH:[path.dirname(findUv()),path.join(os.homedir(),'.local/bin'),'/opt/homebrew/bin','/usr/local/bin',process.env.PATH||''].join(path.delimiter)};
  return new Promise((resolve,reject) => {
    let command,args;
    try {
      if (app.isPackaged) { command=packagedPython(projectRoot);args=['--home',stateHome,'serve','--port','0']; }
      else { command=findUv();args=['run','--project',projectRoot,'casajev','--home',stateHome,'serve','--port','0']; }
    } catch (error) { reject(error);return; }
    backend = spawn(command,args,
      {cwd:projectRoot,env:environment,stdio:['ignore','pipe','pipe']});
    let errors='';
    const timer=setTimeout(()=>reject(new Error('Der lokale CasaJev-Dienst ist nicht rechtzeitig gestartet.')),60000);
    backend.stdout.on('data',chunk => {
      const match=chunk.toString().match(/CasaJev: (http:\/\/127\.0\.0\.1:\d+)/);
      if (match) { clearTimeout(timer); baseUrl=match[1]; resolve(baseUrl); }
    });
    backend.stderr.on('data',chunk => { errors=(errors+chunk.toString()).slice(-4000); });
    backend.on('error',error => { clearTimeout(timer); reject(error); });
    backend.on('exit',code => {
      if (!closing && windowRef && !windowRef.isDestroyed())
        dialog.showErrorBox('CasaJev wurde beendet', errors || ('Der lokale Dienst endete mit Code '+code+'.'));
    });
  });
}

function configureRemoteSession(partition) {
  if (configuredPartitions.has(partition)) return;
  configuredPartitions.add(partition);
  const remote=session.fromPartition(partition);
  remote.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
  remote.setPermissionCheckHandler(()=>false);
  remote.on('will-download',event=>event.preventDefault());
  remote.webRequest.onBeforeRequest((details,callback) => {
    if (/^(about:blank|data:|blob:)/.test(details.url)) { callback({cancel:false}); return; }
    publicRemoteUrl(details.url).then(allowed=>callback({cancel:!allowed})).catch(()=>callback({cancel:true}));
  });
}

function browserRecord(conversation) {
  if (!/^[a-zA-Z0-9_-]{1,64}$/.test(conversation || '')) throw new Error('Ungültige Browser-Zuordnung.');
  const existing=browserViews.get(conversation);
  if (existing) return existing;
  const partition='persist:casajev-chat-'+conversation;
  configureRemoteSession(partition);
  const view=new WebContentsView({webPreferences:{partition,
    nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,
    allowRunningInsecureContent:false}});
  windowRef.contentView.addChildView(view);
  view.setBounds({x:2000,y:60,width:900,height:700});
  view.setVisible(false);
  view.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  view.webContents.on('will-navigate',(event,url)=>{
    publicRemoteUrl(url).then(allowed=>{ if (!allowed && !view.webContents.isDestroyed()) view.webContents.stop(); });
  });
  const record={view,lastPointer:{x:10,y:10},visible:false};
  browserViews.set(conversation,record);
  return record;
}

function createWindow() {
  windowRef=new BrowserWindow({width:1400,height:900,minWidth:900,minHeight:620,
    title:'CasaJev',backgroundColor:'#19191b',show:false,
    webPreferences:{preload:path.join(__dirname,'preload.cjs'),nodeIntegration:false,
      contextIsolation:true,sandbox:true,webSecurity:true}});
  windowRef.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  windowRef.loadURL(baseUrl);
  windowRef.once('ready-to-show',()=>windowRef.show());
  windowRef.on('closed',()=>{windowRef=null;});
}

function enableStaticHotReload() {
  if (app.isPackaged || process.env.CASAJEV_DEV_HOT !== '1' || staticWatcher) return;
  const staticRoot=path.resolve(__dirname,'..','casajev','static');
  let timer;
  staticWatcher=fs.watch(staticRoot,{recursive:true},()=>{
    clearTimeout(timer);
    timer=setTimeout(()=>{
      if (windowRef&&!windowRef.isDestroyed()) windowRef.webContents.reloadIgnoringCache();
    },120);
  });
}

function sendKey(contents,key) {
  windowRef.show();windowRef.focus();contents.focus();
  const modifiers = key === 'ControlOrMeta+A' ? [process.platform==='darwin'?'meta':'control'] : [];
  const code = key === 'ControlOrMeta+A' ? 'A' : key;
  contents.sendInputEvent({type:'keyDown',keyCode:code,modifiers});
  contents.sendInputEvent({type:'keyUp',keyCode:code,modifiers});
}

const supportedKeys=new Set(['Enter','Backspace','Delete','Tab','Escape','Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End','PageUp','PageDown','ControlOrMeta+A','z','x','c']);

async function loadRemote(contents,url) {
  let timedOut=false,timer;
  const navigation=contents.loadURL(url).catch(error=>{if (!timedOut) throw error;});
  try {
    await Promise.race([navigation,new Promise((_,reject)=>{timer=setTimeout(()=>{timedOut=true;reject(new Error('Die Webseite lädt zu lange.'));},20000);})]);
  } catch (error) {
    const current=contents.getURL();
    const redirected=error?.code==='ERR_ABORTED'||/ERR_ABORTED/.test(String(error?.message||error));
    // Chromium reports ERR_ABORTED when a site replaces the requested URL during
    // navigation. If a real web page is already present, this is a redirect rather
    // than a failed load (Google Search commonly behaves this way).
    if ((!timedOut&&!redirected)||!current||current==='about:blank') throw error;
    contents.stop();
  } finally { clearTimeout(timer); }
}

function withTimeout(promise,milliseconds,message) {
  let timer;
  return Promise.race([
    promise,
    new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(message)),milliseconds);})
  ]).finally(()=>clearTimeout(timer));
}

async function pageState(record,conversation,action,includeImage=true) {
  const browserView=record.view;
  const contents=browserView.webContents;
  let bounds=browserView.getBounds();
  let image;
  try { if (includeImage) image=await withTimeout(contents.capturePage(),5000,'Die Browseransicht konnte nicht rechtzeitig erfasst werden.'); }
  catch (error) { if (action==='action_state') throw error; }
  if (includeImage && action==='action_state' && (!image || image.isEmpty())) {
    windowRef.webContents.send('casajev-show-browser',conversation);
    if (!record.visible) browserView.setVisible(true);
    await new Promise(resolve=>setTimeout(resolve,250));
    bounds=browserView.getBounds();
    image=await withTimeout(contents.capturePage(),5000,'Die sichtbare Browseransicht konnte nicht rechtzeitig erfasst werden.');
    if (!record.visible) browserView.setVisible(false);
    if (image.isEmpty()) throw new Error('Die sichtbare Desktop-Browserfläche ist noch nicht verfügbar.');
  }
  const result={url:contents.getURL()||'about:blank',title:contents.getTitle()||'',
    width:bounds.width,height:bounds.height,image:image?image.toJPEG(80).toString('base64'):''};
  if (action === 'action_state') {
    const details=await contents.executeJavaScript(`(() => ({
      text:(document.body?.innerText||'').slice(0,12000),
      elements:[...document.querySelectorAll('a,button,input,textarea,select,[role="button"],[tabindex]')]
        .filter(node=>{const r=node.getBoundingClientRect(),s=getComputedStyle(node);return r.width>2&&r.height>2&&s.visibility!=='hidden'&&s.display!=='none'})
        .slice(0,80).map((node,index)=>{const r=node.getBoundingClientRect(),labels=[...(node.labels||[])].map(label=>label.innerText).join(' '),contextual=node.closest('label')?.innerText||(node.nextElementSibling?.matches('label')?node.nextElementSibling.innerText:'')||node.closest('li,tr')?.querySelector('label')?.innerText||'',aria=node.getAttribute('aria-label')||'',label=(node.type==='checkbox'||node.type==='radio')?(labels||contextual||aria):(aria||labels||contextual);return {index,tag:node.tagName.toLowerCase(),role:node.getAttribute('role')||'',type:(node.getAttribute('type')||'').toLowerCase(),href:node.tagName.toLowerCase()==='a'?(node.getAttribute('href')||'').slice(0,500):'',name:(label||node.getAttribute('placeholder')||node.innerText||(node.type!=='password'?node.value:'')||node.getAttribute('title')||'').trim().slice(0,160),value:node.type==='password'?'':String(node.value||'').slice(0,300),checked:('checked' in node)?Boolean(node.checked):null,selected:('selected' in node)?Boolean(node.selected):null,disabled:Boolean(node.disabled),focused:document.activeElement===node,x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),width:Math.round(r.width),height:Math.round(r.height)}}),
      surfaces:[...document.querySelectorAll('canvas,iframe,video')].slice(0,20).map(node=>({tag:node.tagName.toLowerCase(),title:(node.title||node.getAttribute('aria-label')||'').slice(0,160)}))
    }))()` ,true);
    result.text=details.text;result.elements=details.elements;result.surfaces=details.surfaces;
  }
  return result;
}

async function execute(command) {
  const {action,data}=command;
  const conversation=command.conversation;
  const record=browserRecord(conversation),browserView=record.view,contents=browserView.webContents;
  if (action === 'status') {
    return {result:{url:contents.getURL()||'about:blank',title:contents.getTitle()||''},persisted:false};
  }
  if (action === 'navigate' || (action === 'read_page' && data.url)) {
    if (!await publicRemoteUrl(data.url)) throw new Error('Lokale oder private Netzwerkadressen sind gesperrt.');
    windowRef.webContents.send('casajev-show-browser',conversation);
    await new Promise(resolve=>setTimeout(resolve,80));
    await loadRemote(contents,data.url);
  } else if (action === 'back' && contents.canGoBack()) contents.goBack();
  else if (action === 'forward' && contents.canGoForward()) contents.goForward();
  else if (action === 'reload') contents.reload();
  else if (action === 'click') {
    const bounds=browserView.getBounds(),scaleX=data.basis_width?bounds.width/data.basis_width:1,scaleY=data.basis_height?bounds.height/data.basis_height:1;
    record.lastPointer={x:Math.round(data.x*scaleX),y:Math.round(data.y*scaleY)};
    windowRef.show();windowRef.focus();contents.focus();contents.sendInputEvent({type:'mouseDown',...record.lastPointer,button:'left',clickCount:1});
    contents.sendInputEvent({type:'mouseUp',...record.lastPointer,button:'left',clickCount:1});
  } else if (action === 'move') {
    const bounds=browserView.getBounds(),scaleX=data.basis_width?bounds.width/data.basis_width:1,scaleY=data.basis_height?bounds.height/data.basis_height:1;
    record.lastPointer={x:Math.round(data.x*scaleX),y:Math.round(data.y*scaleY)};
    windowRef.show();windowRef.focus();contents.focus();contents.sendInputEvent({type:'mouseMove',...record.lastPointer});
  }
  else if (action === 'mouse_down') { windowRef.focus();contents.focus();contents.sendInputEvent({type:'mouseDown',...record.lastPointer,button:'left',clickCount:1}); }
  else if (action === 'mouse_up') { windowRef.focus();contents.focus();contents.sendInputEvent({type:'mouseUp',...record.lastPointer,button:'left',clickCount:1}); }
  else if (action === 'scroll') { windowRef.focus();contents.focus();contents.sendInputEvent({type:'mouseWheel',x:10,y:10,deltaX:0,deltaY:Math.round(data.delta)}); }
  else if (action === 'text') { windowRef.focus();contents.focus();await contents.insertText(data.text); }
  else if (action === 'key') sendKey(contents,data.key);
  else if (action === 'control_batch') {
    if (data.kind === 'clicks') {
      if (!Array.isArray(data.points)||data.points.length<2||data.points.length>8) throw new Error('Ungültige lokale Klickfolge.');
      const bounds=browserView.getBounds(),scaleX=data.basis_width?bounds.width/data.basis_width:1,scaleY=data.basis_height?bounds.height/data.basis_height:1;
      const points=data.points.map(point=>({x:Math.round(Number(point.x)*scaleX),y:Math.round(Number(point.y)*scaleY)}));
      if (points.some(point=>!Number.isFinite(point.x)||!Number.isFinite(point.y)||point.x<0||point.y<0||point.x>bounds.width||point.y>bounds.height)) throw new Error('Ungültige Browserposition in Klickfolge.');
      const interval=Math.max(20,Math.min(500,Number(data.interval||.12)*1000));
      windowRef.show();windowRef.focus();contents.focus();
      for (const point of points) {
        record.lastPointer=point;contents.sendInputEvent({type:'mouseDown',...point,button:'left',clickCount:1});
        contents.sendInputEvent({type:'mouseUp',...point,button:'left',clickCount:1});
        await new Promise(resolve=>setTimeout(resolve,interval));
      }
    } else if (data.kind === 'keys') {
      if (!Array.isArray(data.keys)||data.keys.length<1||data.keys.length>40||data.keys.some(key=>!supportedKeys.has(key))) throw new Error('Ungültige lokale Tastenfolge.');
      const interval=Math.max(20,Math.min(500,Number(data.interval||.08)*1000));
      for (const key of data.keys) { sendKey(contents,key);await new Promise(resolve=>setTimeout(resolve,interval)); }
    } else if (data.kind === 'pointer_path') {
      if (!Array.isArray(data.points)||data.points.length<2||data.points.length>16) throw new Error('Ungültiger lokaler Steuerpfad.');
      const bounds=browserView.getBounds(),scaleX=data.basis_width?bounds.width/data.basis_width:1,scaleY=data.basis_height?bounds.height/data.basis_height:1;
      const points=data.points.map(point=>({x:Math.round(Number(point.x)*scaleX),y:Math.round(Number(point.y)*scaleY)}));
      if (points.some(point=>!Number.isFinite(point.x)||!Number.isFinite(point.y)||point.x<0||point.y<0||point.x>bounds.width||point.y>bounds.height)) throw new Error('Ungültige Browserposition im Steuerpfad.');
      const repeat=Math.max(1,Math.min(4,Number(data.repeat||1))),path=[];
      for (let index=0;index<repeat;index+=1) path.push(...points);
      const duration=Math.max(250,Math.min(12000,Number(data.duration||3)*1000)),segments=Math.max(1,path.length-1),steps=Math.max(2,Math.floor(duration/segments/50));
      windowRef.show();windowRef.focus();contents.focus();
      for (let segment=0;segment<path.length-1;segment+=1) for (let step=1;step<=steps;step+=1) {
        const ratio=step/steps,start=path[segment],end=path[segment+1];
        record.lastPointer={x:Math.round(start.x+(end.x-start.x)*ratio),y:Math.round(start.y+(end.y-start.y)*ratio)};
        contents.sendInputEvent({type:'mouseMove',...record.lastPointer});
        await new Promise(resolve=>setTimeout(resolve,duration/segments/steps));
      }
    } else throw new Error('Unbekannte lokale Steuerfolge.');
    return {result:{url:contents.getURL()||'about:blank',title:contents.getTitle()||'',batched:true},persisted:true};
  }
  else if (action === 'wait') await new Promise(resolve=>setTimeout(resolve,Math.max(0,Math.min(2000,data.seconds*1000))));
  else if (action === 'forget') {
    await contents.session.clearStorageData(); await contents.session.clearCache(); await contents.loadURL('about:blank');
    return {result:await pageState(record,conversation,'state',false),forgotten:true};
  } else if (!['state','action_state','content','read_page','search_results','resize'].includes(action)) throw new Error('Unbekannter Desktop-Browserbefehl.');
  if (['content','read_page','search_results'].includes(action)) {
    const result=await contents.executeJavaScript(`(() => ({url:location.href,title:document.title,text:(document.body?.innerText||'').slice(0,40000)}))()`,true);
    if (action === 'search_results') result.links=await contents.executeJavaScript(`[...document.querySelectorAll('a')].filter(a=>a.querySelector('h3')).slice(0,10).map(a=>({title:a.querySelector('h3').innerText,url:a.href}))`,true);
    return {result,persisted:true};
  }
  // The desktop UI renders the live WebContentsView itself. Normal navigation/state
  // responses therefore need metadata only; capturing a hidden view can otherwise
  // stall the entire command driver. Action planning explicitly requests pixels.
  const includeImage=action==='action_state'&&data.include_image!==false;
  return {result:await pageState(record,conversation,action==='action_state'?'action_state':'state',includeImage),persisted:action!=='state'};
}

async function driverLoop() {
  while (!closing) {
    try {
      const response=await fetch(baseUrl+'/api/desktop/next?timeout=.8',{headers:{'X-CasaJev-Desktop-Token':desktopToken}});
      const {command}=await response.json();
      if (!command) continue;
      let body={id:command.id,conversation:command.conversation};
      try { body={...body,...await execute(command)}; } catch (error) { body.error=String(error.message||error); }
      await fetch(baseUrl+'/api/desktop/result',{method:'POST',headers:{'Content-Type':'application/json','X-CasaJev-Desktop-Token':desktopToken},body:JSON.stringify(body)});
    } catch (error) {
      if (!closing) await new Promise(resolve=>setTimeout(resolve,300));
    }
  }
}

ipcMain.on('casajev-browser-bounds',(event,value)=>{
  if (!windowRef || event.sender !== windowRef.webContents) return;
  let record;
  try { record=browserRecord(value.conversation); } catch { return; }
  for (const [identity,item] of browserViews) {
    if (identity!==value.conversation) { item.visible=false;item.view.setVisible(false); }
  }
  const safe={x:value.visible===true?Math.max(0,value.x):windowRef.getBounds().width+100,
    y:Math.max(0,value.y),width:Math.max(320,value.width),height:Math.max(240,value.height)};
  record.visible=value.visible===true;record.view.setBounds(safe);record.view.setVisible(record.visible);
});

app.whenReady().then(async()=>{
  try { await startBackend();createWindow();enableStaticHotReload();driverLoop(); }
  catch (error) { dialog.showErrorBox('CasaJev konnte nicht starten',String(error.message||error));app.quit(); }
});
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{closing=true;if(staticWatcher)staticWatcher.close();if(backend&&!backend.killed)backend.kill('SIGTERM');});

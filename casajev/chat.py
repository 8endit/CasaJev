import csv
import io
import json
import re
import uuid
import time
from .assistant import Assistant
from .contracts import validate_task
from .builder import object_schema, STRING
from .contracts import canonical
from .library import Library
from .preparation import PreparationError


VISIBLE_PAGE_ACTION = re.compile(
    r'\b(?:klick(?:e|en)?|tipp(?:e|en)?|markier(?:e|en)?|filter(?:e|n)?|wähl(?:e|en)?|'
    r'aktivier(?:e|en)?|deaktivier(?:e|en)?|scroll(?:e|en)?|spiel(?:e|en)?|zieh(?:e|en)?|'
    r'füge\b.*\bhinzu|trag(?:e|en)?\b.*\bein)\b', re.I)


def visible_page_action_request(message, browser_state):
    """Recognize explicit UI verbs only when an actual browser page is visible."""
    url=(browser_state or {}).get('url','')
    return bool(url and url != 'about:blank' and VISIBLE_PAGE_ACTION.search(message))


def kind_of(value):
    if isinstance(value,list) and value and all(type(x) in (int,float) for x in value):
        return 'numbers'
    if isinstance(value,list) and value and all(isinstance(x,dict) and {'category','amount_cents'} <= set(x) for x in value):
        return 'transactions'
    return 'json'


def extract_objects(message, attachments):
    objects={}
    for i,attachment in enumerate(attachments):
        name=attachment.get('name','Anhang')
        content=attachment.get('content','')
        if not isinstance(name,str) or not isinstance(content,str) or len(content)>200000:
            raise ValueError('Dieser Anhang ist zu groß oder ungültig.')
        if name.lower().endswith('.json'):
            value=json.loads(content);kind=kind_of(value)
        elif name.lower().endswith('.csv'):
            value=content;kind='csv'
        else:
            value=content;kind='text'
        objects['attachment_'+str(i)]={'kind':kind,'description':name,'value':value}
    blocks=re.findall(r'```(?:json|csv|text)?\s*\n(.*?)```',message,re.S)
    # JSON can be pasted directly into the single chat composer.
    if not blocks:
        for match in re.finditer(r'[\[{]',message):
            try:
                value,end=json.JSONDecoder().raw_decode(message[match.start():])
                if not message[match.start()+end:].strip():
                    objects['input']={'kind':kind_of(value),'description':'Daten aus deiner Nachricht','value':value}
                    break
            except ValueError:
                continue
    for i,block in enumerate(blocks):
        try:
            value=json.loads(block);kind=kind_of(value)
        except ValueError:
            value=block
            try:
                rows=list(csv.reader(io.StringIO(block),strict=True))
                kind='csv' if len(rows)>1 and len(rows[0])>1 and all(len(r)==len(rows[0]) for r in rows) else 'text'
            except csv.Error:
                kind='text'
        objects['block_'+str(i)]={'kind':kind,'description':'Eingefügte Daten','value':value}
    # A trailing ordinary CSV block needs no markup or format selector.
    if not objects:
        lines=message.splitlines()
        for i in range(1,len(lines)-1):
            block='\n'.join(lines[i:]).strip()
            rows=list(csv.reader(io.StringIO(block)))
            if len(rows)>1 and len(rows[0])>1 and all(len(r)==len(rows[0]) for r in rows):
                objects['input']={'kind':'csv','description':'CSV aus deiner Nachricht','value':block}
                break
    return objects


class Chat:
    def __init__(self, harness, browser, assistant=None, desktop=None):
        self.harness,self.store,self.browser=harness,harness.store,browser
        self.assistant = assistant or (Assistant(harness.builder) if harness.builder else None)
        if desktop is None:
            from .desktop import DesktopObserver
            desktop=DesktopObserver()
        self.desktop=desktop
        self.library = Library(self.store)
        with self.store.connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            indexed = {r['id'] for r in conn.execute('SELECT id FROM conversation_search')}
            for row in conn.execute('SELECT id,body FROM conversations').fetchall():
                if row['id'] not in indexed:
                    value = json.loads(row['body'])
                    conn.execute('INSERT INTO conversation_search(id,content) VALUES(?,?)',
                                 (row['id'], '\n'.join(m.get('text','') for m in value.get('messages',[]))))

    def read(self, conversation):
        with self.store.connection() as conn:
            row=conn.execute('SELECT body FROM conversations WHERE id=?',(conversation,)).fetchone()
        return json.loads(row['body']) if row else {'id':conversation,'messages':[]}

    def save(self, convo):
        convo['updated_at']=time.time()
        with self.store.connection() as conn:
            conn.execute('INSERT OR REPLACE INTO conversations VALUES(?,?)',(convo['id'],canonical(convo)))
            meta = conn.execute('SELECT title FROM conversation_meta WHERE id=?', (convo['id'],)).fetchone()
            title = meta['title'] if meta and meta['title'] else ''
            conn.execute('DELETE FROM conversation_search WHERE id=?', (convo['id'],))
            conn.execute('INSERT INTO conversation_search(id,content) VALUES(?,?)',
                         (convo['id'], title+'\n'+'\n'.join(m.get('text','') for m in convo['messages'])))

    def history(self, query='', archived=False):
        with self.store.connection() as conn:
            rows=conn.execute('SELECT rowid, body FROM conversations ORDER BY rowid DESC').fetchall()
            metadata = {r['id']: dict(r) for r in conn.execute('SELECT * FROM conversation_meta')}
            matching = None
            tokens = re.findall(r'\w+', query, re.UNICODE)[:10]
            if tokens:
                expression = ' AND '.join('"'+t+'"' for t in tokens)
                matching = {r['id'] for r in conn.execute('SELECT id FROM conversation_search WHERE conversation_search MATCH ?', (expression,))}
        items=[]
        for row in rows:
            convo=json.loads(row['body'])
            meta = metadata.get(convo['id'], {})
            if bool(meta.get('archived')) != bool(archived) or (matching is not None and convo['id'] not in matching):
                continue
            first=next((m for m in convo.get('messages',[]) if m['role']=='user'),None)
            if first is None:
                continue
            title=meta.get('title') or ' '.join(first['text'].split())
            items.append({'id':convo['id'],'title':title[:90] or 'Chat',
                          'status':convo['messages'][-1].get('status','done'),
                          'updated_at':convo.get('updated_at',0), 'pinned':bool(meta.get('pinned')),
                          'archived':bool(meta.get('archived'))})
        # Stable order preserves SQLite row order for conversations predating timestamps.
        return sorted(items,key=lambda item:(item['pinned'],item['updated_at']),reverse=True)

    def update_meta(self, identity, changes):
        self.library.chat_meta(identity, changes)
        with self.store.connection() as conn:
            row = conn.execute('SELECT body FROM conversations WHERE id=?', (identity,)).fetchone()
            meta = conn.execute('SELECT title FROM conversation_meta WHERE id=?', (identity,)).fetchone()
            content = (meta['title'] or '')+'\n'+'\n'.join(m.get('text','') for m in json.loads(row['body'])['messages'])
            conn.execute('DELETE FROM conversation_search WHERE id=?', (identity,))
            conn.execute('INSERT INTO conversation_search(id,content) VALUES(?,?)', (identity,content))

    def public_read(self, conversation):
        convo=self.read(conversation)
        fields={'role','text','attachments','status','result','browser_url','task_id','sources','checked_at','elapsed_seconds','progress','browser_seconds','execution'}
        return {'id':convo['id'],'messages':[{k:v for k,v in m.items() if k in fields} for m in convo['messages']]}

    def pending(self):
        with self.store.connection() as conn:
            conversations=[json.loads(row['body']) for row in conn.execute('SELECT body FROM conversations')]
        return [c['id'] for c in conversations if c['messages'] and c['messages'][-1].get('status')=='working']

    def submit(self, body):
        cid=body.get('conversation') or uuid.uuid4().hex
        if not isinstance(cid,str) or not re.fullmatch('[a-zA-Z0-9_-]{1,64}',cid):
            raise ValueError('Ungültiges Gespräch.')
        text=body.get('message','').strip()
        attachments=body.get('attachments',[])
        if not text or len(text)>30000 or not isinstance(attachments,list) or len(attachments)>5:
            raise ValueError('Bitte einen Auftrag eingeben. Maximal fünf Anhänge.')
        convo=self.read(cid)
        if convo['messages'] and convo['messages'][-1].get('status')=='working':
            raise ValueError('Jev arbeitet noch an deiner letzten Nachricht.')
        objects=extract_objects(text,attachments)
        fresh_objects=bool(objects)
        if objects:
            convo['objects']=objects
        else:
            objects=convo.get('objects',{})
        convo['messages'].append({'role':'user','text':text,'attachments':[a.get('name','Anhang') for a in attachments]})
        convo['messages'].append({'role':'assistant','text':'','status':'working','objects':objects,'fresh_objects':fresh_objects})
        self.save(convo)
        return cid

    def progress(self, convo, text):
        convo['messages'][-1]['progress'] = text
        self.save(convo)

    def process(self, cid):
        convo=self.read(cid)
        if not convo['messages'] or convo['messages'][-1].get('status') != 'working':
            return
        response=convo['messages'][-1]
        browser=self.browser.for_chat(cid) if hasattr(self.browser,'for_chat') else self.browser
        user=convo['messages'][-2]['text']
        started=time.monotonic()
        try:
            if response.pop('resume_task', False) and response.get('task_id'):
                result = self.harness.run(response['task_id'])
                self.task_response(convo, response, result)
                return
            pending_action=convo.get('pending_action')
            trusted_goal=(pending_action['goal']+'\nNutzerantwort: '+user) if pending_action else user
            browser_context={}
            if browser and VISIBLE_PAGE_ACTION.search(user):
                try:
                    browser_context=browser.call('status',{})
                except Exception:
                    # Browser context improves routing, but a transient UI read must not break chat.
                    browser_context={}
            visible_action=visible_page_action_request(user,browser_context)
            context={'trusted_goal':trusted_goal,
                     'conversation':[{'role':m['role'],'text':m['text'],
                                      'result':('[lokale Desktop-Metadaten nicht an das Sprachmodell übergeben]'
                                                if m.get('execution',{}).get('mode')=='desktop_read' else m.get('result')),
                                      'sources':m.get('sources')} for m in convo['messages'][-18:-1]],
                     'objects':response['objects'],'permissions':['compute','public_web_read','interactive_browser','local_metadata_read'],
                     'available_data_tools':[{'name':v['spec']['name'],'description':v['spec']['description'],
                                              'input_kind':v['spec']['input_kind'],'input_schema':v['spec']['input_schema']}
                                             for v in self.store.tools().values()]}
            if browser_context:
                context['visible_browser']={'url':browser_context.get('url',''),
                                            'title':browser_context.get('title','')}
            context['available_external_tools'] = self.harness.connectors.tools() if self.harness.connectors else {}
            self.progress(convo,'Ich ordne deinen Auftrag ein …')
            route_options = {
                'data_task':{'description':'Exact deterministic transformation or calculation on supplied inputs.','risk':'compute'},
                'connector_task':{'description':'An explicit read request covered by an enabled external connector.','risk':'read'},
                'reply':{'description':'Discussion, writing, translation, or explanation of stable knowledge or supplied text.','risk':'passive'},
                'research':{'description':'Search public web for current facts, office holders, news, prices, recommendations or explicit research.','risk':'read'},
                'browser_search':{'description':'Explicitly Google a topic or search visibly in the integrated browser.','risk':'read'},
                'read_page':{'description':'Read or summarize a URL or the page visible in the built-in browser.','risk':'read'},
                'navigate':{'description':'Only open a user-supplied web address.','risk':'read'},
                'action_task':{'description':'Operate a public website through bounded visible clicks, typing, keys or pointer movement, including games and multi-step interactions.','risk':'interaction'},
                'desktop_task':{'description':'Read-only local discovery: find file names in common user folders, list running processes or installed apps, or identify the foreground app.','risk':'read'},
                'clarify':{'description':'Genuinely missing input or ambiguous intent.','risk':'passive'},
                'need_permission':{'description':'External writes, sending, purchases or unconnected account actions.','risk':'passive'}}
            try:
                if hasattr(self.harness.decision_policy, 'jev'):
                    self.harness.decision_policy.jev = self.harness.jev
                route_decision, route_state = self.harness.controller.choose(context, route_options,
                    'Choose route using the conversation, including short follow-ups. Public facts are not missing user data. '
                    'A NEW factual query about a current office holder needs research. Reformatting a previously sourced answer is reply. Writing and summarization are reply. A URL summary is read_page. '
                    'Explicit Google searches or requests to watch browsing use browser_search. A request to merely open a URL is navigate. '
                    'Requests to click, type, play, fill, mark, filter, select, or otherwise operate the visible website use action_task, even when the user does not say website. '
                    'Requests to find local files, processes, installed apps or the foreground app use desktop_task. Generic uncertainty can use clarify.')
                answer={'action':route_decision.action if route_decision.accepted else None}
                response['routing_evidence']=self.harness.policy_evidence()
                response['routing_decision']={'confidence':route_decision.confidence,
                    'threshold':route_decision.threshold,'risk':route_decision.risk,
                    'accepted':route_decision.accepted,'reason':route_decision.reason}
            except (ValueError, RuntimeError) as exc:
                # A routing outage must not turn every conversation into the same dead end.
                response['routing_error']=str(exc)[:300]
                answer={'action':None}
            action=answer.get('action')
            if pending_action:
                action='action_task'
            from .browser_search import direct_google_query, visible_search
            query=direct_google_query(user)
            if query:
                action='browser_search'
            if visible_action:
                action='action_task'
            response['route']=action
            urlmatch=re.search(r'https?://[^\s<>]+',user)
            url=urlmatch.group().rstrip('.,;)') if urlmatch else ''
            goal=trusted_goal
            plan=None
            # Generative bridge resolves uncertain routes, missing structured arguments and normal replies.
            needs_language_plan=(action not in ('research','read_page','navigate','data_task','browser_search') or
                action=='action_task' or (action=='browser_search' and not query) or
                (action=='data_task' and (not response['objects'] or not response.get('fresh_objects'))))
            # A strong UI verb plus an actual visible page already supplies route, goal and target.
            # Going through a second language planner adds latency and can only weaken that evidence.
            if visible_action:
                needs_language_plan=False
            if needs_language_plan:
                if self.assistant:
                    self.progress(convo,'Ich berücksichtige den Gesprächsverlauf …')
                    plan=self.assistant.plan(context)
                    response.setdefault('language_evidence',[]).append(self.assistant.model.last)
                    response['preparation']=plan.get('preparation')
                    action=plan['action'];goal=plan.get('goal') or trusted_goal
                    if pending_action and action != 'action_task':
                        action='action_task'; goal=pending_action['goal']+'\nNutzerantwort: '+user
                    url=plan['url'] or url
                    if visible_action:
                        # The visible page is the target. Do not let a generic language fallback
                        # turn an explicit UI command into a refusal or reload the current app.
                        action='action_task'; goal=trusted_goal; url=''
                    if action in ('data_task','connector_task') and plan.get('objects'):
                        response['objects']=plan['objects']
                        context['objects']=plan['objects']
                else:
                    response.update(text='Im Demo-Modus kannst du CSV oder JSON verarbeiten. Freie Antworten und Recherche benötigen den Live-Modus.',status='done')
                    return
            response['route']=action
            if self.harness.cancel_event.is_set(): raise InterruptedError('Auftrag angehalten.')
            if action=='browser_search':
                def show_step(label, address):
                    response['browser_url']=address
                    self.progress(convo,label)
                found=visible_search(browser,self.harness.decision_policy,query or goal,user,show_step)
                response['browser_seconds']=round(found['seconds'],3)
                response['browser_evidence']=found['evidence']
                response['browser_steps']=found['steps']
                response['browser_decisions']=found.get('trace',[])
                if found.get('blocked'):
                    response['browser_blocked']=found['blocked']
                page=found['page']
                response['browser_url']=page['url']
                if found['selected'] and self.assistant:
                    self.progress(convo,'Quelle gelesen. Ich formuliere die Antwort …')
                    response['text']=self.assistant.reply_from_page(context,page)
                    response.setdefault('language_evidence',[]).append(self.assistant.model.last)
                    from .assistant import now
                    response['sources']=[{'title':page['title'],'url':page['url'],'retrieved_at':now()}]
                    convo['objects']={'page':{'kind':'text','description':page['title']+' ('+page['url']+')','value':page['text']}}
                else:
                    response['text']=found.get('message','Die gewählte Quelle ist im Browser geöffnet.')
            elif action=='research':
                if not self.assistant:
                    raise RuntimeError('Recherche benötigt den Live-Modus.')
                self.progress(convo,'Ich recherchiere aktuelle Quellen …')
                found=self.assistant.research(context)
                response.setdefault('language_evidence',[]).append(self.assistant.model.last)
                response.update(text=found['reply'],sources=found['sources'],checked_at=found['checked_at'])
            elif action=='navigate':
                if not url:
                    response['text']='Welche Webseite soll ich öffnen?'
                else:
                    response['browser_url']=url
                    self.progress(convo,'Ich öffne die Seite …')
                    browser_started=time.monotonic()
                    page=browser.call('navigate',{'url':url})
                    response['browser_seconds']=round(time.monotonic()-browser_started,3)
                    response.update(text='Geöffnet: '+page['title'],browser_url=page['url'])
            elif action=='read_page':
                if not self.assistant:
                    raise RuntimeError('Seitenzusammenfassungen benötigen den Live-Modus.')
                response['browser_url']=url or 'current'
                self.progress(convo,'Ich lese die Webseite …')
                browser_started=time.monotonic()
                page=browser.call('read_page',{'url':url})
                response['browser_seconds']=round(time.monotonic()-browser_started,3)
                response['browser_url']=page['url']
                self.progress(convo,'Ich verarbeite den Seiteninhalt …')
                response['text']=self.assistant.reply_from_page(context,page)
                response.setdefault('language_evidence',[]).append(self.assistant.model.last)
                from .assistant import now
                response['sources']=[{'title':page['title'],'url':page['url'],'retrieved_at':now()}]
                convo['objects']={'page':{'kind':'text','description':page['title']+' ('+page['url']+')','value':page['text']}}
            elif action=='action_task':
                if not browser or not self.assistant:
                    raise RuntimeError('Der Aktionsmodus benötigt Browser und Codex im Live-Modus.')
                from .action import ActionAgent
                self.progress(convo,'Ich starte den Aktionsmodus …')
                agent=ActionAgent(browser,self.assistant,self.harness.cancel_event,
                                  decision_controller=self.harness.controller)
                result=agent.run(goal,context,url,lambda text:self.progress(convo,text))
                gpt_calls=sum(item.get('planner')=='gpt_vision' for item in result['trace'])
                jev_calls=sum(item.get('planner')=='jev_dom' for item in result['trace'])
                if gpt_calls:
                    response.setdefault('language_evidence',[]).append(self.assistant.model.last)
                response['browser_url']=result['url']
                response['action_trace']=result['trace']
                response['execution']={'mode':'browser_action','gpt_calls':gpt_calls,'jev_calls':jev_calls,
                    'tool_calls':sum(len(item['commands']) for item in result['trace']),
                    'verification':'structured_observation_after_each_batch_with_visual_fallback'}
                response['text']=result['text']
                if result['status']=='completed':
                    convo.pop('pending_action',None)
                else:
                    convo['pending_action']={'goal':goal,'url':result['url']}
                    response['needs_input']=True
            elif action=='desktop_task':
                if not self.assistant:
                    raise RuntimeError('Desktop-Erkennung benötigt den Live-Modus.')
                self.progress(convo,'Ich prüfe den lokalen Desktop im erlaubten Lesebereich …')
                desktop_plan=self.assistant.desktop_plan(context)
                response.setdefault('language_evidence',[]).append(self.assistant.model.last)
                if desktop_plan['operation']=='unsupported_control':
                    response['text']=desktop_plan['reply'] or 'Diese Desktop-Steuerung ist noch nicht freigegeben.'
                else:
                    result=self.desktop.run(desktop_plan['operation'],desktop_plan['query'])
                    response['result']=result
                    response['text']=desktop_plan['reply'] or 'Lokale Desktop-Metadaten wurden gelesen.'
                    response['execution']={'mode':'desktop_read','operation':desktop_plan['operation'],
                        'scope':'metadata_only'}
            elif action in ('data_task','connector_task') and response['objects']:
                self.progress(convo,'Ich verarbeite die Daten und prüfe das Ergebnis …')
                history=[m['text'] for m in convo['messages'][:-2] if m['role']=='user'][-3:]
                task_goal=goal if not history else 'Vorheriger Gesprächskontext: '+canonical(history)+'\nAktueller Auftrag: '+goal
                validate_task({'goal':task_goal,'objects':response['objects']})
                permissions = ['compute','external_read'] if action=='connector_task' else ['compute']
                task=self.store.get(response['task_id']) if response.get('task_id') else self.harness.create({'goal':task_goal,'objects':response['objects'],'permissions':permissions})
                response['task_id']=task['id'];self.save(convo)
                result=self.harness.run(task['id'])
                self.task_response(convo, response, result)
            elif action=='data_task':
                response['text']='Welche Werte soll ich dafür verwenden?'
            else:
                response['text']=plan['reply'] if plan else 'Für diese Aktion fehlt noch ein passender Zugriff.'
            if self.harness.cancel_event.is_set(): raise InterruptedError('Auftrag angehalten.')
            if response['status'] == 'working': response['status']='done'
        except InterruptedError:
            response.update(text='Angehalten. Du kannst den gespeicherten Auftrag fortsetzen.', status='paused')
        except PreparationError as exc:
            response.update(text=str(exc), status='done', needs_input=True)
        except Exception as exc:
            response.update(text='Das hat gerade nicht geklappt: '+str(exc)[:400],status='error')
        finally:
            response['elapsed_seconds']=round(time.monotonic()-started,3)
            response.pop('objects',None)
            response.pop('progress',None)
            self.save(convo)

    def task_response(self, convo, response, result):
        if all(key in result for key in ('jev_calls', 'builder_calls', 'observations')):
            response['execution'] = {'mode': result.get('execution_mode', 'standard'),
                'jev_calls': result['jev_calls'], 'gpt_calls': result['builder_calls'] + len(response.get('language_evidence', [])),
                'tool_calls': len(result['observations']), 'decisions': len(result.get('decision_trace', [])),
                'supervisor_escalations': int(bool(result.get('decision_review_used'))),
                'verification': result.get('verification')}
        if result['status'] == 'completed':
            response.update(result=result['result'], text='Fertig.', status='done')
            convo['objects']={**response.get('objects',convo.get('objects',{})), 'previous_result':{
                'kind':kind_of(result['result']), 'description':'Ergebnis des letzten Auftrags', 'value':result['result']}}
        else:
            response.update(result=None, text=self.explain_status(result), needs_input=True,
                            status='paused' if result['status']=='paused' else 'error' if result['status']=='failed' else 'done')

    def resume(self, identity):
        convo = self.read(identity)
        if not convo['messages'] or convo['messages'][-1].get('status') not in ('paused','error'):
            raise ValueError('Dieser Chat hat keinen angehaltenen Auftrag.')
        response = convo['messages'][-1]
        objects = self.store.get(response['task_id'])['objects'] if response.get('task_id') else convo.get('objects',{})
        response.update(status='working', objects=objects, fresh_objects=bool(objects), resume_task=bool(response.get('task_id')))
        self.save(convo)

    @staticmethod
    def explain_status(state):
        if state['status']=='needs_input' and ('ambiguous to Jev' in state.get('message','') or 'Jev is unsure' in state.get('message','')):
            return 'Ich konnte die passende Werkzeugauswahl noch nicht sicher bestätigen. Der Auftrag ist gespeichert, aber noch nicht erledigt.'
        return {'needs_input':'Mir fehlt noch eine Angabe. Was soll das Ergebnis genau enthalten?',
                'paused':'Angehalten. Der Arbeitsstand ist gespeichert.',
                'needs_review':'Ich konnte das Ergebnis noch nicht ausreichend bestätigen. Der Auftrag bleibt zur Prüfung gespeichert.',
                'needs_permission':'Dafür fehlt mir ein freigegebener Zugriff.',
                'budget_exhausted':'Ich habe das Arbeitslimit erreicht. Der bisherige Stand bleibt gespeichert.',
                'failed':'Der Lauf wurde angehalten. '+state.get('message','Bitte versuche es erneut.')}.get(state['status'],'Die Aufgabe wurde angehalten.')

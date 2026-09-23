"""Bounded, observable browser actions planned by Codex and executed by CasaJev."""
import base64
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
from .builder import object_schema, STRING
from .jev import choice


ACTION_INTENTS = {
    'open_or_start': 'Seite, Spiel oder Runde öffnen/starten',
    'resume_play': 'pausierte Runde fortsetzen',
    'dismiss_overlay': 'Werbung, Consent- oder Pause-Overlay schließen',
    'enter_value': 'Name oder andere ausdrücklich benötigte Eingabe eintragen',
    'activate_control': 'beobachtetes Bedienelement aktivieren',
    'activate_controls_batch': 'mehrere bereits sichtbare reversible Bedienelemente in sicherer Reihenfolge aktivieren',
    'steer_continuously': 'Figur/Mauszeiger mehrere Sekunden flüssig entlang eines Pfads steuern',
    'move_piece': 'Spielfigur mit einer schnellen Tastenfolge bewegen',
    'rotate_piece': 'Spielfigur drehen oder ausrichten',
    'hard_drop': 'Tetris-Stein sofort ablegen',
    'recover_focus': 'Fokus oder Steuerung des Spiels wiederherstellen',
    'inspect_progress': 'kurz warten und anschließend den wirklichen Fortschritt beobachten',
    'finish_goal': 'nur nach sichtbarem Beleg das gesamte Nutzerziel abschließen',
    'other_bounded_action': 'andere kleine, klar begrenzte Browseraktion',
}
SUPPORTED_KEYS = ('Enter','Backspace','Delete','Tab','Escape','Space','ArrowUp','ArrowDown',
                  'ArrowLeft','ArrowRight','Home','End','PageUp','PageDown','ControlOrMeta+A',
                  'z','x','c')
POINT_SCHEMA = object_schema({'x': {'type':'number'}, 'y': {'type':'number'}})
COMMAND_SCHEMA = object_schema({
    'intent': {'type':'string','enum':list(ACTION_INTENTS)},
    'action': {'type':'string','enum':['navigate','click','move','mouse_down','mouse_up','scroll','text','key','wait',
                                      'key_sequence','pointer_path','click_sequence']},
    'target': {'type':'integer','minimum':-1,'maximum':79},
    'targets': {'type':'array','items':{'type':'integer','minimum':0,'maximum':79},'maxItems':8},
    'url': STRING, 'x': {'type':'number'}, 'y': {'type':'number'}, 'delta': {'type':'number'},
    'text': STRING, 'key': STRING, 'seconds': {'type':'number'},
    'keys': {'type':'array','items':{'type':'string','enum':list(SUPPORTED_KEYS)},'maxItems':40},
    'points': {'type':'array','items':POINT_SCHEMA,'maxItems':16},
    'interval': {'type':'number','minimum':0.02,'maximum':0.5},
    'duration': {'type':'number','minimum':0.25,'maximum':12},
    'repeat': {'type':'integer','minimum':1,'maximum':4}})
ACTION_PLAN_SCHEMA = object_schema({
    'status': {'type':'string','enum':['continue','done','ask_user','blocked']},
    'phase': {'type':'string','enum':['setup','playing','result','other']},
    'goal_complete': {'type':'boolean'},
    'completion_evidence': STRING,
    'summary': STRING, 'question': STRING, 'capability': STRING,
    'commands': {'type':'array','items':COMMAND_SCHEMA,'maxItems':12}})


RISKY_CONTROL = re.compile(
    r'\b(?:buy|purchase|pay|checkout|order|send|submit|publish|post|delete|remove|clear|unsubscribe|'
    r'kaufen|bezahlen|bestellen|senden|abschicken|veröffentlichen|löschen|entfernen|leeren|kündigen)\b', re.I)
TEXT_INPUT_TYPES = ('', 'text', 'search', 'email', 'url', 'tel', 'number')


def goal_text_values(goal):
    """Extract explicit user-provided values; Jev never has to generate strings."""
    values=[]
    for value in re.findall(r"[„“\"']([^„“\"']{1,160})[„“\"']", goal):
        if value.strip() not in values:
            values.append(value.strip())
    for segment in re.findall(r':\s*([^\n]+)', goal):
        segment=re.split(
            r'[.!?]\s+(?=(?:markier|hak|zeig|filter|wähl|aktivier|deaktivier|click|check|show|filter|select)\w*)',
            segment, maxsplit=1, flags=re.I)[0]
        for value in re.split(r'\s*(?:,|\bund\b|\band\b)\s*', segment, flags=re.I):
            value=value.strip(' \t\r\n.;:–—')
            if 0 < len(value) <= 160 and value not in values:
                values.append(value)
    return values[:8]


def goal_completion_values(goal):
    values=[]
    patterns=(r'(?:markier\w*|hak\w*)\s+(.+?)\s+als\s+erledigt',
              r'(?:mark|check)\s+(.+?)\s+as\s+(?:done|completed)')
    for pattern in patterns:
        for segment in re.findall(pattern,goal,flags=re.I):
            for value in re.split(r'\s*(?:,|\bund\b|\band\b)\s*',segment,flags=re.I):
                value=value.strip(' \t\r\n.;:–—')
                if value and value not in values:
                    values.append(value)
    return values[:8]


def dom_action_candidates(goal, observation, action_history=()):
    """Bind a finite action space to the current DOM snapshot."""
    actions={};commands={}
    values=goal_text_values(goal)
    completion_values=goal_completion_values(goal)
    page_text=observation.get('text','').casefold()
    entered_values={command.get('text','').casefold() for item in action_history
                    for command in item.get('executed_commands',[]) if command.get('action')=='text'}
    missing_values=[value for value in values if value.casefold() not in page_text and
                    value.casefold() not in entered_values]
    editable=[element for element in observation.get('elements', []) if not element.get('disabled') and
              (element.get('tag')=='textarea' or (element.get('tag')=='input' and
                                                   element.get('type','') in TEXT_INPUT_TYPES))]
    batch_entry=bool(editable and missing_values)
    completion_targets=[]
    for element in observation.get('elements', []):
        name=(element.get('name') or '').casefold()
        if element.get('type')=='checkbox' and not element.get('checked') and any(
                value.casefold() in name or name in value.casefold() for value in completion_values if name):
            completion_targets.append(element.get('index'))
    completion_targets=[index for index in completion_targets if type(index) is int]
    batch_completion=len(completion_targets)>=2
    for element in observation.get('elements', []):
        if element.get('disabled'):
            continue
        index=element.get('index')
        if type(index) is not int:
            continue
        tag=element.get('tag','');kind=element.get('type','')
        name=(element.get('name') or f'{tag} {index}').strip()
        state=[]
        if element.get('checked') is not None:
            state.append('checked='+str(bool(element['checked'])).lower())
        if element.get('selected') is not None:
            state.append('selected='+str(bool(element['selected'])).lower())
        state_text=', '.join(state) or 'visible'
        href=element.get('href','')
        goal_words={word for word in re.findall(r'\w+',goal.casefold()) if len(word)>=3}
        name_words={word for word in re.findall(r'\w+',name.casefold()) if len(word)>=3}
        translated={'active':'aktiv','completed':'erledigt','all':'alle'}
        relevant_link=bool(name_words & goal_words) or any(
            translated[word] in goal.casefold() for word in name_words if word in translated) or href.startswith('#')
        clickable=(kind in ('checkbox','radio') or tag=='button' or element.get('role')=='button' or
                   kind=='button' or (tag=='a' and relevant_link))
        if completion_values and kind=='checkbox':
            clickable=False
        if clickable and not batch_entry:
            if not RISKY_CONTROL.search(name):
                key=f'click:{index}'
                actions[key]={'description':f'Click visible {tag or kind} “{name}” ({state_text}).',
                              'risk':'read' if tag=='a' else 'interaction'}
                commands[key]=[{'intent':'activate_control','action':'click','target':index,
                                'url':'','x':0,'y':0,'delta':0,'text':'','key':'','seconds':0}]
        if (tag=='textarea' or (tag=='input' and kind in TEXT_INPUT_TYPES)) and missing_values:
            if len(missing_values)==1:
                value=missing_values[0];key=f'enter:{index}:0'
                actions[key]={'description':f'Enter exact user-provided value “{value}” into “{name}” and press Enter.',
                              'risk':'interaction'}
                commands[key]=[
                    {'intent':'activate_control','action':'click','target':index,'url':'','x':0,'y':0,
                     'delta':0,'text':'','key':'','seconds':0},
                    {'intent':'enter_value','action':'text','target':-1,'url':'','x':0,'y':0,
                     'delta':0,'text':value,'key':'','seconds':0},
                    {'intent':'activate_control','action':'key','target':-1,'url':'','x':0,'y':0,
                     'delta':0,'text':'','key':'Enter','seconds':0}]
            else:
                key=f'enter_all:{index}'
                actions[key]={'description':'Enter every explicitly listed user value, in order, into '
                              f'“{name}”, pressing Enter after each value: {missing_values}.','risk':'interaction'}
                batch=[{'intent':'activate_control','action':'click','target':index,'url':'','x':0,'y':0,
                        'delta':0,'text':'','key':'','seconds':0}]
                for value in missing_values:
                    batch.extend([
                        {'intent':'enter_value','action':'text','target':-1,'url':'','x':0,'y':0,
                         'delta':0,'text':value,'key':'','seconds':0},
                        {'intent':'activate_control','action':'key','target':-1,'url':'','x':0,'y':0,
                         'delta':0,'text':'','key':'Enter','seconds':0}])
                commands[key]=batch
    if batch_completion and not batch_entry:
        key='complete_requested'
        actions[key]={'description':'Mark all explicitly requested completion targets as done in one reversible batch: '
                      f'{completion_values}.','risk':'interaction'}
        commands[key]=[{'intent':'activate_controls_batch','action':'click_sequence','target':-1,
                        'targets':completion_targets,'url':'','x':0,'y':0,'delta':0,'text':'','key':'',
                        'seconds':0,'interval':.12}]
    actions['done']={'description':'The latest structured page state visibly proves every clause of the goal.',
                     'risk':'submit'}
    return actions,commands


def deterministic_dom_completion(goal, observation, action_history):
    """Verify the common create/complete/filter workflow without a model assertion."""
    values=goal_text_values(goal);completed=goal_completion_values(goal)
    if not values or not completed or not re.search(r'\b(?:aktiv\w*|active)\b',goal,re.I):
        return None
    entered={command.get('text','').casefold() for item in action_history
             for command in item.get('executed_commands',[]) if command.get('action')=='text'}
    if not all(value.casefold() in entered for value in values):
        return None
    if not any(item.get('decision_action')=='complete_requested' for item in action_history):
        return None
    url=observation.get('url','').casefold();text=observation.get('text','').casefold()
    if not ('#/active' in url or '/active' in url):
        return None
    active=[value for value in values if value not in completed]
    if not all(value.casefold() in text for value in active):
        return None
    if any(value.casefold() in text for value in completed):
        return None
    return ('Alle Eingaben wurden ausgeführt, die verlangten Einträge wurden im bestätigten Batch erledigt, '
            'der Aktiv-Filter ist geöffnet und nur die erwarteten offenen Einträge sind sichtbar.')


class ActionAgent:
    def __init__(self, browser, assistant, cancel_event=None, max_rounds=20, max_seconds=600,
                 decision_controller=None):
        self.browser, self.assistant = browser, assistant
        self.cancel_event = cancel_event
        self.max_rounds, self.max_seconds = max_rounds, max_seconds
        self.decision_controller = decision_controller

    def _dom_plan(self, goal, context, observed, action_history):
        if self.decision_controller is None or not observed.get('elements'):
            return None,None
        verified=deterministic_dom_completion(goal,observed,action_history)
        if verified:
            return {'status':'done','phase':'result','goal_complete':True,
                    'completion_evidence':verified,'summary':'Der angeforderte Seitenzustand ist verifiziert.',
                    'question':'','capability':'','commands':[]},{'planner':'code_verify','accepted':True}
        actions,commands=dom_action_candidates(goal,observed,action_history)
        if len(actions)<=1:
            return None,None
        mission={'goal':goal,'permissions':context.get('permissions',[]),
                 'objects':{'page':{'kind':'browser_page','description':'Current structured browser state',
                                    'value':{'url':observed.get('url'),'title':observed.get('title'),
                                             'text':observed.get('text','')[:6000]}}},
                 'observations':[{'tool':'browser_action','result':item,'validated':True,
                                  'validation':'Executed command history'} for item in action_history[-6:]]}
        questions={
            'state_quality':choice('Is the structured DOM state sufficient for the next safe decision?',{
                'enough':'DOM text and controls are sufficient.',
                'needs_visual':'Pixels or canvas content must be inspected.',
                'needs_user':'A required value or authorization is missing.'}),
            'goal_progress':choice('Does the latest observed page prove the complete user goal?',{
                'complete':'Every clause is visibly satisfied now.',
                'incomplete':'At least one requested clause remains.',
                'blocked':'The page cannot currently fulfill the goal.'})}
        try:
            decision,compiled=self.decision_controller.choose(
                mission,actions,
                'Choose exactly one bounded action from the latest structured DOM state. Prefer a bound DOM action. '
                'A labeled input with exact user-provided text bound in an action needs no screenshot. '
                'Choose done only when the current observation proves every clause. Report needs_visual in '
                'state_quality when canvas pixels, an overlay, an unlabeled control or missing state prevents a safe choice.',questions)
        except (RuntimeError,ValueError):
            return None,None
        evidence={'planner':'jev_dom','confidence':decision.confidence,'threshold':decision.threshold,
                  'accepted':decision.accepted,'reason':decision.reason,'answers':decision.answers,
                  'compiled_state':compiled}
        if not decision.accepted or \
                decision.answers.get('state_quality') in ('needs_visual','needs_user'):
            return None,evidence
        if decision.action=='done':
            if decision.answers.get('goal_progress')!='complete':
                return None,evidence
            return {'status':'done','phase':'result','goal_complete':True,
                    'completion_evidence':'Der strukturierte Seitenzustand belegt alle Zielklauseln.',
                    'summary':'Die Seite zeigt den vollständig erreichten Zielzustand.',
                    'question':'','capability':'','commands':[]},evidence
        selected=commands.get(decision.action)
        if not selected:
            return None,evidence
        return {'status':'continue','phase':'other','goal_complete':False,'completion_evidence':'',
                'summary':actions[decision.action]['description'],'question':'','capability':'',
                'commands':selected},evidence

    def _execute(self, command, viewport):
        action = command['action']
        if action == 'click_sequence':
            targets=command.get('targets',[])
            if not 2<=len(targets)<=8 or len(set(targets))!=len(targets):
                raise ValueError('Ungültige Klickfolge.')
            elements={item['index']:item for item in viewport.get('elements',[])}
            if any(target not in elements for target in targets):
                raise ValueError('Ein Element der Klickfolge ist nicht mehr sichtbar.')
            return self.browser.call('control_batch', {'kind':'clicks',
                'points':[{'x':elements[target]['x'],'y':elements[target]['y']} for target in targets],
                'interval':command.get('interval',.12),
                'basis_width':viewport['width'],'basis_height':viewport['height']})
        if action == 'key_sequence':
            keys=command.get('keys',[])
            if not keys or any(key not in SUPPORTED_KEYS for key in keys):
                raise ValueError('Ungültige Tastenfolge.')
            return self.browser.call('control_batch', {'kind':'keys','keys':keys,
                'interval':command.get('interval',.08)})
        if action == 'pointer_path':
            points=command.get('points',[])
            if len(points)<2:
                raise ValueError('Ein Steuerpfad benötigt mindestens zwei Punkte.')
            return self.browser.call('control_batch', {'kind':'pointer_path','points':points,
                'duration':command.get('duration',3),'repeat':command.get('repeat',1),
                'basis_width':viewport['width'],'basis_height':viewport['height']})
        if action == 'navigate':
            return self.browser.call('navigate', {'url':command['url']})
        if action in ('click','move'):
            x,y=command['x'],command['y']
            if action=='click' and command.get('target',-1)>=0:
                element=next((item for item in viewport.get('elements',[]) if item['index']==command['target']),None)
                if element is None: raise ValueError('Das gewählte Seitenelement ist nicht mehr sichtbar.')
                x,y=element['x'],element['y']
            return self.browser.call(action, {'x':x,'y':y,
                'basis_width':viewport['width'],'basis_height':viewport['height']})
        if action in ('mouse_down','mouse_up'):
            return self.browser.call(action, {})
        if action == 'scroll':
            return self.browser.call(action, {'delta':command['delta']})
        if action == 'text':
            return self.browser.call(action, {'text':command['text']})
        if action == 'key':
            return self.browser.call(action, {'key':command['key']})
        return self.browser.call('wait', {'seconds':command['seconds']})

    @staticmethod
    def _changes_layout(command, viewport):
        if command['action'] != 'click':
            return command['action'] in ('navigate','key_sequence','pointer_path','click_sequence') or \
                (command['action']=='key' and command.get('key') in ('Enter','Backspace','Delete'))
        target=command.get('target',-1)
        element=next((item for item in viewport.get('elements',[]) if item.get('index')==target),{})
        text_input=element.get('tag')=='textarea' or (element.get('tag')=='input' and
            element.get('type','text') in ('','text','search','email','url','tel','number','password'))
        return not text_input

    @staticmethod
    def _repeated_text_entry(commands, viewport):
        """A focused list input can accept several text+Enter pairs without new targets."""
        if len(commands)<5 or commands[0].get('action')!='click':
            return False
        target=commands[0].get('target',-1)
        element=next((item for item in viewport.get('elements',[]) if item.get('index')==target),{})
        if not (element.get('tag')=='textarea' or (element.get('tag')=='input' and
                element.get('type','text') in ('','text','search','email','url','tel','number'))):
            return False
        tail=commands[1:]
        return len(tail)%2==0 and all(
            tail[index].get('action')=='text' and tail[index+1].get('action')=='key' and
            tail[index+1].get('key')=='Enter' for index in range(0,len(tail),2))

    def run(self, goal, context, start_url='', progress=None):
        started=time.monotonic(); trace=[]; action_history=[]
        persistent_goal=any(fragment in goal.casefold() for fragment in
            ('spiel','runde','gewin','bis ','hole.io','tetris','worm','snake'))
        round_limit=self.max_rounds if persistent_goal else min(self.max_rounds,12)
        second_limit=self.max_seconds if persistent_goal else min(self.max_seconds,180)
        previous_state=None; unchanged_rounds=0
        if start_url:
            self.browser.call('navigate', {'url':start_url})
        for round_number in range(1,round_limit+1):
            if self.cancel_event is not None and self.cancel_event.is_set():
                raise InterruptedError('Auftrag angehalten.')
            if progress: progress('Ich beobachte die Seite und plane den nächsten Schritt …')
            observed=self.browser.call('action_state',{'include_image':self.decision_controller is None})
            state_key=hashlib.sha256((json.dumps({
                'url':observed.get('url'),'title':observed.get('title'),'text':observed.get('text'),
                'elements':observed.get('elements')},sort_keys=True,ensure_ascii=False)+
                observed.get('image','')).encode()).hexdigest()
            unchanged_rounds=unchanged_rounds+1 if state_key==previous_state else 0
            previous_state=state_key
            if not persistent_goal and unchanged_rounds>=2:
                return {'status':'blocked',
                        'text':'Ich komme auf der Seite nicht weiter: Zwei Aktionsversuche haben den sichtbaren Zustand nicht verändert.',
                        'url':observed['url'],'trace':trace}
            plan,planner_evidence=self._dom_plan(goal,context,observed,action_history)
            planner=(planner_evidence or {}).get('planner','jev_dom') if plan is not None else 'gpt_vision'
            if plan is None:
                encoded=observed.pop('image','')
                if not encoded:
                    encoded=self.browser.call('state').get('image','')
                image=base64.b64decode(encoded)
                root=Path(self.assistant.model.root);root.mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(prefix='action-',suffix='.jpg',dir=root,delete=False) as handle:
                    handle.write(image); image_path=Path(handle.name)
                try:
                    planner_context={**context,'browser_action_history':action_history[-12:]}
                    plan=self.assistant.action_plan(planner_context, observed, image_path)
                finally:
                    image_path.unlink(missing_ok=True)
            record={'round':round_number,'url':observed['url'],'title':observed['title'],
                    'status':plan['status'],'phase':plan.get('phase','other'),
                    'goal_complete':bool(plan.get('goal_complete')),
                    'completion_evidence':plan.get('completion_evidence',''),
                    'summary':plan['summary'],'commands':[],'intents':[],'planner':planner}
            if planner_evidence:
                record['decision']=planner_evidence
            trace.append(record)
            if plan['status']=='ask_user':
                return {'status':'needs_input','text':plan['question'],'url':observed['url'],'trace':trace}
            if plan['status']=='blocked':
                detail=(' Benötigte Fähigkeit: '+plan['capability']+'.') if plan['capability'] else ''
                return {'status':'blocked','text':plan['summary']+detail,'url':observed['url'],'trace':trace}
            done_supported=(not persistent_goal or (plan.get('goal_complete') is True and
                plan.get('phase')=='result' and bool(plan.get('completion_evidence','').strip())))
            if plan['status']=='done' and done_supported:
                return {'status':'completed','text':plan['summary'] or 'Aktion abgeschlossen.',
                        'url':observed['url'],'trace':trace}
            if plan['status']=='done' and not done_supported:
                record['status']='continue'
                record['summary']=(plan['summary'] or 'Ein Zwischenschritt ist abgeschlossen.') + \
                    ' Das Gesamtziel ist noch nicht sichtbar belegt.'
                if progress: progress(record['summary'])
                continue
            if not plan['commands']:
                return {'status':'blocked','text':'Der Aktionsplan enthielt keinen ausführbaren Schritt.',
                        'url':observed['url'],'trace':trace}
            if progress: progress(plan['summary'] or 'Ich führe den nächsten Schritt aus …')
            executed=[]
            repeated_entry=self._repeated_text_entry(plan['commands'],observed)
            for command in plan['commands']:
                self._execute(command, observed)
                record['commands'].append(command['action'])
                record['intents'].append(command.get('intent','other_bounded_action'))
                executed.append({key:command.get(key) for key in ('intent','action','target','text','key','url')})
                if self.cancel_event is not None and self.cancel_event.is_set():
                    raise InterruptedError('Auftrag angehalten.')
                # Coordinates and element indices belong to the last observation. Once a
                # command can change the DOM, observe again instead of using stale targets.
                if self._changes_layout(command,observed) and not repeated_entry:
                    break
            action_history.append({'round':round_number,
                'observed_before':{'url':observed.get('url'),'title':observed.get('title'),
                                   'text':observed.get('text','')[:3000]},
                'summary':plan['summary'],'planner':planner,
                'decision_action':record.get('decision',{}).get('answers',{}).get('action'),
                'executed_commands':executed})
            if time.monotonic()-started >= second_limit:
                break
        state=self.browser.call('state')
        return {'status':'needs_input','text':'Ich pausiere am Zeit- oder Schrittlimit. Das Gesamtziel bleibt gespeichert. Soll ich direkt weiterarbeiten?',
                'url':state['url'],'trace':trace}

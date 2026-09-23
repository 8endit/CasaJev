import argparse
import json
import os
from pathlib import Path
from .builder import CodexBuilder
from .engine import Harness
from .jev import Jev, DemoJev, credentials
from .runner import Runner
from .store import Store
from .settings import configuration, settings, secret
from .library import Library
from .policies import decision_policy


def make_harness(args, demo=False):
    store = Store(args.home)
    config = configuration(store.root)
    options = settings(store.root)
    library = Library(store)
    key_path = args.credentials_file or config.get('credentials_file')
    key = None
    if not demo:
        try:
            key = secret(store.root, 'typesafe') or credentials(key_path)
        except (OSError, RuntimeError):
            if args.command != 'serve': raise
    jev = DemoJev() if demo else Jev(key)
    provider = (getattr(args, 'policy', None) or os.environ.get('CASAJEV_DECISION_PROVIDER')
                or options['general_decision_provider'])
    selected_policy = None if demo else decision_policy(provider, jev=jev, laya_model=options['laya_model'])
    builder = None if demo or getattr(args,'jev_only',False) else CodexBuilder(store.root / 'builds',
        model=os.environ.get('CASAJEV_BUILDER_MODEL') or config.get('builder_model', 'gpt-5.6-terra'),
        escalation_model=os.environ.get('CASAJEV_ESCALATION_MODEL') or config.get('escalation_model', 'gpt-5.6-sol'),
        reasoning='medium')
    runner = Runner()
    if builder:
        builder.skills_provider = library.enabled_skills
    if args.command == 'serve' and not demo:
        from .templates import TEMPLATES, SOURCES
        from .contracts import contract_id, digest
        with store.lock():
            active = store.tools(active_only=False)
            for spec in TEMPLATES:
                source = SOURCES[contract_id(spec)]
                if not any(contract_id(item['spec']) == contract_id(spec)
                           and item['source_hash'] == digest(source) and item['source'] == source for item in active.values()):
                    store.register(spec, source, runner.verify(spec, source))
    harness = Harness(store, jev, runner, builder, use_templates=not getattr(args, 'no_templates', False),
                   execution_mode='jev_only' if getattr(args,'jev_only',False) else 'standard',
                   max_steps=options['max_steps'], max_seconds=options['max_seconds'],
                   max_tool_retries=options['max_tool_retries'], decision_policy=selected_policy)
    from .connectors import Connectors
    harness.connectors = Connectors(library, harness.cancel_event)
    return harness


def main():
    p = argparse.ArgumentParser(description='CasaJev — Jev entscheidet. Die Werkstatt erweitert seine Fähigkeiten.')
    p.add_argument('--home', default=os.environ.get('CASAJEV_HOME', '.casajev'))
    p.add_argument('--credentials-file', default=os.environ.get('CASAJEV_CREDENTIALS_FILE'))
    p.add_argument('--policy', choices=('laya','jev'), help='Bounded decision provider (default from local settings)')
    subs = p.add_subparsers(dest='command', required=True)
    run = subs.add_parser('run'); run.add_argument('task'); run.add_argument('--no-templates', action='store_true')
    run.add_argument('--jev-only',action='store_true',help='Use existing tools only; forbid GPT assistance and new tool construction')
    demo = subs.add_parser('demo'); demo.add_argument('--repeat', type=int, default=2)
    resume = subs.add_parser('resume'); resume.add_argument('id'); resume.add_argument('--clarification'); resume.add_argument('--objects', help='JSON file containing object map')
    inspect = subs.add_parser('inspect'); inspect.add_argument('id')
    subs.add_parser('tools'); subs.add_parser('tasks'); subs.add_parser('doctor')
    subs.add_parser('workflows')
    serve = subs.add_parser('serve'); serve.add_argument('--port', type=int, default=8787); serve.add_argument('--demo', action='store_true')
    args = p.parse_args()
    if args.command == 'workflows':
        from .workflows import export
        print(export(Store(args.home))); return
    if args.command == 'doctor':
        import shutil, platform
        native = platform.system() == 'Darwin' and bool(shutil.which('sandbox-exec'))
        print(json.dumps({'platform': platform.system(), 'codex': bool(shutil.which('codex')),
                          'worker_backend': 'macOS Seatbelt' if native else ('Docker' if shutil.which('docker') else None),
                          'credentials_file_exists': bool(args.credentials_file and Path(args.credentials_file).is_file()),
                          'environment_key_present': bool(os.environ.get('TYPESAFE_API_KEY'))}, indent=2)); return
    if args.command == 'serve':
        from .server import serve
        serve(args); return
    if args.command in ('inspect', 'tools', 'tasks'):
        store = Store(args.home)
        result = {'task': store.get(args.id), 'events': store.events(args.id)} if args.command == 'inspect' else getattr(store, args.command)()
        print(json.dumps(result, ensure_ascii=False, indent=2)); return
    harness = make_harness(args, demo=args.command == 'demo')
    if args.command == 'demo':
        example = Path(__file__).resolve().parent.parent / 'examples/csv.json'
        for _ in range(min(max(args.repeat, 1), 10)):
            state = harness.create(json.loads(example.read_text()))
            result = harness.run(state['id'])
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == 'resume':
        with harness.store.lock():
            state = harness.store.get(args.id)
            if args.clarification:
                state['clarification'] = args.clarification
                state['phase'] = 'decide'
                state.pop('proposals', None)
            if args.objects:
                from .contracts import validate_task
                objects = json.loads(Path(args.objects).read_text())
                validate_task({'goal': state['goal'], 'objects': objects})
                state['objects'].update(objects)
                state['phase'] = 'decide'
            harness.store.save(state, 'user_update', {'clarification': args.clarification, 'objects_added': bool(args.objects)})
        print(json.dumps(harness.run(args.id), ensure_ascii=False, indent=2))
    else:
        state = harness.create(json.loads(Path(args.task).read_text()))
        result = harness.run(state['id'])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result['status'] != 'completed':
            raise SystemExit(1)


if __name__ == '__main__':
    main()

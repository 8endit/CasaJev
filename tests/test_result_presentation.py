from pathlib import Path


STATIC = Path(__file__).parents[1] / 'casajev' / 'static'


def test_result_renderer_is_shape_driven_and_json_is_only_fallback():
    script = (STATIC / 'manage.js').read_text()
    assert 'function renderResult(value)' in script
    assert "return resultTable(value.processes, 'Laufende Prozesse')" in script
    assert "node('summary', 'Technische Daten anzeigen')" in script


def test_message_actions_never_render_missing_counters_or_result_download():
    script = (STATIC / 'manage.js').read_text()
    actions = script[script.index('function messageActions'):script.index("$('stop').onclick")]
    assert 'Number.isFinite(message.execution.jev_calls)' in actions
    assert 'Number.isFinite(message.execution.gpt_calls)' in actions
    assert 'Ergebnis speichern' not in actions
    assert "message.execution.jev_calls + ' Entscheidungen'" not in actions


def test_chat_uses_adaptive_result_renderer():
    page = (STATIC / 'index.html').read_text()
    assert "typeof renderResult==='function'?renderResult(m.result)" in page

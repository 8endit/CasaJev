"""The builder must be told how the existing domain-rejection protocol works."""
from casajev.builder import CodexBuilder
from casajev.runner import Runner, ToolRejectedInput


def test_proposal_and_build_prompts_explain_worker_input_rejection(tmp_path):
    builder = CodexBuilder(tmp_path, model='gpt-6-sol')
    prompts = []

    def capture(prompt, schema, escalate=False):
        prompts.append(prompt)
        if len(prompts) == 1:
            return {'proposals': [], 'question': 'Welches Datum gilt?'}
        return {'source': 'def main(payload):\n    raise InputRejected("Invalid ISO date")\n'}

    builder.invoke = capture
    assert builder.propose({'trusted_goal': 'Reject invalid dates'}) == ([], 'Welches Datum gilt?')
    source = builder.build({'semantics': 'Reject invalid ISO dates'})
    assert 'examples format cannot encode rejection' in prompts[0]
    assert 'trusted goal explicitly asks for error objects as data' in prompts[0]
    assert 'raise InputRejected(message)' in prompts[1]
    assert 'already available in the worker namespace' in prompts[1]
    assert 'A returned {"error": ...} is a successful value' in prompts[1]
    assert 'Contract examples describe successful outputs only' in prompts[1]
    # The named exception is a real worker protocol, not merely prompt text.
    try:
        Runner().run(source, 'bad date')
    except ToolRejectedInput as exc:
        assert 'Invalid ISO date' in str(exc)
    else:
        raise AssertionError('InputRejected was not classified as domain rejection')

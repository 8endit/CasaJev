"""The builder must be told how the existing domain-rejection protocol works."""
from casajev.engine import bound_inputs
from casajev.builder import CodexBuilder
from casajev.runner import Runner, ToolRejectedInput
from casajev.templates import CSV_COLUMNS


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
    assert 'input_schema must validate an existing object value directly' in prompts[0]
    assert 'a CSV object value is a raw string' in prompts[0]
    assert 'Do not invent {"csv": ...} or {"source_csv": ...} wrappers' in prompts[0]
    assert 'Only the existing CSV+columns adapter' in prompts[0]
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


def test_contract_binding_accepts_existing_shapes_without_arbitrary_wrappers():
    raw = 'Supplier,Net,Day\nAcme,1,2026-09-24\n'
    csv_object = {'kind': 'csv', 'value': raw}
    direct = {'input_schema': {'type': 'string'}}
    wrapped_csv = {'input_schema': {'type': 'object', 'properties': {
        'source_csv': {'type': 'string'}}, 'required': ['source_csv']}}
    wrapped_named_csv = {'input_schema': {'type': 'object', 'properties': {
        'csv': {'type': 'string'}}, 'required': ['csv']}}
    assert bound_inputs(csv_object, direct) == [(raw, {})]
    assert bound_inputs(csv_object, wrapped_csv) == []
    assert bound_inputs(csv_object, wrapped_named_csv) == []
    assert ({'csv': raw, 'columns': {'vendor': 'Supplier', 'amount': 'Net', 'date': 'Day'}},
            {'vendor': 'Supplier', 'amount': 'Net', 'date': 'Day'}) in bound_inputs(csv_object, CSV_COLUMNS)
    existing_json = {'kind': 'json', 'value': {'source_csv': raw}}
    assert bound_inputs(existing_json, wrapped_csv) == [(existing_json['value'], {})]

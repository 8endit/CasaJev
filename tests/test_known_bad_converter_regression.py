"""Four fixed 2026-09-23 counterexamples; not new holdout evidence.

The frozen bad source is executed in Runner. Literal external gold stays in a
separate fixture, outside any builder or internal verifier context. This test
does not require the internal verifier to continue accepting the bad source.
"""
import hashlib
import json
from pathlib import Path

from casajev.contracts import validate
from casajev.runner import Runner

from known_bad_fixture import BAD_SOURCE, BAD_SOURCE_SHA256, HOLDOUT_INPUT_SHA256, SPEC
from known_bad_oracle import accepts_value


GOLD_PATH = Path(__file__).parent / 'fixtures' / 'known_bad_converter_cases.json'
GOLD_SHA256 = 'b846a2058fd578d24a76c91701ef89813b6583e9e0ce9f9cc3a204a3df8b9c16'


def test_known_bad_converter_is_rejected_by_all_four_external_golds():
    assert hashlib.sha256(BAD_SOURCE.encode()).hexdigest() == BAD_SOURCE_SHA256
    gold_bytes = GOLD_PATH.read_bytes()
    assert hashlib.sha256(gold_bytes).hexdigest() == GOLD_SHA256
    cases = json.loads(gold_bytes)['cases']
    assert len(cases) == 4
    assert {case['id'] for case in cases} == set(HOLDOUT_INPUT_SHA256)
    assert {case['id']: case['expected']['kind'] for case in cases} == {
        'quoted_comma': 'value', 'missing_amount': 'value',
        'duplicate_header': 'domain_rejection', 'ambiguous_date': 'domain_rejection'}

    runner = Runner()
    for case in cases:
        submitted = case['input']
        assert hashlib.sha256(submitted.encode()).hexdigest() == HOLDOUT_INPUT_SHA256[case['id']]
        observed = runner.run(BAD_SOURCE, submitted)
        validate(observed, SPEC['output_schema'])
        assert not accepts_value(case, observed), case['id']

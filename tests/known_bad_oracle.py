"""External literal-gold check for a previously observed wrong converter.

This module is never passed to the converter, Runner, or builder.
"""
import json


def accepts_value(case, observed):
    expected = case['expected']
    if expected['kind'] == 'domain_rejection':
        return False  # Any returned value violates a required rejection.
    if expected['kind'] != 'value':
        raise ValueError('Unknown expected outcome')
    canonical = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True,
                                         separators=(',', ':'))
    return canonical(observed) == canonical(expected['value'])

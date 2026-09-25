# Frozen known-bad CasaJev 0.5.1 converter from the 2026-09-23 falsification probe.

BAD_SOURCE = "def main(payload):\n    lines = payload.strip().splitlines()\n    result = []\n    for line in lines[1:]:\n        cells = line.split(',')\n        result.append({'vendor': cells[0], 'amount': cells[1], 'date': cells[2]})\n    return {'rows': result}\n"
BAD_SOURCE_SHA256 = '9f566e3878748f2cf514b306e141bba6cf75d4bfe5db1ee356d8983097bf33ae'
SPEC = {'name': 'csv_to_vendor_json',
 'description': 'Convert vendor payment CSV to JSON.',
 'operation': 'convert',
 'input_kind': 'csv',
 'output_kind': 'json',
 'semantics': 'Parse RFC-style quoted CSV. Require the exact unique header vendor,amount,date. '
              'Preserve text values, represent an empty amount as null, and accept only valid '
              'YYYY-MM-DD dates. Reject duplicate/wrong headers, malformed rows and ambiguous '
              'dates.',
 'permissions': ['compute'],
 'input_schema': {'type': 'string', 'maxLength': 200000},
 'output_schema': {'type': 'object',
                   'properties': {'rows': {'type': 'array',
                                           'items': {'type': 'object',
                                                     'properties': {'vendor': {'type': 'string'},
                                                                    'amount': {'type': ['string',
                                                                                        'null']},
                                                                    'date': {'type': 'string'}},
                                                     'required': ['vendor', 'amount', 'date'],
                                                     'additionalProperties': False}}},
                   'required': ['rows'],
                   'additionalProperties': False},
 'examples': [{'input': 'vendor,amount,date\nAda,100,2026-09-01\n',
               'output': {'rows': [{'vendor': 'Ada', 'amount': '100', 'date': '2026-09-01'}]}},
              {'input': 'vendor,amount,date\nBob,25,2026-09-02\n',
               'output': {'rows': [{'vendor': 'Bob', 'amount': '25', 'date': '2026-09-02'}]}}]}
HOLDOUT_INPUT_SHA256 = {'quoted_comma': '5865638d7b018e09d46c00cde721d2cb246ba2c4a06307008886900c7ba75629',
 'missing_amount': 'c14cf2cb9f907f8a572be14f24718b0aff5d0e8185955ed1b795725c3fc05ac6',
 'duplicate_header': 'dbcafe6887893262e1657147b55e66d7af1339c842cbdb25be3a283f11bd6134',
 'ambiguous_date': '8b6ce8c957fe1dfdf45dc7a7132f96ca47356b263714f9c9517e267d14871937'}

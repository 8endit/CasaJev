from .contracts import contract_id

CSV_SOURCE = '''import csv
import io

def main(payload):
    rows = list(csv.reader(io.StringIO(payload), strict=True))
    if not rows:
        return {"groups": [], "records": 0, "extra_duplicates": 0}
    width = len(rows[0])
    buckets = {}
    for index, row in enumerate(rows[1:], 1):
        if len(row) != width:
            raise ValueError("Inconsistent number of columns")
        buckets.setdefault(tuple(row), []).append(index)
    groups = [indexes for indexes in buckets.values() if len(indexes) > 1]
    return {"groups": groups, "records": len(rows) - 1,
            "extra_duplicates": sum(len(group) - 1 for group in groups)}
'''
CSV = {
    'name': 'csv_exact_duplicate_groups',
    'description': 'Find exact duplicate full CSV records; preserve case, whitespace and numeric text. Header excluded; one-based record indices.',
    'operation': 'group', 'input_kind': 'csv', 'output_kind': 'records',
    'semantics': 'Comma separated RFC-style CSV with first row header. Compare complete parsed string records exactly, without normalization. Return all groups of duplicate record indices in first-seen order, one-based excluding header, total record count and extra duplicate count. Reject inconsistent widths.',
    'permissions': ['compute'], 'input_schema': {'type': 'string', 'maxLength': 200000},
    'output_schema': {'type': 'object', 'properties': {
        'groups': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'integer', 'minimum': 1}}},
        'records': {'type': 'integer', 'minimum': 0}, 'extra_duplicates': {'type': 'integer', 'minimum': 0}},
        'required': ['groups', 'records', 'extra_duplicates'], 'additionalProperties': False},
    'examples': [
        {'input': 'name,code\nAda,01\nBob,1\nAda,01\nAda,1\nBob,1\n',
         'output': {'groups': [[1, 3], [2, 5]], 'records': 5, 'extra_duplicates': 2}},
        {'input': 'name\nAda\nada\n Ada\n', 'output': {'groups': [], 'records': 3, 'extra_duplicates': 0}},
        {'input': 'a,b\n"x,y","one\ntwo"\n"x,y","one\ntwo"\n',
         'output': {'groups': [[1, 2]], 'records': 2, 'extra_duplicates': 1}},
        {'input': '', 'output': {'groups': [], 'records': 0, 'extra_duplicates': 0}}
    ]}
SORT = {
    'name': 'sort_numbers', 'description': 'Sort a list of numbers ascending; preserve duplicates.',
    'operation': 'sort', 'input_kind': 'numbers', 'output_kind': 'numbers',
    'semantics': 'Sort numeric input values ascending without removing duplicates.',
    'permissions': ['compute'],
    'input_schema': {'type': 'array', 'items': {'type': 'number'}, 'maxItems': 10000},
    'output_schema': {'type': 'array', 'items': {'type': 'number'}},
    'examples': [{'input': [3, 1, 3, -2], 'output': [-2, 1, 3, 3]}, {'input': [], 'output': []}]}
SUM = {
    'name': 'sum_numbers', 'description': 'Sum a list of numbers and return the total.',
    'operation': 'calculate', 'input_kind': 'numbers', 'output_kind': 'value',
    'semantics': 'Sum all numeric input elements. Empty input sums to zero.',
    'permissions': ['compute'],
    'input_schema': {'type': 'array', 'items': {'type': 'number'}, 'maxItems': 10000},
    'output_schema': {'type': 'number'},
    'examples': [{'input': [3, 1, -2], 'output': 2}, {'input': [], 'output': 0}]}
TEMPLATES = [CSV, SORT, SUM]
SOURCES = {contract_id(CSV): CSV_SOURCE, contract_id(SORT): 'def main(payload):\n    return sorted(payload)\n',
           contract_id(SUM): 'def main(payload):\n    return sum(payload)\n'}

POSITIVE = {
    'name':'positive_numbers', 'description':'Keep only numbers strictly greater than zero, preserving order and duplicates.',
    'operation':'filter','input_kind':'numbers','output_kind':'numbers',
    'semantics':'Return all input numeric elements strictly greater than zero in original order, keeping duplicates. Exclude zero and negatives.',
    'permissions':['compute'], 'input_schema':SORT['input_schema'], 'output_schema':SORT['output_schema'],
    'examples':[{'input':[-1,0,3,2,3],'output':[3,2,3]},{'input':[-2,0],'output':[]},{'input':[],'output':[]}]}
TEMPLATES.append(POSITIVE)
SOURCES[contract_id(POSITIVE)]='def main(payload):\n    return [x for x in payload if x > 0]\n'

# A parameterized data contract. The controller, not the tool or evaluation
# adapter, binds the three role names to observed CSV headers for each call.
CSV_COLUMNS_SOURCE = '''import csv
import io
import datetime

def main(payload):
    rows = list(csv.reader(io.StringIO(payload["csv"]), strict=True))
    if not rows or not rows[0] or any(not cell for cell in rows[0]):
        raise InputRejected("Missing or empty CSV header")
    headers = rows[0]
    if len(set(cell.casefold() for cell in headers)) != len(headers):
        raise InputRejected("Duplicate or ambiguous CSV header")
    columns = payload["columns"]
    names = [columns[role] for role in ("vendor", "amount", "date")]
    if len(set(names)) != 3 or any(name not in headers for name in names):
        raise InputRejected("Missing or ambiguous column mapping")
    indexes = [headers.index(name) for name in names]
    output = []
    for row in rows[1:]:
        if len(row) != len(headers):
            raise InputRejected("Inconsistent CSV width")
        vendor, amount, date = [row[index] for index in indexes]
        try:
            if datetime.date.fromisoformat(date).isoformat() != date:
                raise InputRejected("Non-canonical ISO date")
        except ValueError:
            raise InputRejected("Invalid ISO date")
        output.append({"vendor": vendor, "amount": amount if amount != "" else None, "date": date})
    return {"rows": output}
'''
CSV_COLUMNS = {
    'name': 'csv_columns_to_records',
    'description': 'Read vendor, amount and date from explicitly mapped CSV headers; preserve cell text and map empty amount to null.',
    'operation': 'extract', 'input_kind': 'csv', 'output_kind': 'records',
    'semantics': 'Input is an unchanged CSV string plus an explicit one-to-one header mapping for vendor, amount, date. Reject missing, duplicate or case-ambiguous headers, inconsistent rows and non-canonical or invalid ISO dates. Output rows retain vendor, nonempty amount and date text exactly; empty amount becomes null. Column names may vary; the mapping is a call parameter, never a change to this contract.',
    'permissions': ['compute'],
    'input_schema': {'type':'object','properties': {
        'csv': {'type':'string','maxLength':200000},
        'columns': {'type':'object','properties': {
            'vendor': {'type':'string','minLength':1}, 'amount': {'type':'string','minLength':1},
            'date': {'type':'string','minLength':1}},
            'required':['vendor','amount','date'],'additionalProperties':False}},
        'required':['csv','columns'],'additionalProperties':False},
    'output_schema': {'type':'object','properties': {'rows': {'type':'array','items': {
        'type':'object','properties': {'vendor': {'type':'string'},
            'amount': {'type':['string','null']}, 'date': {'type':'string'}},
        'required':['vendor','amount','date'],'additionalProperties':False}}},
        'required':['rows'],'additionalProperties':False},
    'examples': [
        {'input': {'csv':'Supplier,Net,Day\n Acme ,0012.50,2026-09-24\n',
                   'columns':{'vendor':'Supplier','amount':'Net','date':'Day'}},
         'output': {'rows':[{'vendor':' Acme ','amount':'0012.50','date':'2026-09-24'}]}},
        {'input': {'csv':'Datum,Lieferant,Betrag\n2026-09-25,Öko GmbH,\n',
                   'columns':{'vendor':'Lieferant','amount':'Betrag','date':'Datum'}},
         'output': {'rows':[{'vendor':'Öko GmbH','amount':None,'date':'2026-09-25'}]}}
    ]}
TEMPLATES.append(CSV_COLUMNS)
SOURCES[contract_id(CSV_COLUMNS)] = CSV_COLUMNS_SOURCE

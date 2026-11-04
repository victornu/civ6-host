from civ6_host.runtime.stdout_transport_profiles import verify_selected as _transport_profile
'Prospective parent-side decoder; no change to historical parse_events/reports.\n\nOnly bounded source-proven Chasing texts + the exact Host41 empty-Wait record are split.\nThe result remains diagnostic transport data, never an ACK or game status.\n'
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
import re
SCHEMA = 'civ6rl.native_stdout_chasing_wait.v2'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_stdout_transport.py')))).resolve().parents[1]
SOURCE_SHA256 = '1480668dd8cb634c258e7ec862663a2b6b511397e8a02153e898019d315121fa'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
HOST_SHA256 = '2b938551555af92ef37bbda8631d0a90c585c3e89c9d7710d0758e85e2b01334'
_DEC = '(?:0|[1-9][0-9]{0,9}|-[1-9][0-9]{0,9})'
_PREFIX = re.compile('Chasing target at: (' + _DEC + '), (' + _DEC + ')\\. Moving Unit ID: (' + _DEC + ')\\. Adjacent hex is: (' + _DEC + '), (' + _DEC + ')\\. Distance: (2147483647)')
_WAIT = re.compile('\\{"stage":"empty_job_set_waited","export":"EXP_JobManager_Wait","first_argument_raw":([1-9][0-9]{0,19}),"member8":0,"contract":"null_second_member_only"\\}')
MAX_CONTIGUOUS_PREFIXES = 1024

def verify_source(path=None):
    path = _resolve_resource_path(Path(path)) if path is not None else ROOT / 'work/native-stdout-transport490' / (SOURCE_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('stdout decoder source changed')
    doc = json.loads(raw)
    if doc['schema'] != 'civ6rl.native_stdout_chasing490.static.v1' or doc['image']['sha256'] != CORE_SHA256 or doc['host']['binary']['sha256'] != HOST_SHA256 or (doc['literal']['newline'] is not False) or (doc['literal']['text'] != 'Chasing target at: %d, %d. Moving Unit ID: %d. Adjacent hex is: %d, %d. Distance: %d') or (doc['verification']['instructions_rechecked'] != 150):
        raise ValueError('stdout decoder contract differs')
    return doc

def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result

def _json(text):
    return json.loads(text, object_pairs_hook=_unique, parse_constant=lambda token: (_ for _ in ()).throw(ValueError('nonfinite JSON token')))

def decode_stdout(stdout, *, core_sha256, host_sha256, source_path=None):
    """Decode once, while original stdout line positions are still available.

    The caller must require collection_complete before certifying a new report.
    Unknown stage objects remain events for existing semantic validators; this
    function never replaces those validators. Exact raw native lines and their
    event indexes preserve every occurrence without joining independent records.
    """
    if type(stdout) is not str:
        raise TypeError('decoded stdout text required')
    selected_source = _transport_profile(core_sha256, host_sha256, source_path=source_path, base_verify=verify_source)
    events = []
    native = []
    other = []
    event_lines = []
    other_lines = []
    lines = stdout.split('\n')
    if stdout.endswith('\n'):
        lines.pop()
    for index, chunk in enumerate(lines):
        has_lf = index < len(lines) - 1 or stdout.endswith('\n')
        raw = chunk + ('\n' if has_lf else '')
        line = chunk[:-1] if chunk.endswith('\r') and has_lf else chunk
        try:
            value = _json(line)
        except (ValueError, RecursionError):
            value = None
        if has_lf and type(value) is dict and (type(value.get('stage')) is str):
            event_lines.append(index + 1)
            events.append(value)
            continue
        end = 0
        count = 0
        valid_fields = True
        while count < MAX_CONTIGUOUS_PREFIXES:
            prefix = _PREFIX.match(line, end)
            if prefix is None:
                break
            valid_fields = valid_fields and all((-(1 << 31) <= int(v) < 1 << 31 for v in prefix.groups()))
            end = prefix.end()
            count += 1
        wait = _WAIT.fullmatch(line[end:]) if count else None
        valid = has_lf and count > 0 and (wait is not None) and valid_fields and (0 < int(wait.group(1)) < 1 << 64)
        if valid:
            value = _json(line[end:])
            event_index = len(events)
            native.append(dict(line_number=index + 1, raw_line=raw, native_text=line[:end], json_text=line[end:], event_index=event_index, rule='exact-Chasing-format-plus-exact-empty-Wait' if count == 1 else 'exact-repeated-Chasing-format-plus-exact-empty-Wait', source_sha256=selected_source))
            event_lines.append(index + 1)
            events.append(value)
        else:
            other.append(raw)
            other_lines.append(dict(line_number=index + 1, before_event_index=len(events)))
    digest = hashlib.sha256()
    for offset in range(0, len(stdout), 65536):
        digest.update(stdout[offset:offset + 65536].encode('utf-8'))
    return dict(schema=SCHEMA, source_sha256=selected_source, events=events, core_sha256=core_sha256, host_sha256=host_sha256, decoded_stdout_utf8_sha256=digest.hexdigest(), decoded_stdout_characters=len(stdout), ordinary_event_raw_retained=False, digest_basis='UTF-8 re-encoding of already decoded stdout; not original pipe bytes', event_line_numbers=event_lines, stdout_native=native, stdout_other=other, stdout_other_positions=other_lines, collection_complete=not other, semantic_validation_replaced=False, historical_report_rewritten=False, output_order='original decoded stdout LF line order; no deduplication', text_encoding_limit='Subprocess text decoding may already have replaced invalid UTF-8 bytes.')

def require_complete(result):
    if type(result) is not dict or result.get('schema') != SCHEMA or result.get('collection_complete') is not True or (result.get('stdout_other') != []):
        raise ValueError('Unclassified or damaged stdout transport; no complete collection claim')
    expected = _transport_profile(result.get('core_sha256'), result.get('host_sha256'), base_verify=verify_source)
    if result.get('source_sha256') != expected:
        raise ValueError('Stdout source profile does not match its native identities')

def trial_fields(result):
    """Keep normalized events separate; retain raw only for native/unknown lines."""
    return dict(stdout_native=result['stdout_native'], stdout_transport={key: value for key, value in result.items() if key not in ('events', 'stdout_native', 'stdout_other')})

def validate_trial_collection(trial):
    """Extra jobs gate for a reviewed new probe; never replaces ledger checks."""
    verify_source()
    metadata = trial.get('stdout_transport') if type(trial) is dict else None
    events = trial.get('events') if type(trial) is dict else None
    if type(metadata) is not dict or metadata.get('schema') != SCHEMA or metadata.get('source_sha256') != SOURCE_SHA256 or (metadata.get('core_sha256') != CORE_SHA256) or (metadata.get('host_sha256') != HOST_SHA256) or (metadata.get('collection_complete') is not True) or (trial.get('stdout_other') != []) or (metadata.get('stdout_other_positions') != []) or (metadata.get('semantic_validation_replaced') is not False) or (metadata.get('historical_report_rewritten') is not False) or (metadata.get('ordinary_event_raw_retained') is not False) or (type(events) is not list) or (not events) or any((type(e) is not dict or type(e.get('stage')) is not str for e in events)):
        raise ValueError('Missing, incomplete or malformed prospective stdout receipt')
    numbers = metadata.get('event_line_numbers')
    if type(numbers) is not list or len(numbers) != len(events) or any((type(n) is not int or n != i + 1 for i, n in enumerate(numbers))):
        raise ValueError('Complete stdout occurrence order differs')
    digest = metadata.get('decoded_stdout_utf8_sha256')
    if type(digest) is not str or re.fullmatch('[0-9a-f]{64}', digest) is None or type(metadata.get('decoded_stdout_characters')) is not int or (metadata['decoded_stdout_characters'] <= 0):
        raise ValueError('Decoded stdout identity is malformed')
    natives = trial.get('stdout_native')
    if type(natives) is not list:
        raise ValueError('Missing native stdout occurrence list')
    previous = -1
    for row in natives:
        if type(row) is not dict or set(row) != {'line_number', 'raw_line', 'native_text', 'json_text', 'event_index', 'rule', 'source_sha256'} or type(row['event_index']) is not int or (not previous < row['event_index'] < len(events)) or (type(row['line_number']) is not int) or (row['line_number'] != row['event_index'] + 1) or (type(row['raw_line']) is not str):
            raise ValueError('Malformed/reordered native stdout occurrence')
        parsed = decode_stdout(row['raw_line'], core_sha256=CORE_SHA256, host_sha256=HOST_SHA256)
        require_complete(parsed)
        if len(parsed['stdout_native']) != 1 or len(parsed['events']) != 1:
            raise ValueError('Native stdout raw record is not one exact occurrence')
        expected = parsed['stdout_native'][0] | dict(event_index=row['event_index'], line_number=row['line_number'])
        if row != expected or json.dumps(events[row['event_index']], sort_keys=True) != json.dumps(parsed['events'][0], sort_keys=True):
            raise ValueError('Native stdout raw record differs from its ordered event')
        previous = row['event_index']

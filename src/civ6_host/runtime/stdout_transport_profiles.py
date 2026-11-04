"""Exact engine/host provenance for the shared diagnostic stdout grammar.

Diagnostic coordinates remain private transport evidence. Decoding never
certifies a move, an acknowledgement or a simulation outcome.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from civ6_host.contracts.action_budget import LAN_EVENT_LINE_BYTES
from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path

BASE_SOURCE=('work/native-stdout-transport490/1480668dd8cb634c258e7ec862663a2b6b511397e8a02153e898019d315121fa.json',
             '1480668dd8cb634c258e7ec862663a2b6b511397e8a02153e898019d315121fa')
BASE_HOST='2b938551555af92ef37bbda8631d0a90c585c3e89c9d7710d0758e85e2b01334'
XP1_SOURCE=('work/host-extensions/xp1-stdout-transport/source-v1.json',
            '5fb36f8e81dd3bee0c53dcf1714a40bae91bd6bd55043e3feda2cfd8cab28b17')
XP1_HOST='949949ddca0ec61a55e3368bf062f46fcdb4b2f7dc52f25a49acc4758664224f'
XP2_SOURCE=('work/host-extensions/xp2-stdout-transport/source-v1.json',
            'fc2c15339ba7e3eef9d4ad73fa2b061e597f2719eaa77925d37652bffeeafcc7')
XP2_HOST='a3d977a4aa09d3f4f88a393f59e32f5a34d12d79db48606c39c4b9e09994f799'
_FORMAT='Chasing target at: %d, %d. Moving Unit ID: %d. Adjacent hex is: %d, %d. Distance: %d'
_WAIT_SOURCE='c625001b51660aa0b9b9ee8a3f37fd80ccb83b79c9d28237b3d7e8d2ae32ee3d'


@lru_cache(maxsize=1)
def verify_xp1():
    p=_source(XP1_SOURCE);base=_source(BASE_SOURCE)
    if (p['schema']!='civ6-host.xp1-stdout-chasing-wait.static.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['image']['sha256']!=XP1_CORE_SHA256 or p['host']['binary']['sha256']!=XP1_HOST
            or p['literal']['text']!=_FORMAT or p['literal']['newline'] is not False
            or p['verification']['full_PE_sha256_checked'] is not True
            or p['verification']['instructions_rechecked']!=150
            or p['verification']['complete_pdata_bodies']!=2
            or p['verification']['all_build_input_hashes_checked'] is not True
            or p['verification']['exact_base_wait_source_checked'] is not True
            or p['host']['wait_source_sha256']!=_WAIT_SOURCE
            or base['host']['wait_source_sha256']!=_WAIT_SOURCE
            or p['host']['wait_source']!=base['host']['wait_source']):
        raise ValueError('XP1 stdout producer/host identity or grammar changed')
    return p


def verify_selected(core_sha256,host_sha256,*,source_path=None,base_verify):
    """Refuse an unknown pair before applying any diagnostic text rule."""
    if (core_sha256,host_sha256)==(BASE_CORE_SHA256,BASE_HOST):
        base_verify(source_path)
        return BASE_SOURCE[1]
    if (core_sha256,host_sha256)==(XP2_CORE_SHA256,XP2_HOST):
        verify_xp2();selected=XP2_SOURCE
    elif (core_sha256,host_sha256)==(XP1_CORE_SHA256,XP1_HOST):
        verify_xp1();selected=XP1_SOURCE
    else:
        raise ValueError('No qualified stdout source for this exact Core/host pair')
    if source_path is not None:
        try:
            _source((str(source_path),selected[1]))
        except RuntimeError as exc:
            raise ValueError('stdout decoder source changed') from exc
    return selected[1]


@lru_cache(maxsize=1)
def verify_xp2():
    p=_source(XP2_SOURCE);prior=verify_xp1()
    if (p['schema']!='civ6-host.xp2-stdout-chasing-wait.static.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['image']['sha256']!=XP2_CORE_SHA256 or p['host']['binary']['sha256']!=XP2_HOST
            or p['literal']['text']!=_FORMAT or p['literal']['newline'] is not False
            or p['verification']['instructions_rechecked']!=150
            or p['verification']['complete_pdata_bodies']!=2
            or p['verification']['exact_prior_wait_source_equal'] is not True
            or p['verification']['all_build_inputs_verified'] is not True
            or p['host']['wait_source_sha256']!=_WAIT_SOURCE
            or p['host']['wait_source']!=prior['host']['wait_source']
            or {row['name'] for row in p['imports']}!={'__acrt_iob_func','__stdio_common_vfprintf'}):
        raise ValueError('XP2 stdout producer/host identity or grammar changed')
    for body in p['captures'].values():
        raw=b''.join(bytes.fromhex(row['bytes']) for row in body['instructions'])
        if len(raw)!=body['length'] or hashlib.sha256(raw).hexdigest()!=body['raw_sha256']:
            raise ValueError('XP2 stdout complete instruction body changed')
    return p


def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    # Build/source-manifest/binary are already verified and pinned by
    # prepare_sources. Historical extraction scripts and failed traces are
    # attribution, not files the runtime reads to decode future occurrences.
    refs=(XP1_SOURCE,BASE_SOURCE)
    if core_sha256==XP2_CORE_SHA256:
        p=verify_xp2();refs=(*refs,XP2_SOURCE,
            *((row['path'],row['sha256']) for row in (*p['references'],p['extractor'])))
    elif core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Unknown saved stdout engine')
    else:verify_xp1()
    return {str(resolve_path(resource_root()/path)):sha for path,sha in refs}


def selected_profile(core_sha256, host_sha256):
    from .native import native_stdout_transport as decoder
    return dict(schema=decoder.SCHEMA, core_sha256=core_sha256, host_sha256=host_sha256,
                source_sha256=verify_selected(core_sha256,host_sha256,base_verify=decoder.verify_source))


def validate_profile(profile):
    if (type(profile) is not dict
            or set(profile)!={'schema','source_sha256','core_sha256','host_sha256'}
            or profile != selected_profile(profile['core_sha256'],profile['host_sha256'])):
        raise ValueError('Saved stdout profile is not an exact qualified source')


def decode_record(line, profile=None, *, line_number, line_limit=LAN_EVENT_LINE_BYTES):
    """Decode one bounded physical line; native text is private, never an event.

    No profile means strict legacy JSON, not an inferred engine identity. The
    only admitted mixed line remains the source-qualified Chasing/empty-Wait
    grammar in the existing decoder. Its raw bytes and physical position are
    retained independently from the resulting host event.
    """
    if (type(line) is not bytes or type(line_number) is not int or line_number<1
            or type(line_limit) is not int or line_limit<1
            or not 0<len(line)<=line_limit or not line.endswith(b'\n')):
        raise ValueError('Incomplete or oversized native stdout physical line')
    if profile is not None:
        validate_profile(profile)
    return _decode_physical_line(line, profile, line_number)


def _decode_physical_line(line, profile, line_number):
    native_record=None
    try:
        event=json.loads(line)
    except json.JSONDecodeError:
        if profile is None:raise
        from .native import native_stdout_transport as decoder
        decoded=decoder.decode_stdout(line.decode('utf-8'),core_sha256=profile['core_sha256'],
                                      host_sha256=profile['host_sha256'])
        decoder.require_complete(decoded)
        if len(decoded['events'])!=1 or len(decoded['stdout_native'])!=1:
            raise ValueError('Expected one exact native stdout occurrence')
        event=decoded['events'][0]
        native_record=dict(line_number=line_number,raw_sha256=hashlib.sha256(line).hexdigest(),
            source_sha256=decoded['source_sha256'],rule=decoded['stdout_native'][0]['rule'])
    if type(event) is not dict or type(event.get('stage')) is not str:
        raise ValueError('Malformed native event object')
    return event,native_record


def validate_occurrence_ledger(records, profile):
    if profile is not None:validate_profile(profile)
    previous=0
    if type(records) is not list or len(records)>4096:
        raise ValueError('Invalid supervised stdout occurrence ledger')
    for row in records:
        if (profile is None or type(row) is not dict
                or set(row)!={'line_number','raw_sha256','source_sha256','rule'}
                or type(row['line_number']) is not int or row['line_number']<=previous
                or type(row['raw_sha256']) is not str or len(row['raw_sha256'])!=64
                or any(c not in '0123456789abcdef' for c in row['raw_sha256'])
                or row['source_sha256']!=profile['source_sha256']
                or row['rule'] not in ('exact-Chasing-format-plus-exact-empty-Wait',
                                      'exact-repeated-Chasing-format-plus-exact-empty-Wait')):
            raise ValueError('Invalid supervised stdout occurrence ledger')
        previous=row['line_number']


def iter_records(path, *, profile, expected_records, byte_limit, line_limit=LAN_EVENT_LINE_BYTES):
    """Yield (line number, exact bytes, event); exhaust to authenticate the ledger."""
    if type(byte_limit) is not int or byte_limit<1:
        raise ValueError('Native stdout requires an explicit positive byte bound')
    if type(line_limit) is not int or line_limit < 1:
        raise ValueError('Native stdout requires an explicit positive line bound')
    if type(profile) is dict:
        profile = profile.copy()
    validate_occurrence_ledger(expected_records,profile)
    expected_records = [row.copy() for row in expected_records]
    total=number=0;actual=[]
    with Path(path).open('rb') as stream:
        while True:
            line=stream.readline(line_limit+1)
            if not line:break
            number+=1;total+=len(line)
            if total>byte_limit:raise ValueError('Native stdout transcript exceeds its budget')
            if len(line) > line_limit or not line.endswith(b'\n'):
                raise ValueError('Incomplete or oversized native stdout physical line')
            event,record=_decode_physical_line(line,profile,number)
            if record is not None:
                if len(actual)>=4096:raise ValueError('Native diagnostic record budget exceeded')
                actual.append(record)
            yield number,line,event
    if actual!=expected_records:
        raise ValueError('Native stdout occurrence ledger differs from exact physical lines')


def session_records(run, *, report=None):
    """Read a closed session using its declared source and supervisor ledger."""
    run=Path(run)
    closure=json.loads((run/'closure.json').read_bytes())
    if report is None:report=json.loads((run/'supervisor.json').read_bytes())
    return iter_records(run/'events.jsonl',profile=closure.get('stdout_transport'),
        expected_records=report.get('stdout_native_records',[]),byte_limit=closure['stdout_limit_bytes'])

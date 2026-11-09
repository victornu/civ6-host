"""Copy the actual loaded ICU bytes and Localization settings, without DLL calls.

This producer deliberately does NOT export the active SQLite connection. Its
borrowed pointer is identified for the future exporter, never called or retained.
Stable repeated reads are change detection, not an atomic/lifetime guarantee.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
import json
import re
import struct
import time
import uuid
from civ6_host.runtime.native.native_gameplay_selection994 import _Deadline
from civ6_host.runtime.native.native_gameplay_selection994 import _file_digest
from civ6_host.runtime.native.native_resolved_content import ROOT
from civ6_host.runtime.native.native_resolved_content import CURRENT_EXE_SHA
from civ6_host.runtime.native.native_resolved_content import EXE_SHA
from civ6_host.runtime.native.native_resolved_content import MAX_USER_ADDRESS
from civ6_host.runtime.native.native_resolved_content import ContentSnapshotError
ROUTE_PATH = ROOT / 'work/official-capture/localization-tuner-route.json'
ROUTE_SHA = '2c145e47ec82432bcbf5fe461e8a25253244772d44e1d6e268eb362d2a9f3953'
LOCALIZATION_SHA = '0becd5c425a3d6edc88f5315c01af3dd30dd7cb158271d56f4bba7ff2bb4e056'
DATABASE_SHA = 'e6577e873f946224df65c02f6c4bc3b385607e2a82d957b0fd613e01cbe78b0c'
CURRENT_SHARED_SHA = '2907bbb5b41e8c015c4779e1c49c3940b06b6a719ca815cec61eac41c1340823'
MAX_ICU_BYTES = 64 * 1024 * 1024
MAX_READ_CALLS = 4096
MAX_READ_BYTES = MAX_ICU_BYTES * 2 + 64 * 1024
MAX_SECONDS = 30.0

def source_profile(executable_sha256=EXE_SHA):
    if executable_sha256 not in (EXE_SHA, CURRENT_EXE_SHA):
        raise ContentSnapshotError('Unsupported Localization executable')
    raw = _resolve_resource_path(ROUTE_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ROUTE_SHA:
        raise ContentSnapshotError('Localization capture source changed')
    value = json.loads(raw)
    if value['schema'] != 'civ6rl.localization_tuner_route.v1' or value['images']['localization']['sha256'] != LOCALIZATION_SHA or value['images']['database']['sha256'] != DATABASE_SHA or (value['native_export_allowed'] is not False):
        raise ContentSnapshotError('Unsupported Localization capture source')
    if executable_sha256 == EXE_SHA:
        return value
    raw = _resolve_resource_path(ROOT / 'work/official-capture/current-localization-shared-bindings.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != CURRENT_SHARED_SHA:
        raise ContentSnapshotError('Current Localization correspondence changed')
    current = json.loads(raw)
    for kind in ('localization', 'database'):
        spans = current['body_span_correspondence'][kind]['spans']
        if not spans or any((row['exact_same_rva_bytes'] is not True for row in spans)):
            raise ContentSnapshotError('Incomplete current Localization/Database correspondence')
    if any((row['exact_same_rva_bytes'] is not True for row in current['route_leaf_correspondence'])):
        raise ContentSnapshotError('Current Localization accessor correspondence differs')
    images = {'exe': {**value['images']['exe'], 'sha256': CURRENT_EXE_SHA}}
    for kind, filename in (('localization', 'Localization_FinalRelease.dll'), ('database', 'DatabaseDLL_FinalRelease.dll'), ('havok', 'HavokScript_FinalRelease.dll')):
        image = current['source_images'][filename]
        images[kind] = dict(path=image['current_path'], sha256=image['current_sha256'], base=value['images'][kind]['base'])
    return dict(images=images, reader_contract=value['reader_contract'], leaves={kind: value['leaves'][kind] for kind in ('localization', 'database')}, lookup_sql=value['lookup_sql'], current_shared_source_sha256=CURRENT_SHARED_SHA, native_export_allowed=False)

def read_localization_state(read_memory, localization_base, database_base, *, timeout_seconds=MAX_SECONDS, clock=time.monotonic, max_icu_bytes=MAX_ICU_BYTES, max_read_calls=MAX_READ_CALLS, executable_sha256=EXE_SHA):
    """Return ``(snapshot, complete_icu_bytes)`` using exact, bounded copies.

    The caller supplies a read-only reader and verifies module/process identity.
    No pointer is dereferenced by this Python process and no native call is made.
    Every metadata range and the full ICU buffer are reread. An ABA replacement
    remains possible; therefore atomic_snapshot_proven is always false.
    """
    if not callable(read_memory) or type(max_icu_bytes) is not int or (not 0 < max_icu_bytes <= MAX_ICU_BYTES) or (type(max_read_calls) is not int) or (not 0 < max_read_calls <= MAX_READ_CALLS):
        raise ContentSnapshotError('Invalid Localization capture bounds')
    for base in (localization_base, database_base):
        if type(base) is not int or not 65536 <= base <= MAX_USER_ADDRESS - 2097152:
            raise ContentSnapshotError('Invalid Localization module base')
    deadline = _Deadline(timeout_seconds, clock, MAX_SECONDS)
    profile = source_profile(executable_sha256)
    calls = consumed = 0
    journal = []

    def read(address, size, remember=True):
        nonlocal calls, consumed
        deadline.check()
        if type(address) is not int or type(size) is not int or size <= 0 or (not 65536 <= address <= MAX_USER_ADDRESS - size) or (calls >= max_read_calls) or (consumed + size > MAX_READ_BYTES):
            raise ContentSnapshotError('Localization memory bounds exceeded')
        calls += 1
        raw = read_memory(address, size)
        deadline.check()
        consumed += size
        if type(raw) is not bytes or len(raw) != size:
            raise ContentSnapshotError('Incomplete Localization memory read')
        if remember:
            journal.append((address, raw))
        return raw

    def qword(address):
        return struct.unpack('<Q', read(address, 8))[0]

    def pointer(address):
        value = qword(address)
        if value % 8 or not 65536 <= value <= MAX_USER_ADDRESS - 8:
            raise ContentSnapshotError('Invalid Localization pointer')
        return value

    def cstring(address, bound):
        data = bytearray()
        for offset in range(bound):
            byte = read(address + offset, 1)
            if byte == b'\x00':
                try:
                    return data.decode('ascii')
                except UnicodeDecodeError as exc:
                    raise ContentSnapshotError('Non-ASCII Localization identifier/SQL') from exc
            data.extend(byte)
        raise ContentSnapshotError('Unterminated Localization identifier/SQL')
    for kind, base in (('localization', localization_base), ('database', database_base)):
        for rva, leaf in profile['leaves'][kind].items():
            expected = bytes.fromhex(leaf['raw_hex'])
            if read(base + int(rva, 16), len(expected)) != expected:
                raise ContentSnapshotError('Localization accessor bytes changed')
    c = profile['reader_contract']
    dictionary = pointer(localization_base + c['localization_dictionary_pointer_rva'])
    icu = pointer(localization_base + c['icu_buffer_pointer_rva'])
    size = qword(localization_base + c['icu_buffer_length_rva'])
    if not 1 <= size <= max_icu_bytes:
        raise ContentSnapshotError('Loaded ICU exceeds supported size')
    index = qword(localization_base + c['current_language_index_rva'])
    begin = pointer(localization_base + c['languages_begin_rva'])
    end = qword(localization_base + c['languages_end_rva'])
    stride = c['language_stride']
    if not begin < end <= MAX_USER_ADDRESS or (end - begin) % stride or (end - begin) // stride > 1024 or (index >= (end - begin) // stride):
        raise ContentSnapshotError('Invalid Localization language vector/index')
    language = begin + index * stride
    locale = cstring(language + c['language_type_offset'], 64)
    if not re.fullmatch('[A-Za-z][A-Za-z0-9_@.\\-]{0,62}', locale):
        raise ContentSnapshotError('Unsupported active locale identifier')
    lookup = pointer(dictionary + c['dictionary_lookup_result_offset'])
    auxiliary = pointer(dictionary + c['dictionary_aux_result_offset'])
    for result in (lookup, auxiliary):
        if qword(result) != database_base + c['query_vtable_rva']:
            raise ContentSnapshotError('Unknown Localization query-result ABI')
    connection = pointer(lookup + c['query_connection_offset'])
    if pointer(auxiliary + c['query_connection_offset']) != connection or qword(connection) != database_base + c['connection_vtable_rva']:
        raise ContentSnapshotError('Localization query connection differs/unknown ABI')
    statement = pointer(lookup + c['query_statement_offset'])
    sql_pointer = pointer(statement + c['statement_retained_sql_offset'])
    sql = cstring(sql_pointer, 512)
    variants = {v['text']: k for k, v in profile['lookup_sql'].items()}
    if sql not in variants:
        raise ContentSnapshotError('Unknown Localization fallback query; no default permitted')
    policy = variants[sql]
    payload = bytearray()
    for offset in range(0, size, 1024 * 1024):
        payload.extend(read(icu + offset, min(1024 * 1024, size - offset), False))
    digest = hashlib.sha256(payload).hexdigest()
    second = hashlib.sha256()
    for offset in range(0, size, 1024 * 1024):
        second.update(read(icu + offset, min(1024 * 1024, size - offset), False))
    if second.hexdigest() != digest:
        raise ContentSnapshotError('Loaded ICU bytes changed during capture')
    for address, expected in reversed(journal):
        if read(address, len(expected), False) != expected:
            raise ContentSnapshotError('Localization metadata changed during capture')
    deadline.check()
    return ({'schema': 'civ6rl.localization_memory_snapshot.v2' if executable_sha256 == CURRENT_EXE_SHA else 'civ6rl.localization_memory_snapshot.v1', 'route_source_sha256': ROUTE_SHA, 'locale': locale, 'dictionary_flag': policy == 'strict', 'fallback_policy': policy, 'fallback_policy_sql': sql, 'fallback_policy_sql_sha256': hashlib.sha256(sql.encode()).hexdigest(), 'dictionary_address': hex(dictionary), 'connection_address': hex(connection), 'lookup_result_address': hex(lookup), 'auxiliary_result_address': hex(auxiliary), 'statement_address': hex(statement), 'icu_address': hex(icu), 'icu_sha256': digest, 'icu_bytes': size, 'language_address': hex(language), 'language_index': index, 'languages_begin': hex(begin), 'languages_end': hex(end), 'memory_read_calls': calls, 'memory_read_bytes': consumed, 'observed_ranges_unchanged': True, 'atomic_snapshot_proven': False, 'database_exported': False, 'database_lifetime_lease_proven': False, 'save_identity_bound': False, 'training_eligible': False, **({'current_shared_source_sha256': CURRENT_SHARED_SHA, 'executable_sha256': executable_sha256} if executable_sha256 == CURRENT_EXE_SHA else {})}, bytes(payload))

def capture_process(process, output_dir, *, nonce=None, timeout_seconds=MAX_SECONDS, clock=time.monotonic, executable_sha256=EXE_SHA):
    """Copy ICU to a fresh private folder; inspect an existing read-only handle.

    The 929 process interface is reused (identity/modules/read). No debugger,
    attachment, DLL call, suspension, game launch or remote write is performed.
    Files created here are evidence of this operation only, never a DB export.
    """
    deadline = _Deadline(timeout_seconds, clock, MAX_SECONDS)
    nonce = uuid.uuid4().hex if nonce is None else nonce
    if type(nonce) is not str or not re.fullmatch('[0-9a-f]{32}', nonce):
        raise ContentSnapshotError('Invalid Localization capture nonce')
    profile = source_profile(executable_sha256)
    folder = _resolve_resource_path(Path(output_dir))
    workspace = _resolve_resource_path(ROOT / 'work').resolve()
    if not folder.is_absolute() or _resolve_resource_path(folder).exists():
        raise ContentSnapshotError('Localization output must be a fresh absolute folder')
    parent = _resolve_resource_path(folder.parent).resolve(strict=True)
    if not parent.is_relative_to(workspace):
        raise ContentSnapshotError('Localization output must stay in private workspace work/')
    folder = parent / folder.name
    identity = process.identity()
    if type(identity) is not dict or set(identity) != {'pid', 'creation_filetime', 'image_path'} or type(identity['pid']) is not int or (not 0 < identity['pid'] < 2 ** 32) or (type(identity['creation_filetime']) is not int) or (not 0 < identity['creation_filetime'] < 2 ** 64) or (type(identity['image_path']) is not str):
        raise ContentSnapshotError('Invalid Localization process identity')
    modules = process.modules()
    deadline.check()
    pinned = {}
    for kind in ('exe', 'localization', 'database', 'havok'):
        source = profile['images'][kind]
        expected = _resolve_resource_path(_resolve_resource_path(Path(source['path']))).resolve(strict=True)
        matching = [m for m in modules if _resolve_resource_path(_resolve_resource_path(Path(m['path']))).resolve() == expected]
        if len(matching) != 1 or _file_digest(expected, deadline.check) != source['sha256']:
            raise ContentSnapshotError('Missing/changed/ambiguous Localization module: ' + kind)
        pinned[kind] = {**matching[0], 'sha256': source['sha256']}
    if _resolve_resource_path(_resolve_resource_path(Path(identity['image_path']))).resolve() != _resolve_resource_path(_resolve_resource_path(Path(pinned['exe']['path']))).resolve():
        raise ContentSnapshotError('Localization PID image differs from pinned EXE')
    cores = [m for m in modules if m['name'].lower().startswith('gamecore_') and m['name'].lower().endswith('.dll')]
    if len(cores) != 1:
        raise ContentSnapshotError('Localization capture requires one active GameCore')
    pinned['gamecore'] = {**cores[0], 'sha256': _file_digest(cores[0]['path'], deadline.check)}
    state, payload = read_localization_state(process.read, pinned['localization']['base'], pinned['database']['base'], timeout_seconds=deadline.check(), clock=clock, executable_sha256=executable_sha256)
    if process.identity() != identity or process.modules() != modules:
        raise ContentSnapshotError('Localization process/modules changed during capture')
    for module in pinned.values():
        if _file_digest(module['path'], deadline.check) != module['sha256']:
            raise ContentSnapshotError('Localization module file changed during capture')
    if process.identity() != identity:
        raise ContentSnapshotError('Localization PID changed after module checks')
    folder.mkdir()
    target = folder / 'loaded-icu.dat'
    with _resolve_resource_path(target).open('xb') as stream:
        stream.write(payload)
    if _file_digest(target, deadline.check) != state['icu_sha256']:
        raise ContentSnapshotError('Localization ICU copy differs')
    if process.identity() != identity or process.modules() != modules:
        raise ContentSnapshotError('Localization process/modules changed before publication')
    report = {'schema': 'civ6rl.localization_capture.v2' if executable_sha256 == CURRENT_EXE_SHA else 'civ6rl.localization_capture.v1', 'process': identity, 'nonce': nonce, 'modules': pinned, 'snapshot': state, 'locale': state['locale'], 'dictionary_flag': state['dictionary_flag'], 'icu_data': {'path': str(target), 'sha256': state['icu_sha256'], 'bytes': len(payload)}, 'database': None, 'native_export_allowed': False, 'database_lifetime_lease_proven': False, 'runtime_memory_copied': True, 'game_executable_launched': False, 'remote_code_executed': False, 'memory_written': False, 'save_database_script_bundle_qualified': False, 'strategic_training_ready': False, 'collector_source_sha256': hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_localization_capture.py')))).read_bytes()).hexdigest(), 'route_source_sha256': ROUTE_SHA, 'process_identity_unchanged_before_after': True, 'module_set_unchanged_before_after': True, **({'current_shared_source_sha256': CURRENT_SHARED_SHA, 'executable_sha256': executable_sha256} if executable_sha256 == CURRENT_EXE_SHA else {})}
    deadline.check()
    with _resolve_resource_path(folder / 'localization-manifest.json').open('x', encoding='utf8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report

def capture(pid, output_dir, **kwargs):
    """Explicit caller PID only; this function is not invoked on import."""
    from civ6_host.runtime.workers.capture_official_content929 import ReadOnlyProcess
    with ReadOnlyProcess(pid) as process:
        return capture_process(process, output_dir, **kwargs)

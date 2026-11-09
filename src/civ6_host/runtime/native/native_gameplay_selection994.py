"""Read the official final script list; selection is never execution evidence.

No game code is called, no resolver is reproduced, and no process is written.
The reader rejects unsupported bounds instead of silently omitting entries.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
import json
import math
import struct
import time
from civ6_host.runtime.native.native_resolved_content import ROOT
from civ6_host.runtime.native.native_resolved_content import EXE_SHA
from civ6_host.runtime.native.native_resolved_content import MAX_USER_ADDRESS
from civ6_host.runtime.native.native_resolved_content import ContentSnapshotError
from civ6_host.runtime.native.native_resolved_content import read_resolved_content
from civ6_host.runtime.native.native_resolved_content import source_profile as content_source_profile
ROUTE_SHA256 = '50545b1fd4a7248e7896926da93e5d45c11365133dc8af451d1cee8c14c8dfbf'
AUX_SHA256 = 'b5a3624793720496a071a17870db164f28fe03d5863fc4a2657b11b58229ef1e'
BASE_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MAX_ROWS = 8192
MAX_PATH_UNITS = 259
MAX_READ_BYTES = 16 * 1024 * 1024
MAX_READ_CALLS = 65536
MAX_JOURNAL_RANGES = 16384
MAX_READER_SECONDS = 10.0
MAX_CAPTURE_SECONDS = 30.0
SELECTION_OFFSET = 656
RECORD_BYTES = 40
CURRENT_EXE_SHA256 = 'd1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe'
CURRENT_SOURCE_SHA256 = 'b7a84db116b87f28890f89622553768c8024c2def153cf935df155ea09b7e0ca'

class _Deadline:
    """Cooperative bound: a blocked OS call still needs an external watchdog."""

    def __init__(self, timeout_seconds, clock, maximum):
        if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or (not 0 < timeout_seconds <= maximum) or (not callable(clock)):
            raise ContentSnapshotError('Invalid gameplay selection duration bound')
        self.clock = clock
        self.last = self._now()
        self.end = self.last + timeout_seconds

    def _now(self):
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now):
            raise ContentSnapshotError('Invalid gameplay selection clock')
        return now

    def check(self):
        now = self._now()
        if now < self.last:
            raise ContentSnapshotError('Gameplay selection clock moved backwards')
        self.last = now
        if now >= self.end:
            raise ContentSnapshotError('Gameplay selection cooperative deadline exceeded')
        return self.end - now

def _validate_read_limits(max_read_calls, max_journal_ranges):
    for value, maximum in ((max_read_calls, MAX_READ_CALLS), (max_journal_ranges, MAX_JOURNAL_RANGES)):
        if type(value) is not int or not 0 < value <= maximum:
            raise ContentSnapshotError('Invalid gameplay selection read/range bound')

def source_profile(executable_sha256=EXE_SHA):
    """Verify archived getter bodies and the newly captured field helper."""
    if executable_sha256 == CURRENT_EXE_SHA256:
        path = ROOT / 'work/official-content929/current-exe-source.json'
        raw = _resolve_resource_path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != CURRENT_SOURCE_SHA256:
            raise ContentSnapshotError('Current gameplay selection source pin changed')
        value = json.loads(raw)
        selected = value['selection']
        if value['image']['sha256'] != CURRENT_EXE_SHA256 or value['status']['content_reader_admission'] is not False or selected['status']['runtime_unqualified'] is not True or (selected['status']['content929_admission_implied'] is not False) or (selected['contract_checks']['official_runtime_capture_performed'] is not False):
            raise ContentSnapshotError('Current selection source overclaims its scope')
        for field, verified in selected['contract_checks'].items():
            if field != 'official_runtime_capture_performed' and verified is not True:
                raise ContentSnapshotError('Incomplete current selection contract')
        for ref in selected['historical_sources']:
            if hashlib.sha256(_resolve_resource_path(ROOT / ref['path']).read_bytes()).hexdigest() != ref['sha256']:
                raise ContentSnapshotError('Historical selection source changed')
        spans = selected['verification_spans']
        bodies = {int(row['rva'], 16): bytes.fromhex(row['raw_hex']) for row in spans}
        if len(bodies) != 3 or any((row['kind'] != 'code' for row in spans)) or tuple(sorted(map(len, bodies.values()))) != (8, 55, 95) or (bodies[int(selected['helper']['current_rva'], 16)] != bytes.fromhex('488d8190020000c3')) or (selected['indexed_getter']['record_stride_bytes'] != RECORD_BYTES) or (selected['indexed_getter']['path_pointer_offset'] != 8):
            raise ContentSnapshotError('Invalid current selection getter bodies')
        return {'content': None, 'image': value['image'], 'bodies': bodies, 'manager_global_rva': int(selected['manager_global_rva'], 16), 'current_correspondence_sha256': CURRENT_SOURCE_SHA256}
    if executable_sha256 != EXE_SHA:
        raise ContentSnapshotError('Unsupported gameplay selection executable')
    route_path = ROOT / 'work/phase1-learning994/gameplay-activation-route.json'
    aux_path = ROOT / 'evidence/native-aux-stack.json'
    values = []
    for path, expected in ((route_path, ROUTE_SHA256), (aux_path, AUX_SHA256)):
        raw = _resolve_resource_path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ContentSnapshotError('Gameplay selection source pin changed')
        values.append(json.loads(raw))
    route, aux = values
    helper = route['new_bounded_helper_capture']
    if helper['image_sha256'] != EXE_SHA or helper['rva'] != 2400912 or helper['function_hex'] != '488d8190020000c3' or (aux['images']['exe']['sha256'] != EXE_SHA):
        raise ContentSnapshotError('Unqualified gameplay selection field helper')
    bodies = {helper['rva']: bytes.fromhex(helper['function_hex'])}
    for name, expected_rva, size in (('count_method', 1449600, 55), ('indexed_get_method', 1449504, 95)):
        body = aux['captures'][name]
        fragments = body['fragments']
        if len(fragments) != 1 or int(body['start_va'], 16) != 5368709120 + expected_rva:
            raise ContentSnapshotError('Unexpected gameplay getter extent')
        raw = b''.join((bytes.fromhex(row['bytes']) for row in fragments[0]['instructions']))
        if len(raw) != size:
            raise ContentSnapshotError('Incomplete gameplay getter bytes')
        bodies[expected_rva] = raw
    return {'content': content_source_profile(), 'bodies': bodies}

def read_gameplay_selection(read_memory, image_base, *, max_read_calls=MAX_READ_CALLS, max_journal_ranges=MAX_JOURNAL_RANGES, timeout_seconds=MAX_READER_SECONDS, clock=time.monotonic, executable_sha256=EXE_SHA, include_resolved_content=False):
    """Return the exact final list and stable read observations, not admission.

    Null/empty rows remain records because the original consumer skips them.
    Duplicate strings and their order are preserved. The only known header
    fields are begin/end; no capacity or other record fields are interpreted.
    Re-reading is change detection and does not guarantee an atomic snapshot.
    """
    if not callable(read_memory) or type(include_resolved_content) is not bool:
        raise ContentSnapshotError('Invalid memory reader')
    _validate_read_limits(max_read_calls, max_journal_ranges)
    deadline = _Deadline(timeout_seconds, clock, MAX_READER_SECONDS)
    profile = source_profile(executable_sha256)
    deadline.check()
    consumed = calls = 0

    def bounded(address, size):
        nonlocal consumed, calls
        deadline.check()
        if calls >= max_read_calls:
            raise ContentSnapshotError('Gameplay selection read-call bound exceeded')
        if type(address) is not int or type(size) is not int or size <= 0 or (address < 65536) or (address > MAX_USER_ADDRESS - size) or (consumed + size > MAX_READ_BYTES):
            raise ContentSnapshotError('Gameplay selection memory bounds exceeded')
        calls += 1
        raw = read_memory(address, size)
        deadline.check()
        consumed += size
        if type(raw) is not bytes or len(raw) != size:
            raise ContentSnapshotError('Incomplete gameplay selection memory read')
        return raw
    current = executable_sha256 == CURRENT_EXE_SHA256
    if current:
        if type(image_base) is not int or image_base % 65536 or (not 65536 <= image_base <= MAX_USER_ADDRESS - 50331648):
            raise ContentSnapshotError('Invalid current selection image base')
        before = read_resolved_content(bounded, image_base, executable_sha256=executable_sha256) if include_resolved_content else None
    else:
        before = read_resolved_content(bounded, image_base)
    journal = []

    def remember(address, size):
        if len(journal) >= max_journal_ranges:
            raise ContentSnapshotError('Gameplay selection journal range bound exceeded')
        raw = bounded(address, size)
        journal.append((address, raw))
        return raw
    for rva, expected in profile['bodies'].items():
        if remember(image_base + rva, len(expected)) != expected:
            raise ContentSnapshotError('Gameplay getter code differs from pinned source')
    if current:
        manager = struct.unpack('<Q', remember(image_base + profile['manager_global_rva'], 8))[0]
        if manager % 8 or not 65536 <= manager <= MAX_USER_ADDRESS - SELECTION_OFFSET - 16:
            raise ContentSnapshotError('Absent/unaligned current selection manager')
        if before is not None and int(before['manager_address'], 16) != manager:
            raise ContentSnapshotError('Selection manager differs from resolved content')
    else:
        manager = int(before['manager_address'], 16)
    header = remember(manager + SELECTION_OFFSET, 16)
    begin, end = struct.unpack('<2Q', header)
    if (begin, end) == (0, 0):
        count = 0
    else:
        if not 65536 <= begin <= end <= MAX_USER_ADDRESS or begin % 8 or end % 8 or (end - begin) % RECORD_BYTES or ((end - begin) // RECORD_BYTES > MAX_ROWS):
            raise ContentSnapshotError('Unsupported gameplay selection vector bounds')
        count = (end - begin) // RECORD_BYTES
    payload = remember(begin, count * RECORD_BYTES) if count else b''
    records = []
    for index in range(count):
        pointer = struct.unpack_from('<Q', payload, index * RECORD_BYTES + 8)[0]
        path = None
        if pointer:
            if not 65536 <= pointer <= MAX_USER_ADDRESS - 2 or pointer % 2:
                raise ContentSnapshotError('Invalid gameplay path pointer')
            raw = bytearray()
            for offset in range(MAX_PATH_UNITS + 1):
                unit = remember(pointer + offset * 2, 2)
                if unit == b'\x00\x00':
                    break
                raw.extend(unit)
            else:
                raise ContentSnapshotError('Gameplay path exceeds supported UTF-16 bound')
            try:
                path = raw.decode('utf-16-le', errors='strict')
            except UnicodeDecodeError as exc:
                raise ContentSnapshotError('Invalid gameplay path UTF-16') from exc
        records.append({'index': index, 'path_pointer': hex(pointer), 'path': path, 'consumer_skips': path is None or path == ''})
    for address, raw in reversed(journal):
        if bounded(address, len(raw)) != raw:
            raise ContentSnapshotError('Gameplay selection changed during capture')
    if before is not None:
        after = read_resolved_content(bounded, image_base, executable_sha256=executable_sha256) if current else read_resolved_content(bounded, image_base)
        if before != after:
            raise ContentSnapshotError('Resolved content changed around gameplay selection')
    deadline.check()
    return {'schema': 'civ6rl.gameplay_selection994.memory_snapshot.v2' if current else 'civ6rl.gameplay_selection994.memory_snapshot.v1', 'route_source_sha256': ROUTE_SHA256, 'getter_source_sha256': AUX_SHA256, 'executable_sha256': executable_sha256, 'image_base': hex(image_base), 'manager_address': hex(manager), 'resolved_content': before, 'vector_header_hex': header.hex(), 'record_count': count, 'records': records, 'selected_paths': [row['path'] for row in records if not row['consumer_skips']], 'memory_bytes_read': consumed, 'observed_ranges_unchanged': True, 'memory_read_calls': calls, 'journal_ranges': len(journal), 'bounds': {'max_read_calls': max_read_calls, 'max_journal_ranges': max_journal_ranges, 'cooperative_timeout_seconds': timeout_seconds}, 'atomic_snapshot_proven': False, 'execution_proven': False, 'source_file_bytes_bound': False, 'save_identity_bound': False, 'database_identity_bound': False, 'training_eligible': False, 'player_observation': False, 'read_only': True, **({'current_correspondence_sha256': CURRENT_SOURCE_SHA256, 'resolved_content_captured': before is not None, 'manager_global_rva': hex(profile['manager_global_rva'])} if current else {})}

def _file_digest(path, check_deadline=None):
    digest = hashlib.sha256()
    with _resolve_resource_path(_resolve_resource_path(Path(path))).open('rb') as stream:
        while True:
            if check_deadline is not None:
                check_deadline()
            block = stream.read(1024 * 1024)
            if check_deadline is not None:
                check_deadline()
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()

def capture_process(process, *, timeout_seconds=MAX_CAPTURE_SECONDS, clock=time.monotonic, max_read_calls=MAX_READ_CALLS, max_journal_ranges=MAX_JOURNAL_RANGES, executable_sha256=EXE_SHA, include_resolved_content=False):
    """Capture through 929 with a cooperative deadline and bounded reads.

    Identity/module APIs are checked immediately after return, and file hashing
    checks between 1 MiB chunks. A stalled OS call cannot be preempted here;
    the caller's process watchdog remains necessary for a hard time limit.
    """
    if type(include_resolved_content) is not bool:
        raise ContentSnapshotError('Invalid resolved-content capture option')
    _validate_read_limits(max_read_calls, max_journal_ranges)
    deadline = _Deadline(timeout_seconds, clock, MAX_CAPTURE_SECONDS)
    profile = source_profile(executable_sha256)
    expected = _resolve_resource_path(_resolve_resource_path(Path((profile['image'] if executable_sha256 == CURRENT_EXE_SHA256 else profile['content']['image'])['path']))).resolve(strict=True)
    deadline.check()
    if _file_digest(expected, deadline.check) != executable_sha256:
        raise ContentSnapshotError('Installed EXE differs from pinned source')
    identity = process.identity()
    deadline.check()
    if _resolve_resource_path(_resolve_resource_path(Path(identity['image_path']))).resolve(strict=True) != expected:
        raise ContentSnapshotError('PID does not identify the pinned CivilizationVI executable')
    modules = process.modules()
    deadline.check()
    mains = [m for m in modules if _resolve_resource_path(_resolve_resource_path(Path(m['path']))).resolve() == expected]
    cores = [m for m in modules if m['name'].lower().startswith('gamecore_') and m['name'].lower().endswith('.dll')]
    if len(mains) != 1 or len(cores) != 1:
        raise ContentSnapshotError('Capture requires one EXE and one GameCore module')
    core = cores[0]
    core_sha = _file_digest(core['path'], deadline.check)
    options = {} if executable_sha256 == EXE_SHA else {'executable_sha256': executable_sha256}
    if include_resolved_content:
        options['include_resolved_content'] = include_resolved_content
    state = read_gameplay_selection(process.read, mains[0]['base'], timeout_seconds=min(MAX_READER_SECONDS, deadline.check()), clock=clock, max_read_calls=max_read_calls, max_journal_ranges=max_journal_ranges, **options)
    if process.identity() != identity:
        raise ContentSnapshotError('Process identity changed during capture')
    deadline.check()
    after_modules = process.modules()
    deadline.check()
    key = lambda m: (m['base'], m['name'], m['path'], m['bytes'])
    if sorted(modules, key=key) != sorted(after_modules, key=key):
        raise ContentSnapshotError('Process modules changed during capture')
    if _file_digest(expected, deadline.check) != executable_sha256 or _file_digest(core['path'], deadline.check) != core_sha:
        raise ContentSnapshotError('Executable file changed during capture')
    if process.identity() != identity:
        raise ContentSnapshotError('Process identity changed after final module/file checks')
    deadline.check()
    return {'schema': 'civ6rl.official_gameplay_selection994.capture.v2' if executable_sha256 == CURRENT_EXE_SHA256 else 'civ6rl.official_gameplay_selection994.capture.v1', 'process': identity, 'exe_module': mains[0], 'gamecore_module': {**core, 'sha256': core_sha}, 'snapshot': state, 'consumer_core_matches_base_proof': core_sha == BASE_CORE_SHA256, 'read_only_process_rights': 1024 | 16, 'game_executable_launched': False, 'remote_code_executed': False, 'process_suspended': False, 'memory_written': False, 'execution_proven': False, 'save_database_script_bundle_qualified': False, 'strategic_training_ready': False, 'cooperative_timeout_seconds': timeout_seconds}

def capture(pid, *, timeout_seconds=MAX_CAPTURE_SECONDS, clock=time.monotonic, max_read_calls=MAX_READ_CALLS, max_journal_ranges=MAX_JOURNAL_RANGES, executable_sha256=EXE_SHA, include_resolved_content=False):
    """Inspect an explicit existing PID; never launch or attach a debugger."""
    from civ6_host.runtime.workers.capture_official_content929 import ReadOnlyProcess
    with ReadOnlyProcess(pid) as process:
        return capture_process(process, timeout_seconds=timeout_seconds, clock=clock, max_read_calls=max_read_calls, max_journal_ranges=max_journal_ranges, executable_sha256=executable_sha256, include_resolved_content=include_resolved_content)

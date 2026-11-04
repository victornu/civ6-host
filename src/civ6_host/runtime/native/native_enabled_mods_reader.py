"""Read the existing Core-owned GAME_ROOT.ENABLED_MODS value.

This bounded diagnostic reader only observes the detached, retained
NativeApplicationConfiguration clone before NewGame. It does not create a
cell, resolve dependencies, activate mods/DLC, or mutate game configuration.
The vector and counted-string layouts are statically verified against pinned
PE bytes; this staged reader has not been executed against a live Core object.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
from pathlib import Path
import struct
from typing import Any
from typing import Iterable
from civ6_host.runtime.native import native_application_configuration as app
from civ6_host.runtime.native import native_configuration_finalization as setup
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_enabled_mods_reader.py')))).resolve().parents[1]
READ699_SHA256 = 'e3ed0a102277eef61177963fceaf1986b7d2eba6bd19717327fa3f51f01d4fd2'
CAPTURE715_SHA256 = 'cc68028164e6934fcd5408e3f6112dd8ac79baa5d8d2e1f2e42f05d4936cd190'
MANIFEST715_SHA256 = '8532f1af5213d73308f95f75805c25faf2f77152470e32999cf5030aa5cbed76'
CAPTURE736_SHA256 = '3a7cc2ac220e94d24255d096bff0f180f594a2af67431da5d256b99f5996d289'
APPLICATION_CONFIGURATION_SHA256 = 'b66f3a01ddbe2d513dd7e6a0616b236149db82842208566399303ad9010539f0'
READ699_PATH = ROOT / 'work/native-enabledmods-read699/read699.json'
CAPTURE715_PATH = ROOT / 'work/native-enabledmods-core715/capture715.json'
MANIFEST715_PATH = ROOT / 'work/native-enabledmods-core715/manifest715.json'
CAPTURE736_PATH = ROOT / 'work/native-core-string736/capture736.json'
ENABLED_MODS_KEY = 462213576
MOD_ID_KEY = 3728818622
TREE_VTABLE_RVA = 8507296
TREE_LOOKUP_RVA = 7625904
LIST_VTABLE_RVA = 8510112
LIST_BEGIN_OFFSET = 40
LIST_END_OFFSET = 48
LIST_CAPACITY_OFFSET = 56
VARIANT_SIZE = 24
LIST_STRIDE = 24
TAG_MAP = 10
TAG_VECTOR = 11
TAG_STRING = 5
MAP_FLAGS = 83886080
VECTOR_FLAGS = 285212672
STRING_FLAGS_BASE = 553648128
MAX_MODS = 256
MAX_MOD_ID_BYTES = 256
_LIST_VTABLE_SLOTS = ((0, 7659616), (8, 7661664), (16, 7662048), (24, 7661648), (32, 7661648), (40, 7661648), (48, 7646368), (56, 7646448), (64, 7638640), (72, 7638640), (80, 7645984), (88, 0))

def _proof_path(relative: str) -> Path:
    return ROOT / _resolve_resource_path(Path(relative))

def _file_sha256(path: Path) -> str:
    return hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest()

def verify_source() -> dict[str, Any]:
    """Validate the closed 699/715/736 source chain and local reader parent."""
    read_plan = load_pinned_json(READ699_PATH, READ699_SHA256)
    capture715 = load_pinned_json(CAPTURE715_PATH, CAPTURE715_SHA256)
    manifest715 = load_pinned_json(MANIFEST715_PATH, MANIFEST715_SHA256)
    capture736 = load_pinned_json(CAPTURE736_PATH, CAPTURE736_SHA256)
    keys = read_plan.get('known_offsets_and_tags', {})
    if read_plan.get('schema') != 'civ6rl.native_application_enabled_mods_read_plan699.v1' or read_plan.get('images') != {'core_sha256': setup.CORE_SHA256, 'exe_sha256': setup.EXE_SHA256} or keys.get('core_provider_vtable_rva') != '0x81CFA0' or (keys.get('core_provider_lookup_slot') != '+0x58 -> Core RVA 0x745CB0') or (keys.get('enabled_mods_key_derived_from_pinned_name_hash') != '0x1B8CD1C8') or (keys.get('modid_member_key_derived_from_pinned_name_hash') != '0xDE4141BE') or (keys.get('enabled_mods_cell') != 'tag 0xB, flags 0x11000000, payload points to vector object') or (keys.get('enabled_mods_element') != 'tag 0xA map, flags 0x05000000; ModId is a string member, not ModRowId integer'):
        raise RuntimeError('Enabled-mods read plan 699 source contract changed')
    list_class = capture715.get('list_class', {})
    layout = list_class.get('layout', {})
    observed_slots = {int(row['offset'], 16): 0 if row['target_va'] == '0x0' else int(row['target_va'], 16) - 6442450944 for row in list_class.get('vtable_slots', ())}
    expected_slots = dict(_LIST_VTABLE_SLOTS)
    if capture715.get('schema') != 'civ6rl.native_enabledmods_core_tagb_container715.v1' or capture715.get('images', {}).get('core_sha256') != setup.CORE_SHA256 or capture715.get('validation', {}).get('all_captured_instructions_match_pinned_core') is not True or (capture715.get('validation', {}).get('tagb_branch_addresses_match_parent') is not True) or (capture715.get('validation', {}).get('vtable_entries_match_expected_targets') is not True) or (list_class.get('vtable_va') != '0x18081daa0') or (layout.get('begin_offset') != '0x28') or (layout.get('end_offset') != '0x30') or (layout.get('capacity_end_offset') != '0x38') or (layout.get('element_stride') != LIST_STRIDE) or (observed_slots != expected_slots):
        raise RuntimeError('Enabled-mods Core vector source contract changed')
    if manifest715.get('schema') != 'civ6rl.native_enabledmods_core715_manifest.v1' or manifest715.get('outputs', {}).get('work/native-enabledmods-core715/capture715.json') != CAPTURE715_SHA256 or manifest715.get('parents', {}).get('work/native-enabledmods-read699/read699.json') != READ699_SHA256:
        raise RuntimeError('Enabled-mods 715 provenance manifest changed')
    profile = capture736.get('candidate_read_profile', {})
    asserted = {row.get('va'): (row.get('bytes'), row.get('text')) for row in capture736.get('asserted_instructions', ())}
    if capture736.get('schema') != 'civ6rl.native_core_tag5_counted_string736.static.v1' or capture736.get('core_sha256') != setup.CORE_SHA256 or capture736.get('native_execution') is not False or (capture736.get('all_captured_instructions_match_pinned_PE') is not True) or (capture736.get('verified_instruction_count') != 655) or (profile.get('tag') != TAG_STRING) or (profile.get('element_size') != 1) or (profile.get('upper_flags') != '0x21000000') or (profile.get('length') != 'flags & 0x00ffffff; diagnostic limit<=256 bytes including final NUL') or (profile.get('live_validation_done') is not False) or (asserted.get('0x18003c464') != ('66833905', 'cmp word ptr [rcx], 5')) or (asserted.get('0x18003c46a') != ('488b5108', 'mov rdx, qword ptr [rcx + 8]')) or (asserted.get('0x180747cb4') != ('8b4610', 'mov eax, dword ptr [rsi + 0x10]')) or (asserted.get('0x180747cb7') != ('81e2ffffff00', 'and edx, 0xffffff')):
        raise RuntimeError('Core tag-5 counted-string source contract changed')
    parent715 = capture736.get('parents', {}).get('work/native-enabledmods-core715/capture715.json', {})
    if parent715.get('sha256') != CAPTURE715_SHA256:
        raise RuntimeError('736 does not pin the 715 Core vector capture')
    if _file_sha256(ROOT / 'civ6rl/native_application_configuration.py') != APPLICATION_CONFIGURATION_SHA256:
        raise RuntimeError('NativeApplicationConfiguration reader parent changed')
    for relative, details in capture736.get('parents', {}).items():
        expected = details.get('sha256')
        if not isinstance(expected, str) or _file_sha256(_proof_path(relative)) != expected:
            raise RuntimeError('736 parent source changed: ' + relative)
    return {'read699': read_plan, 'capture715': capture715, 'manifest715': manifest715, 'capture736': capture736}

def _read(read, address: int, size: int) -> bytes:
    if type(address) is not int or address <= 0 or type(size) is not int or (not 0 < size <= 4096) or (address > 18446744073709551615 - size + 1):
        raise ValueError('Invalid bounded enabled-mods memory read')
    value = read(address, size)
    if type(value) is not bytes or len(value) != size:
        raise ValueError('Incomplete enabled-mods memory read')
    return value

def _qword(read, address: int) -> int:
    return struct.unpack('<Q', _read(read, address, 8))[0]

def _lookup_existing(base: int, tree_map: int, key: int, read, call) -> int | None:
    table = base + TREE_VTABLE_RVA
    if _qword(read, tree_map) != table:
        raise ValueError('Unexpected Core tree-map vtable')
    if _qword(read, table + 88) != base + TREE_LOOKUP_RVA:
        raise ValueError('Unverified Core existing-key lookup slot')
    cell = setup._invoke(call, base + TREE_LOOKUP_RVA, C.c_void_p, tree_map, (C.c_uint32,), key)
    if cell is None:
        return None
    if type(cell) is not int:
        raise ValueError('Core existing-key lookup returned an invalid cell')
    if cell == 0:
        return None
    if cell < 0:
        raise ValueError('Core existing-key lookup returned an invalid cell')
    return cell

def _variant(raw: bytes) -> dict[str, int | bytes]:
    if type(raw) is not bytes or len(raw) != VARIANT_SIZE:
        raise ValueError('Invalid 24-byte Core variant cell')
    tag, extra = struct.unpack_from('<HH', raw, 0)
    payload = struct.unpack_from('<Q', raw, 8)[0]
    size = struct.unpack_from('<I', raw, 16)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    return {'raw': raw, 'tag': tag, 'extra': extra, 'payload': payload, 'size': size, 'flags': flags}

def _verify_list_vtable(base: int, vector: int, read) -> None:
    if _qword(read, vector) != base + LIST_VTABLE_RVA:
        raise ValueError('ENABLED_MODS value is not the pinned Core tag-B vector')
    table = base + LIST_VTABLE_RVA
    for slot, target_rva in _LIST_VTABLE_SLOTS:
        if _qword(read, table + slot) != (base + target_rva if target_rva else 0):
            raise ValueError('Unverified tag-B vector vtable slot +0x%x' % slot)

def _vector_header(base: int, vector: int, read) -> tuple[bytes, int, int, int, int]:
    _verify_list_vtable(base, vector, read)
    raw = _read(read, vector, 64)
    begin, end, capacity = struct.unpack_from('<QQQ', raw, LIST_BEGIN_OFFSET)
    if begin == end == capacity == 0:
        return (raw[:8] + raw[LIST_BEGIN_OFFSET:LIST_CAPACITY_OFFSET + 8], begin, end, capacity, 0)
    if not begin or begin > end or end > capacity or any((address % 8 for address in (begin, end, capacity))):
        raise ValueError('Malformed tag-B vector begin/end/capacity pointers')
    if (end - begin) % LIST_STRIDE or (capacity - begin) % LIST_STRIDE:
        raise ValueError('Tag-B vector boundaries do not use the proven 24-byte stride')
    count = (end - begin) // LIST_STRIDE
    if count > MAX_MODS or (capacity - begin) // LIST_STRIDE > MAX_MODS:
        raise ValueError('Tag-B vector exceeds the bounded enabled-mod count')
    stable = raw[:8] + raw[LIST_BEGIN_OFFSET:LIST_CAPACITY_OFFSET + 8]
    return (stable, begin, end, capacity, count)

def _read_mod_id(base: int, map_pointer: int, read, call) -> tuple[str, int, bytes, bytes]:
    if _qword(read, map_pointer) != base + TREE_VTABLE_RVA:
        raise ValueError('Enabled-mod element is not a Core owned map')
    cell = _lookup_existing(base, map_pointer, MOD_ID_KEY, read, call)
    if cell is None:
        raise LookupError('Enabled-mod element has no existing ModId cell')
    cell_raw = _read(read, cell, VARIANT_SIZE)
    variant = _variant(cell_raw)
    if variant['tag'] != TAG_STRING or variant['extra'] != 0:
        raise ValueError('ModId must use the proven Core tag-5 string variant')
    flags = variant['flags']
    count = flags & 16777215
    if flags & 4278190080 != STRING_FLAGS_BASE or variant['size'] != 1:
        raise ValueError('ModId tag-5 flags or element size are outside the source profile')
    if not 1 <= count <= MAX_MOD_ID_BYTES:
        raise ValueError('ModId counted string is empty or exceeds the 256-byte read bound')
    pointer = variant['payload']
    if not pointer or pointer > 18446744073709551615 - count:
        raise ValueError('ModId counted string pointer is invalid')
    raw = _read(read, pointer, count)
    if raw[-1:] != b'\x00' or b'\x00' in raw[:-1]:
        raise ValueError('ModId must contain exactly one final NUL')
    try:
        value = raw[:-1].decode('ascii', 'strict')
    except UnicodeDecodeError as exc:
        raise ValueError('ModId must be ASCII') from exc
    if not value:
        raise ValueError('ModId must be nonempty')
    return (value, cell, cell_raw, raw)

def _expected_ids(value: Iterable[str] | None) -> frozenset[str] | None:
    if value is None:
        return None
    if type(value) not in (tuple, list, set, frozenset):
        raise TypeError('expected_mod_ids must be a bounded tuple/list/set or None')
    rows = tuple(value)
    if len(rows) > MAX_MODS:
        raise ValueError('Expected ModId set exceeds the 256-entry bound')
    for item in rows:
        if type(item) is not str or not item:
            raise ValueError('Expected ModId values must be nonempty strings')
        try:
            encoded = item.encode('ascii', 'strict')
        except UnicodeEncodeError as exc:
            raise ValueError('Expected ModId values must be ASCII') from exc
        if b'\x00' in encoded or len(encoded) + 1 > MAX_MOD_ID_BYTES:
            raise ValueError('Expected ModId value exceeds the bounded C-string profile')
    result = frozenset(rows)
    if len(result) != len(rows):
        raise ValueError('Expected ModId values contain duplicates')
    return result

def read_enabled_mods(owner: app.NativeApplicationConfiguration, *, expected_mod_ids: Iterable[str] | None=None, stopped_configuration_phase: bool=False) -> dict[str, Any]:
    """Read exact declared ModId strings from the retained clone's GAME_ROOT.

    The caller must invoke this at a synchronous stopped configuration boundary
    before NewGame, while the existing application owner is alive. Only the
    already-existing native lookup method is called. An absent property is an
    explicit result and never causes insertion or activation inference.
    """
    if not isinstance(owner, app.NativeApplicationConfiguration):
        raise TypeError('Expected a retained NativeApplicationConfiguration owner')
    if stopped_configuration_phase is not True:
        raise ValueError('Enabled-mod reading requires an explicit stopped configuration phase')
    if owner.new_game_entered is not False:
        raise RuntimeError('Enabled-mod reading is limited to before NewGame')
    expected = _expected_ids(expected_mod_ids)
    proof = verify_source()
    base, context, read, call = (owner.base, owner.context, owner.read, owner.call)
    if type(base) is not int or base <= 0 or type(context) is not int or (context <= 0):
        raise ValueError('Invalid retained application owner identity')
    if not callable(read):
        raise TypeError('Application owner has no bounded memory reader')

    def owner_snapshot():
        owner._check_guard()
        owner.require_context(base, context)
        if owner.new_game_entered is not False:
            raise RuntimeError('Application entered NewGame during enabled-mod reading')
        snapshot = owner.snapshot()
        if snapshot.get('descriptor') != owner.pointer:
            raise ValueError('Application descriptor identity changed')
        if type(snapshot.get('normalized')) is not int or snapshot['normalized'] <= 0:
            raise ValueError('Normalized GAME_ROOT map is absent')
        return snapshot
    before = owner_snapshot()
    game_root = before['normalized']
    if _qword(read, game_root) != base + TREE_VTABLE_RVA:
        raise ValueError('Normalized GAME_ROOT is not the pinned Core tree map')
    mods_cell = _lookup_existing(base, game_root, ENABLED_MODS_KEY, read, call)
    if mods_cell is None:
        if expected is not None and expected:
            raise ValueError('Absent ENABLED_MODS property differs from the explicitly expected set')
        after = _lookup_existing(base, game_root, ENABLED_MODS_KEY, read, call)
        if after is not None or owner_snapshot() != before:
            raise RuntimeError('Absent ENABLED_MODS property changed during read')
        return {'schema': 'civ6rl.native_enabled_mods_read.v2', 'owner_provider': owner.pointer, 'game_root_map': game_root, 'property_present': False, 'mod_ids': None, 'entry_count': None, 'expected_mod_ids_supplied': expected is not None, 'expected_mod_ids_match': None, 'property_source_key': ENABLED_MODS_KEY, 'source_proofs': {'read699_sha256': READ699_SHA256, 'capture715_sha256': CAPTURE715_SHA256, 'capture736_sha256': CAPTURE736_SHA256}, 'read_only': True, 'native_activation_verified': False, 'core_layout_live_validation_done': False, 'eligible_for_training': False}
    tagb_raw = _read(read, mods_cell, VARIANT_SIZE)
    tagb = _variant(tagb_raw)
    if tagb['tag'] != TAG_VECTOR or tagb['extra'] != 0 or tagb['size'] != 0 or (tagb['flags'] != VECTOR_FLAGS) or (not tagb['payload']):
        raise ValueError('ENABLED_MODS cell is outside the exact tag-B vector profile')
    vector = tagb['payload']
    header, begin, end, capacity, count = _vector_header(base, vector, read)
    entry_raws: list[bytes] = []
    child_maps: list[int] = []
    strings: list[tuple[str, bytes, bytes]] = []
    ids: list[str] = []
    for index in range(count):
        cell = begin + index * LIST_STRIDE
        raw = _read(read, cell, VARIANT_SIZE)
        entry = _variant(raw)
        if entry['tag'] != TAG_MAP or entry['extra'] != 0 or entry['size'] != 0 or (entry['flags'] != MAP_FLAGS) or (not entry['payload']):
            raise ValueError('ENABLED_MODS entry is outside the exact owned tag-A map profile')
        child = entry['payload']
        value, lookup_cell, string_cell, string_bytes = _read_mod_id(base, child, read, call)
        if value in ids or child in child_maps:
            raise ValueError('ENABLED_MODS contains duplicate ModId or map identity')
        entry_raws.append(raw)
        child_maps.append(child)
        strings.append((value, lookup_cell, string_cell, string_bytes))
        ids.append(value)
    if expected is not None and frozenset(ids) != expected:
        raise ValueError('Observed ModId set differs from the explicitly expected set')
    if _read(read, mods_cell, VARIANT_SIZE) != tagb_raw:
        raise RuntimeError('ENABLED_MODS variant cell changed during read')
    header_after, begin_after, end_after, capacity_after, count_after = _vector_header(base, vector, read)
    if (header_after, begin_after, end_after, capacity_after, count_after) != (header, begin, end, capacity, count):
        raise RuntimeError('ENABLED_MODS vector header changed during read')
    for index, raw in enumerate(entry_raws):
        if _read(read, begin + index * LIST_STRIDE, VARIANT_SIZE) != raw:
            raise RuntimeError('ENABLED_MODS vector entry changed during read')
        child = child_maps[index]
        value_after, lookup_cell_after, string_cell_after, string_bytes_after = _read_mod_id(base, child, read, call)
        if (value_after, lookup_cell_after, string_cell_after, string_bytes_after) != strings[index]:
            raise RuntimeError('ModId cell or counted bytes changed during read')
    if _lookup_existing(base, game_root, ENABLED_MODS_KEY, read, call) != mods_cell:
        raise RuntimeError('ENABLED_MODS lookup identity changed during read')
    if owner_snapshot() != before:
        raise RuntimeError('Application owner or normalized map topology changed during read')
    return {'schema': 'civ6rl.native_enabled_mods_read.v2', 'owner_provider': owner.pointer, 'game_root_map': game_root, 'property_present': True, 'mod_ids': tuple(ids), 'entry_count': count, 'expected_mod_ids_supplied': expected is not None, 'expected_mod_ids_match': frozenset(ids) == expected if expected is not None else None, 'property_source_key': ENABLED_MODS_KEY, 'source_proofs': {'read699_sha256': READ699_SHA256, 'capture715_sha256': CAPTURE715_SHA256, 'capture736_sha256': CAPTURE736_SHA256}, 'read_only': True, 'native_activation_verified': False, 'core_layout_live_validation_done': False, 'eligible_for_training': False}

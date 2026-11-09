"""Exact XP2 queue reader and captured human queue-tab route.

Admission selects an immutable source/input profile, not captured city state or
current legality. The shared native queue catalogue and request remain intact.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/host-extensions/xp2-production-queue-static/source-profile-v1.json',
          '9b37e1e51be65fb90bf125d14db21c2dc75fc1af6f86592fd4c11b647f0d8df3')
GET_AT_RVA = 0x68BE20
_BASE = 0x180000000
_FIELDS = frozenset(('Directive', 'BuildingType', 'UnitType', 'MilitaryFormationType',
                    'DistrictType', 'ProjectType', 'Modifiers', 'x', 'y', 'Location'))


def _bodies(proof):
    for body in proof['functions'].values():
        joined = b''
        starts = set()
        rows = []
        if body['all_conditional_targets_captured'] is not True:
            raise ValueError('XP2 queue incomplete native body')
        for fragment in body['fragments']:
            raw = bytes.fromhex(fragment['raw_hex'])
            rva = int(fragment['start_rva'], 16)
            cursor = rva
            for row in fragment['instructions']:
                code = bytes.fromhex(row['bytes'])
                if (not code or int(row['rva'], 16) != cursor
                        or int(row['va'], 16) != _BASE + cursor
                        or raw[cursor-rva:cursor-rva+len(code)] != code):
                    raise ValueError('XP2 queue instruction coverage changed')
                starts.add(cursor)
                cursor += len(code)
                rows.append(row)
            if (cursor != rva+len(raw) or not raw or len(raw) != fragment['length']
                    or int(fragment['end_rva_exclusive'], 16) != cursor
                    or hashlib.sha256(raw).hexdigest() != fragment['sha256']):
                raise ValueError('XP2 queue full fragment changed')
            joined += raw
        if (len(body['fragments']) != body['fragment_count']
                or joined.hex() != body['raw_hex'] or len(joined) != body['total_length']
                or hashlib.sha256(joined).hexdigest() != body['sha256']
                or tuple(rows) != tuple(body['instructions'])):
            raise ValueError('XP2 queue full body changed')
        for edge in body['conditional_branch_targets_verified']:
            if int(edge['source_rva'], 16) not in starts or int(edge['target_rva'], 16) not in starts:
                raise ValueError('XP2 queue conditional branch omitted')
    table = proof['embedded_tables']['string_hash_switch']
    raw = bytes.fromhex(table['raw_hex'])
    starts = {row['rva'] for row in proof['functions']['0xd760']['instructions']}
    if (table['rva'] != '0xd9a0' or table['length'] != 52 or len(raw) != 52
            or table['pdata_end_rva'] != '0xd9d4'
            or hashlib.sha256(raw).hexdigest() != table['sha256']
            or tuple(hex(int.from_bytes(raw[i:i+4], 'little')) for i in range(0, 52, 4)) != tuple(table['targets'])
            or any(target not in starts for target in table['targets'])):
        raise ValueError('XP2 queue string-key switch table changed')


def _witness(proof):
    from .xp2_bundle_inputs import REFERENCE
    manifest = _source(REFERENCE)
    if (proof['capture_manifest']['sha256'] != REFERENCE[1]
            or manifest['process_after']['gamecore_module']['sha256'] != XP2_CORE_SHA256
            or manifest['ui_availability']['observed_states_equal'] is not True
            or manifest['ui_availability']['same_bridge_session'] is not True):
        raise ValueError('XP2 queue UI capture identity changed')
    if len(proof['captured_ui_witnesses']) != 2:
        raise ValueError('XP2 queue requires both retained UI witnesses')
    for side, ref in zip(('before', 'after'), proof['captured_ui_witnesses']):
        name = 'ui-availability-' + side + '.json'
        if (Path(ref['path']).name != name
                or manifest['artifacts'][name]['sha256'] != ref['sha256']):
            raise ValueError('XP2 queue witness is not from its exact capture')
        row = _source((ref['path'], ref['sha256']))['diagnostics']['ui_availability']
        if (row['schema'] != 'civ6rl.ui_availability.v2' or row['read_only'] is not True
                or row['observed_unchanged'] is not True or row['player_id'] != 0
                or row['runtime_context_sources_verified'] is not False):
            raise ValueError('XP2 queue witness scope changed')
        for key in ('active', 'manager_active', 'overlay_enabled'):
            if row['tutorial'][key] != {'status': 'observed', 'value': False}:
                raise ValueError('XP2 tutorial queue gate not witnessed inactive')
        if row['tutorial']['any_multiplayer'] != {'status': 'observed', 'value': True}:
            raise ValueError('XP2 queue requires its captured multiplayer profile')
        for key in ('city_production', 'production_queue_tab'):
            for prop in ('hidden', 'disabled'):
                if row['controls'][key][prop] != {'status': 'observed', 'value': False}:
                    raise ValueError('XP2 human queue control route unavailable')


def _ui_source(proof):
    texts = {}
    for key, ref in proof['official_ui_sources'].items():
        raw = resolve_path(Path(ref['path'])).read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref['sha256']:
            raise ValueError('Official XP2 queue source changed: ' + key)
        texts[key] = raw.decode('utf-8-sig')
    if (any(name in texts['modinfo'] for name in ('ProductionPanel', 'ProductionHelper', 'Civ6Common'))
            or 'include("CityPanel_Expansion1")' not in texts['city_xp2']
            or 'include("CityPanel")' not in texts['city_inherited']
            or any(name in texts['city_xp2']+texts['city_inherited']
                   for name in ('ChangeProductionCheck', 'OnProduction', 'QueueTab'))):
        raise ValueError('XP2 queue official UI resolution changed')
    panel = texts['panel']
    if (len(re.findall(r'm_tutorialTestMode\s*(?::\s*boolean)?\s*=', panel)) != 1
            or 'local m_tutorialTestMode:boolean = false;' not in panel
            or len(re.findall(r'm_isTutorialRunning\s*(?::\s*boolean)?\s*=', panel)) != 2
            or 'm_isTutorialRunning = IsTutorialRunning();' not in panel
            or 'return Modding.IsModActive(TUTORIAL_UUID);' not in texts['common']
            or 'MAX_QUEUE_SIZE = 7;' not in texts['helper']):
        raise ValueError('XP2 queue static tutorial/capacity contract changed')
    for key, ranges in proof['official_ui_anchors'].items():
        lines = texts[key].splitlines()
        for row in ranges:
            if '\n'.join(lines[row['first']-1:row['last']]) != row['text']:
                raise ValueError('XP2 queue UI algorithm anchor changed')


def verify_source(core_sha256=XP2_CORE_SHA256):
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('XP2 queue source requires its exact engine')
    proof = _source(SOURCE)
    binding = proof['bindings']['BuildQueue.GetAt']
    if (proof['schema'] != 'civ6_host.xp2_production_queue.static.v1'
            or proof['image']['sha256'] != XP2_CORE_SHA256
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or set(proof['bindings']) != {'BuildQueue.GetAt'}
            or binding['callback_rva'] != hex(GET_AT_RVA) or binding['registrar_rva'] != '0x68b4f0'
            or binding['name_va'] != '0x180a2f828'
            or binding['lua_callback_abi'] != 'int __cdecl(LuaState*) / Windows x64'
            or set(proof['callback_literals'].values()) != _FIELDS):
        raise ValueError('XP2 queue binding identity changed')
    _bodies(proof)
    registrar = {row['va']: row for row in proof['functions']['0x68b4f0']['instructions']}
    window = binding['registration_instructions']
    for address, prefix, target in ((binding['callback_reference_va'], '488d15', _BASE+GET_AT_RVA),
            (binding['name_reference_va'], '4c8d05', int(binding['name_va'], 16))):
        row = registrar[address]
        raw = bytes.fromhex(row['bytes'])
        if (len(raw) != 7 or raw[:3].hex() != prefix
                or int(address, 16)+7+int.from_bytes(raw[3:], 'little', signed=True) != target
                or row not in window):
            raise ValueError('XP2 queue actual registration target changed')
    if (any(registrar.get(row['va']) != row for row in window)
            or not any(row['text']=='jmp 0x18000dab0' for row in window)):
        raise ValueError('XP2 queue registration helper changed')
    expected = {0x6C640: {0x6C640: 'mov eax, dword ptr [rcx + 0x368]'},
        0x6BC30: {0x6BC30: 'cmp edx, dword ptr [rcx + 0x368]',
            0x6BC3A: 'imul rax, rax, 0x38', 0x6BC3E: 'add rax, qword ptr [rcx + 0x358]',
            0x6BC46: 'xor eax, eax'},
        GET_AT_RVA: {0x68BE45: 'call 0x18068b390', 0x68BE73: 'call 0x18006c640',
                     0x68BE85: 'call 0x18006bc30'}}
    for rva, required in expected.items():
        actual = {int(row['rva'], 16): row['text'] for row in proof['functions'][hex(rva)]['instructions']}
        if any(actual.get(at) != text for at, text in required.items()):
            raise ValueError('XP2 queue nested reader ABI changed')
    gate = proof['gate']
    if (any(gate[k] is not v for k, v in dict(tutorial_active=False, test_mode=False,
            queue_tab_visible=True, queue_tab_enabled=True, immutable_headless_profile=True,
            dynamic_game_state_replayed=False, runtime_context_sources_verified=False).items())
            or proof['contracts']['capacity'] != 8 or proof['contracts']['tail_index'] != 7
            or proof['contracts']['public_schema'] != 'civ6rl.production_queue.public.v2'):
        raise ValueError('XP2 queue route contract changed')
    for ref in proof['references']:
        _source((ref['path'], ref['sha256']))
    _ui_source(proof)
    _witness(proof)
    return proof


def source_dependencies(*, execution_image=None):
    from .xp1_production_profile import source_dependencies as production
    proof = verify_source()
    result = dict(production(core_sha256=XP2_CORE_SHA256,
                             execution_image=execution_image))
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), proof['image'], proof['extractor'],
            proof['capture_manifest'], *proof['references'],
            *proof['official_ui_sources'].values(), *proof['captured_ui_witnesses']]
    for ref in refs:
        if ref is proof['image'] and execution_image is not None:
            continue
        path = resolve_path(resource_root()/ref['path']).resolve()
        if (hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']
                or str(path) in result and result[str(path)] != ref['sha256']):
            raise ValueError('XP2 queue dependency changed: ' + str(path))
        result[str(path)] = ref['sha256']
    from .runtime_source_dependencies import materialize_runtime_source_pins
    return materialize_runtime_source_pins(
        result, execution_image=execution_image,
        provenance_images=(proof['image'],),
    )


def verify_live(base, read):
    if type(base) is not int or not 0 < base < (1 << 47)-0x1000000 or not callable(read):
        raise ValueError('XP2 queue requires a module base and reader')
    proof = verify_source()
    spans = [(int(f['start_rva'], 16), bytes.fromhex(f['raw_hex']))
             for body in proof['functions'].values() for f in body['fragments']]
    spans.extend((int(row['rva'], 16), bytes.fromhex(row['raw_hex']))
                 for row in proof['embedded_tables'].values())
    strings = {**proof['callback_literals'], proof['bindings']['BuildQueue.GetAt']['name_va']: 'GetAt'}
    spans.extend((int(va, 16)-_BASE, value.encode()+b'\0') for va, value in strings.items())
    for rva, raw in spans:
        for offset in range(0, len(raw), 4096):
            chunk = raw[offset:offset+4096]
            actual = read(base+rva+offset, len(chunk))
            if type(actual) is not bytes or actual != chunk:
                raise ValueError('XP2 queue native source changed at ' + hex(rva+offset))
    return len(spans)


@dataclass(frozen=True)
class VerifiedQueueSource:
    owner: object
    core: object
    base: int
    inputs: object
    bundle: object
    source_sha256: str
    core_sha256: str
    instruction_read_spans: int


def _check_receipt(owner, core, receipt):
    from .native.native_official_load import OfficialLoadBackend
    if (type(owner) is not OfficialLoadBackend or owner.core is not core
            or owner.load_abi.core_sha256 != XP2_CORE_SHA256
            or type(receipt) is not VerifiedQueueSource or receipt.owner is not owner
            or receipt.core is not core or receipt.base != core._handle
            or receipt.inputs is not owner.inputs or receipt.bundle is not owner.captured_bundle
            or receipt.bundle.inputs is not receipt.inputs
            or receipt.source_sha256 != SOURCE[1] or receipt.core_sha256 != XP2_CORE_SHA256):
        raise ValueError('XP2 queue source belongs to another saved lifetime')


def bind_owner(owner, core, read):
    from .native.native_official_load import OfficialLoadBackend
    if type(owner) is not OfficialLoadBackend:
        raise ValueError('XP2 queue requires the actual saved Load backend')
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256 != XP2_CORE_SHA256
            or type(core._handle) is not int or core._handle <= 0
            or read != owner.runtime.read or owner.destroyed or owner.poisoned):
        raise ValueError('XP2 queue source owner mismatch')
    old = getattr(owner, '_xp2_production_queue_source_receipt', None)
    if old is not None:
        _check_receipt(owner, core, old)
        return old
    from .captured_saved_load import validate_candidate_inputs
    from .xp1_production_profile import bind_owner as bind_production
    validate_candidate_inputs(owner.inputs, owner.captured_bundle)
    bind_production(owner, core, read)
    execution_image = getattr(core, '_civ6_host_execution_image', None)
    source_dependencies(execution_image=execution_image)
    receipt = VerifiedQueueSource(owner, core, core._handle, owner.inputs, owner.captured_bundle,
                                 SOURCE[1], XP2_CORE_SHA256, verify_live(core._handle, read))
    owner._xp2_production_queue_source_receipt = receipt
    return receipt


def gate_admitted(continuation):
    """The witnessed immutable UI route; current native legality stays queried."""
    from .xp1_continuation import SavedContinuation
    if type(continuation) is not SavedContinuation:
        raise ValueError('XP2 queue gate requires the actual saved continuation')
    owner = continuation.owner
    continuation.check(active=owner.busy)
    owner.check_thread()
    receipt = getattr(owner, '_xp2_production_queue_source_receipt', None)
    _check_receipt(owner, owner.core, receipt)
    if continuation.lease.inputs is not receipt.inputs:
        raise ValueError('XP2 queue gate lost its captured input lease')
    return True

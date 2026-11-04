"""Exact XP2 source selection for the shared official world-input route.

Native getters and the four inherited Lua functions retain their algorithms.
This verifies source and ownership; it does not qualify arbitrary movement,
combat, war confirmation or an entire WorldInput UI context.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/host-extensions/xp2-world-input-static/source-profile-v1.json',
          '4f52cd6551bcb61b7af2d4e23571eb300c7c8b55ad34b6b94e0387c94a9e72f3')
CALLBACKS = {'Unit.GetComponentID': 0x6BCB00, 'Unit.GetPlotId': 0x6BD340,
    'Unit.GetCombat': 0x6BCAB0, 'Unit.GetRangedCombat': 0x6BD4F0,
    'Unit.GetBombardCombat': 0x6BCA10, 'Map.GetGridSize': 0x6A2430,
    'Map.GetPlotCount': 0x6A2810, 'Map.GetPlotByIndex': 0x6A2790,
    'Plot.GetIndex': 0x1D270, 'Plot.GetX': 0x1D9B0, 'Plot.GetY': 0x1DA00,
    'Visibility.IsVisible': 0x6B7D60,
    'CombatManager.IsAttackChangeWarState': 0x5AB9C0,
    'UnitManager.GetQueuedDestination': 0x6C1FC0}
REGISTRARS = {'Unit': 0x6BB990, 'Map': 0x6A1550, 'Plot': 0x1B2E0,
    'Visibility': 0x6B7860, 'CombatManager': 0x5AACC0, 'UnitManager': 0x6BFAC0}
_IMAGE_BASE = 0x180000000


def _fragments(proof):
    """Yield every complete fragment, including branches beyond an early RET."""
    for key, body in proof['functions'].items():
        if not key.startswith('registration:'):
            for fragment in body['fragments']:
                yield int(fragment['start_rva'], 16), bytes.fromhex(fragment['raw_hex'])


def _body_contracts(proof):
    for key, body in proof['functions'].items():
        if key.startswith('registration:'):
            continue
        fragments = body['fragments']
        if (body['all_conditional_targets_captured'] is not True
                or not fragments or body['fragment_count'] != len(fragments)):
            raise ValueError('Incomplete XP2 world-input body: ' + key)
        joined = b''
        covered = set()
        flat = []
        for fragment in fragments:
            start = int(fragment['start_rva'], 16)
            raw = bytes.fromhex(fragment['raw_hex'])
            if (not raw or fragment['length'] != len(raw)
                    or int(fragment['end_rva_exclusive'], 16) != start + len(raw)
                    or hashlib.sha256(raw).hexdigest() != fragment['sha256']):
                raise ValueError('XP2 world-input fragment changed: ' + key)
            cursor = start
            for row in fragment['instructions']:
                code = bytes.fromhex(row['bytes'])
                if (not code or int(row['rva'], 16) != cursor
                        or int(row['va'], 16) != _IMAGE_BASE + cursor
                        or raw[cursor-start:cursor-start+len(code)] != code):
                    raise ValueError('XP2 world-input instruction coverage changed: ' + key)
                covered.add(cursor)
                cursor += len(code)
                flat.append(row)
            if cursor != start + len(raw):
                raise ValueError('XP2 world-input instruction tail missing: ' + key)
            joined += raw
        if (joined != bytes.fromhex(body['raw_hex']) or len(joined) != body['total_length']
                or hashlib.sha256(joined).hexdigest() != body['sha256']
                or tuple(flat) != tuple(body['instructions'])):
            raise ValueError('XP2 world-input full body changed: ' + key)
        for edge in body['conditional_branch_targets_verified']:
            if (int(edge['source_rva'], 16) not in covered
                    or int(edge['target_rva'], 16) not in covered):
                raise ValueError('XP2 world-input conditional branch omitted: ' + key)


def _require_rows(proof, body, rows):
    actual = {int(row['rva'], 16): row['text']
              for row in proof['functions'][hex(body)]['instructions']}
    if any(actual.get(address) != text for address, text in rows.items()):
        raise ValueError('XP2 world-input nested ABI changed: ' + hex(body))


def _registration_contracts(proof):
    if set(proof['bindings']) != set(CALLBACKS):
        raise ValueError('XP2 world-input callback set changed')
    for name, callback in CALLBACKS.items():
        binding = proof['bindings'][name]
        registrar = REGISTRARS[name.split('.')[0]]
        if (binding['callback_rva'] != hex(callback)
                or binding['registrar_rva'] != hex(registrar)
                or binding['registration_helper_rva'] != '0xdab0'
                or binding['lua_callback_abi'] != 'int __cdecl(LuaState*) / Windows x64'):
            raise ValueError('XP2 world-input binding changed: ' + name)
        rows = proof['functions'][hex(registrar)]['instructions']
        by_va = {row['va']: row for row in rows}
        callback_row = by_va[binding['callback_reference_va']]
        name_row = by_va[binding['name_reference_va']]
        # The registrar's actual LEA operands, not an inferred symbol match.
        for row, prefix, target in ((callback_row, '488d15', _IMAGE_BASE + callback),
                (name_row, '4c8d05', int(binding['name_va'], 16))):
            code = bytes.fromhex(row['bytes'])
            if (len(code) != 7 or code[:3].hex() != prefix
                    or int(row['va'], 16) + 7 + int.from_bytes(code[3:], 'little', signed=True) != target
                    or tuple(row['rip_targets']) != (hex(target),)):
                raise ValueError('XP2 world-input registrar target changed: ' + name)
        window = proof['functions']['registration:' + name]['instructions']
        if (not window or any(by_va.get(row['va']) != row for row in window)
                or not any(row['text'] in ('call 0x18000dab0', 'jmp 0x18000dab0') for row in window)
                or callback_row not in window or name_row not in window):
            raise ValueError('XP2 world-input registration window changed: ' + name)


def _official_route(proof):
    texts = []
    for row in proof['official_ui']:
        raw = resolve_path(Path(row['path'])).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Official XP2 world-input Lua changed')
        texts.append(raw.decode('utf-8-sig'))
    if len(texts) != 5:
        raise ValueError('XP2 world-input include chain is incomplete')
    _, _, modinfo, xp2, inherited = texts
    nodes = [node for node in ET.fromstring(modinfo).iter('ReplaceUIScript')
             if node.attrib.get('id') == 'Expansion2_WorldInput']
    if (len(nodes) != 1 or nodes[0].attrib.get('criteria') != 'Expansion2'
            or nodes[0].findtext('Properties/LuaContext') != 'WorldInput'
            or nodes[0].findtext('Properties/LuaReplace') != 'UI/Replacements/WorldInput_Expansion2.lua'
            or 'include("WorldInput_Expansion1")' not in xp2
            or 'include("WorldInput")' not in inherited
            or 'Civ6Common' in modinfo):
        raise ValueError('XP2 world-input official replacement route changed')
    from .native.native_movement_ui_source import source_manifest
    functions = source_manifest()['functions']
    if functions != proof['ui_route']['shared_functions']:
        raise ValueError('Shared official movement function bytes changed')
    for name in functions:
        if re.search(r'\b' + re.escape(name) + r'\s*(?:\(|=)', xp2 + inherited):
            raise ValueError('XP2 overrides shared movement function: ' + name)


def verify_source(core_sha256=XP2_CORE_SHA256):
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('XP2 world-input source requires its exact engine')
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6_host.xp2_world_input.static.v1'
            or proof['image']['sha256'] != XP2_CORE_SHA256
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or proof['validation']['exact_registration_pairs'] != 14
            or proof['validation']['all_instruction_bytes_match_image'] is not True
            or proof['validation']['conditional_branches_included'] is not True
            or proof['contracts']['war_confirmation_admitted'] is not False
            or proof['contracts']['other_request_operations_admitted'] is not False):
        raise ValueError('XP2 world-input source identity changed')
    _body_contracts(proof)
    _registration_contracts(proof)
    _require_rows(proof, 0x6A2790, {0x6A27E3: 'call 0x1800160c0'})
    _require_rows(proof, 0x160C0, {0x160E8: 'call 0x18001ab10', 0x1628C: 'call 0x18001b2e0'})
    _require_rows(proof, 0x6C1FC0, {0x6C1FD7: 'call 0x1805a1b00',
        0x6C1FE1: 'mov ecx, dword ptr [rax + 0xd0]',
        0x6C1FE7: 'movzx edx, word ptr [rax + 0xec]', 0x6C2001: 'call 0x1800d0ce0',
        0x6C2006: 'cmp eax, -1', 0x6C203B: 'mov dword ptr [rax], 0'})
    _require_rows(proof, 0xD0CE0, {0xD0D0D: 'call qword ptr [rax + 0x40]',
        0xD0D13: 'call 0x180044f00', 0xD0D22: 'call 0x1802c4360',
        0xD0D62: 'call qword ptr [r8 + 0x78]', 0xD0D6F: 'call qword ptr [rax + 8]',
        0xD0DA5: 'call qword ptr [rax + 0x68]', 0xD0DC8: 'call qword ptr [rdx + 0x38]'})
    for row in proof['functions']['0xd0ce0']['instructions']:
        if row['rva'] in ('0xd0d00', '0xd0dbe') and tuple(row['rip_targets']) != ('0x180b8aa80',):
            raise ValueError('XP2 queued destination has a different HOST owner')
    for reference in proof['references']:
        _source((reference['path'], reference['sha256']))
    _official_route(proof)
    return proof


def source_dependencies(core_sha256=XP2_CORE_SHA256):
    proof = verify_source(core_sha256)
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), proof['extractor'], proof['image'],
            *proof['references'], *proof['official_ui']]
    result = {}
    for row in refs:
        path = resolve_path(resource_root() / row['path']).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('XP2 world-input dependency changed: ' + str(path))
        result[str(path)] = row['sha256']
    from .xp1_status_profiles import source_dependencies as status
    from .unit_operation_ui_profile import source_dependencies as operation
    for provider in (status, operation):
        for path, digest in provider(core_sha256=XP2_CORE_SHA256).items():
            if path in result and result[path] != digest:
                raise ValueError('Conflicting XP2 world-input source pins')
            result[path] = digest
    return result


def verify_live(base, read, core_sha256=XP2_CORE_SHA256):
    if (type(base) is not int or not 0 < base < (1 << 47) - 0x1000000
            or not callable(read)):
        raise ValueError('Expected XP2 module base and memory reader')
    proof = verify_source(core_sha256)
    spans = list(_fragments(proof))
    for name, row in proof['bindings'].items():
        spans.append((int(row['name_va'], 16) - _IMAGE_BASE, name.split('.')[1].encode() + b'\0'))
    row = proof['data']['plot_type_name']
    spans.append((int(row['rva'], 16), row['text'].encode() + b'\0'))
    for rva, raw in spans:
        for offset in range(0, len(raw), 4096):
            expected = raw[offset:offset+4096]
            actual = read(base+rva+offset, len(expected))
            if type(actual) is not bytes or actual != expected:
                raise ValueError('XP2 world-input live source changed at ' + hex(rva+offset))
    return len(spans)


@dataclass(frozen=True)
class VerifiedWorldInputSource:
    owner: object
    core: object
    base: int
    source_sha256: str
    core_sha256: str
    instruction_read_spans: int


def bind_owner(owner, core, read):
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256 != XP2_CORE_SHA256
            or type(core._handle) is not int or core._handle <= 0):
        raise ValueError('XP2 world-input source owner mismatch')
    from .xp1_status_profiles import bind_owner as bind_status
    bind_status(owner, core, read)
    previous = getattr(owner, '_xp2_world_input_source_receipt', None)
    if previous is not None:
        if (type(previous) is not VerifiedWorldInputSource or previous.owner is not owner
                or previous.core is not core or previous.base != core._handle
                or previous.source_sha256 != SOURCE[1] or previous.core_sha256 != XP2_CORE_SHA256):
            raise ValueError('XP2 world-input receipt belongs to another lifetime')
        return previous
    from .unit_operation_ui_profile import verify_live as verify_operation
    verify_operation(core._handle, read, core_sha256=XP2_CORE_SHA256)
    receipt = VerifiedWorldInputSource(owner, core, core._handle, SOURCE[1], XP2_CORE_SHA256,
                                      verify_live(core._handle, read))
    owner._xp2_world_input_source_receipt = receipt
    return receipt

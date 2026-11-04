"""Complete, source-pinned XP2 facade ABI for shared foundation queries."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .configuration_profiles import _source
from .saved_load_profiles import XP2_CORE_SHA256
from .a0_family_source import _path, verify_pinned_files
from .foundation_facade_profiles import _BASE_OPERATIONS

SOURCE = ('work/host-extensions/xp2-foundation-query-facades-static/query-facade-source-v3.json',
          '7313418cd5d5f4f086ed41424c7f502c736e953a6bc345ab1b2da5368462a71e')
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'


def source():
    p = _source(SOURCE)
    if (p.get('schema') != 'civ6-host.xp2-foundation-query-facades.complete.v3'
            or p.get('core_sha256') != XP2_CORE_SHA256
            or p.get('exe_sha256') != EXE_SHA256
            or set(p.get('operations', {})) != set(_BASE_OPERATIONS)
            or p.get('validation', {}).get('native_execution') is not False
            or p['validation'].get('total_operation_count') != 35
            or p['validation'].get('table_count') != len(p.get('tables', {}))
            or p['validation'].get('operation_targets_present') is not True
            or p['validation'].get('all_operation_targets_have_complete_source_bodies') is not True):
        raise ValueError('XP2 foundation query facade source contract differs')
    for row in p['inputs']:
        if 'path' in row:
            if row.get('generator') is True:
                path = _path(row['path'])
                if hashlib.sha256(Path(path).read_bytes()).hexdigest() != row['sha256']:
                    raise ValueError('XP2 foundation facade generator changed')
            else:
                _source((row['path'], row['sha256']))
        elif row.get('source_label') == 'HOST/work/xp2-facade-inventory/district-static.json' and row.get('embedded_bodies') is True:
            continue
        elif row.get('source_label') == 'retained-fixed-EXE-callers' and row.get('native_execution') is False:
            continue
        else:
            raise ValueError('Unknown XP2 foundation facade source input')
    for name, expected in _BASE_OPERATIONS.items():
        op = p['operations'][name]
        if op.get('abi') != expected['abi']:
            raise ValueError('XP2 foundation facade ABI differs: ' + name)
        if name == 'free_snapshot_vector':
            if op.get('kind') != 'import-wrapper' or op.get('import_name') != '_aligned_free':
                raise ValueError('XP2 foundation vector-release contract differs')
            continue
        table = op.get('table')
        slot = op.get('slot')
        target = op.get('target_rva')
        if table != expected['table'] or type(slot) is not str or int(slot, 16) < 0 or int(slot, 16) % 8:
            raise ValueError('XP2 foundation facade selector differs: ' + name)
        row = p['tables'].get(table)
        if row is None or row.get('slots', {}).get(slot) != target:
            raise ValueError('XP2 foundation facade table slot differs: ' + name)
    if (p['operations']['plot_owner']['slot'] != '0x20'
            or p['operations']['plot_owner']['target_rva'] != '0x5a13c0'
            or p['operations']['plot_value']['slot'] != '0x30'
            or p['operations']['plot_value']['target_rva'] != '0x5a1070'):
        raise ValueError('XP2 Plot owner/value selectors do not match the retained EXE callers')
    semantic = p.get('semantic_evidence', {})
    owner = semantic.get('plot_owner', {})
    value = semantic.get('plot_value', {})
    owner_evidence = _source((owner['exe_source']['path'], owner['exe_source']['sha256']))
    value_evidence = _source((value['exe_source']['path'], value['exe_source']['sha256']))
    if (semantic.get('exe_image_sha256') != EXE_SHA256
            or owner_evidence.get('image', {}).get('exe_sha256') != EXE_SHA256
            or value_evidence.get('image', {}).get('exe_sha256') != EXE_SHA256
            or owner.get('caller') != {'va':'0x14014c365','bytes':'ff5020',
                'semantic':'plot owner query via vtable+0x20'}
            or owner.get('consumer') != {'va':'0x14014c368','bytes':'8944242c',
                'width':'DWORD EAX','signed':True}
            or tuple(value.get('callers', ())) != ({'va':'0x14013f092','bytes':'ff5030'},
                                                   {'va':'0x14013f1fa','bytes':'ff5030'})
            or value.get('consumer') != {'bytes':'8945cc','width':'DWORD EAX'}):
        raise ValueError('XP2 Plot semantic caller evidence differs')

    def instruction_rows(evidence, body_name, collection):
        return {row['va']:row for fragment in evidence[collection][body_name]['fragments']
                for row in fragment['instructions']}
    owner_rows = instruction_rows(owner_evidence, 'callback', 'bodies')
    value_rows = instruction_rows(value_evidence, 'callback', 'captures')
    if (owner_rows.get('0x14014c365', {}).get('bytes') != 'ff5020'
            or owner_rows.get('0x14014c368', {}).get('bytes') != '8944242c'
            or any(value_rows.get(va, {}).get('bytes') != 'ff5030'
                   for va in ('0x14013f092','0x14013f1fa'))
            or any(value_rows.get(va, {}).get('bytes') != '8945cc'
                   for va in ('0x14013f095','0x14013f1fd'))):
        raise ValueError('XP2 Plot semantic source callsites differ')

    xp1_ref = next(row for row in p['inputs'] if row.get('role') == 'cross-engine semantic body comparison')
    xp1 = _source((xp1_ref['path'], xp1_ref['sha256']))
    def function_bytes(body):
        if 'fragments' in body:
            return b''.join(bytes.fromhex(row['bytes']) for frag in body['fragments']
                            for row in frag['instructions'])
        return b''.join(bytes.fromhex(row['bytes']) for row in body['instructions'])
    if (function_bytes(p['functions']['0x5a13c0']) !=
            function_bytes(xp1['functions'][hex(xp1['operations']['plot_owner']['rva'])]['body'])
            or function_bytes(p['functions']['0x5a1070']) !=
            function_bytes(xp1['functions'][hex(xp1['operations']['plot_value']['rva'])]['body'])):
        raise ValueError('XP2 Plot owner/value wrappers differ from the XP1 semantic bodies')
    for name, row in p['tables'].items():
        if int(row['vtable_rva'], 16) <= 0:
            raise ValueError('Invalid XP2 foundation facade table')
        for slot, target in row['slots'].items():
            if int(slot, 16) < 0 or int(slot, 16) % 8 or int(target, 16) <= 0:
                raise ValueError('Invalid XP2 foundation facade table slot: ' + name)
    required = {op['target_rva'] for op in p['operations'].values()}
    required.update(('0x5a1dc0', '0x59ed00', '0x596510', '0x596540'))
    if set(p['functions']) != required | {'0x5a12a0'}:
        raise ValueError('XP2 foundation facade source body closure is incomplete')
    for rva in p['functions']:
        body = p['functions'][rva]
        fragments = body.get('fragments')
        if (not fragments or not body.get('boundary_method')
                or any(body.get(key) is not True for key in
                       ('all_reachable_conditional_successors_captured', 'all_conditional_targets_captured')
                       if key in body)):
            raise ValueError('XP2 facade source body is incomplete: ' + rva)
        actual = bytearray()
        for fragment in fragments:
            raw = bytes.fromhex(fragment['raw_hex'])
            if len(raw) != fragment['length'] or hashlib.sha256(raw).hexdigest() != fragment['sha256']:
                raise ValueError('XP2 facade source fragment differs: ' + rva)
            instructions = fragment.get('instructions', ())
            if b''.join(bytes.fromhex(item['bytes']) for item in instructions) != raw:
                raise ValueError('XP2 facade source instruction coverage differs: ' + rva)
            actual.extend(raw)
        if (len(actual) != body.get('bytes')
                or hashlib.sha256(actual).hexdigest() != body.get('sha256')):
            raise ValueError('XP2 facade source body digest differs: ' + rva)
    return p


def source_dependencies():
    p = source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]),
            *[row for row in p['inputs'] if 'path' in row]]
    refs.extend([p['semantic_evidence']['plot_owner']['exe_source'],
                 p['semantic_evidence']['plot_value']['exe_source']])
    pins = {}
    for row in refs:
        path = str(_path(row['path']))
        if path in pins and pins[path] != row['sha256']:
            raise ValueError('Conflicting XP2 foundation facade source dependency')
        pins[path] = row['sha256']
    verify_pinned_files(pins)
    return pins


def verify_live(base, read):
    p = source()
    if type(base) is not int or base <= 0:
        raise ValueError('Invalid XP2 foundation facade base')
    checked = set()
    active_rvas = {op['target_rva'] for op in p['operations'].values()}
    active_rvas.update(('0x5a1dc0', '0x59ed00', '0x596510', '0x596540'))
    for rva in active_rvas:
        body = p['functions'][rva]
        for fragment in body['fragments']:
            start = int(fragment['start_rva'], 16)
            raw = bytes.fromhex(fragment['raw_hex'])
            if read(base + start, len(raw)) != raw:
                raise ValueError('XP2 foundation facade source bytes differ at ' + rva)
            checked.update(int(row['rva'], 16) for row in fragment['instructions'])
    checked_slots = 0
    for table in p['tables'].values():
        table_rva = int(table['vtable_rva'], 16)
        for slot, target in table['slots'].items():
            expected = (base + int(target, 16)).to_bytes(8, 'little')
            if read(base + table_rva + int(slot, 16), 8) != expected:
                raise ValueError('XP2 foundation facade live vtable slot differs')
            checked_slots += 1
    return {'core_sha256': XP2_CORE_SHA256, 'source_sha256': SOURCE[1],
            'operations_checked': 35, 'functions_checked': len(active_rvas),
            'instruction_sites_checked': len(checked), 'table_slots_checked': checked_slots,
            'native_calls_invoked': False}

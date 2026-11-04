"""Exact XP2 map+0x68 method needed by shared positive index lookups."""
from .configuration_profiles import _source, XP2_CORE_SHA256
from .a0_family_source import _path, verify_pinned_files

SOURCE = ('work/host-extensions/xp2-foundation-optional-position/source-profile-v1.json',
          'e7b2451691441490a1319428b3da5835e2481c0de166106e7c2e7b1ca458c927')
TABLE_RVA = 0xA11698
SLOT = 0x68
TARGET_RVA = 0x59B440


def source():
    p = _source(SOURCE)
    row = p['slot']
    body = p['function']
    if (p['schema'] != 'civ6-host.xp2-foundation-optional-position.static.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['image']['sha256'] != XP2_CORE_SHA256
            or p['parent_profile']['sha256'] != 'e6dad3289463a09baecfb8a34a52f3fcaedc03f50f94d06ae11840363de9419b'
            or row['table_rva'] != hex(TABLE_RVA) or row['offset'] != hex(SLOT)
            or row['target_rva'] != hex(TARGET_RVA) or row['bytes_hex'] != '40b4598001000000'
            or body['rva'] != hex(TARGET_RVA) or body['bytes'] != 70
            or body['sha256'] != 'a902d6f4fe75debb0860785ab922bbdbc926d04acdbe659f41c31eb417c80835'
            or p['contract']['abi'] != 'ptr(ptr,out8*,int32)'
            or p['contract']['parameters'] != {'rcx':'map facade','rdx':'writable out8 pointer','r8d':'signed map index'}
            or p['contract']['caller_exe_reference']['sha256'] != '30a78ad61e21b0003de294a0fbd787402835d29a9a89e7bf441418087a39fab1'
            or p['verification'] != {'slot_matches_pe':True,'all_function_bytes_match_pe':True,
                'conditional_targets_closed':True,'function_bytes':70,'instruction_count':23}):
        raise ValueError('XP2 optional map-index source contract changed')
    return p


def source_dependencies():
    p = source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]),
            p['parent_profile'], p['contract']['caller_exe_reference'], *p['extractors']]
    pins = {}
    for ref in refs:
        path = str(_path(ref['path']))
        if path in pins and pins[path] != ref['sha256']:
            raise ValueError('Conflicting XP2 optional-position source identity')
        pins[path] = ref['sha256']
    verify_pinned_files(pins)
    return pins


def verify_live(base, read):
    p = source()
    if type(base) is not int or base <= 0:
        raise ValueError('Invalid XP2 optional-position base')
    slot = read(base + TABLE_RVA + SLOT, 8)
    if slot != (base + TARGET_RVA).to_bytes(8, 'little'):
        raise ValueError('XP2 map+0x68 method differs from the captured source')
    body = p['function']
    checked = 0
    for fragment in body['fragments']:
        raw = bytes.fromhex(fragment['raw_hex'])
        if len(raw) != fragment['length'] or read(base + int(fragment['start_rva'], 16), len(raw)) != raw:
            raise ValueError('XP2 map+0x68 wrapper bytes differ from the captured source')
        checked += len(raw)
    if checked != 70:
        raise ValueError('XP2 optional-position wrapper capture is incomplete')
    return {'core_sha256': XP2_CORE_SHA256, 'source_sha256': SOURCE[1],
            'target_rva': TARGET_RVA, 'function_bytes_checked': checked,
            'table_slot_checked': True, 'native_execution': False}

"""XP2 typed-map producers and the unchanged closed EXE callback registry."""
import hashlib
import re
from .configuration_profiles import XP2_CORE_SHA256, _source
from .a0_family_source import _path, verify_pinned_files, verify_extracted_sources

SOURCE=('work/host-extensions/xp2-absent-events-static/source-profile-v1.json',
        'd59fc66f0cd772324dc1f141e18c3c82b1fdb3022aa18ad038d83449f9faba95')
ROOTS=dict(integer_builder=0x5fb890,integer_caller=0x1a4b30,two_builder=0x5fb000,
           two_caller=0x3fb56,float_builder=0x5fbc80)


def rows(body):
    return tuple(r for f in body['fragments'] for r in f['instructions'])


def source():
    from .native import native_absent_unit_scalar_family as unit
    from .native import native_absent_b4_scalar_family as b4
    from .native import native_absent_d70ba51f as two
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from .xp2_preload_source import SOURCE as reader_source
    p=_source(SOURCE);c=p['contract'];v=p['validation']
    if (p['schema']!='civ6-host.xp2-absent-descriptor-families.static.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['images']['xp2']['sha256']!=XP2_CORE_SHA256
            or p['images']['exe']['sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or dict(p['roots'])!=ROOTS or (v['function_count'],v['total_bytes'])!=(38,12095)
            or v['all_bytes_match_installed_image'] is not True
            or v['explicit_conditional_targets_closed'] is not True or tuple(v['code_relocations'])
            or c['kind_domain']!='uint32-excluding-all-317-registered-kinds'
            or {frozenset(k) for k in c['field_sets']}!={unit.FIELD_KEYS,b4.FIELD_KEYS,two.FIELD_KEYS}
            or (c['selector_tag'],c['two_field_selector_value'],tuple(c['scalar_tags']),c['descriptor_tag'],c['descriptor_bytes'],c['descriptor_flags'])!=(3,0,(2,4),1024,8,0x21000001)
            or (c['internal_dispatch'],c['host_global'],c['host_slot'],c['parameter_destructor'])!=(0x7c670,0xb8aa80,0xa0,0x99e5d0)
            or any(c[k] is not True for k in ('internal_before_host','preserves_existing_fifo','no_synthetic_fields','no_gameplay_success'))
            or any(c[k] is not False for k in ('normalizer_transform_present','dynamic_registration_present','callback_registered','b4_pointee_read'))
            or (c['entity_listener_count'],c['unit_copy_bytes'],c['unit_normalized_type'])!=(0,8,1)
            or p['references']['reader']['sha256']!=reader_source[1]
            or len(EXE_EVENT_CALLBACKS)!=317 or any(k in EXE_EVENT_CALLBACKS for k in (0xc52231ab,0x7b4264e9))):
        raise ValueError('XP2 absent descriptor source contract changed')
    proofs=[unit.verify_source_evidence(),b4.verify_source_evidence(),two.verify_source_evidence()]
    for key,digest in [('unit',unit.PROOF_SHA256),('b4',b4.PROOF_SHA256),('unit_two',two.PINNED_EVIDENCE_SHA256)]:
        ref=p['references'][key]
        if ref['sha256']!=digest:raise ValueError('XP2 shared EXE proof changed')
        _source((ref['path'],ref['sha256']))
    for name in ('normalizer','resolver'):
        if len({proof['captures'][name]['code_sha256'] for proof in proofs})!=1:
            raise ValueError('Shared absent EXE normalizer/resolver differs')
    starts=set()
    for body in p['functions'].values():
        parts=[]
        for f in body['fragments']:
            raw=bytes.fromhex(f['raw_hex']);parts.append(raw);cursor=int(f['start_rva'],16)
            if (len(raw)!=f['length'] or hashlib.sha256(raw).hexdigest()!=f['sha256']
                    or ''.join(r['bytes'] for r in f['instructions'])!=raw.hex()):
                raise ValueError('XP2 absent source fragment changed')
            for row in f['instructions']:
                if int(row['rva'],16)!=cursor:raise ValueError('XP2 absent instruction boundary changed')
                starts.add(cursor);cursor+=len(bytes.fromhex(row['bytes']))
        raw=b''.join(parts)
        if len(raw)!=body['bytes'] or hashlib.sha256(raw).hexdigest()!=body['sha256']:
            raise ValueError('XP2 absent complete source body changed')
    for body in p['functions'].values():
        for row in rows(body):
            m=re.fullmatch(r'j(?!mp\b)\w+ (0x[0-9a-f]+)',row['text'])
            if m and int(m[1],16)-0x180000000 not in starts:
                raise ValueError('XP2 absent source omitted conditional successor')
    for name in ('integer_builder','two_builder','float_builder'):
        body_rows=rows(p['functions'][hex(ROOTS[name])]);texts={r['text'] for r in body_rows}
        required={'mov edx, 0xa1e5a149','mov edx, 0xf0548bb7','mov edx, 0xb4f9542d',
                  'cmp ax, 1','cmp ax, 0x2c','mov r8d, 0x400',
                  'mov dword ptr [rsp + 0x20], 8','mov dword ptr [rsp + 0x28], 1',
                  'mov dword ptr [rsp + 0x30], 0x1000000','call qword ptr [rax + 0xb0]',
                  'call 0x18099e4b0','call 0x1809a0000'}
        if not required<=texts:raise ValueError('XP2 typed descriptor builder changed')
        order={r['text']:int(r['rva'],16) for r in body_rows}
        if not order['call 0x18007c670']<order['call qword ptr [rax + 0xa0]']<order['call 0x18099e5d0']:
            raise ValueError('XP2 internal dispatch or borrowed-map lifetime changed')
        if name=='two_builder':
            if 'mov edx, 0xd6fcf3e4' in texts:raise ValueError('XP2 two-field builder gained scalar')
        elif not {'mov edx, 0xd6fcf3e4','call 0x180'+('99fee0' if name=='integer_builder' else '9a0120')}<=texts:
            raise ValueError('XP2 scalar type source changed')
    caller={r['text'] for r in rows(p['functions'][hex(ROOTS['integer_caller'])])}
    if not {'mov dword ptr [rsp + 0x20], 0xc52231ab','mov dword ptr [rsp + 0x24], 0',
            'mov eax, 0x2c','movzx r8d, byte ptr [rbx + 0x1b0]','call 0x1805fb890'}<=caller:
        raise ValueError('XP2 absent B4 source caller changed')
    caller={r['text'] for r in rows(p['functions'][hex(ROOTS['two_caller'])])}
    if not {'mov qword ptr [rbp - 0x59], 0x7b4264e9','call 0x1805fb000'}<=caller:
        raise ValueError('XP2 absent Unit source caller changed')
    return p


def source_dependencies(*,execution_image=None):
    from .xp2_preload_source import source_pins as reader_pins
    p=source();refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'].values(),*p['extractors'],*p['source_modules']]
    pins=reader_pins()
    for r in refs:
        path=str(_path(r['path']))
        if path in pins and pins[path]!=r['sha256']:raise ValueError('Conflicting absent source pin')
        pins[path]=r['sha256']
    # Static image identities remain in the receipt; only the selected Core is
    # a runtime file dependency for the host.
    provenance_images=list(p['images'].values())
    if execution_image is None:
        pins.update({str(r['path']):r['sha256'] for r in provenance_images})
    else:
        from .runtime_source_dependencies import materialize_runtime_source_pins
        pins=materialize_runtime_source_pins(pins,execution_image=execution_image,
                                             provenance_images=provenance_images)
    verify_pinned_files(pins)
    verify_extracted_sources(p['source_modules'])
    return pins


def verify_live(base,read):
    if type(base) is not int or base<=0 or not callable(read):raise ValueError('XP2 absent source requires actual module/read')
    p=source();count=0
    for body in p['functions'].values():
        for f in body['fragments']:
            raw=bytes.fromhex(f['raw_hex'])
            if read(base+int(f['start_rva'],16),len(raw))!=raw:
                raise ValueError('XP2 absent descriptor live instructions changed')
            count+=1
    for slot,target in p['parameter_vtable']['slots'].items():
        if read(base+p['parameter_vtable']['rva']+int(slot),8)!=(base+target).to_bytes(8,'little'):
            raise ValueError('XP2 absent ParameterMap vtable changed')
    return dict(source_sha256=SOURCE[1],core_sha256=XP2_CORE_SHA256,verified_fragments=count)

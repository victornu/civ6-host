"""Reuse the two proven descriptor normalizers when EXE has no callback.

The native internal dispatcher/B0 publication has already run. An absent EXE
callback returns zero; this neither acknowledges gameplay nor consumes its FIFO.
"""
from functools import lru_cache
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256,_source
from .native import native_absent_unit_scalar_family as unit
from .native import native_absent_b4_scalar_family as b4
from .native import native_absent_d70ba51f as unit_two

SOURCE=('work/host-extensions/xp1-absent-descriptor-static/source-v1.json',
        '7cc3cbe76561c07e982f12d66da7f48fa0cc8fa2a53298971ecc59b8f67ffdb6')
TWO_SOURCE=('work/host-extensions/xp1-absent-descriptor-static/two-field-supplement-v1.json',
            'de4eb3db1b714760c5eda9d248abbeb1197fe3b0a9da6fb9bf02b1a8b7138b13')


def _rows(p):
    return tuple(row for fragment in p['fragments'] for row in fragment['instructions'])


@lru_cache(maxsize=2)
def verify_source(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_absent_event_source import source
        return source()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified absent descriptor engine')
    from .event_argument_source import SOURCE as reader_source
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp1-absent-descriptor-families.source.v1'
            or p['native_execution'] is not False
            or p['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or p['images']['exe']['sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or p['references']['reader']['sha256']!=reader_source[1]
            or p['references']['unit']['sha256']!=unit.PROOF_SHA256
            or p['references']['b4']['sha256']!=b4.PROOF_SHA256
            or p['validation']['all_selected_instruction_bytes_match_pinned_image'] is not True
            or p['family_contract']['field_sets']!=(tuple(sorted(unit.FIELD_KEYS)),tuple(sorted(b4.FIELD_KEYS)))
            or len(EXE_EVENT_CALLBACKS)!=317 or 0xc52231ab in EXE_EVENT_CALLBACKS):
        raise ValueError('XP1 absent descriptor family source identity changed')
    sources={name:_source((ref['path'],ref['sha256'])) for name,ref in p['references'].items()}
    up,bp=unit.verify_source_evidence(),b4.verify_source_evidence()
    if up['captures']['normalizer']['code_sha256']!=bp['captures']['normalizer']['code_sha256']:
        raise ValueError('Absent descriptor normalizers differ')
    rows=_rows(sources['builder']);texts={r['text'] for r in rows}
    required={'mov edx, 0xa1e5a149','mov edx, 0xd6fcf3e4',
              'mov edx, 0xf0548bb7','mov edx, 0xb4f9542d','cmp ax, 1','cmp ax, 0x2c',
              'mov r8d, 0x400','mov dword ptr [rsp + 0x20], 8',
              'mov dword ptr [rsp + 0x28], 1','mov dword ptr [rsp + 0x30], 0x1000000',
              'call qword ptr [rax + 0xb0]','call 0x180845e90','call 0x180845fb0'}
    if not required<=texts:raise ValueError('XP1 descriptor builder shape changed')
    order={r['text']:int(r['va'],16) for r in rows}
    if not order['call 0x180070b10']<order['call qword ptr [rax + 0xa0]']<order['call 0x180844580']:
        raise ValueError('XP1 internal dispatch or borrowed-map lifetime changed')
    caller={r['text'] for r in _rows(sources['caller'])}
    if not {'mov dword ptr [rsp + 0x20], 0xc52231ab','mov dword ptr [rsp + 0x24], 0',
            'mov eax, 0x2c','movzx r8d, byte ptr [rbx + 0x1b0]',
            'call 0x180518940'}<=caller:
        raise ValueError('XP1 absent B4 caller changed')
    verify_two_field_source()
    return p


@lru_cache(maxsize=1)
def verify_two_field_source():
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    p=_source(TWO_SOURCE);contract=p['contract']
    if (p['schema']!='civ6-host.xp1-absent-unit-two-fields.supplement.v1'
            or p['native_execution'] is not False or p['image']['sha256']!=XP1_CORE_SHA256
            or p['references']['family_parent']['sha256']!=SOURCE[1]
            or p['references']['unit_two']['sha256']!=unit_two.PINNED_EVIDENCE_SHA256
            or contract['kind_domain']!='uint32-excluding-all-317-registered-kinds'
            or contract['input_keys']!=tuple(sorted(unit_two.FIELD_KEYS)) or contract['selector']!=0
            or contract['no_synthetic_scalar'] is not True or contract['no_synthetic_kind'] is not True
            or p['validation']['all_selected_instruction_bytes_match_pinned_image'] is not True
            or 0x7b4264e9 in EXE_EVENT_CALLBACKS):
        raise ValueError('XP1 absent two-field unit source changed')
    refs={k:_source((r['path'],r['sha256'])) for k,r in p['references'].items()}
    old=unit_two.verify_source_evidence();generic=unit.verify_source_evidence()
    for name in ('normalizer','resolver'):
        if old['captures'][name]['code_sha256']!=generic['captures'][name]['code_sha256']:
            raise ValueError('Absent two-field normalization or resolver differs')
    rows=_rows(refs['builder']);texts={r['text'] for r in rows}
    if ('mov edx, 0xf0548bb7' not in texts or 'mov edx, 0xa1e5a149' not in texts
            or 'mov edx, 0xd6fcf3e4' in texts):
        raise ValueError('XP1 unit descriptor-only builder changed')
    order={r['text']:int(r['va'],16) for r in rows}
    if not order['call 0x180070b10']<order['call qword ptr [rax + 0xa0]']<order['call 0x180844580']:
        raise ValueError('XP1 descriptor-only native dispatch changed')
    if not any('0x7b4264e9' in r['text'] for r in _rows(refs['caller'])):
        raise ValueError('XP1 conditional unit-operation event changed')
    return p


def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_absent_event_source import source_dependencies as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unqualified absent descriptor engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=verify_source()
    two=verify_two_field_source()
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['images'].values(),*p['references'].values(),
          dict(path=TWO_SOURCE[0],sha256=TWO_SOURCE[1]),*two['references'].values()]
    return {str(resolve_path(resource_root()/ref['path']).resolve()):ref['sha256'] for ref in refs}


def has_shape(fields):
    return type(fields) is dict and set(fields) in (unit.FIELD_KEYS,b4.FIELD_KEYS,unit_two.FIELD_KEYS)


def _bind_reader(arguments):
    from .event_argument_service import EventArgumentReader,EventArgumentService
    from .a0_family_service import A0FamilyService
    if type(arguments) is not EventArgumentService or type(arguments.reader) is not EventArgumentReader:
        raise ValueError('Absent descriptor callback requires its actual argument owner/reader')
    arguments._check()
    reader=arguments.reader;owner=getattr(arguments,'consumer',None);d=arguments.deferred
    if (type(owner) is not A0FamilyService or owner.arguments is not arguments or owner.deferred is not d
            or reader.core is not d.core or reader.base!=d.core._handle
            or reader.core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
            or reader.core_sha256!=d.cache_core_sha256 or reader.closed or reader.thread!=arguments.thread):
        raise ValueError('Absent descriptor callback has a foreign owner or source reader')
    owner._check()
    if reader.core_sha256==XP2_CORE_SHA256:
        from . import xp2_absent_event_source as selected
        pins=(selected.SOURCE[1],)
    else:pins=(SOURCE[1],TWO_SOURCE[1])
    identity=(reader.core,reader.base,reader.core_sha256,reader.read,*pins)
    bound=getattr(reader,'_xp1_absent_descriptor_source',None)
    if bound is not None:
        if bound!=identity:raise ValueError('Absent descriptor source reader changed')
        return owner
    if reader.core_sha256==XP2_CORE_SHA256:
        selected.verify_live(reader.base,reader.read)
        reader._xp1_absent_descriptor_source=identity
        return owner
    p=verify_source()
    two=verify_two_field_source()
    for ref in (p['references']['builder'],p['references']['caller'],
                two['references']['builder'],two['references']['caller'],two['references']['float_builder']):
        for row in _rows(_source((ref['path'],ref['sha256']))):
            raw=bytes.fromhex(row['bytes'])
            if reader.read(reader.base+int(row['va'],16)-0x180000000,len(raw))!=raw:
                raise ValueError('XP1 absent descriptor live instructions changed')
    reader._xp1_absent_descriptor_source=identity
    return owner


def dispatch(arguments,kind,fields):
    """No queue mutation: retain preceding native B0 work for normal publication."""
    owner=_bind_reader(arguments)
    if not has_shape(fields):raise ValueError('Unqualified absent descriptor shape')
    d=arguments.deferred
    before=(id(d.pending),tuple(d.pending),d._sequence,d.consumed_count,d.consumed_bytes,
            d.host_notification_counter,d.host_metadata_counter,d.consumed_digest.copy().digest())
    options=dict(normalizer_transform_present=owner.normalizer_transform_present,
                 registry_profile=owner.callback_registry_profile,
                 dynamic_registration_present=owner.dynamic_event_registration_present,
                 entity_listener_count=owner.entity_listener_count)
    if set(fields)==unit.FIELD_KEYS:
        result=unit.validate_absent_event(kind,fields,arguments.reader.read,**options)
    elif set(fields)==unit_two.FIELD_KEYS:
        result=unit_two._validate_profile_event(kind,fields,arguments.reader.read,**options)
    else:
        result=b4.validate_absent_event(kind,fields,**options)
    after=(id(d.pending),tuple(d.pending),d._sequence,d.consumed_count,d.consumed_bytes,
           d.host_notification_counter,d.host_metadata_counter,d.consumed_digest.copy().digest())
    if before!=after:raise RuntimeError('Absent descriptor normalization changed the owned FIFO')
    if arguments.reader.core_sha256==XP2_CORE_SHA256:
        from .xp2_absent_event_source import SOURCE as selected_source
        provenance=dict(core_sha256=XP2_CORE_SHA256,source_sha256=selected_source[1])
    else:provenance=dict(xp1_source_sha256=SOURCE[1],two_field_supplement_sha256=TWO_SOURCE[1])
    arguments.emit('native_shared_absent_descriptor_event',dispatch_kind=hex(kind),
        normalized_fields=result,native_dispatch_return=result['normalizer_result'],
        **provenance,callback_registered=False,
        core_internal_dispatch_preserved=True,preceding_fifo_preserved=True,
        copied_variant_headers=True,pointer_payloads_retained=False,
        payload_exposed_to_learner=False,eligible_for_training=False)
    return result['normalizer_result']

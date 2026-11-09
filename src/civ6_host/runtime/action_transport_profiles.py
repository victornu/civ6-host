"""Immutable engine layouts for the shared native command transport.

This module selects ABI addresses. It does not construct an action, invent a
queue, implement a game rule or declare delivery equivalent to a game effect.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256,XP2_CORE_SHA256,_source,_body

SOURCE=('work/host-extensions/xp1-action-static/action-transport-source-v1.json',
        'ad72c1bdd6b5c3eb95600f0e3d79161ad6b5441640349487f9c5c9b27ea1608e')

@dataclass(frozen=True)
class ActionTransportProfile:
    core_sha256:str
    processor_flags_rva:int
    game_getter_rva:int
    game_release_rva:int
    game_vtable_rva:int
    game_update_rva:int
    archive_vtable_rva:int
    archive_size_rva:int
    receive_queue_rva:int
    view_ctor_rva:int
    view_dtor_rva:int
    view_vtable_rva:int
    receive_rva:int
    drain_rva:int
    optional_queue_flag_rva:int

BASE=ActionTransportProfile(BASE_CORE_SHA256,
    9156608,4382432,4409168,7990488,4411488,8511040,7670032,
    9156296,7669584,7669776,8510944,4384080,4383952,9156345)

def xp1_source():
    p=_source(SOURCE)
    if (p['schema']!='civ6_host.xp1_action_transport.static.v1'
            or p['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or p['profile']['core_sha256']!=XP1_CORE_SHA256
            or p['validation']['all_instruction_bytes_match_pinned_images'] is not True
            or p['validation']['structural_pair_count']!=21
            or p['validation']['equal_normalized_pairs']!=21 or p['native_execution'] is not False):
        raise ValueError('XP1 action transport source/profile changed')
    for row in p['references'].values():_source((row['path'],row['sha256']))
    return p

def source_dependencies(*,core_sha256=XP1_CORE_SHA256,execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_action_transport_source import source_dependencies as selected
        return selected(execution_image=execution_image)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown action transport source engine')
    if execution_image is not None:raise ValueError('XP1 action transport does not accept an XP2 execution image')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=xp1_source();rows=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'].values()]
    return {str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in rows}

def verify_xp1(base,context,read):
    p=xp1_source();r=p['profile']
    if int.from_bytes(read(context,8),'little')!=base+r['outer_vtable_rva']:
        raise ValueError('XP1 transport outer context differs')
    for name,body in p['functions']['xp1'].items():
        for fragment in _body(body)['fragments']:
            for i in fragment['instructions']:
                raw=bytes.fromhex(i['bytes'])
                if read(base+int(i['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('XP1 action transport code differs: '+name)
    for slot in p['slots']['xp1']:
        if int.from_bytes(read(base+slot['vtable_rva']+slot['slot'],8),'little')!=base+slot['target_rva']:
            raise ValueError('XP1 action transport slot differs')
    g,o,v,q=r['game_update'],r['output_archive'],r['receive_stream'],r['queue']
    return ActionTransportProfile(XP1_CORE_SHA256,g['processor_flags_rva'],g['getter_rva'],
        g['release_rva'],g['facade_vtable_rva'],g['update_rva'],o['vtable_rva'],o['length_rva'],
        q['sentinel_rva'],v['constructor_rva'],v['destructor_rva'],v['vtable_rva'],
        r['receive']['outer_rva'],r['drain']['outer_rva'],q['optional_queue_flag_rva'])

def transport_profile(core_sha256,core,context,read):
    if core_sha256==BASE_CORE_SHA256:return BASE
    if core_sha256==XP2_CORE_SHA256:
        image_path=Path(core._name).resolve()
        selected=getattr(core,'_civ6_host_execution_image',None)
        expected_sha256=core_sha256
        if selected is not None:
            from .execution_images import runtime_source_pins
            if str(image_path)!=selected.path:
                raise ValueError('XP2 action transport Core path differs from its execution image')
            expected_sha256=runtime_source_pins({selected.path:core_sha256},
                execution_image=selected)[selected.path]
        if hashlib.sha256(image_path.read_bytes()).hexdigest()!=expected_sha256:
            raise ValueError('XP2 action transport binary changed')
        from .xp2_action_transport_source import ABI,verify_live
        verify_live(core._handle,read,family='transport',context=context)
        return ABI
    if core_sha256==XP1_CORE_SHA256:
        if hashlib.sha256(Path(core._name).read_bytes()).hexdigest()!=core_sha256:
            raise ValueError('XP1 action transport binary changed')
        return verify_xp1(core._handle,context,read)
    raise ValueError('Native action transport engine is not yet source-qualified')

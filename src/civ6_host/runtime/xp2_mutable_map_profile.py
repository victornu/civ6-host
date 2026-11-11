"""Source/identity guards for XP2's mutable GameEvents table bridge.

This profile does not admit a saved game or establish World Congress behavior.
It reuses the native map reader/owner and an explicit, protected native bridge.
"""
from __future__ import annotations

import hashlib
import struct
import ctypes as C

from .configuration_profiles import _source
from .saved_load_profiles import XP2_CORE_SHA256
from .xp2_aux_map_profile import profile as map_profile, verify_live as verify_map
from .source_build_identity import verify_source_build

SOURCE=('work/host-extensions/xp2-mutable-map/source-profile-v2.json', 'f7629a4468e9ca23f5694852342d1ee0cc64635c5cf7f746a81d6f27618a66e4')
COMPONENTS={'script_game_event_dispatch_legacy.inc': '6c666a6f5e8d0702c47f3ed3a5f6ca66037eccb8963ce394b61777e9bf49d73b', 'script_game_events_full.inc': '228b8679a930eb180990ce92e1237d35cf98337298c04c9c6a4f06bd03b41e69', 'script_aux_a8.inc': 'ca112cccb603a86cd463650732739b47bfc154a108946aa0c66b299776a3276b', 'script_game_event_dispatch.inc': '834ef03bef26a54514a571ce3a45fc977bd30cbcbaadfec8e78785c2d2a4edab', 'script_game_event_result_map.inc': 'b90214047bf68869cfd13c214d7791c2fc6df5c2c61a7fef1106468bc1a65edd'}
VTABLE=0xabf080
SETTERS=((0x20,0x989d0),(0xa8,0x9a0240),(0x108,0x9a6e40),
         (0x120,0x9a0120),(0x128,0x9a0000),(0x130,0x99fee0),(0x138,0x9a0d30))
HELPERS=dict(clone_construct=0x99d920,name_id=0x9a3f10,resolver_vtable=0xabeff8)


def source():
    proof=_source(SOURCE)
    if (proof['schema']!='civ6-host.xp2-mutable-map-source.v1'
            or proof['core_sha256']!=XP2_CORE_SHA256
            or proof['native_execution'] is not False or proof['vtable_rva']!=VTABLE
            or tuple((r['slot'],r['target_rva']) for r in proof['slots'])!=SETTERS
            or dict(proof['helpers'])!=HELPERS):
        raise ValueError('XP2 mutable map source contract differs')
    from .native.native_source_cache import load_pinned_json
    from .paths import resource_root
    from .resource_resolution import resolve_path
    root=resource_root()
    for row in proof['references']:
        path=resolve_path(root/row['path']).resolve(strict=True)
        if not path.is_relative_to(root) or not 0<path.stat().st_size==row['bytes']<=8*1024*1024:
            raise ValueError('XP2 mutable map source reference left its bounds')
        load_pinned_json(path,row['sha256'])
    for body in proof['bodies']:
        raw=bytes.fromhex(body['raw_hex'])
        if (type(body['rva']) is not int or not 0<body['rva']<0x1000000
                or not 0<len(raw)==body['bytes']<=1024*1024
                or hashlib.sha256(raw).hexdigest()!=body['sha256']):
            raise ValueError('XP2 mutable map source body differs')
    return proof


def verify_live(base,read):
    if type(base) is not int or not 0<base<(1<<47)-0x1000000 or not callable(read):
        raise ValueError('XP2 mutable map requires a checked native reader')
    proof=source()
    verify_map(map_profile(),base,read)
    for body in proof['bodies']:
        raw=read(base+body['rva'],body['bytes'])
        if type(raw) is not bytes or raw!=bytes.fromhex(body['raw_hex']):
            raise ValueError('XP2 mutable map code differs: '+body['name'])
    for slot,target in SETTERS:
        if read(base+VTABLE+slot,8)!=struct.pack('<Q',base+target):
            raise ValueError('XP2 mutable map dispatch differs')
    # Relocations are checked as relocated addresses, never as raw PE pointers.
    for slot,target in ((0,0x99d820),(8,0x9a1610)):
        if read(base+HELPERS['resolver_vtable']+slot,8)!=struct.pack('<Q',base+target):
            raise ValueError('XP2 mutable map key resolver dispatch differs')
    return proof


def verify_runtime(runtime,core,read):
    from .native.native_core_context_profiles import (profile_for_core,
        require_executable_profile, validate_loaded_modules)
    from .native.native_probe import Windows
    from .profile_script_binding import _current_executable
    selected=profile_for_core(core._name,mode='context',
        execution_image=getattr(core,'_civ6_host_execution_image',None))
    require_executable_profile(selected)
    if selected.source_core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Mutable map engine differs from its actual file')
    validate_loaded_modules(selected,Windows().modules())
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.GetModuleHandleW.argtypes,kernel.GetModuleHandleW.restype=[C.c_wchar_p],C.c_void_p
    if getattr(runtime.host,'_handle',None)!=kernel.GetModuleHandleW(None):
        raise ValueError('Mutable map native host handle is not the admitted executable')
    kernel.GetModuleFileNameW.argtypes=[C.c_void_p,C.c_wchar_p,C.c_uint32]
    kernel.GetModuleFileNameW.restype=C.c_uint32
    path=C.create_unicode_buffer(32768)
    count=kernel.GetModuleFileNameW(core._handle,path,len(path))
    from pathlib import Path
    if not 0<count<len(path) or Path(path.value).resolve()!=selected.core_path.resolve():
        raise ValueError('Mutable map Core handle differs from its actual file')
    runtime.registry._check()
    if runtime.closed or not runtime.root or runtime.lua['gettop'](runtime.root):
        raise ValueError('Mutable map requires a live owned empty root')
    if not COMPONENTS:
        raise ValueError('Mutable map native components have not been sealed')
    # Select an exact authored source composition. The retained dispatcher is
    # either direct, or aliased under the separately authenticated state-scope
    # wrapper; an arbitrary differently named/rewritten component is refused.
    core_components={k:v for k,v in COMPONENTS.items() if k not in
                     ('script_game_events_full.inc','script_aux_a8.inc')}
    executable = _current_executable()
    from . import xp2_bbg_property_table as bbg
    from .source_build_identity import (xp2_component_requirements, CURRENT_HAVOK_BUILD_PROFILE,
                                        CURRENT_STRINGS_BUILD_PROFILES)
    build = verify_source_build(executable, required_components=xp2_component_requirements(executable, {
        'script_game_event_result_map.inc': core_components['script_game_event_result_map.inc']}))
    if build['profile'] in (bbg.BUILD_PROFILE, CURRENT_HAVOK_BUILD_PROFILE, *CURRENT_STRINGS_BUILD_PROFILES):
        core_components['script_game_event_dispatch_bbg_parent.inc'] = core_components['script_game_event_dispatch.inc']
        core_components['script_game_event_dispatch.inc'] = bbg.dispatch_wrapper_sha256(build)
        core_components['script_aux_b8.inc'] = bbg.property_component_sha256(build)
    native = verify_source_build(executable, required_components=xp2_component_requirements(executable, core_components))
    if any(native['sources'].get(k)!=COMPONENTS[k] for k in
           ('script_game_events_full.inc','script_aux_a8.inc')):
        from .script_event_state import COMPONENTS as scoped
        if not scoped:
            raise ValueError('Mutable map scoped source composition is not sealed')
        native=verify_source_build(_current_executable(),required_components={
            **scoped,'script_game_events_full_legacy.inc':COMPONENTS['script_game_events_full.inc']})
    proof=verify_live(core._handle,read)
    return dict(source_sha256=SOURCE[1],core_sha256=selected.core_sha256,
                native_host_sha256=native['host_sha256'],profile_id=2,
                saved_load_admitted=False,source_schema=proof['schema'])


def source_dependencies():
    from .paths import resource_root
    from .resource_resolution import resolve_path
    proof=source()
    return {str(resolve_path(resource_root()/name).resolve()):digest for name,digest in
            (SOURCE,*[(row['path'],row['sha256']) for row in proof['references']])}

"""Exact XP2 UI registration on the existing owned, protected Lua child.

Native code chooses its mode and registers its own getters. A returned outer
frame does not establish that every nested registration succeeded.
"""
import ctypes as C
import hashlib
import os
from pathlib import Path
import struct

from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp2-ui-binding-static/source-profile-v1.json',
        'cfbf441b0b279dfe48b1b6fd674f6305e5ba0ad57d84ed1d0ff0fb5b870fb1fa')
PINS=('work/host-extensions/xp2-ui-binding-static/source-pins.json',
      '43d51bd03fc2738e70a3e8c9d137c245573afe29e8c803eb64a6dbc1cd1d20f2')
UI_THUNK_RVA=0x5a1db0
UI_COMPONENT_SHA='a1163e8e73ba6c2150e16a3b57706a9a79f23a7e09489d0ee4cc57fbb05c7a70'
_ABI=(0xa101e8,0x68,0x590440,0xb8f0e0,0xa126c8,0x10,0x5a1da0,0x18,
      UI_THUNK_RVA,0x5bdd80,0x9ad880,0xb90cc0,0xb8aa78,0xb8aa78,0x88,0xb8c478,0x68)
_ABI_KEYS=('outer_vtable_rva','outer_script_slot','outer_script_getter_rva',
    'interface_pointer_rva','interface_vtable_rva','game_registration_slot',
    'game_registration_rva','ui_registration_slot','ui_thunk_rva','ui_registration_rva',
    'protected_wrapper_rva','core_registration_lock_rva','registration_prerequisite_global_rva',
    'mode_provider_global_rva','mode_map_offset','mode_key_global_rva','mode_map_getter_slot')


def _bodies(proof):
    return ((group+':'+name,body) for group in
            ('functions','registration_entries','protected_callbacks')
            for name,body in proof[group].items())


def source():
    p=_source(SOURCE);abi=p['abi'];contract=p['contract']
    if (p['schema']!='civ6-host.xp2-ui-binding.source.v1'
            or p['image']['sha256']!=XP2_CORE_SHA256
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or abi['core_sha256']!=XP2_CORE_SHA256
            or tuple(abi[k] for k in _ABI_KEYS)!=_ABI
            or abi['native_return_ignored'] is not True
            or tuple(len(p[g]) for g in ('functions','registration_entries','protected_callbacks'))!=(25,34,17)
            or p['validation']['all_captured_instruction_bytes_match_installed_image'] is not True
            or p['validation']['captured_body_bytes']!=43500
            or contract['protected_registration']['enclosing_registration_tests_result'] is not False
            or contract['error']['outer_zero_status_proves_all_nested_registrations'] is not False
            or contract['error']['preserve_installed_native_writer'] is not True):
        raise ValueError('XP2 UI source/ABI differs')
    for name,b in _bodies(p):
        parts=[]
        for f in b['fragments']:
            raw=bytes.fromhex(f['raw_hex']);parts.append(raw)
            if (len(raw)!=f['length'] or hashlib.sha256(raw).hexdigest()!=f['sha256']
                    or ''.join(i['bytes'] for i in f['instructions'])!=raw.hex()):
                raise ValueError('XP2 UI source fragment differs: '+name)
        raw=b''.join(parts)
        if (raw.hex()!=b['raw_hex'] or len(raw)!=b['bytes']
                or hashlib.sha256(raw).hexdigest()!=b['sha256']):
            raise ValueError('XP2 UI complete body differs: '+name)
        if name=='functions:mode_predicate':
            if (b['all_conditional_targets_resolved_in_profile'] is not True
                    or [dict(r) for r in b['conditional_tail_targets']]!=[
                        dict(source_rva='0x60b5ba',target_rva='0x165aa0',profile_body='configured_mode_getter')]):
                raise ValueError('XP2 UI mode tail is not captured')
        elif (b['all_conditional_targets_captured'] is not True
                or b['boundary_method'] not in ('complete-runtime-function-chained-unwind-root-v2',
                                               'complete-reachable-leaf-cfg-v1')):
            raise ValueError('XP2 UI CFG is incomplete: '+name)
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    return p


def source_dependencies():
    """Resolve the frozen transitive inventory into the current resource root."""
    from .a0_family_source import _path, verify_pinned_files
    from .script_binding_profiles import source_dependencies as game_dependencies
    source();captured=_source(PINS)
    names=[name.replace('\\','/') for name in captured if name.replace('\\','/').endswith('/'+SOURCE[0])]
    if len(names)!=1:raise ValueError('XP2 UI source inventory root differs')
    prefix=names[0][:-len(SOURCE[0])]
    pins={str(_path(PINS[0])):PINS[1]}
    for name,sha in captured.items():
        name=name.replace('\\','/')
        if not name.startswith(prefix):raise ValueError('XP2 UI source inventory escaped its root')
        pins[str(_path(name[len(prefix):]))]=sha
    pins.update(game_dependencies(XP2_CORE_SHA256));verify_pinned_files(pins)
    return pins


def verify_live(base,read):
    """Read all complete captured branches, without invoking a native function."""
    if (type(base) is not int or base<65536 or base%65536
            or base>(1<<47)-0x10000000 or not callable(read)):
        raise ValueError('Invalid XP2 UI image/reader')
    p=source()
    for name,b in _bodies(p):
        for f in b['fragments']:
            raw=bytes.fromhex(f['raw_hex'])
            # The shared local reader deliberately caps each process-memory
            # request at 6784 bytes. Large enum registrations remain complete,
            # checked in bounded chunks without enlarging that reader contract.
            start=base+int(f['start_rva'],16)
            for offset in range(0,len(raw),4096):
                expected=raw[offset:offset+4096]
                actual=read(start+offset,len(expected))
                if type(actual) is not bytes or actual!=expected:
                    raise ValueError('XP2 UI native body differs: '+name)
    for row in p['slots']:
        if read(base+row['table_rva']+row['slot'],8)!=struct.pack('<Q',base+row['target_rva']):
            raise ValueError('XP2 UI native slot differs')
    for address,row in p['error_literals'].items():
        if read(base+int(address,16),row['bytes'])!=bytes.fromhex(row['raw_hex']):
            raise ValueError('XP2 UI native error literal differs')
    return p


def _owner(runtime,game_child,ui_child,context,core):
    from .core_script_services import check_bound
    from .saved_load_services import SavedLoadServices
    from .xp1_ui_binding import SavedPlayerView
    borrowed=check_bound(runtime,context,core)
    prefix=getattr(borrowed.owner,'_saved_load_services',None)
    if (type(prefix) is not SavedLoadServices or prefix.runtime is not runtime
            or prefix.host is not borrowed.owner or prefix.game_child is not game_child
            or getattr(prefix,'ui_child',None) is not ui_child or prefix.core is not core
            or prefix.context!=context or prefix.core_sha256!=XP2_CORE_SHA256):
        raise ValueError('XP2 UI requires the actual saved service owner and children')
    prefix.check();backend=prefix.backend;backend.check_thread()
    view=getattr(backend,'_xp1_player_view',None)
    if (type(view) is not SavedPlayerView or view.owner is not backend
            or view.prefix is not prefix or view.runtime is not runtime or view.child is not ui_child
            or view.core_sha256!=XP2_CORE_SHA256 or view.source_sha256!=SOURCE[1]
            or view.attempted is not True or view.completed is not False
            or backend.core is not core or backend.context!=context or backend.prefix is not prefix
            or backend.destroyed or backend.load_abi.core_sha256!=XP2_CORE_SHA256):
        raise ValueError('XP2 UI requires the exact active player view')
    view.check_active()
    return view,borrowed


def _verify_imports(runtime,selected,base,read,proof):
    """Keep native protection/error imports attached to their actual libraries."""
    if Path(runtime.library._name).resolve(strict=True)!=(
            selected.shared_dependency_directory/'HavokScript_FinalRelease.dll').resolve(strict=True):
        raise ValueError('XP2 UI Lua library differs from the owned runtime')
    libraries={'HavokScript_FinalRelease.dll':runtime.library}
    for row in proof['imports'].values():
        name=row['dll']
        if name not in libraries:libraries[name]=C.WinDLL(name)
        address=C.cast(getattr(libraries[name],row['name']),C.c_void_p).value
        if not address or read(base+int(row['iat_rva'],16),8)!=struct.pack('<Q',address):
            raise ValueError('XP2 UI native import owner differs: '+row['name'])


def bind_ui_api(runtime,game_child,ui_child,core_context,core):
    from . import script_binding_profiles as game
    from .native.native_core_context_profiles import profile_for_core,validate_loaded_modules
    from .native.native_probe import Windows
    from .native.native_setup import local_reader
    from .profile_script_binding import (_current_executable,PROFILE_COMPONENT_SHA,SHARED_COMPONENT_SHA)
    from .source_build_identity import verify_source_build
    if os.name!='nt' or C.sizeof(C.c_void_p)!=8:
        raise ValueError('XP2 UI registration requires Windows x64')
    game_pointer=runtime.registry.validate(game_child);ui_pointer=runtime.registry.validate(ui_child)
    if (game_pointer==ui_pointer or getattr(runtime,'_xp2_ui_bind_entered',False)
            or getattr(runtime,'_profile_script_bind_attempted',False) is not True
            or any(runtime.lua['gettop'](p) for p in (runtime.root,game_pointer,ui_pointer))
            or not hasattr(runtime.host,'LAB_ProfileScriptCoreUIBindingsInstall')):
        raise ValueError('XP2 UI requires fresh distinct managed children and its native export')
    view,borrowed=_owner(runtime,game_child,ui_child,core_context,core)
    selected=profile_for_core(core._name,mode='context')
    if selected.ruleset!='xp2' or selected.core_sha256!=XP2_CORE_SHA256:
        raise ValueError('XP2 UI binder refuses another engine')
    validate_loaded_modules(selected,Windows().modules())
    build=verify_source_build(_current_executable(),required_components={
        'script_core_binding_profiles.inc':PROFILE_COMPONENT_SHA,
        'script_core_bindings.inc':SHARED_COMPONENT_SHA,
        'script_core_ui_binding_profiles.inc':UI_COMPONENT_SHA})
    source_dependencies();read=local_reader();proof=verify_live(core._handle,read)
    abi=game.profile_for_sha(XP2_CORE_SHA256)
    getter=game.verify_live(abi,core._handle,core_context,read)
    _verify_imports(runtime,selected,core._handle,read,proof)
    version=runtime.host.LAB_ProfileScriptCoreBindingsVersion
    version.argtypes,version.restype=[],C.c_uint32
    if version()!=1:raise ValueError('XP2 UI protected profile ABI version differs')
    # Consume the attempt before the official getter, which owns lazy state.
    runtime._xp2_ui_bind_entered=True
    interface=C.WINFUNCTYPE(C.c_void_p,C.c_void_p)(getter)(core_context)
    game.verify_interface(abi,core._handle,interface,read)
    install=runtime.host.LAB_ProfileScriptCoreUIBindingsInstall
    install.argtypes,install.restype=[C.c_void_p]*4+[C.c_uint32],C.c_int
    runtime.emit('before_xp1_ui_api_bind',core_sha256=XP2_CORE_SHA256,
        method_rva=hex(UI_THUNK_RVA),source_sha256=SOURCE[1],native_host_sha256=build['host_sha256'])
    status=install(game_pointer,ui_pointer,interface,core._handle,abi.profile_id)
    runtime._status(ui_pointer,status,'XP2 native UI GameCore API registration')
    if any(runtime.lua['gettop'](p) for p in (runtime.root,game_pointer,ui_pointer)):
        raise RuntimeError('XP2 UI registration left a nonempty Lua stack')
    # The exact owner must still hold the children after native registration.
    view.check_active()
    receipt=dict(native_ui_registration_returned=True,outer_protected_status=status,
        complete_registration_verified=False,method_rva=hex(UI_THUNK_RVA),
        distinct_managed_children=True,gameplay_api_copied=False,
        core_sha256=XP2_CORE_SHA256,source_sha256=SOURCE[1],profile_id=abi.profile_id,
        native_host_sha256=build['host_sha256'],
        service_init_source_sha256=borrowed.init_source_sha256,
        service_type_source_sha256=borrowed.type_source_sha256)
    runtime.emit('xp1_ui_api_bind_returned',**receipt)
    return receipt

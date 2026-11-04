"""Borrow XP2's initialized connections through the existing Lua bindings.

This owns no Database connection and performs no GameCore initialization.
Source/layout guards do not establish saved-Load or script/gameplay readiness.
"""
from __future__ import annotations

import ctypes as C
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import struct
import threading

from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path
from .saved_load_profiles import XP2_CORE_SHA256

INIT_SOURCE = ('work/host-extensions/xp2-script-services/xp2-borrowed-services-init-correction.json',
               'be3ff6728cdc68d146c05d95f25982318ccf8d44ff62107f2e0d9804922ff1a5')
TYPE_SOURCE = ('work/host-extensions/xp2-script-services/xp2-borrowed-services-connection-type.json',
               'e1e8b73b645d9122024e1ded5ef9c14ddd0d69ae556f4942818d891349cf4675')
_LIMIT = (1 << 47)-1


def _require(condition, message):
    if not condition: raise ValueError(message)


def _source(reference):
    name,sha=reference
    _require(len(sha)==64 and all(c in '0123456789abcdef' for c in sha),
             'XP2 borrowed-service type source is not sealed')
    root=resource_root()
    path=resolve_path(root/name).resolve(strict=True)
    _require(path.is_relative_to(root) and 0 < path.stat().st_size <= 4*1024*1024,
             'XP2 borrowed-service source left its bounded resource root')
    return load_pinned_json(path,sha)


def _address(value):
    _require(type(value) is int and 0x10000 <= value <= _LIMIT and value%8==0,
             'Invalid borrowed-service address')
    return value


def _read(read,address,size):
    _require(type(address) is int and 0x10000 <= address <= _LIMIT-size+1,
             'Borrowed-service read overflow')
    raw=read(address,size)
    _require(type(raw) is bytes and len(raw)==size,'Incomplete borrowed-service read')
    return raw


def _pointer(read,address): return struct.unpack('<Q',_read(read,address,8))[0]


def _inspect(core,context,database,read):
    """Read source-proven state only; never invoke Init, Prepare or a getter."""
    source=_source(INIT_SOURCE)
    type_source=_source(TYPE_SOURCE)
    _require(source['image']['sha256']==XP2_CORE_SHA256
             and type_source['image']['sha256']==XP2_CORE_SHA256,
             'Borrowed-service engine source differs')
    base=_address(core._handle);_address(context)
    imported=type_source['create_connection_import']
    _require((imported['dll'],imported['symbol'],imported['iat_rva'],imported['thunk_rva']) ==
             ('DatabaseDLL_FinalRelease.dll',
              '?CreateConnection@Database@@YAPEAVIDatabaseConnection1@1@PEBDHPEAVIDatabaseLogger@1@@Z',
              '0x9b7000','0x99d7b2'),'Borrowed-service import source differs')
    import_thunk=bytes.fromhex(imported['thunk_bytes'])
    _require(len(import_thunk)==6 and hashlib.sha256(import_thunk).hexdigest()==imported['thunk_sha256']
             and _read(read,base+0x99d7b2,6)==import_thunk,'Borrowed-service import thunk changed')
    # Resolving an export address does not invoke Database::CreateConnection.
    target=C.cast(getattr(database,imported['symbol']),C.c_void_p).value
    _require(target is not None and _pointer(read,base+0x9b7000)==target,
             'Borrowed-service import differs from owning DatabaseDLL')
    dispatch=source['init_dispatch']
    _require((dispatch['outer_vtable'],dispatch['outer_init_slot'],dispatch['outer_init_target'],
              dispatch['inner_pointer_offset'],dispatch['inner_vtable'],dispatch['inner_init_slot'],
              dispatch['inner_init_target']) ==
             ('0xa101e8','0x28','0x5905f0','0x08','0xa44f70','0x08','0x45d90'),
             'Borrowed-service Init source dispatch differs')
    body=dispatch['complete_body']
    raw=bytes.fromhex(body['raw_hex'])
    _require(body['total_length']==len(raw)==316
             and hashlib.sha256(raw).hexdigest()==body['sha256']
             and _read(read,base+0x45d90,len(raw))==raw,
             'Borrowed-service Init code changed')
    thunk=bytes.fromhex(''.join(row['bytes'] for row in dispatch['outer_thunk_instructions']))
    _require(len(thunk)==11 and _read(read,base+0x5905f0,len(thunk))==thunk,
             'Borrowed-service Init thunk changed')
    _require(_pointer(read,context)==base+0xa101e8
             and _pointer(read,base+0xa101e8+0x28)==base+0x5905f0,
             'Borrowed-service outer context differs')
    inner=_address(_pointer(read,context+8))
    _require(_pointer(read,inner)==base+0xa44f70
             and _pointer(read,base+0xa44f70+8)==base+0x45d90,
             'Borrowed-service inner context differs')
    _require(_read(read,inner+0x40,1)==b'\x01','Borrowed-service Init has not completed')
    _require(_pointer(read,base+0xb8aa60)==inner
             and _pointer(read,base+0xb8aa78)==inner+0xd80,
             'Borrowed-service globals belong to another context')
    configuration=_address(_pointer(read,inner+0x50))
    gameplay=_address(_pointer(read,inner+0x58))
    return inner,configuration,gameplay


@dataclass(frozen=True,eq=False,slots=True)
class BorrowedCoreServices:
    runtime: object
    owner: object
    core: object
    root: int
    context: int
    inner: int
    configuration: int
    gameplay: int
    thread: int
    init_source_sha256: str
    type_source_sha256: str


def prepare(runtime,owner,context,core,*,core_sha256):
    from .native.native_core_context_profiles import profile_for_core,validate_loaded_modules
    from .native.native_probe import Windows
    from .native.native_setup import local_reader
    from .profile_script_binding import (verify_source_build,_current_executable,
                                         PROFILE_COMPONENT_SHA,SHARED_COMPONENT_SHA)
    _require(core_sha256==XP2_CORE_SHA256,'Unknown profiled script-service engine')
    _require(os.name=='nt' and C.sizeof(C.c_void_p)==8,'Profiled script services require Windows x64')
    _require(core is not None and isinstance(getattr(core,'_name',None),(str,Path)),
             'Profiled script services require the explicit Core library')
    runtime.registry._check()
    _require(not any((runtime.database_bound,runtime.configuration_bound,runtime.locale_bound))
             and getattr(owner,'localization_initialized',False) is True
             and not runtime.lua['gettop'](runtime.root),
             'Profiled script services require fresh owned root and initialized localization')
    selected=profile_for_core(core._name,mode='context')
    _require(selected.ruleset=='xp2' and selected.core_sha256==core_sha256,
             'Borrowed-service Core differs from selected engine')
    validate_loaded_modules(selected,Windows().modules())
    for library,name in ((owner.database,'DatabaseDLL_FinalRelease.dll'),
                         (owner.localization_library,'Localization_FinalRelease.dll')):
        _address(library._handle)
        _require(isinstance(library._name,(str,Path))
                 and Path(library._name).resolve(strict=True)==(selected.shared_dependency_directory/name).resolve(strict=True),
                 'Borrowed-service owner library differs from loaded source profile')
    verify_source_build(_current_executable(),required_components={
        'script_core_binding_profiles.inc':PROFILE_COMPONENT_SHA,
        'script_core_bindings.inc':SHARED_COMPONENT_SHA})
    inner,configuration,gameplay=_inspect(core,context,owner.database,local_reader())
    return BorrowedCoreServices(runtime,owner,core,runtime.root,context,inner,configuration,gameplay,
                                threading.get_ident(),INIT_SOURCE[1],TYPE_SOURCE[1])


def _check(runtime,lease,context,core):
    from .native.native_setup import local_reader
    _require(type(lease) is BorrowedCoreServices and lease.runtime is runtime
             and lease.owner is runtime.service_owner and lease.core is core
             and lease.root==runtime.root and lease.context==context
             and lease.thread==threading.get_ident()
             and lease.init_source_sha256==INIT_SOURCE[1] and lease.type_source_sha256==TYPE_SOURCE[1]
             and getattr(lease.owner,'localization_initialized',False) is True
             and runtime.database_bound is runtime.configuration_bound is runtime.locale_bound is True,
             'Profiled script-service ownership or lifetime differs')
    runtime.registry._check()
    _require(_inspect(core,context,lease.owner.database,local_reader())==(lease.inner,lease.configuration,lease.gameplay),
             'Borrowed-service connection identities changed')


def commit(runtime,lease):
    _check(runtime,lease,lease.context,lease.core)
    _require(getattr(runtime,'_profile_borrowed_services',None) is None,
             'Profiled script-service lease already exists')
    runtime._profile_borrowed_services=lease
    runtime.emit('profile_script_services_borrowed',core_sha256=XP2_CORE_SHA256,
                 init_source_sha256=INIT_SOURCE[1],type_source_sha256=TYPE_SOURCE[1],
                 owns_database_connections=False,initialization_repeated=False)


def check_bound(runtime,context,core):
    lease=getattr(runtime,'_profile_borrowed_services',None)
    _check(runtime,lease,context,core)
    return lease

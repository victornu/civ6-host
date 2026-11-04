"""XP2 preflight for the existing saved-script service graph.

This selects source metadata, not a saved-game admission. The graph still needs
its exact official inputs and real script/context/Load lifetime qualification.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import struct

from .configuration_profiles import _source,configuration_abi
from .saved_load_profiles import XP2_CORE_SHA256,profile_for_sha
from .paths import resource_root
from .resource_resolution import resolve_path
from .native.native_source_cache import load_pinned_json

SOURCE=('work/host-extensions/xp2-saved-script-services/source-profile-v1.json','a285f3b28885d7b3f4323991e2c359afe900d7c6ccfc1d38c323cf4f6c7f668f')


def _require(condition,message):
    if not condition:raise ValueError(message)


def _read(read,address,size):
    _require(type(address) is int and type(size) is int and 0<size<=1024*1024
             and 0<address<(1<<47)-size,'Invalid saved-script source read')
    value=read(address,size)
    _require(type(value) is bytes and len(value)==size,'Incomplete saved-script source read')
    return value


def _pointer(read,address):return struct.unpack('<Q',_read(read,address,8))[0]


def source():
    proof=_source(SOURCE)
    _require(proof['schema']=='civ6-host.xp2-saved-script-services-source.v1'
             and proof['native_execution'] is False and proof['core_sha256']==XP2_CORE_SHA256,
             'XP2 saved-script source identity differs')
    root=resource_root()
    for row in proof['references']:
        path=resolve_path(root/row['path']).resolve(strict=True)
        _require(path.is_relative_to(root) and 0<path.stat().st_size==row['bytes']<=8*1024*1024,
                 'XP2 saved-script source left its bounded root')
        load_pinned_json(path,row['sha256'])
    _require(0<len(proof['bodies'])<=128,'XP2 saved-script body inventory differs')
    for body in proof['bodies']:
        raw=bytes.fromhex(body['raw_hex'])
        _require(type(body['rva']) is int and 0<body['rva']<0x1000000
                 and 0<len(raw)==body['bytes']<=1024*1024
                 and hashlib.sha256(raw).hexdigest()==body['sha256'],
                 'XP2 saved-script source body differs')
    return proof


def verify_live(base,read,*,context,inner,host_pointer,auxiliary_pointer):
    _require(type(base) is int and 0<base<(1<<47)-0x1000000 and callable(read),
             'XP2 saved-script module or reader differs')
    proof=source();abi=profile_for_sha(XP2_CORE_SHA256);contract=proof['contract']
    _require(_pointer(read,context)==base+abi.outer_vtable_rva
             and _pointer(read,context+8)==inner
             and _pointer(read,inner)==base+abi.inner_vtable_rva,
             'XP2 saved-script native context differs')
    for body in proof['bodies']:
        _require(_read(read,base+body['rva'],body['bytes'])==bytes.fromhex(body['raw_hex']),
                 'XP2 saved-script live code differs: '+body['name'])
    for row in proof['slots']:
        _require(_pointer(read,base+row['vtable_rva']+row['slot'])==base+row['target_rva'],
                 'XP2 saved-script dispatch differs')
    for name,pointer in (('host',host_pointer),('auxiliary',auxiliary_pointer),('inner',inner)):
        _require(_pointer(read,base+contract['globals'][name])==pointer,
                 'XP2 saved-script installed global differs: '+name)
    manager=_pointer(read,inner+contract['manager_offset'])
    _require(manager!=0,'XP2 saved-script manager is not constructed')
    _read(read,manager,contract['manager_bytes'])
    return dict(configuration=dict(source_sha256=SOURCE[1],native_calls_made=False),
                events=dict(source_sha256=SOURCE[1],saved_game_load_admitted=False),manager=manager)


def verify_services(backend,runtime,read):
    from .core_script_services import check_bound
    _require(backend.configuration_abi is configuration_abi(XP2_CORE_SHA256),
             'XP2 saved-script configuration ABI must be canonical')
    runtime.registry._check()
    lease=check_bound(runtime,backend.context,backend.core)
    _require(lease.owner is backend.host and runtime.service_owner is backend.host,
             'XP2 saved-script connections belong to another owner')
    return verify_live(backend.core._handle,read,context=backend.context,inner=lease.inner,
                       host_pointer=backend.host.pointer,
                       auxiliary_pointer=C.addressof(backend.host.aux_object))


def require_uninitialized_game(backend,read,game):
    """Preserve the shared early-close guard with exact XP2 source metadata."""
    abi=profile_for_sha(XP2_CORE_SHA256);base=backend.core._handle
    _require(backend.configuration_abi is configuration_abi(XP2_CORE_SHA256),
             'XP2 saved-script close engine differs')
    _require(_read(read,base+abi.game_initialized_rva,8)==bytes.fromhex('0fb681a4020000c3'),
             'XP2 Game initialized getter differs')
    if game:
        _require(_pointer(read,game)==base+abi.game_vtable_rva,'XP2 saved-script close Game differs')
        if _read(read,game+0x2a4,1)!=b'\0':
            raise RuntimeError('Loaded Game teardown still needs its script and borrowed DB services')


def source_dependencies():
    proof=source()
    return {str(resolve_path(resource_root()/name).resolve()):digest for name,digest in
            (SOURCE,*[(row['path'],row['sha256']) for row in proof['references']])}

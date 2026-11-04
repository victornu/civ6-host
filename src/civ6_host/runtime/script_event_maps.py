"""Owned native map arguments, converted by the shared A8 transport at dispatch."""
from __future__ import annotations

import ctypes as C
import threading

from .configuration_profiles import configuration_abi, XP1_CORE_SHA256, XP2_CORE_SHA256
from .native import native_configuration_finalization as setup
from .native.native_application_configuration import NativeApplicationConfiguration, STORAGE_SIZE, _GUARD
from .native.native_aux_map_conversion import snapshot_parameter_map, MAX_OPS
from .native.native_script_arguments import HKSArgument, pack_arguments


class ParameterMapArgument:
    # Reuse the proven guarded native provider destruction, without inheriting
    # configuration readers or requiring 64 application player submaps.
    _check_guard = NativeApplicationConfiguration._check_guard
    _close_native = NativeApplicationConfiguration.close

    def __init__(self, factory, source_pointer):
        factory.check()
        self.factory, self.base, self.read = factory, factory.base, factory.read
        self.call, self.emit, self.closed = None, None, False
        self._configuration_abi = factory.abi
        # Bound and qualify the borrowed source before entering native copy.
        # Names are deliberately not resolved here. The native assignment
        # owns values; its resolver remains borrowed until dispatch/release.
        factory.snapshot(source_pointer,names=False,native_copy_budget=True)
        self.storage=C.create_string_buffer(STORAGE_SIZE+2*len(_GUARD))
        start=C.addressof(self.storage)
        C.memmove(start,_GUARD,len(_GUARD))
        C.memmove(start+len(_GUARD)+STORAGE_SIZE,_GUARD,len(_GUARD))
        self.pointer=start+len(_GUARD)
        factory.quarantined=True
        if setup._invoke(None,self.base+factory.abi.constructor_rva,C.c_void_p,self.pointer)!=self.pointer:
            raise ValueError('Map argument constructor returned a different object')
        self._check_guard()
        if setup._qword(self.read,self.pointer)!=self.base+factory.abi.vtable_rva:
            raise ValueError('Map argument constructor returned an unknown provider')
        if setup._invoke(None,self.base+factory.abi.assign_rva,C.c_void_p,self.pointer,
                         (C.c_void_p,),source_pointer)!=self.pointer:
            raise ValueError('Map argument assignment returned a different object')
        self._check_guard()
        if (self.pointer==source_pointer or self.read(self.pointer+0x20,8)!=self.read(source_pointer+0x20,8)):
            raise ValueError('Map argument copy ownership/resolver differs')
        factory.live[self.pointer]=self
        factory.quarantined=False

    def snapshot(self):
        self.factory.check();self._check_guard()
        if self.factory.live.get(self.pointer) is not self:
            raise ValueError('Map argument is no longer owned')
        return self.factory.snapshot(self.pointer,names=True)

    def close(self):
        self.factory.check();self._check_guard()
        if self.factory.live.get(self.pointer) is not self:
            raise ValueError('Map argument ownership changed')
        self.factory.quarantined=True
        self._close_native()
        del self.factory.live[self.pointer]
        self.factory.quarantined=False


class OperationVectorArgument:
    """Owned transport for a borrowed XP2 operation vector."""

    def __init__(self, factory, pointer):
        self.factory = factory
        self._snapshot = snapshot_parameter_map(
            factory.base, pointer, factory.read, use_string_keys=True,
            core_sha256=XP2_CORE_SHA256, transport_version=2,
            allow_nested_maps=True, xp2_operation_vector=True)
        factory.live[id(self)] = self

    def snapshot(self):
        self.factory.check()
        if self.factory.live.get(id(self)) is not self:
            raise ValueError('Operation vector argument has been released')
        return self._snapshot

    def close(self):
        self.snapshot()
        del self.factory.live[id(self)]
        self._snapshot = None


MAP_ARGUMENT_TYPES = (ParameterMapArgument, OperationVectorArgument)


class MapArgumentFactory:
    def __init__(self, core, *, core_sha256, read=None):
        if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
            raise ValueError('Map argument copy engine is not source-qualified')
        from .script_map_argument_source import verify_xp1,verify_xp2
        self.base,self.abi=core._handle,configuration_abi(core_sha256)
        self.read=setup.local_reader() if read is None else read
        verifier=verify_xp2 if core_sha256==XP2_CORE_SHA256 else verify_xp1
        self.proof=verifier(self.base,self.read)
        self.thread,self.closed,self.quarantined=threading.get_ident(),False,False
        self.live={}

    def check(self):
        if self.thread!=threading.get_ident() or self.closed or self.quarantined:
            raise ValueError('Map argument owner is closed, quarantined or belongs to another thread')

    def snapshot(self,pointer,*,names,native_copy_budget=False):
        return snapshot_parameter_map(self.base,pointer,self.read,use_string_keys=names,
            core_sha256=self.abi.core_sha256,transport_version=2,allow_nested_maps=True,
            native_copy_budget=native_copy_budget)

    def __call__(self,pointer):
        self.check()
        if len(self.live)>=64:raise ValueError('Map argument owner limit exceeded')
        if (self.abi.core_sha256 == XP2_CORE_SHA256
                and setup._qword(self.read, pointer) == self.base + 0xabf918):
            return OperationVectorArgument(self, pointer)
        return ParameterMapArgument(self,pointer)

    def close(self):
        self.check()
        if self.live:raise ValueError('Live map arguments prevent factory closure')
        self.closed=True


def has_maps(arguments):
    return any(isinstance(value,MAP_ARGUMENT_TYPES) for value in arguments)


def argument_evidence(arguments):
    rows=[]
    for value in arguments:
        if isinstance(value,OperationVectorArgument):
            value.snapshot()
            rows.append({'type':'parameter_map','owned_native_clone':False,
                         'names_resolved_at_dispatch':False,'owned_transport_snapshot':True})
        elif isinstance(value,ParameterMapArgument):
            value.factory.check();value._check_guard()
            rows.append({'type':'parameter_map','owned_native_clone':True,'names_resolved_at_dispatch':True})
        else:
            item=pack_arguments((value,))[0]
            rows.append({'type':'boolean' if item.kind else 'uint32','raw':item.value})
    return {'arguments_typed':rows,'arguments_uint32':None}


class MapTransport(C.Structure):
    _fields_=[('ops',C.c_void_p),('count',C.c_uint32),('reserved',C.c_uint32)]


def pack_maps(arguments):
    if not 0<len(arguments)<=64:raise ValueError('Invalid map event argument count')
    packed=(HKSArgument*len(arguments))();maps=[];buffers=[];total=0
    for i,value in enumerate(arguments):
        if isinstance(value,MAP_ARGUMENT_TYPES):
            raw=value.snapshot().transport;count=len(raw)//16;total+=count
            if total>MAX_OPS:raise ValueError('Aggregate map argument transport budget exceeded')
            buffer=C.create_string_buffer(raw,len(raw));buffers.append(buffer)
            packed[i]=HKSArgument(2,len(maps));maps.append(MapTransport(C.addressof(buffer),count,0))
        else:packed[i]=pack_arguments((value,))[0]
    if not maps:raise ValueError('Map transport requires a map argument')
    return packed,(MapTransport*len(maps))(*maps),buffers


def require_map_transport(runtime):
    version=runtime.host.LAB_GameEventsMapArgumentVersion
    version.argtypes,version.restype=[],C.c_int
    if version()!=1:raise ValueError('Unknown native map event argument version')
    version=runtime.host.LAB_AuxMapTransportVersion
    version.argtypes,version.restype=[],C.c_int
    if version()!=2:raise ValueError('Map event arguments require A8 V2')
    return runtime.host.LAB_GameEventsDispatchMapsResult


def dispatch_maps(runtime,name,arguments,*,method,output_initial):
    dispatch=require_map_transport(runtime)
    packed,maps,buffers=pack_maps(arguments)
    dispatch.argtypes=[C.c_void_p,C.c_char_p,C.POINTER(HKSArgument),C.c_size_t,
        C.POINTER(MapTransport),C.c_size_t,C.c_uint,C.POINTER(C.c_uint8),C.POINTER(C.c_uint8)]
    dispatch.restype=C.c_int
    valid,output=C.c_uint8(0),C.c_uint8(output_initial)
    runtime._status(runtime.root,dispatch(runtime.root,name,packed,len(arguments),maps,len(maps),
        int(method=='TestAll'),C.byref(valid),C.byref(output)),'protected GameEvents map dispatch')
    if runtime.lua['gettop'](runtime.root):raise RuntimeError('Map event left a nonempty root stack')
    return bool(valid.value),output.value

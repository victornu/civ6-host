"""Bind the source-pinned scalar writer only during one XP2 deal-item edit."""

import ctypes as C
from hashlib import sha256
from pathlib import Path

from .configuration_profiles import _source
from .native.native_havok import bind as bind_havok
from .paths import resource_root
from .resource_resolution import resolve_path


FRONTIER = ('evidence/host-xp2-deal-resource-setter-auxiliary-frontier.json',
            'a320434cfce8accedda3a3cf2db18590345c5106081d86983e6e177c4156b825')
BUILD = ('work/xp2-deal-draft/value-bridge02/build.json',
         '6c3a2bc848481c243f6de7f8e7eefa5c1f047083cf95b4260abbed5ca4276309')
ARTIFACT = ('work/xp2-deal-draft/value-bridge02/xp2-deal-value.dll',
            '5d482b8ac6778419fa0235abdfbedb63f35a9e6f5cb40731f4271ffd2c8e4d55')
SOURCE = ('work/xp2-deal-draft/value-bridge02/xp2_deal_value_bridge.c',
          'd4bbb723cb0cad6d7b28980abda31266bc038fcc014c2739cbf02e60f9417b75')
SLOT = 0xb8


def _path(reference):
    return resolve_path(resource_root()/reference[0]).resolve()


def dependencies():
    if not _path(ARTIFACT).is_file():
        return {}
    receipt = _source(BUILD)
    if receipt['schema'] != 'civ6-host.xp2-deal-value-bridge.build.v1' or receipt['gamecore_loaded'] is not False:
        raise ValueError('Unknown XP2 deal value bridge build')
    for name, reference in (('source',SOURCE),('artifact',ARTIFACT)):
        row = receipt[name]
        path = _path(reference)
        if (resolve_path(Path(row['path'])).resolve() != path or row['sha256'] != reference[1]
                or not 0 < path.stat().st_size == row['bytes'] <= 1024**2
                or sha256(path.read_bytes()).hexdigest() != reference[1]):
            raise ValueError('XP2 deal value bridge input or artifact changed')
    return {str(_path(reference)): reference[1] for reference in (FRONTIER, BUILD, ARTIFACT, SOURCE)}


def bind(saved, *, image_sha256):
    if not dependencies():
        return None
    proof = _source(FRONTIER)
    call = proof['call']
    if (proof['schema'] != 'civ6-host.xp2-resource-setter-auxiliary.v1'
            or proof['gamecore_sha256'] != image_sha256 or call['lua_method'] != 'SetValueType'
            or call['slot'] != SLOT or call['return_rva'] != 0x6d1063
            or call['resource_index_stack_slot'] != 2 or call['caller_initializes_variant'] is not True):
        raise ValueError('Unknown XP2 deal value producer')
    base = saved.backend.core._handle
    for span in proof['spans']:
        raw = saved.backend.runtime.read(base + span['rva'],span['size'])
        if type(raw) is not bytes or len(raw) != span['size'] or sha256(raw).hexdigest()!=span['sha256']:
            raise ValueError('Live XP2 deal value producer changed')
    return DealValueWriter(saved.prefix,base,C.WinDLL(str(_path(ARTIFACT))))


class DealValueWriter:
    def __init__(self, prefix, base, library):
        self.prefix, self.base, self.library = prefix, base, library
        runtime = prefix.runtime
        self.host = prefix.deferred_events.host
        if runtime.service_owner is not self.host:
            raise RuntimeError('Foreign XP2 deal value auxiliary owner')
        self.owner = C.addressof(self.host.aux_object)
        self.slot_key = (C.addressof(self.host.aux_vtable),SLOT)
        self.previous = self.host._slot_bindings[self.slot_key]
        if not self.previous[0] or self.host.aux_vtable[SLOT//8] != self.previous[0]:
            raise RuntimeError('Unowned XP2 deal value auxiliary slot')
        api = bind_havok(runtime.library,shared_dependency_profile=runtime.shared_dependency_profile)
        self.havok = tuple(C.cast(api[name],C.c_void_p).value for name in ('gettop','type','tonumber'))
        self.begin = library.LAB_DealValueBegin
        self.begin.argtypes, self.begin.restype = [C.c_void_p]*6+[C.c_uint32], C.c_int
        self.end = library.LAB_DealValueEnd
        self.end.argtypes, self.end.restype = [C.c_void_p]*2, C.c_int
        target = library.LAB_DealValueWrite
        self.installed = (C.cast(target,C.c_void_p).value,target)

    def evaluate(self, code, index):
        if type(index) is not int or not 0 <= index <= 0x7fffffff:
            raise ValueError('Invalid expected XP2 deal type index')
        runtime, child = self.prefix.runtime, self.prefix.ui_child
        state = runtime.registry.validate(child)
        host = self.host
        if (runtime.service_owner is not host or host.aux_vtable[SLOT//8]!=self.previous[0]
                or host._slot_bindings[self.slot_key]!=self.previous
                or self.begin(self.base,self.owner,state,*self.havok,index)!=1):
            raise RuntimeError('XP2 deal value scope could not begin')
        host.aux_vtable[SLOT//8] = self.installed[0]
        host._slot_bindings[self.slot_key] = self.installed
        try:
            result = runtime.evaluate_text(child,code,b'@xp2_edit_deal_resource_type',capacity=64)
        finally:
            intact = (host.aux_vtable[SLOT//8]==self.installed[0]
                      and host._slot_bindings.get(self.slot_key)==self.installed)
            if intact:
                host.aux_vtable[SLOT//8] = self.previous[0]
                host._slot_bindings[self.slot_key] = self.previous
            calls = self.end(self.owner,state)
            if not intact or calls not in (0,1):
                raise RuntimeError('XP2 deal value auxiliary scope was not restored')
        if result == b'edited' and calls != 1:
            raise RuntimeError('GameCore did not convert the selected resource type')
        return result,calls

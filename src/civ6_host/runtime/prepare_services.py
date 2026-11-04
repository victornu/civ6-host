"""Prepare callback mechanics; registries and allocation remain shared owners.

This adapter validates ordered engine declarations and counts archive calls.
It deliberately delegates the EXE algorithms to the retained DiagnosticHost.
Callbacks stay installed through native destruction, which owns their removal.
"""
from __future__ import annotations

import ctypes as C


def _retained(host, table, offset, callback=None):
    pointer = int(table[offset//8] or 0)
    retained = {int(C.cast(fn,C.c_void_p).value or 0) for fn in host.functions}
    binding = getattr(host,'_slot_bindings',{}).get((C.addressof(table),offset))
    if (not pointer or pointer not in retained or binding is None or binding[0] != pointer
            or (callback is not None and binding[1] != callback)):
        raise ValueError('Prepare callback pointer/owner is not retained')
    return pointer


def require_host(host):
    from .native.native_host import DiagnosticHost, ArchiveRegistry, TypeRegistry, BOOTSTRAP_TYPE_NAMES
    if (type(host) is not DiagnosticHost or type(host.archives) is not ArchiveRegistry
            or type(host.types) is not TypeRegistry
            or host.types.allowed_names != BOOTSTRAP_TYPE_NAMES
            or not isinstance(host.functions,list)):
        raise ValueError('Prepare requires the shared owned DiagnosticHost registries')
    for name in ('_bind','_copy_type_name','_register_type','_remove_type','_registrar',
                 '_descriptor_context','_archive_register','_archive_remove','_tuner_unavailable'):
        bound = getattr(host,name,None)
        if getattr(bound,'__self__',None) is not host or getattr(bound,'__func__',None) is not getattr(DiagnosticHost,name):
            raise ValueError('Prepare shared callback implementation was replaced: '+name)
    for object_name,table_name in (('object','vtable'),('aux_object','aux_vtable'),
            ('logger_object','logger_vtable'),('registrar_object','registrar_vtable'),
            ('descriptor_object','descriptor_vtable')):
        obj,table = getattr(host,object_name),getattr(host,table_name)
        if int(obj[0] or 0) != C.addressof(table):
            raise ValueError('Prepare host interface layout differs: '+object_name)
    if getattr(host,'_prepare_services',None) is not None or host.types.entries or host.archives.entries:
        raise ValueError('Prepare requires fresh type/archive registries')
    for table,offset,callback in ((host.vtable,0x110,host._registrar),
            (host.registrar_vtable,8,host._remove_type),(host.registrar_vtable,0,None),
            (host.vtable,0x108,None),(host.descriptor_vtable,0,None),(host.descriptor_vtable,8,None)):
        _retained(host,table,offset,callback)


class PrepareServices:
    """One source-selected registry installation on one retained host."""

    def __init__(self, host, base, *, contract):
        require_host(host)
        self.host, self.base, self.contract = host, base, contract
        self.names, self.pairs = contract['type_names'], contract['callback_rvas']
        if type(base) is not int or not 0 < base < (1<<47)-0x1000000:
            raise ValueError('Invalid Prepare module base')
        self.count = 0
        self.getter_calls = self.register_calls = self.remove_calls = 0
        self.accepted_calls = self.rejected_calls = 0
        self.entered = False
        self.phase = 'installed'
        self.installed = False
        # Preserve these exact bound methods, never a substitute registry model.
        self._register = host._register_type
        self._get_archive = host._descriptor_context
        self._register_archive = host._archive_register
        self._remove_archive = host._archive_remove
        changes = ((host.registrar_vtable,0,None,[C.c_void_p]*4,self.register_type),
                   (host.vtable,0x108,C.c_void_p,[C.c_void_p],self.get_archive),
                   (host.descriptor_vtable,0,C.c_bool,[C.c_void_p]*2,self.register_archive),
                   (host.descriptor_vtable,8,None,[C.c_void_p]*2,self.remove_archive))
        tables = (host.vtable,host.registrar_vtable,host.descriptor_vtable,host.aux_vtable,host.logger_vtable)
        snapshots = {C.addressof(t):tuple(int(p or 0) for p in t) for t in tables}
        old_bindings = dict(host._slot_bindings)
        try:
            for table,offset,result,args,callback in changes:
                host._bind(table,offset,result,args,callback)
            allowed = {(C.addressof(t),offset//8) for t,offset,*_ in changes}
            for table in tables:
                address = C.addressof(table)
                if any(int(p or 0) != snapshots[address][i] for i,p in enumerate(table)
                       if (address,i) not in allowed):
                    raise ValueError('Prepare installation modified an unrelated callback slot')
            self.callbacks = tuple((table,offset,callback,_retained(host,table,offset,callback))
                                   for table,offset,_,_,callback in changes)
        except BaseException:
            for table in tables:
                for index,value in enumerate(snapshots[C.addressof(table)]):
                    table[index] = value
            host._slot_bindings = old_bindings
            raise
        self.remove_type_pointer = _retained(host,host.registrar_vtable,8,host._remove_type)
        self.registrar_pointer = _retained(host,host.vtable,0x110,host._registrar)
        self.installed = True
        host._prepare_services = self

    def verify_callbacks(self):
        if self.host._prepare_services is not self or not self.installed:
            raise ValueError('Prepare services lost their retained owner')
        for table,offset,callback,pointer in self.callbacks:
            if _retained(self.host,table,offset,callback) != pointer:
                raise ValueError('Prepare callback changed after installation')
        if (_retained(self.host,self.host.registrar_vtable,8,self.host._remove_type) != self.remove_type_pointer
                or _retained(self.host,self.host.vtable,0x110,self.host._registrar) != self.registrar_pointer):
            raise ValueError('Prepare registrar cleanup/getter changed')

    def register_type(self, this, descriptor, first, second):
        if not self.entered:
            raise ValueError('Type declaration outside Prepare dispatch')
        if this != C.addressof(self.host.registrar_object) or self.count >= len(self.names):
            raise ValueError('Prepare type declaration owner/count differs')
        _,name = self.host._copy_type_name(descriptor)
        pair = tuple(self.base+rva for rva in self.pairs[self.count])
        if name != self.names[self.count] or type(first) is not int or type(second) is not int or (first,second) != pair:
            raise ValueError('Prepare type name/callback differs from selected order')
        self._register(this,descriptor,first,second)
        from .native.native_host import type_name_hash
        if self.host.types.entries.get(type_name_hash(name)) != (name,*pair):
            raise ValueError('Shared TypeRegistry did not retain its verified declaration')
        self.count += 1

    def get_archive(self, this):
        self.getter_calls += 1
        return self._get_archive(this)

    def register_archive(self, this, descriptor):
        self.register_calls += 1
        result = self._register_archive(this,descriptor)
        if type(result) is not bool:
            raise TypeError('Shared ArchiveRegistry must preserve its bool result')
        self.accepted_calls += int(result)
        self.rejected_calls += int(not result)
        return result

    def remove_archive(self, this, descriptor):
        self.remove_calls += 1
        return self._remove_archive(this,descriptor)

    def require_complete(self):
        self.verify_callbacks()
        if self.count != len(self.names) or len(self.host.types.entries) != len(self.names):
            raise ValueError('Prepare returned before all ten ordered type declarations')
        return self.receipt()

    def receipt(self):
        return dict(schema='civ6-host.prepare-services.v1', installed=self.installed,
            source=self.contract['receipt'], phase=self.phase, registered_type_count=self.count,
            expected_type_count=len(self.names), type_names=list(self.names),
            next_expected_type=self.names[self.count] if self.count<len(self.names) else None,
            type_callback_functions_invoked=False, archive_getter_calls=self.getter_calls,
            archive_register_calls=self.register_calls, archive_remove_calls=self.remove_calls,
            archive_accepted_calls=self.accepted_calls, archive_rejected_calls=self.rejected_calls,
            archive_entries=[dict(key=k,pointer=p) for k,p in sorted(self.host.archives.entries.items())],
            active_byte_written_by_host=False, saved_game_loaded=False, eligible_for_training=False)

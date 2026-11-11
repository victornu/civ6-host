"""Restore the source-proven shared HOST+78 callback after XP1 Init masking."""
import ctypes as C
import hashlib

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source, _body

SOURCE = ('work/host-extensions/xp1-slot78-static/slot78-source-v1.json',
          '85062d8783c19f0af4a8235d44c49c8a7d6121f9eefc0d0d22d81466864b96cc')
ADAPTER_COMPATIBILITY = ('work/host-extensions/xp2-turn-static/host78-adapter-compatibility-v1.json',
                        'd496cfec9c33cd5349991514e2ca32b1536be0b04151041f0d745ee0a0f6da09')


def _adapter_references(original):
    """Preserve the old pin; join only the proven unchanged DiagnosticHost."""
    from pathlib import Path
    from .native import native_host
    current=Path(native_host.__file__).resolve()
    actual=hashlib.sha256(current.read_bytes()).hexdigest()
    if actual==original['sha256']:return (original,)
    proof=_source(ADAPTER_COMPATIBILITY)
    if (proof['schema']!='civ6-host.host78-adapter-compatibility.v1'
            or proof['native_execution'] is not False
            or proof['prior_host_sha256']!=original['sha256']
            or Path(proof['current_host']['path']).resolve()!=current
            or proof['exact_diagnostic_host_class_unchanged'] is not True):
        raise ValueError('HOST78 shared callback adapter changed')
    if proof['current_host']['sha256'] == actual:
        return (dict(path=ADAPTER_COMPATIBILITY[0],sha256=ADAPTER_COMPATIBILITY[1]),
                proof['current_host'],proof['archive'])
    from .execution_images import _XP1_PROFILE
    from .xp1_session_inputs import CURRENT_XP1_SESSION_JOIN, current_session_join
    join = current_session_join(_XP1_PROFILE)
    reviewed = join['host78']
    if (reviewed['previous'] != original['sha256']
            or reviewed['current']['sha256'] != actual
            or Path(reviewed['current']['path']).resolve() != current
            or reviewed['diagnostic_host_unchanged'] is not True
            or join['archive'] != proof['archive']):
        raise ValueError('HOST78 shared callback adapter changed')
    return (dict(path=CURRENT_XP1_SESSION_JOIN[0], sha256=CURRENT_XP1_SESSION_JOIN[1]),
            reviewed['current'], join['archive'])


def verify_source(*, core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import source
        return source()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown HOST78 source engine')
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6_host.xp1_host_slot78.static.v1'
            or proof['xp1_sha256'] != XP1_CORE_SHA256
            or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or proof['native_execution'] is not False
            or proof['abi'] != 'uint32 __fastcall(void *host, uint32 key)'
            or proof['host_global_rva'] != 0x9f2640
            or tuple(proof['call_rvas']) != (0x409de,0x40a22)
            or tuple(proof['key_values']) != (0x4fc6296a,0x715c87d1)
            or dict(proof['callback']) != dict(rva=0x9744b0,body_hex='33c0c3',result=0,
                reads_receiver=False,reads_key=False,side_effects=False,caller_reads_result=False)):
        raise ValueError('XP1 HOST+78 source identity changed')
    original = _source((proof['shared_exe_source']['path'],proof['shared_exe_source']['sha256']))
    if (original['slot_bytes'] != 'b044974001000000'
            or ''.join(row['bytes'] for row in original['callback']['instructions']) != '33c0c3'):
        raise ValueError('Shared EXE HOST+78 callback changed')
    rows = {int(row['va'],16)-0x180000000: row
            for fragment in _body(proof['xp1_consumer'])['fragments'] for row in fragment['instructions']}
    if any(rows[rva]['bytes'] != 'ff5078' for rva in proof['call_rvas']):
        raise ValueError('XP1 HOST+78 consumer ABI changed')
    return proof


def source_dependencies(*, core_sha256=XP1_CORE_SHA256, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import source_dependencies as selected
        return selected(execution_image=execution_image)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown HOST78 source engine')
    if execution_image is not None:raise ValueError('XP1 HOST78 does not accept an XP2 execution image')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    proof = verify_source()
    pins = {}
    # This row describes the historical mask, not today's executed helper.
    # Its exact old bytes remain in the immutable source archive. Installation
    # independently requires the current slot to retain its actual fatal owner.
    masking=proof['masking_source']
    original_path=resolve_path(resource_root()/masking['path']).resolve()
    if hashlib.sha256(original_path.read_bytes()).hexdigest()!=masking['sha256']:
        compat=_source(ADAPTER_COMPATIBILITY)
        masking=compat['historical_masking_source']
        if masking['sha256']!=proof['masking_source']['sha256']:
            raise ValueError('HOST78 historical masking source changed')
    for row in (dict(path=SOURCE[0],sha256=SOURCE[1]),proof['shared_exe_source'],
                *_adapter_references(proof['shared_adapter']),masking,proof['refused_native_witness']):
        path=resolve_path(resource_root()/row['path']).resolve()
        raw=path.read_bytes()
        if (hashlib.sha256(raw).hexdigest()!=row['sha256']
                or 'bytes' in row and len(raw)!=row['bytes']):
            raise ValueError('XP1 HOST+78 dependency changed: '+str(path))
        pins[str(path)]=row['sha256']
    return pins


def verify_live(base, read, host_pointer, *, core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import verify_live as selected
        return selected(base,read,family='slot78',host_pointer=host_pointer)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown HOST78 source engine')
    from .xp1_status_profiles import _instruction_spans
    if (type(base) is not int or base<=0 or not callable(read)
            or type(host_pointer) is not int or host_pointer<=0):
        raise ValueError('XP1 HOST+78 requires exact module/host identities')
    proof=verify_source()
    flat={'functions':{'consumer':{'instructions':[row
          for fragment in _body(proof['xp1_consumer'])['fragments'] for row in fragment['instructions']]}}}
    spans=_instruction_spans(flat)
    for rva,raw in spans:
        if read(base+rva,len(raw))!=raw:
            raise ValueError('XP1 HOST+78 instruction mismatch at '+hex(rva))
    if read(base+proof['host_global_rva'],8)!=host_pointer.to_bytes(8,'little'):
        raise ValueError('XP1 HOST+78 references another host')
    return len(spans)


def install(backend):
    from .native.native_host import DiagnosticHost
    backend.check_thread()
    host=backend.host
    core_sha256=backend.load_abi.core_sha256
    if (getattr(backend,'_saved_load_candidate',False) is not True
            or core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
            or backend.stage!='prepared' or backend.prefix is not None
            or backend.busy is not True or backend.poisoned or backend.destroyed
            or hasattr(backend,'_xp1_slot78') or not isinstance(host,DiagnosticHost)):
        raise ValueError('HOST+78 requires the exclusive prepared XP1 owner')
    reference=SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import SOURCE as reference,require_prepared_owner
        require_prepared_owner(backend)
    execution_image = getattr(backend.core, '_civ6_host_execution_image', None)
    source_dependencies(core_sha256=core_sha256,
                        **({'execution_image': execution_image} if core_sha256 == XP2_CORE_SHA256 else {}))
    spans=verify_live(backend.core._handle,backend.runtime.read,host.pointer,core_sha256=core_sha256)
    previous=host._slot_bindings.get((C.addressof(host.vtable),0x78))
    callback=host._constant_zero_slot78
    if (previous is None or previous[0]!=host.vtable[0x78//8]
            or getattr(previous[1],'_native_unavailable',None)!=('host',0x78)
            or getattr(callback,'__func__',None) is not DiagnosticHost._constant_zero_slot78):
        raise ValueError('HOST+78 already has a foreign or admitted callback')
    host._bind(host.vtable,0x78,C.c_uint32,[C.c_void_p,C.c_uint32],callback)
    receipt=dict(source_sha256=reference[1],core_sha256=core_sha256,
        shared_callback_rva='0x9744b0',slot='0x78',callback_pointer=host.vtable[0x78//8],
        source_instruction_spans=spans,constant_is_official_callback_body=True,
        unknown_service_fallback=False)
    backend._xp1_slot78=(host,callback,receipt)
    backend.emit('xp1_host_slot78_installed',**receipt)
    return receipt


# Required by the source-qualified current saved-Load/first-turn composition.
# This is a binding completeness check, never a new callback allowlist.
REQUIRED = {
    'host': ('vtable',(0x00,0x08,0x10,0x18,0x30,0x38,0x40,0x48,0x58,0x60,0x70,0x78,
        0x98,0xA0,0xB0,0xC0,0xD0,0xE8,0xF0,0x108,0x110,0x120,0x130,0x138,0x140,0x158,0x168)),
    'auxiliary': ('aux_vtable',(0x00,0x08,0x18,0x20,0x28,0x30,0x40,0x48,0x60,0x80,0x90,0xD0,0xD8)),
    'logger': ('logger_vtable',(0x10,0x18,0x20,0x28,0x38,0x40,0x50)),
    'type registrar': ('registrar_vtable',(0x00,0x08)),
    'autoarchive registry': ('descriptor_vtable',(0x00,0x08)),
}


def require_composed_callbacks(backend, services):
    """Inspect actual retained entries after all masks and installers.

Does not invoke callbacks, change a slot, or assert semantic qualification from
pointer presence. Existing source-selected owners remain the authority for ABI.
"""
    from .saved_load_services import SavedLoadServices
    backend.check_thread()
    host=backend.host
    core_sha256=backend.load_abi.core_sha256
    if (type(services) is not SavedLoadServices or services.backend is not backend
            or services.host is not host or host._saved_load_services is not services
            or core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
            or backend.stage!='prepared' or backend.prefix is not None
            or backend.busy is not True or backend.destroyed or backend.poisoned
            or services.closed or services.quarantined
            or getattr(backend,'_xp1_commands_requested',False) is not True):
        raise ValueError('Composed callback audit requires the final prepared command services')
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import require_prepared_owner
        require_prepared_owner(backend)
        if (services.core is not backend.core or services.context!=backend.context
                or services.core_sha256!=core_sha256):
            raise ValueError('Composed XP2 callback audit has a foreign service owner')
    from .control_input_source import reactivation_profile
    has_reactivation=reactivation_profile(backend.core) is not None
    result={}
    for interface,(name,slots) in REQUIRED.items():
        if interface=='host':
            if core_sha256==XP2_CORE_SHA256:
                slots=tuple(sorted((*slots,0x20)))
            if has_reactivation:
                slots=tuple(sorted((*slots,0x68)))
        table=getattr(host,name);entries=[]
        for slot in slots:
            binding=host._slot_bindings.get((C.addressof(table),slot))
            if (binding is None or not binding[0] or binding[0]!=table[slot//8]
                    or not callable(binding[1]) or getattr(binding[1],'_native_unavailable',None) is not None):
                raise ValueError('Required composed callback remains unavailable: '+interface+'+'+hex(slot))
            entries.append(dict(slot=hex(slot),callback_module=binding[1].__module__,
                callback_name=binding[1].__qualname__,retained_binding_matches=True))
        result[interface]=entries
    # Scalar/map callbacks are installed as exact compiled C function addresses;
    # their old _slot_bindings entries intentionally retain the revoked Python
    # callbacks. Verify the explicit owners and addresses, not those stale rows.
    scalar=services.scalars;maps=services.maps
    if (host._scalar_service_owner is not scalar or scalar.host is not host or scalar.closed
            or host.aux_vtable[0xA0//8]!=scalar.address
            or C.cast(scalar.function,C.c_void_p).value!=scalar.address
            or host._map_service_owner is not maps or maps.host is not host or maps.closed):
        raise ValueError('Composed native scalar/map owner changed')
    native=[dict(slot='0xa0',export='LAB_AuxPushVariant',retained_native_owner_matches=True)]
    if tuple(row[0] for row in maps.bindings)!=(0xA8,0xB0):
        raise ValueError('Composed map callback group changed')
    for slot,address,previous,function in maps.bindings:
        if not address or host.aux_vtable[slot//8]!=address or C.cast(function,C.c_void_p).value!=address:
            raise ValueError('Composed native map callback replaced')
        native.append(dict(slot=hex(slot),export='LAB_AuxPushMap' if slot==0xA8 else 'LAB_AuxPushOptionalMap',
                           retained_native_owner_matches=True))
    receipt=dict(schema='civ6-host.xp1-composed-callbacks.v1',core_sha256=core_sha256,
        retained_callbacks=result,native_auxiliary_callbacks=native,
        callback_count=sum(len(rows) for rows in result.values())+len(native),
        checked_after_context_mask_and_service_composition=True,
        callbacks_invoked=False,callbacks_installed=False,semantic_qualification_inferred=False)
    backend.emit('xp1_composed_callbacks_verified',**receipt)
    return receipt

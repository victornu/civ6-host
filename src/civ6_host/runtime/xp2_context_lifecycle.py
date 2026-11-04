"""Private Gathering Storm Init/Destroy adapter over the shared mechanics.

No public saved-session admission follows from selecting this adapter. Only the
registered official XP2 captured input owner may reach its native Init call.
"""
import ctypes as C
from . import context_initialization as shared
from .saved_load_profiles import XP2_CORE_SHA256


class XP2ContextInitError(RuntimeError):
    def __init__(self, receipt, message):
        super().__init__(message)
        self.receipt = receipt


def initialize_xp2_context(core, context, host, *, configuration_path,
        gameplay_path, private_root, module_paths, emit=None, candidate_bundle=None):
    from .native.native_core_context_profiles import (
        profile_for_core, validate_loaded_context, validate_loaded_modules)
    from .native.native_xp1_context_init import validate_private_inputs, _native_reader
    from .native.native_host import virtual
    from .xp2_context_profile import verify_source, verify_live
    if candidate_bundle is None:
        raise ValueError('XP2 Init requires its registered captured input owner')
    profile = profile_for_core(core._name, mode='context')
    if (profile.ruleset != 'xp2' or profile.mode != 'context'
            or profile.core_sha256 != XP2_CORE_SHA256):
        raise ValueError('XP2 Init refuses a different engine/context profile')
    validate_loaded_modules(profile, module_paths)
    contract = verify_source()
    verify_live(core._handle, _native_reader, contract)
    callbacks = shared.restrict_callbacks(host,
        host_slots=contract['host_slots'], auxiliary_slots=(),
        logger_slots=contract['logger_slots'])
    inputs = validate_private_inputs(host, configuration_path, gameplay_path,
        private_root, candidate_bundle=candidate_bundle, candidate_family='xp2-lan')
    inputs['host_callbacks_allowlist'] = [
        'host+' + hex(n) for n in contract['host_slots']
    ] + ['logger+' + hex(n) for n in contract['logger_slots']]
    return shared.initialize(core, context, host, profile=profile,
        source=contract['receipt'], input_receipt=inputs, callback_receipt=callbacks,
        slots=contract['slots'], globals_rvas=contract['globals_rvas'],
        declarations=contract['declarations'], vtable_bytes=contract['vtable_bytes'],
        context_validator=validate_loaded_context, virtual_factory=virtual,
        read=_native_reader, emit=emit, error_type=XP2ContextInitError)


def install_xp2_teardown_callbacks(core, context, host, init_receipt, *,
        module_paths, emit=None, candidate_bundle=None):
    """Install source-selected registrar cleanup, never invoke Destroy here."""
    import struct
    from .xp2_context_profile import verify_source, verify_live
    from .xp2_saved_init import validate_init_receipt_binding
    from .native.native_core_context_profiles import (profile_for_core,
        validate_loaded_context, validate_loaded_modules)
    from .native.native_xp1_context_init import _native_reader
    from .native.native_xp1_teardown_adapter import (_check_host,
        _default_owner_verifier, _aligned_free_callable)
    from .native.native_host import virtual
    if candidate_bundle is None or getattr(host,'_xp2_teardown_binding',None)is not None:
        raise ValueError('XP2 teardown needs a fresh exact captured Init owner')
    _check_host(host)
    profile=profile_for_core(core._name,mode='context')
    if profile.ruleset!='xp2' or profile.core_sha256!=XP2_CORE_SHA256:
        raise ValueError('XP2 teardown engine differs')
    validate_loaded_modules(profile,module_paths)
    validate_loaded_context(profile,core._handle,context,_native_reader)
    contract=verify_source()
    verify_live(core._handle,_native_reader,contract)
    if (getattr(host,'context_init_receipt',None)is not init_receipt
            or init_receipt['schema']!='civ6rl.native_xp2_context_init_receipt.v1'
            or init_receipt['status']!='xp2_context_initialized_diagnostic_only'
            or init_receipt['core_sha256']!=XP2_CORE_SHA256
            or any(init_receipt.get(k)is not True for k in
                   ('init_called','init_returned','initialized_after','host_setter_called'))
            or any(init_receipt.get(k)is not False for k in
                   ('game_created','newgame_called','prepare_called','eligible_for_training'))
            or init_receipt['source']!=contract['receipt']):
        raise ValueError('XP2 teardown refuses a failed or different-scope Init')
    validate_init_receipt_binding(candidate_bundle,host,init_receipt)
    declarations=shared.require_declarations(host,contract['declarations'])
    if declarations!=init_receipt['event_filter_declarations']:
        raise ValueError('XP2 teardown event owner differs from Init')
    actual=shared.require_installed_globals(core,host,_native_reader,contract['globals_rvas'])
    if virtual(core,context,0x38,contract['slots'][0x38],C.c_bool)(context)is not True:
        raise ValueError('XP2 teardown requires the initialized native context')
    inner=struct.unpack('<Q',_native_reader(context+8,8))[0]
    if struct.unpack('<Q',_native_reader(inner+96,8))[0]!=0:
        raise ValueError('XP2 Init-only teardown refuses a prepared/loaded Game')
    free_address=struct.unpack('<Q',_native_reader(core._handle+contract['aligned_free_iat_rva'],8))[0]
    if not free_address:raise ValueError('XP2 aligned-free import is null')
    owner=_default_owner_verifier(free_address,module_paths)
    host.native_aligned_free=_aligned_free_callable(free_address)
    host._bind(host.registrar_vtable,8,None,[C.c_void_p,C.c_void_p],host._remove_type)
    host._bind(host.vtable,0x110,C.c_void_p,[C.c_void_p],host._registrar)
    receipt=dict(schema='civ6-host.xp2-context-teardown-installation.v1',installed=True,
        core_sha256=XP2_CORE_SHA256,source=contract['receipt'],
        host_globals_verified=actual,type_names_allowed=list(contract['teardown_names']),
        host_slot='0x110',registrar_remove_slot='0x8',aligned_free_iat_rva=hex(contract['aligned_free_iat_rva']),
        aligned_free_runtime_owner=owner,callback_references_retained=True,
        destroy_called=False,game_created=False,saved_load_admitted=False)
    host._xp2_teardown_binding=receipt
    if emit:emit('xp2_teardown_adapter_installed',receipt=receipt)
    return receipt

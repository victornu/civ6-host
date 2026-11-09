"""Private XP2 Prepare composition over shared EXE registry/localization code.

Selecting this entry does not admit saved Load or a complete Gathering Storm
session. The only supported Tuner mode is the explicit unavailable diagnostic.
"""
from __future__ import annotations

import ctypes as C

from . import xp2_prepare_source as source
from .prepare_services import PrepareServices, require_host, _retained
from .saved_load_profiles import XP2_CORE_SHA256


class XP2PrepareError(RuntimeError):
    def __init__(self, receipt, message):
        super().__init__(message)
        self.receipt = receipt


def require_null_tuner_diagnostic(host, enabled):
    if enabled is not True or getattr(host,'tuner_unavailable_probe',False) is not True:
        raise ValueError('XP2 Prepare requires explicit NULL Tuner diagnostic admission')
    contract = source.verify_source()
    _retained(host,host.aux_vtable,0,host._tuner_unavailable)
    return dict(proof_sha256=source.SOURCE[1], scope='Prepare/Destroy only',
                gameplay_optional_proven=False, eligible_for_training=False,
                cleanup_helper_rva=contract['proof']['null_tuner']['cleanup_helper_rva'])


def _require_lifecycle(core, host, contract, live, profile):
    from .context_initialization import require_declarations
    from .xp2_saved_init import validate_context_receipt_engine_identity
    if getattr(core,'_diagnostic_host',None) is not host:
        raise ValueError('XP2 Prepare requires the core retained host owner')
    init = getattr(host,'context_init_receipt',None)
    teardown = getattr(host,'context_teardown_receipt',None)
    try:
        validate_context_receipt_engine_identity(profile, init)
        validate_context_receipt_engine_identity(profile, teardown)
    except ValueError as exc:
        raise ValueError('XP2 Prepare Init/teardown actual/reference identities differ') from exc
    if (type(init) is not dict or type(teardown) is not dict
            or getattr(host,'_xp2_teardown_binding',None) is not teardown
            or getattr(host,'_xp1_teardown_binding',None) is not None
            or init.get('schema') != 'civ6rl.native_xp2_context_init_receipt.v1'
            or init.get('status') != 'xp2_context_initialized_diagnostic_only'
            or init.get('source') != contract['bootstrap']['receipt']
            or any(init.get(k) is not True for k in ('init_called','init_returned','initialized_after','host_setter_called'))
            or any(init.get(k) is not False for k in ('game_created','newgame_called','prepare_called','eligible_for_training'))
            or init.get('inputs',{}).get('captured_input_binding',{}).get('input_profile') != 'xp2-lan'
            or getattr(host,'manifest',{}).get('input_profile') != 'xp2-lan'
            or teardown.get('schema') != 'civ6-host.xp2-context-teardown-installation.v1'
            or teardown.get('source') != contract['bootstrap']['receipt']
            or teardown.get('installed') is not True
            or teardown.get('callback_references_retained') is not True
            or any(teardown.get(k) is not False for k in ('destroy_called','game_created','saved_load_admitted'))
            or tuple(teardown.get('type_names_allowed',())) != contract['type_names']
            or teardown.get('host_slot') != '0x110' or teardown.get('registrar_remove_slot') != '0x8'
            or teardown.get('aligned_free_iat_rva') != hex(contract['engine']['aligned_free_iat_rva'])
            or teardown.get('host_globals_verified') != live['host_globals']
            or init.get('host_globals_after_set') != live['host_globals']):
        raise ValueError('XP2 Prepare Init/teardown receipt does not own this live context')
    if require_declarations(host,contract['bootstrap']['declarations']) != init.get('event_filter_declarations'):
        raise ValueError('XP2 Prepare event declaration owner differs from Init')


def prepare(core, context, host, profile, emit, *, null_tuner_diagnostic=False):
    """Install the source-qualified group and enter native Prepare exactly once.

The caller must retain the initialized host and enable its explicit unavailable
Tuner probe after Init. Other required service families must already be bound.
Unknown callbacks remain fatal. The caller retains native teardown ownership.
"""
    from .native.native_core_context_profiles import profile_for_core, validate_loaded_modules
    from .native.native_core_context_profiles import require_executable_profile
    from .native.native_xp1_teardown_adapter import _default_owner_verifier
    from .native.native_localization import initialize_localization
    from .native.native_probe import Windows
    from .native.native_setup import local_reader
    from .native.native_host import virtual

    actual = profile_for_core(core._name,mode='context',
        shared_dependency_directory=host.dll_directory,
        execution_image=getattr(core,'_civ6_host_execution_image',None))
    require_executable_profile(profile)
    if profile.execution_image is not getattr(core,'_civ6_host_execution_image',None):
        raise ValueError('XP2 Prepare profile differs from the retained execution identity')
    if profile != actual or (profile.ruleset,profile.mode,profile.source_core_sha256) != ('xp2','context',XP2_CORE_SHA256):
        raise ValueError('XP2 Prepare requires the exact initialized engine profile')
    if getattr(host,'_xp2_prepare_entered',False) or getattr(host,'_xp1_prepare_entered',False):
        raise ValueError('Expansion Prepare has already been entered')
    require_host(host)
    diagnostic = require_null_tuner_diagnostic(host,null_tuner_diagnostic)
    contract = source.verify_source()
    modules = Windows().modules()
    validate_loaded_modules(profile,modules)
    read = local_reader()
    live = source.verify_live(core._handle,context,host,read,contract)
    _require_lifecycle(core,host,contract,live,profile)
    owner = _default_owner_verifier(live['free_address'],modules)
    if owner != host.context_teardown_receipt['aligned_free_runtime_owner']:
        raise ValueError('XP2 Prepare allocator runtime module owner changed')
    services = PrepareServices(host,core._handle,contract=contract)
    host._xp2_prepare_services = services
    from .xp2_saved_init import context_receipt_engine_fields
    receipt = dict(schema='civ6-host.xp2-prepare.v1',status='installed',
        source=contract['receipt'],**context_receipt_engine_fields(profile),
        core_base=hex(core._handle),context_pointer=hex(context),inner_pointer=hex(live['inner']),
        null_tuner_diagnostic=diagnostic,prepare_entered=False,prepare_returned=False,
        services_nonnull=False,saved_game_loaded=False,game_created=False,
        allocated_game_object=False,game_initialized=False,
        eligible_for_training=False,complete_host_contract_verified=False)
    host._xp2_prepare_receipt = receipt
    phase = 'localization'
    try:
        emit('xp2_prepare_services_installed',receipt=services.receipt())
        if getattr(host,'localization_initialized',False) is not True:
            initialize_localization(host,host.dll_directory,
                shared_dependency_profile=getattr(host,
                    '_civ6_host_shared_dependencies',None))
        if getattr(host,'localization_initialized',False) is not True:
            raise ValueError('XP2 Prepare localization did not initialize')
        phase = 'before_prepare'
        source.verify_live(core._handle,context,host,read,contract)
        services.verify_callbacks()
        require_null_tuner_diagnostic(host,null_tuner_diagnostic)
        getter = virtual(core,context,0x38,contract['engine']['outer_initialized_rva'],C.c_bool)
        if getter(context) is not True:
            raise ValueError('XP2 Prepare requires the successful native initialized getter')
        call = virtual(core,context,0x40,contract['engine']['outer_prepare_rva'],None)
        emit('before_xp2_prepare',outer_slot='0x40',inner_slot='0x50',target_rva='0x591870')
        host._xp2_prepare_entered = True
        services.entered = True
        services.phase = 'prepare_entered'
        receipt['prepare_entered'] = True
        receipt.update(game_created=None,allocated_game_object=None,game_initialized=None,
                       services_nonnull=None)
        phase = 'prepare'
        call(context)
        receipt['prepare_returned'] = True
        phase = 'after_prepare'
        allocated = source.pointer(read,live['inner']+contract['engine']['services_offset'])
        receipt.update(services_nonnull=bool(allocated),game_created=bool(allocated),
                       allocated_game_object=bool(allocated),services_pointer=hex(allocated))
        live_after = source.verify_live(core._handle,context,host,read,contract,prepared=True)
        if live_after['inner'] != live['inner']:
            raise ValueError('XP2 Prepare changed its retained inner context')
        services.require_complete()
        services.phase = 'prepare_returned'
        receipt.update(status='xp2_context_prepared_diagnostic_only',game_created=True,
                       allocated_game_object=True,game_initialized=False,
                       services_pointer=hex(live_after['services']),services=services.receipt())
        emit('xp2_prepare_returned',receipt=dict(receipt))
        return receipt
    except Exception as exc:
        services.phase = 'failed'
        receipt.update(status='failed',failure_phase=phase,failure_type=type(exc).__name__,
                       failure_message=str(exc),services=services.receipt())
        raise XP2PrepareError(receipt,'XP2 Prepare failed during '+phase) from exc


def prepare_receipt(host):
    services = getattr(host,'_xp2_prepare_services',None)
    receipt = getattr(host,'_xp2_prepare_receipt',None)
    if not isinstance(services,PrepareServices) or type(receipt) is not dict or services.host is not host:
        raise ValueError('XP2 Prepare receipt has no retained owner')
    return {**receipt,'services':services.receipt()}

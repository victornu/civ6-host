"""Shared expansion Init mechanics selected by source-qualified contracts.

This module owns no engine offsets, input admission or native entry point. The
engine adapter supplies those after source, module and private-input checks.
Unknown host callbacks are revoked before any native setter/Init dispatch.
"""
import ctypes as C
import hashlib
import struct


def restrict_callbacks(host, *, host_slots, auxiliary_slots, logger_slots) -> dict:
    """Revoke inherited Base host callbacks outside the Expansion Init proof."""
    bind = getattr(host, '_bind', None)
    unsupported = getattr(host, '_unsupported', None)
    if not callable(bind) or not callable(unsupported):
        raise ValueError('Expansion Init requires a rebindable DiagnosticHost callback surface')
    tables = (('host', getattr(host, 'vtable', None), host_slots), ('auxiliary', getattr(host, 'aux_vtable', None), auxiliary_slots), ('logger', getattr(host, 'logger_vtable', None), logger_slots), ('type registrar', getattr(host, 'registrar_vtable', None), set()), ('autoarchive registry', getattr(host, 'descriptor_vtable', None), set()))
    rebound = []
    for interface, table, allowlist in tables:
        if table is None or not hasattr(table, '__len__'):
            raise ValueError(f'Expansion Init host is missing its {interface} callback table')
        for index in range(len(table)):
            offset = index * 8
            if offset in allowlist:
                if not table[index]:
                    raise ValueError(f'Expansion Init allowed callback {interface}+{hex(offset)} is unbound')
                continue
            bind(table, offset, None, [C.c_void_p], unsupported(interface, offset))
            rebound.append(f'{interface}+{hex(offset)}')
    return {'rebound_unsupported_count': len(rebound), 'rebound_unsupported_sha256': hashlib.sha256('\n'.join(rebound).encode('ascii')).hexdigest(), 'preserved_allowlist': {'host': [hex(item) for item in sorted(host_slots)], 'auxiliary': [hex(item) for item in sorted(auxiliary_slots)], 'logger': [hex(item) for item in sorted(logger_slots)], 'type_registrar': [], 'autoarchive_registry': []}}

def require_empty_globals(core, read, globals_rvas) -> dict:
    values = {}
    for rva in globals_rvas:
        value = struct.unpack('<Q', read(core._handle + rva, 8))[0]
        values[hex(rva)] = value
    if any((values[hex(rva)] != 0 for rva in globals_rvas)):
        raise ValueError('Expansion host singleton globals are not empty; refusing to replace an installed host')
    return values

def require_installed_globals(core, host, read, globals_rvas) -> dict:
    expected_objects = (getattr(host, 'pointer', None), getattr(host, 'aux_object', None), getattr(host, 'logger_object', None))
    expected = []
    for value in expected_objects:
        if type(value) is int:
            pointer = value
        elif value is not None:
            pointer = C.addressof(value)
        else:
            raise ValueError('Expansion host did not retain a required interface object')
        if pointer <= 0:
            raise ValueError('Expansion host interface object has an invalid pointer')
        expected.append(pointer)
    observed = {hex(rva): struct.unpack('<Q', read(core._handle + rva, 8))[0] for rva in globals_rvas}
    expected_by_rva = {hex(rva): pointer for rva, pointer in zip(globals_rvas, expected)}
    if observed != expected_by_rva:
        raise ValueError('Expansion host setter did not retain the exact host, auxiliary, and logger interfaces')
    return observed

def require_declarations(host, declarations) -> list[dict]:
    filters = getattr(host, 'filters', None)
    entries = getattr(filters, 'entries', None)
    if type(entries) is not dict:
        raise ValueError('Expansion event filter registry is unavailable after Init')
    observed = [(event, filter_id, value) for event, pairs in entries.items() for filter_id, value in pairs]
    if any((type(value) is not int for row in observed for value in row)) or tuple(observed) != declarations:
        raise ValueError('Expansion Init declared a different event-filter list or order')
    return [{'event': hex(event), 'filter_id': hex(filter_id), 'value': value} for event, filter_id, value in observed]


def initialize(core, context, host, *, profile, source, input_receipt,
               callback_receipt, slots, globals_rvas, declarations, vtable_bytes,
               context_validator, virtual_factory, read, emit, error_type):
    """One native Init attempt with a complete, relocated vtable contract."""
    context_validator(profile, core._handle, context, read)
    table = struct.unpack('<Q', read(context, 8))[0]
    expected_ptrs = struct.unpack('<' + 'Q' * (len(vtable_bytes) // 8), vtable_bytes)
    relocated = struct.pack('<' + 'Q' * len(expected_ptrs), *(core._handle + ptr - 6442450944 for ptr in expected_ptrs))
    if read(table, len(relocated)) != relocated:
        raise ValueError('Expansion live context vtable differs from the full pinned Init-boundary capture')
    for slot, rva in slots.items():
        actual = struct.unpack('<Q', read(table + slot, 8))[0]
        if actual != core._handle + rva:
            raise ValueError(f'Expansion context slot {hex(slot)} does not match its pinned target')
    getter = virtual_factory(core, context, 56, slots[56], C.c_bool)
    before = getter(context)
    if type(before) is not bool:
        raise ValueError('Expansion initialized-state getter did not return a bool')
    if before:
        raise ValueError('Expansion context is already initialized; refusing a second Init')
    receipt = {'schema': 'civ6rl.native_' + profile.ruleset + '_context_init_receipt.v1', 'source': source, 'inputs': input_receipt, 'core_sha256': profile.core_sha256, 'initialized_before': before, 'host_setter_called': False, 'host_setter_dispatch_started': False, 'host_callback_surface': callback_receipt, 'host_globals_before_set': None, 'init_called': False, 'init_dispatch_started': False, 'init_returned': None, 'initialized_after': None, 'game_created': False, 'newgame_called': False, 'prepare_called': False, 'simulation_ready': False, 'canonical_database_certified': False, 'eligible_for_training': False, 'context_may_require_destroy': False}
    phase = 'before_host_set'
    try:
        if emit is not None:
            emit('before_' + profile.ruleset + '_host_set', receipt=receipt)
        receipt['host_globals_before_set'] = require_empty_globals(core, read, globals_rvas)
        setter = virtual_factory(core, context, 96, slots[96], None, C.c_void_p)
        receipt['context_may_require_destroy'] = True
        phase = 'host_set'
        receipt['host_setter_dispatch_started'] = True
        setter(context, host.pointer)
        receipt['host_setter_called'] = True
        receipt['host_globals_after_set'] = require_installed_globals(core, host, read, globals_rvas)
        if emit is not None:
            emit(profile.ruleset + '_host_set', slot='0x60', gameplay_path_callback='0x138', configuration_path_callback='0x140')
        if getter(context) is not False:
            raise ValueError('Expansion context state changed during host installation')
        phase = 'before_init'
        if emit is not None:
            emit('before_' + profile.ruleset + '_init', gameplay_label='Gameplay')
        initializer = virtual_factory(core, context, 40, slots[40], C.c_bool)
        phase = 'init'
        receipt['init_dispatch_started'] = True
        init_result = initializer(context)
        receipt['init_called'] = True
        if type(init_result) is not bool:
            raise ValueError('Expansion Init thunk did not return a bool')
        receipt['init_returned'] = init_result
        receipt['event_filter_declarations'] = require_declarations(host, declarations)
        phase = 'post_init_getter'
        after = getter(context)
        if type(after) is not bool:
            raise ValueError('Expansion initialized-state getter did not return a bool')
        receipt['initialized_after'] = after
        if emit is not None:
            emit(profile.ruleset + '_context_init_observed', init_returned=init_result, initialized_after=after, gameplay_connection_slot='0x58', game_created=False, newgame_called=False)
        child = struct.unpack('<Q', read(context + 8, 8))[0]
        if not child:
            raise ValueError('Expansion Init did not retain its inner context object')
        configuration_connection = struct.unpack('<Q', read(child + 80, 8))[0]
        gameplay_connection = struct.unpack('<Q', read(child + 88, 8))[0]
        receipt['connections'] = {'configuration_slot': 'inner+0x50', 'configuration_nonnull': bool(configuration_connection), 'gameplay_slot': 'inner+0x58', 'gameplay_nonnull': bool(gameplay_connection)}
        if not init_result or not after or (not configuration_connection) or (not gameplay_connection):
            raise ValueError('Expansion Init did not establish the native initialized state')
        receipt['status'] = profile.ruleset + '_context_initialized_diagnostic_only'
        return receipt
    except Exception as exc:
        receipt['status'] = 'failed'
        receipt['failure_phase'] = phase
        receipt['failure_type'] = type(exc).__name__
        receipt['failure_message'] = str(exc)
        raise error_type(receipt, f'Expansion context Init failed during {phase}') from exc

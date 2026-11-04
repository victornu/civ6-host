"""Source-bound projection of the official UI's no-timer branch.

Read the current restored application provider with its native lookup. Other
timer modes require the EXE's elapsed-time service and remain unknown here.
The captured initial timer result is never replayed as a live predicate.
"""
from __future__ import annotations

import ctypes as C
import struct
from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256

PROOF_PATH = 'work/host-simultaneous/turn-timer/turn-timer-binding.json'
PROOF_SHA256 = 'f03f9d14621d632a6e4f34f3a183f8e43eb1617c7e946a48838d851eb253ac1e'
NO_TIMER = 0xA5196DAB
TIMER_KEY = 'TURN_TIMER_TYPE'


def verify_source():
    from .provenance import resource_root
    from .native.native_source_cache import load_pinned_json
    from .native.native_configuration_finalization import CORE_SHA256, EXE_SHA256
    proof = load_pinned_json(resource_root() / PROOF_PATH, PROOF_SHA256)
    if (proof['images']['CivilizationVI.exe']['sha256'] != EXE_SHA256
            or proof['images']['GameCore_Base_FinalRelease.dll']['sha256'] != CORE_SHA256
            or proof['registration']['callback_rva'] != '0x1AA480'
            or proof['helper_chain']['configuration_key_global']['literal']['text'] != TIMER_KEY
            or proof['helper_chain']['timer_type_hash_default_and_no_timer']['u32_decimal'] != NO_TIMER):
        raise ValueError('Official timer projection source changed')
    return proof


def elapsed_from_lookup(raw):
    """EXE101390's absent-row sentinel and DWORD read, then EXE0F5520.

No duration/elapsed substitute exists for a non-NONE timer. A malformed memory
copy is an error, distinct from a native lookup returning no row.
"""
    if raw is None:
        return False, None
    if type(raw) is not bytes or len(raw) != 12:
        raise ValueError('Timer lookup requires its exact native DWORD prefix')
    timer_type = struct.unpack_from('<I', raw, 8)[0]
    return (False if timer_type == NO_TIMER else None), timer_type


def read(owner, *, core_sha256=BASE_CORE_SHA256):
    owner.check_thread()
    # This retained proof supplies the shared EXE no-timer projection. The
    # selected native provider ABI is checked separately below for XP1.
    verify_source()
    from .native.native_application_configuration import LOOKUP
    from .native.native_player_configuration import _checked_object, LOOKUP_SLOT
    from .native.native_configuration_finalization import _invoke
    from .native.native_game_configuration import game_configuration_hash
    app, base = owner.owner, owner.core._handle
    reader = owner.runtime.read
    call = getattr(owner.runtime, 'call', None)
    app.require_context(base, owner.context)
    before = app.snapshot()
    target = before['normalized']
    if core_sha256 == BASE_CORE_SHA256:
        lookup = _checked_object(base, target, reader, LOOKUP_SLOT, LOOKUP)
    elif core_sha256 in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        from .configuration_profiles import configuration_abi, require_owner_profile
        abi = require_owner_profile(configuration_abi(core_sha256))
        if (getattr(app, '_configuration_abi', None) is not abi
                or owner.load_abi.core_sha256 != core_sha256):
            raise ValueError('Timer configuration belongs to another engine')
        table_raw = reader(target, 8)
        table = base + abi.vtable_rva
        if type(table_raw) is not bytes or table_raw != table.to_bytes(8, 'little'):
            raise ValueError('XP1 timer configuration vtable differs')
        slot_raw = reader(table + LOOKUP_SLOT, 8)
        lookup = base + abi.lookup_rva
        if type(slot_raw) is not bytes or slot_raw != lookup.to_bytes(8, 'little'):
            raise ValueError('XP1 timer lookup slot differs')
    else:
        raise ValueError('Timer configuration engine is not qualified')
    address = _invoke(call, lookup, C.c_void_p, target, (C.c_uint32,),
                      game_configuration_hash(TIMER_KEY))
    if address is not None and (type(address) is not int or address < 0):
        raise ValueError('Invalid native timer lookup pointer')
    raw = None if not address else reader(address, 12)
    elapsed, timer_type = elapsed_from_lookup(raw)
    if app.snapshot() != before:
        raise RuntimeError('Application provider changed during timer read')
    # Avoid repeating trace records, but never cache the live lookup result.
    signature = (timer_type, elapsed)
    if getattr(owner, '_network_timer_logged', object()) != signature:
        provenance = (dict(configuration_core_sha256=core_sha256,
            configuration_source_sha256=abi.application_proof_sha256)
            if core_sha256 in (XP1_CORE_SHA256,XP2_CORE_SHA256) else {})
        owner.emit('official_lan_timer_projection', source_sha256=PROOF_SHA256,
            provider='restored_application_B', timer_type_u32=timer_type,
            timer_type_present=raw is not None, timer_elapsed=elapsed,
            native_configuration_written=False, elapsed_clock_implemented=False,
            strategic_training_ready=False, **provenance)
        owner._network_timer_logged = signature
    return elapsed

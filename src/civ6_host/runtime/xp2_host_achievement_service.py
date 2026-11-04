"""Source-qualified absence of the optional XP2 platform achievement sink.

This does not unlock achievements or acknowledge a successful platform request.
Only the source-proved caller chain whose result is ultimately unused is
admitted. Other callers of this host interface continue to fail closed.
"""
import ctypes as C

from .configuration_profiles import XP2_CORE_SHA256


def install(backend):
    from .native.native_host import DiagnosticHost
    from .native.native_absent_achievements import capture_stack
    from .xp2_turn_source import require_prepared_owner
    from . import xp2_host_slot20_source as source

    backend.check_thread()
    host = backend.host
    if (getattr(backend, '_saved_load_candidate', False) is not True
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or backend.stage != 'prepared' or backend.prefix is not None
            or backend.busy is not True or backend.poisoned or backend.destroyed
            or getattr(backend, '_xp1_commands_requested', False) is not True
            or hasattr(backend, '_xp2_host20') or not isinstance(host, DiagnosticHost)
            or host.achievement_service_installed is not False):
        raise ValueError('XP2 optional achievement service requires its exclusive prepared owner')
    require_prepared_owner(backend)
    source.source_dependencies()
    live = source.verify_live(backend.core._handle, backend.runtime.read,
                              host_pointer=host.pointer)
    previous = host._slot_bindings.get((C.addressof(host.vtable), 0x20))
    if (previous is None or previous[0] != host.vtable[0x20 // 8]
            or getattr(previous[1], '_native_unavailable', None) != ('host', 0x20)):
        raise ValueError('XP2 HOST+20 has a foreign or already admitted callback')

    def absent_service(this):
        backend.check_thread()
        host._check(this)
        if (backend.host is not host or backend.destroyed or backend.poisoned
                or backend.load_abi.core_sha256 != XP2_CORE_SHA256
                or host.achievement_service_installed is not False):
            raise ValueError('XP2 optional achievement owner changed')
        frames = capture_stack()
        proof_sha256 = source.select_contract(frames,
            service_installed=host.achievement_service_installed)
        backend.emit('native_optional_achievement_service_absent', slot='0x20',
            core_sha256=XP2_CORE_SHA256, native_stack=frames,
            native_null_branch_used=True, platform_service_installed=False,
            platform_request_submitted=False, platform_success_reported=False,
            real_exe_field_initialization_claimed=False,
            source_proof_sha256=proof_sha256, source_qualified_unused_result_path=True)
        return None

    host._bind(host.vtable, 0x20, C.c_void_p, [C.c_void_p], absent_service)
    receipt = dict(core_sha256=XP2_CORE_SHA256, source_sha256=source.SOURCE[1],
        slot='0x20', callback_pointer=host.vtable[0x20 // 8],
        source_verification=live, platform_service_installed=False,
        platform_success_reported=False, unknown_service_fallback=False,
        caller_results_consumed_admitted=False)
    backend._xp2_host20 = (host, absent_service, receipt)
    backend.emit('xp2_optional_achievement_service_installed', **receipt)
    return receipt

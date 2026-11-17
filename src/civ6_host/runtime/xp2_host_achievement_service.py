"""Source-qualified absence of the optional expansion platform achievement sink.

This does not unlock achievements or acknowledge a successful platform request.
Only the source-proved caller chain whose result is ultimately unused is
admitted. Other callers of this host interface continue to fail closed.
"""
import ctypes as C

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256


def install(backend):
    from .xp2_turn_source import require_prepared_owner
    from . import xp2_host_slot20_source as source

    return _install(backend, source=source, core_sha256=XP2_CORE_SHA256,
                    engine='XP2', require_prepared_owner=require_prepared_owner)


def install_xp1(backend):
    from . import xp1_host_slot20_source as source

    return _install(backend, source=source, core_sha256=XP1_CORE_SHA256, engine='XP1',
                    require_prepared_owner=source.require_prepared_owner,
                    require_active_owner=source.require_active_owner)


def _install(backend, *, source, core_sha256, engine, require_prepared_owner,
             require_active_owner=None):
    from .native.native_host import DiagnosticHost
    from .native.native_absent_achievements import capture_stack

    backend.check_thread()
    host = backend.host
    retained = f'_{engine.lower()}_host20'
    if (getattr(backend, '_saved_load_candidate', False) is not True
            or backend.load_abi.core_sha256 != core_sha256
            or backend.stage != 'prepared' or backend.prefix is not None
            or backend.busy is not True or backend.poisoned or backend.destroyed
            or getattr(backend, '_xp1_commands_requested', False) is not True
            or hasattr(backend, retained) or not isinstance(host, DiagnosticHost)
            or host.achievement_service_installed is not False):
        raise ValueError(f'{engine} optional achievement service requires its exclusive prepared owner')
    require_prepared_owner(backend)
    core, runtime = backend.core, backend.runtime
    execution_image = getattr(core, '_civ6_host_execution_image', None)
    options = {'execution_image': execution_image} if execution_image is not None else {}
    image_fields = ({'execution_image_sha256': execution_image.image_sha256}
                    if execution_image is not None else {})
    source.source_dependencies(**options)
    live = source.verify_live(core._handle, runtime.read,
                              host_pointer=host.pointer, **options)
    previous = host._slot_bindings.get((C.addressof(host.vtable), 0x20))
    if (previous is None or previous[0] != host.vtable[0x20 // 8]
            or getattr(previous[1], '_native_unavailable', None) != ('host', 0x20)):
        raise ValueError(f'{engine} HOST+20 has a foreign or already admitted callback')

    def absent_service(this):
        backend.check_thread()
        host._check(this)
        if (backend.host is not host or backend.core is not core or backend.runtime is not runtime
                or getattr(core, '_civ6_host_execution_image', None) is not execution_image
                or backend.destroyed or backend.poisoned
                or backend.load_abi.core_sha256 != core_sha256
                or host.achievement_service_installed is not False):
            raise ValueError(f'{engine} optional achievement owner changed')
        if require_active_owner is not None:
            require_active_owner(backend)
        frames = capture_stack()
        proof_sha256 = source.select_contract(frames,
            service_installed=host.achievement_service_installed, **options)
        backend.emit('native_optional_achievement_service_absent', slot='0x20', **image_fields,
            core_sha256=core_sha256, native_stack=frames,
            native_null_branch_used=True, platform_service_installed=False,
            platform_request_submitted=False, platform_success_reported=False,
            real_exe_field_initialization_claimed=False,
            source_proof_sha256=proof_sha256, source_qualified_unused_result_path=True)
        return None

    host._bind(host.vtable, 0x20, C.c_void_p, [C.c_void_p], absent_service)
    receipt = dict(core_sha256=core_sha256, source_sha256=source.SOURCE[1], **image_fields,
        slot='0x20', callback_pointer=host.vtable[0x20 // 8],
        source_verification=live, platform_service_installed=False,
        platform_success_reported=False, unknown_service_fallback=False,
        caller_results_consumed_admitted=False)
    setattr(backend, retained, (host, absent_service, receipt))
    backend.emit(f'{engine.lower()}_optional_achievement_service_installed', **receipt)
    return receipt

"""Compose captured expansion services for the existing OfficialLoadBackend.

No fixture scripts, diagnostic values, fabricated gameplay callbacks or cleanup
of a possibly loaded Game. The bounded caller retains this graph through its
separately qualified shutdown or controlled process termination.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import json
from pathlib import Path

from .captured_saved_load import validate_candidate_inputs
from .xp1_saved_load import validate_private_bootstrap
from .saved_load_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256


def compose_saved_load_services(backend):
    from .native.native_official_bundle import _manifest, _file, validate_fixture
    from .native.native_gameplay_script_registry import NativeGameplayScriptRegistry
    from .native.native_havok import HAVOK_SHA256
    from .native.native_script_runtime import NativeScriptRuntime
    from .native.native_core_lock import NativeCoreLock
    from .native.native_36c9b2b4_pair_codec import EMPTY_RECEIVER_STATE
    from .saved_load_services import SavedLoadServices

    backend.check_thread()
    if (getattr(backend, '_saved_load_candidate', False) is not True
            or backend.stage != 'prepared' or backend.prefix is not None
            or hasattr(backend, '_xp1_service_roots') or backend.game_flag() != 0):
        raise ValueError('XP1 composition requires one fresh prepared candidate')
    validate_candidate_inputs(backend.inputs, backend.captured_bundle)
    core_sha256 = backend.configuration_abi.core_sha256
    if core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256):
        raise ValueError('Unknown captured service engine')
    xp2 = core_sha256 == XP2_CORE_SHA256
    validate_fixture(backend.captured_bundle, backend.fixture)
    host = backend.host
    validate_private_bootstrap(host.manifest, backend.captured_bundle.fixture['localization_bootstrap'],
                               private_root=Path(backend.fixture).resolve().parent)
    if (host.manifest['databases']['localization']['sha256']
               != backend.captured_bundle.fixture['databases']['localization']['sha256']
            or not host.localization_initialized
            or getattr(host, 'execution_lock', None) is not None):
        raise ValueError('XP1 services require the actual captured private Localization and ICU')

    _, capture = _manifest(backend.captured_bundle.reference)
    source_ref = capture['selected_gameplay_sources']['manifest']
    if xp2:
        from .script_wire_paths import registry_from_capture
        from .xp2_bundle_inputs import SELECTED_PATHS, SCRIPT_SHA256
        registry, script_hashes, script_dependencies = registry_from_capture(source_ref,
            process=capture['preflight']['process'])
        if (tuple(registry.wire_paths) != SELECTED_PATHS or len(script_hashes) != 1
                or set(script_hashes.values()) != {SCRIPT_SHA256}):
            raise ValueError('XP2 registry differs from its captured WorldCongress source')
        backend._saved_script_dependencies = script_dependencies
    else:
        scripts = json.loads(_file(source_ref, {}, maximum=4 * 1024 ** 2))
        script_profile = backend.captured_bundle.content_profile.get('gameplay_scripts')
        count_fields = ('selected_path_count', 'active_count', 'source_records', 'source_files')
        if (scripts.get('selected_paths') != [] or scripts.get('records') != []
                or scripts.get('files') != {} or type(script_profile) is not dict
                or script_profile.get('selected_and_active_empty') is not True
                or any(type(script_profile.get(key)) is not int or script_profile[key] != 0
                       for key in count_fields)):
            raise ValueError('This exact XP1 candidate requires captured empty selected and active gameplay scripts')
        registry = NativeGameplayScriptRegistry((), selected_scripts=())
        script_hashes = {}
    havok = Path(host.dll_directory) / 'HavokScript_FinalRelease.dll'
    if hashlib.sha256(havok.read_bytes()).hexdigest() != HAVOK_SHA256:
        raise ValueError('XP1 saved-service HKS binary changed')
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = [C.c_wchar_p], C.c_void_p
    module = kernel.GetModuleHandleW(None)
    if not module:
        raise RuntimeError('Current host executable module is unavailable')
    executable = C.WinDLL('', handle=module)
    backend._xp1_service_roots = [registry, executable]

    def emit(stage, **fields):
        if 'event_name' in fields:
            if 'gameplay_event_name' in fields:
                raise ValueError('Ambiguous shared gameplay event telemetry')
            fields['gameplay_event_name'] = fields.pop('event_name')
        backend.emit(stage, **fields)

    runtime = NativeScriptRuntime(C.WinDLL(str(havok)), executable, emit)
    backend._xp1_service_roots.append(runtime)
    if xp2:
        runtime.bind_core_services(host, backend.context,
            core_library=backend.core, core_sha256=core_sha256)
    else:
        runtime.bind_core_services(host, backend.context)
    child = runtime.acquire()
    backend._xp1_service_roots.append(child)
    runtime.attach_standard_libraries(child)
    for namespace in ('DB', 'GameInfo', 'GlobalParameters', 'Path', 'Locale'):
        runtime.namespaces.register(child, namespace)
    runtime.bind_native_game_api(child, backend.context, backend.core, core_sha256=core_sha256)
    runtime.attach_game_events(child)
    # No include snapshot is fabricated. XP1 selection is empty; the exact XP2
    # WorldCongress source names no direct includes. Dynamic unbound requests
    # still raise an error through script_include_unavailable.

    def bootstrap(context_child, name):
        # ScriptContextService.acquire rejects every name in an empty selected
        # registry before reaching this callback. Keep direct use strict too.
        raise ValueError('Captured empty gameplay selection cannot create a script context')

    lock = NativeCoreLock(host, executable)
    backend._xp1_service_roots.append(lock)
    host.execution_lock = lock
    from .xp1_saved_load_logger import install_saved_load_logger
    install_saved_load_logger(backend)
    if getattr(backend,'_xp1_commands_requested',False):
        from .xp1_host_thread_gate import install as install_thread_gate
        install_thread_gate(backend)
        from .xp1_host_slot78 import install as install_slot78
        install_slot78(backend)
        if xp2:
            from .xp2_host_achievement_service import install as install_achievements
            install_achievements(backend)
    services = SavedLoadServices(backend, runtime, child, registry,
        core_sha256=core_sha256, script_hashes=script_hashes, bootstrap=None if xp2 else bootstrap,
        saved_map_values=backend.inputs.map_values,
        saved_config_sha=hashlib.sha256(backend.inputs.configuration).hexdigest())
    backend._xp1_service_roots.append(services)
    services.emit = services.events.emit = emit
    services.install_application_mirror()
    from .xp1_load_capability import install_saved_load_capabilities
    install_saved_load_capabilities(backend)
    from .xp1_load_options import install_saved_load_options
    install_saved_load_options(backend)
    deferred = services.install_deferred_events(optional_preprocessor=None, queue_metadata_service=None)
    deferred.emit = emit
    controller = services.install_control_inputs(local_player_id=0)
    arguments = services.install_event_arguments(normalizer_transform=None, dynamic_registrations=())
    # These are this headless host's explicitly created EXE receiver registries:
    # no observers, hooks or entity listeners are installed. They describe our
    # owned receivers, not the Core's event registry and not an inference from
    # the empty captured script list. The native Core registry remains intact;
    # existing A0 guards/decoders refuse unsupported shapes and consumers.
    consumer = arguments.install_consumers(receiver_state=dict(EMPTY_RECEIVER_STATE),
        pre_turn_immediate_state=dict(EMPTY_RECEIVER_STATE), entity_listener_count=0)
    consumer.emit = emit
    consumer.enable_controller_events(controller)
    consumer.enable_notification_scopes()
    if xp2 and not getattr(backend,'_xp2_postload_requested',False):
        # Initial saved Load only. The retained XP1 raw-Load interval did not
        # consume C0/player-query/cache-publication/post160 callbacks. Their XP2
        # implementations are not inferred by installing XP1 wrappers here:
        # unqualified requests retain the original fatal callback. The same
        # real queue/argument/controller owners remain active.
        services.composition_scope = dict(engine='xp2', phase='initial-saved-load-candidate',
            postload_160=False, cache_publication=False, commands=False,
            application_mirror=True,public_session_admitted=False)
        return services
    services.install_status_messages(receiver_state=dict(EMPTY_RECEIVER_STATE),
        writer_metadata_service=None, per_thread_hook=None)
    services.install_cache_facades()
    queries = services.install_player_queries(core_lock=lock)
    consumer.enable_player_queries(queries)
    services.install_postload_aux90_null()
    if xp2:
        services.composition_scope=dict(engine='xp2',phase='saved-postload-candidate',
            postload_160=True,cache_publication=True,commands=False,
            application_mirror=True,public_session_admitted=False)
    if getattr(backend,'_xp1_commands_requested',False):
        from .a0_found_unit_event import enable
        enable(consumer)
        from .a0_foundation_events import enable as enable_foundation
        enable_foundation(consumer, backend)
        from .a0_foundation_events import enable_turn_units
        enable_turn_units(consumer, backend)
        if xp2:
            from .xp2_world_unit_event_source import bind_owner as bind_input_event_sources
            bind_input_event_sources(backend,backend.core,backend.runtime.read)
            from .xp2_production_queue_event_source import bind_owner as bind_queue_event_sources
            bind_queue_event_sources(backend,backend.core,backend.runtime.read)
            from .a0_foundation_events import enable_history_events
            enable_history_events(consumer, backend)
            from .a0_natural_wonder import enable as enable_natural_wonder
            enable_natural_wonder(consumer, backend)
            from .a0_xp2_turn_events import enable as enable_climate_events
            enable_climate_events(consumer, backend)
            from . import xp2_feature_reveal_source
            from .empty_presentation_events import enable as enable_empty_presentation
            enable_empty_presentation(consumer, backend, xp2_feature_reveal_source)
        from .a0_foundation_events import enable_placements
        enable_placements(consumer, backend)
        from .a0_combat_events import enable as enable_combat
        enable_combat(consumer, backend)
        from .a0_foundation_events import enable_improvement_changes
        enable_improvement_changes(consumer, backend)
        from .a0_district_damage import enable as enable_district_damage
        enable_district_damage(consumer, backend)
        from .a0_city_scalar_events import enable as enable_city_scalar
        enable_city_scalar(consumer)
        consumer.enable_private_notifications()
        from .xp1_action_transport import SavedActionTransport
        SavedActionTransport(services)
        from .xp1_host_slot78 import require_composed_callbacks
        require_composed_callbacks(backend,services)
        if xp2:
            services.composition_scope.update(phase='saved-initial-actions-candidate',commands=True,
                complete_action_space=False,public_session_admitted=False)
    # install_prefix() performs the one attach after this callback returns.
    return services

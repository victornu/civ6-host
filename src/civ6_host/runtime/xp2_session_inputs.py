"""Shared XP2 saved-input dependencies for qualification and session preparation.

This owns only source/build selection, never a second loader or game lifecycle.
"""
import hashlib
from .paths import resource_root

def digest(data):return hashlib.sha256(data).hexdigest()

XP2_UI_HOST = ('work/native-host-xp2-ui-build01/civ6rl-native-python.exe',
               'a3d977a4aa09d3f4f88a393f59e32f5a34d12d79db48606c39c4b9e09994f799')


def xp2_saved_load_source_dependencies(*,postload160=False,observe_player=False):
    """Pin the exact private sources consumed by this raw XP2 service graph."""
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, _source
    from civ6_host.runtime.resource_resolution import resolve_path
    from civ6_host.runtime import (xp2_configuration_profile, xp2_context_profile,
        xp2_normalization_source, xp2_prepare_source, xp2_preload_source,
        xp2_saved_script_services, xp1_load_capability, xp1_load_options,
        xp1_saved_load_logger, xp1_loaded_lifetime, saved_load_job_observer,
        captured_saved_load, cache_update_profiles, a0_notification_scope_source,
        core_script_services, script_binding_profiles, application_mirror_profiles,
        a0_controller_source, a0_xp2_victory_source)
    pins={}
    def add(path,expected):
        path=resolve_path(resource_root()/path).resolve(strict=True);name=str(path)
        if (type(expected) is not str or len(expected)!=64
                or name in pins and pins[name]!=expected
                or digest(path.read_bytes())!=expected):
            raise ValueError('XP2 saved Load source dependency differs: '+name)
        pins[name]=expected
    if (type(postload160) is not bool or type(observe_player) is not bool
            or observe_player and not postload160):raise ValueError('Exact XP2 dependency scope required')
    for path, expected in (a0_xp2_victory_source.SOURCE, a0_xp2_victory_source.COMPARISON):
        add(path, expected)
    for selected in (xp2_configuration_profile.source_dependencies(),
            xp2_normalization_source.source_dependencies(),xp2_prepare_source.source_pins(),
            xp2_preload_source.source_pins(),xp2_saved_script_services.source_dependencies(),
            xp1_load_capability.source_dependencies(XP2_CORE_SHA256),
            xp1_load_options.source_dependencies(XP2_CORE_SHA256),
            xp1_saved_load_logger.source_dependencies(XP2_CORE_SHA256),
            xp1_loaded_lifetime.source_dependencies(XP2_CORE_SHA256,postload=postload160),
            cache_update_profiles.source_pins(),a0_notification_scope_source.source_dependencies(),
            script_binding_profiles.source_dependencies(XP2_CORE_SHA256),
            application_mirror_profiles.source_dependencies(XP2_CORE_SHA256),
            a0_controller_source.source_pins()):
        for path,expected in selected.items():add(path,expected)
    context=xp2_context_profile.verify_source()['proof']
    for path,expected in (*captured_saved_load.SOURCES,xp2_context_profile.SOURCE,
                         xp2_context_profile.BOUNDARY,saved_load_job_observer.XP2_SOURCE,
                         core_script_services.INIT_SOURCE,core_script_services.TYPE_SOURCE):
        add(path,expected)
    for ref in (context['capture_script'],*context['extractors']):add(ref['path'],ref['sha256'])
    for version in ('v1','v2'):
        prior=context['source_predecessors']
        add(prior[version+'_profile_path'],prior[version+'_profile_sha256'])
    jobs=_source(saved_load_job_observer.XP2_SOURCE)
    refs=jobs['source_refs'];refs=refs.values() if hasattr(refs,'values') else refs
    for ref in (jobs['extractor'],*refs):add(ref['path'],ref['sha256'])
    captured_saved_load.proofs_for_candidate(XP2_CORE_SHA256)
    if postload160:
        from civ6_host.runtime import xp1_postload_candidate, loaded_cache_publication, xp1_cache_publication, player_notification_profiles
        for selected in (xp1_postload_candidate.source_dependencies(XP2_CORE_SHA256),
                loaded_cache_publication.source_dependencies(core_sha256=XP2_CORE_SHA256),
                xp1_cache_publication.source_dependencies(core_sha256=XP2_CORE_SHA256),
                player_notification_profiles.source_pins(core_sha256=XP2_CORE_SHA256)):
            for path,expected in selected.items():add(path,expected)
    if observe_player:
        from civ6_host.runtime.xp1_ui_binding import source_dependencies as ui_dependencies
        for path,expected in ui_dependencies(core_sha256=XP2_CORE_SHA256).items():add(path,expected)
        from civ6_host.runtime.source_build_identity import verify_source_build
        from civ6_host.runtime.xp2_ui_binding_source import UI_COMPONENT_SHA
        executable=resource_root()/XP2_UI_HOST[0]
        if digest(executable.read_bytes())!=XP2_UI_HOST[1]:raise ValueError('XP2 UI host changed')
        build=verify_source_build(executable,required_components={
            'gamecore_python_host.c':saved_load_job_observer.XP2_HOST_COMPONENT_SHA,
            'script_core_ui_binding_profiles.inc':UI_COMPONENT_SHA})
        for name,expected in build['build_dependencies'].items():add(name,expected)
    return dict(sorted(pins.items()))


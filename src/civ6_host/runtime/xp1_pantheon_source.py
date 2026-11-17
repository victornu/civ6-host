"""Exact installed XP1 pantheon bindings and existing host boundary profiles.

The Base builders retain their default proof. This selected profile proves their
XP1 bindings separately. Native modifier and subscriber logic remains in Core;
unqualified host callbacks still refuse. Source admission is not native coverage.
"""
from hashlib import sha256
from pathlib import Path

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source
from .execution_images import _PROFILE, _XP1_PROFILE
from .xp1_saved_load import REFERENCE
from . import xp2_direct_religion_source as xp2

SOURCE = ('work/x1trade/religion-preparation/e23f3443f2bd4acce7579660d6e4dbaf23a49f11e36e97bbc8bf85b6be8b0c7e.json',
          'e23f3443f2bd4acce7579660d6e4dbaf23a49f11e36e97bbc8bf85b6be8b0c7e')
CENTRAL_SOURCE = ('work/x1trade/religion-preparation/e3c8cd3a517371472e6829df09b4a04bf3b0213cd2883e6ea5b8dfbdb2ae8c71.json',
                  'e3c8cd3a517371472e6829df09b4a04bf3b0213cd2883e6ea5b8dfbdb2ae8c71')
SIGNAL_SOURCE = ('work/x1trade/religion-preparation/signals/f6b091ac7c527afa63d4a1541b0f00591ca38bf2395df52b99d4ccce93dc53a8.json',
                 'f6b091ac7c527afa63d4a1541b0f00591ca38bf2395df52b99d4ccce93dc53a8')
ACTION_SOURCE = ('work/x1trade/religion-preparation/abebd826d22a990c7a7364299c0355e971f0a018e7de8b237922172910b8ac17.json',
                 'abebd826d22a990c7a7364299c0355e971f0a018e7de8b237922172910b8ac17')
_CALLBACKS = {'Game.GetReligion':0x5b7ac0, 'Player.GetReligion':0x5c5950,
    'CachePlayerReligion.GetPantheon':0x5cf160, 'CachePlayerReligion.CanCreatePantheon':0x5cef90,
    'CacheGameReligion.IsInSomePantheon':0x5bc1c0, 'CacheGameReligion.IsInSomeReligion':0x5bc220}


def source_for(image):
    if image is _PROFILE:
        return xp2.SOURCE
    if image is _XP1_PROFILE:
        return SOURCE
    raise ValueError('Unqualified saved pantheon execution image')


def supports(reference,image):
    from .xp2_religious_chain_source import supports as supports_xp2
    return (image is _XP1_PROFILE and reference == REFERENCE) or supports_xp2(reference,image)


def core_for(prefix):
    image = getattr(prefix.backend.core,'_civ6_host_execution_image',None)
    source_for(image)
    return XP2_CORE_SHA256 if image is _PROFILE else XP1_CORE_SHA256


def source_hash(core_sha256):
    verify_source(core_sha256)
    return (xp2.SOURCE if core_sha256 == XP2_CORE_SHA256 else SOURCE)[1]


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        return xp2.verify_source()
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Pantheon bindings require the selected Rise and Fall engine')
    proof = _source(SOURCE)
    central = _source(CENTRAL_SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-installed-pantheon-source.partial.v1'
            or proof['image']['sha256'] != _XP1_PROFILE.image_sha256
            or {name:int(row['callback']['rva'],16) for name,row in proof['bindings'].items()} != _CALLBACKS
            or central['schema'] != 'civ6-host.xp1-pantheon-central-source-supplement.v1'
            or central['image_sha256'] != _XP1_PROFILE.image_sha256
            or central['parent_source']['sha256'] != SOURCE[1]
            or central['factory']['direct_calls_scanned_in_exact_text_section'] != 6):
        raise ValueError('Installed Rise and Fall pantheon source differs')
    return proof,central


def actions_qualified():
    verify_source()
    if ACTION_SOURCE is None:
        return False
    proof = _source(ACTION_SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-pantheon-action-admission.v1'
            or proof['image_sha256'] != _XP1_PROFILE.image_sha256
            or proof['bindings_sha256'] != SOURCE[1]
            or proof['central_sha256'] != CENTRAL_SOURCE[1]
            or proof['signals_sha256'] != SIGNAL_SOURCE[1]
            or proof['can_start_factory_closed'] is not True
            or proof['request_and_effect_codec_qualified'] is not True
            or proof['known_host_boundaries_reuse_existing_profiles'] is not True
            or proof['native_execution'] is not False
            or proof['native_coverage_complete'] is not False):
        raise ValueError('Pantheon action source admission differs')
    for ref in proof['references']:
        _source((ref['path'],ref['sha256']))
    signals = _source(SIGNAL_SOURCE)
    if (signals['schema'] != 'civ6-host.xp1-pantheon-signal-boundaries.static.v1'
            or signals['image']['sha256'] != _XP1_PROFILE.image_sha256
            or len(signals['subscriptions']) != 6
            or signals['validation']['reused_instruction_bytes_match_installed_image'] is not True
            or signals['validation']['capture_count'] != 34):
        raise ValueError('Pantheon signal boundary source differs')
    # Verify the actual shared profiles, without installing another dispatcher
    # or treating Core's notification manager as an absent A0 event.
    from . import game_history_event_profile, game_era_score_event_profile
    from . import faith_event_profile, city_scalar_event_profiles
    from . import retained_game_source, xp1_saved_load_logger, a0_family_source
    from .native.native_host_slot_c0 import verify_source_evidence
    game_history_event_profile.verify_source()
    game_era_score_event_profile.verify_source()
    _source(game_era_score_event_profile.INSTALLED_SHORT_SOURCE)
    faith_event_profile.verify_source()
    city_scalar_event_profiles.source()
    retained_game_source.source()
    xp1_saved_load_logger._checked_source(XP1_CORE_SHA256)
    verify_source_evidence()
    if a0_family_source.family_profile().record_types_by_kind.get(0x565abe26) != frozenset((0xc3,)):
        raise ValueError('Shared PantheonFounded receiver differs')
    return True


def require_actions(image=None):
    if image is _PROFILE:
        xp2.verify_source()
        return
    if image is not None and image is not _XP1_PROFILE:
        raise ValueError('Unqualified saved pantheon execution image')
    if not actions_qualified():
        raise ValueError('Pantheon action dependencies are not qualified')


def source_dependencies(image, *, reference=None):
    if image is _PROFILE:
        return xp2.source_dependencies(image,reference=reference)
    from .a0_family_source import verify_pinned_files
    from .paths import resource_root
    from .resource_resolution import resolve_path
    if image is not _XP1_PROFILE:
        raise ValueError('Pantheon requires the exact installed Rise and Fall image')
    proof,central = verify_source()
    refs = [dict(path=p,sha256=d) for p,d in (SOURCE,CENTRAL_SOURCE,SIGNAL_SOURCE,REFERENCE)]
    refs += list(proof['references'].values()) + list(central['reused_sources'].values())
    if ACTION_SOURCE is not None:
        actions_qualified()
        refs.append(dict(path=ACTION_SOURCE[0],sha256=ACTION_SOURCE[1]))
        refs.extend(_source(ACTION_SOURCE)['references'])
    pins = {}
    for row in refs:
        path = str(resolve_path(resource_root()/row['path']).resolve())
        if pins.setdefault(path,row['sha256']) != row['sha256']:
            raise ValueError('Pantheon source dependency conflict')
    pins.update({str(Path(row['path']).resolve()):row['sha256'] for row in proof['ui'].values()})
    pins[str(Path(image.path).resolve())] = image.image_sha256
    verify_pinned_files(pins)
    return pins


def bind_prefix(prefix, *, action=False):
    if core_for(prefix) == XP2_CORE_SHA256:
        return xp2.bind_prefix(prefix,action=action)
    from .saved_load_services import SavedLoadServices
    if type(prefix) is not SavedLoadServices:
        raise ValueError('Pantheon requires the actual saved service owner')
    backend = prefix.backend
    backend.check_thread()
    core = backend.core
    if (prefix.closed or prefix.quarantined or backend.prefix is not prefix
            or prefix.core is not core or prefix.context != backend.context
            or backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or backend.captured_bundle.reference != REFERENCE
            or getattr(core,'_civ6_host_execution_image',None) is not _XP1_PROFILE):
        raise ValueError('Pantheon requires the exact installed Rise and Fall saved owner')
    if action:
        require_actions()
        from .xp1_action_transport import SavedActionTransport
        from .deferred_service import DeferredService
        if type(prefix.actions) is not SavedActionTransport or type(prefix.deferred_events) is not DeferredService:
            raise ValueError('Pantheon requires the shared saved transport and FIFO')
        prefix.actions.require_transition()
        prefix.deferred_events._check()
    proof,central = verify_source()
    lifetime = (core,prefix)
    if getattr(prefix,'_xp1_pantheon_binding_lifetime',None) == lifetime:
        return
    spans = list(proof['core_bodies'].values()) + list(central['spans'].values())
    spans.extend(row[key] for row in proof['bindings'].values() for key in ('callback','registration'))
    spans.extend(row['registration'] for row in proof['enums'].values())
    signals = _source(SIGNAL_SOURCE)
    spans.extend(dict(rva=row['rva'],bytes=row['length'],sha256=row['sha256'])
                 for row in signals['code_spans'].values())
    for span in spans:
        address = core._handle+int(span['rva'],16)
        raw = b''.join(backend.runtime.read(address+offset,min(4096,span['bytes']-offset))
                       for offset in range(0,span['bytes'],4096))
        if type(raw) is not bytes or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live installed pantheon binding differs')
    for row in signals['callable_vtables'].values():
        raw = backend.runtime.read(core._handle+int(row['rva'],16),row['length'])
        expected = b''.join((core._handle+int(rva,16)).to_bytes(8,'little') for rva in row['target_rvas'])
        if raw != expected:
            raise ValueError('Live installed pantheon signal callable differs')
    prefix._xp1_pantheon_binding_lifetime = lifetime

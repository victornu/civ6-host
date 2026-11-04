"""Exact XP1 capture binding for the existing bounded saved-Load backend.

This module supplies source/input checks and adapters to existing lifecycle
methods. It does not load a DLL, run a session, admit a public profile, create
another scheduler, or replace a missing host callback with a successful result.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .saved_load_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, profile_for_sha
from .configuration_profiles import (
    _source, _body, codec_source, context_copy_source,
)
from .xp1_bundle_inputs import XP1_LAN_PROFILE


REFERENCE = (
    'work/official-capture/xp1-lan-20261030/manifest.json',
    '475f74f15dc4921b3281c9eece768afadbff924c6384f0507d3ea92413c48fcf',
)
CONFIGURATION_BYTES = 35312
CONFIGURATION_SHA256 = 'ae4d3f176ae9d16d3ad5e4aef719eee7ffeff129db69261ba1db601ca4c05aa8'
GAME_BYTES = 6215867
GAME_SHA256 = '8fffd8e843a6f13adfa6efa6278f8c1c45deee9c823287be18b743f715feeb91'
SOURCES = (
    ('work/host-extensions/load-dispatch-static/complete-load-dispatch.json',
     'd3e8f3ada6f37edd1a5baf1bfa59dce93143dbe262fa92d3adb13ecf95d2aef2'),
    ('work/host-extensions/load-prepare-static/prepare-lifecycle-v2.json',
     '615cda7a2fb1ab7e17f3bc726578efd6a1ecbc96482764d6dc2414261a389e5a'),
    ('work/host-extensions/active-list-source/source.json',
     '404cc80b6ebb63a2e95a692a85152ce4df9cebcfc4cd4a90602b4423c5708dc6'),
)


def validate_candidate_inputs(inputs, bundle):
    """Validate only this capture's immutable components and retained owner join.

The parent validates the raw bundle once; the worker consumes the existing
immutable prepared package and registers that exact instance. This check is
deliberately not wired into public validate_profile/admission.
"""
    from .native.native_official_load import OfficialInputs
    from .native.native_official_bundle import PreparedBundle, parse_configuration
    if (type(bundle) is not PreparedBundle or type(inputs) is not OfficialInputs
            or bundle.inputs is not inputs or bundle.reference != REFERENCE
            or inputs.profile is not XP1_LAN_PROFILE
            or inputs.official_bundle != REFERENCE
            or type(inputs.configuration) is not bytes or type(inputs.game) is not bytes
            or inputs.game[:4] != b'\x05\0\0\0'
            or type(bundle.initial_turn) is not int or not 1 <= bundle.initial_turn <= 100000):
        raise ValueError('XP1 candidate requires the exact official captured input pair')
    if inputs.checkpoint is None:
        if (len(inputs.configuration) != CONFIGURATION_BYTES
                or hashlib.sha256(inputs.configuration).hexdigest() != CONFIGURATION_SHA256
                or len(inputs.game) != GAME_BYTES
                or hashlib.sha256(inputs.game).hexdigest() != GAME_SHA256
                or bundle.initial_turn != 1):
            raise ValueError('XP1 original captured input pair changed')
    else:
        from .xp1_session_checkpoint import validate_resumed_inputs
        validate_resumed_inputs(inputs, bundle)
    _, maps = parse_configuration(inputs.configuration, 'LAN')
    if inputs.map_values != maps:
        raise ValueError('XP1 candidate configuration readback fields differ')
    if (bundle.content_profile['engine']['gamecore_sha256'] != XP1_CORE_SHA256
            or tuple(bundle.expected_readback[k] for k in ('turn', 'width', 'height', 'player_id'))
                != (bundle.initial_turn, 74, 46, 0)):
        raise ValueError('XP1 candidate engine/readback identity differs')
    return XP1_LAN_PROFILE


def bind_candidate(bundle, profile, fixture):
    """Reuse a registered input instance and private copies, without raw replay."""
    from .native.native_official_bundle import _reuse_prepared_bundle, validate_fixture
    if (getattr(profile, 'core_sha256', None) != XP1_CORE_SHA256
            or getattr(profile, 'ruleset', None) != 'xp1'
            or getattr(profile, 'mode', None) != 'context'):
        raise ValueError('XP1 candidate requires the exact context-only engine profile')
    validate_candidate_inputs(getattr(bundle, 'inputs', None), bundle)
    _reuse_prepared_bundle(bundle, REFERENCE, 'xp1-lan', _input_only=True)
    validate_fixture(bundle, fixture)
    return profile_for_sha(XP1_CORE_SHA256)


def prepare_input_handoff(destination, *, bundle=None):
    """Parent-only materialization using the existing immutable package format.

If a currently registered complete read_bundle result is available, reuse it.
Otherwise one complete parent validation is necessary. No native deadline or
GameCore process is involved in this materialization function.
"""
    import json
    from . import capture_admission, capture_package
    from .native import native_official_bundle as original
    if capture_admission.configured_reference() is not None:
        raise ValueError('XP1 input preparation must start from the raw validated capture')
    identity = capture_admission.validation_identity()
    if bundle is None:
        bundle = original.read_bundle(REFERENCE, input_profile='xp1-lan')
    original._reuse_prepared_bundle(bundle, REFERENCE, 'xp1-lan', _input_only=True)
    validate_candidate_inputs(bundle.inputs, bundle)
    dependency_digest = hashlib.sha256(json.dumps(bundle.dependencies, sort_keys=True,
        separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')).hexdigest()
    if capture_admission.validation_identity() != identity:
        raise ValueError('XP1 preparation runtime changed during parent validation')
    reference = capture_package.export_capture(bundle, destination,
        source_manifest_bytes=(original.ROOT / REFERENCE[0]).read_bytes(),
        validation_identity=identity, _xp1_candidate=True)
    if capture_admission.validation_identity() != identity:
        raise ValueError('XP1 preparation runtime changed during package materialization')
    return dict(schema='civ6-host.xp1-input-handoff.v1', package=reference,
                origin=dict(path=REFERENCE[0], sha256=REFERENCE[1]),
                original_dependency_count=len(bundle.dependencies),
                original_dependency_pins_sha256=dependency_digest,
                materialization='existing_prepared_capture_format',
                native_execution=False, public_session_admitted=False)


def consume_input_handoff(reference):
    """Worker input validation: hashes real prepared bytes, not 46k raw rows."""
    from . import capture_admission
    capture_admission.configure(reference)
    bundle = capture_admission.try_bundle(REFERENCE, input_profile='xp1-lan', _xp1_candidate=True)
    if bundle is None:
        raise ValueError('XP1 candidate requires its explicit prepared input package')
    validate_candidate_inputs(bundle.inputs, bundle)
    return bundle


def validate_private_bootstrap(manifest, expected, *, private_root):
    """Compare immutable bootstrap data while allowing an exact private ICU copy."""
    from .resource_resolution import resolve_path
    actual = manifest.get('localization_bootstrap')
    if type(actual) is not dict or type(expected) is not dict:
        raise ValueError('XP1 private bootstrap settings are missing')
    def metadata(settings):
        data = dict(settings)
        row = dict(data['icu_data'])
        row.pop('path')
        data['icu_data'] = row
        return data
    if metadata(actual) != metadata(expected):
        raise ValueError('XP1 private bootstrap immutable settings differ')
    root = resolve_path(Path(private_root)).resolve(strict=True)
    raw_path = resolve_path(Path(actual['icu_data']['path']))
    path = raw_path.resolve(strict=True)
    source = resolve_path(Path(expected['icu_data']['path'])).resolve(strict=True)
    if (not raw_path.is_absolute() or raw_path.is_symlink() or raw_path != path
            or path.parent != root or path == source or not path.is_file()):
        raise ValueError('XP1 ICU must be an exact canonical private fixture copy')
    expected_size = expected['icu_data'].get('bytes')
    if expected_size is not None and (type(expected_size) is not int or path.stat().st_size != expected_size):
        raise ValueError('XP1 private ICU byte count differs')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected['icu_data']['sha256']:
        raise ValueError('XP1 private ICU bytes changed')
    return True


def proofs_for_candidate():
    """Reuse configuration ownership proofs; add exact Load source references."""
    _source_bodies()
    return {'provider': codec_source(XP1_CORE_SHA256), 'xp1_saved_load_sources': SOURCES}


def _source_bodies(core_sha256=XP1_CORE_SHA256):
    """Common instruction reader; each expansion retains its own exact ABI."""
    if core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256):
        raise ValueError('Unknown captured saved-Load engine')
    abi = profile_for_sha(core_sha256)
    dispatch, preparation, active = (_source(reference) for reference in SOURCES)
    d, p = dispatch['images'][abi.ruleset], preparation['profiles'][abi.ruleset]
    a = active['profiles'][core_sha256]
    if (dispatch['native_execution'] is not False or preparation['native_execution'] is not False
            or d['image']['sha256'] != core_sha256 or p['image']['sha256'] != core_sha256
            or int(d['outer_vtable_rva'], 16) != abi.outer_vtable_rva
            or int(d['inner_vtable_rva'], 16) != abi.inner_vtable_rva
            or a['layout']['game_vtable_rva'] != abi.game_vtable_rva
            or d['outer_contract']['signature'] != 'int32 Load(void *outer_this, void *reader)'
            or d['outer_contract']['input_r8_used'] is not False
            or d['outer_contract']['inner_eax_preserved'] is not True):
        raise ValueError('Captured saved-Load source identity/ABI changed')
    for vt, slot, target in abi.virtual_targets:
        table = 'outer_slots' if vt == abi.outer_vtable_rva else 'inner_slots'
        if int(p['vtables'][table][hex(slot)]['target_rva'], 16) != target:
            raise ValueError('Captured saved-Load source dispatch differs')
    bodies = {name: _body(body) for name, body in d['functions'].items()}
    bodies.update({'prepare_' + name: _body(row['body']) for name, row in p['targets'].items()})
    bodies.update({'copy_' + name: body for name, body in context_copy_source(abi).items()})
    bodies['game_initialized'] = _body(a['functions'][hex(0x180000000 + abi.game_initialized_rva)])
    return bodies


def verify_live(base, read, proofs):
    """Check retained addressed instructions; never infer one engine's offsets."""
    if (type(base) is not int or not 0 < base < (1 << 63) or not callable(read)
            or proofs.get('xp1_saved_load_sources') != SOURCES
            or proofs.get('provider') != codec_source(XP1_CORE_SHA256)):
        raise ValueError('XP1 candidate source binding is missing or changed')
    seen = {}
    for name, body in _source_bodies().items():
        for fragment in body['fragments']:
            for instruction in fragment['instructions']:
                rva = int(instruction['va'], 16) - 0x180000000
                raw = bytes.fromhex(instruction['bytes'])
                if rva < 0 or not raw or (rva in seen and seen[rva] != raw):
                    raise ValueError('XP1 candidate source instruction conflict: ' + name)
                seen[rva] = raw
    for rva, raw in seen.items():
        if read(base + rva, len(raw)) != raw:
            raise ValueError('XP1 candidate live code differs at RVA ' + hex(rva))
    return {'source_references': SOURCES, 'native_call_made': False, 'public_session_admitted': False}


def prepare_candidate(backend, *, required_ownership_mode):
    """Use qualified context Prepare with the explicit NULL-Tuner diagnostic.

Base ownership/capability callbacks are not installed on XP1. An unimplemented
callback remains the existing host's fatal refusal during the bounded attempt.
"""
    from .native.native_host import prepare_context
    from .native.native_game_configuration import game_configuration_hash
    validate_candidate_inputs(backend.inputs, backend.captured_bundle)
    if (backend.stage != 'B-restored-sealed'
            or required_ownership_mode != game_configuration_hash('LAN')):
        raise ValueError('XP1 candidate Prepare requires its restored LAN configuration')
    backend.topology(game_required=False)
    backend.host.enable_tuner_unavailable_probe()
    receipt = prepare_context(backend.core, backend.context, backend.emit,
                             context_profile=backend.profile, null_tuner_diagnostic=True)
    if backend.game_flag() != 0:
        raise RuntimeError('XP1 prepared Game is already initialized')
    backend.stage = 'prepared'
    return receipt


def attach_services(backend, services):
    """Borrow the actual prepared SavedLoadServices, retaining the one Lua VM."""
    from .saved_load_services import SavedLoadServices
    validate_candidate_inputs(backend.inputs, backend.captured_bundle)
    if (type(services) is not SavedLoadServices or services.backend is not backend
            or services.saved_config_sha != hashlib.sha256(backend.inputs.configuration).hexdigest()
            or services.saved_map_values != backend.inputs.map_values
            or services.contexts.paths or services.contexts.sources):
        raise ValueError('XP1 prefix requires its existing exact captured SavedLoadServices')
    services.attach(backend)


def control_snapshot(backend, *, empty, allow_diplomacy=False, pending_round_actor=None):
    """Inspect actual saved owner queues, including explicitly composed commands."""
    from .saved_load_services import SavedLoadServices
    from .deferred_service import DeferredService
    from .control_input_service import ControlInputService
    from .event_argument_service import EventArgumentService
    from .a0_family_service import A0FamilyService
    if type(empty) is not bool or type(allow_diplomacy) is not bool:
        raise TypeError('XP1 Load control flags must be Boolean')
    if allow_diplomacy or pending_round_actor is not None:
        raise ValueError('XP1 candidate has no admitted action/interrupted-turn control')
    backend.check_thread()
    p = backend.prefix
    if type(p) is not SavedLoadServices or p.backend is not backend:
        raise ValueError('XP1 control requires its actual saved service owner')
    p.check()
    d = getattr(p, 'deferred_events', None)
    controller = getattr(p, 'control_inputs', None)
    arguments = getattr(p, 'event_arguments', None)
    a0 = getattr(p.host, '_a0_family_owner', None)
    if (type(d) is not DeferredService or type(controller) is not ControlInputService
            or type(arguments) is not EventArgumentService or type(a0) is not A0FamilyService
            or d.host is not p.host or d.core is not backend.core or d.context != backend.context
            or controller.deferred is not d or controller.local_player_id != 0
            or arguments.deferred is not d or a0.arguments is not arguments
            or a0.controller_owner is not controller):
        raise ValueError('XP1 Load requires its real deferred/controller/argument/A0 owners')
    d._check(); controller._check(); arguments._check(); a0._check()
    p.events._check(); p.contexts.check(p.contexts.receiver); p.map_arguments.check()
    if (d._draining_empty_receivers or arguments.depth or a0.active_kind is not None
            or a0._active_notification_scope is not None
            or a0._city_command_started_producing or a0._city_command_started_poisoned
            or a0._84c1fdd6_producing or a0._84c1fdd6_poisoned
            or p.events.dispatch_depth or p.events.script_arguments.live_count
            or p.map_arguments.live or p.contexts.depth or p.contexts.lock_depth):
        raise RuntimeError('XP1 Load control has an active or poisoned native consumer')
    for name, check_name in (('status_messages', '_check'), ('player_queries', 'check')):
        owner = getattr(p, name, None)
        if owner is not None:
            getattr(owner, check_name)()
            if owner.depth:
                raise RuntimeError('XP1 Load control has an active ' + name)
    counters = (d._sequence, d.consumed_count, d.host_notification_counter, d.host_metadata_counter)
    if any(type(value) is not int or value < 0 for value in counters):
        raise RuntimeError('XP1 Load control counter is invalid')
    if d.host_notification_counter or d.host_metadata_counter:
        raise RuntimeError('XP1 Load requires closed notification scopes')
    if (type(d.pending) is not list or len(d.pending) > d.limit
            or d.consumed_count > d._sequence
            or len(d.pending) != d._sequence - d.consumed_count):
        raise RuntimeError('XP1 Load deferred ledger is inconsistent')
    actions=getattr(p,'actions',None)
    if actions is not None:
        from .xp1_action_transport import SavedActionTransport
        if type(actions) is not SavedActionTransport or actions.services is not p:
            raise ValueError('XP1 control found a foreign command queue')
        actions.check()
        if empty and actions.pending:raise RuntimeError('XP1 control requires a consumed command queue')
    if empty and d.pending:
        raise RuntimeError('XP1 Load requires a fully consumed deferred queue')
    if a0.private_notification_profile is not None:
        from .a0_private_notifications import get_ring
        ring=get_ring(a0)
        if empty and ring.cursors[ring.selector&1]:
            raise RuntimeError('XP1 control requires consumed private notifications')
    return dict(pending_count=len(d.pending), sequence=d._sequence, consumed=d.consumed_count,
                notification_counter=d.host_notification_counter, metadata_counter=d.host_metadata_counter,
                scope='saved owner services', actions_admitted=False, timers_admitted=False,
                candidate_command_transport_present=actions is not None,
                pending_command_count=len(actions.pending) if actions is not None else None)


def make_job_observer(backend):
    """Use the shared scheduler observer only after its XP1 profile exists."""
    try:
        from .saved_load_job_observer import make_job_observer as factory
    except ModuleNotFoundError as error:
        if error.name != 'civ6_host.runtime.saved_load_job_observer':
            raise
        raise RuntimeError('XP1 saved Load requires the source-qualified scheduler and current-executable observer') from error
    return factory(backend)


def validate_loaded_roster(backend, roster, human_flags):
    """Compare native readback with this captured six-major/one-human scope."""
    from .lan_load import _parse_roster, _parse_humans
    validate_candidate_inputs(backend.inputs, backend.captured_bundle)
    turn, width, height, ids = _parse_roster(roster)
    if (turn, width, height, ids) != (backend.captured_bundle.initial_turn, 74, 46, tuple(range(6))):
        raise ValueError('XP1 loaded roster/map/turn differs from the exact capture')
    humans = _parse_humans(human_flags, ids)
    if humans != (0,) or backend.host.configured_local_player_id != 0:
        raise ValueError('XP1 loaded human/local identity differs from the exact capture')
    return dict(human_player_ids=list(humans), human_status_native_verified=True,
                control_of_all_players_proven=False, simultaneous_execution_qualified=False,
                capture_manifest_sha256=REFERENCE[1], public_session_admitted=False)

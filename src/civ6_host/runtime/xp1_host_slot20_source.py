"""The optional platform service reached by source-qualified XP1 routes."""

import hashlib
from pathlib import Path
import struct

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE, identity


SOURCE = (
    'evidence/host-xp1-capture-optional-achievement-source.json',
    'd0f5f3426490a535c483e0012bd1a0ca48cc1a0034f584ca8c7f766f1334854d',
)
ORIGINAL_SOURCE = (
    'evidence/host-xp1-city-setup-achievement-null-address.json',
    'fab244efc4d9761cf09a30e4bf80d72d0b55975b0e5be53802de3548057c914c',
)
TURN_SOURCE = (
    'evidence/host-xp1-installed-turn-optional-achievement-source.json',
    'b803cbdd948185053019a80d1bc3c32d2ab91002c275833596dc0cbddeedba32',
)
BESIEGED_CITY_SOURCE = (
    'evidence/host-xp1-installed-besieged-city-optional-achievement-source.json',
    '2723d230b0b0d259376bb4843cbba0ec115700523f14601aa441e7814d7dc615',
)
CITY_STATE_CONTACT_SOURCE = (
    'evidence/host-xp1-installed-city-state-contact-optional-achievement-source.json',
    '2d1004f67079ae7f2f15e43366e85432f61a7636b67a39df42e6656f6029e42a',
)
ENVOY_ASSIGNMENT_SOURCE = (
    'evidence/host-xp1-installed-envoy-assignment-optional-achievement-source.json',
    '847f62c4e304ad0ea353011412847f099bb0a0e138619303ad4c9bbd99381ac9',
)
ENVOY_NOTIFICATION_SOURCE = (
    'evidence/host-xp1-installed-envoy-notification-optional-achievement-source.json',
    'e3c9bde32ed312485f85803551f2c695c9f97139a5709b35e4fcf4f34040da06',
)
TURN_LISTENER_SOURCE = (
    'evidence/host-xp1-installed-turn-listener-optional-achievement-source.json',
    '9dd076e960372910095c37d35d42d2dff4ca844e194825cda66806b7a86d4aeb',
)
GOVERNMENT_LISTENER_SOURCE = (
    'evidence/host-xp1-installed-government-listener-optional-achievement-source.json',
    '13d0e1734caeeb60a3e2714b9a57158d2f367589b9d517b9880f74e71f0d2e83',
)
SHARED_BOUNDARY_SOURCE = (
    'work/x1trade/platform-boundary-stage/evidence/host-xp1-shared-optional-platform-boundaries-source.json',
    '514cfd1daa33b3598e00155084d69ae8cde61fed9cf5c32fb4dfc76e01330884',
)
BOUNDARY_CANDIDATE = (
    'work/x1trade/platform-source-audit/xp1-optional-platform-boundaries-candidate.json',
    '0ad445ea9d38b4fb8ba8a63a6bfb5b43b9f0b7d9d01cd7ef2f79b5c49f9187a2',
)
CONTACT_NOTIFICATION_PREFIX = ('0x142cc8', '0x143a1a', '0x27632c', '0x279e00')
GOVERNMENT_NOTIFICATION_TAIL = ('0x100ff3', '0x21c6cd')
LUA_UNLOCK_PREFIX = ('0x142cc8', '0x5f3bdd')
CORE_MODULE = 'GameCore_XP1_FinalRelease.dll'
CALLER_PREFIX = ('0x142cc8', '0x13b0cc', '0x153df4', '0x204ec5', '0x10fa8b')
WORLDBUILDER_CALLER = (*CALLER_PREFIX[:4], '0x205025', '0x5238c1')
TURN_CALLER = ('0x142cc8', '0x143557', '0x100eb4', '0x162775', '0x574767', '0x35fce')
BESIEGED_CITY_CALLER = ('0x142cc8', '0x13affa', '0x100eb4', '0x10e974', '0x2054fd', '0x2bbd57', '0x53b2a')
CITY_STATE_CONTACT_CALLER = ('0x142cc8', '0x143a1a', '0x27632c', '0x279e00', '0x77c06b')
ENVOY_ASSIGNMENT_CALLER = ('0x142cc8', '0x143a1a', '0x27632c', '0x279b85',
                          '0x2771db', '0x277234', '0x28ebac')
# The complete shared observer discards its return before the native influence
# update continues. The outer AI/human operation does not change that contract.
ENVOY_NOTIFICATION_CALLER = ('0x142cc8', '0x143a1a', '0x27632c', '0x279b85')
TURN_LISTENER_TAIL = ('0x4ff23c', '0x1fe3b1', '0x1fe409', '0x58109c')
TURN_LISTENER_SITES = frozenset(('0x13e7aa', '0x13e865', '0x13e8e3', '0x13e95b', '0x13eab8',
                                '0x13eb46', '0x13eb88', '0x13ebfd', '0x13ecd0', '0x13edde',
                                '0x13ee1b'))
GOVERNMENT_LISTENER_TAIL = ('0x100ff3', '0x21c6cd', '0x2b87d', '0x35e73e', '0x35f99a')
GOVERNMENT_LISTENER_TAGS = {'0x13d7d7': 'NEW_ACHIEVEMENT_4_20',
                            '0x13d83f': 'NEW_ACHIEVEMENT_3_13'}
_ADDITIONAL_ROUTES = (
    (TURN_SOURCE, TURN_CALLER, 'turn', 'NEW_ACHIEVEMENT_4_13'),
    (BESIEGED_CITY_SOURCE, BESIEGED_CITY_CALLER, 'besieged-city', 'NEW_ACHIEVEMENT_4_17'),
    (CITY_STATE_CONTACT_SOURCE, CITY_STATE_CONTACT_CALLER, 'city-state-contact', 'NEW_ACHIEVEMENT_4_23'),
    (ENVOY_ASSIGNMENT_SOURCE, ENVOY_ASSIGNMENT_CALLER, 'envoy-assignment', 'NEW_ACHIEVEMENT_4_23'),
    (ENVOY_NOTIFICATION_SOURCE, ENVOY_NOTIFICATION_CALLER, 'envoy-notification', 'NEW_ACHIEVEMENT_4_23'),
)


def source(execution_image):
    if execution_image is not _XP1_PROFILE:
        raise ValueError('XP1 capture achievement requires the registered image')
    proof = _source(SOURCE)
    original = proof['original_private_fixture_proof']
    if (proof['schema'] != 'civ6-host.xp1-capture-optional-achievement.source.v1'
            or proof['image'] != identity(execution_image)
            or (original['path'], original['sha256']) != ORIGINAL_SOURCE
            or proof['core_module'] != CORE_MODULE or proof['caller_prefix'] != CALLER_PREFIX
            or proof['achievement_tag'] != 'NEW_ACHIEVEMENT_4_15'
            or proof['contract'] != dict(slot=32, this_only=True, return_type='optional pointer',
                null_skips_platform_calls=True, listener_return_replaced_before_gameplay_read=True,
                platform_request_submitted=False, platform_success_reported=False,
                other_callers_admitted=False)):
        raise ValueError('XP1 capture achievement source differs')
    previous = _source(ORIGINAL_SOURCE)
    if (previous['schema'] != 'civ6-host.xp1-city-setup-achievement-null-source.v2'
            or previous['engine'] != identity(execution_image)
            or (previous['interface'], previous['slot']) != ('host', 0x20)
            or previous['achievement_tag'] != proof['achievement_tag']
            or previous['core_frames'] != WORLDBUILDER_CALLER
            or previous['source_contract'] != dict(this_only=True, return_type='optional pointer',
                null_skips_both_platform_calls=True, outer_caller_immediately_replaces_return_register=True,
                private_fixture_only=True, gameplay_success_reported=False)
            or proof['host_pointer_load'] != previous['host_pointer_load']
            or proof['host_pointer_rva'] != previous['host_pointer_rva']
            or proof['caller_prefix'][:4] != previous['core_frames'][:4]):
        raise ValueError('XP1 achievement routes lost their shared host lookup or WorldBuilder callsite')
    return proof


def _additional_source(route, execution_image, city_proof):
    reference, caller, name, tag = route
    proof = _source(reference)
    if (proof['schema'] != f'civ6-host.xp1-{name}-optional-achievement.source.v1'
            or proof['image'] != identity(execution_image)
            or proof['core_module'] != CORE_MODULE or proof['caller_prefix'] != caller
            or proof['achievement_tag'] != tag
            or proof['contract'] != city_proof['contract']):
        raise ValueError(f'XP1 {name} achievement source differs')
    return proof


def _turn_listener_source(execution_image, city_proof):
    proof = _source(TURN_LISTENER_SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-turn-listener-optional-achievement.source.v1'
            or proof['image'] != identity(execution_image) or proof['core_module'] != CORE_MODULE
            or (proof['parent']['path'], proof['parent']['sha256']) != SOURCE
            or proof['sink_resume'] != CALLER_PREFIX[0] or proof['dispatcher_tail'] != TURN_LISTENER_TAIL
            or proof['callers'].keys() != TURN_LISTENER_SITES
            or proof['callers']['0x13eb88']['tag'] != 'NEW_ACHIEVEMENT_4_14'
            or proof['contract'] != city_proof['contract']
            or proof['control_flow'] != dict(null_jumps_to=0x142d21,
                listener_continue_uses_no_sink_result=True, listener_tail_return_discarded_by_dispatcher=True,
                dispatcher_tail_return_discarded_by_caller=True,
                research_and_unit_rule_result_computed_elsewhere=True)):
        raise ValueError('XP1 turn listener achievement source differs')
    return proof


def _government_listener_source(execution_image, city_proof):
    proof = _source(GOVERNMENT_LISTENER_SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-government-listener-optional-achievement.source.v1'
            or proof['image'] != identity(execution_image) or proof['core_module'] != CORE_MODULE
            or (proof['parent']['path'], proof['parent']['sha256']) != SOURCE
            or proof['sink_resume'] != CALLER_PREFIX[0]
            or proof['dispatcher_tail'] != GOVERNMENT_LISTENER_TAIL
            or {site: row['tag'] for site, row in proof['callers'].items()} != GOVERNMENT_LISTENER_TAGS
            or proof['contract'] != city_proof['contract']
            or proof['control_flow'] != dict(
                null_jumps_to=0x142d21, first_listener_result_overwritten=True,
                second_listener_result_discarded_by_dispatcher=True,
                dispatcher_result_overwritten_by_government_handler=True,
                government_handler_continues_native_notifications=True)):
        raise ValueError('XP1 government listener achievement source differs')
    return proof


def _shared_boundary_source(execution_image, city_proof):
    proof = _source(SHARED_BOUNDARY_SOURCE)
    expected_parents = {
        'capture': SOURCE,
        'installed-envoy-notification': ENVOY_NOTIFICATION_SOURCE,
        'installed-city-state-contact': CITY_STATE_CONTACT_SOURCE,
        'installed-government-listener': GOVERNMENT_LISTENER_SOURCE,
    }
    expected_boundaries = {
        'city_state_contact': dict(prefix=CONTACT_NOTIFICATION_PREFIX,
            tag='NEW_ACHIEVEMENT_4_23', return_overwrite_rva=0x279e00),
        'government_change': dict(sink_resume=CALLER_PREFIX[0],
            sites=GOVERNMENT_LISTENER_TAGS, dispatcher_tail=GOVERNMENT_NOTIFICATION_TAIL,
            return_overwrite_rva=0x21c6cd),
        'lua_unlock': dict(prefix=LUA_UNLOCK_PREFIX, tag='DLC3_ACHIEVEMENT_10',
            binding='UnlockAchievement', binding_rva=0x5f3b80,
            return_overwrite_rva=0x5f3bdd, lua_result_count=0),
    }
    if (proof['schema'] != 'civ6-host.xp1-shared-optional-platform-boundaries.source.v1'
            or proof['image'] != identity(execution_image) or proof['core_module'] != CORE_MODULE
            or proof['contract'] != city_proof['contract']
            or {name: (row['path'], row['sha256']) for name, row in proof['parents'].items()}
                != expected_parents
            or (proof['candidate']['path'], proof['candidate']['sha256']) != BOUNDARY_CANDIDATE
            or proof['boundaries'] != expected_boundaries
            or proof['control_flow'] != dict(complete_dispatchers_preserve_arguments=True,
                observer_results_not_read=True, contact_caller_replaces_full_rax=True,
                government_caller_replaces_full_rax=True, lua_wrapper_replaces_full_rax=True,
                node_release_final_ret_included=True, outer_origin_not_an_abi_constraint=True)
            or proof['validation'] != dict(native_execution=False, product_integrated=False,
                candidate_spans_verified_against_installed_pe=True)):
        raise ValueError('XP1 shared optional platform boundary source differs')
    # Retain the original proofs and join their actual shared bodies explicitly.
    parents = {name: _source(reference) for name, reference in expected_parents.items()}
    reused = {
        'optional_sink': ('capture', 'optional_service_caller'),
        'contact_listener': ('installed-city-state-contact', 'listener'),
        'contact_caller': ('installed-city-state-contact', 'contact'),
        'contact_dispatcher': ('installed-envoy-notification', 'dispatcher'),
        'government_listener': ('installed-government-listener', 'listener'),
        'government_caller': ('installed-government-listener', 'government_handler'),
    }
    spans = proof['core_spans']
    if (any(spans[name] != parents[parent]['core_spans'][body]
            for name, (parent, body) in reused.items())
            or spans['contact_tag'] != parents['installed-city-state-contact']['tag_span']
            or any(spans['government_tag_' + site] != row['span'] for site, row in
                   parents['installed-government-listener']['callers'].items())
            or (spans['government_dispatcher_complete']['rva'],
                spans['government_dispatcher_complete']['bytes']) != (0x100f90, 0x13e)
            or (spans['shared_node_release_complete']['rva'],
                spans['shared_node_release_complete']['bytes']) != (0x183dc0, 103)
            or (spans['lua_unlock_achievement_complete']['rva'],
                spans['lua_unlock_achievement_complete']['bytes']) != (0x5f3b80, 106)):
        raise ValueError('XP1 shared optional platform source bodies differ')
    return proof


def source_dependencies(*, execution_image):
    proof = source(execution_image)
    _turn_listener_source(execution_image, proof)
    _government_listener_source(execution_image, proof)
    pins = {
        str(_path(SOURCE[0]).resolve()): SOURCE[1],
        str(_path(ORIGINAL_SOURCE[0]).resolve()): ORIGINAL_SOURCE[1],
        str(_path(TURN_LISTENER_SOURCE[0]).resolve()): TURN_LISTENER_SOURCE[1],
        str(_path(GOVERNMENT_LISTENER_SOURCE[0]).resolve()): GOVERNMENT_LISTENER_SOURCE[1],
        str(Path(execution_image.path).resolve()): execution_image.image_sha256,
    }
    for route in _ADDITIONAL_ROUTES:
        _additional_source(route, execution_image, proof)
        path, digest = route[0]
        pins[str(_path(path).resolve())] = digest
    _shared_boundary_source(execution_image, proof)
    for path, digest in (SHARED_BOUNDARY_SOURCE, BOUNDARY_CANDIDATE):
        pins[str(_path(path).resolve())] = digest
    verify_pinned_files(pins)
    return pins


def verify_live(base, read, *, host_pointer, execution_image):
    proof = source(execution_image)
    routes = [proof, *(_additional_source(route, execution_image, proof) for route in _ADDITIONAL_ROUTES)]
    spans = {(span['rva'], span['bytes'], span['sha256'])
             for route in routes
             for span in (*route['core_spans'].values(), route['tag_span'])}
    spans.update((span['rva'], span['size'], span['sha256'])
                 for span in _source(ORIGINAL_SOURCE)['live_spans'])
    for read_listener in (_turn_listener_source, _government_listener_source):
        listener = read_listener(execution_image, proof)
        spans.update((span['rva'], span['bytes'], span['sha256'])
                     for span in (*listener['core_spans'].values(),
                                  *(row['span'] for row in listener['callers'].values())))
    shared = _shared_boundary_source(execution_image, proof)
    spans.update((span['rva'], span['bytes'], span['sha256'])
                 for span in shared['core_spans'].values())
    for rva, size, digest in sorted(spans):
        raw = read(base + rva, size)
        if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Live XP1 achievement caller differs')
    lookup = proof['host_pointer_load']
    raw = read(base + lookup['rva'], lookup['size'])
    if (type(raw) is not bytes or len(raw) != 7 or raw[:3] != bytes.fromhex('48 8b 0d')
            or hashlib.sha256(raw).hexdigest() != lookup['sha256']):
        raise ValueError('Live XP1 achievement host lookup differs')
    displacement, = struct.unpack_from('<i', raw, 3)
    host_rva = lookup['rva'] + len(raw) + displacement
    if (displacement != lookup['signed_disp32'] or host_rva != proof['host_pointer_rva']
            or read(base + host_rva, 8) != struct.pack('<Q', host_pointer)):
        raise ValueError('XP1 achievement caller references another host')
    return dict(verified_spans=len(spans), host_pointer_rva=hex(host_rva))


def require_prepared_owner(backend):
    from .native.native_official_load import OfficialLoadBackend

    if (not isinstance(backend, OfficialLoadBackend)
            or backend.configuration_abi.core_sha256 != XP1_CORE_SHA256
            or getattr(backend.core, '_civ6_host_execution_image', None) is not _XP1_PROFILE
            or backend.runtime.read is None):
        raise ValueError('XP1 achievement service requires its actual saved configuration owner')


def require_active_owner(backend):
    from .xp1_continuation import SavedContinuation

    owner = getattr(backend, '_xp1_continuation', None)
    if type(owner) is not SavedContinuation or owner.owner is not backend:
        raise ValueError('XP1 achievement service requires the active saved-game owner')
    owner.check(active=True)


def select_contract(frames, *, service_installed, execution_image):
    proof = source(execution_image)
    if (service_installed is not False or type(frames) is not list
            or any(type(frame) is not dict or set(frame) != {'module', 'rva'}
                   or type(frame['module']) is not str or type(frame['rva']) is not str
                   for frame in frames)):
        raise ValueError('XP1 achievement caller or optional sink differs')
    core = [frame for frame in frames if frame['module'].startswith('GameCore_')]
    if any(frame['module'] != CORE_MODULE for frame in core):
        raise ValueError('Unproved XP1 optional achievement caller chain')
    callers = tuple(frame['rva'] for frame in core)
    if callers[:len(CALLER_PREFIX)] == CALLER_PREFIX:
        return SOURCE[1]
    if callers == WORLDBUILDER_CALLER:
        return ORIGINAL_SOURCE[1]
    if (len(callers) >= 2 + len(TURN_LISTENER_TAIL) and callers[0] == CALLER_PREFIX[0]
            and callers[1] in TURN_LISTENER_SITES
            and callers[2:2 + len(TURN_LISTENER_TAIL)] == TURN_LISTENER_TAIL):
        _turn_listener_source(execution_image, proof)
        return TURN_LISTENER_SOURCE[1]
    if (len(callers) >= 2 + len(GOVERNMENT_LISTENER_TAIL) and callers[0] == CALLER_PREFIX[0]
            and callers[1] in GOVERNMENT_LISTENER_TAGS
            and callers[2:2 + len(GOVERNMENT_LISTENER_TAIL)] == GOVERNMENT_LISTENER_TAIL):
        _government_listener_source(execution_image, proof)
        return GOVERNMENT_LISTENER_SOURCE[1]
    for route in _ADDITIONAL_ROUTES:
        reference, caller, _, _ = route
        if callers[:len(caller)] == caller:
            _additional_source(route, execution_image, proof)
            return reference[1]
    # Legacy routes above keep their original proof identities. New outer
    # origins stop at the first independently proved result-discard boundary.
    if (callers[:len(CONTACT_NOTIFICATION_PREFIX)] == CONTACT_NOTIFICATION_PREFIX
            or callers[:len(LUA_UNLOCK_PREFIX)] == LUA_UNLOCK_PREFIX
            or (len(callers) >= 4 and callers[0] == CALLER_PREFIX[0]
                and callers[1] in GOVERNMENT_LISTENER_TAGS
                and callers[2:4] == GOVERNMENT_NOTIFICATION_TAIL)):
        _shared_boundary_source(execution_image, proof)
        return SHARED_BOUNDARY_SOURCE[1]
    raise ValueError('Unproved XP1 optional achievement caller chain')

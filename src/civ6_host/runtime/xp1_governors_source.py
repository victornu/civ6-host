"""Installed Rise and Fall governor panels and native notification sources."""

from hashlib import sha256
from pathlib import Path
from types import MappingProxyType

from .a0_family_source import A0FamilyProfile
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE, identity
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = (
    'evidence/host-xp1-installed-governor-source.json',
    '0ff5a199ad26508dffbe9d4147320619b3e8f4099f1f2384cc1be6651447d2fa',
)
REQUEST_SOURCE = SOURCE
ESTABLISHMENT_SOURCE = (
    'evidence/host-xp1-installed-governor-establishment-source.json',
    '5c29dd6fa0c160a8f8bbca82cfd61e4b11251076cc4941056634f590f725e4db',
)
ESTABLISHED = 0xdb0807b6
_GESTURE_EVENTS = {
    0xcf9c73f1: (0xdf, 112, 'GameCoreEvent::GovernorAssigned'),
    0x8c6b2399: (0xe2, 96, 'GameCoreEvent::GovernorPromoted'),
}
EVENTS = {**_GESTURE_EVENTS, ESTABLISHED: (0xe3, 112, 'GameCoreEvent::GovernorEstablished')}


def supports(bundle, image):
    return bundle == REFERENCE and image is _XP1_PROFILE


def source(image=_XP1_PROFILE):
    if image is not _XP1_PROFILE:
        raise ValueError('Governors require the installed Rise and Fall image')
    from .xp2_governors_source import _CONSTANTS

    proof = _source(SOURCE)
    bundle = proof['official_capture']
    if (proof['schema'] != 'civ6-host.xp1-installed-governors.source.v1'
            or proof['image'] != identity(image)
            or (Path(bundle['path']).as_posix(), bundle['sha256']) != REFERENCE
            or {name: row['unsigned32'] for name, row in proof['constants'].items()} != _CONSTANTS
            or proof['xp1_assignment'] != dict(own_cities=True, met_city_states=True,
                other_major_destinations=False, city_state_test_argument_count=2,
                current_destination_uses_assigned_governor_identity=True)
            or {int(k, 16): (r['record'], r['size'], r['name'])
                for k, r in proof['events'].items()} != _GESTURE_EVENTS):
        raise ValueError('Rise and Fall governor source identity or scope differs')
    return proof


def establishment_source(image=_XP1_PROFILE):
    proof = _source(ESTABLISHMENT_SOURCE)
    parent = source(image)
    if (proof['schema'] != 'civ6-host.xp1-installed-governor-establishment.source.v1'
            or proof['image'] != parent['image'] or proof['executable'] != parent['executable']
            or (proof['parent']['path'], proof['parent']['sha256']) != SOURCE
            or {int(k, 16): (r['record'], r['size'], r['name'])
                for k, r in proof['events'].items()} != {ESTABLISHED: EVENTS[ESTABLISHED]}):
        raise ValueError('Rise and Fall governor establishment source differs')
    row = proof['events'][hex(ESTABLISHED)]
    if (row['selector'] != 0 or row['descriptor_kind'] != 2
            or row['record_descriptor_offset'] != 88 or row['record_scalar_offsets'] != (96, 100)
            or row['variant_keys'] != ('0xa1e5a149', '0x23739f42', '0xd6fcf3e4', '0xa1fbc372')):
        raise ValueError('Rise and Fall governor establishment record differs')
    return proof


def event_source(kind):
    if kind == ESTABLISHED:
        return establishment_source()['events'][hex(kind)], ESTABLISHMENT_SOURCE[1]
    return source()['events'][hex(kind)], SOURCE[1]


def _path(ref):
    path = Path(ref['path'])
    return resolve_path(path if path.is_absolute() else resource_root() / path).resolve()


def source_dependencies(image):
    from .xp1_player_age_source import source_dependencies as age_dependencies
    from .xp1_city_state_envoys import source_dependencies as envoy_dependencies
    from .xp1_city_state_levies import source_dependencies as levy_dependencies
    from . import xp1_turn_history_source as turn_history

    proof = source(image)
    establishment = establishment_source(image)
    turn = turn_history.source(image)
    if turn['executable'] != proof['executable']:
        raise ValueError('Rise and Fall history and governor EXE pins differ')
    pins = {str((resource_root() / path).resolve()): sha
            for path, sha in (SOURCE, ESTABLISHMENT_SOURCE, turn_history.SOURCE)}
    for row in (*proof['official_ui'].values(), proof['executable'],
                *establishment['shared_receiver_sources'], *turn['shared_xp2_sources']):
        pins[str(_path(row))] = row['sha256']
    return {**pins, **envoy_dependencies(image), **levy_dependencies(image), **age_dependencies(image)}


def support_source():
    ref = source()['official_ui']['GovernorSupport.lua']
    raw = _path(ref).read_bytes()
    if len(raw) != ref['bytes'] or sha256(raw).hexdigest() != ref['sha256']:
        raise ValueError('Rise and Fall GovernorSupport source changed')
    return raw


def operation_parameters(action):
    from .xp2_governors_source import encode_operation
    return encode_operation(action, source()['constants'])


def _verify_live(base, read, spans):
    for span in spans:
        raw = read(base + span['rva'], span['bytes'])
        if type(raw) is not bytes or len(raw) != span['bytes'] or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError(f"Live Rise and Fall governor binding differs at {span['rva']:#x}")


def bind_owner(saved, *, active):
    if active:
        saved._check_active()
    else:
        saved._check_query()
    b, p = saved.backend, saved.prefix
    core = b.core
    image = getattr(core, '_civ6_host_execution_image', None)
    if (getattr(saved, 'xp1_governors_enabled', False) is not True
            or b.load_abi.core_sha256 != XP1_CORE_SHA256
            or not supports(saved.inputs.official_bundle, image)):
        raise ValueError('Governors require the exact admitted Rise and Fall LAN owner')
    lifetime = (core, p)
    if getattr(saved, '_xp1_governor_lifetime', None) == lifetime:
        return
    proof = source(image)
    spans = [span for row in proof['bindings'].values() for span in row.values()]
    spans.extend(row['span'] for row in proof['constants'].values())
    _verify_live(core._handle, b.runtime.read, spans)
    saved._xp1_governor_lifetime = lifetime


def history_profile(backend, read):
    from . import xp1_player_age_source as age
    from . import xp1_turn_history_source as turn_history

    core = backend.core
    image = getattr(core, '_civ6_host_execution_image', None)
    if not supports(backend.inputs.official_bundle, image):
        raise ValueError('Governor notifications require the exact Rise and Fall capture')
    events = {**source(image)['events'], **establishment_source(image)['events']}
    spans = [span for row in events.values() for span in row['producer']]
    spans.extend(turn_history.source(image)['producer'])
    _verify_live(core._handle, read, spans)
    age.verify_live(core, read)
    records = {kind: frozenset((record,)) for kind, (record, _, _) in EVENTS.items()}
    sizes = {record: size for record, size, _ in EVENTS.values()}
    records[turn_history.KIND] = frozenset((turn_history.RECORD,))
    sizes[turn_history.RECORD] = turn_history.SIZE
    records.update({kind: frozenset((record,)) for kind, (record, _) in age.EVENTS.items()})
    sizes.update({record: age.SIZE for record, _ in age.EVENTS.values()})
    return A0FamilyProfile(
        MappingProxyType(records), MappingProxyType(sizes), SOURCE[1])


def receiver_row(record_type):
    for kind, (record, size, name) in EVENTS.items():
        if record == record_type:
            row, proof = event_source(kind)
            receiver = row['exe']['receiver']
            return dict(event_name=name, handler_va=hex(0x140000000 + receiver['rva']),
                        record_sizes={size}, handler_body_sha256=receiver['sha256'],
                        source_sha256=proof)
    raise ValueError('Unknown Rise and Fall governor receiver')

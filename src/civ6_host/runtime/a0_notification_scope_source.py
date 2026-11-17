"""Explicit counter-independent A0 scope profile; no native execution admission."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType

RESEARCH_CHANGED = 0x48062f97
QUEST_CHANGED = 0xd7111ffd
INFLUENCE_GIVEN = 0x65c1d0a2
_TWO_VALUE_FIELDS = {0xa1e5a149: 3, 0xd6fcf3e4: 2, 0xa1fbc372: 2}
RESEARCH_SOURCE = ('evidence/host-xp2-current-research-notification-scope.json',
                   '7335d1723e3e6fcfc92846a4a0008bf34822ca1a3733ade79a85b7c31ad139ef')
XP1_RESEARCH_SOURCE = ('evidence/host-xp1-current-research-notification-scope.json',
                       'a3601346e1f62578ad7f1101834fe23fdd34ebf0cdecd6d6aed5e1fe8b037bc5')
XP1_QUEST_SOURCE = ('evidence/host-xp1-quest-notification-scope-source.json',
                    '9e84c90e63cf0f71e3bdbe0b61fe38a3d1af2931b42e42a8f08a62b598a858df')
_XP1_INFLUENCE_SOURCE = ('evidence/host-xp1-influence-notification-scope-source.json',
                        'efe332e86e2f358a0eeec902ccdf3180fa4a6b30bbe795427def1c2bc12101e7')
_XP1_CITY_STATE = {
    QUEST_CHANGED: (XP1_QUEST_SOURCE, 'quest', 'QuestChanged', 0xd4, _TWO_VALUE_FIELDS),
    INFLUENCE_GIVEN: (_XP1_INFLUENCE_SOURCE, 'influence', 'InfluenceGiven', 0xd2,
                      {0xa1e5a149: 3, 0xd6fcf3e4: 2}),
}
XP2_CITY_STATE_SOURCE = ('work/x1trade/xp2-city-state-scope-source-stage/source.json',
                         '46890fd0e5d33a33483f35bde3d9c7215beda78e4a4407eb5be30c3ffd57acec')


@dataclass(frozen=True)
class A0NotificationScopeProfile:
    records: object
    proof_sha256s: tuple[str, ...]


def _research_source(execution_image):
    from .a0_policy_unlock_current import CURRENT_PROFILE_ID, CURRENT_EXE_SHA256, _require_image
    from .configuration_profiles import _source
    from .execution_images import _XP1_PROFILE, identity

    if execution_image is _XP1_PROFILE:
        reference, engine = XP1_RESEARCH_SOURCE, 'xp1'
    elif getattr(execution_image, 'id', None) == CURRENT_PROFILE_ID:
        _require_image(execution_image)
        reference, engine = RESEARCH_SOURCE, 'xp2'
    else:
        return None
    proof = _source(reference)
    event = proof['event']
    if (proof['schema'] != f'civ6-host.{engine}-current-research-notification-scope.v1'
            or proof['image_hashes'] != {'exe': CURRENT_EXE_SHA256, 'core': execution_image.image_sha256}
            or (event['kind'], event['type'], event['size'], event['metadata_flag']) !=
               (hex(RESEARCH_CHANGED), 186, 96, 0)
            or event['empty_subscriber_state_required'] is not True
            or event['core_internal_dispatch_retained'] is not True):
        raise ValueError('Current ResearchChanged notification source differs')
    if execution_image is _XP1_PROFILE:
        parent = proof['shared_xp2_source']
        if (proof['image'] != identity(execution_image)
                or (parent['path'], parent['sha256']) != RESEARCH_SOURCE
                or event['exe_spans'] != _source(RESEARCH_SOURCE)['event']['exe_spans']):
            raise ValueError('Rise and Fall ResearchChanged shared EXE source differs')
    return event, reference


def _city_state_source(execution_image, kind):
    from .a0_policy_unlock_current import CURRENT_EXE_SHA256
    from .configuration_profiles import _source
    from .execution_images import _PROFILE, _XP1_PROFILE, identity

    if execution_image is not _XP1_PROFILE and execution_image is not _PROFILE:
        return None
    reference, family, name, record_type, fields = _XP1_CITY_STATE[kind]
    if execution_image is _XP1_PROFILE:
        proof = _source(reference)
        if proof['schema'] != f'civ6-host.xp1-{family}-notification-scope.source.v1':
            raise ValueError(f'Rise and Fall {name} notification source differs')
        identity_proof = proof
    else:
        from . import xp2_bbg_inputs, xp2_bundle_inputs
        reference = XP2_CITY_STATE_SOURCE
        identity_proof = _source(reference)
        captures = tuple((row['path'], row['sha256']) for row in identity_proof['admitted_captures'])
        if (identity_proof['schema'] != 'civ6-host.xp2-city-state-notification-scope.source.v1'
                or captures != (xp2_bundle_inputs.REFERENCE, xp2_bbg_inputs.REFERENCE)
                or set(identity_proof['records']) != {hex(key) for key in _XP1_CITY_STATE}):
            raise ValueError('Gathering Storm city-state notification capture or record identity differs')
        proof = identity_proof['records'][hex(kind)]
    if (identity_proof['image'] != identity(execution_image)
            or identity_proof['executable']['sha256'] != CURRENT_EXE_SHA256
            or proof['event'] != {
                'name': f'GameCoreEvent::{name}', 'kind': hex(kind),
                'record': record_type, 'size': 96, 'flag': 0, 'selector': 0,
                'typed_input': {hex(key): tag for key, tag in fields.items()},
                'payload_offsets': (84, 88), 'empty_receiver_required': True,
                'core_internal_dispatch_retained': True, 'host_counters_retained': True,
            }):
        raise ValueError(f'Installed {name} notification source differs')
    return proof, reference, identity_proof


def _verify_live(name, spans, core_base, read):
    for row in spans:
        data = read(core_base + int(row['rva'], 16), row['bytes'])
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError(f"Live {name} source differs at {row['rva']}")


def verify_research_changed_live(execution_image, core_base, read):
    selected = _research_source(execution_image)
    if selected is None:
        raise ValueError('ResearchChanged requires an exact installed expansion scope')
    event, _ = selected
    _verify_live('ResearchChanged', event['live_core_spans'], core_base, read)


def verify_city_state_live(execution_image, core_base, read):
    for kind in _XP1_CITY_STATE:
        selected = _city_state_source(execution_image, kind)
        if selected is None:
            raise ValueError('City-state notifications require an exact installed expansion scope')
        proof, _, _ = selected
        _verify_live(proof['event']['name'], proof['live_core_spans'].values(), core_base, read)


def city_state_receiver_row(execution_image, record_type):
    kind, = (kind for kind, row in _XP1_CITY_STATE.items() if row[3] == record_type)
    proof, reference, _ = _city_state_source(execution_image, kind)
    receiver = proof['exe_spans']['handler']
    return dict(event_name=proof['event']['name'], record_sizes={proof['event']['size']},
                handler_va=hex(0x140000000 + int(receiver['rva'], 16)),
                handler_body_sha256=receiver['sha256'], source_sha256=reference[1])


def dispatch_scoped_two_value(owner, kind, fields):
    """Use the shared scalar codec under the separately admitted counter scope."""
    from .native.native_two_value_event_family import encode_core_fields

    if owner.active_kind != kind or owner._active_notification_scope is None:
        raise ValueError('Scoped two-value event requires its active A0 scope')
    image = getattr(owner.deferred.core, '_civ6_host_execution_image', None)
    if kind in _XP1_CITY_STATE:
        selected = _city_state_source(image, kind)
        if selected is None:
            raise ValueError('City-state notification requires the selected installed image')
        proof, reference, _ = selected
        engine = 'xp2' if reference == XP2_CITY_STATE_SOURCE else 'xp1'
        suffix = 'quest_changed' if kind == QUEST_CHANGED else 'influence_given'
        stage = f'{engine}_scoped_{suffix}_enqueued'
        record_type = hex(proof['event']['record'])
    elif kind == RESEARCH_CHANGED:
        selected = _research_source(image)
        if selected is None:
            raise ValueError('ResearchChanged requires the selected installed image')
        _, reference = selected
        stage = ('xp1_scoped_research_changed_enqueued' if reference == XP1_RESEARCH_SOURCE
                 else 'xp2_current_scoped_research_changed_enqueued')
        record_type = '0xba'
    else:
        raise ValueError('Unknown scoped two-value event')
    record = encode_core_fields(kind, owner._sequence + 1, fields,
        optional_callback_present=owner.per_thread_hook_present,
        queue_metadata_service_present=owner.writer_metadata_callback_present)
    owner._enqueue(record)
    owner.emit(stage, dispatch_kind=hex(kind),
               queue_type=record_type, sequence=owner._sequence, record_hex=record.hex(),
               notification_counter=owner.host_notification_counter,
               metadata_counter=owner.host_metadata_counter, source_sha256=reference[1])
    return 0


def notification_scope_profile(*, execution_image=None, capture_reference=None, script_hashes=None):
    """Reuse the retained producer/receiver proofs without widening their shapes."""
    from .native import native_scalar_notification_scope as scalar
    from .native import native_counter_neutral_scope as neutral
    from .native import native_f26f3acf_counter_scope as notification
    from .a0_family_source import family_profile
    from . import xp1_diplomacy_meet_source as diplomacy_meet

    scalar.verify_source_evidence()
    neutral.verify_source()
    notification.verify_source_evidence()
    expected_scalar = {
        0x1F943311: (0x11F, 96, 0), 0x3FEAAD02: (0xB3, 112, 4),
        0xBF48FDA8: (0xB2, 112, 4), 0x8FEF0D8E: (0x120, 96, 0),
    }
    expected_neutral = {
        0xB1A27578: (0x92, 96, 0), 0xF7807FF9: (0x75, 96, 0),
        0x13AE3A55: (0x95, 96, 0), 0x265857F7: (0x8D, 96, 0),
        0xD857B21B: (0x93, 128, 0),
    }
    if (dict(scalar.RECORDS) != expected_scalar
            or dict(neutral.RECORD_TYPE_BY_KIND) != {
                kind: row[0] for kind, row in expected_neutral.items()}):
        raise ValueError('Nonzero A0 source membership differs')
    if (notification.RECORD_TYPE, notification.RECORD_SIZE) != (0x100, 96):
        raise ValueError('NotificationAdded source record differs')
    records = {**expected_scalar, **expected_neutral, 0xF26F3ACF: (0x100, 96, 4)}
    research = _research_source(execution_image)
    if research is not None:
        event, _ = research
        records[RESEARCH_CHANGED] = (event['type'], event['size'], event['metadata_flag'])
    city_state_sources = set()
    from .execution_images import _PROFILE, _XP1_PROFILE
    from . import xp2_local_player_changed
    from . import xp2_bbg_inputs, xp2_bundle_inputs
    local_player_changed = (execution_image is _PROFILE
                            and xp2_local_player_changed.supports_script_hashes(script_hashes))
    if local_player_changed:
        xp2_local_player_changed.source()
        records[xp2_local_player_changed.KIND] = xp2_local_player_changed.RECORD
    xp2_capture = (execution_image is _PROFILE
                   and capture_reference in (xp2_bundle_inputs.REFERENCE, xp2_bbg_inputs.REFERENCE))
    if execution_image is _XP1_PROFILE or xp2_capture:
        for kind in _XP1_CITY_STATE:
            proof, reference, _ = _city_state_source(execution_image, kind)
            event = proof['event']
            records[kind] = (event['record'], event['size'], event['flag'])
            city_state_sources.add(reference[1])
    meeting_reference = None
    if diplomacy_meet.scope_supported(execution_image, capture_reference):
        diplomacy_meet.source(execution_image)
        meeting_reference = diplomacy_meet.source_reference(execution_image)
        records.update(diplomacy_meet.RECORDS)
    initial = family_profile()
    for kind, (record_type, size, _) in records.items():
        if (initial.record_types_by_kind.get(kind) != frozenset({record_type})
                or initial.record_sizes.get(record_type) != size):
            raise ValueError('Nonzero A0 scope lies outside the existing codec profile')
    return A0NotificationScopeProfile(MappingProxyType(records), (
        scalar.PROOF_SHA256, neutral.PROOF_SHA256,
        neutral._CLOSED_SCOPE_PROOFS[0x265857F7][1],
        neutral._CLOSED_SCOPE_PROOFS[0xD857B21B][1],
        notification.PROOF_SHA256,
        *((research[1][1],) if research is not None else ()),
        *((xp2_local_player_changed.SOURCE[1],) if local_player_changed else ()),
        *sorted(city_state_sources),
        *((meeting_reference[1],) if meeting_reference is not None else ()),
    ))


def source_dependencies(*, execution_image=None):
    """Pin the same scope proofs and their declared immediate parent sources."""
    import json
    from pathlib import Path
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .native import native_scalar_notification_scope as scalar
    from .native import native_counter_neutral_scope as neutral
    from .native import native_f26f3acf_counter_scope as notification
    from . import xp1_diplomacy_meet_source as diplomacy_meet
    roots = [(scalar.PROOF_PATH, scalar.PROOF_SHA256),
             (neutral.PROOF_PATH, neutral.PROOF_SHA256),
             (notification.PROOF_PATH, notification.PROOF_SHA256)]
    roots.extend((resource_root()/row[0], row[1])
                 for row in neutral._CLOSED_SCOPE_PROOFS.values())
    pins = {}

    def pin(path, expected):
        path = resolve_path(path).resolve()
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            raise ValueError('Notification scope source changed: '+str(path))
        name = str(path)
        if name in pins and pins[name] != expected:
            raise ValueError('Conflicting scope source pins')
        pins[name] = expected
        return path

    def parents(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
                relative = Path(value['path'].replace('\\', '/'))
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('Scope parent path escaped private resources')
                pin(resource_root()/relative, value['sha256'])
            else:
                for child in value.values():
                    parents(child)
        elif isinstance(value, list):
            for child in value:
                parents(child)

    for path, expected in roots:
        path = pin(path, expected)
        parents(json.loads(path.read_text(encoding='utf-8')).get('parents', {}))
    research = _research_source(execution_image)
    if research is not None:
        _, reference = research
        pin(resource_root()/reference[0], reference[1])
        if reference == XP1_RESEARCH_SOURCE:
            pin(resource_root()/RESEARCH_SOURCE[0], RESEARCH_SOURCE[1])
    for kind in _XP1_CITY_STATE:
        selected = _city_state_source(execution_image, kind)
        if selected is not None:
            proof, (path, digest), identity_proof = selected
            pin(resource_root()/path, digest)
            for row in identity_proof['parents']:
                parents(dict(row))
            for row in (identity_proof['executable'], *proof['stock_ui_subscribers']):
                pin(Path(row['path']), row['sha256'])
    for path, expected in diplomacy_meet.source_dependencies(execution_image).items():
        pin(Path(path), expected)
    return pins


def require_scope_fields(kind, fields):
    """Keep scoped field shapes within their captured source boundaries."""
    if kind == 0x265857F7:
        from .native.native_event_265857f7 import BLOB_KEY, SELECTOR_KEY
        if type(fields) is not dict or set(fields) != {BLOB_KEY, SELECTOR_KEY}:
            raise ValueError('Nonzero ResourceRemoved scope requires the original two-field profile')
    if kind in (RESEARCH_CHANGED, QUEST_CHANGED) and (
            type(fields) is not dict or fields.keys() != _TWO_VALUE_FIELDS.keys()):
        raise ValueError('Scoped two-value notification requires all three scalar fields')
    if kind == INFLUENCE_GIVEN and (
            type(fields) is not dict or fields.keys() != _XP1_CITY_STATE[kind][4].keys()):
        raise ValueError('Scoped InfluenceGiven requires the two native scalar fields')
    from .xp1_diplomacy_meet_source import RECORDS
    if kind in RECORDS:
        from .native.native_event_133d411c import SELECTOR_KEY, SECOND_KEY, UNIT_KEY, VALUE_KEY

        required = {SELECTOR_KEY, VALUE_KEY, SECOND_KEY}
        if type(fields) is not dict or set(fields) not in (required, required | {UNIT_KEY}):
            raise ValueError('Scoped diplomacy contact requires its exact native fields')


"""Explicit counter-independent A0 scope profile; no native execution admission."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType

RESEARCH_CHANGED = 0x48062f97
RESEARCH_SOURCE = ('evidence/host-xp2-current-research-notification-scope.json',
                   '7335d1723e3e6fcfc92846a4a0008bf34822ca1a3733ade79a85b7c31ad139ef')


@dataclass(frozen=True)
class A0NotificationScopeProfile:
    records: object
    proof_sha256s: tuple[str, ...]


def _research_source(execution_image):
    from .a0_policy_unlock_current import CURRENT_PROFILE_ID, CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image
    from .configuration_profiles import _source

    if getattr(execution_image, 'id', None) != CURRENT_PROFILE_ID:
        return None
    _require_image(execution_image)
    proof = _source(RESEARCH_SOURCE)
    event = proof['event']
    if (proof['schema'] != 'civ6-host.xp2-current-research-notification-scope.v1'
            or proof['image_hashes'] != {'exe': CURRENT_EXE_SHA256, 'core': CURRENT_CORE_SHA256}
            or (event['kind'], event['type'], event['size'], event['metadata_flag']) !=
               (hex(RESEARCH_CHANGED), 186, 96, 0)
            or event['empty_subscriber_state_required'] is not True
            or event['core_internal_dispatch_retained'] is not True):
        raise ValueError('Current ResearchChanged notification source differs')
    return event


def verify_research_changed_live(execution_image, core_base, read):
    event = _research_source(execution_image)
    if event is None:
        raise ValueError('ResearchChanged requires the exact current XP2 scope')
    for row in event['live_core_spans']:
        data = read(core_base + int(row['rva'], 16), row['bytes'])
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Live ResearchChanged source differs at ' + row['rva'])


def dispatch_scoped_research(owner, fields):
    """Use the shared scalar codec under the separately admitted counter scope."""
    from .native.native_two_value_event_family import encode_core_fields

    if owner.active_kind != RESEARCH_CHANGED or owner._active_notification_scope is None:
        raise ValueError('ResearchChanged requires its active A0 scope')
    record = encode_core_fields(RESEARCH_CHANGED, owner._sequence + 1, fields,
        optional_callback_present=owner.per_thread_hook_present,
        queue_metadata_service_present=owner.writer_metadata_callback_present)
    owner._enqueue(record)
    owner.emit('xp2_current_scoped_research_changed_enqueued', dispatch_kind=hex(RESEARCH_CHANGED),
               queue_type='0xba', sequence=owner._sequence, record_hex=record.hex(),
               notification_counter=owner.host_notification_counter,
               metadata_counter=owner.host_metadata_counter, source_sha256=RESEARCH_SOURCE[1])
    return 0


def notification_scope_profile(*, execution_image=None):
    """Reuse the retained producer/receiver proofs without widening their shapes."""
    from .native import native_scalar_notification_scope as scalar
    from .native import native_counter_neutral_scope as neutral
    from .native import native_f26f3acf_counter_scope as notification
    from .a0_family_source import family_profile

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
        records[RESEARCH_CHANGED] = (research['type'], research['size'], research['metadata_flag'])
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
        *((RESEARCH_SOURCE[1],) if research is not None else ()),
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
    if _research_source(execution_image) is not None:
        pin(resource_root()/RESEARCH_SOURCE[0], RESEARCH_SOURCE[1])
    return pins


def require_scope_fields(kind, fields):
    """Keep scoped field shapes within their captured source boundaries."""
    if kind == 0x265857F7:
        from .native.native_event_265857f7 import BLOB_KEY, SELECTOR_KEY
        if type(fields) is not dict or set(fields) != {BLOB_KEY, SELECTOR_KEY}:
            raise ValueError('Nonzero ResourceRemoved scope requires the original two-field profile')
    if kind == RESEARCH_CHANGED and set(fields) != {0xa1e5a149, 0xd6fcf3e4, 0xa1fbc372}:
        raise ValueError('Nonzero ResearchChanged scope requires all three scalar fields')


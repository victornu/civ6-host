"""Explicit counter-independent A0 scope profile; no native execution admission."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class A0NotificationScopeProfile:
    records: object
    proof_sha256s: tuple[str, ...]


def notification_scope_profile():
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
    ))


def source_dependencies():
    """Pin the same scope proofs and their declared immediate parent sources."""
    import hashlib
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
    return pins


def require_scope_fields(kind, fields):
    """The retained 265857F7 scope proof covers only its original two-field path."""
    if kind == 0x265857F7:
        from .native.native_event_265857f7 import BLOB_KEY, SELECTOR_KEY
        if type(fields) is not dict or set(fields) != {BLOB_KEY, SELECTOR_KEY}:
            raise ValueError('Nonzero ResourceRemoved scope requires the original two-field profile')


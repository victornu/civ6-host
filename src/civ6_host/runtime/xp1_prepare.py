"""Shared XP1 service preparation; this does not admit saved-game Load.

Existing native type/archive/localization adapters are composed here. The
explicit NULL-Tuner mode is a bounded diagnostic, never a gameplay fallback.
"""
from __future__ import annotations

import hashlib
import json

from .paths import resource_root

NULL_TUNER_PROOF = (
    'work/host-extensions/xp1-tuner-absence/analysis.json',
    '9b55c5c7b0536d5d298c5d61d59808e270200c148b13a2b052282de7cb61f2bb',
)


def source_dependencies():
    from .native import native_xp1_archive_access as access
    from .native import native_xp1_archive_registration as registration
    from .native import native_xp1_prepare_dispatch as dispatch
    from .native import native_xp1_prepare_type_registry as registry

    return (
        NULL_TUNER_PROOF,
        *dispatch.PROOF_PINS.values(), *dispatch.SOURCE_PINS.items(),
        *access.BASE_SOURCE_PINS.items(),
        (access.DESCRIPTOR_PROOF_RELATIVE, access.DESCRIPTOR_PROOF_SHA256),
        (access.AUDIT_PROOF_RELATIVE, access.AUDIT_PROOF_SHA256),
        *registration.SOURCE_PINS.items(),
        (registration.AUDIT843_RELATIVE, registration.AUDIT843_SHA256),
        (registration.REGISTRATION_PROOF_RELATIVE, registration.REGISTRATION_PROOF_SHA256),
        (registration.HOST_PROOF_RELATIVE, registration.HOST_PROOF_SHA256),
        (registry.CONTRACT_MANIFEST_REL, registry.CONTRACT_MANIFEST_SHA256),
        (registry.CONTRACT_REL, registry.CONTRACT_SHA256),
        ('evidence/native-xp1-teardown818-v2.json', registry.TEARDOWN_PROOF_SHA256),
    )


def require_null_tuner_diagnostic(host, enabled):
    """Only the recorded local acquisition/cleanup branch is admitted."""
    if enabled is not True or getattr(host, 'tuner_unavailable_probe', False) is not True:
        raise ValueError('XP1 NULL Tuner requires explicit diagnostic admission')
    root = resource_root()
    raw = (root / NULL_TUNER_PROOF[0]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != NULL_TUNER_PROOF[1]:
        raise ValueError('XP1 NULL Tuner acquisition/cleanup proof changed')
    json.loads(raw)
    return {'proof_sha256': NULL_TUNER_PROOF[1], 'scope': 'Prepare/Destroy only',
            'gameplay_optional_proven': False, 'eligible_for_training': False}


def prepare(core, context, host, profile, emit, *, null_tuner_diagnostic=False):
    from .native.native_core_context_profiles import profile_for_core
    from .native.native_probe import Windows
    from .native.native_xp1_prepare_type_registry import (
        install_prepare_type_registry, prepare_registration_receipt)
    from .native.native_xp1_archive_access import install_xp1_archive_access
    from .native.native_xp1_archive_registration import (
        install_xp1_archive_registration, archive_registration_receipt)
    from .native.native_localization import initialize_localization
    from .native.native_xp1_prepare_dispatch import prepare_xp1_context

    actual = profile_for_core(core._name, mode='context',
                              shared_dependency_directory=host.dll_directory)
    if profile != actual or (profile.ruleset, profile.mode) != ('xp1', 'context'):
        raise ValueError('XP1 Prepare requires the exact initialized context profile')
    if getattr(host, '_xp1_prepare_entered', False):
        raise ValueError('XP1 Prepare has already been entered')
    if null_tuner_diagnostic:
        require_null_tuner_diagnostic(host, null_tuner_diagnostic)
    elif getattr(host, 'tuner_unavailable_probe', False):
        raise ValueError('Absent Tuner is not admitted for ordinary XP1 preparation')
    root = resource_root()
    teardown = host.context_teardown_receipt
    registry = install_prepare_type_registry(host, core._handle, teardown, project_root=root)
    emit('xp1_prepare_registry_installed', receipt=registry)
    access = install_xp1_archive_access(host, core._handle, teardown, project_root=root, emit=emit)
    registration = install_xp1_archive_registration(
        host, core._handle, teardown, project_root=root, emit=emit)
    initialize_localization(host, host.dll_directory)
    receipt = prepare_xp1_context(core, context, host, project_root=root,
        module_paths=Windows().modules(), emit=emit,
        null_tuner_diagnostic=null_tuner_diagnostic)
    return {'prepare': receipt, 'registry': prepare_registration_receipt(host),
            'archive_access': access, 'archive_registration': registration,
            'archive_after_prepare': archive_registration_receipt(host),
            'null_tuner_diagnostic': null_tuner_diagnostic,
            'saved_game_loaded': False, 'eligible_for_training': False}

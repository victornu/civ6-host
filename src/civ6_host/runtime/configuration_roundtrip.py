"""Engine-selected, read-only comparison of native provider serializations.

The existing complete-stream comparator is shared unchanged. Its historical
Base proof is an algorithm prerequisite, not evidence for another engine.
Expansion normalization must first have its own source-qualified contract.
No input bytes, provider, database, or native admission are modified here.
"""
from __future__ import annotations

from .saved_load_profiles import BASE_CORE_SHA256, XP2_CORE_SHA256


def compare_provider_roundtrip(before: bytes, after: bytes, *, core_sha256):
    from .native.official_configuration import compare_provider_roundtrip as compare
    from .native.native_checkpoint_configuration_normalization import PROOF_SHA256

    if core_sha256 == BASE_CORE_SHA256:
        source_sha = PROOF_SHA256  # Verified by the shared comparator below.
    elif core_sha256 == XP2_CORE_SHA256:
        from .xp2_normalization_source import verify_source, SOURCE
        verify_source()
        source_sha = SOURCE[1]
    else:
        raise ValueError('No qualified provider normalization for this engine')

    result = compare(before, after)
    if result['normalization_proof_sha256'] != PROOF_SHA256:
        raise ValueError('Shared provider comparison algorithm authority changed')
    return dict(result, normalization_proof_sha256=source_sha,
                comparison_algorithm_proof_sha256=PROOF_SHA256,
                core_sha256=core_sha256, engine_source_qualified=True,
                new_native_execution=False, saved_game_loaded=False)

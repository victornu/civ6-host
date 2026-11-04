"""Private expansion input scopes for the existing prepared-capture format.

Selection here admits input materialization only. It never admits a native
session, changes public capture modes or infers a fallback engine/profile.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class PrivateCaptureCandidate:
    family: str
    reference: tuple
    profile: object
    core_sha256: str
    validate_inputs: object


def select_private_candidate(*, xp1_candidate=False, candidate_profile=None):
    if type(xp1_candidate) is not bool:
        raise ValueError('Candidate input flag must be Boolean')
    if xp1_candidate and candidate_profile is not None:
        raise ValueError('Legacy and explicit candidate selections cannot be combined')
    family = 'xp1-lan' if xp1_candidate else candidate_profile
    if family is None:
        return None
    if type(family) is not str or family not in ('xp1-lan', 'xp2-lan'):
        raise ValueError('Unknown private captured input family')
    if family == 'xp1-lan':
        from .xp1_saved_load import REFERENCE, validate_candidate_inputs
        from .xp1_bundle_inputs import XP1_LAN_PROFILE
        from .saved_load_profiles import XP1_CORE_SHA256
        return PrivateCaptureCandidate(family, REFERENCE, XP1_LAN_PROFILE,
                                       XP1_CORE_SHA256, validate_candidate_inputs)
    from .xp2_bundle_inputs import REFERENCE, XP2_LAN_PROFILE, validate_candidate_inputs
    from .saved_load_profiles import XP2_CORE_SHA256
    return PrivateCaptureCandidate(family, REFERENCE, XP2_LAN_PROFILE,
                                   XP2_CORE_SHA256, validate_candidate_inputs)


def prepare_input_handoff(family, destination, *, bundle=None):
    """Materialize the already validated raw reader result, once per runtime."""
    from . import capture_admission, capture_package
    from .native import native_official_bundle as original
    contract = select_private_candidate(candidate_profile=family)
    if contract is None:
        raise ValueError('Input preparation requires an explicit private family')
    if capture_admission.configured_reference() is not None:
        raise ValueError('Input preparation must start from the raw validated capture')
    identity = capture_admission.validation_identity()
    if bundle is None:
        bundle = original.read_bundle(contract.reference, input_profile=family)
    original._reuse_prepared_bundle(bundle, contract.reference, family, _input_only=True)
    contract.validate_inputs(bundle.inputs, bundle)
    dependency_digest = hashlib.sha256(json.dumps(bundle.dependencies, sort_keys=True,
        separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')).hexdigest()
    if capture_admission.validation_identity() != identity:
        raise ValueError('Preparation runtime changed during parent validation')
    reference = capture_package.export_capture(bundle, destination,
        source_manifest_bytes=(original.ROOT / contract.reference[0]).read_bytes(),
        validation_identity=identity, _candidate_profile=family)
    if capture_admission.validation_identity() != identity:
        raise ValueError('Preparation runtime changed during package materialization')
    return dict(schema='civ6-host.private-input-handoff.v1', input_profile=family,
        package=reference, origin=dict(path=contract.reference[0], sha256=contract.reference[1]),
        original_dependency_count=len(bundle.dependencies),
        original_dependency_pins_sha256=dependency_digest,
        materialization='existing_prepared_capture_format',
        native_execution=False, public_session_admitted=False)


def consume_input_handoff(family, reference):
    """Rehash the compact inputs and their original save/script joins."""
    from . import capture_admission
    contract = select_private_candidate(candidate_profile=family)
    if contract is None:
        raise ValueError('Input consumption requires an explicit private family')
    capture_admission.configure(reference)
    bundle = capture_admission.try_bundle(contract.reference, input_profile=family,
                                         _candidate_profile=family)
    if bundle is None:
        raise ValueError('Candidate requires its explicit prepared input package')
    contract.validate_inputs(bundle.inputs, bundle)
    return bundle

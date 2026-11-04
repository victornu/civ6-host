"""Exact XP1 LAN capture inputs, without native saved-Load admission.

Only the shared raw capture reader consumes this profile. It is deliberately
absent from CAPTURE_MODES, the Base prepared-bundle cache and native profile
admission. An empty current selection/list proves absence, not completed Load.
"""
from .capture_profiles import CapturedModeProfile
from .gameplay_active_profiles import XP1_CORE_SHA256, expansion_profile
import hashlib
from pathlib import Path


XP1_LAN_PROFILE = CapturedModeProfile('xp1-lan-official-capture-inputs', 'LAN')

# The actual XP1 DB journals are 4,244,500/4,244,499 bytes. Retain the
# existing materializer's 16-MiB manifest ceiling; hashes and all journal
# request/row/byte limits still apply. This does not widen the Base reader.
DATABASE_WITNESS_MAX_BYTES = 16 * 1024 ** 2


def reader_validator_digests():
    """Snapshot XP1 input validators without changing Base cache identities."""
    from . import gameplay_active_profiles, capture_profiles
    from .native import native_official_bundle, native_gameplay_empty
    from .native import official_application_configuration
    from .workers import capture_phase1_bundle994
    modules = (gameplay_active_profiles, capture_profiles, native_official_bundle,
               native_gameplay_empty, official_application_configuration,
               capture_phase1_bundle994)
    paths = (Path(__file__).resolve(), *(Path(module.__file__).resolve() for module in modules))
    result = {}
    for path in paths:
        if not path.is_file() or not 0 < path.stat().st_size <= 4 * 1024 ** 2:
            raise ValueError('XP1 input validator source is unavailable or oversized')
        with path.open('rb') as stream:
            raw = stream.read(4 * 1024 ** 2 + 1)
        if not 0 < len(raw) <= 4 * 1024 ** 2:
            raise ValueError('XP1 input validator source exceeds its bound')
        result[str(path)] = hashlib.sha256(raw).hexdigest()
    return result


def recheck_reader_validators(expected):
    if type(expected) is not dict or reader_validator_digests() != expected:
        raise ValueError('XP1 input validator sources changed during admission')


def validate_process(process):
    from .native.official_application_configuration import EXE_SHA256
    if (type(process) is not dict
            or process.get('exe_sha256') != EXE_SHA256
            or type(process.get('gamecore_module')) is not dict
            or process['gamecore_module'].get('sha256') != XP1_CORE_SHA256):
        raise ValueError('XP1 input requires the exact source-pinned EXE and GameCore')
    # Validate the retained, hash-pinned layout before accepting its reports.
    # The same source is revalidated by stable_capture_identity on both sides.
    expansion_profile(XP1_CORE_SHA256)
    return XP1_CORE_SHA256


def validate_selection_scope(runtime):
    if type(runtime) is not dict:
        raise ValueError('XP1 input requires the retained gameplay witnesses')
    selected = runtime.get('gameplay_selection994')
    active = runtime.get('gameplay_active_list')
    embedded = active.get('selection') if type(active) is dict else None
    if any(type(value) is not dict or value.get('consumer_core_matches_base_proof') is not False
           for value in (selected, embedded)):
        raise ValueError('XP1 input must preserve the unsupported Base consumer proof scope')
    snapshot = selected.get('snapshot')
    state = active.get('state')
    if (type(snapshot) is not dict or type(snapshot.get('record_count')) is not int
            or snapshot['record_count'] != 0 or snapshot.get('records') != []
            or snapshot.get('selected_paths') != [] or type(state) is not dict
            or type(state.get('active_count')) is not int or state['active_count'] != 0
            or state.get('active_list_empty') is not True
            or active.get('selected_and_active_empty') is not True):
        raise ValueError('XP1 input requires empty selected and retained active gameplay lists')
    # Content/selection joins, source/state schemas, counters, initialized flags,
    # stable headers and emptiness remain checked by the existing shared reader.


def validate_summary_scope(summary):
    if type(summary) is not dict or any(summary.get(name) is not False for name in (
            'consumer_core_matches_base_proof', 'content_application_success_proven',
            'gameplay_execution_proven')):
        raise ValueError('XP1 input summary overclaims consumer or execution qualification')

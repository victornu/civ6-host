"""8FEF0D8E wrapper over the proven D35E writer byte layout.

Four copied stack bytes are undefined in the source. They are zeroed only for
the explicitly validated empty receiver, never represented as a native default
or learner-visible gameplay value. This module does not enqueue or drain.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_event_d35e import encode_d35e571d_record
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (2414808462, 288, 96)
SELECTOR_KEY = 2716180809
PROOF_SHA256 = 'f69493d849996788153530bf41310a877cfc0289a7a50ea0dae611b4fd275b50'
PADDING_POLICY = 'zero-unread-empty-receiver-payload'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_8fef0d8e.py')))).resolve().parents[1] / 'evidence/native-event-8fef0d8e' / f'{PROOF_SHA256}.json'
_EMPTY_KEYS = frozenset(('observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'))

def verify_source_evidence() -> None:
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_event_8fef0d8e.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['callback_va'] != '0x140149a40' or (proof['registration']['kind'] != '0x8fef0d8e') or (proof['thunk']['raw_hex'] != 'e9fb350000') or (proof['captures']['callback']['raw_sha256'] != 'f94031434006770098fbc2ccacbf9d72c2e866f2a8f8bb62d75b78bd3b5b3f3a') or (proof['captures']['writer']['raw_sha256'] != 'a1e36fc402cfe748c4265525f41c6d36a949d4ffaaccd33dfec3421e856e9394') or (proof['writer_reuse']['canonical_sha256'] != 'b5ffa3f7718c71be5f116be2fd910563a99238dab26dc4979b2cad44e834ac49') or (proof['empty_receiver_source']['row']['record_type'] != '0x120') or (proof['empty_receiver_source']['row']['handler_body_sha256'] != '49018d9ce36f6a4de886ba48645f20d17f9145459b3b28b9fac452bfd07be0a7'):
        raise RuntimeError('Pinned 8FEF0D8E writer-family/receiver identity changed')

def decode_fields(raw_fields: dict[int, bytes]) -> dict[str, int]:
    verify_source_evidence()
    if not isinstance(raw_fields, dict) or set(raw_fields) != {SELECTOR_KEY}:
        raise ValueError('8FEF0D8E requires its exact one-key input')
    raw = raw_fields[SELECTOR_KEY]
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise ValueError('8FEF0D8E selector variant must contain bytes')
    return {'selector': decode_scalar(bytes(raw), 3)}

def encode_record(sequence: int, raw_fields: dict[int, bytes], *, normalizer_transform_present: bool=False, thread_hook_present: bool, writer_metadata_callback_present: bool, padding_policy: str, empty_receiver_state: dict) -> bytes:
    """Reuse the identical writer layout only after explicit profile checks.

    Native callback14D040 initializes four bytes but writer1225F0 copies eight.
    The native sequence replaces the first DWORD; the second is unread stack
    data. Its zero here is a diagnostic policy, not a scalar callback value.
    No other D35E fields or event kinds are admitted by this wrapper.
    """
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('8FEF0D8E requires absent native transform/hooks/services')
    if type(sequence) is not int or not 1 <= sequence <= 2147483647:
        raise ValueError('8FEF0D8E sequence must be a bounded positive integer')
    if padding_policy != PADDING_POLICY:
        raise ValueError('8FEF0D8E copied undefined stack bytes require an explicit unread policy')
    if not isinstance(empty_receiver_state, dict) or set(empty_receiver_state) != _EMPTY_KEYS or type(empty_receiver_state['state_flags']) is not int or (empty_receiver_state['state_flags'] != 0):
        raise ValueError('8FEF0D8E requires complete empty receiver state with zero flags')
    decode_fields(raw_fields)
    record = bytearray(encode_d35e571d_record(sequence, 0, queue_metadata=0))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    validate_empty_profile_record(record, **empty_receiver_state)
    return bytes(record)
__all__ = ['EVENT_KIND', 'RECORD_TYPE', 'RECORD_SIZE', 'SELECTOR_KEY', 'PROOF_SHA256', 'PADDING_POLICY', 'decode_fields', 'encode_record', 'verify_source_evidence']

"""Pinned E992F3CD unit descriptor record; no Core query or counter mutation."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native import native_event_d8adfd71 as descriptor_codec
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (3918721997, 26, 96)
PINNED_EVIDENCE_SHA256 = '382520e22478403ee4bfc8abb7e630e8471f9079d4651940be94fe5a6af4d2ac'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_e992f3cd.py')))).resolve().parents[1] / 'evidence/native-event-e992f3cd' / f'{PINNED_EVIDENCE_SHA256}.json'
EventFields = descriptor_codec.EventFields

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof['schema'] != 'civ6rl.native_event_e992f3cd.static.v1' or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['registration']['kind'] != EVENT_KIND or (proof['registration']['callback_va'] != '0x140157ca0') or (proof['captures']['callback']['code_sha256'] != '4eb5a26ca71ed3885898425412b225c571a1811be8541f766298e15d1f37e056') or (proof['captures']['writer']['code_sha256'] != '98dafed51afe5419b738737c6c03065795a1a77090dffde42c8fb00630e61649') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['shared_descriptor_codec']['sha256'] != descriptor_codec.PINNED_EVIDENCE_SHA256) or (proof['instruction_guards']['writer']['0x140127888'] != 'mov dword ptr [rbx + 4], 0x1a'):
        raise RuntimeError('E992F3CD callback/writer identity changed')
    return proof

def decode_fields(raw_fields, read):
    verify_source_evidence()
    return descriptor_codec.decode_fields(raw_fields, read)

def encode_record(sequence, fields, *, normalizer_transform_present, per_thread_hook_present, writer_metadata_callback_present, padding_policy):
    """Same complete layout as pinned D8 codec, with source type1A header.

    Both callbacks copy normalized unit identity to metadata+8 and payload+8,
    leave only payload+4 uninitialized, and pass explicit metadata to writers.
    The complete writer operation comparison is pinned separately for E992.
    """
    verify_source_evidence()
    record = bytearray(descriptor_codec.encode_record(sequence, fields, normalizer_transform_present=normalizer_transform_present, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, padding_policy=padding_policy))
    struct.pack_into('<I', record, 4, RECORD_TYPE)
    return bytes(record)

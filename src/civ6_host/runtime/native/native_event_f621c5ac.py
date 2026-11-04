"""Restricted headless codec for the source-captured F621C5AC event."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
EVENT_KIND = 4129408428
CALLBACK_VA = 5370093232
WRITER_VA = 5369987392
RECORD_SIZE = 96
RECORD_TYPE = 188
SELECTOR_KEY = 2716180809
A1FBC_KEY = 2717631346
D6_KEY = 3606901732
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PIN = '7b374240a36e7783cbde03033baddbd1722a978aab690c2ece90cc5048771970'
PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_f621c5ac.py')))).resolve().parents[1] / 'evidence/native-event-f621c5ac' / f'{PIN}.json'

def verify_source_evidence() -> None:
    proof = load_pinned_json(PROOF, PIN)
    if proof.get('schema') != 'civ6rl.native_event_f621c5ac.static.v1' or proof.get('exe_sha256') != EXE_SHA256 or proof.get('registration', {}).get('callback_va') != hex(CALLBACK_VA) or (proof.get('record') != {'type': '0xbc', 'size': '0x60', 'callback_va': hex(CALLBACK_VA), 'writer_va': hex(WRITER_VA), 'commit_helper_va': '0x1409898c0'}) or (proof['captures']['callback']['code_sha256'] != '76b6779fee8317e9c0b982a8678995a9e571ef491e283b004a7d12c97d0ecfdb') or (proof['captures']['writer']['code_sha256'] != '3d83716e22df847bf7a879f822c8f88cfa56b589d6d6d6df138d870ae7f2ab83') or (proof['captures']['normalizer']['code_sha256'] != 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e') or (proof['instruction_guards']['normalizer'].get('0x1401ca681') != 'mov dword ptr [rbp - 0x35], eax') or (proof['instruction_guards']['normalizer'].get('0x1401ca676') != 'mov dword ptr [rbp + 0x1b], eax') or (proof['instruction_guards']['normalizer'].get('0x1401ca6ec') != 'mov dword ptr [rbp + 0x17], eax') or (proof['instruction_guards']['writer'].get('0x1401381e8') != 'mov dword ptr [rbx + 4], 0xbc'):
        raise RuntimeError('Pinned F621C5AC callback/writer contract changed')
    witnesses = proof.get('witnesses', {})
    if set(witnesses) != {'prefix209', 'prefix211'}:
        raise RuntimeError('Pinned F621C5AC witness profiles changed')
    for profile, expected in (('prefix209', (0, 0, 0)), ('prefix211', (0, 0, 1))):
        event = witnesses[profile]['event']
        if set(event.get('fields', {})) != {'0xa1e5a149', '0xa1fbc372', '0xd6fcf3e4'}:
            raise RuntimeError(f'Pinned F621C5AC witness shape changed: {profile}')
        values = []
        for key, tag in (('0xa1e5a149', 3), ('0xa1fbc372', 2), ('0xd6fcf3e4', 2)):
            raw = bytes.fromhex(event['fields'][key])
            if len(raw) != 24 or struct.unpack_from('<H', raw)[0] != tag or struct.unpack_from('<I', raw, 20)[0] != 0:
                raise RuntimeError(f'Pinned F621C5AC witness tag/flags changed for {key}')
            values.append(struct.unpack_from('<I', raw, 8)[0])
        if tuple(values) != expected:
            raise RuntimeError(f'Pinned F621C5AC witness value changed: {profile}')

def decode_fields(fields: dict[int, bytes]) -> tuple[int, int, int]:
    """Decode the exact three-key scalar shape and preserve mapped DWORDs."""
    verify_source_evidence()
    if not isinstance(fields, dict) or set(fields) != {SELECTOR_KEY, A1FBC_KEY, D6_KEY}:
        raise ValueError('F621C5AC requires exactly its three source-backed keys')
    selector = decode_scalar(fields[SELECTOR_KEY], 3)
    a1fbc = decode_scalar(fields[A1FBC_KEY], 2)
    d6 = decode_scalar(fields[D6_KEY], 2)
    return (selector, a1fbc, d6)

def encode_record(sequence: int, fields: dict[int, bytes], *, thread_hook_present: bool=False, writer_metadata_callback_present: bool=False, empty_receiver_profile: bool, padding_policy: str) -> bytes:
    """Build the initial 0xBC row under explicit headless empty/hook policy.

    Three bytes in the callback's 16-byte tail are not initialized in source;
    zero is an explicit host diagnostic policy, not a native default.
    """
    decode_fields(fields)
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('sequence must be a nonzero uint32')
    if thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('F621C5AC hook/callback-present paths are unsupported')
    if empty_receiver_profile is not True:
        raise ValueError('F621C5AC requires the explicit empty receiver profile')
    if padding_policy != 'headless-zero-uninitialized-stack':
        raise ValueError('F621C5AC requires an explicit zero policy for three unwritten bytes')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    struct.pack_into('<IIHHIHHIHHIHHIHHIIII', record, 16, 4294967295, 4294967295, 65535, 0, 4294967295, 65535, 0, 4294967295, 65535, 0, 4294967295, 65535, 0, 4294967295, 65535, 0, 4294967295, 0, 0, 4)
    selector, a1fbc, d6 = decode_fields(fields)
    del selector
    struct.pack_into('<IIII', record, 80, sequence, d6, a1fbc, 0)
    return bytes(record)
__all__ = ['EVENT_KIND', 'CALLBACK_VA', 'WRITER_VA', 'RECORD_SIZE', 'RECORD_TYPE', 'decode_fields', 'encode_record', 'verify_source_evidence']

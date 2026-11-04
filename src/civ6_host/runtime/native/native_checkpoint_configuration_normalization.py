"""Pure comparison of bounded provider streams with one native normalization.

This neither restores nor edits a provider. Raw byte equality remains a distinct
result from the exact tag-5 zero-inline representation transition proved below.
Unsupported wire shapes fail closed even when the two inputs are identical.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
import struct
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_checkpoint_configuration_normalization.py')))).resolve().parents[1]
PROOF_SHA256 = 'feb70397ceddc5f5c86eaa3671675e959977684cf2ed8155b0e3943a6651b747'
PROVIDER_PROOF_SHA256 = '3d5ef65d87185b09b2925e2c0f61f7181d993b3f25e2e55cc3fbcc3c08a817a7'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MAX_BYTES = 65536
MAX_ENTRIES = 4096
MAX_DEPTH = 4
_BODY_HASHES = {'value_writer': '59e7a51ef3891abbca2684bb953028aa185e5789fcf961eed179fa4cb73ed14c', 'value_reader': '91b937596a0372f049429a214832f4d3586c50d93b2e72ffb3d5f4a194703663', 'variant_writer_header': 'd0b199683179f2f5261bc7f4c25c2ecf2e9ea90d030e5879d45fe7eb3ffc3075', 'variant_reader_header': '2fcb12ba2378a70227e6cde98240dc3c0e4a762309ee25f247c467626cadcd22', 'read_inline_dword': 'fc24448d2f1302a2a0bc824b15eab9a7a13861d7de9d5120529495cb71dfa029', 'typed_value_constructor': '3ba5ae12d6710fb63d34149a5eee6488b80f60d71c70cceac0096a7c875f2a79'}

def _sha(raw):
    return hashlib.sha256(raw).hexdigest()

def verify_source_evidence():
    path = ROOT / 'evidence/native-checkpoint-empty-string-normalization' / (PROOF_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if _sha(raw) != PROOF_SHA256:
        raise ValueError('Configuration normalization proof hash differs')
    doc = json.loads(raw)
    contract = doc['contract']
    if doc.get('schema') != 'civ6rl.native_checkpoint_empty_string_normalization.static.v1' or doc.get('native_execution') is not False or doc['images']['core']['sha256'] != CORE_SHA256 or (contract['input_exact'] != {'tag': 5, 'extra_word': 0, 'flags': 536870912, 'size': 1, 'inline_value': 0}) or (contract['output_exact'] != {'tag': 5, 'extra_word': 0, 'flags': 0, 'size': 1, 'inline_value': 0}) or (contract['serialized_entry'] != {'key_uint32': 0, 'tag_uint16': 4, 'extra_uint16': 6, 'flags_uint32': 8, 'size_uint32': 12, 'inline_value_uint32': 16, 'entry_bytes': 20}) or (doc['verification']['all_captured_instructions_rechecked_against_pinned_PE'] is not True) or (doc['verification']['full_consumption_both_streams'] is not True):
        raise ValueError('Configuration normalization source contract differs')
    parent = 'evidence/native-checkpoint-configuration-stream-v3/' + PROVIDER_PROOF_SHA256 + '.json'
    if doc['parents'].get(parent) != PROVIDER_PROOF_SHA256 or _sha(_resolve_resource_path(ROOT / parent).read_bytes()) != PROVIDER_PROOF_SHA256:
        raise ValueError('Configuration provider parent differs')
    if any((doc['captures'][name]['code_sha256'] != digest for name, digest in _BODY_HASHES.items())):
        raise ValueError('Configuration normalization source bodies differ')
    return doc

def _bound(value, name, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f'{name} must be an exact positive integer at most {maximum}')

def _parse(raw, max_bytes, max_entries, max_depth):
    if type(raw) is not bytes or not 4 <= len(raw) <= max_bytes:
        raise ValueError('Provider comparison needs bounded immutable bytes')
    offset = 0
    entries, providers = ([], [])

    def take(length):
        nonlocal offset
        if length < 0 or offset + length > len(raw):
            raise ValueError('Truncated configuration provider stream')
        start = offset
        offset += length
        return raw[start:offset]

    def u32():
        return struct.unpack('<I', take(4))[0]

    def provider(path, depth):
        if depth > max_depth:
            raise ValueError('Configuration provider depth bound exceeded')
        start = offset
        count = u32()
        if count > max_entries:
            raise ValueError('Configuration count or header flags are outside the profile')
        providers.append((path, start, count))
        previous_key = -1
        for _ in range(count):
            if len(entries) >= max_entries:
                raise ValueError('Configuration entry bound exceeded')
            start = offset
            key = u32()
            if key <= previous_key:
                raise ValueError('Configuration keys are duplicate or out of native order')
            previous_key = key
            tag, extra = struct.unpack('<HH', take(4))
            flags, size = (u32(), u32())
            entry = {'offset': start, 'key_path': path + (key,), 'tag': tag, 'extra_word': extra, 'flags': flags, 'size': size, 'flags_offset': start + 8}
            entries.append(entry)
            if extra != 0:
                raise ValueError('Unsupported configuration extra WORD')
            if tag == 10 and flags == 83886080 and (size == 0):
                provider(entry['key_path'], depth + 1)
                entry['provider'] = True
            elif tag in (1, 2, 3) and flags == 0 and (size == 0):
                entry['payload'] = take(4)
            elif tag == 5 and flags in (0, 536870912) and (size == 1):
                entry['payload'] = take(4)
                if entry['payload'] != b'\x00' * 4:
                    raise ValueError('Only the proven zero inline string value is admitted')
            elif tag in (5, 6) and flags & 4278190080 == 553648128 and (size == (1 if tag == 5 else 2)):
                count = flags & 16777215
                if count == 0:
                    raise ValueError('Unsupported zero-length indirect configuration string')
                entry['payload'] = take(count * size)
            else:
                raise ValueError('Unsupported configuration variant wire shape')
            entry['end_offset'] = offset
    provider((), 0)
    if offset != len(raw):
        raise ValueError('Trailing bytes after complete configuration provider')
    return (entries, providers)

def compare_configuration_streams(before: bytes, after: bytes, *, max_bytes=MAX_BYTES, max_entries=MAX_ENTRIES, max_depth=MAX_DEPTH):
    """Return a receipt only after complete parsing and exact permitted changes.

    Limits are local diagnostic resource bounds, not native game constraints.
    Both byte objects remain untouched. An accepted normalized relation is never
    reported as raw-byte equality or as a completed game restoration.
    """
    _bound(max_bytes, 'Byte limit', MAX_BYTES)
    _bound(max_entries, 'Entry limit', MAX_ENTRIES)
    _bound(max_depth, 'Depth limit', MAX_DEPTH)
    verify_source_evidence()
    left, left_maps = _parse(before, max_bytes, max_entries, max_depth)
    right, right_maps = _parse(after, max_bytes, max_entries, max_depth)
    if len(before) != len(after) or len(left) != len(right) or left_maps != right_maps:
        raise ValueError('Configuration provider structure changed')
    predicted = bytearray(before)
    changes = []
    for source, destination in zip(left, right):
        if source == destination:
            continue
        if source['tag'] != 5 or source['extra_word'] != 0 or source['size'] != 1 or (source['flags'] != 536870912) or (source.get('payload') != b'\x00' * 4) or (destination['flags'] != 0) or (source != dict(destination, flags=536870912)):
            raise ValueError('Configuration difference is not the exact native zero-string transition')
        flags_offset = source['flags_offset']
        struct.pack_into('<I', predicted, flags_offset, 0)
        changes.append({'key_path': list(source['key_path']), 'entry_offset': source['offset'], 'flags_offset': flags_offset, 'changed_byte_offset': flags_offset + 3})
    if bytes(predicted) != after:
        raise ValueError('Configuration bytes changed outside the proven normalization')
    return {'proof_sha256': PROOF_SHA256, 'provider_proof_sha256': PROVIDER_PROOF_SHA256, 'input_bytes': len(before), 'input_sha256': _sha(before), 'output_bytes': len(after), 'output_sha256': _sha(after), 'raw_bytes_equal': before == after, 'normalized_entry_count': len(changes), 'changes': changes, 'entry_count': len(left), 'provider_count': len(left_maps), 'complete_streams_parsed': True, 'other_bytes_equal': True, 'comparison': 'exact-or-native-zero-inline-string-normalization', 'complete_game_restore_validated': False, 'eligible_for_training': False}

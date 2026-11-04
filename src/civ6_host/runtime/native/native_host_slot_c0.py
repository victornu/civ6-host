"""Source-ordered host status messages; no gameplay outcome is computed here."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_event_domains import validate_sequence
PROOF_SHA256 = '5dd6ed7a6e5c27af035d95cbd1cac1f0610d395e7bd9deb40d84ff17a5eb246b'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host_slot_c0.py')))).resolve().parents[1]
RECORD_TYPE, RECORD_SIZE = (247, 1120)
TEXT_KEY, CATEGORY_KEY, SELECTOR_KEY = (3302320337, 192784602, 2716180809)
PADDING_POLICY = 'zero-unread-status-string-tail-empty-receiver'

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('Host C0 complete source proof is not pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-host-slot-c0' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_host_slot_c0.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['captures']['host_slot_c0']['code_sha256'] != '282a5ff5f23de79a8ecd1712c9c5448dc31d4da0fca39737cc208db106370cdd' or (proof['captures']['status_message']['code_sha256'] != '7a3d897697051af7f0a095e261fe5d807400a601c223208532d948023a1a2f1e') or (proof['captures']['writer']['code_sha256'] != '01fde54d8a5f54f8a02855f32083c1d61959b46ceab6257d8af1f099e7615e89') or (proof['contract']['record']['type'] != RECORD_TYPE) or (proof['contract']['record']['size'] != RECORD_SIZE) or (proof['contract']['record']['payload_size'] != 1040) or (proof['contract']['scalar_conversion']['allowed_mask'] != 3145774) or (proof['contract']['scalar_conversion']['allowed_tags'] != (1, 2, 3, 5, 20, 21)) or (proof['binding']['slot'] != 192) or (proof['binding']['target_va'] != '0x1401ca890') or (proof['binding']['map_lookup_slot'] != 96) or (proof['parents']['retained_game_getter']['sha256'] != '2763ab2aecf67a5d38f789e28190b5e5ab8ff2dfb1424a0d36209f59a3314710') or (proof['empty_receiver_source']['handler_va'] != '0x1400dbd70') or (proof['empty_receiver_source']['row_va'] != '0x1412c9700'):
        raise RuntimeError('Host C0 source contract changed')
    return proof

def _variant(raw):
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24:
        raise ValueError('Host C0 requires exact native 24-byte variants')
    return bytes(raw)

def _scalar(raw, absent):
    if raw is None:
        return absent
    raw = _variant(raw)
    tag, flags = (struct.unpack_from('<H', raw)[0], struct.unpack_from('<I', raw, 20)[0])
    valid = not flags & 536870912 and tag <= 21 and bool(3145774 & 1 << tag)
    return struct.unpack_from('<I', raw, 8)[0] if valid else 0

def _c_string(pointer, read):
    if type(pointer) is not int or pointer <= 0:
        raise ValueError('Host C0 null status string CRT branch is not implemented')
    value = bytearray()
    for offset in range(1024):
        byte = read(pointer + offset, 1)
        if not isinstance(byte, (bytes, bytearray, memoryview)) or len(byte) != 1:
            raise ValueError('Host C0 status string is not completely readable')
        value.extend(byte)
        if byte == b'\x00':
            return bytes(value)
    raise ValueError('Host C0 status string does not fit the native 1024-byte buffer')

def dispatch_status_message(kind, target_value, argument_pointer, *, retained_game_getter, read_fields, read, sequence, empty_receiver_state, padding_policy, writer_metadata_callback_present, per_thread_hook_present):
    """Apply the real getter comparison before any read of the argument map.

    The two DWORDs are transport values, not assumed player or team identities.
    A missing or incompatible text variant follows the source's no-record path.
    """
    verify_source_evidence()
    if any((type(value) is not int or not 0 <= value <= 4294967295 for value in (kind, target_value))):
        raise ValueError('Host C0 arguments must preserve their DWORD bits')
    if not callable(retained_game_getter):
        raise ValueError('Host C0 requires the live retained Game getter')
    native_value = retained_game_getter()
    if type(native_value) is not int or not -(1 << 31) <= native_value < 1 << 31:
        raise ValueError('Host C0 getter must return its actual signed DWORD')
    result = dict(record=None, native_getter_value=native_value, branch='target_differs', map_read=False, text_byte_count=0)
    if target_value != native_value & 4294967295:
        return result
    if type(argument_pointer) is not int or argument_pointer <= 0 or (not callable(read_fields)) or (not callable(read)):
        raise ValueError('Host C0 matching target requires its readable native map')
    fields = read_fields(argument_pointer)
    if type(fields) is not dict:
        raise ValueError('Host C0 argument tree reader must return a copied field map')
    result.update(branch='text_absent_or_incompatible', map_read=True)
    text_variant = fields.get(TEXT_KEY)
    if text_variant is None:
        return result
    text_variant = _variant(text_variant)
    if struct.unpack_from('<H', text_variant)[0] != 5 or not struct.unpack_from('<I', text_variant, 20)[0] & 16777215:
        return result
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    validate_sequence(sequence)
    if writer_metadata_callback_present is not False or per_thread_hook_present is not False:
        raise ValueError('Host C0 optional thread hook or writer metadata service is not implemented')
    if padding_policy != PADDING_POLICY:
        raise ValueError('Host C0 requires its explicit unread string-tail policy')
    if type(empty_receiver_state) is not dict or set(empty_receiver_state) != {'observer_registered', 'state_pointer_nonnull', 'pre_hook', 'post_hook', 'subscriber_count', 'state_flags'}:
        raise ValueError('Host C0 requires the complete StatusMessage receiver state')
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<II', record, 0, RECORD_SIZE, RECORD_TYPE)
    validate_empty_profile_record(record, **empty_receiver_state)
    text = _c_string(struct.unpack_from('<Q', text_variant, 8)[0], read)
    category = _scalar(fields.get(CATEGORY_KEY), 103780558)
    selector = _scalar(fields.get(SELECTOR_KEY), 4294967295)
    struct.pack_into('<IIii', record, 8, sequence, 0, -1, -1)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<III', record, 64, 0 if kind == 4294967295 else kind, 0, 2 if kind == 4294967295 else 0)
    struct.pack_into('<I', record, 80, sequence)
    record[84:84 + len(text)] = text
    struct.pack_into('<IIf', record, 1108, category, selector, 0.0)
    result.update(record=bytes(record), branch='status_record', text_byte_count=len(text), category=category, selector=selector)
    return result

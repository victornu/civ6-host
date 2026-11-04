"""WorldTextMessage transport from the complete native callback15A300.

The GameCore has already applied the action. This copies its notification and
uses the retained public-map snapshot; it never recalculates a gameplay result.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import struct
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = 'f0b54a0e1fa7175125787fa5641c781624f4508b2b0af3e723ce12cb9b125d4f'
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (1169496022, 250, 368)
POSITION_KEY, SELECTOR_KEY = (2353434172, 2716180809)
TEXT_KEY, DESCRIPTOR_KEY = (3302320337, 4032072631)
CITY_DESCRIPTOR_KEY = 594779970
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_45b517d6.py')))).resolve().parents[1]
CITY_PROOF = ROOT / 'work/encampment-completion966/worldtext-city-source.json'
CITY_PROOF_SHA256 = '4b729b9530142707127415972fe06f48f63a96f49a56f830124bf03bab3c94fd'

def verify_city_source():
    p = load_pinned_json(CITY_PROOF, CITY_PROOF_SHA256)
    if p['schema'] != 'civ6rl.worldtext_city966.static.v1' or p['parent']['sha256'] != PROOF_SHA256 or p['contract']['city_record_offset'] != 56 or (p['contract']['city_normalized_offset'] != 24) or (p['contract']['city_record_type'] != 2) or (p['instructions_rechecked'] != 752):
        raise RuntimeError('WorldTextMessage city source changed')
    return p

def verify_source_evidence():
    if not PROOF_SHA256:
        raise RuntimeError('WorldTextMessage source proof is not pinned')
    proof = load_pinned_json(ROOT / 'evidence/native-event-45b517d6' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    from civ6_host.runtime.native.native_deferred_empty_profile import FORTY_FIVE_B517D6_RECEIVER_SHA256
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_event_45b517d6.static.v1' or proof['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or proof['kind'] != EVENT_KIND or (proof['registrar']['registration']['callback_va'] != '0x14015a300') or (proof['parents']['receiver']['sha256'] != FORTY_FIVE_B517D6_RECEIVER_SHA256) or (FORTY_FIVE_B517D6_RECEIVER_SHA256 != '22bc8054f1f86b28fffa266c31aa02513e24a6d55fdc9420ecd79ed180a4f2fa') or (proof['parents']['cache_publication']['sha256'] != '2632e4cd0892fe60c6b9e8149edad8c12b9ad00564101d21a98a9a764d2ec6b6') or (set(contract['input_keys']) != {POSITION_KEY, SELECTOR_KEY, TEXT_KEY, DESCRIPTOR_KEY}) or (contract['tags'] != {'8C468E3C': 0, 'A1E5A149': 3, 'C4D568D1': 5, 'F0548BB7': 1024}) or (contract['selector_domain'] != (0, 4294967295)) or (contract['scalar_flags'] != 0) or (contract['blob_envelope'] != {'flags': 553648129, 'nonnull_pointer': True, 'size': 8}) or (contract['text_envelope'] != {'tag': 5, 'tag_width': 2, 'flags_high_bits_ignored_by_normalizer': True, 'flags_low24_nonzero': True, 'nonnull_pointer': True, 'size_field_ignored': True, 'size_or_count_is_not_copy_length': True}) or (contract['record'] != {'type': RECORD_TYPE, 'size': RECORD_SIZE, 'payload_offset': 80, 'payload_size': 284, 'allocation_zero_ranges': ((76, 80), (364, 368)), 'initialized_payload_complete_for_nonnull_text': True, 'undefined_ranges': ()}) or (contract['cache_index']['width_global_va'] != '0x1422d6028') or ({'dll': 'api-ms-win-crt-string-l1-1-0.dll', 'iat_va': '0x140f97a10', 'image': 'exe', 'name': 'strncpy'} not in proof['imports']) or (proof['verification']['all_captured_instructions_match_pinned_pe'] is not True):
        raise RuntimeError('WorldTextMessage source contract changed')
    for name, digest in {'callback': '9274f0cb924c2b7cebbac4c534466a69503d24f7fa5047353493145d02645c05', 'writer': '12fe51b9a90994a40506f535dcf0ce282f8567e761d533a675299abaa91beeab', 'normalizer': 'c757d2f0c927f36e058ff5e57350a80beac1db2a89d3940fcb5e89c05545f23e', 'resolver': '5d0c3c7557f18ad896d84bb83b4c43b6fd47bbee1b25e73967ee78f1fe583d89', 'cache_refresh': '75082cd8be57511fb09882b0aa291fa3d2e692316965d19797b64e689044bcbd'}.items():
        if proof['captures'][name]['code_sha256'] != digest:
            raise RuntimeError('WorldTextMessage source body changed: ' + name)
    if proof['leaves']['position_index']['reachable_bytes_sha256'] != '32709fff217639c4ffdebf3f0580894adabb11ab63db9fdbdaf3c26b67bf024d':
        raise RuntimeError('WorldTextMessage cached position-index calculation changed')
    return proof

@dataclass(frozen=True)
class EventFields:
    selector: int
    position_bytes: bytes
    descriptor_bytes: bytes
    owner: int
    item_id: int
    text_pointer: int
    entity_type: int = 1

def _blob_pointer(raw, tag):
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if struct.unpack_from('<H', raw)[0] != tag or pointer == 0 or size != 8 or (flags != 553648129):
        raise ValueError('WorldTextMessage borrowed descriptor/position envelope changed')
    return pointer

def _read_bytes(read, pointer, length):
    copied = read(pointer, length)
    if not isinstance(copied, (bytes, bytearray, memoryview)) or len(copied) != length:
        raise ValueError('WorldTextMessage borrowed read is incomplete')
    return bytes(copied)

def decode_fields(raw_fields, read):
    """Normalize one source-proven four-key shape, without reading text."""
    verify_source_evidence()
    common = {POSITION_KEY, SELECTOR_KEY, TEXT_KEY}
    if type(raw_fields) is not dict or set(raw_fields) not in (common | {DESCRIPTOR_KEY}, common | {CITY_DESCRIPTOR_KEY}) or any((type(raw) is not bytes or len(raw) != 24 for raw in raw_fields.values())):
        raise ValueError('WorldTextMessage requires four complete typed fields')
    city = CITY_DESCRIPTOR_KEY in raw_fields
    if city:
        verify_city_source()
    descriptor_key = CITY_DESCRIPTOR_KEY if city else DESCRIPTOR_KEY
    selector = decode_scalar(raw_fields[SELECTOR_KEY], 3)
    position_pointer = _blob_pointer(raw_fields[POSITION_KEY], 0)
    descriptor_pointer = _blob_pointer(raw_fields[descriptor_key], 1024)
    raw_text = raw_fields[TEXT_KEY]
    text_pointer = struct.unpack_from('<Q', raw_text, 8)[0]
    if struct.unpack_from('<H', raw_text)[0] != 5 or not struct.unpack_from('<I', raw_text, 20)[0] & 16777215 or (not text_pointer):
        raise ValueError('WorldTextMessage requires a nonnull normalized tag5 string')
    if city:
        descriptor = _read_bytes(read, descriptor_pointer, 8)
        position = _read_bytes(read, position_pointer, 8)
    else:
        position = _read_bytes(read, position_pointer, 8)
        descriptor = _read_bytes(read, descriptor_pointer, 8)
    owner, _ignored_type, item_id = struct.unpack('<HHI', descriptor)
    return EventFields(selector, position, descriptor, owner, item_id, text_pointer, 2 if city else 1)

def copy_text_buffer(pointer, read):
    """Reproduce strncpy(dst, src, 256), including its complete zero padding."""
    if type(pointer) is not int or pointer <= 0:
        raise ValueError('WorldTextMessage null-string branch is outside this profile')
    buffer = bytearray(256)
    for index in range(256):
        byte = _read_bytes(read, pointer + index, 1)
        buffer[index] = byte[0]
        if byte == b'\x00':
            break
    return bytes(buffer)

def _normalizer_profile(normalizer_transform_present, entity_listener_count):
    if normalizer_transform_present is not False or type(entity_listener_count) is not int or entity_listener_count != 0:
        raise ValueError('WorldTextMessage requires the actual closed normalizer profile')

def _profile(sequence, snapshot, *, normalizer_transform_present, entity_listener_count, per_thread_hook_present, writer_metadata_callback_present, empty_receiver_state):
    _normalizer_profile(normalizer_transform_present, entity_listener_count)
    if per_thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('WorldTextMessage optional producer services are unsupported')
    if type(sequence) is not int or not 1 <= sequence <= 4294967295:
        raise ValueError('WorldTextMessage requires a nonzero DWORD sequence')
    if type(snapshot) is not bytes or len(snapshot) != 28:
        raise ValueError('WorldTextMessage requires the complete native B0+E8 map snapshot')
    width, height, count = struct.unpack_from('<iii', snapshot)
    if width <= 0 or height <= 0 or width * height != count:
        raise ValueError('WorldTextMessage map snapshot has unverified dimensions')
    expected = dict(observer_registered=False, state_pointer_nonnull=True, pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0)
    if type(empty_receiver_state) is not dict or empty_receiver_state != expected or any((type(empty_receiver_state[k]) is not type(v) for k, v in expected.items())):
        raise ValueError('WorldTextMessage requires its actual empty receiver')
    from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II', shape, 0, RECORD_SIZE, RECORD_TYPE)
    row = validate_empty_profile_record(shape, **empty_receiver_state)
    if row['event_name'] != 'GameCoreEvent::WorldTextMessage' or row['handler_va'] != '0x1400dbe90':
        raise ValueError('WorldTextMessage receiver changed')
    return width

def _fields(fields):
    if not isinstance(fields, EventFields) or type(fields.selector) is not int or (not 0 <= fields.selector <= 4294967295) or (type(fields.position_bytes) is not bytes) or (len(fields.position_bytes) != 8) or (type(fields.descriptor_bytes) is not bytes) or (len(fields.descriptor_bytes) != 8) or (type(fields.owner) is not int) or (not 0 <= fields.owner <= 65535) or (type(fields.item_id) is not int) or (not 0 <= fields.item_id <= 4294967295) or (struct.unpack_from('<H', fields.descriptor_bytes)[0] != fields.owner) or (struct.unpack_from('<I', fields.descriptor_bytes, 4)[0] != fields.item_id) or (type(fields.entity_type) is not int) or (fields.entity_type not in (1, 2)) or (type(fields.text_pointer) is not int) or (fields.text_pointer <= 0):
        raise ValueError('WorldTextMessage requires exact normalized fields')

def encode_record(sequence, fields, text_buffer, cache_map_snapshot, **profile):
    verify_source_evidence()
    width = _profile(sequence, cache_map_snapshot, **profile)
    _fields(fields)
    if fields.entity_type == 2:
        verify_city_source()
    if type(text_buffer) is not bytes or len(text_buffer) != 256:
        raise ValueError('WorldTextMessage requires the complete initialized text buffer')
    x, y = struct.unpack('<ii', fields.position_bytes)
    index = y * width + x & 4294967295
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIIIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0, 4294967295, index)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    if fields.owner != 65535 and fields.item_id != 4294967295:
        offset = 56 if fields.entity_type == 2 else 24
        struct.pack_into('<HHI', record, offset, fields.owner, fields.entity_type, fields.item_id)
    struct.pack_into('<II', record, 80, sequence, fields.selector)
    record[92:100] = fields.position_bytes
    record[100:356] = text_buffer
    struct.pack_into('<II', record, 356, 0, 4294967295)
    return bytes(record)

def produce_record(sequence, raw_fields, read, *, gate_enabled, cache_map_snapshot, normalizer_transform_present, entity_listener_count, per_thread_hook_present, writer_metadata_callback_present, empty_receiver_state):
    verify_source_evidence()
    if type(gate_enabled) is not bool:
        raise ValueError('WorldTextMessage cache gate must be an actual boolean state')
    _normalizer_profile(normalizer_transform_present, entity_listener_count)
    profile = dict(normalizer_transform_present=normalizer_transform_present, entity_listener_count=entity_listener_count, per_thread_hook_present=per_thread_hook_present, writer_metadata_callback_present=writer_metadata_callback_present, empty_receiver_state=empty_receiver_state)
    if gate_enabled:
        _profile(sequence, cache_map_snapshot, **profile)
    fields = decode_fields(raw_fields, read)
    if not gate_enabled:
        return None
    text = copy_text_buffer(fields.text_pointer, read)
    return encode_record(sequence, fields, text, cache_map_snapshot, **profile)

"""Pure AE/AF codec for the source-pinned E66012A7 wonder branch.

This encoder does not execute the native plot/district queries or application
effects. Callers must supply the snapshots produced by those separately
validated paths and establish the empty receiver profile before representing
source-stack padding as zero.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import struct
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_event_e66012a7 import EventFields
from civ6_host.runtime.native.native_event_e66012a7 import _fields
EVENT_KIND = 3865055911
RECORD_TYPES = (174, 175)
RECORD_SIZE = 144
PAYLOAD_SIZE = 56
EMPTY_PADDING_POLICY = 'zero-unread-empty-receiver-payload'
PINNED_EVIDENCE_SHA256 = '9f27a38ba65bbbbcc456d6c929304f76c7766c4941438a23540370aa794f3c33'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_event_e66012a7_wonder.py')))).resolve().parents[1] / 'evidence/native-e660-wonder-branch' / f'{PINNED_EVIDENCE_SHA256}.json'
_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_CODE_SHA256 = {'callback': '2b8443eadd74373e0b4ef49533509d74aae7cc17cb7155a404d02d346eaf4da7', 'writer_AE': 'b925ee3aaf308d97ba3da8ce52d8360f2f15a11768ea58aa09a410efe4bd9a50', 'writer_AF': '2eeb735780ed74f9ba7d2b7b8a8b39a6e0181557d7da428958da0f4e4b49fb3c'}

def verify_source_evidence():
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    contract = proof['contract']
    records = contract['records']
    if proof.get('schema') != 'civ6rl.native_e660_wonder_branch.static.v1' or proof['images'].get('core_sha256') != _CORE_SHA256 or proof['images'].get('exe_sha256') != _EXE_SHA256 or ({name: proof['exe_bodies'][name].get('code_sha256') for name in _CODE_SHA256} != _CODE_SHA256) or ([(r.get('type'), r.get('size'), r.get('writer_va'), r.get('payload_pointer')) for r in records] != [('0xae', '0x90', '0x1401369b0', 'currentRSP+0x58'), ('0xaf', '0x90', '0x140136bc0', 'RBP-0x10=currentRSP+0xf0')]) or (contract.get('payload_size') != PAYLOAD_SIZE) or (contract.get('metadata', '').find('flag6') < 0) or (contract.get('hooks', '').find('absent') < 0):
        raise RuntimeError('E66012A7 wonder-branch evidence identity or contract changed')
    return proof

def _validate_fields(fields: EventFields) -> None:
    if not isinstance(fields, EventFields):
        raise ValueError('E66012A7 wonder codec requires pinned event fields')
    _fields(fields)
    if fields.selector != 3434534334:
        raise ValueError('E66012A7 wonder codec admits only selector CCB6D5BE')
    if struct.unpack('<i', struct.pack('<I', fields.second_value))[0] < 100:
        raise ValueError('E66012A7 wonder branch requires signed normalized input A1FBC+54 >= 100')
    if fields.x <= -9999 or fields.y <= -9999:
        raise ValueError('E66012A7 wonder branch requires both coordinates above -9999')

def _validate_third_values(third_values):
    if type(third_values) is not dict or set(third_values) != {'owner', 'city_id', 'district_id', 'flag148'}:
        raise ValueError('E66012A7 requires the complete native third-plot snapshot')
    owner = third_values['owner']
    city_id = third_values['city_id']
    district_id = third_values['district_id']
    flag = third_values['flag148']
    if type(owner) is not int or not -128 <= owner <= 127:
        raise ValueError('E66012A7 third snapshot owner must be the signed native byte')
    if type(city_id) is not int or not 0 <= city_id <= 4294967295:
        raise ValueError('E66012A7 third snapshot city id must be uint32')
    if type(district_id) is not int or not 0 <= district_id <= 4294967295:
        raise ValueError('E66012A7 third snapshot district id must be uint32')
    if type(flag) is not int or not 0 <= flag <= 255:
        raise ValueError('E66012A7 plot+148 result must be preserved as one byte')

def _encode_one(record_type: int, sequence: int, fields: EventFields, third_values: dict, retained_game_value: int) -> bytes:
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, record_type, sequence, 0)
    record[16:24] = b'\xff' * 8
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', record, offset, 65535, 0, 4294967295)
    struct.pack_into('<Q', record, 64, 0)
    city_owner = fields.owner
    flag = 22 if city_owner == retained_game_value else 6
    struct.pack_into('<I', record, 72, flag)
    struct.pack_into('<I', record, 76, 0)
    struct.pack_into('<I', record, 80, sequence)
    record[88:96] = fields.position_bytes
    struct.pack_into('<HHI', record, 96, city_owner & 65535, 2, fields.identifier)
    struct.pack_into('<HHI', record, 104, third_values['owner'] & 65535, 3, third_values['district_id'])
    record[112] = third_values['flag148']
    struct.pack_into('<I', record, 116, fields.value)
    struct.pack_into('<iI', record, 120, city_owner, 100)
    record[128] = 0
    return bytes(record)

def encode_wonder_records(first_sequence, fields, third_values, retained_game_value, *, normalizer_transform_present, thread_hook_present, writer_metadata_callback_present, empty_receiver_profile_verified, padding_policy):
    """Encode records AE then AF without performing native queries/effects.

    The caller's source order is AE enqueue, application effects, AF enqueue.
    Both byte records are prepared from the one retained-game getter value
    captured before AE, matching the native callback's shared metadata block.
    """
    verify_source_evidence()
    _validate_fields(fields)
    _validate_third_values(third_values)
    if type(first_sequence) is not int or not 1 <= first_sequence <= 4294967294:
        raise ValueError('E66012A7 needs two consecutive uint32 sequence values')
    if type(retained_game_value) is not int or not -(1 << 31) <= retained_game_value < 1 << 31:
        raise ValueError('E66012A7 retained game value must be a signed native DWORD')
    if normalizer_transform_present is not False or thread_hook_present is not False or writer_metadata_callback_present is not False:
        raise ValueError('E66012A7 encoding requires explicit absent transforms/hooks/metadata callback')
    if empty_receiver_profile_verified is not True:
        raise ValueError('E66012A7 padding zeroing requires verified empty AE/AF receiver state')
    if padding_policy != EMPTY_PADDING_POLICY:
        raise ValueError('E66012A7 requires the explicit zero-unread-empty-receiver-payload policy')
    first = _encode_one(174, first_sequence, fields, third_values, retained_game_value)
    second = _encode_one(175, first_sequence + 1, fields, third_values, retained_game_value)
    return (first, second)

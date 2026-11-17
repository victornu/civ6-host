"""Owned XP1 text argument profile for an explicitly selected religion name."""

from hashlib import sha256
from pathlib import Path
from struct import Struct

from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('work/x1trade/religion-custom-name-stage/6ce50e30a03269065c8aa07eb3165c2d0ba8f337b1ef20be35a3f605310bd05e.json',
          '6ce50e30a03269065c8aa07eb3165c2d0ba8f337b1ef20be35a3f605310bd05e')
ARCHIVE_SOURCE = ('work/x1trade/religion-custom-name-runtime-stage/archive-source.json',
                  '7c0b6ab8c03ebe7566a33174af3e491661d7e7edc31045bdf328f106e9ec04e0')
FOUND_RELIGION = 0xA4DAFFB5
PARAM_RELIGION_CUSTOM_NAME = 0x0ADDD95F
PARAM_RELIGION_TYPE = 0x22A25B8B
PARAM_INSERT_MODE = 0xAC2FDC09
VALUE_EXCLUSIVE = 0x97FEA5C6
VECTOR_VTABLE = 0x93FE28
SET_CSTRING = 0x84D300
_MAX_ARCHIVE = 6784  # Existing NativeActionTransport bounds.
_HEADER = Struct('<6I')
_ENTRY = Struct('<IHHHII')
_CELL = Struct('<HH4xQII')
_DWORD = Struct('<I')
_OWNED_STRING = 0x21000000
_CSTRING_TAG = 5
_MAX_NAME_BYTES = _MAX_ARCHIVE - (_HEADER.size + 3 * _ENTRY.size + 2 * _DWORD.size + 1)
_MAP_KEYS = {PARAM_RELIGION_TYPE, PARAM_INSERT_MODE, PARAM_RELIGION_CUSTOM_NAME}
_PROFILE_SLOTS = {0x60: 0x84C240, 0x68: 0x84C290, 0xB0: 0x84D430,
                  0x108: SET_CSTRING, 0x130: 0x84C9B0, 0x180: 0x84B7B0}
_LIVE_BODIES = ('vector_set_cstring', 'vector_set_array', 'variant_construct_array', 'variant_move',
                'variant_deepcopy', 'variant_release', 'variant_copy_wrapper', 'vector_copy')
_ARCHIVE_HEADER = (0xC45DE12F, 'player', FOUND_RELIGION, 0, 0x80000001, 3)


def verify_source():
    proof, archive = _source(SOURCE), _source(ARCHIVE_SOURCE)
    image, table = proof['image'], proof['native_parameter_vtable']
    if (proof['schema'] != 'civ6-host.xp1-custom-religion-name-source.static.v1'
            or proof['native_execution'] is not False or proof['action_admission'] is not False
            or proof['ui_unicode_length_qualified'] is not False
            or image['sha256'] != _XP1_PROFILE.image_sha256 or image['reference_abi_sha256'] != XP1_CORE_SHA256
            or int(table['rva'], 16) != VECTOR_VTABLE or proof['enum']['u32'] != PARAM_RELIGION_CUSTOM_NAME
            or {int(slot,16): int(row['target_rva'],16) for slot,row in table['selected_slots'].items()} != _PROFILE_SLOTS
            or archive['schema'] != 'civ6-host.xp1-custom-religion-name-archive.static.v1'
            or archive['native_execution'] is not False or archive['custom_name_command_observed'] is not False
            or archive['parent']['sha256'] != SOURCE[1] or archive['core']['sha256'] != image['sha256']
            or archive['wire']['header'] != _ARCHIVE_HEADER or archive['wire']['max_transport_bytes'] != _MAX_ARCHIVE
            or archive['wire']['max_text_bytes'] != _MAX_NAME_BYTES):
        raise ValueError('Rise and Fall religion name transport source differs')
    return proof, archive


def source_dependencies(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Religion name transport requires the exact installed Rise and Fall image')
    proof, archive = verify_source()
    refs = [dict(path=path,sha256=digest) for path,digest in (SOURCE,ARCHIVE_SOURCE)]
    refs += [proof['image'], archive['parent_manifest'], *proof['references'], *proof['ui']]
    pins = {}
    for row in refs:
        path = Path(row['path'])
        path = resolve_path(path if path.is_absolute() else resource_root() / path)
        if pins.setdefault(str(path.resolve()), row['sha256']) != row['sha256']:
            raise ValueError('Conflicting Rise and Fall religion name source pins')
    verify_pinned_files(pins)
    return pins


def validate_parameters(parameters):
    """Admit exact founding keys and representable name bytes, below archive size."""
    if (type(parameters) is not dict or set(parameters) != _MAP_KEYS or any(type(k) is not int for k in parameters)
            or type(parameters[PARAM_RELIGION_TYPE]) is not int
            or not 0 <= parameters[PARAM_RELIGION_TYPE] <= 0xFFFFFFFF
            or type(parameters[PARAM_INSERT_MODE]) is not int or parameters[PARAM_INSERT_MODE] != VALUE_EXCLUSIVE):
        raise ValueError('Religion name requires the exact founding parameter map')
    name = parameters[PARAM_RELIGION_CUSTOM_NAME]
    if type(name) is not bytes or not 1 <= len(name) <= _MAX_NAME_BYTES or b'\0' in name:
        raise ValueError('Religion name transport requires a nonempty bounded byte string without embedded NUL')
    return name


def verify_live(core, read, abi):
    if (abi.core_sha256 != XP1_CORE_SHA256 or abi.parameters != VECTOR_VTABLE
            or getattr(core, '_civ6_host_execution_image', None) is not _XP1_PROFILE):
        raise ValueError('Religion name transport requires the exact installed Rise and Fall Core')
    proof, archive = verify_source()
    base = core._handle
    sources = (proof['new_complete_code_spans'][name]['fragments'] for name in _LIVE_BODIES)
    spans = [row for fragments in sources for row in fragments] + list(archive['body_spans'])
    for row in spans:
        rva = int(row['rva'],16) if type(row['rva']) is str else row['rva']
        raw = bytes.fromhex(row['raw_hex'])
        size = row.get('length', row.get('bytes'))
        if (not 0 < len(raw) <= 4096 or len(raw) != size or sha256(raw).hexdigest() != row['sha256']
                or read(base + rva, len(raw)) != raw):
            raise ValueError('Live Rise and Fall religion name transport body differs')
    for key, target in _PROFILE_SLOTS.items():
        if read(base + VECTOR_VTABLE + key, 8) != (base + target).to_bytes(8,'little'):
            raise ValueError('Live Rise and Fall religion name parameter slot differs')
    for slots in archive['vtable_slots'].values():
        for row in slots.values():
            if read(base + row['rva'], 8) != (base + row['target_rva']).to_bytes(8,'little'):
                raise ValueError('Live Rise and Fall religion name archive slot differs')


def verify_stored(raw, read, owned_input, name):
    """Verify the native vector owns a distinct tag-5 copy and its final NUL."""
    if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != _CELL.size:
        raise RuntimeError('Native religion name parameter has an incomplete variant')
    tag, extra, address, width, flags = _CELL.unpack(raw)
    count = len(name) + 1
    if (tag != _CSTRING_TAG or extra or width != 1 or flags != (_OWNED_STRING | count)
            or not 0 < address <= 0xFFFFFFFFFFFFFFFF - count
            or owned_input <= address < owned_input + count
            or address <= owned_input < address + count
            or read(address, count) != name + b'\0'):
        raise RuntimeError('Native religion name parameter differs from its owned byte input')


def verify_archive(payload, player, parameters):
    """Read the exact bytes emitted by XP1 for this selected custom name."""
    verify_source()
    name = validate_parameters(parameters)
    if type(player) is not int or not 0 <= player < 64:
        raise ValueError('Foreign religion name archive player')
    if type(payload) is not bytes or len(payload) != len(name) + 1 + _HEADER.size + 3 * _ENTRY.size + 2 * _DWORD.size:
        raise RuntimeError('Religion name native archive size differs')
    if _HEADER.unpack_from(payload) != (_ARCHIVE_HEADER[0], player, *_ARCHIVE_HEADER[2:]):
        raise RuntimeError('Religion name native archive header differs')
    offset = _HEADER.size
    seen = set()
    for _ in range(len(parameters)):
        if offset + _ENTRY.size > len(payload):
            raise RuntimeError('Truncated religion name native archive entry')
        key, key_name_bytes, tag, extra, flags, width = _ENTRY.unpack_from(payload,offset)
        offset += _ENTRY.size
        if key not in parameters or key in seen or key_name_bytes or extra:
            raise RuntimeError('Foreign religion name native archive parameter')
        seen.add(key)
        if key == PARAM_RELIGION_CUSTOM_NAME:
            count = len(name) + 1
            valid = (tag,flags,width) == (_CSTRING_TAG,_OWNED_STRING | count,1)
            actual, expected = payload[offset:offset + count], name + b'\0'
        else:
            count = _DWORD.size
            valid = (tag,flags,width) == (2,0,0)
            actual, expected = payload[offset:offset + count], _DWORD.pack(parameters[key])
        if not valid or actual != expected:
            raise RuntimeError('Religion name native archive parameter value differs')
        offset += count
    if offset != len(payload) or seen != _MAP_KEYS:
        raise RuntimeError('Religion name native archive has trailing or missing data')
    return dict(archive_sha256=sha256(payload).hexdigest(), size_bytes=len(payload), operation=FOUND_RELIGION,
                name_bytes_sha256=sha256(name).hexdigest(), name_byte_count=len(name), source_sha256=ARCHIVE_SOURCE[1])

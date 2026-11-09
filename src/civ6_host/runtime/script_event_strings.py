"""Owned byte strings for the explicitly versioned GameEvents transport.

The EXE copies the counted input, then its Lua marshaller reads through the
first NUL. The native string export owns that normalization; Python retains
the original bytes for lifetime checks and private evidence.
"""
from dataclasses import dataclass
import ctypes as C
import hashlib

from .native.native_script_arguments import HKSArgument, pack_arguments

MAX_STRING_BYTES = 65536
MAX_TOTAL_STRING_BYTES = 1048576
SOURCE = ('evidence/host-xp2-congress-script-argument-source.json',
          'd9720be7939037d44808dd5ea6e544701acbe0fbe2fb48f0c8f1a769be692aab')


def source_dependencies(*, execution_image):
    from .a0_policy_unlock_current import _require_image, CURRENT_EXE_SHA256
    from .configuration_profiles import _source
    from .execution_images import identity
    from .paths import resource_root
    _require_image(execution_image)
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-congress-script-argument-source.v1'
            or proof['images']['core']['sha256'] != identity(execution_image)['image_sha256']
            or proof['images']['exe']['sha256'] != CURRENT_EXE_SHA256
            or proof['payload_contract']['slot'] != '0x30'):
        raise ValueError('String argument source differs from the selected native image')
    return {resource_root() / SOURCE[0]: SOURCE[1]}


def verify_live(core, read):
    from .configuration_profiles import _source
    image = getattr(core, '_civ6_host_execution_image', None)
    source_dependencies(execution_image=image)
    proof = _source(SOURCE)
    for name in ('core_congress_validation', 'core_argument_factory',
                 'core_argument_release', 'core_aux68_wrapper'):
        span = proof['spans'][name]
        raw = read(core._handle + int(span['start_rva'], 16), span['length'])
        if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live script string source differs at ' + name)
    return proof


@dataclass(frozen=True)
class StringArgument:
    raw: bytes

    def __post_init__(self):
        if type(self.raw) is not bytes or len(self.raw) > MAX_STRING_BYTES:
            raise ValueError('Script string argument exceeds its owned byte boundary')


class StringTransport(C.Structure):
    _fields_ = [('data', C.c_void_p), ('size', C.c_uint32), ('reserved', C.c_uint32)]


def has_strings(arguments):
    return any(isinstance(value, StringArgument) for value in arguments)


def pack_strings(arguments):
    """Reuse the map/scalar encoders, replacing only explicit string arguments."""
    from .script_event_maps import MapTransport, has_maps, pack_maps
    arguments = tuple(arguments)
    if not 0 < len(arguments) <= 64 or not has_strings(arguments):
        raise ValueError('String transport requires a bounded explicit string argument')
    projected = tuple(0 if isinstance(value, StringArgument) else value for value in arguments)
    if has_maps(projected):
        packed, maps, buffers = pack_maps(projected)
    else:
        packed, maps, buffers = pack_arguments(projected), (MapTransport * 0)(), []
    strings, total = [], 0
    for index, value in enumerate(arguments):
        if not isinstance(value, StringArgument):
            continue
        raw = value.raw
        total += len(raw)
        if total > MAX_TOTAL_STRING_BYTES:
            raise ValueError('Aggregate script string byte budget exceeded')
        buffer = C.create_string_buffer(raw, max(1, len(raw)))
        buffers.append(buffer)
        packed[index] = HKSArgument(3, len(strings))
        strings.append(StringTransport(C.addressof(buffer), len(raw), 0))
    return packed, maps, (StringTransport * len(strings))(*strings), buffers


def argument_evidence(arguments):
    from .script_event_maps import MAP_ARGUMENT_TYPES, argument_evidence as map_evidence
    rows = []
    for value in arguments:
        if isinstance(value, StringArgument):
            rows.append({'type': 'string', 'bytes': len(value.raw), 'raw_hex': value.raw.hex()})
        elif isinstance(value, MAP_ARGUMENT_TYPES):
            rows.extend(map_evidence((value,))['arguments_typed'])
        else:
            item = pack_arguments((value,))[0]
            rows.append({'type': 'boolean' if item.kind else 'uint32', 'raw': item.value})
    return {'arguments_typed': rows, 'arguments_uint32': None}


def require_string_transport(runtime):
    version = getattr(runtime.host, 'LAB_GameEventsStringArgumentVersion', None)
    if not callable(version):
        raise ValueError('Selected native host has no string argument transport')
    version.argtypes, version.restype = [], C.c_int
    if version() != 1:
        raise ValueError('Unknown native string argument transport version')


def dispatch_strings(runtime, name, arguments, *, method, output_initial):
    from .script_event_maps import MapTransport, require_map_transport
    require_map_transport(runtime)
    require_string_transport(runtime)
    if method not in ('Call', 'TestAll'):
        raise ValueError('Unknown string event dispatch method')
    packed, maps, strings, buffers = pack_strings(arguments)
    dispatch = runtime.host.LAB_GameEventsDispatchStringsResult
    dispatch.argtypes = [C.c_void_p, C.c_char_p, C.POINTER(HKSArgument), C.c_size_t,
        C.POINTER(MapTransport), C.c_size_t, C.POINTER(StringTransport), C.c_size_t,
        C.c_uint, C.POINTER(C.c_uint8), C.POINTER(C.c_uint8)]
    dispatch.restype = C.c_int
    valid, output = C.c_uint8(0), C.c_uint8(output_initial)
    runtime._status(runtime.root, dispatch(runtime.root, name, packed, len(arguments),
        maps, len(maps), strings, len(strings), int(method == 'TestAll'),
        C.byref(valid), C.byref(output)), 'protected GameEvents string dispatch')
    if runtime.lua['gettop'](runtime.root):
        raise RuntimeError('String event left a nonempty root stack')
    return bool(valid.value), output.value

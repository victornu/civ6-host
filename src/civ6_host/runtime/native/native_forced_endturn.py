"""UserForced parameter marshalling, confined to a native diagnostic.

This invokes Core's existing string setter and hash converter. It does not
write a fabricated message or manufacture production progress.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
from civ6_host.runtime.native.native_host import virtual
REASON_KEY = 884977781
USER_FORCED_HASH = 1913349224
_BODIES = ((7657312, 138, '243b799dd9998593e48d36363e43b676b7548dd1f6e40c842d5714acd65453fc'), (4781120, 79, '98fce72c33fc126e547acf08b94affa6c78b5dfbadf774fb886f9bdade4cad1d'))

def write_reason(core, parameters, read, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Use the verified setter on the newly constructed parameter object."""
    from civ6_host.runtime.xp1_turn_profile import turn_profile, forced_body_guards
    _turn_abi = turn_profile(core_sha256)
    base = core._handle
    if int.from_bytes(read(parameters, 8), 'little') != base + _turn_abi.vector_vtable_rva:
        raise ValueError('Forced EndTurn requires the native vector parameter-map type')
    for rva, size, digest in forced_body_guards(_turn_abi, _BODIES):
        if hashlib.sha256(read(base + rva, size)).hexdigest() != digest:
            raise ValueError('Forced EndTurn setter or conversion code changed')
    if int.from_bytes(read(base + _turn_abi.vector_vtable_rva + 176, 8), 'little') != base + _turn_abi.string_storage_rva:
        raise ValueError('Native parameter-map string storage method changed')
    lookup = virtual(core, parameters, 96, _turn_abi.vector_lookup_rva, C.c_void_p, C.c_uint32)
    if lookup(parameters, REASON_KEY):
        raise ValueError('Forced reason key already exists')
    setter = virtual(core, parameters, 264, _turn_abi.string_setter_rva, C.c_void_p, C.c_uint32, C.c_char_p)
    text = C.create_string_buffer(b'UserForced')
    setter(parameters, REASON_KEY, C.cast(text, C.c_char_p))
    value = lookup(parameters, REASON_KEY)
    if not value:
        raise RuntimeError('Native setter did not retain REASON')
    raw = read(value, 24)
    pointer = int.from_bytes(raw[8:16], 'little')
    if int.from_bytes(raw[:2], 'little') != 5 or not int.from_bytes(raw[20:24], 'little') & 1 << 29 or (not pointer) or (read(pointer, 11) != b'UserForced\x00'):
        raise RuntimeError('Native REASON descriptor differs from the string contract')
    convert = C.WINFUNCTYPE(C.c_uint32, C.c_void_p)(base + _turn_abi.reason_converter_rva)
    actual = convert(value)
    if actual != USER_FORCED_HASH:
        raise RuntimeError('Native UserForced hash differs')
    return (text, dict(reason='UserForced', reason_key=hex(REASON_KEY), reason_hash=hex(actual), native_string_setter_used=True, native_reason_converter_used=True, descriptor_type=5, string_roundtrip_verified=True, native_parameter_vtable_rva=hex(_turn_abi.vector_vtable_rva), native_parameter_constructor_rva=hex(_turn_abi.vector_ctor_rva), official_ui_parameter_representation='vector', tutorial_gate_qualified=False))

"""Host-owned nonempty AUX+A8 transport fixtures; no gameplay data or calls.

Only the bounded native supervisor may run this diagnostic. Python constructs
immutable IR, then returns control to a C export which owns every HKS operation
and protected error. No ctypes callback remains active during HKS marshalling.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
from pathlib import Path
import struct
from civ6_host.runtime.native.native_aux_map_adapter import AuxMapOp
from civ6_host.runtime.native.native_aux_map_conversion import TABLE
from civ6_host.runtime.native.native_aux_map_conversion import NUMBER
from civ6_host.runtime.native.native_aux_map_conversion import BOOLEAN
from civ6_host.runtime.native.native_aux_map_conversion import STRING_CONST
from civ6_host.runtime.native.native_aux_map_conversion import RAWSET
from civ6_host.runtime.native.native_aux_map_conversion import RAWSETI
from civ6_host.runtime.native.native_aux_map_conversion import STRING_BYTES
from civ6_host.runtime.native.native_aux_map_conversion import PROOF_SHA256 as CONVERSION_SHA256
from civ6_host.runtime.native.native_aux_map_conversion import validate_transport
from civ6_host.runtime.native.native_aux_map_conversion import verify_source_evidence as verify_conversion
from civ6_host.runtime.native.native_aux_map_conversion import LIST_PROOF_SHA256
from civ6_host.runtime.native.native_aux_map_conversion import STRING_PROOF_SHA256
from civ6_host.runtime.native.native_aux_map_conversion import ARRAY_PROOF_SHA256
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = '1220b46c9f64485f5b46cd2852e85a01a443c18f083f103f135a97e7db827c73'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_aux_map_diagnostic.py')))).resolve().parents[1] / 'evidence/native-aux-map-diagnostic' / f'{PROOF_SHA256}.json'
_OP = struct.Struct('<IIQ')
FIELD_COUNT = 16
STRING_VALUES = (b'', b'LOC_PRODUCTION_PREREQUISITE', 'Production : économie'.encode('utf-8'), b'\xff\xfe\x80', b'1234567890ABCDEF', bytes(range(1, 256)), b'X' * 4095, b'Y' * 65536, b'1234567890ABCDE')
_ERROR_MARKER = 'AUX-A8 expected checker failure'

def verify_source_evidence():
    verify_conversion()
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_aux_map_diagnostic.static.v1' or proof.get('hks_sha256') != '9fb4e34afa6666aafb519d6edb9c1e4e9add9cce2cecaa3b1e5bb8f08b168532' or proof.get('conversion_sha256') != CONVERSION_SHA256 or (proof['exports']['?lua_cpcall@@YAHPEAUlua_State@@P6AH0@ZPEAX@Z'] != '0x180016620'):
        raise RuntimeError('Pinned AUX map diagnostic source changed')
    return proof

def fixture_transport() -> bytes:
    """Fixed source-compatible nonempty IR, including exact signed/float bits."""
    ops = []

    def op(kind, arg=0, payload=0):
        ops.append(_OP.pack(kind, arg, payload))

    def number(value):
        op(NUMBER, 0, struct.unpack('<Q', struct.pack('<d', float(value)))[0])

    def descriptor(player, kind, identifier):
        op(TABLE, 0, 3)
        for key, value in enumerate((player, kind, identifier)):
            op(STRING_CONST, key)
            number(value)
            op(RAWSET)

    def array(values, push):
        op(TABLE, len(values), 0)
        for index, value in enumerate(values, 1):
            push(value)
            op(RAWSETI, index)

    def field(key, push):
        number(key)
        push()
        op(RAWSET)

    def string(value):
        op(STRING_BYTES, len(value))
        ops.append(value + bytes(16 - len(value) % 16))
    single = struct.unpack('<f', struct.pack('<f', 0.1))[0]
    op(TABLE, 0, FIELD_COUNT)
    field(-2147483648, lambda: number(65537))
    field(-1, lambda: number(42))
    field(3, lambda: op(BOOLEAN, 255))
    field(4, lambda: number(-2147483648))
    field(5, lambda: number(2147483647))
    field(6, lambda: number(16777217))
    field(7, lambda: number(single))
    field(8, lambda: number(-0.0))
    field(9, lambda: op(TABLE))
    field(10, lambda: array((0, 1, 255), lambda value: op(BOOLEAN, value)))
    field(11, lambda: array((-2147483648, -1, 0, 2147483647, 16777217), number))
    field(12, lambda: array((-0.0, 1.25, single), number))
    field(13, lambda: descriptor(-1, 3, -2147483648))
    field(14, lambda: array(((0, 1, 65536), (63, 2, 2147483647)), lambda value: descriptor(*value)))

    def nested_list():
        op(TABLE, 4, 0)
        number(-1)
        op(RAWSETI, 1)
        op(BOOLEAN, 255)
        op(RAWSETI, 2)
        op(TABLE, 2, 0)
        op(BOOLEAN, 0)
        op(RAWSETI, 1)
        array((16777217, single), number)
        op(RAWSETI, 2)
        op(RAWSETI, 3)
        op(TABLE, 0, 0)
        op(RAWSETI, 4)
    field(15, nested_list)
    field(16, lambda: array(STRING_VALUES, string))
    raw = b''.join(ops)
    validate_transport(raw)
    return raw

def checker_source() -> bytes:
    """Lua chunk returning a function(table); no globals are mutated."""
    return b"return function(t)\n  assert(type(t)=='table','AUX-A8 root is not a table')\n  local keys={[-2147483648]=true,[-1]=true,[3]=true,[4]=true,[5]=true,[6]=true,\n              [7]=true,[8]=true,[9]=true,[10]=true,[11]=true,[12]=true,[13]=true,[14]=true,[15]=true,[16]=true}\n  local function exactKeys(value,allowed,count)\n    assert(type(value)=='table','AUX-A8 nested value is not a table')\n    local n=0\n    for key,_ in pairs(value) do\n      assert(allowed[key]==true,'AUX-A8 unexpected key'); n=n+1\n    end\n    assert(n==count,'AUX-A8 wrong field count')\n  end\n  local function array(value,count)\n    local allowed={}\n    for index=1,count do allowed[index]=true end\n    exactKeys(value,allowed,count)\n  end\n  local function descriptor(value,player,kind,id)\n    exactKeys(value,{player=true,type=true,id=true},3)\n    assert(type(value.player)=='number' and value.player==player,'AUX-A8 descriptor player')\n    assert(type(value.type)=='number' and value.type==kind,'AUX-A8 descriptor type')\n    assert(type(value.id)=='number' and value.id==id,'AUX-A8 descriptor id')\n  end\n  local minimum=-2147483648\n  local maximum=2147483647\n  local precise=16777217\n  local single=13421773/134217728\n  exactKeys(t,keys,16)\n  assert(t[-2147483648]==65537 and t[-1]==42,'AUX-A8 signed numeric keys')\n  assert(type(t[3])=='boolean' and t[3]==true,'AUX-A8 bool255 normalization')\n  assert(type(t[4])=='number' and t[4]==minimum,'AUX-A8 int32 minimum')\n  assert(type(t[5])=='number' and t[5]==maximum,'AUX-A8 int32 maximum')\n  assert(type(t[6])=='number' and t[6]==precise and t[6]~=16777216,'AUX-A8 integer precision')\n  assert(type(t[7])=='number' and t[7]==single,'AUX-A8 float32 promotion')\n  assert(type(t[8])=='number' and t[8]==0 and 1/t[8]<0,'AUX-A8 negative zero')\n  array(t[9],0)\n  array(t[10],3)\n  assert(t[10][1]==false and t[10][2]==true and t[10][3]==true,'AUX-A8 boolean array')\n  array(t[11],5)\n  assert(t[11][1]==minimum and t[11][2]==-1 and t[11][3]==0 and\n         t[11][4]==maximum and t[11][5]==precise,'AUX-A8 int32 array')\n  array(t[12],3)\n  assert(t[12][1]==0 and 1/t[12][1]<0 and t[12][2]==1.25 and t[12][3]==single,\n         'AUX-A8 float array')\n  descriptor(t[13],-1,3,minimum)\n  array(t[14],2)\n  descriptor(t[14][1],0,1,65536)\n  descriptor(t[14][2],63,2,maximum)\n  array(t[15],4)\n  assert(t[15][1]==-1 and t[15][2]==true,'AUX-A8 mixed list values')\n  array(t[15][3],2)\n  assert(t[15][3][1]==false,'AUX-A8 nested list Boolean')\n  array(t[15][3][2],2)\n  assert(t[15][3][2][1]==precise and t[15][3][2][2]==single,\n         'AUX-A8 nested list numeric precision')\n  array(t[15][4],0)\n  array(t[16],9)\n  assert(type(t[16][1])=='string' and #t[16][1]==0,'AUX-A8 empty string')\n  assert(t[16][2]=='LOC_PRODUCTION_PREREQUISITE','AUX-A8 ASCII string')\n  assert(t[16][3]=='Production : '..string.char(195,169)..'conomie','AUX-A8 UTF8 bytes')\n  assert(t[16][4]==string.char(255,254,128),'AUX-A8 undecoded string bytes')\n  assert(t[16][5]=='1234567890ABCDEF','AUX-A8 aligned string boundary')\n  assert(#t[16][6]==255,'AUX-A8 byte range string length')\n  for index=1,255 do assert(string.byte(t[16][6],index)==index,'AUX-A8 byte range') end\n  assert(t[16][7]==string.rep('X',4095),'AUX-A8 page length string')\n  assert(t[16][8]==string.rep('Y',65536),'AUX-A8 bounded maximum string')\n  assert(t[16][9]=='1234567890ABCDE','AUX-A8 string terminator at record edge')\nend\n"

def string_budget_transport(*, excess=False) -> bytes:
    """Exactly 1 MiB of string bytes, or that bound plus one byte."""
    suffix = _OP.pack(RAWSET, 0, 0)
    item = _OP.pack(NUMBER, 0, 0) + _OP.pack(STRING_BYTES, 65536, 0) + b'a' * 65536 + bytes(16) + suffix
    wire = _OP.pack(TABLE, 0, 16 + int(excess)) + item * 16
    if excess:
        wire += _OP.pack(NUMBER, 0, 0) + _OP.pack(STRING_BYTES, 1, 0) + b'a' + bytes(15) + suffix
    return wire

def malformed_transports() -> tuple[tuple[str, bytes], ...]:
    """Invalid, safely allocated input spans for both complete validators."""
    programs = (('empty', ()), ('unknown_opcode', ((99, 0, 0),)), ('non_table_result', ((NUMBER, 0, 0),)), ('rawset_underflow', ((TABLE, 0, 0), (RAWSET, 0, 0))), ('boolean_out_of_range', ((TABLE, 0, 0), (BOOLEAN, 256, 0))), ('rawseti_zero_index', ((TABLE, 0, 0), (TABLE, 0, 0), (RAWSETI, 0, 0))), ('nonfinite_number', ((TABLE, 0, 0), (NUMBER, 0, 9221120237041090560))), ('string_index_out_of_range', ((TABLE, 0, 0), (STRING_CONST, 3, 0))), ('allocation_hint_out_of_range', ((TABLE, 65537, 0),)), ('stack_bound', ((TABLE, 0, 0),) * 17))
    cases = [(name, b''.join((_OP.pack(*op) for op in ops))) for name, ops in programs]
    prefix = _OP.pack(TABLE, 0, 1) + _OP.pack(NUMBER, 0, 0)
    suffix = _OP.pack(RAWSET, 0, 0)
    for name, length, payload, raw in (('string_length_overflow', 4294967295, 0, b''), ('string_per_value_bound', 65537, 0, b''), ('string_borrowed_pointer_refused', 1, 19087360, b'a' + bytes(15)), ('string_missing_records', 33, 0, bytes(16)), ('string_early_nul', 3, 0, b'a\x00b' + bytes(13)), ('string_missing_terminator', 16, 0, b'a' * 32), ('string_nonzero_padding', 1, 0, b'a\x00b' + bytes(13))):
        cases.append((name, prefix + _OP.pack(STRING_BYTES, length, payload) + raw + suffix))
    cases.append(('string_global_byte_bound', string_budget_transport(excess=True)))
    return tuple(cases)

def run_diagnostic(runtime, child, emit=None) -> dict:
    """Run only the protected C transport diagnostic on an owned live child.

    This function is defined for the root's native supervisor. Unit tests use
    fakes and do not run game DLLs. All buffers stay alive through each export.
    """
    if getattr(runtime, 'closed', True):
        raise RuntimeError('AUX map diagnostic requires an open script runtime')
    pointer = runtime.registry.validate(child)
    if type(pointer) is not int or not 0 < pointer < 1 << 63:
        raise ValueError('AUX map diagnostic requires a non-null registered child')
    if runtime.lua['gettop'](pointer) != 0:
        raise RuntimeError('AUX map diagnostic requires an empty child stack')
    verify_source_evidence()
    if C.sizeof(AuxMapOp) != 16 or AuxMapOp.payload.offset != 8:
        raise RuntimeError('AUX map opcode ABI mismatch')
    try:
        validate = runtime.host.LAB_AuxMapValidateTransport
        diagnostic = runtime.host.LAB_AuxMapDiagnostic
    except AttributeError as exc:
        raise RuntimeError('Native host lacks the AUX map diagnostic export') from exc
    validate.argtypes, validate.restype = ([C.POINTER(AuxMapOp), C.c_uint32], C.c_int)
    diagnostic.argtypes = [C.c_void_p, C.POINTER(AuxMapOp), C.c_uint32, C.c_char_p, C.c_size_t]
    diagnostic.restype = C.c_int
    wire = fixture_transport()
    checker = checker_source()
    if not checker or len(checker) > 16384 or b'\x00' in checker:
        raise RuntimeError('Invalid fixed AUX map checker')
    data = (AuxMapOp * (len(wire) // 16)).from_buffer_copy(wire)
    peak = validate_transport(wire)
    if validate(data, len(data)) != peak:
        raise RuntimeError('Native AUX map validator disagrees on fixture stack')
    boundary = string_budget_transport()
    boundary_data = (AuxMapOp * (len(boundary) // 16)).from_buffer_copy(boundary)
    if validate(boundary_data, len(boundary_data)) != validate_transport(boundary):
        raise RuntimeError('Native AUX map validator disagrees on exact string budget')
    rejected = []
    for name, raw in malformed_transports():
        try:
            validate_transport(raw)
        except ValueError:
            pass
        else:
            raise RuntimeError('Malformed AUX map fixture passed Python validation')
        bad = (AuxMapOp * (len(raw) // 16)).from_buffer_copy(raw) if raw else None
        if validate(bad, len(raw) // 16) != 0:
            raise RuntimeError(f'Native AUX map validator accepted {name}')
        status = diagnostic(pointer, bad, len(raw) // 16, checker, len(checker))
        if status != -1701 or runtime.lua['gettop'](pointer) != 0:
            raise RuntimeError(f'Malformed AUX map transport reached HKS: {name}/{status}')
        rejected.append(name)

    def check(source):
        runtime.registry.validate(child)
        status = diagnostic(pointer, data, len(data), source, len(source))
        runtime._status(pointer, status, 'protected AUX map fixture checker')
        if runtime.lua['gettop'](pointer) != 0:
            raise RuntimeError('AUX map diagnostic left values on the child stack')
    check(checker)
    error_checker = b"return function(t) assert(false, 'AUX-A8 expected checker failure') end"
    try:
        check(error_checker)
    except RuntimeError as exc:
        if _ERROR_MARKER not in str(exc) or runtime.lua['gettop'](pointer) != 0:
            raise
    else:
        raise RuntimeError('AUX map error checker did not return a protected failure')
    check(checker)
    if runtime.evaluate_text(child, b"return 'aux-map-diagnostic-recovered'", b'@aux_map_diagnostic_recovery') != b'aux-map-diagnostic-recovered':
        raise RuntimeError('Child did not recover after AUX map diagnostic error')
    if runtime.lua['gettop'](pointer) != 0:
        raise RuntimeError('AUX map diagnostic recovery left a nonempty stack')
    report = {'schema': 'native-aux-map-diagnostic-v1', 'synthetic_fixture': True, 'gameplay_validated': False, 'native_hks_transport_verified': True, 'field_count': FIELD_COUNT, 'nested_heterogeneous_list_transport': True, 'inline_c_string_transport': True, 'largest_string_bytes': max(map(len, STRING_VALUES)), 'exact_string_byte_budget_validated': 1048576, 'operation_count': len(data), 'peak_added_stack': peak, 'transport_sha256': hashlib.sha256(wire).hexdigest(), 'malformed_transports_refused': tuple(rejected), 'checker_error_recovered': True, 'stack_balanced': True, 'source_proof_sha256': PROOF_SHA256, 'conversion_proof_sha256': CONVERSION_SHA256, 'list_source_proof_sha256': LIST_PROOF_SHA256, 'string_source_proof_sha256': STRING_PROOF_SHA256, 'array_source_proof_sha256': ARRAY_PROOF_SHA256}
    if emit is not None:
        emit('native_aux_map_synthetic_transport_verified', **report)
    return report

def run_optional_diagnostic(runtime, child, emit=None):
    """Exercise B0's nil-versus-table branch in real, protected native HKS."""
    from civ6_host.runtime.native.native_production_placement import verify_source
    from civ6_host.runtime.native.native_production_placement import PROOF_SHA256 as placement_pin
    verify_source()
    if getattr(runtime, 'closed', True):
        raise RuntimeError('Optional map diagnostic needs an open script runtime')
    pointer = runtime.registry.validate(child)
    if runtime.lua['gettop'](pointer) != 0:
        raise RuntimeError('Optional map diagnostic needs an empty stack')
    native = runtime.host.LAB_AuxOptionalMapDiagnostic
    native.argtypes = [C.c_void_p, C.POINTER(AuxMapOp), C.c_uint32, C.c_char_p, C.c_size_t]
    native.restype = C.c_int
    fixtures = (('empty_native_map_is_nil', _OP.pack(TABLE, 0, 0), b'return function(v) assert(v==nil) end'), ('omitted_nil_field_is_table', _OP.pack(TABLE, 0, 1), b"return function(v) assert(type(v)=='table' and next(v)==nil) end"), ('nonempty_native_map_is_table', fixture_transport(), checker_source()))

    def check(raw, source, expected_status=None):
        runtime.registry.validate(child)
        data = (AuxMapOp * (len(raw) // 16)).from_buffer_copy(raw)
        status = native(pointer, data, len(data), source, len(source))
        if expected_status is not None:
            if status != expected_status or runtime.lua['gettop'](pointer) != 0:
                raise RuntimeError('Malformed optional-map root reached HKS')
        else:
            runtime._status(pointer, status, 'protected AUX+B0 checker')
            if runtime.lua['gettop'](pointer) != 0:
                raise RuntimeError('Optional map diagnostic left stack values')
    for _, raw, source in fixtures:
        check(raw, source)
    check(_OP.pack(TABLE, 1, 0), fixtures[0][2], -1701)
    impossible = _OP.pack(TABLE, 0, 0) + _OP.pack(NUMBER, 0, 0) + _OP.pack(BOOLEAN, 1, 0) + _OP.pack(RAWSET, 0, 0)
    check(impossible, fixtures[0][2], -1701)
    try:
        check(fixtures[0][1], b"return function(v) error('AUX-B0 expected checker failure') end")
    except RuntimeError as exc:
        if 'AUX-B0 expected checker failure' not in str(exc) or runtime.lua['gettop'](pointer) != 0:
            raise
    else:
        raise RuntimeError('Optional map checker failure was not protected')
    check(fixtures[1][1], fixtures[1][2])
    result = {'schema': 'civ6rl.native_optional_map_diagnostic.v1', 'cases': [name for name, _, _ in fixtures], 'malformed_root_refusals': 2, 'protected_error_recovered': True, 'stack_balanced': True, 'source_proof_sha256': placement_pin, 'native_hks_transport_verified': True, 'array_source_proof_sha256': ARRAY_PROOF_SHA256, 'gameplay_validated': False, 'eligible_for_training': False}
    if emit is not None:
        emit('native_aux_optional_map_transport_verified', **result)
    return result

"""Internal XP2 EXECUTE_SCRIPT sender for source-qualified Lua objects."""
from __future__ import annotations

import ctypes as C
from contextlib import contextmanager
import struct

from .configuration_profiles import XP2_CORE_SHA256, _source
from .native.native_aux_map_conversion import encode_script_request_table
from .native.native_player_operation_request import _GuardedStorage
from .xp2_initial_choice_source import ENTRIES, VTABLES, verify_live
from .xp2_mutable_map_profile import verify_live as verify_tree

_OWNERSHIP = ('evidence/host-xp2-script-request-child-ownership.json',
              '71629e45819acfa3c5aaefda15a7879bd320f0e8fdd9517ec2706181fbf6ed14')
_ROOT = VTABLES['parameters']
_TREE = 0xabf080
_RESOLVER = 0xabeff8
_ROOT_SLOTS = {0x20: 0x989d0, 0x60: ENTRIES['lookup'], 0xa8: 0x9a6a50, 0x108: 0x9a6e40,
               0x130: 0x9a64f0, 0x138: 0x9a7590}
_TREE_SLOTS = {0x20: 0x989d0, 0x60: 0x99f5c0, 0xa8: 0x9a0240, 0x108: 0x9a6e40,
               0x130: 0x99fee0, 0x138: 0x9a0d30}


def deliver_script_operation(continuation, player, parameters):
    """Use the retained native action queue inside an active XP2 transition."""
    continuation.check(active=True)
    backend = continuation.owner
    if (backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or type(player) is not int
            or continuation.observation['player_id'] != player):
        raise ValueError('Script operation requires the active XP2 player view')
    transport = continuation.transport
    transport.require_empty_native_queue()
    receipt = submit_script_operation(
        backend.core, backend.context, player, parameters, read=backend.runtime.read)
    pending = transport.pending
    # Same official PlayerOperation archive used for research and civics.
    if len(pending) != 1 or pending[0][:4] != struct.pack('<I', 3294486831):
        raise RuntimeError('Script request did not emit exactly one player-operation archive')
    transport.deliver_one()
    continuation.prefix.deferred_events.drain_empty_receivers()
    transport.require_empty_native_queue()
    return {**receipt, 'native_archive_delivered': True}


def _check_stored_value(read, address, value, *, child=None):
    if not address:
        raise RuntimeError('XP2 script-operation setter did not store its key')
    raw = read(address, 24)
    tag, _, payload, size, flags = struct.unpack('<H6sQII', raw)
    kind = type(value)
    if kind is dict:
        matches = tag == 10 and flags == 0x05000000 and size == 0 and payload == child
    elif kind is bytes:
        matches = (tag == 5 and flags & 0xff000000 in (0x20000000, 0x21000000)
                   and bool(payload) and read(payload, len(value) + 1) == value + b'\0')
    elif kind is bool:
        matches = tag == 1 and flags == 0 and payload & 0xff == int(value)
    else:
        matches = tag == 2 and flags == 0 and payload & 0xffffffff == value & 0xffffffff
    if not matches:
        raise RuntimeError('XP2 script-operation native parameter differs from its input')


def submit_script_operation(core, context, player, parameters, *, read):
    """Submit on the owning native thread after the caller validates its Lua context.

    This mirrors UI.RequestPlayerOperation for the EXECUTE_SCRIPT operation.
    The return indicates invocation only. The caller must observe the archive,
    event delivery and effect separately before publishing a gameplay result.
    """
    if (type(player) is not int or not 0 <= player < 64
            or type(context) is not int or not 0 < context < (1 << 47)):
        raise ValueError('Invalid XP2 player or context')
    base = core._handle
    with _script_parameters(base, parameters, read=read) as storage:
        if read(context, 8) != struct.pack('<Q', base + VTABLES['outer']):
            raise ValueError('Unexpected XP2 outer interface')
        request = C.WINFUNCTYPE(None, C.c_void_p, C.c_int32, C.c_uint32, C.c_void_p)(
            base + ENTRIES['request'])
        request(context, player, 0xc665ad08, storage.address)
        storage.check()
    return {'request_invoked': True, 'native_parameters_verified': True,
            'gameplay_outcome_verified': False}


@contextmanager
def _script_parameters(base, parameters, *, read):
    encode_script_request_table(parameters)
    if type(parameters.get(b'OnStart')) is not bytes or not parameters[b'OnStart']:
        raise ValueError('EXECUTE_SCRIPT requires a named OnStart event')

    def check_objects(table):
        for item in table.values():
            if type(item) is dict:
                if not any(type(key) is bytes for key in item):
                    raise ValueError('Nested Lua array classification is not admitted')
                check_objects(item)

    check_objects(parameters)
    proof = _source(_OWNERSHIP)
    if proof['core_sha256'] != XP2_CORE_SHA256:
        raise ValueError('Unexpected XP2 script-operation source')
    verify_live(base, read, 'research')
    verify_tree(base, read)
    for address, expected in proof['instructions'].items():
        expected = bytes.fromhex(expected)
        if read(base + int(address, 16), len(expected)) != expected:
            raise ValueError('XP2 script-operation ownership instructions differ')

    def qword(address):
        return struct.unpack('<Q', read(address, 8))[0]

    for vtable, slots in ((_ROOT, _ROOT_SLOTS), (_TREE, _TREE_SLOTS)):
        for slot, target in slots.items():
            if qword(base + vtable + slot) != base + target:
                raise ValueError('Unexpected XP2 script-operation setter')

    def bind(rva, result, *args):
        return C.WINFUNCTYPE(result, *args)(base + rva)

    pointer, word = C.c_void_p, C.c_uint32
    ctor = bind(ENTRIES['parameter_ctor'], pointer, pointer)
    dtor = bind(ENTRIES['parameter_dtor'], None, pointer)
    get_resolver = bind(0x989d0, pointer, pointer)
    resolve_name = bind(0x9a3f10, word, pointer, C.c_char_p)
    clone = bind(0x99d920, pointer, pointer, pointer, pointer)
    storage = _GuardedStorage(72, 'XP2 script-operation vector')

    def populate(destination, table, vtable):
        slots = _ROOT_SLOTS if vtable == _ROOT else _TREE_SLOTS
        lookup = bind(slots[0x60], pointer, pointer, word)
        resolver = get_resolver(destination)
        if not resolver or qword(resolver) != base + _RESOLVER:
            raise RuntimeError('XP2 script-operation key resolver differs')
        resolved = {}
        for key, value in table.items():
            key = resolve_name(resolver, key) if type(key) is bytes else key & 0xffffffff
            if key in resolved:
                raise ValueError('XP2 script-operation keys collide after resolution')
            resolved[key] = value
        for key, value in resolved.items():
            kind = type(value)
            child = None
            if kind is dict:
                empty = C.create_string_buffer(struct.pack('<IIQII', 10, 0, 0, 0, 0x05000000))
                output = C.create_string_buffer(24)
                address = C.addressof(output)
                if clone(resolver, address, C.addressof(empty)) != address:
                    raise RuntimeError('XP2 child variant constructor differed')
                tag, _, child, size, flags = struct.unpack('<IIQII', output.raw)
                if (tag, size, flags) != (10, 0, 0x05000000) or not child or qword(child) != base + _TREE:
                    raise RuntimeError('Unexpected XP2 child variant')
                # The parent takes ownership before recursive population, so
                # its destructor also cleans up on a later validation failure.
                bind(slots[0xa8], None, pointer, word, pointer)(destination, key, child)
            elif kind is bytes:
                bind(slots[0x108], None, pointer, word, C.c_char_p)(destination, key, value)
            elif kind is bool:
                bind(slots[0x138], None, pointer, word, C.c_uint8)(destination, key, value)
            else:
                bind(slots[0x130], None, pointer, word, word)(destination, key, value & 0xffffffff)
            storage.check()
            _check_stored_value(read, lookup(destination, key), value, child=child)
            if child is not None:
                populate(child, value, _TREE)

    result = ctor(storage.address)
    storage.check()
    if result != storage.address or qword(storage.address) != base + _ROOT:
        raise RuntimeError('Unexpected XP2 script-operation vector')
    try:
        if read(storage.address + 0x28, 24) != bytes(24):
            raise RuntimeError('XP2 script-operation vector is not empty')
        populate(storage.address, parameters, _ROOT)
        yield storage
    finally:
        dtor(storage.address)
        storage.check()

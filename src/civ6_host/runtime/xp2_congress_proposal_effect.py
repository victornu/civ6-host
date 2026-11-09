"""Private own-proposal/LOOKED readback on the exact retained XP2 owner.

This reader makes no request and settles no journal. Its caller must join the
two snapshots to an entirely delivered, same-owner native batch. The final
multiset proves the requested own state delta, not individual packet ACKs.
"""
import ctypes as C
from collections import Counter
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import struct
from weakref import WeakKeyDictionary

from .a0_policy_unlock_current import _require_image
from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path
from .source_verification import file_sha256

SOURCE = ('work/trade-common-client/congress-proposal-effect-source.json',
          '11acfc6fe4262dec0374918c89f1c5f129906fd171da181b4c020fedf7f81807')
MAX_ROWS = 4096
_MAX_POINTER = 0x7fffffffffff
_GAME = 0xb8aa68
_STRIDE = 0x140
_CALLS = {0x3bd000: (), 0x26c770: (C.c_int32,), 0x7d08c0: (),
          0x2209a0: (C.c_void_p, C.c_uint32)}
_ROOTS = dict(selection=0x3c0a00, proposal_constructor=0x3b9a50,
    proposal_copy=0x3b9970, proposal_vector_grow=0x3c0210,
    congress_manager=0x3bd000, definition_table=0x7d08c0,
    looked_predicate=0x5de300, proposal_candidates=0x3bd320,
    definition_lookup=0x2209a0, player_congress_data=0x26c770,
    player_component_lookup=0x72e3d0)


def _verify(proof):
    """Exact source header and ABI, in addition to the immutable JSON pin."""
    expected_accessors = (
        ('0x3bd000', 'void* getter(void)'),
        ('0x26c770', 'void* getter(int32 player)'),
        ('0x7d08c0', 'void* getter(void)'),
        ('0x2209a0', 'void* lookup(void* table,uint32 typeKey)'))
    if (proof['schema'] != 'civ6-host.congress-own-proposal-effects.static.v1'
            or proof['native_execution'] is not False
            or proof['process_memory_read'] is not False or proof['host_modified'] is not False
            or proof['operation_values'] != dict(WORLD_CONGRESS_DISCUSSION_SELECTION=0xe4d75de3,
                                                WORLD_CONGRESS_LOOKED_AT_AVAILABLE=0x1b75025a)
            or proof['correspondence']['tuple_layout'] != dict(manager_vector_begin='0x168',
                manager_vector_capacity='0x170', manager_vector_count='0x178', stride='0x140',
                own_sender='0x118', target='0xc', definition_index='0x138')
            or tuple((r['rva'], r['abi']) for r in proof['minimal_private_read_option']['accessors'])
               != expected_accessors
            or {k: int(v['root_rva'], 16) for k, v in proof['functions'].items()} != _ROOTS
            or tuple(int(s['rva'], 16) for s in proof['dispatch_spans'])
               != (0x30d1f2, 0x30d285, 0x30de4e, 0x30e3e5)):
        raise ValueError('Congress proposal effect source contract changed')
    for span in _spans(proof):
        if (span['dir64_relocations'] or type(span['bytes']) is not int
                or not 0 < span['bytes'] <= 4096
                or int(span['end_rva'], 16) - int(span['rva'], 16) != span['bytes']):
            raise ValueError('Congress proposal effect source span changed')
    return proof


def _spans(proof):
    return [s for row in proof['functions'].values() for s in row['spans']] + list(proof['dispatch_spans'])


def source(*, execution_image):
    _require_image(execution_image)
    proof = _verify(_source(SOURCE))
    if (proof['core']['sha256'] != execution_image.image_sha256
            or Path(proof['core']['path']).resolve() != Path(execution_image.path).resolve()):
        raise ValueError('Congress proposal effect execution image changed')
    return proof


def source_dependencies(*, execution_image):
    proof = source(execution_image=execution_image)
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), *proof['parents']]
    pins = {}
    for row in refs:
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Congress proposal source path escaped resources')
        path = resolve_path(resource_root() / relative)
        if file_sha256(path) != row['sha256']:
            raise ValueError('Congress proposal effect source dependency changed')
        pins[str(path.resolve())] = row['sha256']
    core_path = Path(proof['core']['path'])
    if file_sha256(core_path) != proof['core']['sha256']:
        raise ValueError('Congress proposal effect installed image changed')
    pins[str(core_path.resolve())] = proof['core']['sha256']
    module = Path(__file__).resolve()
    pins[str(module)] = file_sha256(module)
    return pins


def _pointer(value, *, size=1, nullable=False):
    if nullable and (value is None or type(value) is int and value == 0):
        return 0
    if (type(value) is not int or type(size) is not int or not 0 < size
            or not 0x10000 <= value <= _MAX_POINTER
            or size - 1 > _MAX_POINTER - value):
        raise ValueError('Invalid bounded Congress native pointer')
    return value


def _bytes(runtime, address, size):
    _pointer(address, size=size)
    if size > 4096:
        raise ValueError('Congress native read exceeds its bound')
    raw = runtime.read(address, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError('Incomplete Congress native memory copy')
    return raw


def _qword(runtime, address):
    return struct.unpack('<Q', _bytes(runtime, address, 8))[0]


def _int(runtime, address):
    return struct.unpack('<i', _bytes(runtime, address, 4))[0]


def _call(runtime, base, rva, *arguments):
    types = _CALLS.get(rva)
    if types is None or len(arguments) != len(types):
        raise ValueError('Unknown Congress read accessor or ABI')
    # No fabricated receiver: both zero-argument getters are truly static.
    # The fixture interface receives the complete native argument type list.
    call = getattr(runtime, 'call', None)
    value = (call(base + rva, C.c_void_p, types, *arguments) if call is not None
             else C.WINFUNCTYPE(C.c_void_p, *types)(base + rva)(*arguments))
    return _pointer(value, nullable=True)


@dataclass(eq=False)
class _Reader:
    saved: object
    backend: object
    continuation: object
    prefix: object
    identity: object
    core: object
    runtime: object
    base: int
    image: object
    episode_id: str
    game_generation: str
    records: object = field(default_factory=WeakKeyDictionary)
    serial: int = 0


@dataclass(frozen=True, eq=False)
class Snapshot:
    """Administrative values only; the seal cannot be recreated by copying."""
    _reader: object
    serial: int
    player_id: int
    turn: int
    sequence: int
    marker_turn: int
    own_rows: tuple
    resolved_types: tuple


def _values(s):
    return (s.serial, s.player_id, s.turn, s.sequence, s.marker_turn, s.own_rows, s.resolved_types)


def _owner(saved, active):
    from .xp1_world_input import _owner as require_owner
    from .xp1_session_view import _reference
    if type(active) is not bool:
        raise ValueError('Congress effect owner mode must be Boolean')
    b, c, p, identity = require_owner(saved, active=active)
    if (b.load_abi.core_sha256 != XP2_CORE_SHA256
            or getattr(saved, 'world_congress_diagnostic', False) is not True):
        raise ValueError('Congress effect requires the retained explicit XP2 owner')
    pid, turn = c.observation['player_id'], c.observation['turn']
    if (type(pid) is not int or not 0 <= pid < 64 or type(turn) is not int
            or not 0 <= turn <= 100000):
        raise ValueError('Invalid Congress effect perspective')
    _reference(saved, pid)
    runtime, base = b.runtime, _pointer(b.core._handle)
    image = getattr(b.core, '_civ6_host_execution_image', None)
    _require_image(image)
    owner = getattr(c, '_xp2_congress_proposal_effect_reader', None)
    if owner is None:
        owner = _Reader(saved, b, c, p, identity, b.core, runtime, base, image,
                        identity.episode_id, identity.game_generation)
        c._xp2_congress_proposal_effect_reader = owner
    if (type(owner) is not _Reader
            or any(a is not e for a, e in zip(
                (owner.saved, owner.backend, owner.continuation, owner.prefix, owner.identity,
                 owner.core, owner.runtime, owner.image), (saved, b, c, p, identity, b.core, runtime, image)))
            or owner.base != base or owner.episode_id != identity.episode_id
            or owner.game_generation != identity.game_generation):
        raise ValueError('Congress effect retained owner changed')
    return owner, pid, turn, c.sequence


def _vector(runtime, manager):
    raw = _bytes(runtime, manager + 0x168, 20)
    pointer, capacity, _, count = struct.unpack('<QIII', raw)
    if count > capacity or capacity > MAX_ROWS:
        raise ValueError('Congress proposal vector count/capacity exceeds its bound')
    if capacity:
        _pointer(pointer, size=capacity * _STRIDE)
    elif pointer:
        _pointer(pointer)
    return raw, pointer, count


def _definition_rows(runtime, table):
    header = _bytes(runtime, table, 40)
    primary, primary_end, _, secondary, secondary_end = struct.unpack('<QQQQQ', header)
    arrays = []
    for begin, end in ((primary, primary_end), (secondary, secondary_end)):
        if end < begin or (end - begin) % 8 or (end - begin) // 8 > MAX_ROWS:
            raise ValueError('Congress definition pointer vector exceeds its bound')
        if end != begin:
            _pointer(begin, size=end - begin)
        elif begin:
            _pointer(begin)
        rows = []
        for address in range(begin, end, 8):
            row = _pointer(_qword(runtime, address), size=0x1c)
            index, key = struct.unpack('<iI', _bytes(runtime, row + 0x14, 8))
            if index < 0:
                raise ValueError('Congress definition index is invalid')
            rows.append((row, index, key))
        arrays.append(tuple(rows))
    if any(a[2] > b[2] for a, b in zip(arrays[1], arrays[1][1:])):
        raise ValueError('Congress definition hash index is not sorted')
    return header, tuple(arrays)


def _resolve(runtime, base, keys):
    if not keys:
        return ()
    table = _pointer(_call(runtime, base, 0x7d08c0), size=40)
    header, (primary, secondary) = _definition_rows(runtime, table)
    resolved = []
    for key in keys:
        row = _pointer(_call(runtime, base, 0x2209a0, table, key), size=0x1c)
        candidates = primary[key:key+1] if key < len(primary) else tuple(r for r in secondary if r[2] == key)
        if not candidates or row != candidates[0][0]:
            raise ValueError('Congress official definition lookup returned an unknown row')
        index = _int(runtime, row + 0x14)
        if index != candidates[0][1]:
            raise ValueError('Congress definition changed during lookup')
        resolved.append((key, index))
    if _bytes(runtime, table, 40) != header:
        raise ValueError('Congress definition table changed during lookup')
    return tuple(resolved)


def read(saved, *, type_keys=(), active=True):
    """Borrow official accessors, then copy only this player's own tuples.

    Caller owns FIFO emptiness at the two batch boundaries. No action, callback,
    flush, publication, worker scheduling or public observation is performed.
    """
    if (type(type_keys) not in (list, tuple) or len(type_keys) > MAX_ROWS
            or any(type(k) is not int or not 0 <= k <= 0xffffffff for k in type_keys)
            or len(set(type_keys)) != len(type_keys)):
        raise ValueError('Congress effect needs bounded unique unsigned type keys')
    owner, pid, turn, sequence = _owner(saved, active)
    runtime, base = owner.runtime, owner.base
    source_dependencies(execution_image=owner.image)
    proof = source(execution_image=owner.image)
    for span in _spans(proof):
        raw = _bytes(runtime, base + int(span['rva'], 16), span['bytes'])
        if hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Congress proposal effect live source differs at ' + span['rva'])
    game = _pointer(_qword(runtime, base + _GAME), size=0xc4)
    if _int(runtime, game + 0xc0) != turn:
        raise ValueError('Congress effect native turn differs from its owner')
    manager = _pointer(_call(runtime, base, 0x3bd000), size=0x17c)
    player = _pointer(_call(runtime, base, 0x26c770, pid), size=0x2cc)
    header, vector, count = _vector(runtime, manager)
    own = []
    for index in range(count):
        address = vector + index * _STRIDE
        sender = _int(runtime, address + 0x118)
        if sender != pid:
            continue  # Do not copy target/type or retain another player's row.
        target = _int(runtime, address + 0xc)
        definition = _int(runtime, address + 0x138)
        if definition < 0:
            raise ValueError('Congress own proposal has an invalid definition index')
        own.append((sender, target, definition))
    marker = _int(runtime, player + 0x2c8)
    resolved = _resolve(runtime, base, tuple(type_keys))
    if (_vector(runtime, manager)[0] != header
            or _int(runtime, player + 0x2c8) != marker
            or _qword(runtime, base + _GAME) != game
            or _int(runtime, game + 0xc0) != turn):
        raise ValueError('Congress native storage changed during its read')
    if _owner(saved, active) != (owner, pid, turn, sequence):
        raise ValueError('Congress effect owner revision changed during its read')
    owner.serial += 1
    snapshot = Snapshot(owner, owner.serial, pid, turn, sequence, marker, tuple(own), resolved)
    owner.records[snapshot] = _values(snapshot)
    return snapshot


def _check_snapshot(owner, snapshot, pid, turn, sequence):
    if (type(snapshot) is not Snapshot or snapshot._reader is not owner
            or snapshot not in owner.records or owner.records[snapshot] != _values(snapshot)
            or (snapshot.player_id, snapshot.turn, snapshot.sequence) != (pid, turn, sequence)):
        raise ValueError('Congress effect snapshot is foreign, mutated or stale')


def _description(snapshot):
    return dict(player_id=snapshot.player_id, turn=snapshot.turn, sequence=snapshot.sequence,
        marker_turn=snapshot.marker_turn, own_rows=[dict(sender=s, target=t, type_index=i)
            for s, t, i in snapshot.own_rows],
        resolved_types=[dict(type_key=k, type_index=i) for k, i in snapshot.resolved_types])


def compare(saved, before, after, *, selections=(), looked=True, active=True):
    """Return own-state evidence only; delivery and journal release stay external."""
    owner, pid, turn, sequence = _owner(saved, active)
    _check_snapshot(owner, before, pid, turn, sequence)
    _check_snapshot(owner, after, pid, turn, sequence)
    if after.serial <= before.serial:
        raise ValueError('Congress effect snapshots are not ordered before/after reads')
    if (type(looked) is not bool or type(selections) not in (list, tuple)
            or len(selections) > MAX_ROWS):
        raise ValueError('Invalid Congress effect comparison request')
    additions = []
    left, right = dict(before.resolved_types), dict(after.resolved_types)
    for row in selections:
        if (type(row) is not dict or set(row) != {'target', 'type_key'}
                or type(row['target']) is not int or not -0x80000000 <= row['target'] <= 0x7fffffff
                or type(row['type_key']) is not int or row['type_key'] not in left
                or row['type_key'] not in right or left[row['type_key']] != right[row['type_key']]):
            raise ValueError('Congress effect selection lacks its exact stable type lookup')
        additions.append((pid, row['target'], left[row['type_key']]))
    selection_match = Counter(before.own_rows) + Counter(additions) == Counter(after.own_rows)
    marker_match = after.marker_turn == turn if looked else after.marker_turn == before.marker_turn
    marker_effect = ('not_requested' if not looked else 'not_observed' if not marker_match
                     else 'already_satisfied' if before.marker_turn == turn else 'changed')
    return dict(own_state_matches=selection_match and marker_match,
        selection_effect_observed=selection_match, looked_effect=marker_effect,
        before=_description(before), after=_description(after),
        expected_additions=[dict(sender=s, target=t, type_index=i) for s, t, i in additions],
        transport_acknowledged=False, congress_completion_claimed=False,
        checkpoint_release_qualified=False, source_sha256=SOURCE[1])

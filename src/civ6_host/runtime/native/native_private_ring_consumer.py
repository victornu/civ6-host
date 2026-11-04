"""Pure diagnostic drain for a source-validated empty private-ring receiver table.

This does not call the EXE or native code. It accepts a read-only bank snapshot
and table-row snapshots, and only accounts for type 0x54/0x57 records when the
source handler rows are initialized and demonstrably have no hooks/listeners.
It does not rotate or mutate banks, model callbacks, or authorize training.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
RECORD_SIZE = 128
BANK_CAPACITY = 4194304
DISPATCH_TABLE = 5405228672
EMPTY_RECEIVER_PROFILE = 'private-ring-empty-receivers-readonly-diagnostic'
CONSUMER_PROOF_SHA = 'db6e44123cc842c613c474009fc9bffb93ea78e887b69e46d38b1cdc11e361b2'
ROW57_PROOF_SHA = '9353497ff2976464cefc3856715fb441ba1a3cdeb1cfef6142f5231d86446a42'
EXE_SHA = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_private_ring_consumer.py')))).resolve().parents[1]
_CONSUMER_PROOF = _ROOT / 'evidence/native-event-1be52206-consumer' / f'{CONSUMER_PROOF_SHA}.json'
_ROW57_PROOF = _ROOT / 'evidence/native-event-1be52206-consumer-row57' / f'{ROW57_PROOF_SHA}.json'
_HANDLERS = {84: 5369693840, 87: 5369694128}
_DESTRUCTOR = 5369667808

@dataclass(frozen=True)
class HandlerRowSnapshot:
    """Raw EXE row/list bytes plus their addresses from one table snapshot.

    `row_bytes` is the 0x30-byte handler row. `list_bytes` is the allocated
    0x38-byte listener-list object referenced from row+0x18. Keeping addresses
    explicit lets the validator reject a mismatched or absent list pointer.
    """
    row_address: int
    row_bytes: bytes
    list_address: int
    list_bytes: bytes

@dataclass(frozen=True)
class DrainResult:
    records_consumed: int
    bytes_consumed: int
    counts_by_type: tuple[tuple[int, int], ...]
    input_cursor_unchanged: int
    final_read_offset: int
    profile: str = EMPTY_RECEIVER_PROFILE
    callbacks_invoked: int = 0
    training_eligible: bool = False

def verify_source_evidence() -> None:
    """Fail closed if either pinned consumer contract or type-57 row proof moved."""
    for path, expected, schema in ((_CONSUMER_PROOF, CONSUMER_PROOF_SHA, 'civ6rl.native_event_1be52206.consumer.static.v1'), (_ROW57_PROOF, ROW57_PROOF_SHA, 'civ6rl.native_private_ring_type57_row.static.v1')):
        raw = _resolve_resource_path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError('Pinned private-ring consumer evidence changed')
        proof = json.loads(raw)
        if proof.get('schema') != schema:
            raise RuntimeError('Pinned private-ring consumer evidence schema changed')
        image_hash = proof.get('image', {}).get('sha256')
        if image_hash != EXE_SHA:
            raise RuntimeError('Private-ring consumer EXE identity changed')
    consumer = json.loads(_resolve_resource_path(_CONSUMER_PROOF).read_bytes())
    ring = consumer.get('ring_object', {})
    if ring.get('dispatch_table_va') != hex(DISPATCH_TABLE):
        raise RuntimeError('Pinned private-ring dispatch table changed')
    init54 = {i['va']: i for fragment in consumer['functions']['type_0x54_row_initializer']['fragments'] for i in fragment['instructions']}
    for va, target in (('0x1400edc4f', DISPATCH_TABLE + 84 * 48), ('0x1400edc5d', _HANDLERS[84]), ('0x1400edc68', _DESTRUCTOR)):
        row = init54.get(va)
        if row is None or row.get('rip_targets') != [hex(target)]:
            raise RuntimeError('Pinned type-0x54 row initialization changed')
    row57 = json.loads(_resolve_resource_path(_ROW57_PROOF).read_bytes())['row_contract']
    if row57.get('type') != 87 or row57.get('row_address_formula') != 'dispatch_table + type * 0x30' or row57.get('dispatch_table_va') != hex(DISPATCH_TABLE) or (row57.get('row_address_va') != hex(DISPATCH_TABLE + 87 * 48)) or (row57.get('handler_va') != '0x1400f07b0') or (row57.get('destructor_va') != '0x1400ea0e0'):
        raise RuntimeError('Pinned type-0x57 row contract changed')

def _validate_row(record_type: int, table_base: int, row: HandlerRowSnapshot) -> None:
    if record_type not in _HANDLERS:
        raise ValueError(f'Unsupported private-ring record type {record_type:#x}')
    if not isinstance(row, HandlerRowSnapshot):
        raise ValueError('A raw handler-row/list snapshot is required')
    if type(row.row_address) is not int or type(row.list_address) is not int:
        raise ValueError('Handler row/list addresses must be exact integers')
    expected_row = table_base + record_type * 48
    if row.row_address != expected_row:
        raise ValueError('Handler row address does not match the record type slot')
    if not isinstance(row.row_bytes, bytes) or len(row.row_bytes) != 48:
        raise ValueError('Handler row snapshot must be exactly 0x30 bytes')
    if not isinstance(row.list_bytes, bytes) or len(row.list_bytes) != 56:
        raise ValueError('Listener list must be an allocated 0x38-byte snapshot')
    if row.list_address <= 0 or struct.unpack_from('<Q', row.row_bytes, 24)[0] != row.list_address:
        raise ValueError('Handler row does not reference the supplied allocated listener list')
    pre_hook, post_hook, row_field = struct.unpack_from('<QQQ', row.row_bytes, 0)
    handler, destructor = struct.unpack_from('<QQ', row.row_bytes, 32)
    if (pre_hook, post_hook, row_field) != (0, 0, 0):
        raise ValueError('Handler row has an active hook or unmodeled row field')
    if handler != _HANDLERS[record_type] or destructor != _DESTRUCTOR:
        raise ValueError('Handler row method/destructor does not match pinned source')
    if struct.unpack_from('<Q', row.list_bytes, 0)[0] != 268435455:
        raise ValueError('Listener list sentinel changed')
    if struct.unpack_from('<QQQ', row.list_bytes, 8) != (0, 0, 0):
        raise ValueError('Listener list has storage/hooks not present in the empty profile')
    count = struct.unpack_from('<I', row.list_bytes, 32)[0]
    if count != 0:
        raise ValueError('Private-ring receiver row has listeners; drain is not modeled')
    if struct.unpack_from('<II', row.list_bytes, 36) != (268435455, 268435455):
        raise ValueError('Listener-list iterator state is not the source-initialized state')
    flags = row.list_bytes[48]
    if flags & 3:
        raise ValueError('Listener-list dispatch flags are busy or select an unmodeled path')

def consume_empty_bank(bank: bytes | bytearray | memoryview, cursor: int, table_state: Mapping[int, HandlerRowSnapshot], *, table_base: int=DISPATCH_TABLE, profile: str=EMPTY_RECEIVER_PROFILE) -> DrainResult:
    """Validate and account for one bank without changing it.

    Only header types 0x54 and 0x57 are admitted, and their corresponding row
    snapshots must prove allocated empty receiver lists. Records are accepted
    only when the header chain ends exactly at `cursor`; malformed, unknown,
    hooked, busy, or listener-bearing state raises before any result is returned.
    This is a diagnostic empty-list route, not a general event dispatcher.
    """
    verify_source_evidence()
    if profile != EMPTY_RECEIVER_PROFILE:
        raise ValueError('The private-ring consumer requires its explicit empty-receiver profile')
    if type(table_base) is not int or table_base != DISPATCH_TABLE:
        raise ValueError('Unmodeled private-ring dispatch table')
    if not isinstance(bank, (bytes, bytearray, memoryview)):
        raise ValueError('Private-ring bank must be a byte snapshot')
    view = memoryview(bank).cast('B')
    if type(cursor) is not int or cursor < 0 or cursor > BANK_CAPACITY:
        raise ValueError('Private-ring cursor is outside the source bank bounds')
    if cursor > len(view) or cursor % RECORD_SIZE:
        raise ValueError('Private-ring cursor is truncated or not record-aligned')
    if not isinstance(table_state, Mapping):
        raise ValueError('Handler-table state mapping is required')
    counts: dict[int, int] = {}
    offset = 0
    while offset < cursor:
        if cursor - offset < 16:
            raise ValueError('Truncated private-ring record header')
        size, record_type, reserved0, reserved1 = struct.unpack_from('<IIII', view, offset)
        if size != RECORD_SIZE:
            raise ValueError('Private-ring record size does not match the proven 0x80 allocator')
        if record_type not in _HANDLERS:
            raise ValueError(f'Unmodeled private-ring record type {record_type:#x}')
        if reserved0 != 0 or reserved1 != 0:
            raise ValueError('Private-ring record header reserved fields are nonzero')
        if offset + size > cursor:
            raise ValueError('Private-ring record extends past its cursor')
        if record_type not in table_state:
            raise ValueError(f'No source-validated handler-row state for {record_type:#x}')
        _validate_row(record_type, table_base, table_state[record_type])
        counts[record_type] = counts.get(record_type, 0) + 1
        offset += size
    if offset != cursor:
        raise ValueError('Private-ring record walk did not terminate at cursor')
    return DrainResult(records_consumed=sum(counts.values()), bytes_consumed=cursor, counts_by_type=tuple(sorted(counts.items())), input_cursor_unchanged=cursor, final_read_offset=offset)
__all__ = ['BANK_CAPACITY', 'DISPATCH_TABLE', 'EMPTY_RECEIVER_PROFILE', 'HandlerRowSnapshot', 'DrainResult', 'verify_source_evidence', 'consume_empty_bank']

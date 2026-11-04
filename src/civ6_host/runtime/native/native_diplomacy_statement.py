"""Official statement transport and lifetime; responses remain explicit choices."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from pathlib import Path
import ctypes as C
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_application_mirror import decode_scalar
from civ6_host.runtime.native.native_configuration_finalization import _invoke
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_diplomacy_statement.py')))).resolve().parents[1]
PROOF_SHA256 = 'b78799f583992bcddcb16f76d3714869bf547dda7f96b79a0e9fc3abe32f13f8'
EVENT_KIND, RECORD_TYPE, RECORD_SIZE = (4235402789, 132, 112)
NAMES = {'StatementType': 3136235966, 'StatementSubType': 304523663, 'ResponseType': 2612666305, 'SessionID': 2133911650, 'FromPlayer': 2623097599, 'ToPlayer': 406339414, 'Initiator': 940935371, 'FromPlayerMood': 3012028737, 'ToPlayerMood': 1206716586, 'AiReason': 3960653642, 'AiModifier': 2854660138, 'IsFirstStatementOfType': 654530884}
BLOB_KEY, OPAQUE_KEY = (2684726792, 2663773416)
PADDING_POLICY = 'zero-seven-unread-bytes-typed-statement-receiver'

def verify_source_evidence():
    p = load_pinned_json(ROOT / 'evidence/native-event-fc731e25' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if p['schema'] != 'civ6rl.native_event_fc731e25.static.v1' or p['images'] != {'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63', 'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'} or p['contract']['record_type'] != RECORD_TYPE or (p['contract']['record_size'] != RECORD_SIZE) or (p['leaves']['cleanup']['raw_hex'] != '488b5118488d0d25d21802e9201a0800') or (p['core_captures']['get_player']['code_sha256'] != '68f7714aad11caa17bd397aab3cebbf2294474a46b963eecc9f4e4f3fb16bd64'):
        raise RuntimeError('Diplomacy statement source changed')
    return p

@dataclass(frozen=True)
class StatementFields:
    values: tuple
    opaque: int
    blob: bytes | None

    def named(self):
        return dict(self.values)

def decode_fields(fields, read):
    verify_source_evidence()
    from civ6_host.runtime.native.native_diplomacy_default import verify_source
    verify_source()
    required = set(NAMES.values()) | {OPAQUE_KEY}
    if set(fields) not in (required, required | {BLOB_KEY}):
        raise ValueError('Statement has unknown fields or lacks a required scalar')
    values = {}
    for name, key in NAMES.items():
        tag = 1 if name == 'IsFirstStatementOfType' else 2 if name in ('FromPlayer', 'ToPlayer', 'Initiator') else 3
        if tag == 1:
            raw = fields[key]
            if type(raw) is not bytes or len(raw) != 24 or struct.unpack_from('<H', raw)[0] != 1 or (raw[20:] != bytes(4)) or (raw[8] not in (0, 1)):
                raise ValueError('Statement Boolean envelope differs')
            values[name] = raw[8] != 0
        else:
            values[name] = decode_scalar(fields[key], tag)
    opaque = decode_scalar(fields[OPAQUE_KEY], 3)
    if BLOB_KEY not in fields:
        return StatementFields(tuple(values.items()), opaque, None)
    raw = fields[BLOB_KEY]
    if type(raw) is not bytes or len(raw) != 24 or struct.unpack_from('<H', raw)[0] != 13:
        raise ValueError('Statement blob envelope differs')
    pointer, size, flags = struct.unpack_from('<QII', raw, 8)
    if not pointer or size != 8 or flags != 553648129:
        raise ValueError('Statement blob ownership/size differs')
    data = read(pointer, 8)
    if type(data) is not bytes or len(data) != 8:
        raise ValueError('Statement blob is incomplete')
    return StatementFields(tuple(values.items()), opaque, data)

def encode_record(sequence, pointer, fields, *, padding_bytes):
    verify_source_evidence()
    from civ6_host.runtime.native.native_player_event_domains import validate_sequence
    validate_sequence(sequence)
    if type(pointer) is not int or not 0 < pointer <= 18446744073709551615:
        raise ValueError('Statement needs a live owned map pointer')
    if not isinstance(fields, StatementFields) or set(fields.named()) != set(NAMES):
        raise ValueError('Malformed decoded statement')
    if type(padding_bytes) is not bytes or len(padding_bytes) != 7:
        raise ValueError('Explicit unread padding required')
    values = fields.named()
    if any((type(v) is not int or not 0 <= v <= 4294967295 for k, v in values.items() if k != 'IsFirstStatementOfType')):
        raise ValueError('Statement scalar is not uint32')
    if type(values['IsFirstStatementOfType']) is not bool or type(fields.opaque) is not int or (not 0 <= fields.opaque <= 4294967295):
        raise ValueError('Statement Boolean/opaque field differs')
    data = bytearray(RECORD_SIZE)
    struct.pack_into('<IIIIii', data, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0, -1, -1)
    for offset in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', data, offset, 65535, 0, 4294967295)
    struct.pack_into('<I', data, 72, 4)
    struct.pack_into('<I', data, 80, sequence)
    data[84:88] = padding_bytes[:4]
    struct.pack_into('<IIIB', data, 88, values['FromPlayer'], values['ToPlayer'], fields.opaque, values['IsFirstStatementOfType'])
    data[101:104] = padding_bytes[4:]
    struct.pack_into('<Q', data, 104, pointer)
    return bytes(data)

def player_predicate(facades, signed_player, read, *, call=None):
    """F14D0 then player+38 then Release, on the already retained Game facade."""
    proof = verify_source_evidence()
    if facades is None or facades._closed or (not facades.backend.context_alive()) or (type(signed_player) is not int) or (not -(1 << 31) <= signed_player < 1 << 31):
        raise RuntimeError('Statement player query requires the live retained Game facade')
    base = facades.backend.core_base
    game = facades.game_facade

    def exact(address, size):
        value = read(address, size)
        if type(value) is not bytes or len(value) != size:
            raise ValueError('Incomplete statement native read')
        return value

    def qword(address):
        return struct.unpack('<Q', exact(address, 8))[0]

    def slot(table, offset, target):
        if qword(base + table + offset) != base + target:
            raise ValueError('Statement native slot changed')
    if not game or qword(game) != base + 7990488 or qword(game + 8) != 0 or (not qword(game + 16)):
        raise ValueError('Statement retained Game is not the cache-backed facade')
    for table, offset, target in ((7990488, 144, 4410544), (7992320, 56, 4424032), (7992320, 8, 4421040)):
        slot(table, offset, target)
    for body in (proof['core_captures']['get_player'], proof['core_captures']['release_player']):
        for fragment in body['fragments']:
            for ins in fragment['instructions']:
                data = bytes.fromhex(ins['bytes'])
                if exact(base + int(ins['va'], 16) - 6442450944, len(data)) != data:
                    raise ValueError('Statement native query code changed')
    leaf = proof['leaves']['player_predicate']
    data = bytes.fromhex(leaf['raw_hex'])
    if exact(base + 4424032, len(data)) != data:
        raise ValueError('Statement player predicate changed')
    player = _invoke(call, base + 4410544, C.c_void_p, game, (C.c_int32,), signed_player)
    if not player:
        return None
    if qword(player) != base + 7992320:
        raise ValueError('Statement player facade type differs')
    try:
        if qword(player + 8) != 0 or not qword(player + 16):
            raise ValueError('Statement player facade is not cache-backed')
        value = _invoke(call, base + 4424032, C.c_uint8, player)
        if type(value) is not int or not 0 <= value <= 255:
            raise ValueError('Statement predicate result is not a byte')
        return value != 0
    finally:
        _invoke(call, base + 4421040, None, player)

def apply_effects(core, context, read, state, getter, facades, fields, *, game_query=None, predicate=None):
    verify_source_evidence()
    from civ6_host.runtime.native.native_wonder_application import native_game_comparison_value
    if type(getattr(state, 'service_flags', None)) is not int or not 0 <= state.service_flags <= 255 or (not callable(getter)):
        raise RuntimeError('Statement effects require valid shared UI service flags')
    before = state.service_flags
    comparison_value = retained = None
    matched = False
    query = native_game_comparison_value if game_query is None else game_query
    with query(core, context, read) as comparison_value:
        if comparison_value is not None:
            retained = getter()
            matched = comparison_value == retained
            if matched:
                state.service_flags |= 64
    local = getter()
    if type(local) is not int or not -(1 << 31) <= local < 1 << 31:
        raise ValueError('Invalid retained getter result')
    values = fields.named()
    participant = local & 4294967295 in (values['FromPlayer'], values['ToPlayer']) and local != -1
    result = None
    if participant:
        result = (player_predicate if predicate is None else predicate)(facades, local, read)
        if result is not None and type(result) is not bool:
            raise ValueError('Statement predicate did not return bool/null')
        if result is True:
            state.service_flags |= 64
    return dict(flags_before=before, flags_after=state.service_flags, comparison_value=comparison_value, comparison_retained_value=retained, comparison_matched=matched, participant_getter_value=local, participant_matched=participant, player_predicate=result, native_gameplay_written=False)

class StatementReceiver:
    """Deliver a pointer-free pending choice, then run the mandatory post-hook."""

    def __init__(self):
        self.busy = False
        self.poisoned = False

    def consume(self, record, registry, base_state, read_fields, read, *, deliver):
        verify_source_evidence()
        from civ6_host.runtime.native.native_combat_receiver import validate_receiver_profile
        validate_receiver_profile(base_state)
        if self.busy or self.poisoned:
            raise RuntimeError('Statement receiver is active or poisoned')
        if type(record) is not bytes or len(record) != RECORD_SIZE:
            raise ValueError('Statement record length differs')
        pointer = struct.unpack_from('<Q', record, 104)[0]
        sequence = struct.unpack_from('<I', record, 8)[0]
        matches = [(token, owner, count) for token, (owner, count) in registry.entries.items() if owner.pointer == pointer]
        if len(matches) != 1 or matches[0][2] != 1:
            raise ValueError('Statement requires exactly one native owner reference')
        token, owner, _ = matches[0]
        if owner.closed or owner.poisoned:
            raise ValueError('Statement map owner is unavailable')
        fields = decode_fields(read_fields(pointer), read)
        if record != encode_record(sequence, pointer, fields, padding_bytes=bytes(7)):
            raise ValueError('Statement record differs from its owned map')
        statement = dict(event_sequence=sequence, fields=fields.named(), opaque_9ec5f4e8=fields.opaque, opaque_a005ae08_hex=None if fields.blob is None else fields.blob.hex(), source_proof_sha256=PROOF_SHA256, learner_exposure_validated=False, automatic_response=False)
        self.busy = True
        try:
            deliver(statement)
            remaining = registry.release(token)
            if remaining != 0 or registry.lookup(token) is not None or (not owner.closed):
                raise RuntimeError('Statement pointer-release post-hook did not destroy its owned map')
        except BaseException:
            self.poisoned = True
            raise
        else:
            self.busy = False
        return dict(record_type=RECORD_TYPE, token=token, sequence=sequence, native_map_destructor_returned=True, pointer_release_post_hook_reproduced=True, registry_live_maps=len(registry.entries), pending_choice_delivered=True, source_proof_sha256=PROOF_SHA256, eligible_for_training=False)

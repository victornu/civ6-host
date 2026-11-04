"""Bounded observation of one CityCommand's individual UnitKilledInCombat receipts.

No dispatch or native value is synthesized. The emitter tap forwards every call
unchanged and exists only during the synchronous Request/delivery/publication.
397 alone does not name a victim; 399 joins the named Unit damage bindings to
SECOND. The separate453/457 path joins FIRST to its native threshold test.
Neither establishes universal semantics for other two-descriptor events.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy
import hashlib
import json
import os
import struct
import threading
from pathlib import Path
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_city_kill_receipt.py')))).resolve().parents[1]
PINS = {'work/native-unit-kill-city-range397.json': 'c842767928885018a5b3ab6599b303a60c579328d2996f742fd9f8677a2f625f', 'work/native-kill-damage-binding399.json': '5243851a28efcdc385f7be0580a4efffca4d676cd17f96f597cb610176ab79ab', 'evidence/native-event-754cbd1b/7bd71b81b11516427125c29ae96bffbbae878b87c0d3e1049716fc4547f5a12f.json': '7bd71b81b11516427125c29ae96bffbbae878b87c0d3e1049716fc4547f5a12f', 'evidence/native-754cbd1b-receiver/1e72a04840bac400f35d7928946526f590f29cf3094179a49f91e2f388fea641.json': '1e72a04840bac400f35d7928946526f590f29cf3094179a49f91e2f388fea641', 'evidence/native-city-command-archive-trace/6be400e3139d9d6a6a32956dae72e152c7499920e35a1f309afb3e769e9eb6fc.json': '6be400e3139d9d6a6a32956dae72e152c7499920e35a1f309afb3e769e9eb6fc'}
PRODUCER_SHA = PINS[next((p for p in PINS if p.startswith('evidence/native-event-754')))]
RECEIVER_SHA = PINS[next((p for p in PINS if p.startswith('evidence/native-754')))]
POLICY = 'zero-unread-unit-pair-gap-empty-receiver'
ENQUEUE = 'native_deferred_host_event_enqueued'
CONSUME = 'native_deferred_empty_record_consumed'
STAGES = {'actions': {'native_command_archive_queued', 'native_command_received_in_core_queue', 'before_native_command_queue_drain', 'native_command_queue_drained'}, 'deferred': {ENQUEUE, CONSUME}, 'publisher': {'before_native_player_view_publish', 'native_player_view_published'}}
MAX_ROWS = 128
CITY_SOURCE_PROOF_SHA256 = '1ebae31819231e78b093a7d27f51a8680f7d421a012bf205874e4e9769a49143'
CITY_SOURCE_PROOF_PATH = 'evidence/native-event-754cbd1b-city-variant/' + CITY_SOURCE_PROOF_SHA256 + '.json'
CITY_ATTRIBUTION_SHA256 = '16898b6f9964529570fc9d1859d2b470c78e65e905ba8a65f116db8fb23e00e7'
CITY_ATTRIBUTION_PATH = 'work/native-city-kill-attribution457/' + CITY_ATTRIBUTION_SHA256 + '.json'
CITY_RECHECK_PATH = 'work/native-754cbd1b-city-variant453-recheck.json'
CITY_RECHECK_SHA256 = 'c93bce1dd84242d4f2ae7d762670928cf03e89836e770bffb418e34cffabf1b4'
CITY_FIELD_PROFILE = 'first-unit-first-district'
CITY_MARKERS = {'source_field_profile', 'source_district_descriptor', 'source_second_unit_descriptor_default'}
CITY_PINS = {CITY_SOURCE_PROOF_PATH: CITY_SOURCE_PROOF_SHA256, CITY_ATTRIBUTION_PATH: CITY_ATTRIBUTION_SHA256, CITY_RECHECK_PATH: CITY_RECHECK_SHA256}

def verify_city_sources():
    docs = {}
    for path, digest in CITY_PINS.items():
        raw = _resolve_resource_path(ROOT / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('city/district754 source changed: ' + path)
        docs[path] = json.loads(raw)
    proof = docs[CITY_SOURCE_PROOF_PATH]
    attribution = docs[CITY_ATTRIBUTION_PATH]
    recheck = docs[CITY_RECHECK_PATH]
    contract = attribution['contract']
    if proof['schema'] != 'civ6rl.native_event_754cbd1b_city_variant.static.v1' or proof['binding']['kind'] != '0x754cbd1b' or proof['binding']['callback_va'] != '0x1401573e0' or (type(proof['source_mapping']['selector_origin']['value']) is not int) or (proof['source_mapping']['selector_origin']['value'] != 0) or (proof['source_mapping']['normalizer']['defaults']['slot2_base_plus_0x10'] != {'owner': 65535, 'type': 1, 'id': 4294967295}) or (attribution['schema'] != 'civ6rl.native_city_kill_attribution457.static.v1') or (attribution['parents'] != {CITY_SOURCE_PROOF_PATH: CITY_SOURCE_PROOF_SHA256, 'work/native-kill-damage-binding399.json': PINS['work/native-kill-damage-binding399.json'], CITY_RECHECK_PATH: CITY_RECHECK_SHA256}) or (attribution['images'] != proof['images']) or (contract['event_kind'] != '0x754cbd1b') or (contract['source_field_profile'] != CITY_FIELD_PROFILE) or (contract['victim_descriptor_role'] != 'FIRST') or (contract['condition'] != 'subject.GetDamage() >= subject.GetMaxDamage()') or (contract['handler_va'] != '0x180107d80') or (contract['event_call_va'] != '0x180107f0a') or (contract['second_unit_descriptor'] != [65535, 1, 4294967295]) or (contract['district_city_id_equivalence_claimed'] is not False) or (attribution['validation']['all_instruction_bytes_match_pinned_pe'] is not True) or (recheck['schema'] != 'civ6rl.native_event_754cbd1b_city_variant_recheck.static.v1') or (recheck['proof']['sha256'] != CITY_SOURCE_PROOF_SHA256):
        raise ValueError('city/district754 attribution contract changed')
    guards = {row['va']: row['bytes'] for row in attribution['source_captures']['attribution_instructions']}
    if any((guards.get(va) != raw for va, raw in {'0x180107ea7': '8b9e50040000', '0x180107ead': '488bce', '0x180107eb0': 'e86b331900', '0x180107eb5': '3bd8', '0x180107eb7': '0f8ce7010000', '0x180107ebd': '0fb78628010000', '0x180107eea': '8b86b0000000', '0x180107f0a': 'e8a1cf3700'}.items())):
        raise ValueError('city/district754 threshold-to-FIRST source join changed')
    return dict(CITY_PINS)

def _source_form(data):
    source = data.get('source_proof_sha256')
    if source == PRODUCER_SHA:
        if CITY_MARKERS.intersection(data):
            raise ValueError('historical unit-pair source cannot claim city/district provenance')
        return 'unit-pair'
    if source != CITY_SOURCE_PROOF_SHA256:
        raise ValueError('kill producer source changed')
    verify_city_sources()
    descriptor = data.get('source_district_descriptor')
    if data.get('source_field_profile') != CITY_FIELD_PROFILE or data.get('source_second_unit_descriptor_default') is not True or type(descriptor) is not list or (len(descriptor) != 3) or any((type(value) is not int for value in descriptor)) or (not 0 <= descriptor[0] <= 65535) or (descriptor[1] != 3) or (not 0 <= descriptor[2] <= 4294967295):
        raise ValueError('missing explicit city/district754 normalized-field provenance')
    return CITY_FIELD_PROFILE

def verify_sources():
    docs = {}
    for path, digest in PINS.items():
        raw = _resolve_resource_path(ROOT / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('city kill source changed: ' + path)
        docs[path] = json.loads(raw)
    d = docs['work/native-kill-damage-binding399.json']
    a = d['kill_event_attribution']
    if d['schema'] != 'civ6rl.native_kill_damage_binding399.static.v1' or a['event_kind'] != '0x754CBD1B' or a['caller_va'] != '0x180106970' or ('SECOND' not in a['descriptor_result']) or ('subject.GetDamage() >= subject.GetMaxDamage()' not in a['condition']):
        raise ValueError('victim attribution contract changed')
    return dict(PINS)

def _uint(value, limit=4294967295):
    if type(value) is not int or not 0 <= value <= limit:
        raise ValueError('expected exact bounded integer')
    return value

def _record(data):
    form = _source_form(data)
    if data.get('dispatch_kind') != '0x754cbd1b' or data.get('queue_type') != '0x1e' or data.get('unspecified_padding_policy') != POLICY or (data.get('empty_receiver_state_verified') is not True) or (type(data.get('entity_listener_count')) is not int) or (data['entity_listener_count'] != 0) or (type(data.get('native_dispatch_return')) is not int) or (data['native_dispatch_return'] != 0) or any((data.get(k) is not False for k in ('native_queries_executed', 'normalizer_transform_present', 'optional_preprocessing_hook_registered', 'queue_metadata_service_registered'))):
        raise ValueError('kill enqueue source/profile changed')
    hx = data.get('record_hex')
    if type(hx) is not str or len(hx) != 224:
        raise ValueError('kill record has no complete bytes')
    raw = bytes.fromhex(hx)
    if len(raw) != 112:
        raise ValueError('kill record size changed')
    size, kind, sequence, flags = struct.unpack_from('<IIII', raw)
    first = struct.unpack_from('<HHI', raw, 88)
    second = struct.unpack_from('<HHI', raw, 96)
    if size != 112 or kind != 30 or flags != 0 or (sequence == 0) or (first[1] != 1) or (second[1] != 1):
        raise ValueError('kill record header/descriptors changed')
    expected = bytearray(112)
    struct.pack_into('<IIIIII', expected, 0, 112, 30, sequence, 0, 4294967295, 4294967295)
    for off in (24, 32, 40, 48, 56):
        struct.pack_into('<HHI', expected, off, 65535, 0, 4294967295)
    struct.pack_into('<HHI', expected, 24, *first)
    struct.pack_into('<I', expected, 80, sequence)
    struct.pack_into('<HHI', expected, 88, *first)
    struct.pack_into('<HHI', expected, 96, *second)
    if raw != expected:
        raise ValueError('kill record layout/metadata/padding disagrees with the admitted codec')
    if form == CITY_FIELD_PROFILE and second != (65535, 1, 4294967295):
        raise ValueError('city/district754 requires the native absent-SECOND default')
    return (sequence, first, second)

def validate_kill_window(rows, *, pid, candidate, archive_sha256, attacking_player_id=None):
    """Pure audit of retained individual rows; an aggregate counter never suffices."""
    pins = verify_sources()
    _uint(pid, 2147483647)
    if pid == 0 or type(candidate) is not dict or type(archive_sha256) is not str or (len(archive_sha256) != 64) or (type(rows) is not list) or (not 1 <= len(rows) <= MAX_ROWS):
        raise ValueError('missing bounded kill window')
    owner = _uint(candidate.get('target_owner'), 63)
    identifier = _uint(candidate.get('target_unit_id'))
    by_stage = {}
    for i, row in enumerate(rows):
        if type(row) is not dict or set(row) != {'ordinal', 'pid', 'role', 'stage', 'data'} or type(row['ordinal']) is not int or (row['ordinal'] != i) or (type(row['pid']) is not int) or (row['pid'] != pid) or (row['role'] not in STAGES) or (row['stage'] not in STAGES[row['role']]) or (type(row['data']) is not dict):
            raise ValueError('malformed/cross-process kill receipt')
        by_stage.setdefault(row['stage'], []).append(row)

    def one(stage):
        found = by_stage.get(stage, [])
        if len(found) != 1:
            raise ValueError('one exact command window required: ' + stage)
        return found[0]
    capture = one('native_command_archive_queued')
    receive = one('native_command_received_in_core_queue')
    before = one('before_native_command_queue_drain')
    drained = one('native_command_queue_drained')
    prepublish = one('before_native_player_view_publish')
    published = one('native_player_view_published')
    if not capture['ordinal'] < receive['ordinal'] < before['ordinal'] < drained['ordinal'] < prepublish['ordinal'] < published['ordinal']:
        raise ValueError('command/publication order changed')
    archives = []
    for row in (capture, receive):
        hx = row['data'].get('archive_hex')
        if type(hx) is not str or not 8 <= len(hx) <= 2 * 6784:
            raise ValueError('invalid captured archive')
        raw = bytes.fromhex(hx)
        if raw[:4] != bytes.fromhex('130a6b34') or hashlib.sha256(raw).hexdigest() != archive_sha256:
            raise ValueError('wrong CityCommand archive (generic discriminant only)')
        archives.append(raw)
    if archives[0] != archives[1] or capture['data'].get('delivery_pending') is not True or receive['data'].get('native_owned_copy') is not True or (drained['data'].get('native_dispatcher_used') is not True):
        raise ValueError('native delivery not established')
    for key in ('width', 'height', 'plot_count'):
        _uint(published['data'].get(key), 2147483647)
    if published['data']['width'] <= 0 or published['data']['height'] <= 0 or published['data']['plot_count'] != published['data']['width'] * published['data']['height']:
        raise ValueError('publication map shape invalid')
    game = _uint(prepublish['data'].get('source_game_pointer'), 18446744073709551615)
    if not game or type(prepublish['data'].get('event_kind')) is not int or prepublish['data']['event_kind'] != 4 or (type(published['data'].get('source_game_pointer')) is not int) or (published['data']['source_game_pointer'] != game) or (published['data'].get('cache_owner_borrowed') is not True):
        raise ValueError('publication borrowed Game identity changed')
    enqueues = {}
    victim = []
    for row in by_stage.get(ENQUEUE, []):
        seq, first, second = _record(row['data'])
        if seq in enqueues or not before['ordinal'] < row['ordinal'] < drained['ordinal']:
            raise ValueError('duplicate/stale kill event outside native command drain')
        enqueues[seq] = row
        form = _source_form(row['data'])
        selected = second
        if form == CITY_FIELD_PROFILE:
            _uint(attacking_player_id, 1)
            district = row['data']['source_district_descriptor']
            if district[0] != attacking_player_id or owner == attacking_player_id:
                raise ValueError('city/district754 attacker owner disagrees with command perspective')
            selected = first
            pins.update(verify_city_sources())
        if selected == (owner, 1, identifier):
            victim.append((seq, row, first, second, form, selected))
    consumed = {}
    for row in by_stage.get(CONSUME, []):
        d = row['data']
        seq = _uint(d.get('sequence'))
        if seq in consumed or seq not in enqueues or (not drained['ordinal'] < row['ordinal'] < prepublish['ordinal']) or (type(d.get('record_type')) is not int) or (d['record_type'] != 30) or (type(d.get('record_size')) is not int) or (d['record_size'] != 112) or (d.get('event_name') != 'GameCoreEvent::UnitKilledInCombat') or (d.get('handler_va') != '0x1400d6af0') or (d.get('native_handler_has_no_gameplay_callback_in_this_profile') is not True):
            raise ValueError('kill individual consumption changed or outside drain window')
        consumed[seq] = row
    if len(victim) != 1 or set(consumed) != set(enqueues):
        raise ValueError('one source-attributed victim and every individual consumption required')
    seq, enqueue, first, second, form, selected = victim[0]
    result = {'schema': 'civ6rl.native_city_kill_window.v1', 'pid': pid, 'sequence': seq, 'victim_descriptor': list(selected), 'other_descriptor': list(first if form == 'unit-pair' else second), 'archive_sha256': archive_sha256, 'source_pins': pins, 'individual_rows': copy.deepcopy(rows), 'first_descriptor_is_city_claimed': False, 'window_attribution_only': True}
    if form == CITY_FIELD_PROFILE:
        result.update(source_field_profile=CITY_FIELD_PROFILE, victim_descriptor_role='FIRST', attacking_player_id=attacking_player_id, source_district_descriptor=list(enqueue['data']['source_district_descriptor']), district_city_id_equivalence_claimed=False)
    return result

def audit_killed_effect(effect, preceding_events):
    """Separate pure death-branch audit, including independently logged rows.

    preceding_events is a bounded report slice ending just before this effect.
    The latest matching archive capture starts the window; earlier pairs and
    global counts cannot be substituted. Runtime-added timing/memory fields are
    removed only when comparing each raw receipt retained by the live tap.
    """
    if type(effect) is not dict or type(preceding_events) is not list or len(preceding_events) > 8192 or (effect.get('target_killed_verified') is not True) or (effect.get('effect_kind') != 'target-killed-individual-event') or (effect.get('after_damage') is not None) or (effect.get('damage_readback_unavailable') is not True) or (effect.get('native_effect_verified') is not True):
        raise ValueError('not an explicit death receipt')
    pid = effect.get('pid')
    _uint(pid, 2147483647)
    candidate = effect.get('candidate')
    if type(candidate) is not dict:
        raise ValueError('missing pre-request candidate identity')
    for name in ('target_owner', 'target_unit_id', 'target_unit_type', 'before_damage'):
        if type(effect.get(name)) is not int or effect[name] != candidate.get(name):
            raise ValueError('death effect identity differs from candidate')
    proof = effect.get('kill_evidence')
    if type(proof) is not dict:
        raise ValueError('no individual kill evidence')
    result = validate_kill_window(proof.get('individual_rows'), pid=pid, candidate=candidate, archive_sha256=effect.get('captured_archive_sha256'), attacking_player_id=effect.get('player_id'))
    if result != proof:
        raise ValueError('embedded kill receipt differs from its recomputed contract')
    expected = result['individual_rows']
    captures = []
    for i, event in enumerate(preceding_events):
        if type(event) is not dict:
            raise ValueError('invalid report event')
        if event.get('stage') == 'native_command_archive_queued' and event.get('archive_hex') == expected[0]['data'].get('archive_hex') and (type(event.get('pid')) is int) and (event['pid'] == pid):
            captures.append(i)
    if not captures:
        raise ValueError('missing independent command capture')
    logged = []
    roles = {stage: role for role, stages in STAGES.items() for stage in stages}
    for event in preceding_events[captures[-1]:]:
        stage = event.get('stage')
        if stage not in roles:
            continue
        if stage == ENQUEUE and event.get('queue_type') != '0x1e':
            continue
        if stage == CONSUME and event.get('record_type') != 30:
            continue
        data = {k: v for k, v in event.items() if k not in {'stage', 'pid', 'seconds', 'monotonic_seconds', 'memory'}}
        logged.append({'ordinal': len(logged), 'pid': event.get('pid'), 'role': roles[stage], 'stage': stage, 'data': data})
    if logged != expected:
        raise ValueError('independent capture/delivery/kill/consumption/publication rows disagree')
    return {'target_killed_verified': True, 'sequence': result['sequence'], 'after_damage': None, 'damage_value_inferred': False, 'independent_individual_rows_verified': True, 'source_pins': result['source_pins']}

class KillReceiptWindow:
    """Owner/thread-scoped tap. It never changes events or native queue methods."""

    def __init__(self, actions, deferred, publisher):
        self.owners = (actions, deferred, publisher)
        self.bindings = []
        self.rows = []
        self.thread = threading.get_ident()
        self.pid = os.getpid()
        self.closed = False

    def __enter__(self):
        verify_sources()
        if len({id(o) for o in self.owners}) != 3 or self.bindings or self.closed:
            raise RuntimeError('receipt window owner/reentry changed')
        originals = [getattr(o, 'emit', None) for o in self.owners]
        if not all((callable(e) for e in originals)):
            raise RuntimeError('kill observation requires actual transport/deferred/publisher emitters')
        if any((getattr(e, '_city_kill_receipt_tap', False) for e in originals)):
            raise RuntimeError('nested kill receipt tap is forbidden')
        try:
            for role, owner, original in zip(STAGES, self.owners, originals):

                def tap(stage, _role=role, _original=original, **data):
                    self._observe(_role, stage, data)
                    return _original(stage, **data)
                tap._city_kill_receipt_tap = True
                self.bindings.append((owner, original, tap))
                owner.emit = tap
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _observe(self, role, stage, data):
        if self.closed or os.getpid() != self.pid or threading.get_ident() != self.thread or any((owner.emit is not tap for owner, _, tap in self.bindings)):
            raise RuntimeError('receipt emitter/thread/ownership changed')
        if stage not in STAGES[role]:
            return
        if role == 'deferred':
            if stage == ENQUEUE and data.get('queue_type') != '0x1e':
                return
            if stage == CONSUME and data.get('record_type') != 30:
                return
        if len(self.rows) >= MAX_ROWS:
            raise RuntimeError('kill receipt window exceeded bound')
        raw = json.dumps(data, allow_nan=False).encode('utf-8')
        if len(raw) > 64 * 1024:
            raise RuntimeError('kill receipt row exceeded byte bound')
        self.rows.append({'ordinal': len(self.rows), 'pid': self.pid, 'role': role, 'stage': stage, 'data': copy.deepcopy(data)})

    def __exit__(self, exc_type, exc, tb):
        changed = os.getpid() != self.pid or threading.get_ident() != self.thread or any((owner.emit is not tap for owner, _, tap in self.bindings))
        for owner, original, _ in reversed(self.bindings):
            owner.emit = original
        self.closed = True
        if changed:
            raise RuntimeError('receipt emitter replaced during native command')

    def verify(self, candidate, archive_sha256, *, attacking_player_id=None):
        if self.closed or threading.get_ident() != self.thread:
            raise RuntimeError('kill window is no longer the current command')
        return validate_kill_window(self.rows, pid=self.pid, candidate=candidate, archive_sha256=archive_sha256, attacking_player_id=attacking_player_id)

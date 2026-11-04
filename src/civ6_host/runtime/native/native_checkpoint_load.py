"""Isolated Base Load-only diagnostic. Import/tests never invoke native DLLs.

The supervised worker must explicitly invoke run_load_only after its
verified factory. This owns Init but intentionally does NOT claim completed
post-load lifecycle or Destroy. Owners stay retained until controlled worker
termination; +160 is a separate refused boundary. No NewGame, finalization,
GameUpdate or gameplay action is implemented here. Configuration serialization
only checks the restored provider before any Game exists.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import struct
from civ6_host.runtime.native import native_checkpoint_configuration_only as configuration
from civ6_host.runtime.native import native_checkpoint_provider as provider
from civ6_host.runtime.native import native_application_configuration as application
from civ6_host.runtime.native.native_checkpoint_stream import Win64Stream
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_checkpoint_load.py')))).resolve().parents[1]
LOAD_PATH = 'work/native-checkpoint-load-plan347.json'
LOAD_SHA256 = '09d365eca9bc902d20f1e02f168ed02152bea25f468327f1bbe960d45dbc9d83'
PREPARED_PATH, PREPARED_SHA256 = (configuration.AUDIT_PATH, configuration.AUDIT_SHA)
CORE_BASE = 6442450944
GAME_SHA256 = '2b09cc670fa719b643e73278e9fbf50eee0f076c6156e231a32380d3f480d7d9'
GAME_BYTES = 2542367
MAX_BYTES, MAX_CALLS = (32 * 1024 * 1024, 1000000)
GAME_READ_MAX_CALLS = 2000000
FATAL_EXIT_CODE = 89
_RETAINED = {}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def pinned_json(path, expected):
    raw = _resolve_resource_path(ROOT / path).read_bytes()
    if sha(raw) != expected:
        raise ValueError('Load draft source/input pin changed: ' + path)
    return json.loads(raw)

def instructions(value):
    """Visit individual addressed instructions, never join noncontiguous blocks."""
    if isinstance(value, dict):
        if {'va', 'bytes'} <= value.keys():
            yield value
        else:
            for child in value.values():
                yield from instructions(child)
    elif isinstance(value, list):
        for child in value:
            yield from instructions(child)

def verify_source():
    provider_proof, witness = configuration.verify_source()
    load = pinned_json(LOAD_PATH, LOAD_SHA256)
    prepared = pinned_json(PREPARED_PATH, PREPARED_SHA256)
    contract = load['contract']
    if load['images']['core']['sha256'] != provider.CORE_SHA256 or contract['load_abi']['win64_signature'] != 'int32 Load(void *outer_this, void *reader)' or contract['load_abi']['R8_input_used'] is not False or (contract['load_abi']['outer_rva'] != 4383776) or (contract['load_abi']['inner_rva'] != 246368) or (contract['configuration_copy']['outer_rva'] != 4387952) or (contract['configuration_copy']['inner_rva'] != 247936) or (prepared['contract']['game_state']['getter']['raw_hex'] != '0fb681a4020000c3') or (prepared['contract']['game_state']['getter']['field_width_bytes'] != 1) or (load['verification']['each_instruction_rechecked_by_va'] is not True):
        raise ValueError('Load/Prepare/initialized getter source contract differs')
    for parent in load['parents'].values():
        pinned_json(parent['path'], parent['sha256'])
    return dict(provider=provider_proof, witness=witness, load=load, prepared=prepared)

@dataclass(frozen=True)
class MatchedInputs:
    configuration: bytes
    game: bytes
    manifest_sha256: str
    expected_turn: int
    expected_width: int
    expected_height: int
    profile_name: str = 'baseline352'

def _events(value):
    if isinstance(value, dict):
        if 'stage' in value:
            yield value
        for child in value.values():
            yield from _events(child)
    elif isinstance(value, list):
        for child in value:
            yield from _events(child)

def read_matched_inputs(witness):
    manifest = pinned_json(configuration.MANIFEST_PATH, configuration.MANIFEST_SHA)
    config = configuration.read_pinned_sidecar()
    row = manifest['components']['gamecore']
    relative = _resolve_resource_path(Path(row['path']))
    folder = _resolve_resource_path(ROOT / configuration.MANIFEST_PATH).resolve().parent
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Game component path must be contained and relative')
    path = _resolve_resource_path(ROOT / relative).resolve()
    if path.parent != folder or path.name != 'round1.gamecore.raw':
        raise ValueError('Game component is outside the matched checkpoint directory')
    game = _resolve_resource_path(path).read_bytes()
    if row['sha256'] != GAME_SHA256 or type(row['bytes']) is not int or row['bytes'] != GAME_BYTES or (len(game) != GAME_BYTES) or (sha(game) != GAME_SHA256) or (game[:4] != b'\x05\x00\x00\x00'):
        raise ValueError('Game component complete bytes/version differ')
    events = list(_events(witness))
    saves = [e for e in events if e['stage'] == 'native_checkpoint_preflight']
    population = [e for e in events if e['stage'] == 'native_new_game_population_verified']
    prior = events[:events.index(saves[0])] if len(saves) == 1 else []
    round1 = [e for e in prior if e['stage'] == 'native_round_effect_verified' and e.get('native_rounds_completed') == 1]
    if len(saves) != 1 or saves[0]['round_completed'] != 1 or saves[0]['mode'] != 'save-config' or (len(population) != 1) or (len(round1) != 1) or (round1[0]['after']['current_game_turn'] != 2) or ((population[0]['width'], population[0]['height']) != (74, 46)):
        raise ValueError('Matched saved readback provenance differs')
    return MatchedInputs(config, game, configuration.MANIFEST_SHA, 2, 74, 46)

def validate_inputs(inputs):
    if type(inputs) is MatchedInputs and inputs.profile_name == 'previctory12':
        from civ6_host.runtime.native.native_checkpoint_previctory_profile import validate_load_binding
        validate_load_binding(inputs, ROOT, MatchedInputs)
        return
    if type(inputs) is MatchedInputs and inputs.profile_name in ('retained118', 'retained121', 'retained150', 'retained182'):
        from civ6_host.runtime.native.native_checkpoint_retained_profile import validate_load_binding
        validate_load_binding(inputs, ROOT, MatchedInputs)
        return
    if type(inputs) is MatchedInputs and inputs.profile_name == 'late380':
        from civ6_host.runtime.native.native_checkpoint_profile import LATE_380
        LATE_380.require_ready()
        if type(inputs.configuration) is not bytes or type(inputs.game) is not bytes or len(inputs.configuration) != LATE_380.configuration_bytes or (sha(inputs.configuration) != LATE_380.configuration_sha256) or (len(inputs.game) != LATE_380.game_bytes) or (sha(inputs.game) != LATE_380.game_sha256) or (inputs.manifest_sha256 != LATE_380.manifest_sha256) or any((type(v) is not int for v in (inputs.expected_turn, inputs.expected_width, inputs.expected_height))) or ((inputs.expected_turn, inputs.expected_width, inputs.expected_height) != (115, 74, 46)):
            raise ValueError('Late Load admits only the finalized immutable380 component pair')
        return
    if type(inputs) is not MatchedInputs or inputs.profile_name != 'baseline352' or type(inputs.configuration) is not bytes or (type(inputs.game) is not bytes) or (len(inputs.configuration) != configuration.SIDECAR_SIZE) or (sha(inputs.configuration) != configuration.SIDECAR_SHA) or (len(inputs.game) != GAME_BYTES) or (sha(inputs.game) != GAME_SHA256) or (inputs.manifest_sha256 != configuration.MANIFEST_SHA) or any((type(v) is not int for v in (inputs.expected_turn, inputs.expected_width, inputs.expected_height))) or ((inputs.expected_turn, inputs.expected_width, inputs.expected_height) != (2, 74, 46)):
        raise ValueError('Only the immutable matched352 component pair is admitted')

def read_selected_inputs(profile_name, baseline_witness):
    """Select one frozen pair explicitly; no save picker or approximate restore."""
    if profile_name == 'previctory12':
        from civ6_host.runtime.native.native_checkpoint_previctory_profile import read_selected_inputs as previctory_inputs
        return previctory_inputs(profile_name, ROOT, MatchedInputs)
    if profile_name in ('retained118', 'retained121', 'retained150', 'retained182'):
        from civ6_host.runtime.native.native_checkpoint_retained_profile import read_selected_inputs as retained_inputs
        return retained_inputs(profile_name, ROOT, MatchedInputs)
    if profile_name == 'baseline352':
        return (read_matched_inputs(baseline_witness), baseline_witness)
    if profile_name != 'late380':
        raise ValueError('Unknown immutable checkpoint profile')
    from civ6_host.runtime.native.native_checkpoint_profile import LATE_380
    from civ6_host.runtime.native.native_checkpoint_profile import read_verified_pair
    pair = read_verified_pair(LATE_380)
    inputs = MatchedInputs(pair.configuration, pair.game, pair.manifest_sha256, LATE_380.expected_turn, LATE_380.width, LATE_380.height, 'late380')
    validate_inputs(inputs)
    witness = pinned_json(LATE_380.witness_path, LATE_380.witness_sha256)
    return (inputs, witness)

def validated_owner_inputs(owner):
    """Read the exact immutable input binding retained by this native owner."""
    if type(owner) is not NativeLoadBackend:
        raise TypeError('Checkpoint input binding requires the retained native owner')
    inputs = getattr(owner, 'inputs', None)
    validate_inputs(inputs)
    return inputs
READBACK_LUA = b"local function integer(v,lo,hi)\n assert(type(v)=='number' and v==math.floor(v) and v>=lo and v<=hi,'invalid load readback integer')\n return v\nend\nassert(Game and type(Game.GetCurrentGameTurn)=='function','loaded Game getter unavailable')\nassert(Map and type(Map.GetGridSize)=='function','loaded Map getter unavailable')\nassert(PlayerManager and type(PlayerManager.GetAliveMajorIDs)=='function','loaded roster unavailable')\nlocal turn=integer(Game.GetCurrentGameTurn(),0,2147483647)\nlocal w,h=Map.GetGridSize(); w=integer(w,1,16384); h=integer(h,1,16384)\nassert(w*h<=16384,'loaded map exceeds diagnostic bound')\nlocal ids=PlayerManager.GetAliveMajorIDs(); assert(type(ids)=='table' and #ids==2,'loaded major roster differs')\ntable.sort(ids)\nassert(integer(ids[1],0,63)==0 and integer(ids[2],0,63)==1,'loaded player identities differ')\nassert(Players[0]~=nil and Players[1]~=nil,'loaded native player facade absent')\nreturn string.format('%d|%d|%d|%d|%d',turn,w,h,ids[1],ids[2])\n"

def parse_readback(raw, inputs):
    if type(raw) is not bytes or re.fullmatch(b'(0|[1-9][0-9]*)\\|[1-9][0-9]*\\|[1-9][0-9]*\\|0\\|1', raw) is None:
        raise ValueError('Malformed native Load readback')
    turn, width, height, _, _ = map(int, raw.split(b'|'))
    if (turn, width, height) != (inputs.expected_turn, inputs.expected_width, inputs.expected_height):
        raise ValueError('Loaded turn/map differs from the matched saved witness')
    return dict(current_game_turn=turn, width=width, height=height, major_player_ids=[0, 1], scope='privileged diagnostic; no learner observation', game_update_called=False)

def check_live_bodies(base, read, proofs):
    names = ('load_outer', 'inner_load', 'new_0x42f470', 'new_0x3c880', 'new_0x10c170', 'new_0x10c2c0', 'new_0x10d3e0', 'new_0x3bdd0')
    bodies = [proofs['load']['core_functions'][name] for name in names]
    bodies += [proofs['prepared']['captures']['core'][name] for name in ('outer_prepare', 'prepare', 'game_initialized_getter', 'game_read_prepare')]
    seen = {}
    for body in bodies:
        captured = list(instructions(body))
        if not captured:
            raise ValueError('Required Load method has no captured instructions')
        for ins in captured:
            rva, raw = (int(ins['va'], 16) - CORE_BASE, bytes.fromhex(ins['bytes']))
            if rva < 0 or not raw:
                raise ValueError('Invalid addressed source instruction')
            if rva in seen and seen[rva] != raw:
                raise ValueError('Conflicting source capture bytes')
            seen[rva] = raw
    for rva, raw in seen.items():
        if read(base + rva, len(raw)) != raw:
            raise ValueError('Load live body differs at RVA ' + hex(rva))

def _fatal(error):
    try:
        os.write(2, (json.dumps(dict(stage='load_only_fatal', error=str(error)[:512], retry_permitted=False, cleanup_guessed=False)) + '\n').encode())
    finally:
        from civ6_host.runtime.native.native_checkpoint_stream import terminate_worker
        terminate_worker(FATAL_EXIT_CODE)

class NativeLoadBackend(configuration._NativeBackend):
    """Concrete calls, deliberately no Load-success cleanup/continuation claim."""

    def __init__(self, core, context, fixture, dll_directory, profile, proofs, emit, *, candidate_bundle=None):
        from civ6_host.runtime.saved_load_profiles import profile_for_sha
        from civ6_host.runtime.saved_load_profiles import require_saved_load_admission
        self._saved_load_candidate = candidate_bundle is not None
        if self._saved_load_candidate:
            from civ6_host.runtime.captured_saved_load import bind_candidate
            self.load_abi = bind_candidate(candidate_bundle, profile, fixture)
            self.captured_bundle = candidate_bundle
        else:
            self.load_abi = require_saved_load_admission(profile_for_sha(profile.core_sha256))
        super().__init__(core, context, fixture, dll_directory, profile, proofs['provider'], emit)
        self.proofs = proofs
        self.stage = 'fresh'
        self.busy = self.poisoned = False
        self.prefix = self.reader = self.jobs = None
        self.streams = []
        self.snapshot_phase = 'idle'
        self.load_attempted = False
        self.inputs = None
        self.verify_load_bodies()

    def check_thread(self):
        if self.runtime.thread() != self.thread or self.poisoned or self.destroyed:
            raise RuntimeError('Load owner is foreign-thread, poisoned or destroyed')

    def topology(self, *, game_required):
        self.check_thread()
        read, base = (self.runtime.read, self.core._handle)
        q = lambda p: struct.unpack('<Q', read(p, 8))[0]
        if q(self.context) != base + self.load_abi.outer_vtable_rva:
            raise ValueError('Load outer vtable differs')
        inner = q(self.context + 8)
        if not inner or q(inner) != base + self.load_abi.inner_vtable_rva:
            raise ValueError('Load inner vtable differs')
        for vt, slot, target in self.load_abi.virtual_targets:
            if q(base + vt + slot) != base + target:
                raise ValueError('Load virtual target differs')
        if not q(inner + 80) or not q(inner + 88):
            raise ValueError('Load lacks actual Configuration/Gameplay connections')
        game = q(inner + 96)
        if game_required:
            if not game or q(game) != base + self.load_abi.game_vtable_rva:
                raise ValueError('Prepared native Game identity differs')
        elif game:
            raise ValueError('Fresh restore requires native Game NULL')
        return dict(inner=inner, game=game, provider=q(inner + 3584))

    def game_flag(self):
        t = self.topology(game_required=True)
        base = self.core._handle
        if self.runtime.read(base + self.load_abi.game_initialized_rva, 8) != bytes.fromhex('0fb681a4020000c3'):
            raise ValueError('Native Game initialized getter changed')
        return int(C.WINFUNCTYPE(C.c_uint32, C.c_void_p)(base + self.load_abi.game_initialized_rva)(t['game']))

    def initialize_fresh(self):
        self.state(False)
        self.initialize()
        self.state(True)
        self.stage = 'initialized'

    def restore_b(self, inputs):
        validate_inputs(inputs)
        if self.inputs is not inputs:
            raise RuntimeError('Configuration restore is not bound to this Load input pair')
        self.clone()
        before = self.state(True)
        restored = provider.restore_provider(self.core, self.context, self.owner, inputs.configuration, expected_sha256=sha(inputs.configuration), max_bytes=MAX_BYTES, max_calls=MAX_CALLS)
        output, serialized = self.serialize()
        from civ6_host.runtime.native.native_checkpoint_configuration_normalization import compare_configuration_streams
        comparison = compare_configuration_streams(inputs.configuration, output)
        if self.state(True) != before:
            raise RuntimeError('Configuration restore changed A/context identity')
        provider.seal_restoration(self.core, self.context, self.owner, max_bytes=MAX_BYTES, max_calls=MAX_CALLS)
        self.stage = 'B-restored-sealed'
        return dict(restore=restored, serialize=serialized, comparison=comparison)

    def prepare(self, *, required_ownership_mode=208129763):
        if getattr(self, '_saved_load_candidate', False):
            from civ6_host.runtime.captured_saved_load import prepare_candidate
            return prepare_candidate(self, required_ownership_mode=required_ownership_mode)
        self.topology(game_required=False)
        self.host.enable_tuner_unavailable_probe()
        self.host.configure_local_player_id(0)
        from civ6_host.runtime.native.native_options import enable_empty_performance_probe
        from civ6_host.runtime.native.native_host_capability_status import install_typed_refusal
        from civ6_host.runtime.native.native_host_thread_gate import install_synchronous_host_thread_gate
        from civ6_host.runtime.native.native_host_thread_gate import PROFILE
        from civ6_host.runtime.native.native_host_slot28 import install
        from civ6_host.runtime.native.native_host_slot28 import PROFILE as HISTORY_PROFILE
        from civ6_host.runtime.native.native_app_ownership import install_closed_base_status
        enable_empty_performance_probe(self.host, self.core)
        install_typed_refusal(self.host, base=self.core._handle, read=self.runtime.read)
        install_synchronous_host_thread_gate(self.host, profile=PROFILE)
        install(self.host, profile=HISTORY_PROFILE)
        captured_bundle = getattr(self, 'captured_bundle', None)
        if captured_bundle is not None and getattr(captured_bundle, 'inputs', None) is not self.inputs:
            raise ValueError('Official bundle ownership context differs from the loaded input pair')
        install_closed_base_status(self.host, self.owner, self.dll_directory.parents[2], required_mode=required_ownership_mode, captured_bundle=captured_bundle)
        from civ6_host.runtime.native.native_host import prepare_context
        prepare_context(self.core, self.context, self.emit, saved_load_abi=self.load_abi)
        if self.game_flag() != 0:
            raise RuntimeError('Fresh prepared Game is already initialized')
        self.stage = 'prepared'

    def install_prefix(self):
        self.check_thread()
        from civ6_host.runtime.native.native_map_script import NativeMapScriptPrefix
        self.prefix = NativeMapScriptPrefix(self.host, self.core, self.context, self.emit, selected_gameplay_scripts=(), diagnostic_action='initial-view', configuration_readback='after-configuration-copy')
        if self.prefix.configuration_readback_verified is not False:
            raise RuntimeError('Load configuration readback was not deferred until +120')
        self.stage = 'prefix-installed'

    def copy_b_to_a(self):
        if self.load_abi.ruleset != 'base':
            from civ6_host.runtime.configuration_profiles import verify_context_copy
            verify_context_copy(self.load_abi, self.core._handle, self.runtime.read)
        before = self.topology(game_required=True)
        self.owner.require_context(self.core._handle, self.context)
        b_before = self.owner.snapshot()
        if self.owner.new_game_entered is not False or self.game_flag() != 0:
            raise ValueError('Load copy requires fresh B and uninitialized Game')
        C.WINFUNCTYPE(None, C.c_void_p, C.c_void_p)(self.core._handle + self.load_abi.copy_rva)(self.context, self.owner.pointer)
        after = self.topology(game_required=True)
        from civ6_host.runtime.native import native_configuration_finalization as setup
        indexed = setup._linked_snapshot(self.core._handle, self.context, self.runtime.read, None, core_sha256=self.load_abi.core_sha256)
        a = application.provider_snapshot(self.core._handle, after['provider'], self.runtime.read, core_sha256=self.load_abi.core_sha256)
        b = self.owner.snapshot()
        if before['inner'] != after['inner'] or before['game'] != after['game'] or b != b_before or (self.game_flag() != 0) or any((a[k] != indexed[k] for k in ('descriptor', 'normalized', 'map_normalized', 'players'))):
            raise RuntimeError('Native +120 copy/reindex identity changed unexpectedly')

        def addresses(s):
            return {s['descriptor'], s['normalized'], s['map_normalized'], *s['players']}
        if addresses(a) & addresses(b):
            raise RuntimeError('Loaded A and owned B share native submaps')
        self.prefix.verify_configuration_scalar_marshalling()
        if self.prefix.configuration_readback_verified is not True:
            raise RuntimeError('Copied A configuration readback was not verified')
        self.stage = 'copied'
        return dict(core_player_records_reacquired=64, distinct_submaps=66, all_property_values_compared=False, new_game_called=False)

    def control(self, *, empty, allow_diplomacy=False, pending_round_actor=None):
        if getattr(self, '_saved_load_candidate', False):
            from civ6_host.runtime.captured_saved_load import control_snapshot
            return control_snapshot(self, empty=empty, allow_diplomacy=allow_diplomacy, pending_round_actor=pending_round_actor)
        p = self.prefix
        if p is None:
            raise ValueError('Load prefix is absent')
        d = p.deferred_events
        if type(allow_diplomacy) is not bool or (pending_round_actor is not None and (not allow_diplomacy or type(pending_round_actor) is not int or pending_round_actor != 0)):
            raise ValueError('Invalid interrupted-turn control scope')
        if p.actions.pending and pending_round_actor is not None:
            p.actions.validate_completed_round_echo(pending_round_actor)
        if p.actions.pending and pending_round_actor is None or any((getattr(d, n, False) for n in ('_draining_empty_receivers', '_deferred_drain_poisoned', '_combat_producer_poisoned', '_status_producer_poisoned', '_experience_producer_poisoned', '_f391_poisoned', '_f391_producing', '_found_city_poisoned', '_found_city_producing', '_36c9_poisoned', '_36c9_producing', '_district_combat_poisoned', '_district_combat_producing', '_city_command_started_poisoned', '_city_command_started_producing', '_84c1fdd6_poisoned', '_84c1fdd6_producing', '_diplomacy_poisoned', '_diplomacy_producing'))):
            raise RuntimeError('Load control is busy or poisoned')
        if not allow_diplomacy and getattr(d, 'pending_diplomacy_statements', []):
            raise RuntimeError('Load control retains an unanswered diplomacy statement')
        receiver = getattr(d, 'diplomacy_receiver', None)
        if receiver is not None and (receiver.busy or receiver.poisoned):
            raise RuntimeError('Load control has an active or poisoned diplomacy receiver')
        if any((getattr(p.actions, n, False) for n in ('_city_range_attack_poisoned', '_city_range_attack_producing'))):
            raise RuntimeError('Load control has an active or poisoned city command producer')
        if any((type(getattr(d, n)) is not int or getattr(d, n) != 0 for n in ('host_notification_counter', 'host_metadata_counter'))):
            raise RuntimeError('Load requires a closed notification scope')
        registry = d.combat_map_registry
        if registry is not None and (registry.poisoned or registry.entries):
            raise RuntimeError('Load retains combat snapshots')
        if empty and (d.pending or d._sequence != d.consumed_count):
            raise RuntimeError('Load must start with fully consumed public notifications')
        return dict(pending_count=len(d.pending), sequence=d._sequence, consumed=d.consumed_count, notification_counter=d.host_notification_counter, metadata_counter=d.host_metadata_counter)

    def create_reader(self, inputs):
        if getattr(self, '_saved_load_candidate', False):
            from civ6_host.runtime.captured_saved_load import validate_candidate_inputs
            validate_candidate_inputs(inputs, self.captured_bundle)
            if self.inputs is not inputs:
                raise ValueError('XP1 reader is not bound to the retained captured input pair')
        from civ6_host.runtime.capture_profiles import LAN_PROFILE
        call_limit = GAME_READ_MAX_CALLS
        if getattr(inputs, 'profile', None) is LAN_PROFILE or getattr(self, '_saved_load_candidate', False):
            if not 0 < len(inputs.game) <= MAX_BYTES:
                raise ValueError('Captured LAN stream exceeds the byte limit')
            call_limit = max(GAME_READ_MAX_CALLS, len(inputs.game) * 2)
            self.emit('native_lan_stream_budget', game_bytes=len(inputs.game), call_limit=call_limit, stream_byte_limit=MAX_BYTES, simulation_rules_changed=False)
        from civ6_host.runtime.native.native_checkpoint_job_observer import make_job_observer
        from civ6_host.runtime.native.native_checkpoint_jobs import PROFILE
        self.check_thread()
        if self.load_attempted or self.reader is not None or self.stage != 'copied':
            raise RuntimeError('Load reader may be constructed exactly once after +120')
        self.reader = Win64Stream('reader', max_bytes=MAX_BYTES, max_calls=call_limit, input_bytes=inputs.game)
        self.streams.append(self.reader)
        self.jobs = self.make_job_observer()
        self.bound_identity = self.topology(game_required=True)
        if self.game_flag() != 0:
            raise ValueError('Native Game initialized before first Load')
        self.verify_load_bodies()
        self.control(empty=True)
        self.reader._check(self.reader.pointer)
        self.load_call = C.WINFUNCTYPE(C.c_int32, C.c_void_p, C.c_void_p)(self.core._handle + self.load_abi.load_rva)

    def jobs_snapshot(self, phase):
        if phase not in ('before', 'after'):
            raise ValueError('Unknown Load job observation phase')
        self.snapshot_phase = phase
        return self.jobs()

    def load_raw(self):
        self.check_thread()
        if self.load_attempted or self.stage != 'copied' or (not self.busy) or (self.snapshot_phase != 'before'):
            raise RuntimeError('Load entry requires its first exclusive post-snapshot attempt')
        self.reader._check(self.reader.pointer)
        self.snapshot_phase = 'load'
        self.load_attempted = True
        if getattr(self, '_saved_load_candidate', False):
            from civ6_host.runtime.xp1_load_capability import capability_source_scope
            with capability_source_scope(self, 'load'):
                return self.load_call(self.context, self.reader.pointer)
        return self.load_call(self.context, self.reader.pointer)

    def validate_load_return(self, status, inputs, before_jobs, after_jobs):
        self.snapshot_phase = 'postflight'
        self.reader._check(self.reader.pointer)
        if type(status) is not int or status != 0:
            raise RuntimeError('Native Load compatibility status is not exact zero')
        if self.reader.transport.cursor != len(inputs.game):
            raise RuntimeError('Native Load did not consume the complete Game component')
        from civ6_host.runtime.native.native_checkpoint_postload_jobs import validate_quiescent_snapshot_transition
        try:
            jobs_candidate = self.validate_job_transition(before_jobs, after_jobs)
        except (ValueError, RuntimeError) as error:
            raise RuntimeError('Load scheduler transition refused: ' + str(error)) from error
        after = self.topology(game_required=True)
        if after != self.bound_identity or self.game_flag() != 1:
            raise RuntimeError('Load identity or actual Game initialized flag differs')
        self.control(empty=False)
        self.stage = 'raw-loaded'
        return dict(status=status, bytes_consumed=self.reader.transport.cursor, stream_calls=self.reader.transport.calls, game_initialized=1, jobs_identical=before_jobs == after_jobs, jobs_structural_candidate=jobs_candidate, scheduler_ledger_reconciliation_pending=True, readback_only_diagnostic=True, load_source_sha256=self.load_source_sha256)

    def invalidate_reader(self):
        if self.reader is not None and (not self.reader.transport.closed):
            self.reader.close()

    def read_loaded(self, inputs):
        self.check_thread()
        if self.stage != 'raw-loaded':
            raise RuntimeError('Readback requires the validated raw Load boundary')
        raw = self.prefix.runtime.evaluate_text(self.prefix.game_child, READBACK_LUA, b'@native_loaded_component_readback', capacity=256)
        return parse_readback(raw, inputs)

    def postload_160(self):
        raise RuntimeError('Post-load +160 is a separate unadmitted phase; AUX kind1/category2 needs Host42')

    def verify_load_bodies(self):
        if getattr(self, '_saved_load_candidate', False):
            from civ6_host.runtime.captured_saved_load import verify_live, SOURCES
            result = verify_live(self.core._handle, self.runtime.read, self.proofs)
            self.load_source_sha256 = SOURCES[0][1]
            return result
        self.load_source_sha256 = LOAD_SHA256
        return check_live_bodies(self.core._handle, self.runtime.read, self.proofs)

    def make_job_observer(self):
        if getattr(self, '_saved_load_candidate', False):
            from civ6_host.runtime.captured_saved_load import make_job_observer
            return make_job_observer(self)
        from civ6_host.runtime.native.native_checkpoint_job_observer import make_job_observer
        from civ6_host.runtime.native.native_checkpoint_jobs import PROFILE
        return make_job_observer(self.runtime.read, expected_executable_path=ROOT / 'work/native-script-services-host41/civ6rl-native-python.exe', owner_thread_id=self.thread[1], profile=PROFILE, exclusive_owner_entry=lambda: self.busy and self.snapshot_phase in ('before', 'after') and (self.runtime.thread() == self.thread))

    def validate_job_transition(self, before_jobs, after_jobs):
        if getattr(self, '_saved_load_candidate', False):
            from civ6_host.runtime.saved_load_job_observer import validate_transition
            return validate_transition(self, before_jobs, after_jobs)
        from civ6_host.runtime.native.native_checkpoint_postload_jobs import validate_quiescent_snapshot_transition
        return validate_quiescent_snapshot_transition(before_jobs, after_jobs)

    def close_loaded(self, *, completed):
        from civ6_host.runtime.xp1_loaded_lifetime import close_loaded
        return close_loaded(self, completed=completed)

def _run_backend(backend, inputs, emit, *, fatal=_fatal):
    """Pure orchestration seam; concrete backend is the only future native path."""
    validate_inputs(inputs)
    if backend.busy or backend.poisoned or backend.stage != 'fresh' or (getattr(backend, 'inputs', None) is not None):
        raise RuntimeError('Load-only is one attempt on a fresh owner')
    backend.inputs = inputs
    entered = False
    backend.busy = True
    try:
        entered = True
        backend.initialize_fresh()
        configuration_receipt = backend.restore_b(inputs)
        backend.prepare()
        backend.install_prefix()
        topology = backend.copy_b_to_a()
        backend.create_reader(inputs)
        emit('before_native_checkpoint_load', manifest_sha256=inputs.manifest_sha256, checkpoint_profile=inputs.profile_name, expected_game_turn=inputs.expected_turn, configuration=configuration_receipt, topology=topology, game_component_bytes=len(inputs.game), game_read_call_limit=GAME_READ_MAX_CALLS, stream_byte_limit=MAX_BYTES, eligible_for_training=False)
        try:
            before = backend.jobs_snapshot('before')
            status = backend.load_raw()
            after = backend.jobs_snapshot('after')
            emit('native_checkpoint_load_returned_diagnostic', native_status=status, jobs_before=before, jobs_after=after, jobs_identical=before == after, validation_completed=False, eligible_for_training=False)
            receipt = backend.validate_load_return(status, inputs, before, after)
        finally:
            backend.invalidate_reader()
        readback = backend.read_loaded(inputs)
        result = dict(raw_component_load_observed=True, receipt=receipt, readback=readback, post160_called=False, post160_completed=False, continuation_validated=False, context_destroyed=False, owners_retained=True, new_game_called=False, game_update_called=False, reset_validated=False, eligible_for_training=False, controlled_stop_required=True)
        backend.stage = 'observed-awaiting-post160'
        emit('native_checkpoint_load_only_observed', **result)
        return result
    except BaseException as error:
        backend.poisoned = True
        backend.stage = 'poisoned'
        if entered:
            fatal(error)
            raise RuntimeError('Fatal implementation unexpectedly returned') from error
        raise
    finally:
        backend.busy = False

def run_load_only(core, context, *, fixture, dll_directory, profile, emit, checkpoint_profile='baseline352'):
    """Supervised worker entry; no CLI, no DLL loading, no reset claim.

    Caller must treat return as an observed partial lifecycle and terminate or
    enter a separately source-validated post160 phase. It must NOT run the
    normal worker Destroy/close sequence merely because status was zero.
    """
    if not callable(emit):
        raise ValueError('A bounded diagnostic emitter is required')
    proofs = verify_source()
    inputs, witness = read_selected_inputs(checkpoint_profile, proofs['witness'])
    fixture = configuration.validate_private_fixture(fixture, witness)
    key = (id(core), context)
    if key in _RETAINED or key in configuration._RETAINED:
        raise ValueError('Load-only context already belongs to a diagnostic attempt')
    backend = NativeLoadBackend(core, context, fixture, dll_directory, profile, proofs, emit)
    _RETAINED[key] = backend
    return _run_backend(backend, inputs, emit)

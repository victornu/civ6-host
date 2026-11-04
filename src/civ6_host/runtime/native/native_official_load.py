"""One frozen official-save Load experiment; never a training admission.

Reuses the established Base loader without extending its matched checkpoint
profiles. The database and gameplay-script association to this save is NOT
proved. This diagnostic can discover a refusal, not certify a faithful restore.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
import ctypes as C
import hashlib
import json
from pathlib import Path
import time
from civ6_host.runtime.native.native_checkpoint_load import NativeLoadBackend
from civ6_host.runtime.native.native_checkpoint_load import MAX_BYTES
from civ6_host.runtime.native.native_checkpoint_load import MAX_CALLS
from civ6_host.runtime.native import native_checkpoint_provider as provider
from civ6_host.runtime.native.official_configuration import read_provider
from civ6_host.runtime.native.official_configuration import compare_provider_roundtrip
from civ6_host.runtime.native.native_game_configuration import game_configuration_hash
from civ6_host.runtime.native.native_map_script import NativeMapScriptPrefix
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_official_load.py')))).resolve().parents[1]
SAVE_SHA = '008cfcb376532994febdb0c6d039c98bd4ef7a1b75c92a810d91eee29605fdeb'
CONFIG_SHA = '7e96a2ce3c16c2ffb9b69f373ce82251fea1c76e339ae9cce5416f2c161edf08'
GAME_SHA = 'fefe0e23acd34db2cc06d8a966a6dac0bcf3f37c11c309de7213b7660303e0e3'
SAVE_FOLDER = ROOT / 'work/official-save907/capture01' / SAVE_SHA
WITNESS_PATH = ROOT / 'evidence/phase14-native-pretransport-snapshot01.json'
WITNESS_SHA = '964d1e6f67f07b9cc339170c97ecfb93cc0c9da05f490a001959274ce4585d26'

@dataclass(frozen=True)
class OfficialProfile:
    name: str
    save_sha: str
    config_start: int
    config_end: int
    config_sha: str
    game_file: str
    game_sha: str
    game_bytes: int
    mode_name: str
    capture_root: str = 'work/official-save907/capture01'

    @property
    def folder(self):
        return ROOT / self.capture_root / self.save_sha
HOTSEAT_PROFILE = OfficialProfile('hotseat-combat-fixture', SAVE_SHA, 14018, 32651, CONFIG_SHA, 'section-02-0000c6b7-gamecore_stream_candidate.raw', GAME_SHA, 746428, 'HOTSEAT')
SINGLE_PROFILE = OfficialProfile('base-single-baseline', '14efc4c87cac1fdb46c8e87114750d1ff9bbf5875c7843395b5afe9a6a1e9cc8', 79353, 100967, '8008c2f3725b05c35d52edeaa13e474dc977274e2307b265e53248691e8e7efb', 'section-03-0001ac76-gamecore_stream_candidate.raw', '88f5f8920e6e45b5e0f0549f06c8913e40c8f5bda1427e13e26661550cc43fc8', 1199830, 'SINGLEPLAYER')
HOTSEAT_FOUR_PROFILE = OfficialProfile('hotseat-four-human-baseline', '49a7529fe506c2b9c1cb05933eb11499c67caa96d9697c3c6a73007b252b1490', 12867, 35427, 'b7e54787fcba5ee344b788d548152a27d73fcd90acf030093d657f3b9a80a1d3', 'section-02-0000e0cd-gamecore_stream_candidate.raw', '1ce59da52e157406e99874e966a4d7377419a7ebd538a0289b967050a1f24b1b', 2246656, 'HOTSEAT', 'work/official-hotseat921/capture01')

def validate_profile(profile):
    if profile is LAN_PROFILE:
        return profile
    if not any((profile is admitted for admitted in (HOTSEAT_PROFILE, SINGLE_PROFILE, HOTSEAT_FOUR_PROFILE))):
        raise ValueError('Only the frozen official Base diagnostics are admitted')
    return profile

def roster_readback_source(profile, *, candidate_bundle=None):
    if candidate_bundle is not None:
        from civ6_host.runtime.captured_saved_load import validate_candidate_inputs
        if validate_candidate_inputs(candidate_bundle.inputs, candidate_bundle) is not profile:
            raise ValueError('XP1 roster profile differs from its captured bundle')
        from civ6_host.runtime.lan_load import roster_readback_source as lan_source
        return lan_source()
    if profile is LAN_PROFILE:
        from civ6_host.runtime.lan_load import roster_readback_source as lan_roster_source
        return lan_roster_source()
    validate_profile(profile)
    if profile is not HOTSEAT_FOUR_PROFILE:
        from civ6_host.runtime.native.native_checkpoint_load import READBACK_LUA
        return READBACK_LUA
    return b"local function integer(v,lo,hi)\n assert(type(v)=='number' and v==math.floor(v) and v>=lo and v<=hi,'invalid load readback integer')\n return v\nend\nassert(Game and type(Game.GetCurrentGameTurn)=='function','loaded Game getter unavailable')\nassert(Map and type(Map.GetGridSize)=='function','loaded Map getter unavailable')\nassert(PlayerManager and type(PlayerManager.GetAliveMajorIDs)=='function','loaded roster unavailable')\nlocal turn=integer(Game.GetCurrentGameTurn(),0,2147483647)\nlocal w,h=Map.GetGridSize();w=integer(w,1,16384);h=integer(h,1,16384)\nassert(w*h<=16384,'loaded map exceeds diagnostic bound')\nlocal ids=PlayerManager.GetAliveMajorIDs();assert(type(ids)=='table' and #ids==4,'loaded major roster differs')\ntable.sort(ids)\nlocal rows={tostring(turn),tostring(w),tostring(h)}\nfor i=1,4 do\n assert(integer(ids[i],0,63)==i-1,'loaded player identities differ')\n assert(Players[ids[i]]~=nil,'loaded native player facade absent')\n assert(type(Players[ids[i]].IsHuman)=='function' and Players[ids[i]]:IsHuman()==true,\n        'loaded major is not a human player')\n rows[#rows+1]=tostring(ids[i])\nend\nreturn table.concat(rows,'|')"

def sha(data):
    return hashlib.sha256(data).hexdigest()

@dataclass(frozen=True)
class OfficialInputs:
    configuration: bytes
    game: bytes
    map_values: tuple[tuple[str, int | None], ...]
    profile: OfficialProfile = HOTSEAT_PROFILE
    checkpoint: tuple[str, str] | None = None
    official_bundle: tuple[str, str] | None = None

def validate_inputs(inputs, *, candidate_bundle=None):
    if candidate_bundle is not None:
        from civ6_host.runtime.captured_saved_load import validate_candidate_inputs
        return validate_candidate_inputs(inputs, candidate_bundle)
    if type(inputs) is OfficialInputs and inputs.profile is LAN_PROFILE and (inputs.official_bundle is None):
        raise ValueError('LAN inputs require a validated exact official capture')
    if type(inputs) is not OfficialInputs:
        raise ValueError('Expected immutable official diagnostic inputs')
    profile = validate_profile(inputs.profile)
    if inputs.official_bundle is not None:
        from civ6_host.runtime.native.native_official_bundle import validate_inputs as validate_bundle
        validate_bundle(inputs)
    elif inputs.checkpoint is not None:
        from civ6_host.runtime.native.native_session_resume import validate_inputs as validate_checkpoint
        validate_checkpoint(inputs)
    elif sha(inputs.configuration) != profile.config_sha or sha(inputs.game) != profile.game_sha:
        raise ValueError('Frozen official input pair differs from the selected profile')
    return profile

def read_inputs(profile=HOTSEAT_PROFILE):
    if profile is LAN_PROFILE:
        raise ValueError('There is no historical LAN fixture; supply an exact official capture')
    profile = validate_profile(profile)
    data = _resolve_resource_path(profile.folder / 'source.Civ6Save').read_bytes()
    if sha(data) != profile.save_sha or data[profile.config_start - 4:profile.config_start] != b'\x01\x00\x00\x00':
        raise ValueError('Official save or app configuration marker changed')
    configuration = data[profile.config_start:profile.config_end]
    values, end = read_provider(configuration)
    if end != len(configuration) or sha(configuration) != profile.config_sha:
        raise ValueError('Official app provider boundary differs')
    root = {v.key: v for v in values}
    game_root = root[game_configuration_hash('GAME_ROOT')]
    mode = next((v for v in game_root.children if v.key == game_configuration_hash('GAME_MODE')))
    if mode.tag != 3 or mode.scalar() != game_configuration_hash(profile.mode_name):
        raise ValueError('This experiment requires the saved actual ' + profile.mode_name + ' mode')
    map_root = root[game_configuration_hash('MAP_ROOT')]
    children = {v.key: v for v in map_root.children}
    expected = []
    for name in ('start', 'world_age', 'RANDOM_SEED', 'MAP_SIZE'):
        value = children.get(game_configuration_hash(name))
        if value is None and name in ('start', 'world_age'):
            expected.append((name, None))
            continue
        if value is None:
            raise ValueError('Required saved map value is absent: ' + name)
        if value.tag not in (2, 3) or value.flags != 0:
            raise ValueError('Saved map scalar is outside this readback profile')
        expected.append((name, C.c_int32(value.scalar()).value))
    game = _resolve_resource_path(profile.folder / profile.game_file).read_bytes()
    if sha(game) != profile.game_sha or len(game) != profile.game_bytes or game[:4] != b'\x05\x00\x00\x00':
        raise ValueError('Official decompressed component changed')
    return OfficialInputs(configuration, game, tuple(expected), profile)

def compare_reference(observed):
    """Only the explicit P0 fields witnessed before this exact official save."""
    raw = _resolve_resource_path(WITNESS_PATH).read_bytes()
    if sha(raw) != WITNESS_SHA:
        raise ValueError('Official pre-save witness changed')
    witness = json.loads(raw)
    if witness['snapshot']['sha256'] != SAVE_SHA or witness['snapshot']['bytes'] != 111642:
        raise ValueError('Witness does not identify this exact official save')
    record = witness['pre_snapshot_observation']
    state = record['observation']
    fields = ('id', 'type', 'x', 'y', 'damage', 'moves')
    expected = dict(turn=record['turn'], width=state['map']['width'], height=state['map']['height'], player_id=record['player_id'], gold=state['economy']['gold'], city_count=len(state['cities']), units=sorted(({k: u[k] for k in fields} for u in state['units']), key=lambda u: u['id']))
    if observed != expected:
        raise ValueError('Loaded limited P0 state differs from the same-save native witness: ' + json.dumps(dict(expected=expected, observed=observed)))
    return dict(matched=True, reference_sha256=WITNESS_SHA, save_sha256=SAVE_SHA, compared=expected, comparison_scope='pre-save P0 own units, city count, gold, turn and dimensions', complete_state_compared=False, observation_filter_validated=False, postload_completed=False, strategic_training_ready=False)

def compare_four_player_reference(observed):
    """The P0 subset recorded before the exact four-human official save."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    folder = ROOT / 'evidence/phase2-hotseat-save-admin'
    record = load_pinned_json(folder / 'before.json', 'bfa60727147212cec5e4cf40cd7c3a0009ffdc1769936446a4cf847f9fa63b23')
    saved = load_pinned_json(folder / 'result.json', 'f5cc3c2e4a5b786ab2888d3575f28775f5225d8fb57e20ef742793d4bd5af447')
    if saved['sha256'] != HOTSEAT_FOUR_PROFILE.save_sha or saved['bytes'] != 221617 or saved['acknowledgement']['player_id'] != record['player_id'] or (saved['acknowledgement']['turn'] != record['turn']) or ((record['player_id'], record['turn']) != (0, 3)):
        raise ValueError('Four-player save witness identity changed')
    state = record['observation']
    fields = ('id', 'type', 'x', 'y', 'damage', 'moves')
    expected = dict(turn=record['turn'], width=state['map']['width'], height=state['map']['height'], player_id=0, gold=state['economy']['gold'], city_count=len(state['cities']), units=sorted(({k: u[k] for k in fields} for u in state['units']), key=lambda u: u['id']))
    if observed != expected:
        raise ValueError('Loaded four-player P0 subset differs from the exact pre-save witness: ' + json.dumps(dict(expected=expected, observed=observed)))
    return dict(matched=True, save_sha256=HOTSEAT_FOUR_PROFILE.save_sha, reference_sha256='bfa60727147212cec5e4cf40cd7c3a0009ffdc1769936446a4cf847f9fa63b23', compared=expected, comparison_scope='pre-save P0 own units, city count, gold, turn and dimensions', complete_state_compared=False, other_player_states_compared=False, observation_filter_validated=False, postload_completed=False, strategic_training_ready=False)

class SavedConfigurationReadback:

    def verify_configuration_scalar_marshalling(self):
        if self.configuration_readback_verified:
            raise ValueError('Configuration scalar readback already verified')
        lines = [f"assert(MapConfiguration.GetValue('{name}')=={('nil' if value is None else value)},'saved {name} differs')" for name, value in self.saved_map_values]
        lines.append("assert(MapConfiguration.GetValue('CIV6RL_MISSING_PROPERTY')==nil)")
        self.runtime.execute(self.game_child, '\n'.join(lines).encode('ascii'), b'@official_saved_configuration_readback')
        self.configuration_readback_verified = True
        self.emit('official_saved_configuration_lua_readback_verified', compared=dict(self.saved_map_values), configuration_mutated=False, source_configuration_sha256=self.saved_config_sha, eligible_for_training=False)

class OfficialPrefix(SavedConfigurationReadback, NativeMapScriptPrefix):

    def __init__(self, *args, saved_map_values, saved_config_sha, **kwargs):
        self.saved_map_values = saved_map_values
        self.saved_config_sha = saved_config_sha
        super().__init__(*args, **kwargs)

class OfficialLoadBackend(NativeLoadBackend):

    def restore_b(self, inputs):
        if type(inputs) is not OfficialInputs or self.inputs is not inputs:
            raise ValueError('Official diagnostic owner/input mismatch')
        profile = validate_inputs(inputs, candidate_bundle=getattr(self, 'captured_bundle', None) if getattr(self, '_saved_load_candidate', False) else None)
        self.clone()
        before = self.state(True)
        restored = provider.restore_provider(self.core, self.context, self.owner, inputs.configuration, expected_sha256=sha(inputs.configuration), max_bytes=MAX_BYTES, max_calls=MAX_CALLS)
        output, written = self.serialize()
        if getattr(self, '_saved_load_candidate', False) and self.load_abi.ruleset == 'xp2':
            from civ6_host.runtime.configuration_roundtrip import compare_provider_roundtrip as selected_comparison
            comparison = selected_comparison(inputs.configuration, output, core_sha256=self.load_abi.core_sha256)
        else:
            comparison = compare_provider_roundtrip(inputs.configuration, output)
        from civ6_host.runtime.native.official_saved_content import compare_content
        declared_content = compare_content(inputs.configuration, output)
        from civ6_host.runtime.native.native_saved_mod_members import read_saved_members
        if getattr(self, '_saved_load_candidate', False):
            native_members = dict(status='separate-native-member-reader-unqualified-for-xp1', native_member_lookup_called=False, serialized_content_compared=True)
        else:
            native_members = read_saved_members(self.owner, inputs.configuration, stopped_configuration_phase=True)
        if self.state(True) != before:
            raise RuntimeError('Official provider restore changed Core identity')
        provider.seal_restoration(self.core, self.context, self.owner, max_bytes=MAX_BYTES, max_calls=MAX_CALLS)
        self.stage = 'B-restored-sealed'
        return dict(restore=restored, serialize=written, comparison=comparison, declared_content=declared_content, native_mod_members=native_members)

    def install_prefix(self, *, services=None):
        if getattr(self, '_saved_load_candidate', False):
            from civ6_host.runtime.captured_saved_load import attach_services
            return attach_services(self, services)
        if services is not None:
            raise ValueError('Externally composed services require the explicit XP1 candidate')
        self.check_thread()
        self.prefix = OfficialPrefix(self.host, self.core, self.context, self.emit, saved_map_values=self.inputs.map_values, saved_config_sha=sha(self.inputs.configuration), selected_gameplay_scripts=(), diagnostic_action='initial-view', configuration_readback='after-configuration-copy')
        if self.prefix.configuration_readback_verified is not False:
            raise RuntimeError('Official configuration readback was not deferred')
        self.stage = 'prefix-installed'

    def read_loaded_diagnostic(self):
        if self.stage != 'raw-loaded':
            raise RuntimeError('Readback requires the validated raw Load return')
        source = b'local w,h=Map.GetGridSize()\nlocal p=Players[0]; assert(p~=nil)\nlocal units={}; for _,u in p:GetUnits():Members() do units[#units+1]=u end\ntable.sort(units,function(a,b) return a:GetID()<b:GetID() end)\nlocal rows={}; for _,u in ipairs(units) do\n for _,name in ipairs({\'GetID\',\'GetType\',\'GetX\',\'GetY\',\'GetDamage\',\'GetMovesRemaining\'}) do\n  assert(type(u[name])==\'function\',\'missing GameCore unit getter: \'..name)\n end\n rows[#rows+1]=string.format(\'{"id":%d,"type":%d,"x":%d,"y":%d,"damage":%d,"moves":%.17g}\',\n u:GetID(),u:GetType(),u:GetX(),u:GetY(),u:GetDamage(),u:GetMovesRemaining())\nend\nlocal cities=0; for _,c in p:GetCities():Members() do cities=cities+1 end\nreturn string.format(\'{"turn":%d,"width":%d,"height":%d,"player_id":0,"gold":%.17g,"city_count":%d,"units":[%s]}\',\n Game.GetCurrentGameTurn(),w,h,p:GetTreasury():GetGoldBalance(),cities,table.concat(rows,\',\'))'
        if self.inputs.checkpoint is not None:
            from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
            if self.load_abi.core_sha256 == XP2_CORE_SHA256:
                original = b'for _,u in p:GetUnits():Members() do units[#units+1]=u end'
                if source.count(original) != 1:
                    raise ValueError('Saved own-unit enumeration changed')
                source = source.replace(original,
                    b'for _,u in p:GetUnits():Members() do\n'
                    b' assert(type(u.IsDelayedDeath)=="function","unit lifecycle getter unavailable")\n'
                    b' if not (u:IsDelayedDeath() == true and u:GetX() == -9999 and u:GetY() == -9999) then\n'
                    b'  units[#units+1]=u\n'
                    b' end\n'
                    b'end')
        raw = self.prefix.runtime.evaluate_text(self.prefix.game_child, source, b'@official_loaded_diagnostic', capacity=4096)
        observed = json.loads(raw)
        profile = validate_inputs(self.inputs, candidate_bundle=getattr(self, 'captured_bundle', None) if getattr(self, '_saved_load_candidate', False) else None)
        if self.inputs.official_bundle is not None:
            bundle = getattr(self, 'captured_bundle', None)
            if bundle is None or bundle.inputs is not self.inputs or observed != bundle.expected_readback:
                raise ValueError('Loaded own-player fields differ from the captured official bundle')
            comparison = dict(matched=True, reference_sha256=bundle.reference[1], compared=observed, comparison_scope='same-save P0 own units, city count, gold, turn and dimensions', complete_state_compared=False, observation_filter_validated=False, strategic_training_ready=False)
        else:
            comparison = compare_reference(observed) if profile is HOTSEAT_PROFILE else compare_four_player_reference(observed) if profile is HOTSEAT_FOUR_PROFILE else dict(matched=None, reference_sha256=None, save_sha256=profile.save_sha, reason='No gameplay witness bound to this exact save hash', complete_state_compared=False, observation_filter_validated=False, strategic_training_ready=False)
        roster = self.prefix.runtime.evaluate_text(self.prefix.game_child, roster_readback_source(profile, candidate_bundle=getattr(self, 'captured_bundle', None) if getattr(self, '_saved_load_candidate', False) else None), b'@official_loaded_roster', capacity=256)
        values = tuple(map(int, roster.decode('ascii').split('|')))
        if len(values) < 4 or values[:3] != (observed['turn'], observed['width'], observed['height']) or tuple(sorted(set(values[3:]))) != values[3:] or (values[3] != 0):
            raise ValueError('Loaded native roster is inconsistent with raw readback')
        if profile is HOTSEAT_FOUR_PROFILE and values[3:] != (0, 1, 2, 3):
            raise ValueError('Four-player saved roster differs; human control is not inferred')
        if self.inputs.official_bundle is not None and profile is SINGLE_PROFILE and (values[3:] != (0, 1)):
            raise ValueError('Captured Single roster is outside the existing two-major adapter')
        self.loaded_readback = observed
        self.loaded_roster = roster
        result = dict(observed=observed, comparison=comparison, major_player_ids=list(values[3:]), privileged_diagnostic=True, learner_observation=False)
        if profile is HOTSEAT_FOUR_PROFILE:
            result.update(human_player_ids=list(values[3:]), human_status_native_verified=True, control_of_all_players_proven=False)
        if profile is LAN_PROFILE:
            from civ6_host.runtime.lan_load import human_status_readback_source
            from civ6_host.runtime.lan_load import validate_loaded_roster
            humans = self.prefix.runtime.evaluate_text(self.prefix.game_child, human_status_readback_source(values[3:]), b'@official_loaded_lan_humans', capacity=320)
            result.update(validate_loaded_roster(self, roster, humans))
        if getattr(self, '_saved_load_candidate', False):
            from civ6_host.runtime.lan_load import human_status_readback_source
            from civ6_host.runtime.captured_saved_load import validate_loaded_roster
            humans = self.prefix.runtime.evaluate_text(self.prefix.game_child, human_status_readback_source(values[3:]), b'@official_loaded_xp1_humans', capacity=320)
            result.update(validate_loaded_roster(self, roster, humans))
        return result

def run_experiment(backend, inputs, *, prepare_services=None):
    """Caller must retain owners and terminate the bounded process afterwards."""
    candidate = getattr(backend, '_saved_load_candidate', False)
    if candidate and (not callable(prepare_services)):
        raise ValueError('XP1 candidate requires explicit existing runtime/child/service composition')
    if not candidate and prepare_services is not None:
        raise ValueError('Service composition is only admitted for the exact XP1 candidate')
    if backend.stage != 'fresh' or backend.inputs is not None:
        raise RuntimeError('Official Load requires one fresh context')
    backend.inputs, backend.busy = (inputs, True)
    profile = validate_inputs(inputs, candidate_bundle=backend.captured_bundle if candidate else None)
    emit = backend.emit
    save_sha = profile.save_sha
    if inputs.official_bundle is not None:
        from civ6_host.runtime.native.native_official_bundle import _manifest
        save_sha = _manifest(inputs.official_bundle)[1]['save']['source']['sha256']
    emit('official_load_scope', save_sha256=save_sha if inputs.checkpoint is None else None, origin_official_save_sha256=save_sha, checkpoint_reference=inputs.checkpoint, official_bundle_reference=inputs.official_bundle, configuration_sha256=sha(inputs.configuration), game_sha256=sha(inputs.game), profile=profile.name, saved_mode=profile.mode_name, same_save_database_proven=False, gameplay_script_selection_proven=False, eligible_for_training=False)
    phase_started = time.perf_counter()
    backend.initialize_fresh()
    emit('native_reset_timing', phase='initialize_fresh_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='non-overlapping stage', strategic_training_ready=False)
    phase_started = time.perf_counter()
    receipt = backend.restore_b(inputs)
    emit('native_reset_timing', phase='restore_configuration_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='non-overlapping stage', strategic_training_ready=False)
    emit('official_configuration_restored', **receipt)
    phase_started = time.perf_counter()
    backend.prepare(required_ownership_mode=game_configuration_hash(profile.mode_name))
    backend.install_prefix(services=prepare_services(backend)) if candidate else backend.install_prefix()
    emit('native_reset_timing', phase='host_prepare_and_prefix_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='non-overlapping stage', strategic_training_ready=False)
    phase_started = time.perf_counter()
    topology = backend.copy_b_to_a()
    backend.create_reader(inputs)
    emit('native_reset_timing', phase='database_copy_and_reader_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='non-overlapping stage', strategic_training_ready=False)
    emit('before_official_gamecore_load', topology=topology, game_bytes=len(inputs.game))
    phase_started = time.perf_counter()
    before = backend.jobs_snapshot('before')
    status = backend.load_raw()
    after = backend.jobs_snapshot('after')
    emit('native_reset_timing', phase='raw_gamecore_load_and_job_snapshots_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='non-overlapping stage', strategic_training_ready=False)
    emit('official_gamecore_load_returned', status=status, jobs_before=before, jobs_after=after, bytes_consumed=backend.reader.transport.cursor, validation_completed=False, eligible_for_training=False)
    phase_started = time.perf_counter()
    result = backend.validate_load_return(status, inputs, before, after)
    backend.invalidate_reader()
    readback = backend.read_loaded_diagnostic()
    emit('native_reset_timing', phase='load_validation_and_readback_seconds', elapsed_seconds=time.perf_counter() - phase_started, timing_scope='non-overlapping stage', strategic_training_ready=False)
    backend.busy = False
    emit('official_gamecore_load_observed', result=result, readback=readback, postload_completed=False, normal_destroy_validated=False, same_save_database_proven=False, full_restore_proven=False, controlled_process_stop_required=True, strategic_training_ready=False)
    return result
from civ6_host.runtime.capture_profiles import LAN_PROFILE

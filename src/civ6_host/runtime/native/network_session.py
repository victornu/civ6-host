"""Bounded native owner for explicitly selected captured LAN sessions.

Supervision, process limits, closure pinning, and cleanup remain in the shared
NativeSavedSession/NativeActionSession implementation. This adapter only
connects the LAN actor protocol to those existing lifecycle hooks.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

from civ6_host.runtime.network_protocol import CLOSURE_SCHEMA, NetworkProtocol, SCHEMA
from civ6_host.runtime.network_protocol import validate_network_response
from civ6_host.runtime.network_protocol import _player_id
from civ6_host.runtime.native.native_action_session import NativeActionSession
from civ6_host.contracts.action_budget import LAN_EVENT_LINE_BYTES
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256


def xp1_loaded_close_evidence(run, report, pins, *, core_sha256=XP1_CORE_SHA256, official_bundle=None):
    """Read-only receipt authentication for one already reaped expansion session.

    This does not rerun the engine, rewrite retained supervisors or replace the
    separate full native job-ledger qualification with an exit-code inference.
    """
    from civ6_host.runtime.xp1_loaded_lifetime import SOURCE, validate_jobs_shutdown
    from civ6_host.runtime.captured_session_profile import select
    candidate=select(core_sha256, official_bundle=official_bundle).candidate
    REFERENCE=candidate.reference
    engine = 'xp2' if core_sha256 == XP2_CORE_SHA256 else 'xp1'
    unload_rva='0x4be690'
    if core_sha256==XP2_CORE_SHA256:
        from civ6_host.runtime.xp2_loaded_lifetime_source import SOURCE, source
        unload_rva=hex(source()['contract']['unload_target_rva'])
    from civ6_host.runtime.paths import resource_root
    from civ6_host.runtime.resource_resolution import recorded_path, resolve_path
    run = Path(run).resolve()
    if (report.get('exit_code') != 90 or report.get('reaped') is not True
            or report.get('job_assigned') is not True or report.get('error') is not None
            or report.get('stop_reason') is not None or report.get('timed_out') is not False
            or not pins or set(report.get('source_unchanged', {})) != set(pins)
            or any(value is not True for value in report['source_unchanged'].values())):
        raise ValueError(f'{engine.upper()} loaded close lacks clean bounded supervision')
    closure_path = run/'closure.json'
    recorded_closure = recorded_path(closure_path)
    relocated = recorded_closure != closure_path
    raw_closure = closure_path.read_bytes()
    if not 0 < len(raw_closure) <= 4*1024*1024 or pins.get(str(recorded_closure)) != hashlib.sha256(raw_closure).hexdigest():
        raise ValueError(f'{engine.upper()} close closure differs from its parent pin')
    closure = json.loads(raw_closure)
    proof_path = resolve_path(resource_root()/SOURCE[0]).resolve()
    proof_path = str(recorded_path(proof_path) if relocated else proof_path)
    if (closure.get('input_profile') != candidate.family or closure.get('schema') != CLOSURE_SCHEMA
            or closure.get('official_bundle') != dict(path=REFERENCE[0], sha256=REFERENCE[1])
            or closure.get('close_loaded_candidate') is not True
            or closure.get('pins', {}).get(proof_path) != SOURCE[1]
            or pins.get(proof_path) != SOURCE[1]):
        raise ValueError(f'{engine.upper()} close source/capture identity differs')
    # The shared session wrapper retains its historical XP1 marker names.
    # LoadedLifetime emits the selected engine's five native lifetime markers.
    lifetime_markers = ('before_{engine}_loaded_unload', '{engine}_loaded_unload_returned',
        'before_{engine}_loaded_destroy', '{engine}_loaded_destroy_returned',
        '{engine}_loaded_lifetime_closed')
    stages = ('before_xp1_saved_loaded_close',
        *(stage.format(engine=engine) for stage in lifetime_markers),
        'xp1_saved_loaded_close_returned', 'official_session_response',
        'official_session_controlled_stop')
    foreign_stages = {stage.format(engine='xp1' if engine == 'xp2' else 'xp2')
                      for stage in lifetime_markers}
    selected, total, count = [], 0, 0
    transcript_hash = hashlib.sha256()
    from civ6_host.runtime.stdout_transport_profiles import iter_records
    records=report.get('stdout_native_records',[])
    transcript = resolve_path(recorded_closure.with_name('events.jsonl'))
    with closing(iter_records(transcript,profile=closure.get('stdout_transport'),
        expected_records=records,byte_limit=closure['stdout_limit_bytes'])) as stream:
        for count,line,event in stream:
            total += len(line)
            transcript_hash.update(line)
            stage = event['stage']
            if stage in ('official_session_refused', 'unsupported_host_contract'):
                raise ValueError('Refused native session cannot claim a clean close')
            if stage in foreign_stages:
                raise ValueError('Loaded close contains another engine lifetime marker')
            if stage == 'official_session_response' and event.get('operation') != 'close':
                continue
            if stage in stages:
                if len(selected) >= len(stages) or stage != stages[len(selected)]:
                    raise ValueError(f'{engine.upper()} close markers are missing, repeated or out of order')
                selected.append((count, event))
    if len(selected) != len(stages) or selected[-1][0] != count:
        raise ValueError(f'{engine.upper()} close did not end with its authenticated controlled stop')
    events = {event['stage']: event for _, event in selected}
    for stage in stages[1:6]:
        if events[stage].get('source_sha256') != SOURCE[1]:
            raise ValueError(f'{engine.upper()} native lifetime marker has another source')
    unloaded, destroyed = events[stages[2]], events[stages[4]]
    if (events[stages[1]].get('target_rva') != unload_rva
            or any(unloaded.get(key) is not True for key in
                   ('game_object_null', 'cache_service_null', 'rules_manager_null', 'void_return_ignored'))
            or destroyed.get('void_return_ignored') is not True
            or destroyed.get('native_globals_detached') is not True
            or destroyed.get('context_storage_read_after_destroy') is not False):
        raise ValueError(f'{engine.upper()} unload/Destroy returns are incomplete')
    receipt = events['xp1_saved_loaded_close_returned'].get('receipt')
    recorded_target = recorded_closure.with_name('loaded-lifetime-result.json')
    target = resolve_path(recorded_target)
    if (type(receipt) is not dict or set(receipt) != {'path', 'bytes', 'sha256'}
            or receipt['path'] != str(recorded_target) or type(receipt['bytes']) is not int
            or not 0 < receipt['bytes'] <= 1024*1024 or target.is_symlink()
            or target.resolve() != target):
        raise ValueError(f'{engine.upper()} close receipt is not its exact run-owned result')
    raw = target.read_bytes()
    if len(raw) != receipt['bytes'] or hashlib.sha256(raw).hexdigest() != receipt['sha256']:
        raise ValueError(f'{engine.upper()} close receipt bytes changed')
    result = json.loads(raw)
    if result != {key:value for key,value in events[stages[5]].items() if key != 'stage'}:
        raise ValueError(f'{engine.upper()} close receipt differs from the native lifetime return')
    steps = ['native_cache_wrappers_released', 'native_unload', 'native_destroy',
        'shared_services_closed', 'native_performance_map_destroyed', 'native_configuration_destroyed',
        'native_lua_closed', 'native_core_lock_closed', 'database_shutdown']
    ui_fields = {'ui_child_released', 'ui_child_release_order', 'ui_source_sha256', 'ui_source_pin_count'}
    if core_sha256 == XP1_CORE_SHA256 and ui_fields.intersection(result):
        from civ6_host.runtime.xp1_ui_binding import SOURCE as ui_source
        ui_proof = resolve_path(resource_root()/ui_source[0]).resolve()
        ui_proof = str(recorded_path(ui_proof) if relocated else ui_proof)
        if (result.get('ui_child_released') is not True
                or result.get('ui_child_release_order') != 'after_native_destroy_before_game_child_and_runtime_close'
                or result.get('ui_source_sha256') != ui_source[1]
                or pins.get(ui_proof) != ui_source[1]
                or type(result.get('ui_source_pin_count')) is not int
                or result['ui_source_pin_count'] < 1):
            raise ValueError('XP1 loaded close lacks its owned UI/game child release')
        steps[6:6] = ['saved_ui_child_released', 'game_child_released']
    if core_sha256==XP2_CORE_SHA256:
        steps[6:6]=['saved_ui_child_released','game_child_released']
        from civ6_host.runtime.xp2_action_transport_source import SOURCE as command_source
        if (result.get('raw_load_only') is not False or result.get('post160_called') is not True
                or result.get('postload_candidate_only') is not False
                or result.get('continuation_closed') is not True
                or result.get('command_transport_closed') is not True
                or result.get('command_source_sha256')!=command_source[1]
                or type(result.get('continuation_source_pin_count')) is not int
                or result['continuation_source_pin_count']<1
                or result.get('ui_child_released') is not True
                or result.get('ui_child_release_order')!='after_native_destroy_before_game_child_and_runtime_close'):
            raise ValueError('XP2 loaded close lacks its owned UI/game child release')
    performance = result.get('performance_closed')
    if (result.get('steps') != steps or result.get('source_sha256') != SOURCE[1]
            or any(result.get(key) is not True for key in ('native_unload_called',
                'native_destroy_called', 'context_destroyed', 'cache_wrappers_released',
                'services_closed', 'configuration_closed', 'lua_closed', 'core_lock_closed',
                'database_shutdown', 'unknown_host_callbacks_refused'))
            or result.get('cleanup_inferred_from_process_exit') is not False
            or result.get('public_loaded_lifetime_admitted') is not False
            or type(performance) is not dict
            or performance.get('native_destructor_returned') is not True
            or performance.get('guards_intact') is not True
            or performance.get('outer_storage_freed_by_native') is not False
            or 'event_recorder_closed' in result and result['event_recorder_closed'] is not True):
        raise ValueError(f'{engine.upper()} loaded teardown did not return all source-qualified steps')
    if (unloaded.get('jobs_unloaded') != result.get('jobs_unloaded')
            or unloaded.get('jobs_transition') != result.get('jobs_transition')
            or any(result[key]['core_identity']['sha256'] != core_sha256
            for key in ('jobs_before', 'jobs_unloaded'))
            or validate_jobs_shutdown(result['jobs_before'], result['jobs_unloaded']) != result['jobs_transition']):
        raise ValueError(f'{engine.upper()} close snapshots differ from their native lifetime receipt')
    response = events['official_session_response']
    if (response.get('schema') != SCHEMA or response.get('nonce') != closure.get('nonce')
            or response.get('episode_id') != report.get('episode_id')
            or response.get('sequence') != report.get('last_sequence')
            or response.get('game_generation') != 'native-'+report['episode_id']
            or events['official_session_controlled_stop'].get('normal_destroy_called') is not True):
        raise ValueError(f'{engine.upper()} close response/stop belongs to another session boundary')
    return dict(schema=('civ6-host.xp1-loaded-close-evidence.v1' if core_sha256==XP1_CORE_SHA256
                       else 'civ6-host.xp2-loaded-close-evidence.v1'), receipt=receipt,
        source_sha256=SOURCE[1], transcript_sha256=transcript_hash.hexdigest(),
        transcript_bytes=total, ordered_marker_lines=[line for line, _ in selected],
        stdout_transport=closure.get('stdout_transport'),stdout_native_records=copy.deepcopy(records),
        native_unload_and_destroy_returned=True, native_calls_during_verification=False,
        full_job_ledger_requalified=False, cleanup_inferred_from_process_exit=False)


class NativeNetworkSession(NativeActionSession):
    event_line_limit_bytes = LAN_EVENT_LINE_BYTES
    input_profile = 'lan'
    worker_name = 'network_worker.py'
    closure_schema = CLOSURE_SCHEMA
    protocol_class = NetworkProtocol
    response_validator = staticmethod(validate_network_response)
    command_schema = SCHEMA

    def __init__(self, run_root=None, *, official_bundle=None, round_limit=8,
                 lifetime_seconds=45, stdout_limit_mib=64, checkpoint=None,
                 checkpoint_on_close=False, privileged_critic_diagnostic=False,
                 foundation_legality_diagnostic=False,
                 governors_diagnostic=False,
                 diplomacy_overview_diagnostic=False,
                 trade_diagnostic=False,
                 standard_trade=False, unit_formations=False, stock_dedications=False,
                 espionage_diagnostic=False,
                 world_congress_diagnostic=False,
                 world_congress_review_diagnostic=False,
                 ui_profile=None, episode_budget=None, _admitted_bundle=None,
                 forced_endturn_diagnostic=False, production_queue_diagnostic=False,
                 city_focus_diagnostic=False, city_management_diagnostic=False,
                 multiturn_movement_diagnostic=False, movement_information_diagnostic=False,
                 unit_order_cancel_diagnostic=False, movement_ui_probe=None,
                 world_input_diagnostic=False, input_profile='lan',
                 prepared_capture=None, public_display_diagnostic=False,
                 public_display_source=None, war_source_sha256=None,
                 execution_image_profile=None, checkpoint_compatibility=None,
                 command_profile_diagnostic=False, **options):
        if type(input_profile) is not str or input_profile not in ('lan', 'xp1-lan', 'xp2-lan'):
            raise ValueError('Unknown captured network input profile')
        self.execution_image = None
        if execution_image_profile is not None:
            if input_profile not in ('xp1-lan', 'xp2-lan') or type(execution_image_profile) is not str:
                raise ValueError('An execution image requires an explicit expansion profile name')
            from civ6_host.runtime.execution_images import _XP1_PROFILE, known_path, select
            self.execution_image = select(execution_image_profile,
                core_path=known_path(execution_image_profile))
            if (self.execution_image is _XP1_PROFILE) != (input_profile == 'xp1-lan'):
                raise ValueError('Selected execution image differs from its expansion family')
            if self.execution_image is _XP1_PROFILE and (
                    city_focus_diagnostic is not False or city_management_diagnostic is not False):
                raise ValueError('Installed XP1 session has no city-control admission yet')
        if (type(command_profile_diagnostic) is not bool
                or command_profile_diagnostic and (
                    input_profile != 'xp2-lan' or self.execution_image is None)):
            raise ValueError('Command profiling requires an explicit XP2 execution image')
        self.command_profile_diagnostic = command_profile_diagnostic
        if checkpoint_compatibility is not None:
            from civ6_host.runtime.network_checkpoint import (
                REFERENCE_CHECKPOINT_COMPATIBILITY, XP1_COMBAT_CHECKPOINT_COMPATIBILITY)
            expected_compatibility = (XP1_COMBAT_CHECKPOINT_COMPATIBILITY if input_profile == 'xp1-lan'
                                      else REFERENCE_CHECKPOINT_COMPATIBILITY)
            if (checkpoint_compatibility != expected_compatibility
                    or self.execution_image is None or checkpoint is None):
                raise ValueError('Checkpoint compatibility requires an explicit image and checkpoint')
        self.checkpoint_compatibility = checkpoint_compatibility
        from civ6_host.runtime.xp2_world_war import source_pin
        self.war_source_sha256 = source_pin(war_source_sha256, input_profile)
        if (type(public_display_diagnostic) is not bool
                or (public_display_diagnostic and input_profile != 'xp2-lan')):
            raise ValueError('Public display requires the explicit XP2 diagnostic')
        self.public_display_diagnostic = public_display_diagnostic
        if public_display_source is not None and not public_display_diagnostic:
            raise ValueError('A display source requires the explicit public display capability')
        if public_display_diagnostic:
            from civ6_host.runtime.player_display_toppanel import selected_source
            self.public_display_source = selected_source(public_display_source)
        else:
            self.public_display_source = None
        self.input_profile = input_profile
        self.prepared_capture = None
        if input_profile in ('xp1-lan','xp2-lan'):
            if (_admitted_bundle is not None
                    or any((production_queue_diagnostic, multiturn_movement_diagnostic,
                            movement_information_diagnostic, unit_order_cancel_diagnostic,
                            world_input_diagnostic))):
                raise ValueError('XP1 session cannot inherit Base diagnostic admission')
            from civ6_host.runtime.session_limits import standard_lifetime_limit
            if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= standard_lifetime_limit(input_profile):
                raise ValueError('Expansion session exceeds its bounded diagnostic lifecycle')
            from civ6_host.runtime.capture_admission import _reference
            self.prepared_capture = _reference(prepared_capture)
        elif prepared_capture is not None:
            raise ValueError('Explicit prepared_capture on this adapter requires the XP1 profile')
        if official_bundle is None:
            raise ValueError('LAN session requires its exact official capture bundle')
        if type(checkpoint_on_close) is not bool or type(privileged_critic_diagnostic) is not bool:
            raise ValueError('LAN administrative options require exact Boolean values')
        if type(forced_endturn_diagnostic) is not bool:
            raise ValueError('LAN forced-EndTurn option requires an exact Boolean value')
        if privileged_critic_diagnostic and input_profile != 'xp2-lan':
            raise ValueError('The LAN critic diagnostic requires the exact BBG XP2 capture')
        if (type(foundation_legality_diagnostic) is not bool
                or (foundation_legality_diagnostic and input_profile != 'xp2-lan')):
            raise ValueError('Foundation legality requires the explicit XP2 diagnostic')
        if (type(governors_diagnostic) is not bool
                or (governors_diagnostic and input_profile != 'xp2-lan')):
            raise ValueError('Governors require the explicit XP2 diagnostic')
        if (type(diplomacy_overview_diagnostic) is not bool
                or diplomacy_overview_diagnostic and (
                    input_profile != 'xp2-lan' or not governors_diagnostic
                    or self.execution_image is None or self.war_source_sha256 is None)):
            raise ValueError('Initial diplomacy requires current XP2, its receiver and the complete v32 query group')
        if type(trade_diagnostic) is not bool or trade_diagnostic and not diplomacy_overview_diagnostic:
            raise ValueError('Trade requires the complete current XP2 diplomacy query group')
        if (type(standard_trade) is not bool or standard_trade and (
                input_profile != 'xp2-lan' or self.execution_image is None
                or trade_diagnostic or governors_diagnostic or foundation_legality_diagnostic)):
            raise ValueError('Standard trade requires the current stock Gathering Storm session')
        if type(unit_formations) is not bool or unit_formations and not standard_trade:
            raise ValueError('Unit formations require the exact stock Gathering Storm session')
        if type(stock_dedications) is not bool or stock_dedications and not unit_formations:
            raise ValueError('Dedications require the exact stock Gathering Storm v2 capability')
        if type(espionage_diagnostic) is not bool or espionage_diagnostic and not trade_diagnostic:
            raise ValueError('Espionage requires the complete current XP2 trade query group')
        if (type(world_congress_diagnostic) is not bool or world_congress_diagnostic and not (
                espionage_diagnostic or stock_dedications and world_congress_review_diagnostic is True)):
            raise ValueError('World Congress requires the complete XP2 BBG or stock review group')
        if (type(world_congress_review_diagnostic) is not bool
                or world_congress_review_diagnostic and not world_congress_diagnostic):
            raise ValueError('Congress review requires the explicit current XP2 Congress group')
        if ui_profile is not None:
            raise ValueError('LAN sessions do not accept a Hotseat UI profile')
        if episode_budget is not None:
            raise ValueError('LAN sessions use their bounded lifecycle, not a learning budget')
        if forced_endturn_diagnostic:
            raise ValueError('LAN forced turns require captured UI gates, not a diagnostic bypass')
        from civ6_host.runtime.session_limits import standard_lifetime_limit
        if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= standard_lifetime_limit(input_profile):
            raise ValueError('LAN session exceeds its bounded profile lifecycle')
        from civ6_host.runtime.native.native_saved_session import MAX_STANDARD_STDOUT
        if (type(stdout_limit_mib) is not int
                or not 1 <= stdout_limit_mib <= MAX_STANDARD_STDOUT // (1024 * 1024)):
            raise ValueError('LAN stdout budget exceeds the shared bounded supervisor limit')
        if movement_ui_probe is not None:
            raise ValueError('LAN sessions do not accept Single-profile UI instrumentation')
        diagnostic_flags = (production_queue_diagnostic, city_focus_diagnostic,
            city_management_diagnostic, multiturn_movement_diagnostic,
            movement_information_diagnostic, unit_order_cancel_diagnostic,
            world_input_diagnostic)
        if any(type(flag) is not bool for flag in diagnostic_flags):
            raise ValueError('LAN diagnostic overrides require exact Boolean flags')
        if city_management_diagnostic and not city_focus_diagnostic:
            raise ValueError('LAN city management requires its complete city-focus group')
        from civ6_host.runtime.native.native_saved_session import ROOT
        super().__init__(run_root or ROOT / 'work/host-simultaneous/native-runs',
            round_limit=round_limit, lifetime_seconds=lifetime_seconds,
            stdout_limit_mib=stdout_limit_mib, checkpoint_on_close=False,
            checkpoint=None, forced_endturn_diagnostic=False,
            production_queue_diagnostic=False, privileged_critic_diagnostic=False,
            city_focus_diagnostic=False, city_management_diagnostic=False,
            multiturn_movement_diagnostic=False, movement_information_diagnostic=False,
            unit_order_cancel_diagnostic=False, movement_ui_probe=None,
            world_input_diagnostic=False, ui_profile=None,
            official_bundle=official_bundle, episode_budget=None,
            _admitted_bundle=_admitted_bundle, **options)
        # These same explicit diagnostic switches are consumed by the LAN
        # worker and the inherited closure/proof pinning code. Force EndTurn,
        # critic and Hotseat UI admission remain unavailable. Checkpoints use
        # their separate administrative provenance/boundary below.
        self.production_queue_diagnostic = production_queue_diagnostic
        self.city_focus_diagnostic = city_focus_diagnostic
        self.city_management_diagnostic = city_management_diagnostic
        self.multiturn_movement_diagnostic = multiturn_movement_diagnostic
        self.movement_information_diagnostic = movement_information_diagnostic
        self.unit_order_cancel_diagnostic = unit_order_cancel_diagnostic
        self.world_input_diagnostic = world_input_diagnostic
        self.privileged_critic_diagnostic = privileged_critic_diagnostic
        self.foundation_legality_diagnostic = foundation_legality_diagnostic
        self.governors_diagnostic = governors_diagnostic
        self.diplomacy_overview_diagnostic = diplomacy_overview_diagnostic
        self.trade_diagnostic = trade_diagnostic
        self.standard_trade = standard_trade
        self.unit_formations = unit_formations
        self.stock_dedications = stock_dedications
        self.espionage_diagnostic = espionage_diagnostic
        self.world_congress_diagnostic = world_congress_diagnostic
        self.world_congress_review_diagnostic = world_congress_review_diagnostic
        from civ6_host.runtime.network_checkpoint import normalize, manifest, verify_resume_head
        self.network_checkpoint_ref = normalize(checkpoint) if checkpoint is not None else None
        self.checkpoint_on_close = checkpoint_on_close
        self._last_actor_id = None
        if input_profile in ('xp1-lan','xp2-lan'):
            from civ6_host.runtime.captured_session_profile import for_family
            candidate = for_family(input_profile, official_bundle=self.official_bundle).candidate
            if self.official_bundle != candidate.reference:
                raise ValueError('Expansion session requires its exact retained official capture')
            if standard_trade:
                from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
                if candidate.reference != REFERENCE:
                    raise ValueError('Standard trade requires its exact stock capture')
            from civ6_host.runtime import xp2_bbg_inputs as bbg
            if privileged_critic_diagnostic and candidate.reference != bbg.REFERENCE:
                raise ValueError('The LAN critic diagnostic requires the exact BBG XP2 capture')
            if foundation_legality_diagnostic or governors_diagnostic:
                from civ6_host.runtime.captured_session_profile import require_bbg_capture
                require_bbg_capture(candidate.reference, execution_image=self.execution_image)
            if candidate.reference == bbg.REFERENCE and self.prepared_capture != bbg.prepared_reference():
                raise ValueError('BBG session requires its exact local recovered handoff')
            if self.network_checkpoint_ref is not None:
                verify_resume_head(self.network_checkpoint_ref, official_bundle=self.official_bundle,
                    core_sha256=candidate.core_sha256,
                    **({'execution_image': self.execution_image,
                        'checkpoint_compatibility': self.checkpoint_compatibility}
                       if self.execution_image is not None else {}))
        elif self.network_checkpoint_ref is not None:
            manifest(self.network_checkpoint_ref, official_bundle=self.official_bundle)

    def _initial_protocol(self, identity, closure):
        if self.input_profile in ('xp1-lan','xp2-lan'):
            from civ6_host.runtime.captured_session_profile import for_family
            candidate = for_family(self.input_profile, official_bundle=self.official_bundle).candidate
            return NetworkProtocol(identity, self.nonce, round_limit=closure['rounds'],
                initial_turn=closure['initial_turn'],core_sha256=candidate.core_sha256,
                war_source_sha256=closure.get('war_source_sha256'))
        return self.protocol_class(identity, self.nonce, round_limit=closure['rounds'])

    @contextmanager
    def _xp1_preparation(self):
        """Retain only supervised runs as reset ancestry after a parent failure."""
        missing = object()
        names = ('run', 'pins', 'nonce', 'stdout_identity', 'win', 'initial_turn',
                 'reset_timings_seconds', 'reset_resource_samples', 'reset_started')
        previous = {name: getattr(self, name, missing) for name in names}
        self._xp1_preparation_run = None
        self._xp1_preparation_phase = 'preflight'
        try:
            yield
        except BaseException as exc:
            failed_run = self._xp1_preparation_run
            failure = dict(schema='civ6-host.xp1-parent-preparation-failure.v1',
                phase=self._xp1_preparation_phase, error=repr(exc),
                run_directory=str(failed_run) if failed_run is not None else None,
                previous_supervised_run=None if previous['run'] is missing else str(previous['run']),
                native_process_started=False, supervisor_report_created=False,
                reset_timings_seconds=copy.deepcopy(self.reset_timings_seconds))
            try:
                if failed_run is not None:
                    from civ6_host.runtime.xp1_session_inputs import _write_once
                    failure['receipt'] = _write_once(failed_run/'parent-preparation-failure.json', failure)
            except OSError as recording_error:
                failure['recording_error'] = repr(recording_error)
            finally:
                for name, value in previous.items():
                    if value is missing:
                        if hasattr(self, name):
                            delattr(self, name)
                    else:
                        setattr(self, name, value)
                self.last_preparation_failure = failure
            raise
        finally:
            del self._xp1_preparation_run
            del self._xp1_preparation_phase

    def reset(self):
        if self.input_profile not in ('xp1-lan','xp2-lan'):
            return super().reset()
        self.last_native_turn_reactivation = None
        reset_started = time.perf_counter()
        self._owner()
        from civ6_host.runtime.native.native_saved_session import ROOT, sha
        previous = getattr(self, 'run', None)
        if not self.finished:
            self.close_context = 'reset'
            self.close()
        replaces = None
        if previous is not None:
            if not self.report['reaped']:
                raise RuntimeError('Previous native process was not reaped')
            replaces = dict(run=previous.relative_to(ROOT).as_posix(),
                supervisor_sha256=sha(previous/'supervisor.json'),
                episode_id=self.report['episode_id'], previous_pid=self.report['pid'],
                previous_reaped=True)
        from civ6_host.runtime.native.native_probe import Windows
        from civ6_host.runtime.capture_candidates import consume_input_handoff
        from civ6_host.runtime.captured_session_profile import for_family
        selected=for_family(self.input_profile, official_bundle=self.official_bundle)
        from civ6_host.runtime.xp1_session_inputs import (
            prepare_sources, prepare_private_fixture, saved_load_pin,
            SAVED_LOAD_CLOSURE_ENV)
        from civ6_host.runtime.native.native_official_bundle import DATABASE_PROFILE, LOCALIZATION_HANDOFF_ENV
        from civ6_host.runtime.capture_admission import ENV as PREPARED_ENV
        from civ6_host.runtime.provenance import worker_path, verify_installation
        with self._xp1_preparation():
            self.reset_timings_seconds, self.reset_resource_samples = {}, []
            self.reset_started = reset_started
            self.win = Windows()
            self._check_reset_resources('before_preflight')
            phase_started = time.perf_counter()
            try:
                verify_installation()
                package = copy.deepcopy(self.prepared_capture)
                execution_options = ({'execution_image': self.execution_image}
                                     if self.execution_image is not None else {})
                captured = consume_input_handoff(self.input_profile, package,
                    official_bundle=self.official_bundle, **execution_options)
                if captured.reference != selected.candidate.reference or self.official_bundle != captured.reference:
                    raise ValueError('XP1 prepared inputs differ from the requested official capture')
                self._set_bundle_initial_turn(captured.initial_turn)
                self.pins, executable = prepare_sources(captured, package, postload160=True,
                    publish_cache=True, close_loaded=True, observe_player=True, unit_commands=True,
                    core_sha256=selected.candidate.core_sha256)
                if self.input_profile == 'xp2-lan':
                    from civ6_host.runtime.xp2_end_turn_readback import SOURCE
                    saved_load_pin(self.pins, ROOT / SOURCE[0], SOURCE[1])
                self.stdout_identity = dict(core_sha256=selected.candidate.core_sha256, host_sha256=sha(executable))
                from civ6_host.runtime.stdout_transport_profiles import verify_selected
                from civ6_host.runtime.native import native_stdout_transport
                verify_selected(**self.stdout_identity,base_verify=native_stdout_transport.verify_source)
                self._check_reset_resources('after_preflight')
            finally:
                self.reset_timings_seconds['parent_preflight_seconds'] = time.perf_counter()-phase_started
            self.run = self.run_root/('run-'+uuid.uuid4().hex)
            self.run.mkdir(parents=True, exist_ok=False)
            self._xp1_preparation_run = self.run
            self._xp1_preparation_phase = 'private_fixture'
            phase_started = time.perf_counter()
            fixture, isolation = prepare_private_fixture(self.run, captured, self.pins)
            self.reset_timings_seconds['fixture_prepare_total_seconds'] = time.perf_counter()-phase_started
            self.reset_timings_seconds['fixture_prepare_subphases_seconds'] = isolation.get('timings_seconds', {})
            self._xp1_preparation_phase = 'closure'
            phase_started = time.perf_counter()
            self.nonce = uuid.uuid4().hex
            closure = dict(schema=self.closure_schema, pins=self.pins, nonce=self.nonce,
                fixture=str(fixture), fixture_isolation=isolation, input_profile=self.input_profile,
                rounds=self.round_limit, native_controller=True, experimental_fresh_controller=False,
                database_profile=DATABASE_PROFILE,
                official_bundle=dict(path=captured.reference[0], sha256=captured.reference[1]),
                initial_turn=captured.initial_turn, prepared_capture=package, replaces=replaces,
                raw_only_candidate=True, post160_candidate=True, publish_cache_candidate=True,
                close_loaded_candidate=True, observe_player_candidate=True, unit_commands_candidate=True,
                checkpoint_on_close=self.checkpoint_on_close, lifetime_seconds=self.lifetime_seconds,
                stdout_limit_bytes=self.stdout_limit_bytes,
                stdout_transport=dict(schema=native_stdout_transport.SCHEMA,
                    source_sha256=verify_selected(**self.stdout_identity,base_verify=native_stdout_transport.verify_source),
                    **self.stdout_identity))
            worker = worker_path(self.worker_name)
            self._write_private_closure(closure, captured=captured)
            self._set_bundle_initial_turn(closure['initial_turn'])
            # The child authenticates the complete immutable closure; the supervisor
            # pins it after writing, outside its own recursive source map.
            self.pins = dict(self.pins)
            saved_load_pin(self.pins, self.run/'closure.json')
            self.reset_timings_seconds['closure_pin_and_write_seconds'] = time.perf_counter()-phase_started
            env = os.environ.copy()
            env.pop('PYTHONPATH', None)
            env.pop(LOCALIZATION_HANDOFF_ENV, None)
            env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', CIV6RL_PYTHON_HOME=sys.base_prefix)
            env.update({PREPARED_ENV: json.dumps(package, sort_keys=True),
                        SAVED_LOAD_CLOSURE_ENV: self.pins[str((self.run/'closure.json').resolve())]})
            env['PATH'] = sys.base_prefix+os.pathsep+env.get('PATH', '')
        self.runs.append(self.run)
        from civ6_host.runtime.session_launch import launch
        return launch(self, executable, worker, closure, env, captured, reset_started)

    def _commit_response(self, request, response):
        self.protocol.commit_reply(request, response)

    def _finish(self):
        already_finished = self.finished
        result = super()._finish()
        if self.input_profile not in ('xp1-lan','xp2-lan') or already_finished:
            return result
        report = self.report
        if (report.get('exit_code') != 90 or report.get('reaped') is not True
                or report.get('error') is not None or report.get('stop_reason') is not None):
            return result
        try:
            from civ6_host.runtime.captured_session_profile import for_family
            candidate = for_family(self.input_profile, official_bundle=self.official_bundle).candidate
            evidence = xp1_loaded_close_evidence(self.run, report, self.pins,
                core_sha256=candidate.core_sha256, official_bundle=self.official_bundle)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # A clean process exit is insufficient. Make a missing/corrupted
            # receipt visible to the shared request(close) result check.
            self.error = repr(exc)
            self.stop_reason = self.input_profile.removesuffix('-lan')+'_loaded_close_unverified'
            report.update(error=self.error, stop_reason=self.stop_reason,
                          normal_destroy_called=False)
        else:
            report.update(normal_destroy_called=True, native_lifetime=evidence)
        from civ6_host.runtime.native.native_saved_session import write_json
        write_json(self.run/'supervisor.json', report)
        return result

    def _accepted_response(self, response):
        super()._accepted_response(response)
        self.protocol.accept_response(response)
        observation = response.get('observation')
        if observation is not None:
            self._last_actor_id = observation['player_id']
        elif response.get('outcome', {}).get('terminated') is True:
            # The protocol already bound this result to the requested actor.
            # A terminal reply can have no board and still change perspective.
            self._last_actor_id = response['outcome']['native_victory']['player_id']

    def _cancel_offer_admitted(self):
        if self.unit_order_cancel_diagnostic:
            return True
        if self.input_profile in ('xp1-lan','xp2-lan'):
            from civ6_host.runtime.captured_session_profile import for_family
            REFERENCE=for_family(self.input_profile, official_bundle=self.official_bundle).candidate.reference
            if self.input_profile=='xp2-lan':
                from civ6_host.runtime.xp2_unit_orders_source import SOURCE, TRANSPORT_SOURCE, UI_SOURCE
            else:
                from civ6_host.runtime.xp1_unit_orders_profile import SOURCE, TRANSPORT_SOURCE, UI_SOURCE
            receipt = getattr(self, '_xp1_unit_order_source_admission', None)
            if (self.official_bundle != REFERENCE or receipt != dict(
                    official_bundle=self.official_bundle,
                    source_sha256=(SOURCE[1], TRANSPORT_SOURCE[1], UI_SOURCE[1]))):
                raise ValueError('Parent expansion unit-order admission lacks its exact bundle and sources')
            return True
        receipt = getattr(self, '_lan_map_source_admission', None)
        if receipt is None:
            return False
        from civ6_host.runtime.network_ui import MAP_SOURCES
        if (self.input_profile != 'lan'
                or receipt['official_bundle'] != self.official_bundle
                or receipt['source_sha256'] != tuple(row[1] for row in MAP_SOURCES)):
            raise ValueError('Parent LAN action admission belongs to another bundle or source')
        return True

    def _configure_closure(self, closure):
        compatibility = getattr(self, 'checkpoint_compatibility', None)
        if compatibility is not None:
            closure['checkpoint_compatibility'] = compatibility
        if self.input_profile in ('xp1-lan','xp2-lan'):
            from importlib import import_module
            from civ6_host.runtime.xp1_session_inputs import saved_load_pin
            from civ6_host.runtime.captured_session_profile import for_family
            selected=for_family(self.input_profile, official_bundle=self.official_bundle)
            image = getattr(self, 'execution_image', None)
            execution_options = {'execution_image': image} if image is not None else {}
            # No Base catalogue/provider admission. These authored adapters and
            # their private source evidence supplement the shared native phases.
            saved_load_pin(closure['pins'], Path(__file__))
            if self.command_profile_diagnostic:
                from civ6_host.runtime import command_profiling
                closure['command_profile_diagnostic'] = True
                saved_load_pin(closure['pins'], Path(command_profiling.__file__))
            if self.privileged_critic_diagnostic:
                from civ6_host.runtime import xp2_bbg_critic
                closure['privileged_critic_diagnostic'] = True
                for path in xp2_bbg_critic.source_files():
                    saved_load_pin(closure['pins'], path)
            if self.foundation_legality_diagnostic:
                from civ6_host.runtime.xp2_foundation_legality import pin_sources
                pin_sources(closure['pins'], **execution_options)
                closure['foundation_legality_diagnostic'] = True
            for name in ('workers.network_worker', 'xp1_session_view', 'xp1_session_result',
                         'xp1_status_profiles', 'xp1_session_admission'):
                module = import_module('civ6_host.runtime.'+name)
                saved_load_pin(closure['pins'], Path(module.__file__))
                if name != 'workers.network_worker':
                    dependencies=(module.source_dependencies(**execution_options) if name=='xp1_session_admission'
                        else module.source_dependencies(core_sha256=selected.candidate.core_sha256,
                                                        **execution_options))
                    for path, expected in dependencies.items():
                        saved_load_pin(closure['pins'], path, expected)
            if self.city_focus_diagnostic or self.city_management_diagnostic:
                from civ6_host.runtime.expansion_city_controls import requested
                from civ6_host.runtime.expansion_city_controls_profile import source_dependencies as city_dependencies
                closure.update(city_focus_diagnostic=self.city_focus_diagnostic,
                    city_management_diagnostic=self.city_management_diagnostic)
                requested(closure)
                for path,expected in city_dependencies(selected.candidate.core_sha256,
                        official_bundle=self.official_bundle,**execution_options).items():
                    saved_load_pin(closure['pins'],path,expected)
            if self.input_profile=='xp2-lan':
                from civ6_host.runtime.source_build_identity import CURRENT_STRINGS_BUILD_PROFILE
                if image is not None and image.native_host_build.profile_id == CURRENT_STRINGS_BUILD_PROFILE:
                    from civ6_host.runtime import script_event_strings
                    saved_load_pin(closure['pins'], Path(script_event_strings.__file__))
                    for path, digest in script_event_strings.source_dependencies(execution_image=image).items():
                        saved_load_pin(closure['pins'], path, digest)
                if self.war_source_sha256 is not None:
                    from civ6_host.runtime import xp2_world_war_display
                    closure['war_source_sha256'] = self.war_source_sha256
                    for path, expected in xp2_world_war_display.source_dependencies(**execution_options).items():
                        saved_load_pin(closure['pins'], Path(path), expected)
                if self.governors_diagnostic:
                    from civ6_host.runtime import xp2_governors
                    closure['governors_diagnostic'] = True
                    for path, expected in xp2_governors.source_dependencies(
                            execution_image=self.execution_image).items():
                        saved_load_pin(closure['pins'], path, expected)
                if getattr(self, 'diplomacy_overview_diagnostic', False):
                    from civ6_host.runtime.xp2_diplomacy_overview import source_dependencies
                    closure['diplomacy_overview_diagnostic'] = True
                    for path, digest in source_dependencies(execution_image=self.execution_image).items():
                        saved_load_pin(closure['pins'], path, digest)
                if getattr(self, 'trade_diagnostic', False):
                    from civ6_host.runtime import xp2_bbg_trade_feedback, xp2_trade
                    closure['trade_diagnostic'] = True
                    for module in (xp2_trade, xp2_bbg_trade_feedback):
                        for path, digest in module.source_dependencies(execution_image=self.execution_image).items():
                            saved_load_pin(closure['pins'], path, digest)
                if getattr(self, 'standard_trade', False):
                    from civ6_host.runtime import xp2_trade
                    closure['standard_trade'] = True
                    dependencies = xp2_trade.standard_source_dependencies(selected.candidate.reference,
                        core_sha256=selected.candidate.core_sha256, execution_image=image)
                    for path, digest in dependencies.items():
                        saved_load_pin(closure['pins'], path, digest)
                if getattr(self, 'unit_formations', False):
                    from civ6_host.runtime import xp2_unit_formations
                    closure['unit_formations'] = True
                    for path, digest in xp2_unit_formations.source_dependencies(selected.candidate.reference, image).items():
                        saved_load_pin(closure['pins'], path, digest)
                if getattr(self, 'stock_dedications', False):
                    from civ6_host.runtime import xp2_dedications
                    closure['stock_dedications'] = True
                    dependencies = xp2_dedications.source_dependencies(
                        selected.candidate.reference, execution_image=image)
                    for path, digest in dependencies.items():
                        saved_load_pin(closure['pins'], path, digest)
                if getattr(self, 'espionage_diagnostic', False):
                    from civ6_host.runtime import xp2_espionage
                    closure['espionage_diagnostic'] = True
                    for path, digest in xp2_espionage.source_dependencies(
                            execution_image=self.execution_image).items():
                        saved_load_pin(closure['pins'], path, digest)
                if getattr(self, 'world_congress_diagnostic', False):
                    from civ6_host.runtime.xp2_world_congress_source import source_dependencies
                    closure['world_congress_diagnostic'] = True
                    for path, digest in source_dependencies(execution_image=self.execution_image).items():
                        saved_load_pin(closure['pins'], path, digest)
                review_requested = getattr(self, 'world_congress_review_diagnostic', False)
                if (type(review_requested) is not bool
                        or review_requested and getattr(self, 'world_congress_diagnostic', False) is not True):
                    raise ValueError('Congress review closure requires its exact Boolean parent group')
                if review_requested:
                    from civ6_host.runtime.xp2_world_congress_review import source_dependencies
                    closure['world_congress_review_diagnostic'] = True
                    for path, digest in source_dependencies(execution_image=self.execution_image).items():
                        saved_load_pin(closure['pins'], path, digest)
                    from civ6_host.runtime import xp2_trade_overview
                    reference = selected.candidate.reference
                    if xp2_trade_overview.supports(reference, image):
                        closure['trade_overview_ui_selected'] = True
                        for path, digest in xp2_trade_overview.source_dependencies(reference, image).items():
                            saved_load_pin(closure['pins'], path, digest)
                if closure.get('standard_trade') or (
                        closure.get('trade_diagnostic') and closure.get('trade_overview_ui_selected')):
                    from civ6_host.runtime import xp2_captured_city
                    stock = bool(closure.get('standard_trade')) and xp2_captured_city.supports_stock(
                        selected.candidate.reference, image)
                    if stock or closure.get('trade_diagnostic'):
                        for path, digest in xp2_captured_city.source_dependencies(
                                execution_image=image, stock=stock).items():
                            saved_load_pin(closure['pins'], path, digest)
                if self.public_display_diagnostic:
                    from civ6_host.runtime.player_display_toppanel import pin_display_closure
                    pin_display_closure(closure,self.public_display_source)
                if closure.get('resume_checkpoint') is not None:
                    raise ValueError('XP2 cannot inherit a historical Base checkpoint')
                from civ6_host.runtime.xp2_unit_orders_source import SOURCE, TRANSPORT_SOURCE, UI_SOURCE
                self._xp1_unit_order_source_admission=dict(official_bundle=self.official_bundle,
                    source_sha256=(SOURCE[1],TRANSPORT_SOURCE[1],UI_SOURCE[1]))
                if self.checkpoint_on_close or self.network_checkpoint_ref is not None:
                    from civ6_host.runtime.xp1_checkpoint_profile import source_dependencies
                    from civ6_host.runtime.network_checkpoint import configure_closure
                    for path,expected in source_dependencies(core_sha256=selected.candidate.core_sha256,
                                                            **execution_options).items():
                        saved_load_pin(closure['pins'],path,expected)
                    configure_closure(closure, self.network_checkpoint_ref, validate_fields=True,
                                      **execution_options)
                return
            # The XP1 family is now exposed through its source-qualified v5
            # catalogue, not an inherited Base diagnostic flag. The view's
            # dependency closure above pins each selected profile/UI source.
            from civ6_host.runtime.xp1_unit_orders_profile import SOURCE, TRANSPORT_SOURCE, UI_SOURCE
            self._xp1_unit_order_source_admission = dict(
                official_bundle=self.official_bundle,
                source_sha256=(SOURCE[1], TRANSPORT_SOURCE[1], UI_SOURCE[1]))
            from civ6_host.runtime.network_checkpoint import configure_closure
            if self.checkpoint_on_close or self.network_checkpoint_ref is not None:
                from civ6_host.runtime.xp1_checkpoint_profile import source_dependencies
                for path, expected in source_dependencies(**execution_options).items():
                    saved_load_pin(closure['pins'], path, expected)
            configure_closure(closure, self.network_checkpoint_ref, validate_fields=True,
                              **execution_options)
            return
        super()._configure_closure(closure)
        from civ6_host.runtime.network_ui import city_source_files, map_source_files
        closure['pins'].update(city_source_files())
        closure['pins'].update(map_source_files())
        from civ6_host.runtime.native import native_saved_city_focus1000 as focus
        from civ6_host.runtime.native import native_saved_citizens as citizens
        focus.verify_source()
        citizens.verify_source()
        closure['pins'][str(focus.ROOT / 'work/city-focus1000/source.json')] = focus.SOURCE_SHA
        closure['pins'][str(citizens.PROOF)] = citizens.SOURCE_SHA
        from civ6_host.runtime.native import native_plot_purchases as plots
        plots.verify_source()
        closure['pins'][str(plots.ROOT / plots.SOURCE_PATH)] = plots.SOURCE_SHA256
        from civ6_host.runtime.network_ui import MAP_SOURCES
        self._lan_map_source_admission = dict(official_bundle=self.official_bundle,
            source_sha256=tuple(row[1] for row in MAP_SOURCES))
        from civ6_host.runtime.network_checkpoint import configure_closure
        configure_closure(closure, self.network_checkpoint_ref)

    @property
    def saved_checkpoint(self):
        if not self.finished or not getattr(self, 'report', {}).get('reaped'):
            raise RuntimeError('LAN checkpoint is available only after supervised close')
        path = self.run / 'checkpoint' / 'checkpoint.json'
        if not path.is_file():
            return None
        from civ6_host.runtime.network_checkpoint import reference, manifest
        ref = reference(path)
        image=getattr(self,'execution_image',None)
        manifest(ref, official_bundle=self.official_bundle,
                 **({'execution_image':image} if image is not None else {}))
        return ref

    def command(self, operation, player_id=None):
        self._owner()
        if self.protocol is None or self.protocol.session is None:
            raise RuntimeError('Reset before issuing a LAN command')
        if operation == 'act':
            raise ValueError('Use act(player_id, candidate_id) for actor-specific choices')
        if player_id is None:
            player_id = self._last_actor_id
        if player_id is None:
            player_id = self.protocol.session['local_player_id']
        protocol = self.protocol
        request = dict(schema=self.command_schema, nonce=self.nonce,
            episode_id=protocol.identity.episode_id,
            game_generation=protocol.identity.game_generation,
            sequence=protocol.sequence + 1, operation=operation,
            player_id=player_id)
        return self.request(request)

    def act(self, player_id, candidate_id, *, assignments=None, decision_id=None):
        self._owner()
        if self.protocol is None:
            raise RuntimeError('Reset before choosing a LAN action')
        player_id = _player_id(player_id)
        catalogue = self.protocol.catalogues.get(player_id)
        if catalogue is None:
            raise RuntimeError('No current decision catalogue for this LAN actor')
        if decision_id is None:
            decision_id = catalogue['decision_id']
        selection = dict(decision_id=decision_id, candidate_id=candidate_id)
        if assignments is not None:
            selection['parameters'] = dict(assignments=copy.deepcopy(assignments))
        protocol = self.protocol
        return self.request(dict(schema=self.command_schema, nonce=self.nonce,
            episode_id=protocol.identity.episode_id,
            game_generation=protocol.identity.game_generation,
            sequence=protocol.sequence + 1, operation='act',
            player_id=player_id, selection=selection))

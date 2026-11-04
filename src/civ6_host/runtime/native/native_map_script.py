"""Explicitly partial headless Map Script diagnostic; never training eligible.

Unknown host methods abort; unknown Lua services raise. This prefix measures
the actual NewGame caller beyond script acquisition, with private databases.
It does not label partial bootstrap as the original complete EXE factory.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from pathlib import Path
from civ6_host.runtime.native.native_host import sha256
from civ6_host.runtime.native.native_havok import HAVOK_SHA256
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
PREVICTORY12_CHECKPOINT = 'save-config-pre-victory12'

def _movement_position_source(choice, effect):
    """Re-read the exact own unit and obtain its native plot ID after delivery."""
    pid, turn, uid = (choice['player_id'], choice['current_game_turn'], choice['unit_id'])
    x, y = (effect['x'], effect['y'])
    return f"local pid,turn,uid,expectedX,expectedY={pid},{turn},{uid},{x},{y}\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n       Game.GetCurrentGameTurn()==turn,'movement position perspective changed')\nlocal player=Players and Players[pid]\nassert(player and player:IsAlive()==true,'movement position player unavailable')\nlocal found=nil;local count=0\nfor _,unit in player:GetUnits():Members() do\n count=count+1;assert(count<=4096 and unit:GetOwner()==pid,'invalid own unit collection')\n if unit:GetID()==uid then assert(found==nil,'duplicate own unit ID');found=unit end\nend\nassert(found~=nil and found:GetX()==expectedX and found:GetY()==expectedY,\n       'movement position changed between native readbacks')\nlocal plot=Map.GetPlotIndex(expectedX,expectedY)\nassert(type(plot)=='number' and plot%1==0 and plot>=0 and plot<Map.GetPlotCount(),\n       'invalid observed movement plot')\nreturn string.format('%d,%d,%d,%d,%d,%d',pid,turn,uid,expectedX,expectedY,plot)\n".encode('ascii')

def _parse_movement_position(payload, choice, effect):
    from civ6_host.runtime.native.native_unit_movement import _parse_uint
    if type(payload) is not bytes or len(payload) > 128:
        raise ValueError('Invalid native movement position response')
    fields = payload.split(b',')
    if len(fields) != 6:
        raise ValueError('Malformed native movement position response')
    actual = tuple((_parse_uint(value, label) for value, label in zip(fields, ('player ID', 'game turn', 'unit ID', 'observed x', 'observed y', 'observed plot'))))
    expected = (choice['player_id'], choice['current_game_turn'], choice['unit_id'], effect['x'], effect['y'])
    if actual[:5] != expected:
        raise ValueError('Native movement position identity differs')
    return actual[5]

def _validate_checkpoint_profile(diagnostic_checkpoint, diagnostic_rounds, diagnostic_action, diagnostic_production_policy, diagnostic_score_turn_limit, local_player_id=None):
    if diagnostic_checkpoint == PREVICTORY12_CHECKPOINT:
        if type(diagnostic_rounds) is not int or diagnostic_rounds != 16 or diagnostic_action != 'develop-round' or (diagnostic_production_policy != 'native-development') or (type(diagnostic_score_turn_limit) is not int) or (diagnostic_score_turn_limit != 12) or (type(local_player_id) is not int) or (local_player_id != 0):
            raise ValueError('Pre-victory12 checkpoint requires the exact native score-12 profile')
        return
    late = diagnostic_checkpoint == 'save-config-late114'
    if diagnostic_checkpoint not in ('baseline', 'save', 'save-config', 'save-config-late114') or diagnostic_rounds != (128 if late else 2) or diagnostic_action != 'develop-round' or (diagnostic_production_policy != 'native-development') or (diagnostic_score_turn_limit is not None):
        raise ValueError('Checkpoint requires its exact bounded development profile')

class NativeGameEventCallbacks:

    def check(self, this):
        if this != C.addressof(self.host.aux_object):
            raise ValueError('Foreign script-service receiver')

    def game_event_call(self, this, name, arguments, output):
        self.check(this)
        values = self.script_arguments.arguments(arguments)
        from civ6_host.runtime.native.native_script_arguments import argument_evidence
        evidence = argument_evidence(values)
        if not name or len(name) > 255 or (not name.isascii()) or (not output):
            self.host._fatal('unverified GameEvents synchronous call shape', interface='auxiliary', slot='0x60', event_name=name.decode('ascii') if name else None, **evidence, output_pointer_present=bool(output), result_substituted=False)
        C.c_uint8.from_address(output).value = 0
        valid, result = self.runtime.dispatch_game_event_result(name, values, method='Call')
        C.c_uint8.from_address(output).value = int(result)
        self.emit('native_game_event_dispatched', event_name=name.decode('ascii'), **evidence, output_boolean=result, protected_call_success=True, result_non_nil=valid, listener_profile='source-decoded-basic-methods', eligible_for_training=False)
        return valid

    def game_event_test_all(self, this, name, arguments, output):
        self.check(this)
        if not name or len(name) > 255 or (not name.isascii()) or (not output):
            raise ValueError('Unverified AUX80 TestAll arguments')
        values = self.script_arguments.arguments(arguments)
        from civ6_host.runtime.native.native_script_arguments import argument_evidence
        initial = C.c_uint8.from_address(output).value
        valid, result = self.runtime.dispatch_game_event_result(name, values, method='TestAll', output_initial=initial)
        if valid:
            C.c_uint8.from_address(output).value = result
        elif result != initial:
            raise RuntimeError('AUX80 nil result modified the output byte')
        self.emit('native_game_event_test_all', event_name=name.decode('ascii'), **argument_evidence(values), result_non_nil=valid, output_byte=result, output_written=valid, eligible_for_training=False)
        return valid

class NativeMapScriptPrefix(NativeGameEventCallbacks):

    def __init__(self, host, core, context, emit, *, selected_gameplay_scripts, diagnostic_action='found-city', diagnostic_rounds=1, diagnostic_production_policy='warrior', diagnostic_score_turn_limit=None, diagnostic_checkpoint=None, configuration_readback='immediate'):
        if configuration_readback not in ('immediate', 'after-configuration-copy'):
            raise ValueError('Unknown configuration readback phase')
        if configuration_readback == 'after-configuration-copy' and (diagnostic_action != 'initial-view' or diagnostic_rounds != 1 or diagnostic_production_policy != 'warrior' or (diagnostic_score_turn_limit is not None) or (diagnostic_checkpoint is not None)):
            raise ValueError('Deferred configuration readback is limited to the load-only profile')
        self.configuration_readback_verified = False
        if diagnostic_action not in ('found-city', 'found-city-produce', 'end-turn', 'end-round', 'initial-view', 'turn-ready', 'skip-units', 'skip-round', 'research', 'civic', 'research-civic', 'develop-round', 'develop-move-round', 'move-unit'):
            raise ValueError('Unknown native action diagnostic')
        self.diagnostic_action = diagnostic_action
        if diagnostic_production_policy not in ('warrior', 'native-first', 'native-placement', 'native-development', 'mac-cpu', 'mac-mps'):
            raise ValueError('Unknown diagnostic production selector')
        self.diagnostic_production_policy = diagnostic_production_policy
        self.mac_chooser = None
        if type(diagnostic_rounds) is not int or not 1 <= diagnostic_rounds <= 512:
            raise ValueError('Native round diagnostic is bounded to 1..512 rounds')
        if diagnostic_rounds > 32 and diagnostic_action not in ('develop-round', 'develop-move-round'):
            raise ValueError('Long diagnostics require develop-round or develop-move-round')
        if 1 < diagnostic_rounds <= 32 and diagnostic_action not in ('end-round', 'skip-round', 'develop-round', 'develop-move-round'):
            raise ValueError('Multiple diagnostic rounds require an end-round, skip-round or develop-round action')
        self.diagnostic_rounds = diagnostic_rounds
        if diagnostic_score_turn_limit is not None:
            if type(diagnostic_score_turn_limit) is not int or not 2 <= diagnostic_score_turn_limit <= 32 or diagnostic_rounds <= diagnostic_score_turn_limit or (diagnostic_action not in ('develop-round', 'develop-move-round')):
                raise ValueError('Unverified custom score diagnostic profile')
        self.diagnostic_score_turn_limit = diagnostic_score_turn_limit
        self.score_turn_limit_readback = None
        self.native_rounds_completed = 0
        self.checkpoint = None
        if diagnostic_checkpoint is not None:
            _validate_checkpoint_profile(diagnostic_checkpoint, diagnostic_rounds, diagnostic_action, diagnostic_production_policy, diagnostic_score_turn_limit, getattr(host, 'configured_local_player_id', None))
            from civ6_host.runtime.native.native_checkpoint_diagnostic import make_diagnostic
            self.checkpoint = make_diagnostic(diagnostic_checkpoint)
        self.development_players = set()
        self.host, self.core, self.context, self.emit = (host, core, context, emit)
        from civ6_host.runtime.native.native_episode_identity import initialize_episode
        identity = initialize_episode(self)
        emit('native_diagnostic_episode_opened', episode_id=identity.episode_id, game_generation=identity.game_generation, native_new_game_called=False, reset_validated=False, eligible_for_training=False)
        self.children = {}
        self.ui_child = None
        from civ6_host.runtime.native.native_application_mirror import NativePlayerApplicationMirror
        self.application_mirror = NativePlayerApplicationMirror(host, core, context, emit)
        from civ6_host.runtime.native.native_host_events import NativeDeferredHostEvents
        self.deferred_events = NativeDeferredHostEvents(host, core, context, emit, entity_observer_profile='no-exe-entity-listeners', visual_profile='empty-style-registry')
        from civ6_host.runtime.native.native_action_transport import NativeActionTransport
        self.actions = NativeActionTransport(host, core, context, emit)
        from civ6_host.runtime.native.native_script_arguments import NativeScriptArguments
        self.script_arguments = NativeScriptArguments(host)
        from civ6_host.runtime.native.native_gameplay_script_registry import NativeGameplayScriptRegistry
        self.gameplay_scripts = NativeGameplayScriptRegistry((host.dll_directory.parents[1] / 'Assets',), selected_scripts=selected_gameplay_scripts)
        self.map_path = (host.dll_directory.parents[1] / 'Assets/Maps/Continents.lua').absolute()
        self.map_source = _resolve_resource_path(self.map_path).read_bytes()
        if len(self.map_source) > 16 * 1024 * 1024:
            raise ValueError('Installed map source exceeds admitted bound')
        path = host.dll_directory / 'HavokScript_FinalRelease.dll'
        if sha256(path) != HAVOK_SHA256:
            raise ValueError('Unverified HavokScript module')
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = ([C.c_wchar_p], C.c_void_p)
        executable = C.WinDLL('', handle=kernel.GetModuleHandleW(None))
        from civ6_host.runtime.native.native_telemetry import NativeTelemetryProfile
        self.telemetry = NativeTelemetryProfile(executable, emit)
        from civ6_host.runtime.native.native_core_lock import NativeCoreLock
        self.core_lock = NativeCoreLock(host, executable)
        self.runtime = NativeScriptRuntime(C.WinDLL(str(path)), executable, emit)
        from civ6_host.runtime.native.native_include_registry import collect_lua_sources
        self.runtime.set_include_sources(collect_lua_sources((host.dll_directory.parents[1] / 'Assets/Maps',)))
        self.runtime.bind_core_services(host, context)
        self.game_child = self.runtime.acquire()
        self.runtime.attach_standard_libraries(self.game_child)
        self.runtime.attach_game_events(self.game_child)
        for source, expected, capacity in ((b"return 'ok'", b'ok', 2), (b"return ''", b'', 1), (b"return 'a'..string.char(0)..'b'", b'a\x00b', 3)):
            if self.runtime.evaluate_text(self.game_child, source, capacity=capacity) != expected:
                raise RuntimeError('Lua/Python string copy mismatch')
        for source, capacity, message in ((b'return 12', 4, 'must be a string'), (b"return 'oversize'", 2, 'exceeds output capacity'), (b"error('transport deliberate')", 128, 'transport deliberate')):
            try:
                self.runtime.evaluate_text(self.game_child, source, capacity=capacity)
            except RuntimeError as exc:
                if message not in str(exc):
                    raise
            else:
                raise RuntimeError('Invalid Lua result unexpectedly succeeded')
        if self.runtime.evaluate_text(self.game_child, b"return 'recovered'") != b'recovered':
            raise RuntimeError('Lua result transport did not recover after errors')
        emit('native_lua_python_result_transport_verified', bounded_copy=True, embedded_nul_preserved=True, error_recovery_verified=True)
        from civ6_host.runtime.native.native_aux_map_diagnostic import run_diagnostic as check_aux_map_transport
        check_aux_map_transport(self.runtime, self.game_child, emit)
        from civ6_host.runtime.native.native_aux_map_diagnostic import run_optional_diagnostic
        run_optional_diagnostic(self.runtime, self.game_child, emit)
        from civ6_host.runtime.native.native_player_observation import build_visibility_guard_case
        from civ6_host.runtime.native.native_player_observation import parse_player_observation
        guard = self.runtime.evaluate_text(self.game_child, build_visibility_guard_case(), b'@observation_visibility_guards')
        parsed_guard = parse_player_observation(guard, 0)
        if len(parsed_guard['plots']) != 2 or len(parsed_guard['visible_enemy_units']) != 1:
            raise RuntimeError('Visibility guard returned unexpected rows')
        visible_resource, concealed_resource = parsed_guard['plots']
        if visible_resource.get('resource_type') != 2 or visible_resource.get('resource_count') != 3 or 'resource_type' in concealed_resource or ('resource_count' in concealed_resource):
            raise RuntimeError('Native HKS guard failed to distinguish disclosed and hidden resources')
        emit('native_hks_observation_visibility_guards_verified', scope='Real collector against Lua doubles in native HKS, not native gameplay visibility', forbidden_getter_accesses=0, eligible_for_training=False)
        from civ6_host.runtime.native.native_revealed_plot_observation import build_revealed_plot_guard_case
        from civ6_host.runtime.native.native_revealed_plot_observation import parse_revealed_plot_observation
        revealed_guard = self.runtime.evaluate_text(self.game_child, build_revealed_plot_guard_case(), b'@revealed_plot_guards')
        revealed_rows = parse_revealed_plot_observation(revealed_guard, 0)['plots']
        if [row['index'] for row in revealed_rows] != [1, 2]:
            raise RuntimeError('Revealed-plot guard returned unexpected rows')
        emit('native_hks_revealed_plot_guards_verified', scope='Real collector against Lua doubles in native HKS, not native gameplay visibility', unrevealed_details_blocked=True, tech_hidden_resources_blocked=True, foreign_observer_blocked=True, eligible_for_training=False)
        from civ6_host.runtime.native.native_combat_actions import build_guard_case
        from civ6_host.runtime.native.native_combat_actions import parse_candidates
        combat_guard = self.runtime.evaluate_text(self.game_child, build_guard_case(), b'@combat_visibility_guards')
        combat_payload, submission = combat_guard.rsplit(b'|', 1)
        combat_candidates = parse_candidates(combat_payload, 0, 7)['candidates']
        if submission != b'submitted' or len(combat_candidates) != 1:
            raise RuntimeError('Combat visibility/request guard returned unexpected result')
        emit('native_hks_combat_guards_verified', scope='Readiness, visibility and request checks against doubles in native HKS', native_attack_executed=False, eligible_for_training=False)
        from civ6_host.runtime.native.native_winning_team import guard_case as winning_team_guard_case
        if self.runtime.evaluate_text(self.game_child, winning_team_guard_case(), b'@native_winning_team_guards') != b'winning-team-guards-ok':
            raise RuntimeError('Native HKS winning-team result guards failed')
        emit('native_hks_winning_team_guards_verified', scope='Public result collector against doubles in native HKS', eligible_for_training=False)
        from civ6_host.runtime.native.native_unit_actions import action_guard_case
        if self.runtime.evaluate_text(self.game_child, action_guard_case(), b'@native_unit_action_guard_cases') != b'action-guards-ok':
            raise RuntimeError('Native HKS action guard cases failed')
        emit('native_hks_action_guards_verified', scope='Request chunks against Lua doubles, not native gameplay legality', stale_legality_refused=True, inactive_player_refused=True, missing_unit_refused=True, eligible_for_training=False)
        from civ6_host.runtime.native.native_unit_skip import action_guard_case as skip_action_guard_case
        if self.runtime.evaluate_text(self.game_child, skip_action_guard_case(), b'@native_unit_skip_guard_cases') != b'unit-skip-guards-ok':
            raise RuntimeError('Native HKS unit skip guard cases failed')
        emit('native_hks_unit_skip_guards_verified', scope='Real request source against Lua doubles, not gameplay validation', stale_legality_refused=True, foreign_unit_refused=True, smallest_legal_ready_unit_selected=True, eligible_for_training=False)
        from civ6_host.runtime.native.native_endturn_gate import guard_case as endturn_guard_case
        if self.runtime.evaluate_text(self.game_child, endturn_guard_case(), b'@native_endturn_gate_cases') != b'endturn-gates-ok':
            raise RuntimeError('Native HKS endturn gate cases failed')
        emit('native_hks_endturn_gate_guards_verified', scope='Lua doubles, not native gameplay acceptance', eligible_for_training=False)
        from civ6_host.runtime.native.native_research_actions import guard_case as research_guard_case
        if self.runtime.evaluate_text(self.game_child, research_guard_case(), b'@native_research_guard_cases') != b'research-civic-guards-ok':
            raise RuntimeError('Native HKS research candidate/effect guards failed')
        emit('native_hks_research_guards_verified', scope='Lua candidate/effect doubles; no operation submitted', eligible_for_training=False)
        from civ6_host.runtime.native.native_research_catalog import guard_case as research_catalog_guard_case
        if self.runtime.evaluate_text(self.game_child, research_catalog_guard_case(), b'@native_research_catalog_guards') != b'research-catalog-guards-ok':
            raise RuntimeError('Native HKS research catalog guards failed')
        emit('native_hks_research_catalog_guards_verified', scope='Full candidate enumeration and explicit selection against Lua doubles', eligible_for_training=False)
        from civ6_host.runtime.native.native_policy_actions import guard_case as policy_guard_case
        if self.runtime.evaluate_text(self.game_child, policy_guard_case(), b'@native_policy_guard_cases') != b'native-policy-action-guards-ok':
            raise RuntimeError('Native HKS policy request guards failed')
        emit('native_hks_policy_guards_verified', scope='Complete free policy assignments and prior-slot checks against Lua doubles; no native policy changed', partial_filled_slots_refused=False, paid_change_refused=True, active_relocation_refused=True, unchanged_request_refused=True, eligible_for_training=False)
        from civ6_host.runtime.native.native_city_actions import action_guard_case as city_action_guard_case
        if self.runtime.evaluate_text(self.game_child, city_action_guard_case(), b'@native_city_action_guard_cases') != b'city-action-guards-ok':
            raise RuntimeError('Native HKS city action guard cases failed')
        emit('native_hks_city_action_guards_verified', scope='Real request source against Lua doubles, not gameplay validation', stale_legality_refused=True, unready_player_refused=True, missing_or_foreign_city_refused=True, nonempty_queue_refused=True, wrong_perspective_refused=True, eligible_for_training=False)
        from civ6_host.runtime.native.native_game_event_cases import CASES
        from civ6_host.runtime.native.native_game_event_cases import CLEANUP
        self.runtime.execute(self.game_child, CASES, b'@native_game_events_cases')
        if not self.runtime.dispatch_game_event(b'Civ6RL_SignedArguments', (4294967295, 2147483648, 65536, 2147483647)):
            raise RuntimeError('GameEvents signed argument listener did not return true')
        if not self.runtime.dispatch_game_event(b'Civ6RL_ManyArguments', tuple((v & 4294967295 for v in range(-32, 32)))):
            raise RuntimeError('GameEvents 64-argument listener did not return true')
        self.runtime.execute(self.game_child, CLEANUP, b'@native_game_events_cleanup')
        from civ6_host.runtime.native.native_game_event_cases import TYPED_ARGUMENT_SETUP
        from civ6_host.runtime.native.native_game_event_cases import TYPED_ARGUMENT_EVENT
        from civ6_host.runtime.native.native_game_event_cases import TYPED_ARGUMENTS
        from civ6_host.runtime.native.native_game_event_cases import TYPED_ARGUMENT_EXPECTED_RESULT
        from civ6_host.runtime.native.native_game_event_cases import TYPED_ARGUMENT_CLEANUP
        self.runtime.execute(self.game_child, TYPED_ARGUMENT_SETUP, b'@typed_game_events_setup')
        from civ6_host.runtime.native.native_script_arguments import BooleanArgument
        typed_args = tuple((BooleanArgument(255 if value else 0) if type(value) is bool else value for value in TYPED_ARGUMENTS))
        for method in ('Call', 'TestAll'):
            if self.runtime.dispatch_game_event_result(TYPED_ARGUMENT_EVENT, typed_args, method=method, output_initial=165) != TYPED_ARGUMENT_EXPECTED_RESULT:
                raise RuntimeError('Typed GameEvents argument/result contract failed')
        self.runtime.execute(self.game_child, TYPED_ARGUMENT_CLEANUP, b'@typed_game_events_cleanup')
        emit('native_game_events_typed_arguments_verified', raw_boolean_byte_normalized=True, booleans_distinct_from_numbers=True, signed_dword_preserved=True, call_and_test_all_verified=True, eligible_for_training=False)
        from civ6_host.runtime.native.native_game_event_aggregator_cases import CASES as AGGREGATE_CASES
        from civ6_host.runtime.native.native_game_event_aggregator_cases import CONTEXT_SETUP
        from civ6_host.runtime.native.native_game_event_aggregator_cases import CONTEXT_DISPATCH
        from civ6_host.runtime.native.native_game_event_aggregator_cases import CONTEXT_VERIFY_AND_CLEANUP
        self.runtime.execute(self.game_child, AGGREGATE_CASES, b'@native_game_event_aggregators')
        other = self.runtime.acquire()
        try:
            self.runtime.attach_standard_libraries(other)
            self.runtime.attach_game_events(other)
            for child, marker in ((self.game_child, b'first'), (other, b'second')):
                self.runtime.execute(child, b"Civ6RL_AggregatorMarker='" + marker + b"';" + CONTEXT_SETUP, b'@aggregate_context_setup')
                self.runtime.execute(child, b"Civ6RL_EventMarker='" + marker + b"'; Civ6RL_EventHits=0; GameEvents.Civ6RL_ContextCheck.Add(function(value) assert(Civ6RL_EventMarker=='" + marker + b"' and value==31); Civ6RL_EventHits=Civ6RL_EventHits+1; return true end)", b'@game_event_context_setup')
            if not self.runtime.dispatch_game_event(b'Civ6RL_ContextCheck', (31,)):
                raise RuntimeError('Cross-context GameEvents delivery failed')
            for child in (self.game_child, other):
                self.runtime.execute(child, b'assert(Civ6RL_EventHits==1); GameEvents.Civ6RL_ContextCheck.RemoveAll()', b'@game_event_context_verify')
            self.runtime.execute(self.game_child, CONTEXT_DISPATCH, b'@aggregate_context_dispatch')
            for child in (self.game_child, other):
                self.runtime.execute(child, CONTEXT_VERIFY_AND_CLEANUP, b'@aggregate_context_verify')
        finally:
            self.runtime.registry.release(other)
        if self.runtime.dispatch_game_event(b'Civ6RL_EmptyProfile', (0, 65536)):
            raise RuntimeError('Empty GameEvents Call unexpectedly returned true')
        for method, expected in (('Call', (False, 0)), ('TestAll', (False, 165))):
            if self.runtime.dispatch_game_event_result(b'Civ6RL_EmptyProfile', (0,), method=method, output_initial=165) != expected:
                raise RuntimeError('Empty GameEvents result validity/output mismatch')
        for literal, expected in ((b'false', False), (b'true', True), (b'0', True)):
            self.runtime.execute(self.game_child, b'GameEvents.Civ6RL_ResultProbe.Add(function(v) assert(v==-1); return ' + literal + b' end)', b'@game_events_result_setup')
            for method in ('Call', 'TestAll'):
                if self.runtime.dispatch_game_event_result(b'Civ6RL_ResultProbe', (4294967295,), method=method, output_initial=165) != (True, int(expected)):
                    raise RuntimeError('GameEvents non-nil Boolean result mismatch')
            self.runtime.execute(self.game_child, b'GameEvents.Civ6RL_ResultProbe.RemoveAll()', b'@game_events_result_cleanup')
        emit('native_game_events_result_contract_verified', call_nil_clears_output=True, test_all_nil_preserves_output=True, false_result_distinct_from_nil=True, zero_is_truthy=True, signed_argument_verified=True, eligible_for_training=False)
        emit('native_game_events_listener_profile_verified', remaining_diagnostic_listeners=0, protected_native_dispatch=True, callback_result='nil', output_boolean=False, append_remove_clear_and_call=True, signed_integer_arguments_verified=True, two_context_listeners_and_function_environments_verified=True, sixty_four_integer_arguments_verified=True, numeric_and_boolean_aggregation_verified=True, eligible_for_training=False)
        self.runtime.attach_event_category(self.game_child, 1)
        self.runtime.install_aux_event_registry()
        from civ6_host.runtime.native.native_aux_event_cases import AUX_EVENT_CASES
        from civ6_host.runtime.native.native_aux_event_cases import AUX_EVENT_NATIVE_DISPATCH
        self.runtime.execute(self.game_child, AUX_EVENT_CASES['dispatch_setup'].encode(), b'@aux_event_setup')
        self.runtime.dispatch_aux_event(AUX_EVENT_NATIVE_DISPATCH['event_name'].encode())
        self.runtime.execute(self.game_child, AUX_EVENT_CASES['dispatch_verify_and_cleanup'].encode(), b'@aux_event_verify')
        for name in ('remove_all', 'additional_listener_refusal', 'duplicate_listener_refusal', 'mutation_during_call_refusal'):
            self.runtime.execute(self.game_child, AUX_EVENT_CASES[name].encode(), ('@aux_event_' + name).encode())
        emit('native_aux_event_registry_verified', root_to_child_listener_delivery=True, admitted_listeners_per_event=1, complete_native_event_factory=False)
        self.runtime.bind_native_game_api(self.game_child, context, core)
        self.runtime.execute(self.game_child, b'print("CIV6RL_NATIVE_ACTION_ENDTURN",ActionTypes and ActionTypes.ACTION_ENDTURN)', b'@native_action_enum_witness')
        host._bind(host.aux_vtable, 0, C.c_void_p, [C.c_void_p, C.c_char_p, C.c_uint8], self.acquire)
        host._bind(host.aux_vtable, 8, None, [C.c_void_p, C.c_void_p], self.release)
        host._bind(host.aux_vtable, 24, C.c_bool, [C.c_void_p, C.c_void_p, C.c_void_p], self.load)
        host._bind(host.aux_vtable, 40, C.c_uint32, [C.c_void_p], self.script_count)
        host._bind(host.aux_vtable, 48, C.c_void_p, [C.c_void_p, C.c_int], self.script_path)
        host._bind(host.aux_vtable, 80, C.c_bool, [C.c_void_p] * 4, self.protected_call)
        host._bind(host.aux_vtable, 88, C.c_bool, [C.c_void_p, C.c_void_p, C.c_int, C.c_int], self.stack_call)
        host._bind(host.aux_vtable, 96, C.c_bool, [C.c_void_p, C.c_char_p, C.c_void_p, C.c_void_p], self.game_event_call)
        host._bind(host.aux_vtable, 128, C.c_bool, [C.c_void_p, C.c_char_p, C.c_void_p, C.c_void_p], self.game_event_test_all)
        host._bind(host.aux_vtable, 144, C.c_bool, [C.c_void_p, C.c_int, C.c_void_p, C.c_void_p], self.dispatch_aux_event)
        host._bind(host.aux_vtable, 208, None, [C.c_void_p], self.lock)
        host._bind(host.aux_vtable, 216, None, [C.c_void_p], self.unlock)
        host._bind(host.aux_vtable, 232, None, [C.c_void_p, C.c_void_p], self.log_literal)
        push_variant = executable.LAB_AuxPushVariant
        push_variant.argtypes, push_variant.restype = ([C.c_void_p] * 3, None)
        host.aux_vtable[160 // 8] = C.cast(push_variant, C.c_void_p).value
        self.push_variant = push_variant
        from civ6_host.runtime.native.native_aux_map_adapter import NativeAuxMapAdapter
        self.aux_map_adapter = NativeAuxMapAdapter(executable, self.runtime, core, C.addressof(host.aux_object), emit)
        self.aux_map_adapter.install()
        push_map = executable.LAB_AuxPushMap
        push_map.argtypes, push_map.restype = ([C.c_void_p] * 3 + [C.c_uint8], None)
        host.aux_vtable[168 // 8] = C.cast(push_map, C.c_void_p).value
        self.push_map = push_map
        push_optional = executable.LAB_AuxPushOptionalMap
        push_optional.argtypes, push_optional.restype = ([C.c_void_p] * 3 + [C.c_uint8], None)
        host.aux_vtable[176 // 8] = C.cast(push_optional, C.c_void_p).value
        self.push_optional_map = push_optional
        if configuration_readback == 'immediate':
            self.verify_configuration_scalar_marshalling()
        else:
            emit('native_configuration_lua_readback_deferred', required_phase='after-configuration-copy', eligible_for_training=False)
        emit('native_map_script_prefix_enabled', eligible_for_training=False, missing_context_components=['EXE engine Events', 'FLua exposures', 'EXE game-data callbacks', 'native include registry ordering'], strict_load_errors=True, tuner_unavailable=True)
        emit('native_gameplay_script_selection', selected_paths=[str(p) for p in self.gameplay_scripts.paths], explicit_selection=True, fixture_active_mods_match_verified=False, eligible_for_training=False)

    def verify_configuration_scalar_marshalling(self):
        """Validate native A once, after its initial setup or the Load B->A copy."""
        if self.configuration_readback_verified:
            raise ValueError('Configuration scalar readback already verified')
        self.runtime.execute(self.game_child, b"assert(MapConfiguration.GetValue('start')==1)\nassert(MapConfiguration.GetValue('world_age')==2)\nassert(MapConfiguration.GetValue('RANDOM_SEED')==42042)\nassert(MapConfiguration.GetValue('MAP_SIZE')==-1837222328)\nassert(MapConfiguration.GetValue('CIV6RL_MISSING_PROPERTY')==nil)\n", b'@native_configuration_scalar_marshalling')
        self.configuration_readback_verified = True
        self.emit('native_configuration_lua_readback_verified', native_core_callback=True, includes_signed_hash=True, missing_key_is_nil=True)

    def trace_game_event(self, this, kind, argument):
        self.host._check(this)
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
        vtable = int.from_bytes(read(argument, 8), 'little') if argument else 0
        fields = {}
        if vtable == self.core._handle + 8507296:
            lookup = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(self.core._handle + 7625904)
            for key in (2716180809, 3606901732, 2717631346):
                value = lookup(argument, key)
                fields[hex(key)] = read(value, 24).hex() if value else None
        self.host._fatal('unimplemented native event dispatch', interface='host', slot='0xa0', dispatch_kind=hex(kind), argument_vtable_rva=hex(vtable - self.core._handle), fields=fields, result_substituted=False)

    def dispatch_aux_event(self, this, kind, name, arguments):
        self.check(this)
        if kind != 0 or not name or arguments:
            raise ValueError('Unverified AUX event category or argument interface')
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
        raw = bytearray()
        for index in range(256):
            unit = read(name + index, 1)
            if unit == b'\x00':
                break
            raw.extend(unit)
        else:
            raise ValueError('AUX event name exceeds bound')
        event = raw.decode('ascii')
        if event != 'NewGameInitialized':
            raise ValueError('Unverified AUX event name: ' + event)
        self.runtime.dispatch_aux_event(event.encode('ascii'))
        self.emit('native_aux_event_dispatched', name=event, category=1, argument_count=0, source='Core native callback', strict_errors=True)
        return True

    def trace_host_dispatch(self, this, kind, argument, output):
        self.host._check(this)
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
        snapshots = {}
        for label, pointer in (('argument', argument), ('output', output)):
            snapshots[label] = {'pointer': pointer}
            if pointer:
                try:
                    raw = read(pointer, 48)
                    snapshots[label]['prefix_hex'] = raw.hex()
                    first = int.from_bytes(raw[:8], 'little')
                    if self.core._handle <= first < self.core._handle + 12582912:
                        snapshots[label]['first_pointer_core_rva'] = hex(first - self.core._handle)
                except OSError as error:
                    snapshots[label]['read_error'] = str(error)
        fields = {}
        source_relationship = {}
        if snapshots['argument'].get('first_pointer_core_rva') == '0x81d838':
            address = int.from_bytes(read(self.core._handle + 8509496 + 104, 8), 'little')
            if address != self.core._handle + 7652928:
                raise ValueError('Unverified dispatch argument lookup')
            lookup = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(address)
            for key in (2716180809, 4033489650, 212608518):
                value = lookup(argument, key)
                fields[hex(key)] = {'present': bool(value)}
                if value:
                    raw = read(value, 24)
                    fields[hex(key)].update(raw_hex=raw.hex(), tag=int.from_bytes(raw[:2], 'little'), value_uint32=int.from_bytes(raw[8:12], 'little'), flags=hex(int.from_bytes(raw[20:24], 'little')))
        if kind == 1829978708 and output:
            from civ6_host.runtime.native.native_player_records import bounded_get_player_config
            entry = bounded_get_player_config(self.core._handle, self.context, 0)
            source_relationship = {'is_record_provider': output == entry['provider'], 'is_record_value': output == entry['pointer']}
            lookup = C.WINFUNCTYPE(C.c_void_p, C.c_void_p, C.c_uint32)(self.core._handle + 7625904)
            value = lookup(entry['pointer'], 1655168934)
            source_relationship['player_zero_alive_variant'] = read(value, 24).hex() if value else None
        self.host._fatal('unimplemented native host dispatch', interface='host', slot='0x130', dispatch_kind=hex(kind), arguments=snapshots, fields=fields, source_relationship=source_relationship, result_substituted=False)

    def script_count(self, this):
        self.check(this)
        count = self.gameplay_scripts.count()
        self.emit('native_gameplay_script_count', count=count, source='explicit host selection')
        return count

    def script_path(self, this, index):
        self.check(this)
        return self.gameplay_scripts.get(index)

    def lock(self, this):
        self.check(this)
        call = self.runtime.host.LAB_ScriptLockEnter
        call.argtypes, call.restype = ([], C.c_int)
        if call() != 1:
            raise RuntimeError('Native script critical-section acquisition failed')

    def unlock(self, this):
        self.check(this)
        call = self.runtime.host.LAB_ScriptLockLeave
        call.argtypes, call.restype = ([], C.c_int)
        if call() != 1:
            raise RuntimeError('Native script critical-section release failed')

    def log_literal(self, this, pointer):
        self.check(this)
        if not pointer:
            return
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
        data = bytearray()
        for index in range(2048):
            value = read(pointer + index, 1)
            if value == b'\x00':
                break
            data.extend(value)
        else:
            raise ValueError('Script log exceeds native 0x800-byte buffer')
        if b'%' in data:
            raise ValueError('Script variadic logging is unverified; literal text only')
        if not data.endswith(b'\n'):
            data.extend(b'\n')
        self.emit('native_script_log', message_hex=data.hex(), message=data.decode('utf-8', errors='replace'), diagnostic_sink=True, native_logger_file_routing=False)

    def acquire(self, this, name, flag):
        self.check(this)
        if name == b'GameCore_Tuner' and flag == 1:
            return self.host._tuner_unavailable(this, name, flag)
        if name != b'Map Script' or flag != 0:
            raise ValueError(f'Unverified script request {name!r}, flag {flag}')
        child = self.runtime.acquire()
        self.runtime.attach_standard_libraries(child)
        self.runtime.attach_game_events(child)
        self.runtime.attach_include(child)
        self.runtime.attach_event_category(child, 1)
        self.runtime.attach_ui_enums(child)
        for namespace in ('Achievements', 'DB', 'GameInfo', 'GlobalParameters', 'Path', 'Locale'):
            self.runtime.namespaces.register(child, namespace)
        self.runtime.attach_native_game_api(child)
        self.runtime.execute(child, b'StateName="Map Script"', b'@map_script_state_name')
        self.children[child.pointer] = child
        self.emit('native_map_script_acquired', complete_factory=False, eligible_for_training=False)
        return child.pointer

    def release(self, this, pointer):
        self.check(this)
        child = self.children.pop(pointer)
        self.runtime.registry.release(child)
        self.emit('native_map_script_released')

    def load(self, this, pointer, path):
        self.check(this)
        child = self.children[pointer]
        from civ6_host.runtime.native.native_setup import local_reader
        read = local_reader()
        raw = bytearray()
        for index in range(260):
            unit = read(path + 2 * index, 2)
            if unit == b'\x00\x00':
                break
            raw.extend(unit)
        else:
            raise ValueError('Map load path missing UTF-16 terminator')
        path = raw.decode('utf-16-le')
        self.emit('native_map_script_path_decoded', path=path)
        if _resolve_resource_path(Path(path)) != self.map_path:
            raise ValueError('Unverified script outside the selected map snapshot')
        import hashlib
        self.emit('native_map_script_load', path=str(self.map_path), sha256=hashlib.sha256(self.map_source).hexdigest(), snapshot_before_newgame=True)
        self.runtime.execute(child, self.map_source, str(self.map_path).encode('ascii'))
        return True

    def close(self):
        if self.children:
            raise RuntimeError('GameCore retained script contexts at destruction')
        if self.script_arguments.live_count:
            raise RuntimeError('GameCore retained script argument payloads at destruction')
        self.aux_map_adapter.close()
        if self.ui_child is not None:
            self.runtime.registry.release(self.ui_child)
            self.ui_child = None
        self.runtime.registry.release(self.game_child)
        self.runtime.unbind_services()
        self.runtime.close()
        self.gameplay_scripts.close()
        self.core_lock.close()

    def close_player_view_before_unload(self):
        if self.mac_chooser is not None:
            self.mac_chooser.close()
            self.emit('native_diagnostic_mac_chooser_closed', before_core_unload=True, eligible_for_training=False)
        publisher = getattr(self, 'view_publisher', None)
        if publisher is not None:
            self.deferred_events.ui_cache_callbacks_enabled = False
            publisher.close()
            self.emit('native_player_view_facades_closed', before_core_unload=True, context_destroyed=False, eligible_for_training=False)

    def inspect_new_game(self):
        """Read actual native players/units after NewGame; this is not policy input."""
        if not self.configuration_readback_verified:
            raise RuntimeError('NewGame inspection requires the native configuration readback')
        snapshot = self.runtime.evaluate_text(self.game_child, b"local ids=PlayerManager.GetAliveMajorIDs()\nassert(#ids==2 and PlayerManager.GetAliveMajorsCount()==2,'expected two native major players')\nlocal w,h=Map.GetGridSize()\nassert(w>0 and h>0 and w*h<=16384,'invalid native map')\nlocal rows={}\nfor _,id in ipairs(ids) do\n    assert(id==0 or id==1,'unexpected native major ID')\n    local p=Players[id]\n    assert(p~=nil,'missing native player')\n    local count=0\n    for _,u in p:GetUnits():Members() do\n        count=count+1\n        assert(count<=128,'initial native unit count exceeds bound')\n        for _,method in ipairs({'GetID','GetType','GetX','GetY'}) do\n            assert(type(u[method])=='function','missing native unit method: '..method)\n        end\n        rows[#rows+1]=string.format('%d,%d,%d,%d,%d',id,u:GetID(),u:GetType(),u:GetX(),u:GetY())\n    end\n    assert(count>0,'native player has no starting units')\nend\nreturn string.format('%d|%d|%d|%d|%s',Game.GetCurrentGameTurn(),w,h,#ids,table.concat(rows,';'))\n", b'@native_new_game_witness')
        turn, width, height, count, rows = snapshot.decode('ascii').split('|')
        units = []
        for row in rows.split(';'):
            owner, identifier, unit_type, x, y = map(int, row.split(','))
            units.append(dict(owner=owner, identifier=identifier, unit_type=unit_type, x=x, y=y))
        if int(count) != 2 or {u['owner'] for u in units} != {0, 1}:
            raise RuntimeError('Native population result failed its player invariants')
        if len({(u['owner'], u['identifier']) for u in units}) != len(units):
            raise RuntimeError('Native population result has duplicate units')
        self.emit('native_new_game_population_verified', major_players=2, current_game_turn=int(turn), width=int(width), height=int(height), units=units, each_has_native_units=True, training_ready=False, observation_scope='Privileged diagnostic only, not learner observation', native_turns_executed=0)
        self.deferred_events.drain_empty_receivers()
        from civ6_host.runtime.native.native_player_view import NativePlayerViewPublisher
        self.view_publisher = NativePlayerViewPublisher(self.core, self.context, self.emit)
        self.actions.update_game_once()
        self.deferred_events.drain_empty_receivers()
        dimensions = self.view_publisher.publish()
        self.deferred_events.admit_initialized_ui_cache_profile(self.view_publisher.initialization_profile, dimensions, cache_map_snapshot=self.view_publisher.cache_map_snapshot, full_facade_initialization_reproduced=self.view_publisher.full_facade_initialization_reproduced)
        self.deferred_events.bind_retained_game_getter(self.view_publisher.read_retained_game_value)
        self.deferred_events.bind_retained_combat_predicate(self.view_publisher.query_combat_owner)
        self.deferred_events.bind_natural_wonder_facades(self.view_publisher)
        initial_state = self.inspect_player_view()
        self.emit('native_action_diagnostic_selected', profile=self.diagnostic_action, automatic_training=False, eligible_for_training=False)
        if self.diagnostic_action == 'initial-view':
            return
        self.inspect_turn_readiness(initial_state, 0)
        if self.diagnostic_action == 'turn-ready':
            return
        if self.diagnostic_action == 'skip-units':
            self.inspect_skip_units(0)
            return
        if self.diagnostic_action == 'move-unit':
            self.inspect_unit_movement(0)
            return
        if self.diagnostic_action in ('research', 'civic', 'research-civic'):
            kinds = ('research', 'civic') if self.diagnostic_action == 'research-civic' else (self.diagnostic_action,)
            for kind in kinds:
                self.inspect_player_research_choice(0, kind)
            return
        if self.diagnostic_action in ('found-city', 'found-city-produce'):
            self.inspect_found_city(0)
        if self.diagnostic_action == 'found-city-produce':
            self.inspect_unit_production(0)
        if self.diagnostic_action in ('develop-round', 'develop-move-round'):
            self.inspect_development_decisions(0)
        if self.diagnostic_action == 'skip-round':
            self.inspect_clear_unit_decisions(0)
        self.actions.request_end_turn(0)
        self.telemetry.inspect('before_endturn_delivery')
        self.actions.deliver_one()
        self.telemetry.inspect('after_endturn_delivery')
        self.deferred_events.drain_empty_receivers()
        self.emit('native_turn_after_one_endturn', current_game_turn=int(self.runtime.evaluate_text(self.game_child, b'return tostring(Game.GetCurrentGameTurn())', b'@turn_after_command')), full_round_verified=False, eligible_for_training=False)
        self.view_publisher.publish()
        state = self.inspect_player_view()
        if self.diagnostic_action in ('end-round', 'skip-round', 'develop-round', 'develop-move-round'):
            state = self.inspect_second_player_endturn(state)
            for _ in range(1, self.diagnostic_rounds):
                ready = self.inspect_turn_readiness(state, 0)
                if self.diagnostic_action in ('develop-round', 'develop-move-round'):
                    self.inspect_development_decisions(0)
                if self.diagnostic_action == 'skip-round':
                    self.inspect_clear_unit_decisions(0)
                self.actions.request_end_turn(0)
                self.actions.deliver_one()
                self.deferred_events.drain_empty_receivers()
                self.view_publisher.publish()
                handoff = self.inspect_player_view()
                if handoff['current_game_turn'] != ready['current_game_turn']:
                    raise RuntimeError('First player unexpectedly advanced the global turn')
                state = self.inspect_second_player_endturn(handoff)

    def inspect_turn_readiness(self, state, player_id=0):
        """Pump public GameUpdate until the actual active player is ready.

        IsTurnActiveComplete is a begin-turn readiness predicate used by the
        installed ActionPanel. It must not be replaced by IsTurnActive alone.
        The eight-update cap is a diagnostic bound, not an EXE frame cadence.
        """
        if type(player_id) is not int or player_id not in (0, 1):
            raise ValueError('Only the two configured players have a readiness contract')
        initial_turn = state['current_game_turn']
        for updates in range(9):
            players = state['players']
            if state['current_game_turn'] != initial_turn or state['local_player'] != player_id or len(players) != 2 or (players[0]['player_id'] != 0) or (players[1]['player_id'] != 1) or (not players[player_id]['active']) or players[1 - player_id]['active']:
                raise RuntimeError(f'Native readiness changed player/turn: {state!r}')
            if players[player_id]['complete']:
                from civ6_host.runtime.native.native_turn_decisions import blocker_source
                from civ6_host.runtime.native.native_turn_decisions import parse_blockers
                blocker_bytes = self.runtime.evaluate_text(self.ui_child, blocker_source(player_id), b'@native_end_turn_blockers')
                blockers = parse_blockers(blocker_bytes, player_id, initial_turn)
                self.emit('native_end_turn_blockers_observed', **blockers, source='Native NotificationManager UI getters; no decisions overridden', diagnostic_endturn_may_bypass_ui_blockers=True, eligible_for_training=False)
                self.emit('native_player_turn_ready_verified', state=state, player_id=player_id, additional_public_updates=updates, native_flags_written_by_host=False, source='ActionPanel.IsTurnActiveComplete; native-player-turn-state.json', full_action_legality_validated=False, eligible_for_training=False)
                return state
            if updates == 8:
                break
            self.emit('before_native_turn_readiness_update', update_number=updates + 1, current_game_turn=initial_turn, player_id=player_id, eligible_for_training=False)
            self.actions.update_game_once()
            self.deferred_events.drain_empty_receivers()
            self.view_publisher.publish()
            state = self.inspect_player_view()
        raise RuntimeError('Native player turn did not become ready within eight public updates')

    def inspect_second_player_endturn(self, before):
        """Bounded two-player handoff test, with no synthetic player switch."""
        expected_before = [{'player_id': 0, 'active': False, 'complete': False}, {'player_id': 1, 'active': True, 'complete': False}]
        if before['local_player'] != 1 or before['players'] != expected_before:
            raise RuntimeError(f'Native first-player handoff is not ready: {before!r}')
        self.emit('native_first_player_handoff_verified', state=before, host_local_identity=self.host.configured_local_player_id, host_identity_changed=False, core_perspective_changed=True, player_switch_memory_written_by_host=False, eligible_for_training=False)
        before = self.inspect_turn_readiness(before, 1)
        if self.diagnostic_action in ('develop-round', 'develop-move-round'):
            self.inspect_development_decisions(1)
        if self.diagnostic_action == 'skip-round':
            self.inspect_clear_unit_decisions(1)
        self.actions.request_end_turn(1)
        self.telemetry.inspect('before_second_endturn_delivery')
        self.actions.deliver_one()
        self.telemetry.inspect('after_second_endturn_delivery')
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        from civ6_host.runtime.native.native_ai_round_pump import wait_for_completed_round_echo
        after = wait_for_completed_round_echo(self, before['current_game_turn'])
        ended_state = [{'player_id': 0, 'active': False, 'complete': False}, {'player_id': 1, 'active': False, 'complete': False}]
        if after['current_game_turn'] != before['current_game_turn'] or after['local_player'] != 1 or after['players'] != ended_state:
            raise RuntimeError(f'Native ended-round handoff differs: {after!r}')
        self.actions.deliver_completed_round_echo(1)
        self.deferred_events.drain_empty_receivers()
        if self.diagnostic_action in ('develop-round', 'develop-move-round'):
            from civ6_host.runtime.native.native_victory_diagnostic import observe_after_round_echo
            self.view_publisher.publish()
            observe_after_round_echo(self, 1, before['current_game_turn'])
        self.actions.update_game_once()
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        after = self.inspect_player_view()
        expected_after = [{'player_id': 0, 'active': True, 'complete': False}, {'player_id': 1, 'active': False, 'complete': False}]
        if after['current_game_turn'] != before['current_game_turn'] + 1 or after['local_player'] != 0 or after['players'] != expected_after:
            raise RuntimeError(f'Native complete-round effect differs: {after!r}')
        self.native_rounds_completed += 1
        self.emit('native_round_effect_verified', before=before, after=after, native_rounds_completed=1, action_players=[0, 1], cumulative_native_rounds_completed=self.native_rounds_completed, host_identity_changed=False, core_perspective_changed=True, empty_capital_diagnostic=self.diagnostic_action not in ('develop-round', 'develop-move-round'), complete_game=False, unit_orders_resolved_before_each_endturn=self.diagnostic_action in ('skip-round', 'develop-round', 'develop-move-round'), eligible_for_training=False)
        if getattr(self, 'checkpoint', None) is not None:
            self.checkpoint.at_completed_round(self, after)
        return after

    def inspect_development_decisions(self, player_id):
        """Compose verified native requests; the final native gate stays strict."""
        self.inspect_episode_facts(player_id)
        if player_id not in self.development_players:
            self.inspect_found_city(player_id)
            self.development_players.add(player_id)
            self.inspect_unit_production(player_id)
        else:
            self.inspect_unit_production(player_id, require_candidate=False)
        self.inspect_city_production_progress(player_id)
        for kind in ('research', 'civic'):
            self.inspect_player_research_choice(player_id, kind)
        self.inspect_government_choice(player_id)
        self.inspect_government_consideration(player_id)
        self.inspect_initial_policy_choice(player_id)
        self.inspect_pantheon_choice(player_id)
        for _ in range(64):
            if self.inspect_great_person_choice(player_id) is None:
                break
        else:
            raise RuntimeError('Great-person diagnostic exceeded 64 verified recruitments in one decision phase')
        self.inspect_religion_development(player_id)
        for _ in range(64):
            if self.inspect_envoy_choice(player_id) is None:
                break
        else:
            raise RuntimeError('Envoy diagnostic exceeded 64 verified actions in one decision phase')
        if self.diagnostic_action == 'develop-move-round':
            self.inspect_visible_combat_candidates(player_id)
            self.inspect_unit_movement(player_id, require_candidate=False)
        self.inspect_clear_unit_decisions(player_id)
        self.inspect_episode_facts(player_id)
        self.emit('native_development_decisions_resolved', player_id=player_id, founded_players=sorted(self.development_players), native_endturn_gate_verified=True, complete_game=False, eligible_for_training=False)

    def inspect_envoy_choice(self, player_id, *, selected_target=None, retain=False, review=False):
        """Send a native envoy, or explicitly retain tokens by closing its panel.

        The diagnostic acts only when the native prompt is pending. Explicit
        send choices can also be tested when no prompt is present. Final turn
        permission still comes from the independent native EndTurn gate.
        """
        import struct
        from civ6_host.runtime.native import native_envoy_actions as envoy
        from civ6_host.runtime.native.native_player_operation_request import request_player_operation
        if type(retain) is not bool or type(review) is not bool or (retain and review) or ((retain or review) and selected_target is not None):
            raise ValueError('Envoy sending and retention are separate choices')
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Envoy choice requires a published UI view and drained queues')
        turn = int(self.runtime.evaluate_text(self.ui_child, b'return tostring(Game.GetCurrentGameTurn())', b'@native_envoy_turn'))
        source = envoy.catalog_source(player_id, turn)
        before = envoy.parse_catalog(self.runtime.evaluate_text(self.ui_child, source, b'@native_envoy_catalog'), player_id, turn)
        self.emit('native_envoy_catalog_observed', catalog=before, source_proof_sha256=envoy.PROOF_SHA256, eligible_for_training=False)
        if selected_target is None and (not retain) and (not review) and (not before['giving_tokens_blocker_present']):
            return None
        choices = [r for r in before['targets'] if r['can_give']]
        if retain or review or (selected_target is None and (not choices or not before['can_give_influence'] or before['tokens_to_give'] == 0)):
            requested = envoy.parse_catalog(self.runtime.evaluate_text(self.ui_child, envoy.consideration_source(before, require_blocker=not review), b'@native_envoy_consideration_request'), player_id, turn)
            if self.actions.pending:
                raise RuntimeError('Envoy consideration unexpectedly serialized a command')
            if not requested['considered'] or requested['tokens_to_give'] != before['tokens_to_give']:
                raise RuntimeError('Native envoy consideration immediate readback differs')
            self.deferred_events.drain_empty_receivers()
            self.view_publisher.publish()
            after = envoy.parse_catalog(self.runtime.evaluate_text(self.ui_child, source, b'@native_envoy_consideration_after'), player_id, turn)
            effect = envoy.verify_considered_effect(before, after, require_blocker=not review)
            self.emit('native_envoy_consideration_effect_verified', before=before, after=after, effect=effect, diagnostic_choice='review_panel' if review else 'retain_tokens', source_proof_sha256=envoy.PROOF_SHA256, eligible_for_training=False)
            return effect
        target = choices[0]['target_player_id'] if selected_target is None else selected_target
        choice = envoy.choose(before, target)
        checked = envoy.validate_fresh_choice(self.runtime.evaluate_text(self.ui_child, envoy.revalidation_source(choice), b'@native_envoy_revalidation'), choice)
        operation, parameters = envoy.operation_parameters(checked)
        self.emit('native_envoy_candidate', choice=choice, operation=operation, parameters=parameters, selection_policy='first-native-candidate' if selected_target is None else 'explicit', source_proof_sha256=envoy.PROOF_SHA256, eligible_for_training=False)
        result = request_player_operation(self.core, self.context, player_id, operation, parameters)
        self.emit('native_player_operation_request_returned', kind='give-influence-token', **result)
        if not result['can_start'] or not result['request_invoked']:
            raise RuntimeError('Native CanStartPlayerOperation refused envoy assignment')
        if len(self.actions.pending) != 1 or self.actions.pending[0][:4] != struct.pack('<I', 3294486831):
            raise RuntimeError('Envoy request did not emit exactly one native operation archive')
        self.actions.deliver_one()
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        after = envoy.parse_catalog(self.runtime.evaluate_text(self.ui_child, source, b'@native_envoy_effect'), player_id, turn)
        effect = envoy.verify_sent_effect(after, choice)
        self.emit('native_envoy_send_effect_verified', choice=choice, before=before, after=after, effect=effect, source_proof_sha256=envoy.PROOF_SHA256, eligible_for_training=False)
        return effect

    def inspect_visible_combat_candidates(self, player_id):
        from civ6_host.runtime.native.native_combat_actions import candidate_source
        from civ6_host.runtime.native.native_combat_actions import parse_candidates
        turn = int(self.runtime.evaluate_text(self.ui_child, b'return string.format("%.0f",Game.GetCurrentGameTurn())', b'@combat_candidate_turn'))
        payload = self.runtime.evaluate_text(self.ui_child, candidate_source(player_id, turn), b'@native_visible_combat_candidates')
        result = parse_candidates(payload, player_id, turn)
        self.emit('native_visible_combat_candidates_observed', **result, request_submitted=False, damage_predicted=False, complete_action_space=False, eligible_for_training=False)

    def inspect_city_production_progress(self, player_id):
        from civ6_host.runtime.native.native_city_production_observation import production_snapshot_source
        from civ6_host.runtime.native.native_city_production_observation import parse_production_snapshot
        from civ6_host.runtime.native.native_city_production_observation import guard_case_source
        from civ6_host.runtime.native.native_city_production_observation import own_entity_snapshot_source
        from civ6_host.runtime.native.native_city_production_observation import parse_own_entity_snapshot
        from civ6_host.runtime.native.native_city_production_observation import own_entity_guard_case_source
        from civ6_host.runtime.native.native_city_production_observation import diff_production_observations
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Production progress requires a published UI view and drained queues')
        if not getattr(self, '_production_progress_guard_verified', False):
            result = self.runtime.evaluate_text(self.ui_child, guard_case_source(), b'@native_production_progress_guards')
            if result != b'city-production-guards-ok':
                raise RuntimeError('Native HKS production guard check failed')
            self._production_progress_guard_verified = True
            self.emit('native_hks_city_production_guards_verified', eligible_for_training=False)
            roster_guard = self.runtime.evaluate_text(self.ui_child, own_entity_guard_case_source(), b'@native_own_roster_guards')
            if roster_guard != b'own-roster-guards-ok':
                raise RuntimeError('Native HKS own roster guard check failed')
            self.emit('native_hks_own_roster_guards_verified', eligible_for_training=False)
        snapshot = parse_production_snapshot(self.runtime.evaluate_text(self.ui_child, production_snapshot_source(player_id), b'@native_city_production_progress', capacity=65536), player_id)
        self.emit('native_city_production_progress_observed', **snapshot, source='Native local-player city build queue UI getters', completion_inferred=False, eligible_for_training=False)
        roster = parse_own_entity_snapshot(self.runtime.evaluate_text(self.ui_child, own_entity_snapshot_source(player_id), b'@native_own_roster', capacity=262144), player_id)
        if roster['game_turn'] != snapshot['game_turn']:
            raise RuntimeError('Native own roster and production snapshots crossed turns')
        self.emit('native_own_entity_roster_observed', **roster, eligible_for_training=False)
        previous = getattr(self, '_production_snapshots', {})
        if player_id in previous:
            before, before_roster = previous[player_id]
            delta = diff_production_observations(before, snapshot, before_roster, roster)
            self.emit('native_production_and_roster_delta_observed', **delta, completion_inferred=False, eligible_for_training=False)
        previous[player_id] = (snapshot, roster)
        self._production_snapshots = previous

    def inspect_initial_policy_choice(self, player_id):
        """Submit a free, complete policy assignment and verify native slots.

        The native end-turn gate still refuses any remaining decision, including
        an unpaid or unsupported change. A not-due result does not clear it.
        """
        from civ6_host.runtime.native.native_policy_actions import candidate_source
        from civ6_host.runtime.native.native_policy_actions import parse_candidate
        from civ6_host.runtime.native.native_policy_actions import request_source
        from civ6_host.runtime.native.native_policy_actions import parse_request_result
        from civ6_host.runtime.native.native_policy_actions import effect_source
        from civ6_host.runtime.native.native_policy_actions import parse_effect
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Policy choice requires a current UI view and drained queues')
        turn = int(self.runtime.evaluate_text(self.ui_child, b'return tostring(Game.GetCurrentGameTurn())', b'@native_policy_turn'))
        candidate = parse_candidate(self.runtime.evaluate_text(self.ui_child, candidate_source(player_id), b'@native_policy_candidate'), player_id, turn)
        if candidate['status'] == 'not_due':
            self.emit('native_policy_change_not_due', **candidate, request_invoked=False, decisions_overridden=False, eligible_for_training=False)
            return
        if candidate['status'] == 'unavailable' and candidate['reason'] == 'no_unlocked_policies':
            self.emit('native_policy_catalog_unavailable', **candidate, request_invoked=False, decisions_overridden=False, endturn_gate_still_required=True, eligible_for_training=False)
            return
        if candidate['status'] != 'candidate':
            raise RuntimeError('No complete legal policy assignment in the supported free window')
        self.emit('native_policy_change_candidate', **candidate, eligible_for_training=False)
        accepted = parse_request_result(self.runtime.evaluate_text(self.ui_child, request_source(player_id, candidate), b'@native_policy_request'), player_id, turn, candidate['slot_count'])
        if len(self.actions.pending) != 1:
            raise RuntimeError('Policy change did not serialize exactly one native command')
        self.emit('native_policy_change_request_accepted', **accepted, action_applied=False, eligible_for_training=False)
        self.actions.deliver_one()
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        effect = parse_effect(self.runtime.evaluate_text(self.ui_child, effect_source(player_id, candidate), b'@native_policy_effect'), player_id, candidate, turn)
        self.emit('native_policy_change_effect_verified', **effect, native_rules_used=True, eligible_for_training=False)

    def inspect_pantheon_choice(self, player_id, *, selected_index=None):
        """Submit a source-backed pantheon choice; keep the final turn gate strict."""
        import struct
        from civ6_host.runtime.native.native_pantheon_actions import catalog_source
        from civ6_host.runtime.native.native_pantheon_actions import parse_catalog
        from civ6_host.runtime.native.native_pantheon_actions import choose
        from civ6_host.runtime.native.native_pantheon_actions import revalidate_choice_source
        from civ6_host.runtime.native.native_pantheon_actions import parse_revalidated_choice
        from civ6_host.runtime.native.native_pantheon_actions import effect_source
        from civ6_host.runtime.native.native_pantheon_actions import parse_effect
        from civ6_host.runtime.native.native_pantheon_actions import guard_case
        from civ6_host.runtime.native.native_player_operation_request import request_player_operation
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Pantheon choice requires a published UI view and drained queues')
        if not getattr(self, '_pantheon_guard_verified', False):
            if self.runtime.evaluate_text(self.ui_child, guard_case(), b'@native_pantheon_guards') != b'pantheon-guards-ok':
                raise RuntimeError('Native HKS pantheon choice guards failed')
            self._pantheon_guard_verified = True
            self.emit('native_hks_pantheon_guards_verified', scope='Protected candidate/revalidation/effect collectors against Lua doubles', native_pantheon_founded=False, eligible_for_training=False)
        turn = int(self.runtime.evaluate_text(self.ui_child, b'return tostring(Game.GetCurrentGameTurn())', b'@native_pantheon_turn'))
        catalog = parse_catalog(self.runtime.evaluate_text(self.ui_child, catalog_source(player_id, turn), b'@native_pantheon_catalog', capacity=131072), player_id, turn)
        self.emit('native_pantheon_catalog_observed', **catalog, eligible_for_training=False)
        if catalog['status'] == 'not_due':
            if selected_index is not None:
                raise RuntimeError('Explicit pantheon choice is not currently due')
            self.emit('native_pantheon_choice_not_due', player_id=player_id, current_game_turn=turn, reason=catalog['reason'], request_invoked=False, endturn_gate_still_required=True, eligible_for_training=False)
            return
        if not catalog['choices']:
            raise RuntimeError('Native pantheon creation is due but no selectable belief exists')
        candidate = choose(catalog, catalog['choices'][0]['index'] if selected_index is None else selected_index)
        self.emit('native_pantheon_candidate', **candidate, eligible_for_training=False)
        checked = parse_revalidated_choice(self.runtime.evaluate_text(self.ui_child, revalidate_choice_source(candidate), b'@native_pantheon_revalidation'), candidate)
        result = request_player_operation(self.core, self.context, player_id, checked['operation'], checked['parameters'])
        self.emit('native_player_operation_request_returned', kind='pantheon', **result)
        if not result['can_start'] or not result['request_invoked']:
            raise RuntimeError('Native CanStartPlayerOperation refused pantheon creation')
        if len(self.actions.pending) != 1 or self.actions.pending[0][:4] != struct.pack('<I', 3294486831):
            raise RuntimeError('Pantheon request did not emit exactly one native operation archive')
        self.actions.deliver_one()
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        after = parse_effect(self.runtime.evaluate_text(self.ui_child, effect_source(candidate), b'@native_pantheon_effect'), candidate)
        if not after['confirmed']:
            raise RuntimeError(f'Native pantheon effect differs after delivery: {after!r}')
        self.emit('native_pantheon_effect_verified', player_id=player_id, current_game_turn=turn, selected_index=candidate['selected_index'], selected_hash=candidate['selected_hash'], after=after, native_rules_used=True, eligible_for_training=False)
        return after

    def inspect_great_person_choice(self, player_id, *, selected_individual=None):
        """Recruit a native-admitted individual and observe its grant transition."""
        import struct
        from civ6_host.runtime.native.native_great_people_actions import catalog_source
        from civ6_host.runtime.native.native_great_people_actions import parse_catalog
        from civ6_host.runtime.native.native_great_people_actions import choose
        from civ6_host.runtime.native.native_great_people_actions import revalidate_choice_source
        from civ6_host.runtime.native.native_great_people_actions import parse_revalidated_choice
        from civ6_host.runtime.native.native_great_people_actions import effect_source
        from civ6_host.runtime.native.native_great_people_actions import parse_effect
        from civ6_host.runtime.native.native_great_people_actions import guard_case
        from civ6_host.runtime.native.native_player_operation_request import request_player_operation
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Great-person choice requires a published UI view and drained queues')
        if not getattr(self, '_great_people_guard_verified', False):
            if self.runtime.evaluate_text(self.ui_child, guard_case(), b'@native_great_people_guards') != b'great-people-guards-ok':
                raise RuntimeError('Native HKS great-person choice guards failed')
            self._great_people_guard_verified = True
            self.emit('native_hks_great_people_guards_verified', scope='Protected candidate/revalidation/effect collectors against Lua doubles', native_person_recruited=False, eligible_for_training=False)
        turn = int(self.runtime.evaluate_text(self.ui_child, b'return tostring(Game.GetCurrentGameTurn())', b'@native_great_people_turn'))
        catalog = parse_catalog(self.runtime.evaluate_text(self.ui_child, catalog_source(player_id, turn), b'@native_great_people_catalog', capacity=131072), player_id, turn)
        self.emit('native_great_people_catalog_observed', **catalog, eligible_for_training=False)
        if catalog['status'] == 'not_due':
            if selected_individual is not None:
                raise RuntimeError('Explicit great-person choice is not currently due')
            self.emit('native_great_person_choice_not_due', player_id=player_id, current_game_turn=turn, reason=catalog['reason'], request_invoked=False, endturn_gate_still_required=True, eligible_for_training=False)
            return None
        if not catalog['choices']:
            raise RuntimeError('Great-person catalog has no selectable individual')
        individual = catalog['choices'][0]['individual'] if selected_individual is None else selected_individual
        candidate = choose(catalog, individual)
        self.emit('native_great_person_candidate', **candidate, selection_policy='first-native-candidate' if selected_individual is None else 'explicit', eligible_for_training=False)
        before = parse_effect(self.runtime.evaluate_text(self.ui_child, effect_source(candidate), b'@native_great_people_before'), candidate)
        self.emit('native_great_person_before_observed', **before, eligible_for_training=False)
        if before['status'] != 'pending' or before['confirmed'] or before['current_present'] is not True or (before['past_present'] is not False):
            raise RuntimeError('Selected Great Person has no pending current-timeline state')
        checked = parse_revalidated_choice(self.runtime.evaluate_text(self.ui_child, revalidate_choice_source(candidate), b'@native_great_people_revalidation'), candidate)
        result = request_player_operation(self.core, self.context, player_id, checked['operation'], checked['parameters'])
        self.emit('native_player_operation_request_returned', kind='recruit-great-person', **result)
        if not result['can_start'] or not result['request_invoked']:
            raise RuntimeError('Native CanStartPlayerOperation refused great-person recruitment')
        if len(self.actions.pending) != 1 or self.actions.pending[0][:4] != struct.pack('<I', 3294486831):
            raise RuntimeError('Great-person request did not emit exactly one native operation archive')
        self.actions.deliver_one()
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        after = parse_effect(self.runtime.evaluate_text(self.ui_child, effect_source(candidate), b'@native_great_people_effect'), candidate)
        if not after['confirmed']:
            raise RuntimeError(f'Native great-person effect differs after delivery: {after!r}')
        self.emit('native_great_person_effect_verified', player_id=player_id, current_game_turn=turn, selected_individual=candidate['selected_individual'], before=before, after=after, native_rules_used=True, eligible_for_training=False)
        return after

    def inspect_player_research_choice(self, player_id, kind, *, selected_index=None, submit_preselected=False):
        """Request a native player operation and verify its resulting choice."""
        import struct
        from civ6_host.runtime.native.native_research_actions import effect_source
        from civ6_host.runtime.native.native_research_actions import parse_effect
        from civ6_host.runtime.native.native_research_catalog import catalog_source
        from civ6_host.runtime.native.native_research_catalog import parse_catalog
        from civ6_host.runtime.native.native_research_catalog import choose
        from civ6_host.runtime.native.native_research_catalog import revalidate_choice_source
        from civ6_host.runtime.native.native_research_catalog import parse_revalidated_choice
        from civ6_host.runtime.native.native_player_operation_request import request_player_operation
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Player operation requires a current UI view and drained queues')
        turn = int(self.runtime.evaluate_text(self.ui_child, b'return tostring(Game.GetCurrentGameTurn())', b'@native_research_turn'))
        catalog = parse_catalog(self.runtime.evaluate_text(self.ui_child, catalog_source(player_id, kind, turn, core_sha256=getattr(self, 'operation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')), b'@native_research_catalog', capacity=131072), player_id, kind, turn)
        self.emit('native_player_research_catalog_observed', **catalog, complete_game_action_space=False, eligible_for_training=False)
        if not catalog['choices']:
            raise RuntimeError(f'No native {kind} candidate in this diagnostic')
        if selected_index is None and kind == 'research' and (self.diagnostic_production_policy in ('native-placement', 'native-development')):
            priority = int(self.runtime.evaluate_text(self.ui_child, b"return string.format('%.0f',GameInfo.Technologies.TECH_ASTROLOGY.Index)", b'@placement_diagnostic_research_priority'))
            if any((row['index'] == priority for row in catalog['choices'])):
                selected_index = priority
            self.emit('native_placement_diagnostic_research_priority', player_id=player_id, priority_technology='TECH_ASTROLOGY', priority_index=priority, currently_legal=selected_index is not None, rule_state_granted=False, eligible_for_training=False)
        candidate = choose(catalog, catalog['choices'][0]['index'] if selected_index is None else selected_index)
        source = effect_source(player_id, kind, candidate['selected_index'], core_sha256=getattr(self, 'operation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
        before = parse_effect(self.runtime.evaluate_text(self.ui_child, source, b'@native_research_before'), player_id, kind, candidate['selected_index'], turn)
        if before['confirmed'] and (not submit_preselected):
            self.emit('native_player_research_preselected_observed', **candidate, before=before, request_invoked=False, selection_change_verified=False, eligible_for_training=False)
            return
        self.emit('native_player_research_candidate', **candidate, before=before, eligible_for_training=False)
        revalidated = parse_revalidated_choice(self.runtime.evaluate_text(self.ui_child, revalidate_choice_source(candidate, core_sha256=getattr(self, 'operation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3')), b'@native_research_revalidation'), candidate)
        result = request_player_operation(self.core, self.context, player_id, revalidated['operation'], revalidated['parameters'], core_sha256=getattr(self, 'operation_core_sha256', 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
        self.emit('native_player_operation_request_returned', kind=kind, **result)
        if not result['can_start'] or not result['request_invoked']:
            raise RuntimeError(f'Native CanStartPlayerOperation refused {kind}')
        if len(self.actions.pending) != 1 or self.actions.pending[0][:4] != struct.pack('<I', 3294486831):
            raise RuntimeError('Player operation did not emit exactly one native operation archive')
        self.actions.deliver_one()
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        after = parse_effect(self.runtime.evaluate_text(self.ui_child, source, b'@native_research_after'), player_id, kind, candidate['selected_index'], turn)
        if not after['confirmed']:
            raise RuntimeError(f'Native {kind} selection differs after delivery: {after!r}')
        self.emit('native_player_research_effect_verified', kind=kind, player_id=player_id, before=before, after=after, selected_hash=candidate['selected_hash'], native_rules_used=True, eligible_for_training=False)

    def inspect_found_city(self, player_id, *, unit_id=None, expected_x=None, expected_y=None):
        """Submit a Core-admitted city foundation through the UI operation API.

        This remains an isolated diagnostic, never an unverified RL transition.
        The city and consumed settler are checked through public UI state after
        native dispatch and cache publication; no entity is created by Python.
        """
        from civ6_host.runtime.native.native_unit_actions import found_city_candidate_source
        from civ6_host.runtime.native.native_unit_actions import request_found_city_source
        from civ6_host.runtime.native.native_unit_actions import _identifier
        requested_id = unit_id
        if requested_id is not None:
            _identifier(requested_id, 'unit ID', 4294967295)
            _identifier(expected_x, 'founder x', 65535)
            _identifier(expected_y, 'founder y', 65535)
        elif expected_x is not None or expected_y is not None:
            raise ValueError('Explicit foundation needs unit ID and both coordinates')
        if self.ui_child is None:
            raise RuntimeError('A native UI observation context is required before acting')
        candidate = self.runtime.evaluate_text(self.ui_child, found_city_candidate_source(player_id, requested_id), b'@native_found_city_legality')
        if candidate == b'none':
            raise RuntimeError('Native legality admitted no city foundation in this diagnostic')
        owner, unit_id, unit_type, x, y = map(int, candidate.decode('ascii').split(','))
        if owner != player_id:
            raise RuntimeError('Native action candidate owner changed')
        if requested_id is not None and (unit_id, x, y) != (requested_id, expected_x, expected_y):
            raise RuntimeError('Selected founder or site changed before submission')
        count_before = len(self.actions.pending)
        if count_before:
            raise RuntimeError('Native command queue must be empty before one-action diagnostic')
        self.emit('native_found_city_candidate', player_id=owner, unit_id=unit_id, unit_type=unit_type, x=x, y=y, legality_source='native UnitManager.CanStartOperation', action_applied=False, eligible_for_training=False)
        result = self.runtime.evaluate_text(self.ui_child, request_found_city_source(owner, unit_id), b'@native_found_city_request')
        if result != b'submitted' or len(self.actions.pending) != 1:
            raise RuntimeError('Native city request did not serialize exactly one command')
        self.actions.deliver_one()
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        witness = b'local p=Players[' + str(owner).encode() + b']\nlocal unitPresent=false\nfor _,u in p:GetUnits():Members() do\n  if u:GetID()==' + str(unit_id).encode() + b' then unitPresent=true end\nend\nlocal found=nil\nfor _,c in p:GetCities():Members() do\n  if c:GetX()==' + str(x).encode() + b' and c:GetY()==' + str(y).encode() + b" then\n    assert(found==nil,'duplicate city at target'); found=c\n  end\nend\nassert(not unitPresent and found~=nil,'native city foundation effect is absent')\nreturn string.format('%d,%d,%d,%d',found:GetID(),found:GetX(),found:GetY(),found:GetPopulation())\n"
        city_id, cx, cy, population = map(int, self.runtime.evaluate_text(self.ui_child, witness, b'@native_found_city_effect').decode('ascii').split(','))
        self.emit('native_found_city_effect_verified', player_id=owner, consumed_unit_id=unit_id, city_id=city_id, x=cx, y=cy, population=population, native_rules_used=True, eligible_for_training=False)
        return dict(player_id=owner, consumed_unit_id=unit_id, city_id=city_id, x=cx, y=cy, population=population)

    def inspect_clear_unit_decisions(self, player_id):
        blockers = self.inspect_skip_units(player_id)
        if blockers['has_primary_blocker'] or blockers['all']:
            raise RuntimeError(f'Native player decisions remain unresolved: {blockers!r}')
        self.inspect_city_range_attack_notification(player_id, blockers['turn'])
        self.emit('native_endturn_unit_decisions_cleared', player_id=player_id, blockers=blockers, normal_end_turn_legality_verified=False, eligible_for_training=False)
        from civ6_host.runtime.native.native_endturn_gate import gate_source
        from civ6_host.runtime.native.native_endturn_gate import parse_gate
        if self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('End-turn decision gate requires drained host queues')
        result = parse_gate(self.runtime.evaluate_text(self.ui_child, gate_source(player_id), b'@native_manual_endturn_decision_gate'), player_id, blockers['turn'])
        self.emit('native_manual_endturn_decision_gate_verified', **result, host_command_and_deferred_queues_empty=True)

    def inspect_city_range_attack_notification(self, player_id, expected_turn):
        """Resolve one genuinely active city ranged-attack prompt diagnostically."""
        from civ6_host.runtime.native import native_city_range_attack as attack
        from civ6_host.runtime.native.native_player_observation import observe_player
        if type(player_id) is not int or player_id not in (0, 1) or type(expected_turn) is not int or (expected_turn < 0):
            raise ValueError('City ranged-attack player/turn is outside the development profile')
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('City ranged attack requires UI child and drained host queues')
        if getattr(self.actions, '_city_range_attack_producing', False) or getattr(self.actions, '_city_range_attack_poisoned', False):
            raise RuntimeError('City ranged-attack owner is busy or poisoned')
        pins = attack.verify_inputs()
        status = attack.parse_notification_status(self.runtime.evaluate_text(self.ui_child, attack.notification_status_source(player_id), b'@native_city_range_notification_status', capacity=4096), player_id=player_id, turn=expected_turn)
        if status == 'none':
            return None
        if status == 'dismissed':
            self.emit('native_city_range_attack_notification_dismissed', player_id=player_id, turn=expected_turn, notification_present=True, notification_status='dismissed', request_submitted=False, source_pins=pins, eligible_for_training=False)
            return None
        observation = observe_player(self.runtime, self.ui_child, player_id)
        if observation['turn'] != expected_turn:
            raise RuntimeError('City-attack observation turn changed')
        catalog = attack.parse_catalog(self.runtime.evaluate_text(self.ui_child, attack.catalog_source(player_id, observation['visible_enemy_units']), b'@native_city_range_attack_candidates', capacity=262144), player_id)
        if catalog['turn'] != expected_turn:
            raise RuntimeError('City-attack candidate catalog is stale')
        if not catalog['candidates']:
            self.emit('native_city_range_attack_not_attempted', player_id=player_id, turn=expected_turn, notification_status='active', request_submitted=False, reason='no_visible_native_legal_target', source_pins=pins, eligible_for_training=False)
            raise RuntimeError('Active city-attack notification has no visible native-legal candidate')
        candidate = min(catalog['candidates'], key=lambda row: (row['city_id'], row['target_owner'], row['target_unit_id'], row['x'], row['y']))
        result = attack.submit_deliver_publish_readback(self.runtime, self.ui_child, self.actions, self.deferred_events, self.view_publisher, player_id, expected_turn, candidate)
        self.emit('native_city_range_attack_effect_verified', candidate=candidate, source_pins=pins, action_profile='one native-legal visible target per confirmed attempt; deterministic diagnostic ordering', **result)
        return result

    def inspect_skip_units(self, player_id):
        """Resolve ready units with real native requests, then reread blockers."""
        from civ6_host.runtime.native.native_unit_skip import candidate_source
        from civ6_host.runtime.native.native_unit_skip import request_source
        from civ6_host.runtime.native.native_unit_skip import effect_source
        from civ6_host.runtime.native.native_unit_skip import parse_candidate
        from civ6_host.runtime.native.native_unit_skip import parse_effect
        from civ6_host.runtime.native.native_turn_decisions import blocker_source
        from civ6_host.runtime.native.native_turn_decisions import parse_blockers
        from civ6_host.runtime.native.native_diagnostic_traffic import unit_order_budget_source
        from civ6_host.runtime.native.native_diagnostic_traffic import parse_unit_order_budget
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Skip-unit diagnostic needs a UI view and empty command queue')
        budget = parse_unit_order_budget(self.runtime.evaluate_text(self.ui_child, unit_order_budget_source(player_id), b'@native_unit_order_budget'), player_id)
        self.emit('native_diagnostic_unit_order_budget', **budget, gameplay_rules_modified=False, eligible_for_training=False)
        seen = set()
        movement_actions = 0
        skip_actions = 0
        for _ in range(budget['action_budget']):
            candidate = parse_candidate(self.runtime.evaluate_text(self.ui_child, candidate_source(player_id), b'@native_skip_unit_candidate'), player_id)
            if candidate is None:
                remaining = self.runtime.evaluate_text(self.ui_child, b'local p=Players[' + str(player_id).encode() + b']\nassert(p and Game.GetLocalPlayer()==' + str(player_id).encode() + b",'unit perspective changed')\nlocal u=p:GetUnits():GetFirstReadyUnit()\nif u==nil then return 'none' end\nassert(u:GetOwner()==Game.GetLocalPlayer(),'foreign ready unit')\nreturn tostring(u:GetID())\n", b'@native_ready_unit_exhaustion')
                if remaining != b'none':
                    unit_id = int(remaining)
                    self.emit('native_diagnostic_policy_move_without_skip_candidate', player_id=player_id, unit_id=unit_id, no_skip_candidate=True, native_legality_override=False, eligible_for_training=False)
                    effect = self.inspect_unit_movement(player_id, unit_id=unit_id, resolve_friendly_blockage=True)
                    seen.discard(effect['unit_id'])
                    movement_actions += 1
                    continue
                break
            owner, unit_id = candidate
            if unit_id in seen or self.actions.pending:
                raise RuntimeError('Native skip selected a previous unit or found a pending command')
            result = self.runtime.evaluate_text(self.ui_child, request_source(owner, unit_id), b'@native_skip_unit_request')
            if result != b'submitted' or len(self.actions.pending) != 1:
                raise RuntimeError('Native skip request did not serialize exactly one command')
            self.actions.deliver_one()
            self.deferred_events.drain_empty_receivers()
            self.view_publisher.publish()
            effect = parse_effect(self.runtime.evaluate_text(self.ui_child, effect_source(owner, unit_id), b'@native_skip_unit_effect'), unit_id)
            if effect['ready'] is not False or effect['first_ready_id'] == unit_id:
                raise RuntimeError(f'Native skip unit effect is absent: {effect!r}')
            seen.add(unit_id)
            skip_actions += 1
            self.emit('native_skip_unit_effect_verified', player_id=owner, unit_id=unit_id, **effect, native_rules_used=True, eligible_for_training=False)
        else:
            raise RuntimeError(f"Native unit-order diagnostic exceeded {budget['action_budget']} bounded attempts")
        state = self.inspect_player_view()
        blockers = parse_blockers(self.runtime.evaluate_text(self.ui_child, blocker_source(player_id), b'@native_blockers_after_unit_orders'), player_id, state['current_game_turn'])
        self.emit('native_unit_orders_resolved', player_id=player_id, units_skipped=skip_actions, units_movement_actions=movement_actions, blockers=blockers, normal_end_turn_legality_verified=False, eligible_for_training=False)
        return blockers

    def inspect_production_catalog_choice(self, player_id, *, require_candidate=True):
        """Choose a native-admitted production and verify the applied queue.

        This is an explicit diagnostic policy. Purchases, formations and editing
        occupied queues remain reported gaps, never training-ready.
        """
        from civ6_host.runtime.native.native_production_catalog import catalog_source
        from civ6_host.runtime.native.native_production_catalog import parse_catalog
        from civ6_host.runtime.native.native_production_catalog import choose
        from civ6_host.runtime.native.native_production_catalog import request_source
        from civ6_host.runtime.native.native_production_catalog import guard_case
        from civ6_host.runtime.native.native_production_catalog import PROOF_SHA256
        from civ6_host.runtime.native.native_player_observation import build_player_observation_source
        from civ6_host.runtime.native.native_player_observation import parse_player_observation
        from civ6_host.runtime.native.native_city_production_observation import production_snapshot_source
        from civ6_host.runtime.native.native_city_production_observation import parse_production_snapshot
        from civ6_host.runtime.native import native_production_placement as placement
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Production selection requires a current player view and drained queues')
        if not getattr(self, '_production_catalog_guards_verified', False):
            guard = self.runtime.evaluate_text(self.ui_child, guard_case(), b'@production_catalog_guards')
            if guard != b'native-production-catalog-guards-ok':
                raise RuntimeError('Native HKS production catalog guards failed')
            self._production_catalog_guards_verified = True
            self.emit('native_hks_production_catalog_guards_verified', native_gameplay_mutated=False, eligible_for_training=False)
        if not getattr(self, '_production_placement_guards_verified', False):
            guard = self.runtime.evaluate_text(self.ui_child, placement.guard_case(), b'@production_placement_guards')
            if guard != b'native-production-placement-guards-ok':
                raise RuntimeError('Native HKS placement guards failed')
            self._production_placement_guards_verified = True
            self.emit('native_hks_production_placement_guards_verified', native_gameplay_mutated=False, eligible_for_training=False)
        header = parse_player_observation(self.runtime.evaluate_text(self.ui_child, build_player_observation_source(player_id), b'@production_owned_cities'), player_id)
        turn = header['turn']
        self.inspect_district_completion(player_id, turn)
        self.inspect_wonder_completion(player_id, turn)
        applied = 0
        for city_id in sorted((city['id'] for city in header['cities'])):
            paired = b'local observation=(function()\n' + build_player_observation_source(player_id) + b'\nend)(); local catalog=(function()\n' + catalog_source(player_id, city_id, turn) + b'\nend)(); local placements=(function()\n' + placement.catalog_source(player_id, city_id, turn) + b'\nend)(); return observation.."\\n"..catalog.."\\n"..placements'
            observation_bytes, catalog_bytes, placement_bytes = self.runtime.evaluate_text(self.ui_child, paired, b'@native_production_decision_input').split(b'\n')
            observation = parse_player_observation(observation_bytes, player_id)
            if observation['turn'] != turn:
                raise RuntimeError('Production observation changed turn during candidate query')
            catalog = parse_catalog(catalog_bytes, player_id, city_id, turn)
            placed_catalog = placement.parse_catalog(placement_bytes, player_id, city_id, turn)
            if placed_catalog['status'] != catalog['status'] or placed_catalog['width'] != observation['width'] or placed_catalog['height'] != observation['height']:
                raise RuntimeError('Placement and production catalogues disagree on context')
            self.emit('native_production_catalog_observed', catalog=catalog, source_proof_sha256=PROOF_SHA256, complete_action_space=False, eligible_for_training=False)
            self.emit('native_production_placement_catalog_observed', catalog=placed_catalog, source_proof_sha256=placement.PROOF_SHA256, complete_action_space=False, eligible_for_training=False)
            if catalog['status'] == 'queue_nonempty' or not (catalog['candidates'] or placed_catalog['candidates']):
                continue
            candidates = []
            members = {}
            for row in catalog['candidates']:
                identity = f"produce-{player_id}-{city_id}-{row['kind']}-{row['index']}"
                if identity in members:
                    raise RuntimeError('Duplicate production candidate identity')
                members[identity] = row
                candidates.append({'candidate_id': identity, 'action': {'kind': 'choose_production', 'city_id': city_id, 'category': row['kind'], 'item_index': row['index'], 'item_hash': row['hash'], 'item_type': row['item_type']}})
            for row in placed_catalog['candidates']:
                identity = f"produce-{player_id}-{city_id}-{row['kind']}-{row['index']}-{row['mode']}-{row['plot_id']}"
                if identity in members:
                    raise RuntimeError('Duplicate production placement candidate identity')
                members[identity] = row
                candidates.append({'candidate_id': identity, 'action': {'kind': 'choose_production', 'city_id': city_id, 'category': row['kind'], 'item_index': row['index'], 'item_hash': row['hash'], 'item_type': row['item_type'], 'placement_mode': row['mode'], 'plot_id': row['plot_id'], 'x': row['x'], 'y': row['y']}})
            if len(candidates) > 256:
                raise RuntimeError('Combined production catalogue exceeds bound; refusing truncation')
            event = {'stage': 'native_diagnostic_decision_input', 'player_id': player_id, 'observation': observation, 'candidates': candidates, 'same_protected_query': True, 'applied_before_observation': False, 'complete_player_observation': False, 'complete_action_space': False, 'exposed_to_learner': False, 'eligible_for_training': False}
            self.emit(event['stage'], **{k: v for k, v in event.items() if k != 'stage'})
            if self.diagnostic_production_policy == 'native-first':
                selected = candidates[0]['candidate_id']
            elif self.diagnostic_production_policy == 'native-placement':
                ranked = sorted(candidates, key=lambda c: (0 if c['action'].get('placement_mode') == 'place' else 1 if c['action'].get('item_type') == 'UNIT_SCOUT' else 2, c['candidate_id']))
                selected = ranked[0]['candidate_id']
            elif self.diagnostic_production_policy == 'native-development':
                from civ6_host.runtime.native.native_diagnostic_production import select_development
                selected = select_development(candidates)
            elif self.diagnostic_production_policy in ('mac-cpu', 'mac-mps'):
                if self.mac_chooser is None:
                    raise RuntimeError('Embedded diagnostic policies are not part of the host; use explicit client choices')
                    from civ6_host.runtime.native.native_episode_identity import require_episode
                    identity = require_episode(self)
                    self.mac_chooser = NativeDiagnosticMacChooser(self.emit, device=self.diagnostic_production_policy[4:], max_requests=128, game_generation=identity.game_generation, episode_id=identity.episode_id)
                selected = self.mac_chooser.select(event)
            else:
                raise RuntimeError('Catalog requested without an explicit production selector')
            if selected not in members:
                raise RuntimeError('Production selector returned an unapproved candidate')
            row = members[selected]
            is_placement = 'mode' in row
            choice = placement.choose(placed_catalog, row['kind'], row['index'], row['plot_id']) if is_placement else choose(catalog, row['kind'], row['index'])
            self.emit('native_production_catalog_choice_selected', candidate_id=selected, choice=choice, policy=self.diagnostic_production_policy, game_action_applied=False, eligible_for_training=False)
            result = self.runtime.evaluate_text(self.ui_child, placement.request_source(choice) if is_placement else request_source(choice), b'@native_production_choice_request')
            if result != b'submitted' or len(self.actions.pending) != 1:
                raise RuntimeError('Production choice did not serialize exactly one native command')
            self.actions.deliver_one()
            self.deferred_events.drain_empty_receivers()
            self.view_publisher.publish()
            effect = parse_production_snapshot(self.runtime.evaluate_text(self.ui_child, production_snapshot_source(player_id), b'@native_production_choice_effect'), player_id)
            city_rows = [city for city in effect['cities'] if city['city_id'] == city_id]
            if len(city_rows) != 1 or effect['game_turn'] != turn:
                raise RuntimeError('Production effect is for another city or turn')
            city = city_rows[0]
            if city['queue_size'] != 1 or city['current_production_hash'] & 4294967295 != choice['hash']:
                raise RuntimeError('Native production queue does not match the selected candidate')
            expected_kind = {'unit': 'U', 'building': 'B', 'project': 'P', 'district': 'D'}[choice['kind']]
            if city['kind'] != expected_kind or city['item_index'] != choice['index']:
                raise RuntimeError('Native production readback changed item kind or index')
            placement_effect = None
            if is_placement:
                placement_effect = placement.parse_effect(self.runtime.evaluate_text(self.ui_child, placement.effect_source(choice), b'@native_production_placement_effect'), choice)
            applied += 1
            self.emit('native_production_catalog_choice_effect_verified', candidate_id=selected, player_id=player_id, city_id=city_id, turn=turn, policy=self.diagnostic_production_policy, production=city, placement=placement_effect, game_action_applied=True, item_completed=False, native_rules_used=True, eligible_for_training=False)
            if is_placement and choice['kind'] == 'district' and (choice['mode'] == 'place'):
                key = (player_id, city_id, choice['plot_id'])
                tracked = getattr(self, '_placed_district_choices', {})
                if key in tracked or len(tracked) >= 256:
                    raise RuntimeError('Duplicate or excessive tracked district placements')
                tracked[key] = choice.copy()
                self._placed_district_choices = tracked
                self.inspect_district_completion(player_id, turn)
            if is_placement and choice['kind'] == 'building' and (choice['mode'] == 'place'):
                key = (player_id, city_id, choice['plot_id'])
                tracked = getattr(self, '_placed_wonder_choices', {})
                if key in tracked or len(tracked) >= 256:
                    raise RuntimeError('Duplicate or excessive tracked wonder placements')
                tracked[key] = choice.copy()
                self._placed_wonder_choices = tracked
                self.inspect_wonder_completion(player_id, turn)
        if require_candidate and (not applied):
            raise RuntimeError('No supported legal production for this required diagnostic decision')
        return applied

    def inspect_district_completion(self, player_id, turn):
        """Observe previously placed districts using the native Boolean getter.

        This readback stays in the owning player's active, published view. It
        neither advances production nor interprets a queue or boost as completion.
        """
        from civ6_host.runtime.native import native_district_completion as completion
        tracked = getattr(self, '_placed_district_choices', {})
        choices = [tracked[k] for k in sorted(tracked) if k[0] == player_id]
        if not choices:
            return
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('District readback requires drained queues and a current player view')
        if not getattr(self, '_district_completion_guards_verified', False):
            marker = self.runtime.evaluate_text(self.ui_child, completion.guard_case(), b'@district_completion_guards')
            if marker != b'native-district-completion-guards-ok':
                raise RuntimeError('Native HKS district completion guards failed')
            self._district_completion_guards_verified = True
            self.emit('native_hks_district_completion_guards_verified', native_gameplay_mutated=False, eligible_for_training=False)
        previous = getattr(self, '_district_completion_observations', {})
        for choice in choices:
            result = completion.parse_readback(self.runtime.evaluate_text(self.ui_child, completion.readback_source(choice, turn), b'@native_district_completion'), choice, turn)
            key = (player_id, choice['city_id'], choice['plot_id'])
            self.emit('native_district_completion_observed', observation=result, previous_native_is_complete=previous.get(key), source_proof_sha256=completion.PROOF_SHA256, native_gameplay_mutated=False, eligible_for_training=False)
            previous[key] = result['native_is_complete']
        self._district_completion_observations = previous

    def inspect_government_choice(self, player_id, *, selected_index=None):
        """Submit one explicit native government choice and verify adoption.

        Without a caller choice, the diagnostic selects the lowest-index legal
        government requiring no anarchy. Other rows stay in the recorded
        catalogue; an explicit unsupported or illegal choice is never replaced.
        """
        import struct
        from civ6_host.runtime.native import native_government_actions as government
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Government choice requires a current view and drained queues')
        if not getattr(self, '_government_action_guards_verified', False):
            marker = self.runtime.evaluate_text(self.ui_child, government.guard_case(), b'@government_action_guards')
            if marker != b'government-action-guards-ok':
                raise RuntimeError('Native HKS government action guards failed')
            self._government_action_guards_verified = True
            self.emit('native_hks_government_action_guards_verified', native_gameplay_mutated=False, eligible_for_training=False)
        turn = int(self.runtime.evaluate_text(self.ui_child, b'return string.format("%.0f",Game.GetCurrentGameTurn())', b'@native_government_turn'))
        catalog = government.parse_catalog(self.runtime.evaluate_text(self.ui_child, government.catalog_source(player_id, turn), b'@native_government_catalog', capacity=16384), player_id, turn)
        self.emit('native_government_catalog_observed', catalog=catalog, complete_government_action_space=False, eligible_for_training=False)
        global_gate = catalog['can_change_government_at_all'] and (not catalog['government_change_made']) and (catalog['current_government_index'] == -1 or catalog['civic_completed_this_turn'])
        if not global_gate:
            if selected_index is not None:
                raise RuntimeError('Explicit government choice is unavailable in the native change window')
            return None
        explicit_choice = selected_index is not None
        if selected_index is None:
            ordinary = [r for r in catalog['choices'] if r['unlocked'] and r['can_change'] and (not r['requires_anarchy_path']) and (r['index'] != catalog['current_government_index'])]
            if not ordinary:
                self.emit('native_government_diagnostic_no_direct_choice', player_id=player_id, current_game_turn=turn, anarchy_choices_not_reclassified_as_illegal=True, eligible_for_training=False)
                return None
            selected_index = min((r['index'] for r in ordinary))
        choice = government.choose(catalog, selected_index)
        checked = government.parse_revalidated_choice(self.runtime.evaluate_text(self.ui_child, government.revalidate_choice_source(choice), b'@native_government_revalidation'), choice)
        before = government.parse_effect(self.runtime.evaluate_text(self.ui_child, government.effect_source(choice), b'@native_government_effect_before'), choice)
        if before['confirmed'] or before['government_change_made'] or before['current_government_index'] != choice['current_government_index']:
            raise RuntimeError('Government choice has no verified unmodified starting state')
        self.emit('native_government_choice_selected', choice=choice, policy='explicit' if explicit_choice else 'native-first-direct', request_revalidated=checked['valid'], eligible_for_training=False)
        submitted = government.parse_request_result(self.runtime.evaluate_text(self.ui_child, government.request_source(choice), b'@native_government_request'), choice)
        if len(self.actions.pending) != 1:
            raise RuntimeError('Government request archive differs from the admitted single-packet profile')
        government.validate_native_archive(self.actions.pending[0], choice)
        self.emit('native_government_archive_verified', choice=choice, archive_hex=self.actions.pending[0].hex(), archive_fabricated=False, transport_proof_sha256=government.TRANSPORT_PROOF_SHA256, submitted=submitted['submitted'], action_effect_verified=False, eligible_for_training=False)
        self.actions.deliver_one()
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        after = government.parse_effect(self.runtime.evaluate_text(self.ui_child, government.effect_source(choice), b'@native_government_effect_after'), choice)
        if not after['confirmed']:
            raise RuntimeError('Native government adoption did not match the requested choice')
        self.emit('native_government_change_effect_verified', choice=choice, before=before, after=after, source_proof_sha256=government.PINNED_EVIDENCE_SHA256, policy_slots_resolved=False, complete_government_action_space=False, native_rules_used=True, eligible_for_training=False)
        return after

    def inspect_government_consideration(self, player_id):
        """Explicit diagnostic choice to retain a current government.

        The official government panel acknowledges consideration even when the
        player selects no replacement. This action uses that public setter and
        verifies both its live flag and the native end-turn blocker afterwards.
        It does not supply a complete government selection action catalogue.
        """
        from civ6_host.runtime.native import native_government_consideration as government
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Government consideration requires a current view and drained queues')
        if not getattr(self, '_government_consideration_guards_verified', False):
            marker = self.runtime.evaluate_text(self.ui_child, government.guard_case(), b'@government_consideration_guards')
            if marker != b'government-consideration-guards-ok':
                raise RuntimeError('Native HKS government consideration guards failed')
            self._government_consideration_guards_verified = True
            self.emit('native_hks_government_consideration_guards_verified', native_gameplay_mutated=False, eligible_for_training=False)
        turn = int(self.runtime.evaluate_text(self.ui_child, b'return string.format("%.0f",Game.GetCurrentGameTurn())', b'@native_government_consideration_turn'))
        before = government.parse_readback(self.runtime.evaluate_text(self.ui_child, government.readback_source(player_id, turn), b'@native_government_consideration_before'), player_id, turn)
        self.emit('native_government_consideration_observed', observation=before, native_gameplay_mutated=False, eligible_for_training=False)
        if not before['consideration_blocker_present']:
            return None
        if before['considered'] or before['government_index'] < 0:
            raise RuntimeError('Native consideration blocker has an unsupported current state')
        self.emit('native_government_consideration_choice_selected', player_id=player_id, current_game_turn=turn, government_index=before['government_index'], diagnostic_choice='retain_current_government', complete_government_action_space=False, eligible_for_training=False)
        submitted = government.parse_request_result(self.runtime.evaluate_text(self.ui_child, government.request_source(player_id, turn, before['government_index']), b'@native_government_consideration_request'), player_id, turn, before['government_index'])
        if self.actions.pending:
            raise RuntimeError('Consideration setter unexpectedly serialized an action')
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        after = government.parse_readback(self.runtime.evaluate_text(self.ui_child, government.readback_source(player_id, turn), b'@native_government_consideration_after'), player_id, turn)
        if not after['considered'] or after['consideration_blocker_present'] or after['government_index'] != before['government_index']:
            raise RuntimeError('Native government consideration effect was not verified')
        self.emit('native_government_consideration_effect_verified', before=before, after=after, setter_readback=submitted, government_changed=False, diagnostic_choice='retain_current_government', source_proof_sha256=government.PINNED_EVIDENCE_SHA256, native_rules_used=True, complete_government_action_space=False, eligible_for_training=False)
        return after

    def inspect_episode_facts(self, player_id):
        from civ6_host.runtime.native.native_episode_diagnostic import observe_episode_facts
        return observe_episode_facts(self, player_id)

    def inspect_religion_development(self, player_id):
        from civ6_host.runtime.native.native_religion_diagnostic import develop_religion
        return develop_religion(self, player_id)

    def inspect_own_religion_snapshot(self, player_id):
        """Read only the acting player's religion, after native cache publication."""
        from civ6_host.runtime.native import native_religion_observation as observation
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Religion readback requires drained queues and a current player view')
        if not getattr(self, '_religion_observation_guards_verified', False):
            marker = self.runtime.evaluate_text(self.ui_child, observation.guard_case(), b'@religion_observation_guards')
            if marker != b'native-religion-observation-guards-ok':
                raise RuntimeError('Native HKS religion observation guards failed')
            self._religion_observation_guards_verified = True
            self.emit('native_hks_religion_observation_guards_verified', native_gameplay_mutated=False, eligible_for_training=False)
        turn = int(self.runtime.evaluate_text(self.ui_child, b'return string.format("%.0f",Game.GetCurrentGameTurn())', b'@native_religion_observation_turn'))
        result = observation.parse_observation(self.runtime.evaluate_text(self.ui_child, observation.build_source(player_id, turn), b'@native_own_religion_observation', capacity=observation.MAX_RESPONSE), player_id, turn)
        self.emit('native_own_religion_observed', observation=result, native_gameplay_mutated=False, eligible_for_training=False)
        return result

    def inspect_wonder_completion(self, player_id, turn):
        """Read native building membership after visibility/ownership checks.

        AE/AF notifications and production progress are not completion evidence.
        A cleared placement is recorded separately with no inferred cause.
        """
        from civ6_host.runtime.native import native_wonder_completion as completion
        tracked = getattr(self, '_placed_wonder_choices', {})
        choices = [tracked[k] for k in sorted(tracked) if k[0] == player_id]
        if not choices:
            return
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Wonder readback requires drained queues and a current player view')
        if not getattr(self, '_wonder_completion_guards_verified', False):
            marker = self.runtime.evaluate_text(self.ui_child, completion.guard_case(), b'@wonder_completion_guards')
            if marker != b'native-wonder-completion-guards-ok':
                raise RuntimeError('Native HKS wonder completion guards failed')
            self._wonder_completion_guards_verified = True
            self.emit('native_hks_wonder_completion_guards_verified', native_gameplay_mutated=False, eligible_for_training=False)
        previous = getattr(self, '_wonder_completion_observations', {})
        for choice in choices:
            result = completion.parse_readback(self.runtime.evaluate_text(self.ui_child, completion.readback_source(choice, turn), b'@native_wonder_completion'), choice, turn)
            key = (player_id, choice['city_id'], choice['plot_id'])
            absent = result.get('wonder_absent') is True
            self.emit('native_wonder_absence_observed' if absent else 'native_wonder_completion_observed', observation=result, previous_city_has_building=previous.get(key), source_proof_sha256=completion.ABSENCE_PROOF_SHA256 if absent else completion.PROOF_SHA256, native_gameplay_mutated=False, eligible_for_training=False)
            if absent:
                del tracked[key]
                previous.pop(key, None)
                self.emit('native_wonder_tracking_retired', choice=choice, absence_observation=result, source_proof_sha256=completion.ABSENCE_PROOF_SHA256, native_gameplay_mutated=False, eligible_for_training=False)
            else:
                previous[key] = result['city_has_building']
        self._placed_wonder_choices = tracked
        self._wonder_completion_observations = previous

    def inspect_unit_production(self, player_id, *, require_candidate=True):
        """Verify one native production queue mutation after city foundation."""
        if self.diagnostic_production_policy != 'warrior':
            return self.inspect_production_catalog_choice(player_id, require_candidate=require_candidate)
        from civ6_host.runtime.native.native_city_actions import unit_production_candidate_source
        from civ6_host.runtime.native.native_city_actions import request_unit_production_source
        if self.ui_child is None or self.actions.pending:
            raise RuntimeError('Production diagnostic needs a UI view and empty command queue')
        from civ6_host.runtime.native.native_player_observation import build_player_observation_source
        from civ6_host.runtime.native.native_player_observation import parse_player_observation
        paired = b'local observation=(function()\n' + build_player_observation_source(player_id) + b'\nend)(); local candidate=(function()\n' + unit_production_candidate_source(player_id) + b'\nend)(); return observation.."\\n"..candidate'
        observation_bytes, candidate = self.runtime.evaluate_text(self.ui_child, paired, b'@native_unit_production_decision_input').rsplit(b'\n', 1)
        observation = parse_player_observation(observation_bytes, player_id)
        if candidate == b'none':
            if require_candidate:
                raise RuntimeError('Native legality admitted no warrior production in an empty queue')
            self.emit('native_unit_production_no_candidate', player_id=player_id, request_invoked=False, eligible_for_training=False)
            return
        owner, city_id, unit_index, unit_hash = map(int, candidate.decode('ascii').split(','))
        if owner != player_id or city_id < 0 or unit_index < 0:
            raise RuntimeError('Native production candidate changed owner or identity')
        self.emit('native_unit_production_candidate', player_id=owner, city_id=city_id, unit_index=unit_index, unit_hash=unit_hash, source='Native CityManager.CanStartOperation; native-city-action-route.json', action_applied=False, eligible_for_training=False)
        self.emit('native_diagnostic_decision_input', player_id=owner, observation=observation, candidates=[{'candidate_id': f'produce-{owner}-{city_id}-{unit_index}', 'action': {'kind': 'choose_production', 'city_id': city_id, 'unit_index': unit_index, 'unit_hash': unit_hash}}], source='Native CityManager.CanStartOperation; native-city-action-route.json', same_protected_query=True, applied_before_observation=False, complete_player_observation=False, complete_action_space=False, exposed_to_learner=False, eligible_for_training=False)
        result = self.runtime.evaluate_text(self.ui_child, request_unit_production_source(owner, city_id), b'@native_unit_production_request')
        if result != b'submitted' or len(self.actions.pending) != 1:
            raise RuntimeError('Native production request did not serialize exactly one command')
        self.actions.deliver_one()
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        source = b'local p=Players[' + str(owner).encode() + b']\nlocal found=nil\nfor _,city in p:GetCities():Members() do\n if city:GetID()==' + str(city_id).encode() + b" then\n  assert(found==nil,'duplicate native city ID');found=city\n end\nend\nassert(found~=nil,'native production city disappeared')\nlocal q=found:GetBuildQueue()\nreturn string.format('%d,%d',q:GetSize(),q:GetCurrentProductionTypeHash())\n"
        queue_size, current_hash = map(int, self.runtime.evaluate_text(self.ui_child, source, b'@native_unit_production_effect').decode('ascii').split(','))
        if queue_size != 1 or current_hash != unit_hash:
            raise RuntimeError(f'Native production queue effect differs: {(queue_size, current_hash)!r}')
        self.emit('native_unit_production_effect_verified', player_id=owner, city_id=city_id, queue_size=queue_size, current_unit_hash=current_hash, produced_unit=False, native_rules_used=True, eligible_for_training=False)

    def inspect_unit_movement(self, player_id, *, unit_id=None, destination_plot_id=None, require_candidate=True, resolve_friendly_blockage=False, allow_improvements=False, allow_own_cities=False, allow_multiturn=False):
        """Request a visible native path and read its effect.

        Only the diagnostic unit-order policy opts into moving a different own
        unit to clear congestion. An explicit unit/destination is never remapped.
        """
        from civ6_host.runtime.native.native_unit_movement import guard_case
        from civ6_host.runtime.native.native_unit_movement import candidate_source
        from civ6_host.runtime.native.native_unit_movement import parse_candidates
        from civ6_host.runtime.native.native_unit_movement import choose
        from civ6_host.runtime.native.native_unit_movement import request_source
        from civ6_host.runtime.native.native_unit_movement import parse_request_result
        from civ6_host.runtime.native.native_unit_movement import effect_source
        from civ6_host.runtime.native.native_unit_movement import parse_effect
        if type(allow_improvements) is not bool:
            raise ValueError('Improved movement scope must be explicit Boolean')
        if type(allow_own_cities) is not bool:
            raise ValueError('Owned-city movement scope must be explicit Boolean')
        if type(allow_multiturn) is not bool:
            raise ValueError('Multi-turn movement scope must be explicit Boolean')
        if allow_multiturn and (unit_id is None or destination_plot_id is None):
            raise ValueError('Multi-turn movement requires explicit unit and destination IDs')
        movement_profile = 'native_reachable_single_turn_visible_ordinary_improvements989' if allow_improvements else 'native_reachable_single_turn_visible'
        if allow_multiturn:
            movement_profile = 'native_reachable_multiturn_visible_ordinary_improvements' if allow_improvements else 'native_reachable_multiturn_visible'
        if allow_own_cities:
            movement_profile = 'native_reachable_multiturn_visible_ordinary_improvements_and_own_cities' if allow_multiturn and allow_improvements else 'native_reachable_multiturn_visible_own_cities' if allow_multiturn else 'native_reachable_single_turn_visible_ordinary_improvements_and_own_cities999' if allow_improvements else 'native_reachable_single_turn_visible_own_cities999'
        if type(resolve_friendly_blockage) is not bool or (resolve_friendly_blockage and (unit_id is None or destination_plot_id is not None)):
            raise ValueError('Traffic policy requires a blocked unit without an explicit destination')
        if self.ui_child is None or self.actions.pending or self.deferred_events.pending:
            raise RuntimeError('Movement needs a current UI view and drained queues')
        if self.runtime.evaluate_text(self.game_child, guard_case(), b'@native_movement_guard_cases') != b'unit-movement-guards-ok':
            raise RuntimeError('Native HKS movement guards failed')
        self.emit('native_hks_movement_guards_verified', native_unit_changed=False, eligible_for_training=False)
        turn = int(self.runtime.evaluate_text(self.ui_child, b'return tostring(Game.GetCurrentGameTurn())', b'@native_movement_turn'))
        from civ6_host.runtime.native.native_reachable_movement import candidate_source as reachable_source
        from civ6_host.runtime.native.native_reachable_movement import parse_reachable
        from civ6_host.runtime.native.native_reachable_movement import guard_case
        if not getattr(self, 'reachable_guards_verified', False):
            result = self.runtime.evaluate_text(self.ui_child, guard_case(), b'@native_reachable_movement_guards')
            if result != b'reachable-movement-guards-ok':
                raise RuntimeError('Native HKS reachable-movement guard failed')
            self.reachable_guards_verified = True
        reachable = parse_reachable(self.runtime.evaluate_text(self.ui_child, reachable_source(player_id, turn), b'@native_reachable_movement'), player_id, turn)
        self.emit('native_reachable_movement_observed', observation=reachable, request_submitted=False, complete_action_space=False, eligible_for_training=False)
        catalog = parse_candidates(self.runtime.evaluate_text(self.ui_child, candidate_source(player_id, turn, allow_improvements=allow_improvements, allow_own_cities=allow_own_cities, allow_multiturn=allow_multiturn), b'@native_movement_candidates'), player_id, turn)
        self.emit('native_movement_catalog_observed', player_id=player_id, current_game_turn=turn, choices=[dict(item, moves_token=item['moves_token'].decode('ascii')) for item in catalog['choices']], complete_action_space=False, movement_profile=movement_profile, eligible_for_training=False)
        if unit_id is None and destination_plot_id is None:
            if not catalog['choices']:
                if not require_candidate:
                    self.emit('native_single_turn_movement_unavailable', player_id=player_id, current_game_turn=turn, request_invoked=False, endturn_gate_still_required=True, eligible_for_training=False)
                    return
                raise RuntimeError('No move in the admitted native single-turn movement profile')
            first = catalog['choices'][0]
            unit_id, destination_plot_id = (first['unit_id'], first['destination_plot_id'])
        elif unit_id is not None and destination_plot_id is None:
            matching = [item for item in catalog['choices'] if item['unit_id'] == unit_id]
            if not matching:
                relocation = None
                if resolve_friendly_blockage:
                    from civ6_host.runtime.native.native_diagnostic_traffic import choose_relocation
                    relocation = choose_relocation(catalog, reachable, unit_id)
                if relocation is None:
                    raise RuntimeError(f'No admitted native single-turn move for ready unit {unit_id}')
                self.emit('native_diagnostic_traffic_relocation_selected', player_id=player_id, current_game_turn=turn, blocked_unit_id=unit_id, relocated_unit_id=relocation['unit_id'], source_plot_id=relocation['source_plot_id'], destination_plot_id=relocation['destination_plot_id'], explicit_diagnostic_policy=True, blocked_unit_effect_verified=False, applied=False, eligible_for_training=False)
                unit_id = relocation['unit_id']
                destination_plot_id = relocation['destination_plot_id']
            else:
                destination_plot_id = matching[0]['destination_plot_id']
        elif unit_id is None:
            raise ValueError('Explicit movement needs both unit and destination IDs')
        choice = choose(catalog, unit_id, destination_plot_id)
        inspection = None
        if allow_improvements or allow_own_cities:
            from civ6_host.runtime.native.native_unit_movement import inspection_source
            from civ6_host.runtime.native.native_unit_movement import parse_inspection
            inspection = parse_inspection(self.runtime.evaluate_text(self.ui_child, inspection_source(choice, allow_improvements=allow_improvements, allow_own_cities=allow_own_cities, allow_multiturn=allow_multiturn), b'@native_own_city_movement_inspection999' if allow_own_cities else b'@native_improved_movement_inspection989', capacity=524289), choice, allow_improvements=allow_improvements, allow_own_cities=allow_own_cities, allow_multiturn=allow_multiturn)
            self.emit('native_own_city_movement_path_inspected999' if allow_own_cities else 'native_improved_movement_path_inspected989', inspection=inspection, native_gameplay_mutated=False, eligible_for_training=False)
        submission = parse_request_result(self.runtime.evaluate_text(self.ui_child, request_source(choice, allow_improvements=allow_improvements, allow_own_cities=allow_own_cities, allow_multiturn=allow_multiturn), b'@native_movement_request'), choice, allow_multiturn=allow_multiturn)
        if inspection is not None and ([row['plot_id'] for row in inspection['path']] != list(submission['native_path']['plot_ids']) or [row['turn'] for row in inspection['path']] != list(submission['native_path']['turns'])):
            raise RuntimeError('Movement request path differs from its inspected native preview')
        if len(self.actions.pending) != 1:
            raise RuntimeError('Movement did not serialize exactly one native command')
        self.emit('native_unit_movement_request_submitted', player_id=player_id, current_game_turn=turn, unit_id=unit_id, source_plot_id=choice['source_plot_id'], destination_plot_id=choice['destination_plot_id'], movement_profile=movement_profile, native_path=submission['native_path'], serialized_commands=1, applied=False, eligible_for_training=False)
        self.actions.deliver_one()
        self.deferred_events.drain_empty_receivers()
        self.view_publisher.publish()
        effect = parse_effect(self.runtime.evaluate_text(self.ui_child, effect_source(choice), b'@native_movement_effect'), choice)
        multi_path = allow_multiturn and max(submission['native_path']['turns']) > 1
        if not effect['found'] or (not multi_path and (effect['moves_remaining'] >= choice['moves_remaining'] or not effect['at_destination'])):
            raise RuntimeError(f'Native movement effect not established: {effect!r}')
        if multi_path:
            from civ6_host.runtime.native.native_saved_combat import queued_destination_source
            actual_plot = _parse_movement_position(self.runtime.evaluate_text(self.ui_child, _movement_position_source(choice, effect), b'@native_movement_position'), choice, effect)
            path_ids = submission['native_path']['plot_ids']
            path_turns = submission['native_path']['turns']
            first_turn = [plot for plot, path_turn in zip(path_ids, path_turns) if path_turn == 1]
            if not first_turn or actual_plot != first_turn[-1] or actual_plot not in path_ids or (actual_plot == choice['destination_plot_id']):
                raise RuntimeError('Multi-turn movement did not stop at the last reachable first-turn path plot')
            queued_only = actual_plot == choice['source_plot_id']
            if queued_only and (first_turn != [choice['source_plot_id']] or effect['moves_remaining'] != choice['moves_remaining']) or (not queued_only and effect['moves_remaining'] >= choice['moves_remaining']):
                raise RuntimeError('Multi-turn movement consumption differs from native path progress')
            queued_raw = self.runtime.evaluate_text(self.ui_child, queued_destination_source(player_id, turn, unit_id), b'@explicit_own_queued_destination', capacity=32)
            if type(queued_raw) is not bytes or not queued_raw.isdigit() or int(queued_raw) != destination_plot_id:
                raise RuntimeError('Native multi-turn MOVE_TO target was not retained')
            effect.update(actual_plot_id=actual_plot, retained_target_plot_id=destination_plot_id, multi_turn_order_verified=True, multi_turn_progress_verified=not queued_only, multi_turn_queued_only=queued_only, multi_turn_path=True)
        self.emit('native_unit_movement_effect_verified', **effect, source_x=choice['source_x'], source_y=choice['source_y'], source_plot_id=choice['source_plot_id'], destination_plot_id=choice['destination_plot_id'], movement_profile=movement_profile, moves_before=choice['moves_remaining'], native_rules_used=True, eligible_for_training=False)
        return effect

    def inspect_player_view(self, *, completed_round_echo_player=None, player_ids=(0, 1)):
        """Probe a separate player view without replacing an unavailable view.

        A rejected observation is recorded and discarded. The independent
        native action diagnostic can still run; no policy receives a fallback.
        """
        from civ6_host.runtime.native.native_diagnostic_roster import validate_roster
        validate_roster(player_ids)
        if completed_round_echo_player is not None and player_ids != (0, 1):
            raise ValueError('Legacy victory boundary is scoped to two players')
        if self.ui_child is None:
            self.ui_child = self.runtime.acquire()
            self.runtime.attach_standard_libraries(self.ui_child)
            self.runtime.attach_ui_enums(self.ui_child)
            self.runtime.namespaces.register(self.ui_child, 'GameInfo')
            self.runtime.bind_native_ui_api(self.game_child, self.ui_child, self.context, self.core)
        self.runtime.execute(self.game_child, b"assert(type(PlayersVisibility[0].IsUnitVisible)~='function','UI bindings polluted gameplay visibility')", b'@native_ui_gameplay_binding_isolation')
        dimension_source = b'local w,h=Map.GetGridSize(); return string.format("%d,%d,%d",w,h,Map.GetPlotCount())'
        dimensions = {}
        for name, child in (('gameplay', self.game_child), ('ui', self.ui_child)):
            dimensions[name] = list(map(int, self.runtime.evaluate_text(child, dimension_source, b'@native_map_view_dimensions').decode('ascii').split(',')))
        self.emit('native_map_view_dimensions', columns=['width', 'height', 'plot_count'], views=dimensions, player_observation=False, eligible_for_training=False)
        state = self.runtime.evaluate_text(self.ui_child, b'local ids={' + b','.join((str(p).encode() for p in player_ids)) + b"}\nlocal rows={}\nfor _,id in ipairs(ids) do\n local p=Players[id]\n assert(p and type(p.IsTurnActive)=='function' and\n        type(p.IsTurnActiveComplete)=='function','native player turn API unavailable')\n rows[#rows+1]=string.format('%d,%d,%d',id,p:IsTurnActive() and 1 or 0,\n                             p:IsTurnActiveComplete() and 1 or 0)\nend\nreturn string.format('%d|%d|%s',Game.GetCurrentGameTurn(),Game.GetLocalPlayer(),table.concat(rows,';'))\n", b'@native_player_turn_state')
        turn, local_player, rows = state.decode('ascii').split('|')
        states = []
        for row in rows.split(';'):
            player, active, complete = map(int, row.split(','))
            states.append({'player_id': player, 'active': bool(active), 'complete': bool(complete)})
        self.emit('native_player_turn_state_observed', current_game_turn=int(turn), local_player=int(local_player), players=states, source='Native UI player methods; native-player-turn-state.json', full_round_verified=False, eligible_for_training=False)
        from civ6_host.runtime.native.native_winning_team import source as winning_team_source
        from civ6_host.runtime.native.native_winning_team import parse as parse_winning_team
        winner = parse_winning_team(self.runtime.evaluate_text(self.ui_child, winning_team_source(), b'@native_winning_team_observation'))
        self.emit('native_winning_team_observed', **winner, current_game_turn=int(turn), source='Native Game.GetWinningTeam; native-winning-team.json', episode_termination_inferred=False, complete_game=False, eligible_for_training=False)
        if getattr(self, 'diagnostic_score_turn_limit', None) is not None and getattr(self, 'score_turn_limit_readback', None) is None:
            from civ6_host.runtime.native.native_score_limit_diagnostic import observe
            self.score_turn_limit_readback = observe(self, int(local_player), int(turn), self.diagnostic_score_turn_limit)
        if completed_round_echo_player is not None:
            from civ6_host.runtime.native.native_victory_diagnostic import defer_at_completed_round_echo
            defer_at_completed_round_echo(self, int(local_player), states, completed_round_echo_player)
        elif self.diagnostic_action in ('develop-round', 'develop-move-round'):
            from civ6_host.runtime.native.native_victory_diagnostic import observe_victory_boundary
            observe_victory_boundary(self, int(local_player), int(turn), winner)
        from civ6_host.runtime.native.native_player_observation import build_player_observation_source
        from civ6_host.runtime.native.native_player_observation import parse_player_observation
        for player_id in (int(local_player),) if int(local_player) in player_ids else ():
            try:
                payload = self.runtime.evaluate_text(self.ui_child, build_player_observation_source(player_id), b'@native_player_observation')
            except RuntimeError as exc:
                self.emit('native_player_observation_rejected', player_id=player_id, reason=str(exc), observation_substituted=False, eligible_for_training=False)
                continue
            observation = parse_player_observation(payload, player_id)
            self.emit('native_player_observation_diagnostic', player_id=player_id, observation=observation, resource_information_included=True, resource_visibility_source='Native player GetResources:IsResourceVisible(hash)', explored_memory_included=False, complete_player_observation=False, eligible_for_training=False)
            from civ6_host.runtime.native.native_revealed_plot_observation import build_revealed_plot_observation_source
            from civ6_host.runtime.native.native_revealed_plot_observation import parse_revealed_plot_observation
            try:
                revealed_payload = self.runtime.evaluate_text(self.ui_child, build_revealed_plot_observation_source(player_id), b'@native_revealed_plots')
                revealed = parse_revealed_plot_observation(revealed_payload, player_id)
            except (RuntimeError, ValueError) as exc:
                self.emit('native_revealed_plot_observation_rejected', player_id=player_id, reason=str(exc), observation_substituted=False, eligible_for_training=False)
            else:
                self.emit('native_revealed_plot_observation_diagnostic', player_id=player_id, observation=revealed, source='Official PlotToolTip reveal/resource predicates', historical_fog_memory_validated=False, exposed_to_learner=False, complete_player_observation=False, eligible_for_training=False)
        return {'current_game_turn': int(turn), 'local_player': int(local_player), 'players': states}

    def protected_call(self, this, pointer, callback, userdata):
        self.check(this)
        child = self.children[pointer]
        self.runtime.registry.validate(child)
        rva = callback - self.core._handle
        if rva not in (4583056, 4582800, 4583984):
            raise ValueError(f'Unverified native Lua callback {rva:#x}')
        self.emit('native_map_protected_callback', callback_rva=hex(rva), userdata_origin='unchanged Core argument', strict_errors=True)
        call = self.runtime.host.LAB_ScriptProtectedCall
        call.argtypes, call.restype = ([C.c_void_p] * 3, C.c_int)
        status = call(pointer, callback, userdata)
        self.runtime._status(pointer, status, 'Core native map callback')
        self.emit('native_map_protected_callback_completed', callback_rva=hex(rva), lua_status=status, host_return=True)
        if rva == 4582800:
            self.runtime.execute(child, b"local w,h=Map.GetGridSize()\nassert(w>0 and h>0 and w*h<=16384,'diagnostic native grid bound')\nlocal rows={}\nfor i=0,w*h-1 do\n    local p=Map.GetPlotByIndex(i)\n    assert(p~=nil,'missing native plot')\n    local t=p:GetTerrainType()\n    assert(t>=0,'unset native terrain')\n    rows[#rows+1]=string.format('%d,%d,%d',t,p:GetFeatureType(),p:GetResourceType())\nend\nprint('CIV6RL_NATIVE_MAP_SNAPSHOT',w,h,Map.GetMapSize(),table.concat(rows,';'))\nprint('CIV6RL_NATIVE_MAP_PLAYERS',PlayerManager.GetAliveMajorsCount(),\n      PlayerManager.GetAliveMinorsCount(),table.concat(PlayerManager.GetAliveMajorIDs(),','))\n", b'@native_generated_map_witness')
            self.emit('native_map_plot_witness_completed', all_plots_have_terrain=True, snapshot_location='stderr CIV6RL_NATIVE_MAP_SNAPSHOT', game_playable_validated=False)
        return True

    def stack_call(self, this, pointer, nargs, nresults):
        self.check(this)
        self.runtime.registry.validate(self.children[pointer])
        call = self.runtime.host.LAB_ScriptProtectedStackCall
        call.argtypes, call.restype = ([C.c_void_p, C.c_int, C.c_int], C.c_int)
        status = call(pointer, nargs, nresults)
        self.runtime._status(pointer, status, 'Core requested Lua stack call')
        self.emit('native_map_stack_call_completed', nargs=nargs, nresults=nresults, lua_status=status)
        return True

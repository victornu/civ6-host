"""Installed-source and public boundary checks for the archaeology reader."""

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from struct import pack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from lupa.lua51 import LuaError, LuaRuntime
import pefile

from civ6_host import SessionClient
from civ6_host.contracts import archaeology, network_turn
from civ6_host.runtime import xp2_archaeology, xp2_bbg_inputs, xp2_bundle_inputs
from civ6_host.runtime import xp2_archaeology_excavation as excavation
from civ6_host.runtime.a0_family_source import verify_pinned_files
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE, _XP1_PROFILE
from civ6_host.runtime.native import native_event_great_work, native_player_operation_request
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.workers import network_worker
from test_xp2_great_person_activation import checked_event, checked_json, seal


class ArchaeologyTests(TestCase):
    def test_current_stock_and_bbg_bindings_and_dependencies(self):
        with pefile.PE(_PROFILE.path, fast_load=True) as pe:
            base = pe.OPTIONAL_HEADER.ImageBase
            read = lambda address, size: pe.get_data(address-base, size)
            for reference in (xp2_bundle_inputs.REFERENCE, xp2_bbg_inputs.REFERENCE):
                with self.subTest(reference=reference[0]):
                    pins = xp2_archaeology.source_dependencies(reference, _PROFILE)
                    verify_pinned_files(pins)
                    self.assertIn(reference[1], pins.values())
                    self.assertIn(_PROFILE.image_sha256, pins.values())
                    self.assertEqual(any(name.endswith('BetterBalancedGame.modinfo') for name in pins),
                                     reference == xp2_bbg_inputs.REFERENCE)
                    xp2_archaeology.verify_live(base, read, reference=reference, image=_PROFILE)
                    extra = xp2_archaeology.source_dependencies(reference, _PROFILE, commands=True)
                    verify_pinned_files(extra)
                    self.assertTrue(pins.items() <= extra.items())
                    self.assertIn(xp2_archaeology._APPLICATION[1], extra.values())
                    self.assertIn(xp2_archaeology._PANEL[1], extra.values())
                    self.assertIn(xp2_archaeology._PLACEMENT[1], extra.values())
                    xp2_archaeology.verify_live(base, read, reference=reference, image=_PROFILE, commands=True)
            with self.assertRaisesRegex(ValueError, 'Live archaeology binding differs'):
                xp2_archaeology.verify_live(base, lambda address, size: bytes(size),
                                            reference=xp2_bundle_inputs.REFERENCE, image=_PROFILE)
        with self.assertRaisesRegex(ValueError, 'exact stock or BBG'):
            xp2_archaeology.source_dependencies(xp2_bundle_inputs.REFERENCE, _XP1_PROFILE)

    def test_popup_projects_one_or_two_origins_without_reading_hidden_fields(self):
        lua = LuaRuntime(encoding=None)
        lua.execute(b'''
            local core = {Type=0, ActingPlayerEra=2, ActingPlayerID=7, TargetPlayerID=63}
            source = core
            targetReads, observer, unitOwner = 0, 0, 0
            local artifact = setmetatable({}, {__index=function(_, key)
                assert(key ~= 'TargetPlayerEra', 'read irrelevant origin era')
                if key == 'TargetPlayerID' then
                    assert(core.Type ~= 1 and core.Type ~= 2 and core.Type ~= 5,
                           'read hidden origin on confirmation-only popup')
                    targetReads = targetReads + 1
                end
                return core[key]
            end})
            local unit = {
                GetID=function() return 28 end,
                GetOwner=function() return unitOwner end,
                GetArchaeology=function() return {GetArtifactIndex=function() return 906 end} end,
            }
            local units = {GetNextExtractingArchaeologist=function()
                if not noUnit then return unit end
            end}
            Players = {[0]={GetUnits=function() return units end}}
            Game = {GetLocalPlayer=function() return 0 end, GetLocalObserver=function() return observer end,
                GetCurrentGameTurn=function() return 9 end, GetArtifactByIndex=function(i)
                    assert(i == 906)
                    if not missingArtifact then return artifact end
                end}
            GameInfo = {Eras={[2]={}}}
        ''')
        observation = dict(player_id=0, turn=9, units=[dict(id=28, owner=0)])
        source = xp2_archaeology.build_source(0, 9)
        for artifact in range(6):
            lua.globals()[b'source'][b'Type'] = artifact
            state = xp2_archaeology.parse(lua.execute(source), observation)['pending']
            origins = [7] if artifact in archaeology.CONFIRM_ONLY_TYPES else [7, 63]
            self.assertEqual(state, dict(unit_id=28, artifact_type=artifact, era_index=2, origin_player_ids=origins))
        self.assertEqual(lua.globals()[b'targetReads'], 3)
        for field in (b'noUnit', b'missingArtifact'):
            lua.globals()[field] = True
            self.assertIsNone(xp2_archaeology.parse(lua.execute(source), observation)['pending'])
            lua.globals()[field] = False
        lua.globals()[b'unitOwner'] = 1
        with self.assertRaisesRegex(LuaError, 'unit is foreign'):
            lua.execute(source)
        lua.globals()[b'observer'] = 1
        with self.assertRaisesRegex(LuaError, 'stale archaeology perspective'):
            lua.execute(source)

    def test_optional_archaeology_in_a_real_checkpoint_catalogue_and_python_client(self):
        root = resource_root()
        ref = checked_json(root/'evidence/host-xp2-stock-great-writer-work-move-reload-native.json',
                           '7ffb1756a65b79820f90a044018b411ca7fbd1f067dcda707cd1bcc31bc9a23a')
        response = checked_event(root, ref['event_log'], 5454)
        self.assertEqual(response['operation'], 'reset')
        original = deepcopy(response['decisions'])
        observation = response['observation']
        unit = observation['units'][0]
        frame = f"0|111|{unit['id']}|906|3|0|0|1".encode('ascii')
        public = xp2_archaeology.parse(frame, observation)
        combined = response['decisions']
        combined['archaeology'] = public
        seal(combined)
        client = SessionClient(SimpleNamespace(reset=lambda: response, abort=Mock()))
        client.reset()
        info = client.information('archaeology')
        self.assertEqual(info['data'], public)
        self.assertEqual(info['source_contracts']['archaeology'], archaeology.SCHEMA)
        self.assertEqual(info['native_decision_id'], combined['decision_id'])
        self.assertEqual(combined['candidates'], original['candidates'])
        projected, change = network_turn.checkpoint_catalogue(combined, original, observation,
                                                            core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, original)
        self.assertEqual(change['added_public_fields'], ['archaeology'])

        self.assertEqual(change['added_action_families'], [])
        self.assertEqual(network_turn.checkpoint_catalogue(combined, combined, observation,
                         core_sha256=XP2_CORE_SHA256), (combined, None))

        reader_only = deepcopy(combined)
        network_turn.add_archaeology_choices(combined)
        seal(combined)
        client = SessionClient(SimpleNamespace(reset=lambda: response, abort=Mock()))
        reply = client.reset()
        choices = reply['decisions']
        rows = [row for row in choices['candidates'] if row['action']['kind'] == archaeology.KIND]
        self.assertEqual([row['action']['origin_player_id'] for row in rows], [0, 1])
        for row in rows:
            self.assertEqual(network_turn.select_capability(choices, dict(decision_id=choices['decision_id'],
                candidate_id=row['candidate_id'])), row['action'])
        projected, change = network_turn.checkpoint_catalogue(combined, reader_only, observation,
            core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, reader_only)
        self.assertEqual(change['added_action_families'], [archaeology.KIND])
        projected, change = network_turn.checkpoint_catalogue(combined, original, observation,
            core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, original)
        self.assertEqual(change['added_public_fields'], ['archaeology'])

        origin_only = deepcopy(combined)
        combined = deepcopy(reader_only)
        offer = dict(kind=archaeology.EXCAVATE, unit_id=unit['id'], x=unit['x'], y=unit['y'])
        network_turn.add_archaeology_choices(combined, excavations=[offer])
        seal(combined)
        response['decisions'] = combined
        client = SessionClient(SimpleNamespace(reset=lambda: response, abort=Mock()))
        choices = client.reset()['decisions']
        picked, = (row for row in choices['candidates'] if row['action']['kind'] == archaeology.EXCAVATE)
        self.assertEqual(network_turn.select_capability(choices, dict(decision_id=choices['decision_id'],
            candidate_id=picked['candidate_id'])), offer)
        projected, change = network_turn.checkpoint_catalogue(combined, origin_only, observation,
            core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, origin_only)
        self.assertEqual(change['added_action_families'], [archaeology.EXCAVATE])

    def test_rejects_noncanonical_frame_and_foreign_or_extra_public_data(self):
        observation = dict(player_id=0, turn=9, units=[dict(id=28, owner=0)])
        for frame in (b'1|9|none', b'0|09|none', b'0|9|028|906|0|0|0|1', b'0|9|28|906|6|0|0|1',
                      b'0|9|28|906|5|0|0|1', b'0|9|28|906|3|0|0', b'0|9|28|906|1|0|64',
                      b'0|9|99|906|1|0|0', b'0|9|28|2147483648|1|0|0'):
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                xp2_archaeology.parse(frame, observation)
        record = xp2_archaeology.parse(b'0|9|28|906|1|0|0', observation)
        record['pending']['artifact_index'] = 906
        with self.assertRaisesRegex(ValueError, 'public artifact fields'):
            archaeology.validate(record, 0, 9, observation=observation)

    def test_museum_makes_owned_era_and_origin_available_to_client_and_checkpoint(self):
        root = resource_root()
        ref = checked_json(root/'evidence/host-xp2-stock-great-writer-work-move-reload-native.json',
                           '7ffb1756a65b79820f90a044018b411ca7fbd1f067dcda707cd1bcc31bc9a23a')
        response = checked_event(root, ref['event_log'], 5454)
        decisions, observation = response['decisions'], response['observation']
        panel = decisions['city_buildings']
        placement = panel['great_work_slots'][0]
        placement['work'].update(type='GREATWORK_ARTIFACT_1', object_type='GREATWORKOBJECT_ARTIFACT')
        self.assertEqual((placement['city_id'], placement['building_index'], placement['slot'],
                          placement['work']['index']), (65536, 1, 0, 2))
        state = xp2_archaeology.parse(b'0|111|none', observation)
        decisions['archaeology'] = state
        seal(decisions)
        legacy = deepcopy(decisions)
        lua = LuaRuntime(encoding=None)
        lua.execute(br'''
            calls, cityOwner, slotWork, origin, observer = 0, 0, 2, 63, 0
            local buildings = {
                HasBuilding=function(_, id) return id == 1 end,
                GetGreatWorkInSlot=function(_, id, slot) assert(id == 1 and slot == 0); return slotWork end,
                GetGreatWorkTypeFromIndex=function(_, work) assert(work == 2); return 8 end,
            }
            local city = {GetOwner=function() return cityOwner end,
                GetBuildings=function() return buildings end}
            local cities = {FindID=function(_, id) assert(id == 65536); return city end}
            Players={[0]={GetCities=function() return cities end}}
            Game={GetLocalPlayer=function() return 0 end,
                  GetLocalObserver=function() return observer end,
                  GetCurrentGameTurn=function() return 111 end,
                  GetGreatWorkPlayer=function(work) assert(work == 2); calls = calls+1; return origin end}
            GameInfo={GreatWorks={[8]={EraType='ERA_CLASSICAL', GreatWorkObjectType='GREATWORKOBJECT_ARTIFACT'}},
                      Eras={ERA_CLASSICAL={}}}
        ''')
        core = object()

        def evaluate(context, code, label, *, capacity):
            if label == b'@public_archaeology':
                return b'0|111|none'
            self.assertEqual(label, b'@public_museum_artifacts')
            return lua.execute(code)

        prefix = SimpleNamespace(core=core, ui_child=object(), runtime=SimpleNamespace(evaluate_text=evaluate))
        saved = SimpleNamespace(prefix=prefix, _archaeology_core=core, _check_query=Mock())
        details = xp2_archaeology.read(saved, observation, panel=panel)
        expected = dict(city_id=65536, building_index=1, slot=0, work_index=2,
                        era_type='ERA_CLASSICAL', origin_player_id=63)
        self.assertEqual(details['museum_artifacts'], [expected])
        self.assertEqual(saved.explicit_archaeology, (state, None))
        decisions['archaeology'] = details
        seal(decisions)
        client = SessionClient(SimpleNamespace(reset=lambda: response, abort=Mock()))
        client.reset()
        info = client.information('archaeology')
        self.assertEqual(info['data'], details)
        self.assertEqual(info['source_contracts']['archaeology'], archaeology.MUSEUM_SCHEMA)
        self.assertEqual(info['source_contracts']['city_buildings'], panel['schema'])
        projected, change = network_turn.checkpoint_catalogue(decisions, legacy, observation,
            core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, legacy)
        self.assertEqual(change['added_public_fields'], ['archaeology.museum_artifacts'])
        self.assertEqual(decisions['candidates'], legacy['candidates'])
        with self.assertRaisesRegex(ValueError, 'Invalid or foreign'):
            archaeology.validate(dict(details, museum_artifacts=[dict(expected, city_id=65537)]),
                                 0, 111, observation=observation, panel=panel)
        self.assertEqual(lua.globals()[b'calls'], 1)
        for name, rejected_value, original, reason in (
            (b'cityOwner', 1, 0, 'foreign museum city'),
            (b'slotWork', 7, 2, 'museum artifact slot changed'),
            (b'observer', 1, 0, 'stale archaeology perspective'),
        ):
            with self.subTest(name=name):
                lua.globals()[name] = rejected_value
                with self.assertRaisesRegex(LuaError, reason):
                    xp2_archaeology.read_museum_artifacts(prefix, observation, panel)
                lua.globals()[name] = original
        self.assertEqual(lua.globals()[b'calls'], 1)
        lua.globals()[b'origin'] = -1
        self.assertEqual(xp2_archaeology.read_museum_artifacts(prefix, observation, panel),
                         [dict(expected, origin_player_id=None)])
        placement['work']['object_type'] = 'GREATWORKOBJECT_WRITING'
        self.assertEqual(xp2_archaeology.read_museum_artifacts(prefix, observation, panel), [])
        self.assertEqual(lua.globals()[b'calls'], 2)

    def test_worker_refuses_same_visible_options_if_native_artifact_changed(self):
        observation = dict(player_id=0, turn=9, units=[dict(id=28, owner=0)])
        state = xp2_archaeology.parse(b'0|9|28|906|1|0|7', observation)
        action, = archaeology.actions(state)
        saved = SimpleNamespace(explicit_archaeology=(state, 906), execute=Mock(),
                                continuation=SimpleNamespace(observation=observation))

        def refresh(*_):
            saved.explicit_archaeology = state, 907
            return {}, observation, dict(candidates=[dict(action=action)])

        with patch('civ6_host.runtime.xp1_session_view.read', side_effect=refresh):
            receipt = network_worker._execute_xp1(saved, action, 0, 9, Path('unused-fixture-path'))
        self.assertEqual(receipt['reason'], 'native_artifact_origin_choice_changed')
        saved.execute.assert_not_called()

    def test_borrowed_origin_refuses_changed_private_artifact_before_native_request(self):
        observation = dict(player_id=1, turn=9, units=[dict(id=28, owner=1)])
        state = xp2_archaeology.parse(b'1|9|28|906|1|0|7', observation)
        action, = archaeology.actions(state)
        core = object()
        prefix = SimpleNamespace(ui_child=object(), runtime=SimpleNamespace(evaluate_text=Mock(
            side_effect=[b'ready', b'1|9|28|907|1|0|7'])))
        primary = object()
        saved = SimpleNamespace(prefix=prefix, explicit_archaeology=primary, _check_active=Mock(),
            _archaeology_commands_core=core, backend=SimpleNamespace(core=core), continuation=object(),
            _xp2_borrowed_archaeology={1: (state, 906)})
        with patch.object(native_player_operation_request, 'request_player_operation') as dispatch:
            result = xp2_archaeology.apply(saved, action, observation, borrowed_public=state)
        self.assertEqual((result['status'], result['refusal_code']),
                         ('refused', 'native_artifact_origin_choice_changed'))
        dispatch.assert_not_called()
        self.assertIs(saved.explicit_archaeology, primary)
        self.assertEqual(saved._xp2_borrowed_archaeology, {1: (state, 906)})

    def test_exact_native_origin_archive_and_result_readback(self):
        before = dict(player_id=0, turn=9, units=[dict(id=28, owner=0)],
                      cities=[dict(owner=0, id=129, x=5, y=8)])
        frame = b'0|9|28|906|5|0|7'
        state = xp2_archaeology.parse(frame, before)
        action, = archaeology.actions(state)
        core = SimpleNamespace(_civ6_host_execution_image=_PROFILE)
        op = xp2_archaeology.OPERATION
        key = xp2_archaeology.PARAMETER

        def work(artifact=906, *, sequence=13, owner=0, unit=28, city=129):
            return native_event_great_work.encode_record(sequence, dict(
                position_bytes=pack('<ii', 5, 8), x=5, y=8, selector=0,
                source_value=artifact, descriptor_tail=11), pack('<HHI', 0, 1, unit),
                dict(owner=owner, city_id=city, district_id=0))

        cases = (
            (b'-1', True, 0, [work()], True, 'completed'),
            (b'removed', False, 0, [work()], True, 'completed'),
            (b'906', True, 0, [work()], True, 'submitted'),
            (b'-1', True, 0, [], False, 'submitted'),
            (b'-1', True, 0, [work(907)], False, 'submitted'),
            (b'-1', True, 0, [work(unit=29)], False, 'submitted'),
            (b'-1', True, 0, [work(owner=1)], False, 'submitted'),
            (b'-1', True, 0, [work(city=130)], False, 'submitted'),
            (b'-1', True, 0, [work(sequence=12)], False, 'submitted'),
            (b'-1', True, 0, [work(), work(sequence=14)], False, 'submitted'),
            (b'removed', True, 0, [work()], True, None),
            (b'-1', True, 1, [work()], True, None),
        )
        for readback, present, sender, records, created, status in cases:
            with self.subTest(readback=readback, present=present, sender=sender, records=records):
                after = deepcopy(before)
                if not present:
                    after['units'].clear()
                queue = []
                events = SimpleNamespace(pending=[], consumed_count=12, drain_empty_receivers=Mock())

                def deliver_to_engine():
                    queue.pop()
                    events.pending.extend(records)

                deliver = Mock(side_effect=deliver_to_engine)
                prefix = SimpleNamespace(ui_child=object(), runtime=SimpleNamespace(evaluate_text=Mock(
                    side_effect=[b'ready', frame, readback])), actions=SimpleNamespace(pending=queue,
                    deliver_one=deliver), deferred_events=events, view_publisher=SimpleNamespace(publish=Mock()))
                saved = SimpleNamespace(prefix=prefix, explicit_archaeology=(state, 906), _check_active=Mock(),
                    _archaeology_commands_core=core, backend=SimpleNamespace(core=core, context=12, control=Mock(),
                    runtime=SimpleNamespace(read=Mock())), continuation=SimpleNamespace(trade_feedback=None,
                    transport=SimpleNamespace(require_empty_native_queue=Mock())))

                def request(actual, context, actor, operation, parameters, *, core_sha256, read, archaeology_permit):
                    self.assertEqual((actual, context, actor, operation, parameters), (core, 12, 0, op, {key: 7}))
                    self.assertEqual(xp2_archaeology.authorize_request(archaeology_permit, actual, context,
                        actor, operation, parameters, core_sha256=core_sha256, submit=True, allow_empty=False),
                        'CHOOSE_ARTIFACT_PLAYER')
                    queue.append(pack('<7IHH10xI', 0xc45de12f, sender, op, 2, 0x80000001, 1, key, 0, 2, 7))
                    return dict(request_invoked=True, can_start=None)

                with (patch.object(native_player_operation_request, 'request_player_operation', side_effect=request),
                      patch('civ6_host.runtime.native.native_player_observation.observe_player', return_value=after)):
                    if status is None:
                        with self.assertRaises(RuntimeError):
                            xp2_archaeology.apply(saved, action, before)
                        if sender != 0:
                            deliver.assert_not_called()
                    else:
                        result = xp2_archaeology.apply(saved, action, before)
                        self.assertEqual(result['status'], status)
                        self.assertEqual(result['receipt']['native_pending_cleared'], readback != b'906')
                        self.assertEqual(result['receipt']['native_artifact_creation_observed'], created)
                        deliver.assert_called_once_with()

    def test_excavation_uses_native_visibility_legality_and_parameterless_archive(self):
        lua = LuaRuntime(encoding=None)
        lua.execute(b'''
            local function unit(id)
                return {id=id, GetID=function() return id end,
                    GetMovesRemaining=function() return 1 end,
                    GetOwner=function() return 0 end, GetX=function() return 3 end, GetY=function() return 5 end,
                    GetArchaeology=function() return {GetArtifactIndex=function() return artifactIndex end} end}
            end
            local a, b, c = unit(28), unit(4), unit(16)
            local units = {Members=function() return ipairs({a,b,c}) end,
                FindID=function(_, id) assert(id == 28); return a end}
            Players = {[0] = {GetUnits=function() return units end, IsTurnActive=function() return true end,
                IsTurnActiveComplete=function() return true end}}
            Game = {GetLocalPlayer=function() return 0 end, GetLocalObserver=function() return 0 end,
                GetCurrentGameTurn=function() return 9 end}
            GameInfo = {UnitOperations={UNITOPERATION_EXCAVATE={Hash=1548958412, VisibleInUI=true, Index=21}}}
            OperationResultsTypes={NO_TARGETS=42}
            function UnitCanStart(unit, hash, target, visible, flags)
                assert(hash == 1548958412 and target == nil)
                if visible then assert(flags == nil); return unit.id ~= 4 end
                assert(flags == 42 and unit.id ~= 4)
                return unit.id == 28 and nativeLegal
            end
            UnitManager={CanStartOperation=UnitCanStart, RequestOperation=function(...)
                assert(select('#', ...) == 2)
                local unit, hash = ...
                assert(unit.id == 28 and hash == 1548958412)
                enqueue()
            end}
        ''')
        obs = dict(player_id=0, turn=9, units=[dict(id=id, owner=0, x=3, y=5) for id in (4, 16, 28)])
        runtime = SimpleNamespace(evaluate_text=lambda child, source, tag, *, capacity: lua.execute(source))
        globals_ = lua.globals()
        offer = dict(kind=archaeology.EXCAVATE, unit_id=28, x=3, y=5)
        for legal, sender, effect_index, status in ((True, 0, 206, 'completed'), (True, 0, -1, 'submitted'),
                                                   (False, 0, -1, 'refused'), (True, 1, 206, None)):
            with self.subTest(legal=legal, sender=sender, effect=effect_index):
                queue = []
                delivered = []
                transport = SimpleNamespace(pending=queue, require_empty_native_queue=Mock())

                @contextmanager
                def guarded(check, *, allow_no_archive):
                    self.assertTrue(allow_no_archive)

                    def deliver():
                        check(queue[0])
                        delivered.append(queue.pop())
                        globals_[b'artifactIndex'] = effect_index

                    transport.deliver_one = deliver
                    yield

                transport.require_xp2_single_archive = guarded
                globals_[b'enqueue'] = lambda: queue.append(pack('<IHH5I', 0x8c0f3f36, sender, 1,
                                                                  28, 21, 0xffffffff, 0, 0))
                globals_[b'artifactIndex'] = -1
                globals_[b'nativeLegal'] = legal
                core = object()
                prefix = SimpleNamespace(runtime=runtime, ui_child=None, actions=transport,
                    deferred_events=SimpleNamespace(drain_empty_receivers=Mock()), view_publisher=SimpleNamespace(publish=Mock()))
                saved = SimpleNamespace(prefix=prefix, _check_active=Mock(), _check_query=Mock(),
                    _archaeology_commands_core=core, backend=SimpleNamespace(core=core),
                    continuation=SimpleNamespace(transport=transport, trade_feedback=None))
                self.assertEqual(excavation.read(saved, obs), [offer] if legal else [])
                with patch.object(excavation, 'observe_player', return_value=obs):
                    if status is None:
                        with self.assertRaisesRegex(ValueError, 'exact actor'):
                            excavation.apply(saved, offer, obs)
                    else:
                        result = excavation.apply(saved, offer, obs)
                        self.assertEqual(result['status'], status)
                        if legal:
                            self.assertEqual(result['receipt']['native_pending_created'], status == 'completed')
                self.assertEqual(len(delivered), 1 if legal and sender == 0 else 0)

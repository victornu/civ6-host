"""Rock-band source checks, Lua calls and composed human-seat transport."""

from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
from struct import pack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from lupa.lua51 import LuaRuntime
import pefile

from civ6_host import SessionClient
from civ6_host.contracts import information, network_turn, rock_bands
from civ6_host.runtime import a0_foundation_events as foundation
from civ6_host.runtime import empty_presentation_events, expansion_city_growth, network_timer
from civ6_host.runtime import xp2_bbg_inputs, xp2_bundle_inputs, xp2_lan_unit_commands
from civ6_host.runtime import xp2_rock_bands as bands, xp2_rock_concert_source as concert
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE
from civ6_host.runtime.paths import resource_root
from test_xp1_turn_a0 import scalar
from test_xp2_great_person_activation import seal
from test_xp2_secondary_unit_panel import SecondaryPanelFixture


def install_source(original):
    def install(owner, backend):
        backend.core._civ6_host_execution_image = _PROFILE
        memory = owner.read.__self__
        with pefile.PE(_PROFILE.path, fast_load=True) as image:
            for span in concert.core_spans():
                memory.put(memory.core_base + span['rva'], image.get_data(span['rva'], span['bytes']))
        owner.arguments.reader.core_sha256 = backend.load_abi.core_sha256
        original(owner, backend)
        empty_presentation_events.enable(owner, backend, concert)
    return install


def result_fields(memory, player=1, unit=28):
    memory.put(0x715000, pack('<HHI', player, 1, unit))
    memory.put(0x715100, pack('<ii', 3, 0))
    return {
        concert.SELECTOR: scalar(3, 0),
        concert.UNIT: pack('<H6xQII', 1024, 0x715000, 8, 0x21000001),
        concert.POSITION: pack('<H6xQII', 0, 0x715100, 8, 0x21000001),
        concert.RESULT: scalar(2, 2),
        concert.TOURISM: scalar(2, 1500),
    }


class RockFixture(SecondaryPanelFixture):
    def __init__(self):
        original = foundation.enable_turn_units
        with patch.object(foundation, 'enable_turn_units', install_source(original)):
            super().__init__()
        self.saved._xp2_rock_bands = object()
        self.performed = False
        self.emit_concert = True

    def evaluate(self, child, source, name, **options):
        if name not in (b'@rock_band_information', b'@rock_concert_index', b'@rock_concert_request'):
            return super().evaluate(child, source, name, **options)
        assert self.player == 1 and child is self.token.ui_child and b'local pid,turn=1,8\n' in source
        if name == b'@rock_band_information':
            return b'28|3|0|2|1500|0|0' if self.performed else b'28|3|0|1|0|1|1'
        if name == b'@rock_concert_index':
            return b'27'
        assert b'local chosen,x,y,opcode=28,3,0,27\n' in source
        self.queued_panel_command = 'concert'
        self.token.transport.pending.append(pack('<IHH5I', 0x8c0f3f36, self.archive_actor,
                                                  1, 28, 27, 0xffffffff, 0, 0))
        return b'requested'

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.queued_panel_command != 'concert':
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            assert self.player == 1
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, pack('<QQ', self.sentinel, self.sentinel))
            if self.emit_concert:
                owner = self.backend.host._a0_family_owner
                owner.dispatch(concert.KIND, result_fields(self.memory), 0)
                self.performed = True
            self.queued_panel_command = None
        return drain


class RockBandTests(TestCase):
    def test_public_result_requires_the_requested_actor_unit_turn_and_confirmation(self):
        from civ6_host import ProtocolError
        from civ6_host.session_client import _validate_command

        observation = dict(player_id=1, turn=8, units=[dict(owner=1,id=28,x=3,y=0)])
        action = dict(kind=rock_bands.KIND, unit_id=28, x=3, y=0)
        result = dict(schema=rock_bands.RESULT_SCHEMA,player_id=1,turn=8,unit_id=28,
                      x=3,y=0,result_id=2,tourism=1500)
        command = dict(status='completed',reason=None,requested_action=action,concert=result)
        self.assertEqual(_validate_command(command,observation)['concert'],result)
        for field, value in (('player_id',0),('unit_id',29),('turn',9),('x',4),('tourism',True)):
            changed = deepcopy(command)
            changed['concert'][field] = value
            with self.subTest(field=field), self.assertRaises(ProtocolError):
                _validate_command(changed,observation)
        changed = deepcopy(command)
        del changed['concert']
        with self.assertRaises(ProtocolError):
            _validate_command(changed,observation)
        for status in ('refused','submitted','pending'):
            changed = dict(command,status=status)
            with self.subTest(status=status), self.assertRaises(ProtocolError):
                _validate_command(changed,observation)

    def test_result_rejects_invalid_player_and_turn_even_when_self_consistent(self):
        action = dict(kind=rock_bands.KIND, unit_id=28, x=3, y=0)
        result = dict(schema=rock_bands.RESULT_SCHEMA,player_id=1,turn=8,unit_id=28,
                      x=3,y=0,result_id=2,tourism=1500)
        for player, turn in ((True,8),(-1,8),(64,8),(1,True),(1,-1)):
            value = dict(result, player_id=player, turn=turn)
            with self.subTest(player=player,turn=turn), self.assertRaises(ValueError):
                rock_bands.validate_result(value,player,turn,action)

    def test_primary_python_client_and_historical_checkpoint_projection(self):
        from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
        from civ6_host.runtime.network_protocol import NetworkProtocol, validate_network_response

        path = resource_root() / ('work/xp2-workmove/stock-writer/native-runs/'
                                 'run-59f1539157f14da286bd9e1c1fb43f07/events.jsonl')
        self.assertLess(path.stat().st_size, 3*1024**2)
        raw = path.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(),
                         '649cef3fd68b1d2a34af1250b7b57b2bc8a3f4fdac0fbad45d1306fa158eedf5')
        response = json.loads(raw.splitlines()[5440])
        previous = deepcopy(response['decisions'])
        observation = response['observation']
        unit = observation['units'][0]
        panel = dict(schema=rock_bands.SCHEMA, player_id=observation['player_id'],
                     turn=observation['turn'], units=[dict(unit_id=unit['id'], x=unit['x'], y=unit['y'],
                         level=1, album_sales=0, visible=True, available=True)])
        network_turn.add_rock_band_choices(response['decisions'], panel)
        seal(response['decisions'])
        projected, transition = network_turn.checkpoint_catalogue(
            response['decisions'], previous, observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, previous)
        self.assertIn('rock_bands', transition['added_public_fields'])
        self.assertIn(rock_bands.KIND, transition['added_action_families'])
        action, = rock_bands.actions(panel)
        protocol = NetworkProtocol(
            DiagnosticEpisodeIdentity(response['episode_id'],response['game_generation']),
            response['nonce'], initial_turn=observation['turn'], core_sha256=XP2_CORE_SHA256)
        validate_network_response(response,protocol,'reset')
        protocol.accept_response(response)

        def request(query):
            reply = deepcopy(response)
            reply.update(operation='act', sequence=query['sequence'], applied_action=action,
                         command_result=dict(status='completed', reason=None, requested_action=action))
            reply['command_result']['concert'] = dict(schema=rock_bands.RESULT_SCHEMA,
                player_id=observation['player_id'],turn=observation['turn'],
                unit_id=unit['id'],x=unit['x'],y=unit['y'],result_id=2,tourism=1500)
            decisions = reply['decisions']
            decisions['sequence'] = query['sequence']
            for field in decisions.values():
                if type(field) is dict and 'sequence' in field:
                    field['sequence'] = query['sequence']
            decisions['candidates'] = [row for row in decisions['candidates']
                                       if row['action']['kind'] != rock_bands.KIND]
            updated = deepcopy(panel)
            updated['units'][0].update(level=2, album_sales=1500, visible=False, available=False)
            network_turn.add_rock_band_choices(decisions, updated)
            seal(decisions)
            for field,value in (('player_id',1),('turn',observation['turn']+1),
                                ('unit_id',unit['id']+1)):
                changed = deepcopy(reply)
                changed['command_result']['concert'][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    validate_network_response(changed,protocol,'act',request=query)
            changed = deepcopy(reply)
            del changed['command_result']['concert']
            with self.assertRaises(ValueError):
                validate_network_response(changed,protocol,'act',request=query)
            protocol.commit_reply(query,reply)
            protocol.accept_response(reply)
            return reply

        client = SessionClient(SimpleNamespace(reset=lambda: response, request=request, abort=Mock()))
        view = client.reset()
        self.assertEqual(client.information('rock_bands')['data'], panel)
        candidate, = view['decisions']['families'][rock_bands.KIND]['candidate_ids']
        client.act(observation['player_id'], view['decisions']['decision_id'], candidate)
        self.assertEqual(client.command_result['status'], 'completed')
        self.assertEqual(client.command_result['concert']['tourism'], 1500)
        self.assertEqual(client.information('rock_bands')['data']['units'][0]['album_sales'], 1500)

    def test_pinned_native_bindings_and_both_captures(self):
        from civ6_host.runtime.a0_family_source import verify_pinned_files

        with pefile.PE(_PROFILE.path, fast_load=True) as image:
            core = SimpleNamespace(_handle=image.OPTIONAL_HEADER.ImageBase,
                                   _civ6_host_execution_image=_PROFILE)
            read = lambda address, size: image.get_data(address-core._handle, size)
            concert.verify_live(core, read)
            lifetime = (core, object(), object(), object(), object(), xp2_bundle_inputs.REFERENCE)
            saved = SimpleNamespace(backend=SimpleNamespace(runtime=SimpleNamespace(read=read)))
            with patch.object(expansion_city_growth, '_owner', return_value=lifetime):
                bands.bind(saved)
                self.assertTrue(bands.enabled(saved))
        for reference in (xp2_bbg_inputs.REFERENCE, xp2_bundle_inputs.REFERENCE):
            pins = bands.source_dependencies(reference, _PROFILE)
            verify_pinned_files(pins)
            self.assertIn(reference[1], pins.values())
        with self.assertRaises(ValueError):
            bands.source_dependencies(('unqualified', '0'*64), _PROFILE)

    def fixture(self):
        f = RockFixture()
        self.addCleanup(f.close)
        self.enterContext(patch.object(network_timer, 'read', return_value=False))
        self.enterContext(patch.object(expansion_city_growth, '_owner', return_value=f.saved._xp2_rock_bands))
        return f

    def observe(self, f):
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=f.token.identity,
                                   session=dict(turn=8), catalogue=None)
        protocol.selected = lambda request: network_turn.select_capability(
            protocol.catalogue, request['selection'])
        _, protocol.session, observation, choices, _ = xp2_lan_unit_commands.read_reply(
            f.saved, protocol, dict(sequence=1, player_id=1, operation='observe'), (0, 1))
        network_turn.validate_catalogue(choices, protocol.identity, 1, 8,
                                       player_id=1, observation=observation)
        protocol.catalogue = choices
        return protocol, observation, choices

    def request(self, f, protocol, choices):
        candidate, = choices['families'][rock_bands.KIND]['candidate_ids']
        return xp2_lan_unit_commands.read_reply(f.saved, protocol,
            dict(sequence=2, player_id=1, operation='act',
                 selection=dict(decision_id=choices['decision_id'], candidate_id=candidate)), (0, 1))

    def test_secondary_info_command_actual_fifo_and_result_callback(self):
        f = self.fixture()
        protocol, observation, choices = self.observe(f)
        panel = information.project('rock_bands', observation, choices)
        self.assertEqual(panel['units'][0]['album_sales'], 0)
        _, protocol.session, after, current, receipt = self.request(f, protocol, choices)
        self.assertEqual(receipt['status'], 'completed')
        self.assertEqual(receipt['requested_action']['kind'], rock_bands.KIND)
        self.assertEqual(receipt['concert']['player_id'], 1)
        self.assertEqual(receipt['concert']['tourism'], 1500)
        self.assertTrue(f.performed)
        self.assertEqual(f.player, 0)
        self.assertIsNone(f.backend.host._a0_family_owner._xp2_requested_rock_concert)
        self.assertEqual(current['rock_bands']['units'][0]['album_sales'], 1500)
        self.assertEqual(current['families'][rock_bands.KIND]['candidate_ids'], [])
        network_turn.validate_catalogue(current, protocol.identity, 2, 8, player_id=1, observation=after)

    def test_missing_native_callback_stays_submitted(self):
        f = self.fixture()
        f.emit_concert = False
        protocol, _, choices = self.observe(f)
        _, _, _, _, receipt = self.request(f, protocol, choices)
        self.assertEqual(receipt['status'], 'submitted')
        self.assertEqual(receipt['reason'], bands.SUBMITTED)
        self.assertIsNone(f.backend.host._a0_family_owner._xp2_requested_rock_concert)

    def test_foreign_archive_is_refused_before_delivery(self):
        f = self.fixture()
        protocol, _, choices = self.observe(f)
        f.archive_actor = 0
        with self.assertRaisesRegex(ValueError, 'archive differs'):
            self.request(f, protocol, choices)
        self.assertFalse(f.performed)
        self.assertIsNone(f.backend.host._a0_family_owner._xp2_requested_rock_concert)

    def test_actual_empty_owner_preserves_preceding_records_and_rejects_hooks(self):
        from civ6_host.runtime import foundation_event_profile
        from test_xp2_turn_notifications import XP2ComposedNotifications

        original = foundation.enable_turn_units
        pillage = foundation_event_profile.pillage_source
        with (patch.object(foundation, 'enable_turn_units', install_source(original)),
              patch.object(foundation_event_profile, 'pillage_source',
                           lambda **_: pillage(execution_image=_PROFILE))):
            graph = XP2ComposedNotifications().graph()
        owner = graph.owner
        pending = bytes(range(96))
        owner.pending.append(pending)
        before = (owner._sequence, tuple(owner.pending))
        self.assertEqual(owner.dispatch(concert.KIND, result_fields(graph.memory), 0), 0)
        self.assertEqual((owner._sequence, tuple(owner.pending)), before)
        self.assertIs(owner.pending[0], pending)
        owner.per_thread_hook_present = True
        with self.assertRaisesRegex((ValueError, RuntimeError), 'receiver|hooks'):
            owner.dispatch(concert.KIND, result_fields(graph.memory), 0)

    def test_lua51_reader_and_request_revalidate_visibility_movement_and_owner(self):
        lua = LuaRuntime(encoding=None)
        lua.execute(br'''
moves, visible, allowed, owner, active=2,true,true,1,true
local unit={GetOwner=function() return owner end, GetID=function() return 28 end,
 GetX=function() return 3 end, GetY=function() return 0 end,
 GetMovesRemaining=function() return moves end, GetUnitType=function() return 14 end,
 GetRockBand=function() return {GetRockBandLevel=function() return 2 end,
  GetAlbumSales=function() return 1234 end} end}
local units={Members=function() return ipairs({unit}) end,
 FindID=function(_,id) if id==28 then return unit end end}
Players={[1]={GetUnits=function() return units end,IsTurnActive=function() return active end,
 IsTurnActiveComplete=function() return active end}}
Game={GetLocalPlayer=function() return 1 end,GetLocalObserver=function() return 1 end,
 GetCurrentGameTurn=function() return 8 end}
GameInfo={Units={[14]={UnitType='UNIT_ROCK_BAND'}},
 UnitOperations={UNITOPERATION_TOURISM_BOMB={Hash=-2060655393,Index=27,VisibleInUI=true}}}
OperationResultsTypes={NO_TARGETS=99}
UnitManager={CanStartOperation=function(u,op,third,show,flags)
 assert(u==unit and op==-2060655393 and third==nil)
 if show then return visible end
 assert(show==false and flags==99)
 return allowed
 end,
 RequestOperation=function(...)
 assert(select('#',...)==2 and select(1,...)==unit and select(2,...)==-2060655393)
 capture()
 end}
''')
        observation = dict(player_id=1, turn=8)
        requests = []
        lua.globals()[b'capture'] = lambda: requests.append(True)
        self.assertEqual(lua.execute(bands._lua(observation, bands._QUERY)), b'28|3|0|2|1234|1|1')
        constants = b'local chosen,x,y,opcode=28,3,0,27\n'
        self.assertEqual(lua.execute(bands._lua(observation, bands._REQUEST, constants)), b'requested')
        for change in (b'moves=0', b'moves=2; allowed=false', b'allowed=true; active=false',
                       b'active=true; owner=0'):
            lua.execute(change)
            self.assertEqual(lua.execute(bands._lua(observation, bands._REQUEST, constants)), b'refused')
        self.assertEqual(len(requests), 1)

    def test_decoder_owns_blob_copies_and_rejects_foreign_shapes(self):
        f = self.fixture()
        fields = result_fields(f.memory)
        decoded = concert.decode_fields(concert.KIND, fields, f.memory.read)
        f.memory.put(0x715000, bytes(8))
        self.assertEqual((decoded.player_id, decoded.unit_id, decoded.result, decoded.tourism), (1,28,2,1500))
        for invalid in ({}, {**fields, 4: scalar(2, 0)},
                        {**fields, concert.SELECTOR: scalar(3, 1)}):
            with self.assertRaises(ValueError):
                concert.decode_fields(concert.KIND, invalid, f.memory.read)


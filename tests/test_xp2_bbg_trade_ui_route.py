"""Check the official BBG Lua route and the composed host's fail-closed boundary."""
import ctypes as C
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import struct

from civ6_host.runtime.a0_family_source import family_profile
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, _source
from civ6_host.runtime.native.native_aux_map_conversion import encode_script_request_table
from civ6_host.runtime.xp2_bbg_inputs import REFERENCE
from civ6_host.runtime.xp2_bbg_amani import event_source, listener_source, parse_property, parse_request, property_source
from civ6_host.runtime import xp2_bbg_promotion as promotion
from civ6_host.runtime import xp2_bbg_spy as spy
from civ6_host.runtime.xp2_bbg_trade_feedback import TradeFeedback, _requests, lua_bridge
import test_a0_family_service as shared

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None


class BBGTradeReceiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = family_profile()

    def test_bbg_activity_cannot_fall_through_to_the_base_empty_receiver(self):
        host, deferred, arguments, owner, reader, *_ = shared.A0FamilyServiceTests.fixture(
            self, XP2_CORE_SHA256,
        )
        owner._foundation_backend = SimpleNamespace(captured_bundle=SimpleNamespace(reference=REFERENCE))
        reader.fields.return_value = {}
        with self.assertRaisesRegex(ValueError, 'requires the official UI-to-gameplay bridge'):
            arguments.dispatch(host.pointer, 0x5d706996, 0x9000)
        self.assertTrue(arguments.quarantined)
        self.assertTrue(owner.quarantined)
        self.assertEqual((deferred._sequence, deferred.consumed_count, deferred.pending), (0, 0, []))
        reader.read.assert_not_called()

    def test_installs_over_the_inherited_records_and_drains_through_the_composed_owner(self):
        from civ6_host.runtime import a0_xp2_bbg_trade as event
        from civ6_host.runtime.native.native_event_5d706996 import FIRST_KEY, SECOND_KEY, SELECTOR_KEY

        host, deferred, arguments, owner, reader, *_ = shared.A0FamilyServiceTests.fixture(
            self, XP2_CORE_SHA256)
        backend = SimpleNamespace(core=deferred.core, profile=SimpleNamespace(execution_image=None))
        owner._foundation_backend = backend
        self.assertTrue(owner.handles_kind(event.KIND))
        self.assertTrue(owner.handles_record(event.RECORD_TYPE))
        producer = dict(dispatch=dict(rva='0x20', bytes=1, sha256=hashlib.sha256(b'x').hexdigest()),
                        callsites=[])
        seen = []
        reader.read.return_value = b'x'
        with patch.object(event, '_profile', return_value=({}, producer)), \
                patch.object(event, '_turn_source', return_value={'core_producers': []}), \
                patch.object(event, '_property_source', return_value=[]), \
                patch.object(event, '_check_owner'):
            event.enable(owner, backend, lambda *args: seen.append(args),
                         on_local_turn_begin=lambda sequence: seen.append((sequence,)))
        reader.fields.return_value = {
            FIRST_KEY: struct.pack('<HHIQII', 1024, 0, 0, 0x1000, 8, 553648129),
            SECOND_KEY: struct.pack('<HHIQII', 1024, 0, 0, 0x2000, 8, 553648129),
            SELECTOR_KEY: struct.pack('<H6xI8xI', 3, 0, 0),
        }
        reader.read.side_effect = lambda address, _: (struct.pack('<HHI', 0, 0, 11)
            if address == 0x1000 else struct.pack('<HHI', 7, 0, 22))
        self.assertEqual(arguments.dispatch(host.pointer, event.KIND, 0x9000), 0)
        self.assertEqual(seen, [])
        self.assertEqual(deferred.drain(), 1)
        self.assertEqual(seen, [(1, 0, 0, 11, 7, 22)])
        property_fields = {
            FIRST_KEY: reader.fields.return_value[FIRST_KEY],
            SELECTOR_KEY: reader.fields.return_value[SELECTOR_KEY],
            # Native attempt two left the unused variant bytes 4..7 nonzero.
            event.PROPERTY_KEY: bytes.fromhex('020000004c5449508b1da645000000000000000000000000'),
        }
        with self.assertRaisesRegex(ValueError, 'Unqualified current BBG city property'):
            event.dispatch_city_property(owner, property_fields, 0x9000)
        with event.expect_city_property(owner, 0, 11):
            reader.fields.return_value = property_fields
            self.assertEqual(arguments.dispatch(host.pointer, event.CITY_PROPERTY_KIND, 0x9000), 0)
            self.assertEqual(struct.unpack_from('<II', deferred.pending[0]), (96, 90))
            self.assertEqual(deferred.drain(), 1)
        self.assertEqual(seen, [(1, 0, 0, 11, 7, 22)])

    def test_compiled_table_variant_reuses_the_map_converter_and_original_scalar(self):
        from civ6_host.runtime.execution_images import known_path, select
        from civ6_host.runtime.xp2_trade_table_variant import source_dependencies

        profile = 'xp2-gamecore-current-092abfbb'
        deps = source_dependencies(execution_image=select(profile, core_path=known_path(profile)))
        library = next(path for path in deps if path.suffix == '.dll')
        self.assertEqual(hashlib.sha256(library.read_bytes()).hexdigest(), deps[library])
        native = C.WinDLL(str(library))
        ptr = C.c_void_p
        native.Civ6HostBindTradeTableVariant.argtypes = [ptr] * 3
        native.Civ6HostUnbindTradeTableVariant.argtypes = [ptr]
        native.Civ6HostPushTradeTableVariant.argtypes = [ptr] * 3
        native.Civ6HostPushTradeTableVariant.restype = None
        calls = []
        scalar = C.CFUNCTYPE(None, ptr, ptr, ptr)(lambda *args: calls.append(('scalar', *args)))
        table = C.CFUNCTYPE(None, ptr, ptr, ptr, C.c_ubyte)(lambda *args: calls.append(('map', *args)))
        self.assertEqual(native.Civ6HostBindTradeTableVariant(5, C.cast(scalar, ptr), C.cast(table, ptr)), 1)
        try:
            variant = C.create_string_buffer(struct.pack('<IIQII', 10, 0, 17, 0, 0x05000000))
            native.Civ6HostPushTradeTableVariant(5, 7, C.addressof(variant))
            self.assertEqual(calls[-1], ('map', 5, 7, 17, 1))
            unknown = C.create_string_buffer(struct.pack('<IIQII', 10, 0, 17, 1, 0x05000000))
            native.Civ6HostPushTradeTableVariant(5, 7, C.addressof(unknown))
            self.assertEqual(calls[-1], ('scalar', 5, 7, C.addressof(unknown)))
        finally:
            self.assertEqual(native.Civ6HostUnbindTradeTableVariant(5), 1)

    def test_governor_and_property_notifications_share_the_composed_fifo(self):
        from civ6_host.runtime import a0_xp2_bbg_amani as amani, a0_xp2_bbg_trade as event

        host, deferred, arguments, owner, reader, *_ = shared.A0FamilyServiceTests.fixture(self, XP2_CORE_SHA256)
        backend = SimpleNamespace(core=deferred.core, profile=SimpleNamespace(execution_image=None))
        owner._foundation_backend = backend
        owner.history_event_profile = owner._history_event_profile = SimpleNamespace(
            record_types_by_kind={amani.GOVERNOR_ASSIGNED: frozenset({amani.ASSIGNED_RECORD})},
            record_sizes={amani.ASSIGNED_RECORD: 112})
        producer = dict(dispatch=dict(rva='0x20', bytes=1, sha256=hashlib.sha256(b'x').hexdigest()),
                        callsites=[])
        seen = []
        reader.read.return_value = b'x'
        with (patch.object(event, '_profile', return_value=({}, producer)),
              patch.object(event, '_turn_source', return_value={'core_producers': []}),
              patch.object(event, '_property_source', return_value=[]),
              patch.object(event, '_check_owner'), patch.object(amani, 'verify_live'),
              patch.object(promotion, 'verify_live'), patch.object(spy, 'verify_live')):
            event.enable(owner, backend, lambda *args: None, on_local_turn_begin=lambda seq: None,
                         on_governor=lambda seq, player, source: seen.append((seq, player, source)),
                         on_promotion=lambda seq, player, unit, source: seen.append((seq, player, unit, source)),
                         on_spy=lambda *args: seen.append(args))
        selector = shared.scalar(3, 0)
        reader.fields.return_value = {0xa1e5a149: selector, 0xd6fcf3e4: shared.scalar(2, 0),
                                      0xa1fbc372: shared.scalar(2, 1)}
        self.assertEqual(arguments.dispatch(host.pointer, amani.GOVERNOR_CHANGED, 0x9000), 0)
        self.assertEqual(seen, [])
        self.assertEqual(deferred.drain(), 1)
        self.assertEqual(seen, [(1, 0, b'return Civ6HostBBGAmani.changed(0,1)')])

        with amani.expect_properties(owner, player=0, plots=((4, 9),), allow_player=True):
            reader.fields.return_value = {0xa1e5a149: selector, 0xd6fcf3e4: shared.scalar(3, 0x259285b3),
                                          0xf06a2af2: shared.scalar(2, 0)}
            self.assertEqual(arguments.dispatch(host.pointer, amani.PLAYER_PROPERTY, 0x9000), 0)
            self.assertEqual(deferred.pending, [])
            reader.read.return_value = struct.pack('<ii', 4, 9)
            reader.fields.return_value = {0xa1e5a149: selector, 0xd6fcf3e4: shared.scalar(2, 0x4c608a17),
                                          0x8c468e3c: struct.pack('<H6xQII', 0, 0x1000, 8, 0x21000001)}
            self.assertEqual(arguments.dispatch(host.pointer, amani.PLOT_PROPERTY, 0x9000), 0)
            self.assertEqual(struct.unpack_from('<Iii', deferred.pending[0], 80), (2, 4, 9))
            self.assertEqual(deferred.drain(), 1)
        from civ6_host.runtime.native.native_unit_value_event_family import UNIT_KEY
        reader.fields.return_value = {0xa1e5a149: selector, 0xd6fcf3e4: shared.scalar(2, 14),
                                      UNIT_KEY: struct.pack('<H6xQII', 1024, 0x2000, 8, 0x21000001)}
        reader.read.return_value = struct.pack('<HHI', 1, 1, 131073)
        self.assertEqual(arguments.dispatch(host.pointer, promotion.KIND, 0x9000), 0)
        self.assertEqual(seen, [(1, 0, b'return Civ6HostBBGAmani.changed(0,1)')])
        self.assertEqual(deferred.drain(), 1)
        self.assertEqual(seen[-1], (3, 1, 131073, b'return Civ6HostBBGPromotion(1,131073,14)'))
        reader.fields.return_value = {0xa1e5a149: shared.scalar(3, 0x81c5bd7e),
                                      0xd6fcf3e4: shared.scalar(2, 0), 0xa1fbc372: shared.scalar(2, 12)}
        self.assertEqual(arguments.dispatch(host.pointer, 0x19087a58, 0x9000), 0)
        self.assertEqual(struct.unpack_from('<IIII', deferred.pending[0]), (96, 86, 4, 0))
        self.assertEqual(struct.unpack_from('<Iii', deferred.pending[0], 80), (4, 0, 12))
        self.assertEqual(deferred.drain(), 1)
        self.assertEqual(seen[-1], (4, 0, 12))
        self.assertEqual((deferred.consumed_count, deferred.pending), (4, []))
        reader.fields.return_value = {0xa1e5a149: selector, 0xd6fcf3e4: shared.scalar(2, 0x4c608a17),
                                      0x8c468e3c: struct.pack('<H6xQII', 0, 0x1000, 8, 0x21000001)}
        with self.assertRaisesRegex(ValueError, 'outside the exact property operation'):
            arguments.dispatch(host.pointer, amani.PLOT_PROPERTY, 0x9000)

    def test_spy_source_and_selector_match_the_current_producer(self):
        from civ6_host.runtime.execution_images import known_path, select

        profile = 'xp2-gamecore-current-092abfbb'
        sources = spy.source_dependencies(execution_image=select(profile, core_path=known_path(profile)))
        self.assertEqual(set(sources.values()), {spy.SOURCE[1], spy.FIFO_SOURCE[1]})
        fields = {0xa1e5a149: shared.scalar(3, 0), 0xd6fcf3e4: shared.scalar(2, 0),
                  0xa1fbc372: shared.scalar(2, 12)}
        with self.assertRaisesRegex(ValueError, 'selector'):
            spy.encode_event(fields, 1)

    def test_active_table_converter_accepts_only_its_auxiliary_slot_on_its_lease(self):
        from civ6_host.runtime.xp2_trade_table_variant import (
            TradeTableVariantReader, matches_active_binding,
        )

        snapshot = tuple(range(1, 25))
        auxiliary = list(snapshot)
        reader = TradeTableVariantReader.__new__(TradeTableVariantReader)
        host = SimpleNamespace(aux_vtable=auxiliary)
        continuation = SimpleNamespace(trade_feedback=SimpleNamespace(table_reader=reader))
        lease = SimpleNamespace(host=host, continuation=continuation)
        reader.host, reader.continuation, reader.active_lease = host, continuation, lease
        reader.push, reader.push_address, reader.original_address = object(), 33, snapshot[20]
        reader.scalar = SimpleNamespace(function=reader.push, address=reader.push_address)
        auxiliary[20] = reader.push_address
        self.assertTrue(matches_active_binding(lease, auxiliary, snapshot))
        self.assertFalse(matches_active_binding(lease, list(auxiliary), snapshot))
        auxiliary[21] = 43
        self.assertFalse(matches_active_binding(lease, auxiliary, snapshot))
        auxiliary[21] = snapshot[21]
        reader.active_lease = None
        self.assertFalse(matches_active_binding(lease, auxiliary, snapshot))


_PROOF = ('work/trade-common-client/xp2-current-trade-registration.json',
          'cdd63fa9e758eb02170ebc7d35a48c9ef7b2fa4e49ae330d64ff2061d79b6f43')


def _source_bytes(reference):
    raw = Path(reference['path']).read_bytes()
    if len(raw) != reference['bytes'] or hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise ValueError('Installed BBG trade script changed')
    return raw


def _between(raw, start, end):
    if raw.count(start) != 1:
        raise ValueError('BBG trade source anchors are ambiguous')
    first = raw.index(start)
    last = raw.find(end, first + len(start))
    if last < 0:
        raise ValueError('BBG trade source anchors are out of order')
    return raw[first:last]


@unittest.skipIf(LuaRuntime is None, 'optional Lua 5.1 fixture unavailable')
class BBGTradeLuaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        files = _source(_PROOF)['bbg_ui_route']['installed_sources']
        ui = _source_bytes(files['scripts/bbg_uitogameplay.lua'])
        cls.bridge = lua_bridge(ui)
        cls.amani_bridge = listener_source(ui)
        gameplay = _source_bytes(files['scripts/bbg_script.lua'])
        cls.promotion_bridge = promotion.listener_source(ui).replace(b'iUnitPlayerID: number, iUnitID : number',
                                                                    b'iUnitPlayerID, iUnitID')
        cls.promotion_gameplay = (_between(gameplay, b'function OnGameplayPromotionFixExp(',
                                           b'function OnCityBuilt(')
                                  .replace(b'iUnitPlayerID: number', b'iUnitPlayerID')
                                  .replace(b' :object', b''))
        cls.spy_bridge = spy.listener_source(ui).replace(b':table', b'')
        cls.spy_gameplay = _between(gameplay, b'function OnGameplaySpyMissionCompleted(', b'local c_BeliefClass')
        cls.ui = (_between(ui, b'local tBufferedParams = {}', b'UIEvents = ExposedMembers.LuaEvents')
                  + _between(ui, b'function OnTradeRouteActivityChanged(', b'function OnGovernorChanged('))
        cls.gameplay = (_between(gameplay, b'function OnGameplaySetAmaniProperty(',
                                 b'function OnGameplayGPGeneralUnifierCreated(')
                        + _between(gameplay, b'function IDToPos(', b'function GetAliveMajorTeamIDs('))

    def setUp(self):
        self.lua = LuaRuntime(encoding=None, max_memory=4 * 1024 * 1024)
        self.lua.execute(b'''
            print = function() end
            allow_unready, outgoing = true, {}
            city_properties, plot_properties, queued = {}, {}, {}
            local player_properties = { AMANI = { iMinorID = 7, Status = 1 } }
            Players = {
                [0] = { CanUnreadyTurn = function() return allow_unready end,
                        GetProperty = function(self, name) return player_properties[name] end },
                [7] = { IsMajor = function() return false end },
                [8] = { IsMajor = function() return false end },
                [9] = { IsMajor = function() return true end },
            }
            local city = {
                GetTrade = function() return { GetOutgoingRoutes = function() return outgoing end } end,
                GetProperty = function(self, name) return city_properties[name] end,
                SetProperty = function(self, name, value) city_properties[name] = value end,
                GetID = function() return 11 end,
                GetX = function() return 1 end,
                GetY = function() return 2 end,
            }
            CityManager = { GetCity = function(pid, cid) return city end }
            Players[0].SetProperty = function(self, name, value) player_properties[name] = value end
            Players[0].GetCities = function()
                return { Members = function() return ipairs({city}) end }
            end
            local plot = {
                GetProperty = function(self, name) return plot_properties[name] end,
                SetProperty = function(self, name, value) plot_properties[name] = value end,
            }
            Map = { GetPlot = function(x, y) assert(x == 1 and y == 2); return plot end }
            PlayerOperations = { EXECUTE_SCRIPT = 0xC665AD08 }
            UI = { RequestPlayerOperation = function(pid, op, params)
                assert(pid == 0 and op == PlayerOperations.EXECUTE_SCRIPT)
                queued[#queued + 1] = params
            end }
        ''')
        self.lua.execute(self.gameplay)
        self.lua.execute(self.ui)

    def _request(self, index, target):
        parameters = dict(self.lua.globals()[b'queued'][index])
        self.assertEqual(parameters, {b'OnStart': b'GameplaySetCSTrader', b'iOriginPlayerID': 0,
                                      b'iOriginCityID': 11, b'iTargetPlayerID': target})
        self.assertTrue(encode_script_request_table(parameters))
        self.lua.globals()[b'OnGameplaySetCSTrader'](0, self.lua.globals()[b'queued'][index])

    def test_city_state_route_and_delayed_removal_recalculate_amani(self):
        self.lua.execute(b'outgoing = {{DestinationCityPlayer = 7}}; OnTradeRouteActivityChanged(0,0,11,7,22)')
        self._request(1, 7)
        self.assertEqual(self.lua.eval(b'city_properties.CS_TRADERS[1]'), 7)
        self.assertEqual(self.lua.eval(b'plot_properties.TRADER_TO_AMANI_CS'), 1)
        self.lua.execute(b'outgoing = {}; allow_unready = false; OnTradeRouteActivityChanged(0,0,11,7,22)')
        self.assertEqual(self.lua.eval(b'#queued'), 1)
        self.assertEqual(self.lua.eval(b'plot_properties.TRADER_TO_AMANI_CS'), 1)
        self.lua.execute(b'OnLocalPlayerTurnBegin()')
        self._request(2, -7)
        self.assertEqual(self.lua.eval(b'#city_properties.CS_TRADERS'), 0)
        self.assertIsNone(self.lua.eval(b'plot_properties.TRADER_TO_AMANI_CS'))

    def test_major_route_does_not_request_script_and_two_removals_keep_lua_order(self):
        self.lua.execute(b'''
            OnTradeRouteActivityChanged(0,0,11,9,23)
            allow_unready = false
            OnTradeRouteActivityChanged(0,0,11,7,22)
            OnTradeRouteActivityChanged(0,0,11,8,23)
        ''')
        self.assertEqual(self.lua.eval(b'#queued'), 0)
        self.lua.execute(b'OnLocalPlayerTurnBegin()')
        self.assertEqual(self.lua.eval(b'#queued'), 1)
        self._request(1, -7)
        self.lua.execute(b'OnLocalPlayerTurnBegin()')
        self.assertEqual(self.lua.eval(b'#queued'), 2)
        self._request(2, -8)

    def test_production_bridge_preserves_the_original_fifo_callbacks(self):
        self.lua.execute(self.bridge)
        self.lua.execute(b'outgoing = {{DestinationCityPlayer = 7}}')
        self.assertEqual(_requests(self.lua.eval(
            b'Civ6HostBBGTradeFeedback.activity(0,0,11,7,22)'), 0), [(0, 11, 7)])
        self.lua.execute(b'outgoing = {}; allow_unready = false')
        for target in (7, 8):
            self.assertEqual(self.lua.eval(
                f'Civ6HostBBGTradeFeedback.activity(0,0,11,{target},22)'.encode()), b'')
        self.assertEqual(self.lua.eval(b'Civ6HostBBGTradeFeedback.buffered()'), b'2')
        self.assertEqual(_requests(self.lua.eval(b'Civ6HostBBGTradeFeedback.turn_begin()')), [(0, 11, -7)])
        self.assertEqual(self.lua.eval(b'Civ6HostBBGTradeFeedback.buffered()'), b'1')
        self.assertEqual(_requests(self.lua.eval(b'Civ6HostBBGTradeFeedback.turn_begin()')), [(0, 11, -8)])
        self.assertEqual(self.lua.eval(b'Civ6HostBBGTradeFeedback.buffered()'), b'0')

    def test_trade_request_owner_is_bound_to_origin_and_survives_official_buffer(self):
        self.lua.execute(self.bridge)
        self.lua.execute(b'Players[1] = Players[0]; outgoing = {{DestinationCityPlayer = 7}}')
        self.assertEqual(_requests(self.lua.eval(
            b'Civ6HostBBGTradeFeedback.activity(0,1,11,7,22)'), 1), [(1, 11, 7)])
        self.lua.execute(b'outgoing = {}; allow_unready = false')
        self.assertEqual(self.lua.eval(b'Civ6HostBBGTradeFeedback.activity(0,1,11,7,22)'), b'')
        self.assertEqual(_requests(self.lua.eval(b'Civ6HostBBGTradeFeedback.turn_begin()')), [(1, 11, -7)])
        with self.assertRaisesRegex(ValueError, 'native event owner'):
            _requests(b'1,11,7', 0)

    def test_amani_ui_listeners_preserve_all_three_official_transitions(self):
        # The production bridge retains the annotations supported by Firaxis Lua.
        fixture = (self.amani_bridge.replace(b'playerID:number, governorTypeIndex:number',
                                            b'playerID, governorTypeIndex')
                   .replace(b'local pPlayer:table', b'local pPlayer')
                   .replace(b'local pPlayerGovernors:table', b'local pPlayerGovernors'))
        self.lua.execute(fixture)
        self.lua.execute(b"""
            amani_established = true
            GameInfo = { Governors = { [1] = { Hash = 123 } } }
            local amani = {
                GetType = function() return 1 end,
                IsEstablished = function(_, mode) assert(mode == 1); return amani_established end,
                GetAssignedCity = function() return CityManager.GetCity(7, 22) end,
            }
            Players[0].GetGovernors = function()
                return {
                    GetGovernorList = function() return true, {amani} end,
                    HasGovernor = function(_, hash) return hash == 123 end,
                }
            end
            Players[0].GetProperty = function()
                return {iCityID = 22, iMinorID = 7, Status = 0}
            end
        """)
        record = bytearray(112)
        struct.pack_into('<III', record, 0, len(record), 223, 11)
        struct.pack_into('<I4xh2xiii', record, 80, 11, 7, 22, 0, 0)
        self.assertIsNone(parse_request(self.lua.execute(event_source(bytes(record), 11)), 0))
        struct.pack_into('<i', record, 100, 1)
        assigned = parse_request(self.lua.execute(event_source(bytes(record), 11)), 0)
        record = bytearray(96)
        struct.pack_into('<III', record, 0, len(record), 224, 12)
        struct.pack_into('<Iii', record, 80, 12, 0, 1)
        changed = event_source(bytes(record), 12)
        established = parse_request(self.lua.execute(changed), 0)
        self.lua.execute(b'amani_established = false')
        removed = parse_request(self.lua.execute(changed), 0)
        for request, status in ((assigned, 0), (established, 1), (removed, -1)):
            self.assertEqual(request.parameters(), {
                b'OnStart': b'GameplaySetAmaniProperty', b'iGovernorOwnerID': 0,
                b'tAmani': {b'iCityID': 22, b'iMinorID': 7, b'Status': status},
            })
            self.assertTrue(encode_script_request_table(request.parameters()))
        with self.assertRaisesRegex(ValueError, 'current player authority'):
            parse_request(b'1,22,7,1', 0)

    def test_governor_event_marshalling_preserves_signed_values_and_requires_its_owned_record(self):
        record = bytearray(112)
        struct.pack_into('<III', record, 0, len(record), 223, 2)
        struct.pack_into('<I4xh2xiii', record, 80, 2, -1, -1, 4, 1)
        self.assertEqual(event_source(bytes(record), 2), b'return Civ6HostBBGAmani.assigned(-1,-1,4,1)')
        with self.assertRaisesRegex(ValueError, 'size or sequence'):
            event_source(bytes(record), 3)
        struct.pack_into('<I', record, 4, 224)
        with self.assertRaisesRegex(ValueError, 'record type'):
            event_source(bytes(record), 2)

    def test_promotion_forwards_the_official_request_and_reads_xp_from_the_same_unit(self):
        self.lua.execute(self.promotion_bridge)
        self.lua.execute(self.promotion_gameplay)
        self.lua.execute(b"""
            xp = 14
            GameInfo = { Units = { [3] = { FormationClass = 'FORMATION_CLASS_LAND_COMBAT' } } }
            local unit = {
                GetOwner = function() return 0 end,
                GetID = function() return 131073 end,
                GetType = function() return 3 end,
                GetExperience = function()
                    return {
                        GetExperiencePoints = function() return xp end,
                        GetExperienceForNextLevel = function() return 45 end,
                        ChangeExperience = function(_, delta) xp = xp + delta end,
                    }
                end,
            }
            UnitManager = {GetUnit = function(owner, id)
                assert(owner == 0 and id == 131073)
                return unit
            end}
        """)
        raw = self.lua.execute(b'return Civ6HostBBGPromotion(0,131073,14)')
        request = promotion.parse_request(raw, 0)
        self.assertEqual(request, {b'OnStart': b'GameplayPromotionFixExp',
                                   b'iUnitPlayerID': 0, b'iUnitID': 131073})
        with self.assertRaisesRegex(ValueError, 'native event owner'):
            promotion.parse_request(raw, 1)
        foreign = self.lua.execute(b'return Civ6HostBBGPromotion(1,131073,14)')
        self.assertEqual(promotion.parse_request(foreign, 1, event_unit=131073)[b'iUnitPlayerID'], 1)
        read = promotion.experience_source(0, 131073)
        self.assertEqual(promotion.parse_experience(self.lua.execute(read)), 14)
        self.lua.globals()[b'OnGameplayPromotionFixExp'](0, self.lua.table_from(request))
        self.assertEqual(promotion.parse_experience(self.lua.execute(read)), 15)

    def test_spy_feedback_runs_the_installed_lua_only_for_its_local_mission(self):
        from civ6_host.runtime import xp2_script_operation

        self.lua.execute(self.spy_bridge)
        self.lua.execute(self.spy_gameplay)
        self.lua.execute(b"""
            Game = {GetLocalPlayer = function() return 0 end}
            EspionageResultTypes = {CAPTURED = 7, KILLED = 8}
            capacity = 2
            local missions = {
                [12] = {InitialResult = 3, EscapeResult = 7},
                [13] = {InitialResult = 8, EscapeResult = 0},
                [14] = {InitialResult = 3, EscapeResult = 0},
            }
            Players[0].GetDiplomacy = function() return {
                GetMission = function(_, owner, id) assert(owner == 0); return missions[id] end,
                GetSpyCapacity = function() return capacity end,
            } end
            Players[0].AttachModifierByID = function(_, modifier)
                assert(modifier == 'MODIFIER_CAPTURED_ADD_SPY_CAPACITY_BBG')
                capacity = capacity + 1
            end
        """)
        seen, submitted = [], []
        feedback = TradeFeedback(SimpleNamespace(
            check=lambda **_: None, publishing=False, observation={'player_id': 0},
            prefix=SimpleNamespace(deferred_events=SimpleNamespace(pending=[], _draining_empty_receivers=False)),
            ui_child=object(), runtime=SimpleNamespace(evaluate_text=lambda _, source, *args, **kw: self.lua.execute(source)),
            owner=SimpleNamespace(emit=lambda stage, **data: seen.append((stage, data)))), None, None)

        def execute_script(continuation, owner, parameters):
            self.assertTrue(encode_script_request_table(parameters))
            submitted.append(parameters)
            self.lua.globals()[b'OnGameplaySpyMissionCompleted'](owner, self.lua.table_from(parameters))
            return {'native_archive_delivered': True}

        for seq, owner, mission in ((1, 0, 12), (2, 0, 13), (3, 0, 14), (4, 1, 12)):
            feedback.spy(seq, owner, mission)
        with patch.object(xp2_script_operation, 'deliver_script_operation', side_effect=execute_script):
            feedback.flush()
        self.assertEqual(submitted, [
            {b'OnStart': b'GameplaySpyMissionCompleted', b'iPlayerID': 0, b'iMissionID': 12, b'State': 0},
            {b'OnStart': b'GameplaySpyMissionCompleted', b'iPlayerID': 0, b'iMissionID': 13, b'State': 1},
        ])
        self.assertEqual([(d['event_sequence'], d['capacity_before'], d['capacity_after']) for _, d in seen],
                         [(1, 2, 3), (2, 3, 3)])
        self.assertFalse(feedback.events)
        with self.assertRaisesRegex(ValueError, 'native event identity'):
            spy.parse_request(b'0,13,0', local_player=0, event_player=0, mission=12)

    def test_official_gameplay_recalculates_held_city_with_an_active_trade_route(self):
        self.lua.execute(b'city_properties.CS_TRADERS = {7}')
        invoke = self.lua.globals()[b'OnGameplaySetAmaniProperty']
        for status, established in ((0, None), (1, 1), (-1, None)):
            parameters = parse_request(f'0,22,7,{status}'.encode('ascii'), 0).parameters()
            parameters[b'tAmani'] = self.lua.table_from(parameters[b'tAmani'])
            invoke(0, self.lua.table_from(parameters))
            self.assertEqual(self.lua.eval(b'Players[0]:GetProperty("AMANI").Status'), status)
            self.assertEqual(self.lua.eval(b'plot_properties.AMANI_ESTABLISHED_CS'), established)
            self.assertEqual(self.lua.eval(b'plot_properties.TRADER_TO_AMANI_CS'), 1)
            amani, plots, positions = parse_property(self.lua.execute(property_source(0)), 0)
            self.assertEqual(amani.status, status)
            self.assertEqual(plots, {11: (bool(established), True)})
            self.assertEqual(positions, {11: (1, 2)})

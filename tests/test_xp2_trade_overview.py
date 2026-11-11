import copy
from hashlib import sha256
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host import InformationUnavailable, SessionClient
from civ6_host.contracts import network_turn, trade_overview
from civ6_host.runtime.native import native_trade_overview as reader
import test_world_congress_active_effects as previous_effects
from test_world_congress_review_client import ReplayBackend, validate

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None


class TradeCivicHookTests(unittest.TestCase):
    def test_owned_fifo_checks_local_civic_and_latches_first_positive_capacity(self):
        from civ6_host.runtime import xp2_trade_overview
        from civ6_host.runtime.a0_family_service import A0FamilyService
        from civ6_host.runtime.execution_images import _PROFILE
        from civ6_host.runtime.native.native_event_87667464 import EventFields, _source_record

        core = SimpleNamespace(_handle=0x180000000, _civ6_host_execution_image=_PROFILE)
        bodies = {'producer': dict(rva=17, bytes=3, sha256=sha256(b'raw').hexdigest())}
        backend = SimpleNamespace(core=core, runtime=SimpleNamespace(read=Mock(return_value=b'raw')),
                                  check_thread=Mock())
        events = SimpleNamespace(core=core, pending=[], consumed_count=0,
                                 _sequence=0, _draining_empty_receivers=False)
        owner = SimpleNamespace(deferred=events, _check=Mock(), handles_record=lambda kind: kind == 192,
                                active_kind=None, policy_unlock_event_profile=None,
                                bbg_trade_event_profile=None, climate_event_profile=None,
                                empty_receiver_state={})
        runtime = SimpleNamespace(evaluate_text=Mock(side_effect=[b'16:0', b'16:1']))
        prefix = SimpleNamespace(deferred_events=events, runtime=runtime, ui_child=object(),
                                 event_arguments=SimpleNamespace(consumer=owner))
        saved = SimpleNamespace(backend=backend, prefix=prefix, emit=Mock(),
                                continuation=SimpleNamespace(check=Mock()))

        def consume_empty(record, sequence, **_):
            self.assertIs(events.pending.pop(0), record)
            events.consumed_count = sequence

        events._consume_empty_record = consume_empty
        with patch.object(xp2_trade_overview, '_civic_source', return_value=(None, {'core_bodies': bodies})):
            xp2_trade_overview.bind_civic_hook(saved)
        backend.runtime.read.assert_called_once_with(core._handle + 17, 3)
        for sequence, player in enumerate((1, 0, 0, 0), 1):
            record = _source_record(sequence, EventFields(0, 2, player))
            events.pending.append(record)
            events._sequence = sequence
            events._draining_empty_receivers = True
            A0FamilyService.consume(owner, record, sequence)
            events._draining_empty_receivers = False
        self.assertEqual(runtime.evaluate_text.call_count, 2)
        self.assertEqual([call.kwargs['capacity'] for call in saved.emit.call_args_list], [0, 1])
        self.assertEqual([call.kwargs['deferred_sequence'] for call in saved.emit.call_args_list], [2, 3])
        self.assertEqual(saved._trade_overview_unlock, (None, True))

    def test_civic_wire_rejects_unbounded_or_malformed_values(self):
        self.assertEqual(reader.parse_civic_capacity(b'16:1'), (16, 1))
        for raw in (b'16:-1', b'16:2147483648', b'16:1\n', b'16:1:2'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                reader.parse_civic_capacity(raw)


_NATIVE_FIXTURE = b'''
local function collection(rows)
 return {
  Members=function()
   local i=0
   return function()
    i=i+1
    local item=rows[i]
    if item then return item:GetID(),item end
   end
  end,
  FindID=function(_,id)
   for _,r in ipairs(rows) do if r:GetID()==id and not r.skipFind then return r end end
  end,
 }
end
function makeCity(owner,id,name,x)
 local outgoing={}
 return {
  outgoing=outgoing,governors={},
  GetOwner=function() return owner end,
  GetID=function() return id end,
  GetName=function() return name end,
  GetX=function() return x end,
  GetY=function() return 0 end,
  GetAllAssignedGovernors=function(self) return self.governors end,
  GetReligion=function() return {GetMajorityReligion=function() return -1 end} end,
  GetTrade=function()
   return {GetOutgoingRoutes=function() return outgoing end,
    HasActiveTradingPost=function(_,origin)
     assert(type(origin)=='table' and Players[origin:GetID()]==origin)
     return origin:GetID()==3
    end}
  end,
 }
end
local function makeUnit(id)
 return {GetID=function() return id end,GetOwner=function() return 1 end,
  GetUnitType=function() return 0 end}
end
function makeGovernor(owner,name,established)
 return {GetOwner=function() return owner end,GetName=function() return name end,
  IsEstablished=function() return established end}
end
own=makeCity(1,10,'Boston',0)
minor=makeCity(2,20,'Hattusa',2)
other=makeCity(3,30,'Rome',3)
unseen=makeCity(3,31,'Never returned',5)
own.outgoing[1]={OriginCityPlayer=1,OriginCityID=10,DestinationCityPlayer=2,
 DestinationCityID=20,TraderUnitID=101}
other.outgoing[1]={OriginCityPlayer=3,OriginCityID=30,DestinationCityPlayer=1,
 DestinationCityID=10,TraderUnitID=301}
other.outgoing[2]={OriginCityPlayer=3,OriginCityID=30,DestinationCityPlayer=2,
 DestinationCityID=20,TraderUnitID=302}
minor.governors={makeGovernor(1,'LOC_GOVERNOR_THE_AMBASSADOR_NAME',true)}
units={makeUnit(101),makeUnit(102)}
capacity=3
local function makePlayer(id,cities)
 return {
  GetID=function() return id end,IsAlive=function() return true end,
  IsTurnActive=function() return true end,IsTurnActiveComplete=function() return true end,
  GetCities=function() return collection(cities) end,
  GetUnits=function() return collection(units) end,
  GetTrade=function()
   return {
    GetNumOutgoingRoutes=function() return 1 end,
    GetOutgoingRouteCapacity=function() return capacity end,
    GetInternationalYieldModifier=function() return 1 end,
   }
  end,
 }
end
Players={[1]=makePlayer(1,{own}),[2]=makePlayer(2,{minor}),[3]=makePlayer(3,{other,unseen})}
PlayerManager={GetAliveMinors=function() return {Players[2]} end}
local trade={}
for _,side in ipairs({'Origin','Destination'}) do
 trade['Calculate'..side..'YieldsFromPotentialRoute']=function() return {1.24,3} end
 trade['Calculate'..side..'YieldsFromPath']=function() return {0,0} end
 trade['Calculate'..side..'YieldsFromModifiers']=function() return {0,0} end
end
trade.CanStartRoute=function(_,origin,cid,destination,did,allowPotential)
 assert(origin==1 and cid==10 and allowPotential==true)
 return destination==3 and did==30
end
function stockLookupFixture()
 local extra=makeCity(1,11,'Vanished from lookup',1)
 extra.skipFind=true
 Players[1].GetCities=function() return collection({own,extra}) end
end
observer=1
Game={
 GetLocalPlayer=function() return 1 end,GetLocalObserver=function() return observer end,
 GetCurrentGameTurn=function() return 64 end,GetTradeManager=function() return trade end,
 GetWorldCongress=function() return {IsInSession=function() return congressInSession==true end} end,
 GetPlayers=function() return {Players[3],Players[1],Players[2]} end,
}
GameInfo={Units={[0]={MakeTradeRoute=true}},Yields={
 [0]={IconString='food',Name='Food'},[1]={IconString='production',Name='Production'},
},GameCapabilities={CAPABILITY_TRADE_VIEW={}}}
Locale={Lookup=function(key,...) return key end}
Map={
 GetGridSize=function() return 8,4 end,GetPlotCount=function() return 32 end,
 GetPlotDistance=function(x,_,destX,_) return math.abs(x-destX) end,
}
'''


@unittest.skipIf(LuaRuntime is None, 'optional Lua 5.1 fixture unavailable')
class TradeOverviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = reader.source(1, 64, 15, check_capacity=True)

    def setUp(self):
        self.lua = LuaRuntime(encoding=None, max_memory=4 * 1024 * 1024)
        self.lua.execute(_NATIVE_FIXTURE)

    def read(self):
        panel, status = reader.parse(self.lua.execute(self.source), 1, 64, 15)
        self.assertEqual(status, 'available')
        return panel

    def test_tabs_preserve_official_scopes_and_the_bbg_amani_quote(self):
        panel = self.read()
        self.assertEqual((panel['active_count'], panel['capacity']), (1, 3))
        self.assertEqual(panel['idle_trader_ids'], [102])
        self.assertEqual(panel['produce_trader_slots'], 1)
        own, = panel['own_routes']
        self.assertEqual((own['unit_id'], own['destination_city'], own['distance']), (101, 20, 2))
        self.assertFalse(own['has_post'])
        self.assertEqual(own['origin_yields']['values'], [3.2, 5])
        self.assertEqual(own['destination_yields']['values'], [3.2, 5])
        incoming, = panel['incoming_routes']
        self.assertEqual((incoming['origin_city'], incoming['destination_city']), (30, 10))
        self.assertNotIn('unit_id', incoming)
        self.assertTrue(incoming['has_post'])
        potential, = panel['available_routes']
        self.assertEqual((potential['origin_city'], potential['destination_city']), (10, 30))
        self.assertEqual(potential['origin_yields']['values'], [1.2, 3])

    def test_stock_trade_uses_the_standard_helper_and_city_lookup(self):
        self.lua.execute(b'stockLookupFixture()')
        stock = trade_overview.STOCK_PROFILE
        source = reader.source(1, 64, 15, check_capacity=True, profile=stock)
        raw = self.lua.execute(source)
        panel, status = reader.parse(raw, 1, 64, 15, profile=stock)
        self.assertEqual(status, 'available')
        self.assertEqual(panel['own_routes'][0]['origin_yields']['values'], [1.2, 3])
        self.assertEqual(panel['own_routes'][0]['destination_yields']['values'], [1.2, 3])
        self.assertEqual([row['origin_city'] for row in panel['available_routes']], [10])
        self.assertEqual(len(panel['incoming_routes']), 1)
        observation = dict(player_id=1, turn=64, cities=[dict(id=10)], units=[dict(id=102)])
        self.assertEqual(trade_overview.compare_player(panel, observation, 15, profile=stock), panel)
        with self.assertRaisesRegex(ValueError, 'absent own city'):
            trade_overview.compare_player(panel, dict(observation, cities=[]), 15, profile=stock)
        with self.assertRaisesRegex(ValueError, 'display profile'):
            reader.parse(raw, 1, 64, 15)
        self.lua.execute(b'congressInSession=true')
        raw = self.lua.execute(source)
        self.assertEqual(reader.parse(raw, 1, 64, 15, profile=stock),
                         (None, 'ui_boundary_unavailable'))
        with self.assertRaisesRegex(ValueError, 'availability'):
            reader.parse(raw, 1, 64, 15)

    def test_available_tab_is_independent_of_idle_trader_and_spare_capacity(self):
        self.lua.execute(b'units[2]=nil; capacity=1')
        panel = self.read()
        self.assertEqual(panel['idle_trader_ids'], [])
        self.assertEqual(panel['produce_trader_slots'], 0)
        self.assertEqual(len(panel['available_routes']), 1)
        for setup in (
                b"minor.governors={makeGovernor(3,'LOC_GOVERNOR_THE_AMBASSADOR_NAME',true)}",
                b"minor.governors={makeGovernor(1,'LOC_GOVERNOR_THE_AMBASSADOR_NAME',false)}",
                b"minor.governors={makeGovernor(1,'LOC_GOVERNOR_THE_DEFENDER_NAME',true)}"):
            with self.subTest(setup=setup):
                self.lua.execute(setup)
                self.assertEqual(self.read()['own_routes'][0]['origin_yields']['values'], [1.2, 3])

    def test_selected_bbg_chooser_uses_its_displayed_yields_in_both_directions(self):
        from civ6_host.runtime.native import native_saved_trade as chooser
        expression = b'''
return yields(own,minor,false).values[1],yields(own,minor,true).values[2]
'''
        stock = chooser.source(1,64)
        bbg = chooser.source(1,64,bbg_display=True)
        self.assertTrue(stock.endswith(chooser.LUA.encode()))
        self.assertTrue(bbg.endswith(chooser.LUA.encode()))
        self.assertEqual(self.lua.execute(stock+expression), (1.24,3))
        self.assertEqual(self.lua.execute(bbg+expression), (3.24,5))
        self.lua.execute(b"minor.governors={makeGovernor(3,'LOC_GOVERNOR_THE_AMBASSADOR_NAME',true)}")
        self.assertEqual(self.lua.execute(bbg+expression), self.lua.execute(stock+expression))

    def test_locked_or_disabled_panel_exposes_no_rows(self):
        self.lua.execute(b'capacity=0')
        raw = self.lua.execute(self.source)
        self.assertEqual(reader.parse(raw, 1, 64, 15), (None, 'unlock_history_unavailable'))
        with self.assertRaisesRegex(ValueError, 'availability'):
            reader.parse(raw, 1, 64, 16)
        self.lua.execute(b'GameInfo.GameCapabilities.CAPABILITY_TRADE_VIEW=nil')
        self.assertEqual(reader.parse(self.lua.execute(self.source), 1, 64, 15),
                         (None, 'trade_view_disabled'))

    def test_unlock_stays_latched_when_capacity_drops_to_zero(self):
        self.read()
        self.lua.execute(b'capacity=0')
        latched = reader.source(1, 64, 15, check_capacity=False, unlocked=True)
        panel, status = reader.parse(self.lua.execute(latched), 1, 64, 15)
        self.assertEqual(status, 'available')
        self.assertEqual(panel['capacity'], 0)
        self.assertEqual(panel['idle_trader_ids'], [])
        self.assertEqual(len(panel['incoming_routes']), 1)
        self.lua.execute(b'capacity=3')
        locked = reader.source(1, 64, 15, check_capacity=False)
        self.assertEqual(reader.parse(self.lua.execute(locked), 1, 64, 15),
                         (None, 'unlock_history_unavailable'))

    def test_binds_the_panel_to_the_public_view_and_rejects_leaks(self):
        panel = self.read()
        observation = dict(player_id=1, turn=64, width=8, height=4,
                           cities=[dict(id=10)], units=[dict(id=101, x=0, y=0), dict(id=102, x=0, y=0)])
        active = {key: panel['own_routes'][0][key] for key in (*trade_overview.PAIR, 'unit_id')}
        routes = dict(player_id=1, turn=64, width=8, height=4, traders=[], active_routes=[active])
        self.assertEqual(trade_overview.compare_own(panel, observation, routes, 15), panel)
        for field, key, value in (
                ('incoming_routes', 'unit_id', 301),
                ('incoming_routes', 'destination_owner', 2),
                ('available_routes', 'origin_owner', 3),
                ('own_routes', 'unit_id', 103)):
            with self.subTest(field=field, key=key):
                wrong = copy.deepcopy(panel)
                wrong[field][0][key] = value
                with self.assertRaises(ValueError):
                    trade_overview.compare_own(wrong, observation, routes, 15)
        with self.assertRaisesRegex(ValueError, 'boundary'):
            trade_overview.compare_own(panel, observation, routes, 16)
        self.lua.execute(b'observer=3')
        with self.assertRaisesRegex(Exception, 'trade perspective changed'):
            self.read()


class TradeOverviewClientTests(unittest.TestCase):
    def setUp(self):
        self.reply, _ = previous_effects.ActiveEffectsContractTests().upgraded()
        self.old = self.reply['decisions']
        quote = dict(values=[], majority_religion=-1, religion_pressure=-1,
                     path_bonus=False, tooltip='')
        rows = [dict(row, origin_name='Origin', destination_name='Destination', distance=1,
                     has_post=False, origin_yields=quote, destination_yields=quote)
                for row in self.old['trade_routes']['active_routes']]
        rows.sort(key=lambda row: tuple(row[k] for k in (*trade_overview.PAIR, 'unit_id')))
        self.panel = dict(schema=trade_overview.SCHEMA, profile=trade_overview.PROFILE,
                          player_id=self.old['player_id'], turn=self.old['turn'], sequence=self.old['sequence'],
                          active_count=len(rows), capacity=len(rows), idle_trader_ids=[], produce_trader_slots=0,
                          own_routes=rows, incoming_routes=[], available_routes=[])

    def upgrade(self, panel, status):
        current = network_turn.upgrade_trade_overview_catalogue(
            self.old, panel, observation=self.reply['observation'], status=status)
        validate(current, self.reply['observation'])
        return current

    def test_client_adds_a_cached_group_without_changing_choices(self):
        current = self.upgrade(self.panel, 'available')
        self.assertEqual(current['candidates'], self.old['candidates'])
        self.assertEqual(current['families'], self.old['families'])
        self.reply['decisions'] = current
        backend = ReplayBackend(self.reply)
        client = SessionClient(backend, allow_administrative=True)
        client.reset()
        result = client.information('trade_overview')
        self.assertEqual(result['data'], self.panel)
        self.assertEqual(result['native_decision_id'], current['decision_id'])
        result['data']['capacity'] += 1
        self.assertEqual(client.information('trade_overview')['data'], self.panel)
        with self.assertRaises(InformationUnavailable):
            client.information('trade_overview', channel='administrative')
        self.assertEqual(backend.calls, [])

    def test_old_and_unavailable_replies_do_not_turn_into_empty_panels(self):
        client = SessionClient(ReplayBackend(self.reply))
        client.reset()
        with self.assertRaises(InformationUnavailable):
            client.information('trade_overview')
        self.reply['decisions'] = self.upgrade(None, 'unlock_history_unavailable')
        client = SessionClient(ReplayBackend(self.reply))
        client.reset()
        with self.assertRaisesRegex(InformationUnavailable, 'unlock_history_unavailable'):
            client.information('trade_overview')
        with self.assertRaisesRegex(ValueError, 'availability'):
            self.upgrade(self.panel, 'trade_view_disabled')

    def test_checkpoint_transition_leaves_previous_catalogue_exact(self):
        current = self.upgrade(self.panel, 'available')
        projected, transition = network_turn.checkpoint_catalogue(
            current, self.old, self.reply['observation'], core_sha256=network_turn._XP2_COMBAT_CORE)
        self.assertEqual(projected, self.old)
        self.assertEqual(transition['added_public_fields'], ['trade_overview', 'trade_overview_status'])
        self.assertNotIn('added_action_families', transition)

from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from civ6_host.contracts import diplomacy_overview as contract, information, network_turn
from civ6_host.runtime import xp2_major_deals as deals
import test_initial_diplomacy_capabilities as capability_fixture
from test_xp2_city_state_peace import ACTION, PEACE_PANEL

try:
    from lupa.lua51 import LuaError, LuaRuntime
except ImportError:
    LuaRuntime = None


def frame():
    return dict(schema=contract.CITY_STATE_PEACE_SCHEMA, capability=True, paused=False,
                complete_action_space=False, player_id=0, turn=8, city_state_peace=deepcopy(PEACE_PANEL),
                targets=[dict(player_id=2, selections=[], relationship=None)])


LUA = '''
observer, met, living=0,true,true
Game={GetLocalPlayer=function() return 0 end, GetLocalObserver=function() return observer end,
 GetCurrentGameTurn=function() return 8 end}
Players={[0]={GetID=function() return 0 end, GetDiplomacy=function()
 return {HasMet=function(_,id) assert(id==2); return met end} end},
 [2]={GetID=function() return 2 end, IsMajor=function() return true end,
 IsAlive=function() return living end}}
DealItemTypes={GOLD=1, RESOURCES=2}
DealItemSubTypes={NONE=0}
local function item(duration, amount, index)
 return {GetDuration=function() return duration end, GetAmount=function()
  assert(duration~=0,'lump sum inspected'); return amount end,
  GetEnactedTurn=function() return 4 end,
  GetValueType=function() assert(index,'gold index inspected'); return index end}
end
local deal={FindItemsByType=function(_,kind,sub,giver)
 assert(sub==0 and (giver==0 or giver==2))
 if kind==1 and giver==0 then return {item(30,3),item(0,200)} end
 if kind==2 and giver==2 then return {item(15,1,6)} end
end}
queries=0
DealManager={HasPendingDeal=function(a,b) assert(a==0 and b==2); queries=queries+1; return true end,
 GetPlayerDeals=function(a,b) assert(a==0 and b==2); queries=queries+1; return {deal} end}
'''


class MajorDealTests(unittest.TestCase):
    def test_selected_native_reader_spans_are_required(self):
        import pefile
        from civ6_host.runtime import execution_images

        image = execution_images.select('xp2-gamecore-current-092abfbb',
                                        core_path=execution_images._GAMECORE_PATH)
        pe = pefile.PE(image.path, fast_load=True)
        self.addCleanup(pe.close)
        base = 0x180000000
        deals.verify_live(base, lambda address, size: pe.get_data(address-base, size),
                          execution_image=image)
        with self.assertRaisesRegex(ValueError, 'source changed'):
            deals.verify_live(base, lambda address, size: bytes(size), execution_image=image)

    @unittest.skipIf(LuaRuntime is None, 'Lua fixture unavailable')
    def test_only_local_pending_status_and_reported_per_turn_terms_are_read(self):
        lua = LuaRuntime()
        lua.execute(LUA)
        overview = frame()
        code = deals.source(overview).decode('ascii')
        raw = lua.execute(code)
        prefix = SimpleNamespace(ui_child=object(), runtime=Mock())
        prefix.runtime.evaluate_text.return_value = raw.encode('ascii')
        out = deals.read(prefix, overview)
        self.assertEqual(out['major_deals'], [dict(player_id=2, pending=True, terms=[
            dict(direction='outgoing', kind='gold', amount=3, remaining_turns=26, resource_index=None),
            dict(direction='incoming', kind='resource', amount=1, remaining_turns=11, resource_index=6)])])
        self.assertEqual(contract.candidates(out), contract.candidates(overview))
        self.assertEqual(lua.globals().queries, 2)
        for invalid in ('observer=1', 'observer=0; met=false', 'met=true; living=false'):
            lua.execute(invalid)
            with self.assertRaises(LuaError):
                lua.execute(code)
            self.assertEqual(lua.globals().queries, 2)

    def test_foreign_and_extra_fields_are_refused(self):
        row = dict(player_id=2, pending=True, terms=[])
        for invalid in ([], [dict(row, player_id=3)], [dict(row, pending=1)], [dict(row, ai_value=0)]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                value = dict(frame(), schema=contract.MAJOR_DEALS_SCHEMA, major_deals=invalid)
                contract.validate(value, 0, 8)

    def test_checkpoint_projection_keeps_the_live_city_state_action_for_v3(self):
        capability_fixture.InitialDiplomacyCapabilityTests.setUpClass()
        fixture = capability_fixture.InitialDiplomacyCapabilityTests()
        v2, obs = fixture._active_v33()
        overview = v2['diplomacy_overview']
        overview['schema'] = contract.RELATIONSHIPS_SCHEMA
        for target in overview['targets']:
            target['relationship'] = None
        fixture._redigest(v2)
        v3 = deepcopy(v2)
        v3['diplomacy_overview'].update(schema=contract.CITY_STATE_PEACE_SCHEMA,
                                        city_state_peace=deepcopy(PEACE_PANEL))
        offer = dict(action=ACTION, candidate_id=network_turn.digest(ACTION))
        v3['candidates'].append(offer)
        v3['families']['diplomacy_initiate']['candidate_ids'].append(offer['candidate_id'])
        fixture._redigest(v3)
        current = deepcopy(v3)
        rows = [dict(player_id=2, pending=False, terms=[])]
        current['diplomacy_overview'].update(schema=contract.MAJOR_DEALS_SCHEMA, major_deals=rows)
        fixture._redigest(current)
        fixture._validate(current, obs)
        self.assertEqual(information.project('diplomacy', obs, current)['major_deals'], rows)
        for previous in (v2, v3):
            projected, receipt = network_turn.checkpoint_catalogue(
                current, previous, obs, core_sha256=capability_fixture.XP2_CORE)
            self.assertEqual(projected, previous)
            self.assertIn('diplomacy_overview.major_deals', receipt['added_public_fields'])
            self.assertEqual(bool(receipt.get('added_action_variants')), previous is v2)

    def test_draft_only_adds_a_candidate_for_a_met_ai_without_a_pending_deal(self):
        overview = frame()
        overview['targets'][0]['selections'] = [
            dict(key=contract.OPEN_DEAL, disabled=False, supported=False, text=None,
                 tooltip=None, diplomatic_action_type=None)]
        prior = dict(overview, schema=contract.MAJOR_DEALS_SCHEMA,
                     major_deals=[dict(player_id=2, pending=False, terms=[])])
        for pending, human in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(pending=pending, human=human):
                prefix = SimpleNamespace(ui_child=object(), runtime=Mock())
                state = str(pending).lower()
                counterparty = str(human).lower()
                prefix.runtime.evaluate_text.return_value = (
                    f'[{{"player_id":2,"pending":{state},"terms":[],"counterparty_is_human":{counterparty}}}]'
                    .encode('ascii'))
                latest = deals.read(prefix, overview, draft=True)
                added = [dict(kind='diplomacy_initiate', target_player_id=2, choice=contract.OPEN_DEAL)]
                self.assertEqual(contract.candidates(latest),
                                 (added if not (pending or human) else []) + contract.candidates(overview))
                expected = dict(prior, major_deals=[dict(player_id=2, pending=pending, terms=[])])
                self.assertEqual(contract.project_legacy(latest, 0, 8, schema=contract.MAJOR_DEALS_SCHEMA),
                                 expected)
                current = deepcopy(latest)
                current['schema'] = contract.OPEN_BORDERS_SCHEMA
                current['major_deals'][0]['open_borders'] = dict(outgoing=False,incoming=True)
                self.assertEqual(contract.project_legacy(current, 0, 8, schema=contract.DEAL_DRAFT_SCHEMA), latest)
                self.assertEqual(contract.candidates(current), contract.candidates(latest))

    def test_major_peace_adds_one_choice_and_preserves_city_state_peace_on_reload(self):
        capability_fixture.InitialDiplomacyCapabilityTests.setUpClass()
        fixture = capability_fixture.InitialDiplomacyCapabilityTests()
        current, obs = fixture._active_v33()
        prior = current['diplomacy_overview']
        prior.update(schema=contract.CITY_STATE_PEACE_SCHEMA, city_state_peace=deepcopy(PEACE_PANEL))
        for target in prior['targets']:
            target['relationship'] = None
        prior['targets'][0]['selections'].append(dict(key=contract.MAKE_PEACE, disabled=False,
            supported=False, text=None, tooltip=None, diplomatic_action_type=None))
        prefix = SimpleNamespace(ui_child=object(), runtime=Mock())
        prefix.runtime.evaluate_text.return_value = (
            b'[{"player_id":2,"pending":false,"terms":[],"counterparty_is_human":false,'
            b'"open_borders":{"outgoing":false,"incoming":false}}]'
        )
        previous = deepcopy(current)
        previous['diplomacy_overview'] = deals.read(prefix, prior, draft=True, open_borders=True, demand=True)
        current['diplomacy_overview'] = deals.read(prefix, prior, draft=True, open_borders=True,
                                                  demand=True, major_peace=True)
        by_target = dict(kind='diplomacy_initiate', target_player_id=2, choice=contract.MAKE_PEACE)
        expected_major = next(action for action in contract.candidates(current['diplomacy_overview'])
                              if action == by_target)
        for catalogue in (previous, current):
            panel = catalogue['diplomacy_overview']
            offers = [dict(action=action, candidate_id=network_turn.digest(action))
                      for action in contract.candidates(panel)]
            catalogue['candidates'] = [row for row in catalogue['candidates']
                                       if row['action']['kind'] != 'diplomacy_initiate'] + offers
            catalogue['families']['diplomacy_initiate']['candidate_ids'] = [row['candidate_id'] for row in offers]
            fixture._redigest(catalogue)
            fixture._validate(catalogue, obs)
        projected, proof = network_turn.checkpoint_catalogue(
            current, previous, obs, core_sha256=capability_fixture.XP2_CORE)
        self.assertEqual(proof['added_action_variants'], ['diplomacy_initiate.open_major_peace'])
        self.assertIn(expected_major, [row['action'] for row in current['candidates']])
        self.assertNotIn(expected_major, [row['action'] for row in projected['candidates']])
        self.assertIn(ACTION, [row['action'] for row in projected['candidates']])
        self.assertEqual(projected, previous)

    def test_stock_negotiation_follows_native_selection_and_keeps_the_historical_panels(self):
        overview = frame()
        overview.pop('city_state_peace')
        overview['schema'] = contract.RELATIONSHIPS_SCHEMA
        overview['targets'][0]['selections'] = [
            dict(key=key, supported=(key == contract.DENOUNCE or key in
                 contract.STOCK_DIRECT_AI_CHOICES[contract.STOCK_PROMISE_SCHEMA]), disabled=False,
                 text=None, tooltip=None, diplomatic_action_type=None)
            for key in (contract.DENOUNCE, contract.MAKE_PEACE, contract.OPEN_DEAL, contract.OPEN_DEMAND,
                        *contract.PROMISE_CHOICES, contract.DECLARE_FRIENDSHIP)]
        for pending, human, disabled in (
                (False, False, False), (True, False, False), (False, True, False), (False, False, True)):
            with self.subTest(pending=pending, human=human, disabled=disabled):
                previous = deepcopy(overview)
                previous['targets'][0]['selections'][1]['disabled'] = disabled
                previous['targets'][0]['selections'][-2]['disabled'] = disabled
                previous['targets'][0]['selections'][-1]['disabled'] = disabled
                prefix = SimpleNamespace(ui_child=object(), runtime=Mock())
                reported = dict(player_id=2, pending=pending, terms=[], counterparty_is_human=human)
                active = None if human else ['DONT_CONVERT_MY_CITIES']
                prefix.runtime.evaluate_text.return_value = json.dumps(
                    [dict(reported, open_borders=dict(outgoing=False, incoming=True),
                          active_promises=active)]).encode('ascii')
                result = deals.read_stock_negotiation(prefix, previous)
                self.assertEqual(result['targets'][0]['active_promises'], active)
                expected = [contract.DENOUNCE]
                if not (pending or human or disabled):
                    expected.append(contract.MAKE_PEACE)
                if not (pending or human):
                    expected.extend((contract.OPEN_DEAL, contract.OPEN_DEMAND))
                if not human:
                    expected.extend(contract.PROMISE_CHOICES[:-1] if disabled else contract.PROMISE_CHOICES)
                if not (human or disabled):
                    expected.append(contract.DECLARE_FRIENDSHIP)
                self.assertEqual([row['choice'] for row in contract.candidates(result)], expected)
                for item in previous['targets'][0]['selections']:
                    if item['key'] in contract.STOCK_DIRECT_AI_CHOICES[contract.STOCK_PROMISE_SCHEMA]:
                        item['supported'] = False
                self.assertEqual(contract.project_legacy(result, 0, 8,
                    schema=contract.RELATIONSHIPS_SCHEMA), previous)
                negotiation = contract.project_legacy(result, 0, 8, schema=contract.STOCK_NEGOTIATION_SCHEMA)
                self.assertEqual(negotiation['major_deals'], result['major_deals'])
                self.assertEqual(contract.candidates(negotiation), [row for row in contract.candidates(result)
                    if row['choice'] not in (*contract.PROMISE_CHOICES, contract.DECLARE_FRIENDSHIP)])
                friendship = contract.project_legacy(result, 0, 8, schema=contract.STOCK_FRIENDSHIP_SCHEMA)
                self.assertEqual(contract.candidates(friendship), [row for row in contract.candidates(result)
                    if row['choice'] not in contract.PROMISE_CHOICES])
                previous_promises = contract.project_legacy(result, 0, 8, schema=contract.STOCK_PROMISE_SCHEMA)
                self.assertNotIn('active_promises', previous_promises['targets'][0])
                self.assertEqual(contract.candidates(previous_promises), contract.candidates(result))
                if human:
                    result['targets'][0]['selections'][-1]['supported'] = True
                    with self.assertRaisesRegex(ValueError, 'AI counterparty'):
                        contract.validate(result, 0, 8)
                    result['targets'][0]['selections'][-1]['supported'] = False
                historical = contract.project_legacy(result, 0, 8, schema=contract.STOCK_MAJOR_PEACE_SCHEMA)
                self.assertEqual(historical['major_deals'], [reported])
                self.assertEqual([row['choice'] for row in contract.candidates(historical)],
                                 [key for key in expected if key in (contract.DENOUNCE, contract.MAKE_PEACE)])
                with self.assertRaises(ValueError):
                    contract.project_legacy(result, 0, 8, schema=contract.MAJOR_PEACE_SCHEMA)

    @unittest.skipIf(LuaRuntime is None, 'Lua fixture unavailable')
    def test_stock_promise_status_uses_the_ui_getter_from_the_observing_player(self):
        lua = LuaRuntime()
        lua.execute(LUA + """
human,queryCount=false,0
PromiseTypes={DONT_SETTLE_NEAR_ME=101,DONT_SPY_ON_ME=102,
              DONT_DIG_UP_MY_ARTIFACTS=103,DONT_CONVERT_MY_CITIES=104}
local getDiplomacy=Players[0].GetDiplomacy
Players[0].GetDiplomacy=function()
 local base=getDiplomacy()
 base.HasOpenBordersFrom=function(_,peer) assert(peer==2);return false end
 base.IsPromiseMade=function(_,peer,kind)
   assert(not human and peer==2 and kind>=101 and kind<=104)
   queryCount=queryCount+1
   return kind==102 or kind==104
 end
 return base
end
Players[2].GetDiplomacy=function()
 return {HasOpenBordersFrom=function(_,peer) assert(peer==0);return false end}
end
Players[2].IsHuman=function() return human end
""")
        initial = frame()
        del initial['city_state_peace']
        initial['schema'] = contract.RELATIONSHIPS_SCHEMA
        prefix = SimpleNamespace(ui_child=object(), runtime=Mock())
        prefix.runtime.evaluate_text.side_effect = lambda _child, src, *_args, **_kwargs: (
            lua.execute(src.decode('ascii')).encode('ascii'))
        value = deals.read_stock_negotiation(prefix, initial)
        self.assertEqual(value['targets'][0]['active_promises'],
                         ['DONT_SPY_ON_ME', 'DONT_CONVERT_MY_CITIES'])
        self.assertEqual(lua.globals().queryCount, 4)
        lua.execute('human=true')
        value = deals.read_stock_negotiation(prefix, initial)
        self.assertIsNone(value['targets'][0]['active_promises'])
        self.assertEqual(lua.globals().queryCount, 4)
        lua.execute('human=false; PromiseTypes=nil')
        with self.assertRaisesRegex(LuaError, 'Native PromiseTypes'):
            deals.read_stock_negotiation(prefix, initial)


if __name__ == '__main__':
    unittest.main()

"""Loyalty panel precision, own-city boundary and coexistence with growth."""

from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest

from civ6_host.contracts import city_growth, information, network_turn
from civ6_host.runtime import expansion_city_growth, expansion_city_loyalty as reader
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from test_session_capabilities import seal


PRELUDE = br'''
actor, observer, turn, owner, cityID = 0, 0, 76, 0, 65536
outcome, countdown, transfer = 4, 5, 1
Game = {
    GetLocalPlayer = function() return actor end,
    GetLocalObserver = function() return observer end,
    GetCurrentGameTurn = function() return turn end,
}
IdentityConversionOutcome = {GAINING_LOYALTY=3, LOSING_LOYALTY=4}
GameInfo = {LoyaltyLevels = {[2] = {Name='LOC_LOW_LOYALTY'}}}
Locale = {Lookup = function(key) return key end}
local identity = {
    GetLoyalty = function() return 22.567 end,
    GetMaxLoyalty = function() return 100 end,
    GetLoyaltyPerTurn = function() return -0.567 end,
    GetLoyaltyLevel = function() return 2 end,
    GetLoyaltyPerTurnStatus = function() return 'LOC_CITY_LOYALTY_FALLING' end,
    GetPotentialTransferPlayer = function() return transfer end,
    GetConversionOutcome = function() return outcome end,
    GetTurnsToConversion = function() return countdown end,
    GetIdentitySourcesDetailedBreakdown = function()
        return {{['Citoyens']=3.25}, {['Influence']=-2.42}, {['Bonus nul']=0},
                {['Mineur']=-0.01}}
    end,
}
local city = {
    GetID = function() return cityID end,
    GetOwner = function() return owner end,
    GetCulturalIdentity = function() assert(owner==actor); return identity end,
}
Players = {[0] = {GetCities=function() return {Members=function() return ipairs({city}) end} end}}
'''


class ExpansionCityLoyaltyTests(unittest.TestCase):
    def lua(self):
        from lupa.lua51 import LuaRuntime
        runtime = LuaRuntime(encoding=None)
        runtime.execute(PRELUDE)
        return runtime

    def observation(self):
        return dict(player_id=0, turn=76, cities=[dict(id=65536, owner=0)])

    def test_rounding_pressure_and_native_displayed_conversion(self):
        lua = self.lua()
        source = reader.build_source(0, 76)
        data = reader.parse(lua.execute(source), 0, 76, self.observation())
        row, = data['cities']
        self.assertEqual((row['current'], row['maximum'], row['per_turn']), (22.6, 100, -0.6))
        self.assertEqual((row['trend'], row['conversion_turns'], row['potential_new_owner']),
                         ('losing', 5, 1))
        self.assertEqual(row['level_name'], 'LOC_LOW_LOYALTY')
        self.assertEqual(row['sources'], [
            dict(name='Citoyens', change=3.3, negative=False),
            dict(name='Influence', change=-2.4, negative=True),
            dict(name='Mineur', change=0, negative=True),
        ])
        lua.execute(b'outcome=3; countdown=0; transfer=-1')
        row, = reader.parse(lua.execute(source), 0, 76, self.observation())['cities']
        self.assertEqual((row['trend'], row['conversion_turns'], row['potential_new_owner']),
                         ('gaining', None, None))
        lua.execute(b'outcome=2; countdown=9')
        row, = reader.parse(lua.execute(source), 0, 76, self.observation())['cities']
        self.assertEqual((row['trend'], row['conversion_turns']), ('stable', None))

    def test_roster_and_perspective_guards(self):
        from lupa.lua51 import LuaError
        lua = self.lua()
        source = reader.build_source(0, 76)
        data = lua.execute(source)
        with self.assertRaisesRegex(ValueError, 'roster differs'):
            reader.parse(data, 0, 76, dict(self.observation(), cities=[]))
        with self.assertRaisesRegex(ValueError, 'Foreign city loyalty'):
            reader.parse(data, 0, 77, self.observation())
        lua.execute(b'owner=1')
        with self.assertRaisesRegex(LuaError, 'another player'):
            lua.execute(source)
        lua.execute(b'owner=0; observer=1')
        with self.assertRaisesRegex(LuaError, 'foreign or stale'):
            lua.execute(source)

    def test_all_admitted_exact_captures_pin_verified_loyalty_interfaces(self):
        import pefile
        for reference, (image, _) in expansion_city_growth.CAPTURES.items():
            with self.subTest(engine=image.id, reference=reference[0]):
                pins = reader.source_dependencies(reference, image)
                self.assertIn(reference[1], pins.values())
                selected = reader._profile(reference, image)
                with pefile.PE(str(image.path), fast_load=True) as pe:
                    expansion_city_growth.verify_bindings(selected, 0, pe.get_data)
        with self.assertRaises(ValueError):
            reader.source_dependencies(('foreign', '0' * 64), image)

    def test_checkpoint_preserves_choices_when_both_city_panels_are_added(self):
        root = resource_root()
        receipt = json.loads((root / 'evidence/host-xp2-bbg-religion-founding-save-t76-native.json').read_bytes())
        ref = receipt['checkpoint']
        raw = (root / ref['path']).read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), ref['sha256'])
        saved = json.loads(raw)
        observation, prior = saved['observation'], saved['decisions']
        sample = reader.parse(self.lua().execute(reader.build_source(0, 76)), 0, 76, self.observation())
        example, = sample['cities']
        loyalty = dict(sample, cities=[dict(example, city_id=row['id']) for row in observation['cities']])
        growth = dict(schema=city_growth.EXPANSION_SCHEMA, player_id=0, turn=76, cities=[
            dict(city_id=row['id'], population=row['population'], occupied=False, housing=5,
                 amenities=0, amenities_needed=0, happiness=3, starving=False,
                 display=dict.fromkeys(city_growth.EXPANSION_TEXT_FIELDS, '0') | {'GrowthLongNum': 0},
                 growth_icon=dict(color='StatNormalCSGlow', u=0, v=0))
            for row in observation['cities']])
        current = dict(deepcopy(prior), city_growth=growth, city_loyalty=loyalty)
        seal(current)
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        network_turn.validate_capability_catalogue(current, identity, current['sequence'], 76,
            player_id=0, observation=observation)
        self.assertEqual(information.project('city_loyalty', observation, current), loyalty)
        projected, proof = network_turn.checkpoint_catalogue(current, prior, observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, prior)
        self.assertEqual(proof['added_public_fields'], ['city_growth', 'city_loyalty'])
        self.assertEqual(proof['added_action_families'], [])

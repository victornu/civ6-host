"""Official park labels follow the current player's native reveal boundary."""

from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest

from civ6_host.contracts import information, network_turn
from civ6_host.runtime import expansion_city_growth, expansion_national_parks as reader
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from test_session_capabilities import seal


PRELUDE = br'''
observer,turn=0,76
Game={
    GetLocalPlayer=function() return 0 end,
    GetLocalObserver=function() return observer end,
    GetCurrentGameTurn=function() return turn end,
}
local revealed={[0]=true,[1]=true,[2]=false,[3]=true}
PlayersVisibility={[0]={IsRevealed=function(_,index) return revealed[index] end}}
Map={
    GetGridSize=function() return 4,1 end,
    GetPlotCount=function() return 4 end,
    GetPlotByIndex=function(index)
        assert(revealed[index], 'read outside native reveal gate')
        return {
            IsNationalPark=function() return index<3 end,
            GetNationalParkName=function()
                assert(index<3, 'name read outside a national park')
                return index==0 and 'Parc de l\195\137tang' or ''
            end,
        }
    end,
}
'''


class ExpansionNationalParksTests(unittest.TestCase):
    def observation(self):
        return dict(player_id=0, turn=76, width=4, height=1, plots=[
            dict(index=0, revealed=True, visible=True),
            dict(index=2, revealed=False, visible=False),
            dict(index=3, revealed=True, visible=True),
        ])

    def test_revealed_fog_keeps_park_and_unrevealed_handle_is_never_read(self):
        from lupa.lua51 import LuaError, LuaRuntime
        lua = LuaRuntime(encoding=None)
        lua.execute(PRELUDE)
        source = reader.build_source(0, 76)
        raw = lua.execute(source)
        observation = self.observation()
        shown = reader.parse(raw, observation)
        self.assertEqual(shown['plots'], [
            dict(plot_id=0, name='Parc de lÉtang', visible=True),
            dict(plot_id=1, name=None, visible=False),
        ])
        with self.assertRaisesRegex(ValueError, 'public map boundary'):
            reader.parse(raw + b'\n2|', observation)
        with self.assertRaisesRegex(ValueError, 'national park plot'):
            reader.parse(raw + b'\n1|', observation)
        with self.assertRaisesRegex(ValueError, 'Foreign national park frame'):
            reader.parse(raw, dict(observation, turn=77))
        lua.execute(b'observer=1')
        with self.assertRaisesRegex(LuaError, 'foreign or stale'):
            lua.execute(source)

    def test_exact_callbacks_and_ui_files_on_admitted_profiles(self):
        import pefile
        for capture, (image, _) in expansion_city_growth.CAPTURES.items():
            with self.subTest(capture=capture):
                pins = reader.source_dependencies(capture, image)
                self.assertIn(capture[1], pins.values())
                _, selected = reader._profile(capture, image)
                with pefile.PE(str(image.path), fast_load=True) as pe:
                    reader.verify_live(selected, 0, pe.get_data)
        with self.assertRaises(ValueError):
            reader.source_dependencies(('foreign', '0' * 64), image)

    def test_known_checkpoint_actions_survive_opt_in_revealed_park_view(self):
        root = resource_root()
        previous = json.loads((root / 'evidence/host-xp2-bbg-religion-founding-save-t76-native.json').read_bytes())
        ref = previous['checkpoint']
        raw = (root / ref['path']).read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), ref['sha256'])
        saved = json.loads(raw)
        observation, prior = saved['observation'], saved['decisions']
        visible_plot = observation['plots'][0]['index']
        frame = f'national-parks-v1|0|76|44|26\n{visible_plot}|50617263'.encode('ascii')
        park_view = reader.parse(frame, observation)
        current = dict(deepcopy(prior), national_parks=park_view)
        seal(current)
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        network_turn.validate_capability_catalogue(current, identity, current['sequence'], 76,
            player_id=0, observation=observation)
        self.assertEqual(information.project('national_parks', observation, current), park_view)
        projected, proof = network_turn.checkpoint_catalogue(current, prior, observation, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, prior)
        self.assertEqual(proof['added_public_fields'], ['national_parks'])
        self.assertEqual(proof['added_action_families'], [])

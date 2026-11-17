"""Great People parent/worker/view composition without starting a native process."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from lupa.lua51 import LuaRuntime

from civ6_host.contracts import network_turn
from civ6_host.runtime import xp1_great_people as adapter, xp1_session_view as view
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native.network_session import NativeNetworkSession
from civ6_host.runtime.workers import network_worker as worker
from civ6_host.runtime.xp1_saved_load import REFERENCE
from test_xp1_network_session import Fixture as ParentFixture
from test_xp1_great_people import Fixture as ReaderFixture
from test_xp1_city_religion import religion_fixture
from test_xp1_religion_beliefs_public import terminal_v11
from test_session_capabilities import seal


class GreatPeopleSessionTests(unittest.TestCase):
    def test_parent_selects_exact_profile_and_pins_reader_in_real_closure(self):
        with ParentFixture() as f:
            legacy=f.session()
            self.assertFalse(legacy.xp1_great_people)
            for invalid in (1,0,None,'true'):
                with self.subTest(flag=invalid), self.assertRaises(ValueError):
                    f.session(xp1_great_people=invalid)
            with self.assertRaisesRegex(ValueError,'exact installed'):
                f.session(xp1_great_people=True)
            current=f.session(xp1_great_people=True,execution_image_profile=_XP1_PROFILE.id)
            self.assertIs(type(current),NativeNetworkSession)
            self.assertFalse(current.xp1_religion_founding)
            self.assertFalse(current.xp1_religion_beliefs)
            self.assertEqual(f.spawns,[])
            current.reset()
            closure=json.loads((current.run/'closure.json').read_text(encoding='utf-8'))
            self.assertTrue(closure['xp1_great_people'])
            self.assertEqual(len(f.spawns),1)  # OS call replaced by existing fixture.
            for path,digest in adapter.source_dependencies(_XP1_PROFILE).items():
                self.assertEqual(closure['pins'][str(Path(path).resolve())],digest)

    def test_actual_worker_preflight_rejects_foreign_profile_or_missing_pin(self):
        tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
        owner=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_open_xp1')
        blocks=[n for n in owner.body if isinstance(n,ast.If) and isinstance(n.test,ast.Name)
                and n.test.id=='xp1_great_people']
        self.assertEqual(len(blocks),1)
        f=ast.parse('def check(xp1_great_people,xp1_dedications,selected,occupation_image,closure):\n pass').body[0]
        f.body=blocks
        namespace={'_Path':Path}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[f],type_ignores=[])),str(worker.__file__),'exec'),namespace)
        check=namespace['check']; pins=adapter.source_dependencies(_XP1_PROFILE)
        check(True,True,SimpleNamespace(reference=REFERENCE),_XP1_PROFILE,dict(pins=pins))
        for image,dedications,reference,retained in ((None,True,REFERENCE,pins),
                (_XP1_PROFILE,False,REFERENCE,pins),(_XP1_PROFILE,True,('other','0'*64),pins),
                (_XP1_PROFILE,True,REFERENCE,{})):
            with self.subTest(image=image,reference=reference,dedications=dedications),self.assertRaises(ValueError):
                check(True,dedications,SimpleNamespace(reference=reference),image,dict(pins=retained))
        check(False,False,None,None,{})
        guards=[n for n in ast.walk(tree) if isinstance(n,ast.Compare)
                and ast.unparse(n)=="type(closure.get('xp1_great_people', False)) is not bool"]
        self.assertEqual(len(guards),1)
        for flag in (True,False,0,1,None):
            self.assertEqual(eval(compile(ast.Expression(guards[0]),str(worker.__file__),'eval'),
                                  {'closure':{'xp1_great_people':flag}}),type(flag) is not bool)

    def test_view_reads_actual_saved_owner_and_keeps_every_previous_action(self):
        f=ReaderFixture();self.addCleanup(f.close)
        obs,_,_,decisions=religion_fixture()
        f.mutation=('\ncfg.turn='+str(obs['turn'])).encode('ascii')
        previous=deepcopy(decisions)
        view._add_xp1_great_people(f.saved,obs,decisions)
        self.assertEqual(f.evaluations,[b'@xp1_public_great_people'])
        self.assertEqual(decisions['candidates'],previous['candidates'])
        self.assertEqual(decisions['families'],previous['families'])
        self.assertIsNone(decisions['great_people']['timeline'][0]['claimant_player_id'])
        self.assertEqual(decisions['great_people']['own_points'][0]['points_total'],17.00390625)
        seal(decisions)
        network_turn.validate_capability_catalogue(decisions,
            SimpleNamespace(episode_id=decisions['episode_id'],game_generation=decisions['game_generation']),
            decisions['sequence'],obs['turn'],player_id=obs['player_id'],observation=obs)

    def test_waiting_and_closed_are_unqueried_not_empty_native_timeline(self):
        for closed in (False,True):
            obs,_,_,decisions=religion_fixture()
            if not closed:decisions['turn_controls'].update(active=False,active_complete=False)
            with patch.object(adapter,'read',side_effect=AssertionError('Unavailable native read')):
                view._add_xp1_great_people(None,obs,decisions,actions_closed=closed)
            self.assertIsNone(decisions['great_people'])
        obs,_,_,decisions=religion_fixture();decisions=terminal_v11(decisions);before=deepcopy(decisions)
        with patch.object(adapter,'read',side_effect=AssertionError('Terminal native read')):
            view._add_xp1_great_people(None,obs,decisions,actions_closed=True)
        self.assertEqual(decisions,before)


if __name__=='__main__':
    unittest.main()

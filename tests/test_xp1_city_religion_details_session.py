
"""Explicit XP1 city religion details use existing query/session ownership."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from civ6_host.contracts import city_religion, network_turn
from civ6_host.runtime import xp1_city_religion as reader, xp1_session_view as view
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.workers import network_worker
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture
from test_xp1_network_session import Fixture
from test_xp1_religion_beliefs_public import terminal_v11, unavailable, validate


FLAG = 'xp1_city_religion_details'


class CityReligionDetailsSessionTests(TestCase):
    def test_flag_parent_pins_and_worker_preflight(self):
        with Fixture() as fixture:
            self.assertFalse(fixture.session().xp1_city_religion_details)
            for flag in (0, 1, None, 'true'):
                with self.subTest(flag=flag),self.assertRaises(ValueError):
                    fixture.session(**{FLAG:flag})
            with self.assertRaisesRegex(ValueError,'exact installed'):
                fixture.session(**{FLAG:True})
            session=fixture.session(execution_image_profile=_XP1_PROFILE.id,**{FLAG:True})
            session.reset()
            self.assertEqual(len(fixture.spawns),1)
            path=session.run/'closure.json'
            self.assertLess(path.stat().st_size,8*1024*1024)
            closure=json.loads(path.read_text(encoding='utf-8'))
            self.assertIs(closure[FLAG],True)
            exact=reader.source_dependencies(_XP1_PROFILE,include_details=True)
            for path,digest in exact.items():
                self.assertEqual(closure['pins'][str(Path(path).resolve())],digest)
        # Execute the worker's actual preflight statements with native
        # preparation excluded, including both flag and pinned input checks.
        path=Path(network_worker.__file__)
        worker=ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
        opens=next(n for n in worker.body if isinstance(n,ast.FunctionDef) and n.name=='_open_xp1')
        checks=[n for n in opens.body if isinstance(n,ast.If) and FLAG in ast.unparse(n.test)]
        self.assertEqual(len(checks),2)
        wrapper=ast.parse(f'def check({FLAG},selected,occupation_image,closure):\\n pass'.replace('\\n','\n'))
        wrapper.body[0].body=checks
        local={}
        exec(compile(ast.fix_missing_locations(wrapper),str(path),'exec'),local)
        preflight=local['check']
        selected=SimpleNamespace(family='xp1-lan',reference=reader.REFERENCE)
        preflight(True,selected,_XP1_PROFILE,dict(pins=exact))
        preflight(False,None,None,{})
        for flag,candidate,image,pins in (
            (1,selected,_XP1_PROFILE,exact),
            (True,selected,None,exact),
            (True,selected,_XP1_PROFILE,{}),
            (True,SimpleNamespace(family='xp1-lan',reference=('wrong','0'*64)),_XP1_PROFILE,exact),
        ):
            with self.assertRaises(ValueError):
                preflight(flag,candidate,image,dict(pins=pins))

    def test_final_wrapper_preserves_majority_when_actor_waits_and_skips_terminal(self):
        obs,_,_,decisions=religion_fixture()
        owner=object()
        for waiting in (False, True):
            catalogue=deepcopy(decisions)
            if waiting:unavailable(catalogue)
            old=deepcopy(catalogue['city_religion'])
            new=deepcopy(old)
            new['schema']=city_religion.DETAILS_SCHEMA
            for city in new['cities']:city['religions']=[]
            with patch.object(reader,'read_details',return_value=new) as native:
                view._add_xp1_city_religion_details(owner,obs,catalogue)
            native.assert_called_once_with(owner,obs,expected_majority=old)
            seal(catalogue)
            validate(obs,catalogue)
            self.assertEqual(catalogue['city_religion'],new)
            self.assertEqual(city_religion.project_majority(new,obs['player_id'],obs['turn']),old)
        closed=terminal_v11(decisions)
        baseline=deepcopy(closed)
        with patch.object(reader,'read_details') as native:
            view._add_xp1_city_religion_details(owner,obs,closed)
            native.assert_not_called()
        self.assertEqual(closed,baseline)

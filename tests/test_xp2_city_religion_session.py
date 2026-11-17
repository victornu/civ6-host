"""Opt-in XP2 city religion routes; native reader acceptance is separate."""
import ast
from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.contracts import network_turn as network
from civ6_host.runtime import xp1_city_religion as reader, xp1_session_view as view
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE, _XP1_PROFILE
from civ6_host.runtime.native.network_session import NativeNetworkSession
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.source_build_identity import CURRENT_UNSIGNED_LOG_HOST_REFERENCE
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.workers import network_worker as worker
from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
from civ6_host.runtime import xp2_bbg_inputs
from test_xp1_network_session import Fixture as ParentFixture, reset_reply
from test_xp2_religious_chain_session import worker_preflight
from test_xp2_religious_chain_public import preceding, added as add_chain, validate
from test_xp2_pantheon_public import added as add_pantheon
from test_xp2_religious_unit_operations_public import permissions_preceding
from test_xp1_city_religion_details_public import details
from test_xp1_religion_beliefs_public import terminal_v11
from test_session_capabilities import seal


FLAG='xp2_city_religion_details'


class XP2CityReligionSessionTests(unittest.TestCase):
    def test_parent_exact_independent_flag_and_source_pins_in_actual_closure(self):
        with ParentFixture() as f:
            f.captured.reference=REFERENCE
            f.executable=resource_root()/CURRENT_UNSIGNED_LOG_HOST_REFERENCE[0]
            base=dict(input_profile='xp2-lan',official_bundle=dict(zip(('path','sha256'),REFERENCE)))
            self.assertIs(getattr(f.session(**base),FLAG),False)
            for value in (0,1,None,'true'):
                with self.assertRaises(ValueError):f.session(**base,**{FLAG:value})
            with self.assertRaises(ValueError):f.session(**{FLAG:True})
            with self.assertRaisesRegex(ValueError,'exact admitted'):f.session(**base,**{FLAG:True})
            options=dict(base,execution_image_profile=_PROFILE.id,**{FLAG:True})
            with patch.object(reader,'source_dependencies',side_effect=ValueError('details source refused')):
                with self.assertRaisesRegex(ValueError,'details source refused'):f.session(**options)
            current=f.session(**options)
            for other in ('xp1_city_religion_details','xp2_pantheon','xp2_prophet_activation',
                          'xp2_religion_founding','xp2_religion_beliefs','xp2_religious_unit_operations'):
                self.assertIs(getattr(current,other),False)
            from civ6_host.runtime.xp1_session_result import result_provenance
            def reply(session):
                result=reset_reply(session)
                result['outcome']['native_victory'].update(result_provenance(XP2_CORE_SHA256))
                return result
            with patch.object(NativeNetworkSession,'_receive',reply):current.reset()
            path=current.run/'closure.json'
            self.assertLess(path.stat().st_size,8*1024*1024)
            closure=json.loads(path.read_text(encoding='utf-8'))
            self.assertIs(closure[FLAG],True)
            for dependency_path,digest in reader.source_dependencies(_PROFILE,include_details=True,reference=REFERENCE).items():
                self.assertEqual(closure['pins'][str(Path(dependency_path).resolve())],digest)
            self.assertEqual(len(f.spawns),1)  # Existing OS-launch double, no engine.

    def test_worker_profile_capture_dependency_guard_preserves_closure_path(self):
        check=worker_preflight(FLAG)
        for reference in (REFERENCE,xp2_bbg_inputs.REFERENCE):
            pins=reader.source_dependencies(_PROFILE,include_details=True,reference=reference)
            check(True,NS(reference=reference,family='xp2-lan'),_PROFILE,dict(pins=pins))
            for image,family,ref,retained in ((None,'xp2-lan',reference,pins),
                    (_XP1_PROFILE,'xp2-lan',reference,pins),(replace(_PROFILE),'xp2-lan',reference,pins),
                    (_PROFILE,'xp1-lan',reference,pins),(_PROFILE,'xp2-lan',('foreign','0'*64),pins),
                    (_PROFILE,'xp2-lan',reference,{})):
                with self.assertRaises(ValueError):check(True,NS(reference=ref,family=family),image,dict(pins=retained))
        for value in (0,1,None,'true'):
            with self.assertRaises(ValueError):check(value,None,None,{})
        check(False,None,None,{})
        tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
        opener=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_open_xp1')
        self.assertFalse([n for n in ast.walk(opener) if isinstance(n,ast.Name)
                          and isinstance(n.ctx,ast.Store) and n.id=='path'])
        self.assertEqual(len([n for n in ast.walk(opener) if isinstance(n,ast.Assign)
            and ast.unparse(n)=='saved.'+FLAG+' = '+FLAG]),1)
        boolean_checks=[n for n in ast.walk(tree) if isinstance(n,ast.Compare)
            and ast.unparse(n)=="type(closure.get('"+FLAG+"', False)) is not bool"]
        self.assertEqual(len(boolean_checks),1)

    def test_view_reads_own_cities_waiting_and_without_action_permission_but_not_after_close(self):
        saved=SavedLoadOwner.__new__(SavedLoadOwner)
        states=[]
        for index in range(3):
            prior,obs=preceding(index,unit_operations=True)
            states.append((add_pantheon(add_chain(prior,obs),obs),obs))
        for waiting,strategic,tactical in product((False,True),repeat=3):
            states.append(permissions_preceding(state='waiting' if waiting else 'active',
                strategic=strategic,tactical=tactical))
        for prior,obs in states:
            value=deepcopy(prior);expected=details(obs)
            with patch.object(reader,'read_details',autospec=True,return_value=expected) as native:
                view._add_xp2_city_religion_details(saved,obs,value)
            native.assert_called_once_with(saved,obs)
            seal(value);validate(value,obs)
            self.assertEqual(value['city_religion'],expected)
            self.assertEqual(value['candidates'],prior['candidates'])
            self.assertEqual(value['families'],prior['families'])
            expected['cities'].clear()
            self.assertEqual(len(value['city_religion']['cities']),len(obs['cities']))
        prior,obs=preceding();terminal=terminal_v11(prior)
        for value in (terminal,prior):
            before=deepcopy(value)
            with patch.object(reader,'read_details',side_effect=AssertionError('closed query')):
                view._add_xp2_city_religion_details(saved,obs,value,actions_closed=True)
            self.assertEqual(value,before)
        with patch.object(reader,'read_details',side_effect=AssertionError('bad predecessor query')):
            with self.assertRaisesRegex(ValueError,'preceding'):
                view._add_xp2_city_religion_details(saved,obs,terminal)


if __name__=='__main__':unittest.main()

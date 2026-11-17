"""Session composition on real saved owners; no DLL or process is launched."""
import ast
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from lupa.lua51 import LuaRuntime  # Load the fixture before worker import isolation.

from civ6_host.contracts import network_turn, religion_beliefs as public
from civ6_host.runtime import xp1_religion_beliefs as adapter, xp1_religion_beliefs_source as source
from civ6_host.runtime import xp1_session_view as view, xp1_load_capability
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native.network_session import NativeNetworkSession
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_continuation import SavedContinuation
from civ6_host.runtime.xp1_saved_load import REFERENCE
from civ6_host.runtime.workers import network_worker as worker
from test_xp1_network_session import Fixture as ParentFixture
from test_xp1_religion_beliefs import Fixture as NativeBoundaryFixture
from test_xp1_religion_beliefs_public import state, terminal_v11
from test_xp1_city_religion import religion_fixture
from test_xp1_pantheon_public import offered as pantheon_offered


def worker_preflight():
    """Compile the actual pre-Load source block; never call the loader."""
    tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_open_xp1')
    blocks=[n for n in function.body if isinstance(n,ast.If)
            and isinstance(n.test,ast.Name) and n.test.id=='xp1_religion_beliefs']
    if len(blocks)!=1:raise AssertionError('Expected one belief preflight')
    wrapper=ast.parse('def check(xp1_religion_beliefs,xp1_dedications,selected,occupation_image,closure):\n pass').body[0]
    wrapper.body=blocks
    module=ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[]))
    namespace={'_Path':Path}
    exec(compile(module,str(worker.__file__),'exec'),namespace)
    return namespace['check']


def native_state(obs, mode):
    projected=state(obs,mode)
    own=dict(projected['own'],player_id=obs['player_id'],current_game_turn=obs['turn'],
        observation_only=True,action_effect_verified=False,source_proof_sha256=source.snapshot.SOURCE[1],
        exposed_to_learner=False,eligible_for_training=False)
    return dict(own=own,beliefs=projected['beliefs'])


class ReligionBeliefsSessionTests(unittest.TestCase):
    def fixture(self):
        f=NativeBoundaryFixture();self.addCleanup(f.close)
        f.saved.xp1_religion_beliefs=True
        f.token.world_input_prompts={};f.token.trade_feedback=None
        from civ6_host.runtime.unit_operation_ui_profile import verify_live
        f.token.unit_source=verify_live(f.backend.core._handle,f.backend.runtime.read,core_sha256=XP1_CORE_SHA256)
        return f

    def test_constructor_option_profile_and_actual_closure_preserve_independence(self):
        with ParentFixture() as f:
            historical=f.session()
            self.assertIs(type(historical),NativeNetworkSession)
            self.assertFalse(historical.xp1_religion_beliefs)
            self.assertIsNone(historical.execution_image)
            for flag in (1,0,None,'true'):
                with self.subTest(flag=flag),self.assertRaises(ValueError):f.session(xp1_religion_beliefs=flag)
            with self.assertRaisesRegex(ValueError,'exact installed'):f.session(xp1_religion_beliefs=True)
            with patch.object(source,'actions_qualified',return_value=False),self.assertRaisesRegex(ValueError,'not qualified'):
                f.session(xp1_religion_beliefs=True,execution_image_profile=_XP1_PROFILE.id)
            current=f.session(xp1_religion_beliefs=True,execution_image_profile=_XP1_PROFILE.id)
            self.assertIs(current.execution_image,_XP1_PROFILE)
            self.assertTrue(current.xp1_religion_beliefs)
            self.assertFalse(current.xp1_pantheon)
            self.assertEqual(f.spawns,[])
            # Existing ParentFixture replaces OS launch, native loading and pipe
            # replies. The real reset still creates and pins the actual closure.
            current.reset()
            closure_path=current.run/'closure.json'
            self.assertLess(closure_path.stat().st_size,8*1024*1024)
            closure=json.loads(closure_path.read_text(encoding='utf-8'))
            self.assertTrue(closure['xp1_religion_beliefs'])
            self.assertFalse(closure.get('xp1_pantheon',False))
            self.assertEqual(len(f.spawns),1)  # mocked call, no process
            for path,digest in source.source_dependencies(_XP1_PROFILE).items():
                self.assertEqual(closure['pins'][str(Path(path).resolve())],digest)

    def test_worker_exact_profile_and_source_closure_preflight(self):
        check=worker_preflight();selected=SimpleNamespace(reference=REFERENCE)
        pins=source.source_dependencies(_XP1_PROFILE)
        check(True,True,selected,_XP1_PROFILE,dict(pins=pins))
        for image,dedications,reference,retained in ((None,True,REFERENCE,pins),
                (_XP1_PROFILE,False,REFERENCE,pins),(_XP1_PROFILE,True,('foreign','0'*64),pins),
                (_XP1_PROFILE,True,REFERENCE,{})):
            with self.subTest(image=image is None,dedications=dedications,pins=bool(retained)),self.assertRaises(ValueError):
                check(True,dedications,SimpleNamespace(reference=reference),image,dict(pins=retained))
        with patch.object(source,'actions_qualified',return_value=False),self.assertRaisesRegex(ValueError,'not qualified'):
            check(True,True,selected,_XP1_PROFILE,dict(pins=pins))
        check(False,False,None,None,{})
        # Exact worker wire-type expression is part of the real closure guard.
        tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
        expressions=[n for n in ast.walk(tree) if isinstance(n,ast.Compare)
            and ast.unparse(n)=="type(closure.get('xp1_religion_beliefs', False)) is not bool"]
        self.assertEqual(len(expressions),1)
        expr=compile(ast.Expression(expressions[0]),str(worker.__file__),'eval')
        for flag in (True,False,0,1,None,'true'):
            self.assertEqual(eval(expr,{'closure':{'xp1_religion_beliefs':flag}}),type(flag) is not bool)

    def test_view_projects_only_metadata_preserves_pantheon_absence_and_waiting(self):
        for mode in ('offered','absent','spent','waiting','closed'):
            for pantheon_enabled in (False,True):
                with self.subTest(mode=mode,pantheon=pantheon_enabled):
                    obs,_,_,decisions=religion_fixture()
                    saved=SavedLoadOwner.__new__(SavedLoadOwner)
                    saved.explicit_religion_beliefs={'stale':True}
                    unavailable=mode in ('waiting','closed')
                    if mode=='waiting':decisions['turn_controls'].update(active=False,active_complete=False)
                    if pantheon_enabled:
                        network_turn.add_xp1_pantheon(decisions,None if unavailable else pantheon_offered(obs),actions_closed=mode=='closed')
                    previous_candidates=deepcopy(decisions['candidates'])
                    previous_pantheon=deepcopy(decisions.get('pantheon'))
                    native=native_state(obs,'offered' if unavailable else mode)
                    before=deepcopy(native)
                    def read(actual,observation):
                        self.assertIs(actual,saved);self.assertIs(observation,obs)
                        saved.explicit_religion_beliefs=deepcopy(native)
                        return native
                    with patch.object(adapter,'catalogue',side_effect=read) as queried:
                        view._add_xp1_religion_beliefs(saved,obs,decisions,actions_closed=mode=='closed')
                    self.assertIn(decisions['schema'],network_turn.XP1_RELIGION_BELIEFS_SCHEMAS)
                    self.assertEqual(decisions.get('pantheon'),previous_pantheon)
                    self.assertEqual(decisions['candidates'][:len(previous_candidates)],previous_candidates)
                    if unavailable:
                        queried.assert_not_called();self.assertIsNone(saved.explicit_religion_beliefs)
                        self.assertIsNone(decisions['religion_beliefs'])
                        self.assertEqual(decisions['families']['add_belief']['status'],'unqualified')
                    else:
                        queried.assert_called_once()
                        public.validate(decisions['religion_beliefs'],obs['player_id'],obs['turn'],observation=obs)
                        self.assertFalse(set(decisions['religion_beliefs']['own'])&public._NATIVE_META)
                        self.assertEqual(saved.explicit_religion_beliefs,native)
                        self.assertEqual(native,before)
                        self.assertEqual(public.actions(decisions['religion_beliefs']),adapter.actions(native))

    def test_reduced_terminal_v11_is_preserved_without_query(self):
        obs,_,_,prior=religion_fixture();decisions=terminal_v11(prior);before=deepcopy(decisions)
        saved=SavedLoadOwner.__new__(SavedLoadOwner);saved.explicit_religion_beliefs={'stale':True}
        with patch.object(adapter,'catalogue',side_effect=AssertionError('Closed native query')):
            view._add_xp1_religion_beliefs(saved,obs,decisions,actions_closed=True)
        self.assertEqual(decisions,before)
        self.assertEqual(decisions['schema'],network_turn.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertIsNone(saved.explicit_religion_beliefs)
        self.assertNotIn('religion_beliefs',decisions)
        with patch.object(adapter,'catalogue',return_value=native_state(obs,'offered')):
            with self.assertRaisesRegex(ValueError,'preceding'):
                view._add_xp1_religion_beliefs(saved,obs,decisions)

    def test_real_saved_continuation_applies_and_commits_effect_or_refusal(self):
        for allowed in (True,False):
            with self.subTest(can_start=allowed):
                f=self.fixture()
                self.assertIs(type(f.saved),SavedLoadOwner)
                self.assertIs(type(f.backend.prefix),SavedLoadServices)
                self.assertIs(type(f.token),SavedContinuation)
                before=adapter.catalogue(f.saved,f.token.observation)
                f.can_start=allowed;f.saved._running=False
                # This inherited fixture's documentary source-scope boundary
                # remains separate; native owners/transition/FIFO execute.
                with patch.object(xp1_load_capability,'capability_source_scope',return_value=nullcontext()):
                    result=f.saved.execute(f.choice)
                self.assertEqual(result['action'],f.choice)
                self.assertEqual(result['effect']['status'],'completed' if allowed else 'refused')
                self.assertEqual(result['effect']['observation'],result['observation_after'])
                self.assertEqual(f.token.sequence,1)
                self.assertFalse(f.backend.busy);self.assertFalse(f.saved.poisoned)
                self.assertEqual(f.token.transport.pending,[])
                with f.saved._attempt():
                    after=adapter.catalogue(f.saved,f.token.observation)
                self.assertEqual(after['own']['own_religion']['belief_indices'],[2] if allowed else [])
                for native in (before,after):
                    projected=public.project_snapshot(native['own'],0,8)
                    self.assertTrue(projected['has_religious_founding_unit'])
                    self.assertFalse(set(projected)&public._NATIVE_META)
                    self.assertIn('source_proof_sha256',native['own'])
                f.close()

    def test_continuation_rejects_disabled_wrong_engine_and_bad_choice(self):
        for mode in ('disabled','xp2','bool_index','wrong_class'):
            f=self.fixture();action=deepcopy(f.choice)
            if mode=='disabled':f.saved.xp1_religion_beliefs=False
            elif mode=='xp2':f.backend.load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)
            elif mode=='bool_index':action['index']=True
            else:action['class']='bad class'
            with self.subTest(mode=mode),self.assertRaises(ValueError):f.token.execute(action,session=f.saved)
            self.assertEqual(f.machine,[]);f.close()

    def command_result(self,effect,*,available=True):
        f=self.fixture();action=f.choice
        result=dict(action=deepcopy(action),effect=deepcopy(effect))
        decisions={'candidates':[dict(action=action)] if available else []}
        from civ6_host.runtime import xp1_session_inputs
        with (patch.object(view,'read',return_value=({},f.token.observation,decisions)),
              patch.object(f.saved,'execute',return_value=result) as execute,
              patch.object(xp1_session_inputs,'_write_once',return_value={'fixture':True})):
            value=worker._execute_xp1(f.saved,action,0,0,Path(__file__).parent/'fixture-closure.json')
        count=execute.call_count;f.close();return value,count

    def test_worker_completed_refused_and_invalid_identity_receipts(self):
        completed=dict(status='completed',selected_index=2,selected_hash=0xffffffff,
            selected_class='BELIEF_CLASS_FOLLOWER',source_sha256=source.SOURCE[1])
        refused=dict(status='refused',refusal_code='native_belief_can_start_false',
            request=dict(can_start=False,request_invoked=False),source_sha256=source.SOURCE[1])
        for effect in (completed,refused):
            result,count=self.command_result(effect)
            self.assertEqual(result['status'],effect['status']);self.assertEqual(count,1)
        result,count=self.command_result(completed,available=False)
        self.assertEqual(result['reason'],'native_action_no_longer_available');self.assertEqual(count,0)
        bad=[None,[],dict(completed,source_sha256='0'*64),dict(completed,selected_index=True),
             dict(completed,selected_hash=True),dict(completed,selected_class=True),
             dict(completed,selected_index=3),dict(completed,selected_hash=1),
             dict(completed,selected_class='BELIEF_CLASS_WORSHIP'),dict(completed,status='pending'),
             dict(refused,request=dict(can_start=0,request_invoked=False)),
             dict(refused,request=dict(can_start=False,request_invoked=True)),dict(refused,refusal_code='invented')]
        for effect in bad:
            with self.subTest(effect=effect),self.assertRaises(RuntimeError):self.command_result(effect)


if __name__=='__main__':unittest.main()

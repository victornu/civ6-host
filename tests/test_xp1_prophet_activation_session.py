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

from civ6_host.contracts import network_turn, prophet_activation as public
from civ6_host.runtime import xp1_prophet_activation as adapter, xp1_prophet_activation_source as source
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
from test_xp1_prophet_activation import Fixture as NativeBoundaryFixture
from test_xp1_prophet_activation_public import state, native_own, preceding
from test_xp1_religion_beliefs_public import terminal_v11, validate, unavailable
from civ6_host.contracts.religion_beliefs import _NATIVE_META
from test_xp1_city_religion import religion_fixture


def worker_preflight():
    """Compile the actual pre-Load source block; never call the loader."""
    tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_open_xp1')
    blocks=[n for n in function.body if isinstance(n,ast.If)
            and isinstance(n.test,ast.Name) and n.test.id=='xp1_prophet_activation']
    if len(blocks)!=1:raise AssertionError('Expected one prophet activation preflight')
    wrapper=ast.parse('def check(xp1_prophet_activation,xp1_dedications,selected,occupation_image,closure):\n pass').body[0]
    wrapper.body=blocks
    module=ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[]))
    namespace={'_Path':Path}
    exec(compile(module,str(worker.__file__),'exec'),namespace)
    return namespace['check']


def native_state(obs, mode):
    return dict(own=native_own(obs,mode), activation=state(obs,mode)['activation'])


class ProphetActivationSessionTests(unittest.TestCase):
    def fixture(self):
        f=NativeBoundaryFixture();self.addCleanup(f.close)
        f.saved.xp1_prophet_activation=True
        f.token.world_input_prompts={};f.token.trade_feedback=None
        from civ6_host.runtime.unit_operation_ui_profile import verify_live
        f.token.unit_source=verify_live(f.backend.core._handle,f.backend.runtime.read,core_sha256=XP1_CORE_SHA256)
        return f

    def test_constructor_option_profile_and_actual_closure_preserve_independence(self):
        with ParentFixture() as f:
            historical=f.session()
            self.assertIs(type(historical),NativeNetworkSession)
            self.assertFalse(historical.xp1_prophet_activation)
            self.assertIsNone(historical.execution_image)
            for flag in (1,0,None,'true'):
                with self.subTest(flag=flag),self.assertRaises(ValueError):f.session(xp1_prophet_activation=flag)
            with self.assertRaisesRegex(ValueError,'exact installed'):f.session(xp1_prophet_activation=True)
            with patch.object(source,'actions_qualified',return_value=False),self.assertRaisesRegex(ValueError,'not qualified'):
                f.session(xp1_prophet_activation=True,execution_image_profile=_XP1_PROFILE.id)
            current=f.session(xp1_prophet_activation=True,execution_image_profile=_XP1_PROFILE.id)
            self.assertIs(current.execution_image,_XP1_PROFILE)
            self.assertTrue(current.xp1_prophet_activation)
            self.assertFalse(current.xp1_pantheon)
            self.assertFalse(current.xp1_religion_beliefs)
            self.assertEqual(f.spawns,[])
            # Existing ParentFixture replaces OS launch, native loading and pipe
            # replies. The real reset still creates and pins the actual closure.
            current.reset()
            closure_path=current.run/'closure.json'
            self.assertLess(closure_path.stat().st_size,8*1024*1024)
            closure=json.loads(closure_path.read_text(encoding='utf-8'))
            self.assertTrue(closure['xp1_prophet_activation'])
            self.assertFalse(closure.get('xp1_pantheon',False))
            self.assertFalse(closure.get('xp1_religion_beliefs',False))
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
            and ast.unparse(n)=="type(closure.get('xp1_prophet_activation', False)) is not bool"]
        self.assertEqual(len(expressions),1)
        expr=compile(ast.Expression(expressions[0]),str(worker.__file__),'eval')
        for flag in (True,False,0,1,None,'true'):
            self.assertEqual(eval(expr,{'closure':{'xp1_prophet_activation':flag}}),type(flag) is not bool)

    def test_view_projects_state_preserves_other_families_and_checkpoints(self):
        for mode in ('offered','empty','no_unit','consumed','founded','waiting','closed'):
            for options in ((False,False,False,False),(True,True,True,True)):
                with self.subTest(mode=mode,options=options):
                    obs,_,_,city=religion_fixture()
                    decisions=deepcopy(city)
                    saved=SavedLoadOwner.__new__(SavedLoadOwner)
                    saved.explicit_prophet_activation={'stale':True}
                    inactive=mode in ('waiting','closed')
                    native_mode='offered' if inactive else mode
                    if inactive:unavailable(decisions)
                    preceding(decisions,obs,options,waiting=inactive,mode=native_mode)
                    prior=deepcopy(decisions)
                    native=native_state(obs,native_mode);before=deepcopy(native)
                    def read(actual,observation):
                        self.assertIs(actual,saved);self.assertIs(observation,obs)
                        saved.explicit_prophet_activation=deepcopy(native)
                        return native
                    with patch.object(adapter,'catalogue',side_effect=read) as queried:
                        view._add_xp1_prophet_activation(saved,obs,decisions,actions_closed=mode=='closed')
                    validate(obs,decisions,closed=mode=='closed')
                    self.assertIn(decisions['schema'],network_turn.XP1_PROPHET_ACTIVATION_SCHEMAS)
                    self.assertEqual({k:v for k,v in decisions['families'].items() if k!='activate_prophet'},prior['families'])
                    self.assertEqual(decisions['candidates'][:len(prior['candidates'])],prior['candidates'])
                    for group in ('pantheon','religion_beliefs','religion_founding','great_people'):
                        self.assertEqual(decisions.get(group),prior.get(group))
                    if inactive:
                        queried.assert_not_called();self.assertIsNone(saved.explicit_prophet_activation)
                        self.assertIsNone(decisions['prophet_activation'])
                        self.assertEqual(decisions['families']['activate_prophet']['status'],'unqualified')
                    else:
                        queried.assert_called_once()
                        public.validate(decisions['prophet_activation'],obs['player_id'],obs['turn'],observation=obs)
                        self.assertFalse(set(decisions['prophet_activation']['own'])&_NATIVE_META)
                        self.assertEqual(saved.explicit_prophet_activation,native)
                        self.assertEqual(native,before)
                        self.assertEqual(public.actions(decisions['prophet_activation']),adapter.actions(native))
                        self.assertEqual(decisions['families']['activate_prophet']['status'],'queried_complete')
                        projected,receipt=network_turn.checkpoint_catalogue(decisions,prior,obs,core_sha256=XP1_CORE_SHA256)
                        self.assertEqual(projected,prior)
                        self.assertEqual(receipt['added_public_fields'],['prophet_activation'])
                        self.assertEqual(receipt['added_action_families'],['activate_prophet'])

    def test_reduced_terminal_v11_is_preserved_without_query(self):
        obs,_,_,prior=religion_fixture();decisions=terminal_v11(prior);before=deepcopy(decisions)
        saved=SavedLoadOwner.__new__(SavedLoadOwner);saved.explicit_prophet_activation={'stale':True}
        with patch.object(adapter,'catalogue',side_effect=AssertionError('Closed native query')):
            view._add_xp1_prophet_activation(saved,obs,decisions,actions_closed=True)
        self.assertEqual(decisions,before)
        self.assertEqual(decisions['schema'],network_turn.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertIsNone(saved.explicit_prophet_activation)
        self.assertNotIn('prophet_activation',decisions)
        with patch.object(adapter,'catalogue',return_value=native_state(obs,'offered')):
            with self.assertRaisesRegex(ValueError,'preceding'):
                view._add_xp1_prophet_activation(saved,obs,decisions)

    def test_real_saved_continuation_commits_selected_unit_or_official_refusal(self):
        for allowed in (True,False):
            with self.subTest(can_start=allowed):
                f=self.fixture()
                self.assertIs(type(f.saved),SavedLoadOwner)
                self.assertIs(type(f.backend.prefix),SavedLoadServices)
                self.assertIs(type(f.token),SavedContinuation)
                before=adapter.catalogue(f.saved,f.token.observation)
                f.can_start=allowed;f.saved._running=False
                # Source-document admission and machine execution are fixture
                # seams; actual owner, transition, transport and FIFO remain.
                with (patch.object(xp1_load_capability,'capability_source_scope',return_value=nullcontext()),
                      patch.object(f.saved,'emit',wraps=f.saved.emit) as emitted):
                    result=f.saved.execute(f.choice)
                self.assertEqual(result['action'],f.choice)
                self.assertEqual(result['effect']['status'],'completed' if allowed else 'refused')
                self.assertEqual(result['effect']['observation'],result['observation_after'])
                effects=[c for c in emitted.call_args_list if c.args[0]=='official_explicit_religion_effect']
                self.assertEqual(len(effects),int(allowed))
                if allowed:
                    self.assertEqual(effects[0].kwargs['action'],f.choice)
                    self.assertFalse(effects[0].kwargs['automatic_choices_applied'])
                    self.assertTrue(effects[0].kwargs['receipt']['unit_consumed'])
                    self.assertEqual(result['effect']['founding_site'],dict(player=0,type=2,id=65536))
                    self.assertEqual([u['id'] for u in result['observation_after']['units']],[17])
                else:
                    self.assertFalse(any(row[0]=='request' for row in f.machine))
                    self.assertEqual(result['effect']['request']['can_start'],False)
                    self.assertEqual(f.token.publication_count,0)
                self.assertEqual(f.token.sequence,1)
                self.assertFalse(f.backend.busy);self.assertFalse(f.saved.poisoned)
                self.assertEqual(f.token.transport.pending,[])
                self.assertEqual(f.backend.prefix.deferred_events.pending,[])
                self.assertEqual(f.maps,{})
                with f.saved._attempt():
                    after=adapter.catalogue(f.saved,f.token.observation)
                self.assertEqual(after['own']['religion_type_created'],-1)
                self.assertIsNone(after['own']['own_religion'])
                self.assertEqual(after['own']['holy_city_present'],allowed)
                self.assertEqual(after['own']['num_beliefs_earned'],3 if allowed else 0)
                for native in (before,after):
                    projected=public.project_snapshot(native['own'],0,8)
                    self.assertTrue(projected['has_religious_founding_unit'])
                    self.assertFalse(set(projected)&_NATIVE_META)
                    self.assertIn('source_proof_sha256',native['own'])
                f.close()

    def test_continuation_rejects_disabled_wrong_engine_and_bad_choice(self):
        for mode in ('disabled','xp2','bool_unit','bool_x','extra_individual'):
            f=self.fixture();action=deepcopy(f.choice)
            if mode=='disabled':f.saved.xp1_prophet_activation=False
            elif mode=='xp2':f.backend.load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)
            elif mode=='bool_unit':action['unit_id']=True
            elif mode=='bool_x':action['x']=True
            else:action['individual_index']=117
            with self.subTest(mode=mode),self.assertRaises(ValueError):f.token.execute(action,session=f.saved)
            self.assertEqual(f.machine,[]);f.close()

    def command_result(self,f,effect,*,available=True):
        action=f.choice
        result=dict(action=deepcopy(action),effect=deepcopy(effect))
        decisions={'candidates':[dict(action=action)] if available else []}
        from civ6_host.runtime import xp1_session_inputs
        with (patch.object(view,'read',return_value=({},f.token.observation,decisions)),
              patch.object(f.saved,'execute',return_value=result) as execute,
              patch.object(xp1_session_inputs,'_write_once',return_value={'fixture':True})):
            value=worker._execute_xp1(f.saved,action,0,0,Path(__file__).parent/'fixture-closure.json')
        return value,execute.call_count

    def test_worker_completed_refused_and_corrupt_identity_or_site_receipts(self):
        f=self.fixture()
        completed=dict(status='completed',unit_id=18,x=1,y=0,
            founding_site=dict(player=0,type=2,id=65536),source_sha256=source.SOURCE[1])
        refused=dict(status='refused',refusal_code='native_prophet_can_start_false',
            request=dict(can_start=False,request_invoked=False,request_submitted=False),
            source_sha256=source.SOURCE[1])
        for effect in (completed,refused):
            result,count=self.command_result(f,effect)
            self.assertEqual(result['status'],effect['status']);self.assertEqual(count,1)
            self.assertEqual(result['requested_action'],f.choice)
        result,count=self.command_result(f,completed,available=False)
        self.assertEqual(result['reason'],'native_action_no_longer_available');self.assertEqual(count,0)
        bad=[None,[],dict(completed,source_sha256='0'*64),dict(completed,status='pending'),
             dict(refused,request=dict(can_start=0,request_invoked=False,request_submitted=False)),
             dict(refused,request=dict(can_start=False,request_invoked=True,request_submitted=False)),
             dict(refused,request=dict(can_start=False,request_invoked=False,request_submitted=True)),
             dict(refused,request=dict(can_start=False,request_invoked=False)),
             dict(refused,refusal_code='invented')]
        for key in ('unit_id','x','y'):
            bad.extend((dict(completed,**{key:True}),dict(completed,**{key:completed[key]+1})))
        for site in (None,[],dict(player=True,type=2,id=65536),dict(player=1,type=2,id=65536),
                dict(player=0,type=True,id=65536),dict(player=0,type=1,id=65536),
                dict(player=0,type=2,id=True),dict(player=0,type=2,id=-1),
                dict(player=0,type=2,id=2**31),dict(player=0,type=2,id=65536,extra=1)):
            bad.append(dict(completed,founding_site=site))
        for effect in bad:
            with self.subTest(effect=effect),self.assertRaises(RuntimeError):self.command_result(f,effect)


if __name__=='__main__':unittest.main()

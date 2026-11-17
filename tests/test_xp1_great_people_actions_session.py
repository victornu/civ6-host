"""Rise and Fall Great Person session routes and opt-in rejection; no engine."""

import ast
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lupa.lua51 import LuaRuntime  # Import before worker module isolation.
from civ6_host.contracts import great_people_actions as public, network_turn
from civ6_host.runtime import xp1_great_people_commands as commands, xp1_load_capability
from civ6_host.runtime import xp1_session_inputs, xp1_session_view as view
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native import native_player_observation
from civ6_host.runtime.native.network_session import NativeNetworkSession
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.workers import network_worker as worker
from civ6_host.runtime.xp1_continuation import SavedContinuation
from civ6_host.runtime.xp1_saved_load import REFERENCE
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from test_session_capabilities import seal
from test_xp1_city_religion import religion_fixture
from test_xp1_great_people_commands import Fixture as CommandFixture, _RECRUIT, _GOLD, _FAITH
from test_xp1_great_people_reject import Fixture as RejectFixture, REJECT
from test_xp1_network_session import Fixture as ParentFixture
from test_xp1_religion_beliefs_public import terminal_v11


def worker_preflight():
    """Compile the actual worker branch without executing the loader."""
    tree = ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
    opening = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_open_xp1')
    guarded = [node for node in opening.body if isinstance(node, ast.If)
               and isinstance(node.test, ast.Name)
               and node.test.id in ('xp1_great_people_actions','xp1_great_people_reject')]
    assert len(guarded) == 2
    wrapper = ast.parse('def check(xp1_great_people_actions,xp1_great_people,xp1_dedications,'
                        'selected,occupation_image,closure,xp1_great_people_reject=False):\n pass').body[0]
    wrapper.body = guarded
    namespace = {'_Path':Path}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])),
                 str(worker.__file__), 'exec'), namespace)
    return namespace['check'], tree


def wrap_view(saved, decisions, *, actions_closed=False):
    """Exercise the actual post-query wrapper branch, without other UI readers."""
    tree = ast.parse(Path(view.__file__).read_text(encoding='utf-8'))
    branch, = [node for node in ast.walk(tree) if isinstance(node,ast.If)
               and ast.unparse(node.test) ==
               "getattr(saved, 'xp1_great_people_actions', False) is True and 'great_people' in decisions"]
    wrapper = ast.parse('def wrap(saved,decisions,actions_closed):\n pass').body[0]
    wrapper.body = [branch]
    scope = {'contract':network_turn}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[])),
                 str(view.__file__),'exec'),scope)
    scope['wrap'](saved,decisions,actions_closed)


class GreatPersonActionsSessionTests(unittest.TestCase):
    def fixture(self, *, reject=False):
        f = RejectFixture() if reject else CommandFixture()
        f.saved.xp1_great_people_actions = True
        f.saved.xp1_great_people_reject = reject
        f.token.world_input_prompts = {}
        f.token.trade_feedback = None
        from civ6_host.runtime.unit_operation_ui_profile import verify_live
        f.token.unit_source = verify_live(f.backend.core._handle, f.backend.runtime.read, core_sha256=XP1_CORE_SHA256)
        self.addCleanup(f.close)
        return f

    def test_constructor_requires_exact_image_query_and_pins_actual_reset(self):
        with ParentFixture() as f:
            legacy = f.session()
            self.assertIs(type(legacy), NativeNetworkSession)
            self.assertFalse(legacy.xp1_great_people_actions)
            self.assertFalse(legacy.xp1_great_people_reject)
            for flag in (0, 1, None, 'true'):
                with self.subTest(flag=flag), self.assertRaises(ValueError):
                    f.session(xp1_great_people_actions=flag, xp1_great_people=True)
                with self.subTest(reject_flag=flag), self.assertRaises(ValueError):
                    f.session(xp1_great_people_reject=flag, xp1_great_people_actions=True,
                              xp1_great_people=True, execution_image_profile=_XP1_PROFILE.id)
            for opts in ({}, {'xp1_great_people':True}, {'xp1_great_people_actions':True}):
                with self.subTest(dependencies=opts), self.assertRaises(ValueError):
                    f.session(xp1_great_people_reject=True,execution_image_profile=_XP1_PROFILE.id,**opts)
            with self.assertRaisesRegex(ValueError,'require the Great People query'):
                f.session(xp1_great_people_actions=True, execution_image_profile=_XP1_PROFILE.id)
            with self.assertRaisesRegex(ValueError,'exact installed'):
                f.session(xp1_great_people_actions=True, xp1_great_people=True)
            with patch.object(commands,'require_actions',side_effect=ValueError('source unavailable')):
                with self.assertRaisesRegex(ValueError,'source unavailable'):
                    f.session(xp1_great_people_actions=True,xp1_great_people=True,execution_image_profile=_XP1_PROFILE.id)
            with patch.object(commands,'verify_reject_source',side_effect=ValueError('reject source unavailable')):
                with self.assertRaisesRegex(ValueError,'reject source unavailable'):
                    f.session(xp1_great_people_reject=True,xp1_great_people_actions=True,
                              xp1_great_people=True,execution_image_profile=_XP1_PROFILE.id)
            current = f.session(xp1_great_people_actions=True, xp1_great_people=True,
                                execution_image_profile=_XP1_PROFILE.id)
            self.assertTrue(current.xp1_great_people_actions)
            self.assertFalse(current.xp1_prophet_activation)
            self.assertFalse(f.spawns)
            current.reset()
            closure_path = current.run / 'closure.json'
            self.assertLess(closure_path.stat().st_size, 8*1024*1024)
            closure = json.loads(closure_path.read_text(encoding='utf-8'))
            self.assertTrue(closure['xp1_great_people_actions'])
            self.assertTrue(closure['xp1_great_people'])
            self.assertEqual(len(f.spawns),1)  # Existing OS spawn double.
            for file, digest in commands.source_dependencies(_XP1_PROFILE).items():
                self.assertEqual(closure['pins'][str(Path(file).resolve())], digest)
            self.assertNotIn('xp1_great_people_reject',closure)
            self.assertNotIn(commands.REJECT_SOURCE[1],closure['pins'].values())
            current = f.session(xp1_great_people_reject=True,xp1_great_people_actions=True,
                                xp1_great_people=True,execution_image_profile=_XP1_PROFILE.id)
            current.reset()
            closure_path = current.run/'closure.json'
            self.assertLess(closure_path.stat().st_size,8*1024*1024)
            closure = json.loads(closure_path.read_text(encoding='utf-8'))
            self.assertIs(closure['xp1_great_people_reject'],True)
            for file,digest in commands.source_dependencies(_XP1_PROFILE,include_reject=True).items():
                self.assertEqual(closure['pins'][str(Path(file).resolve())],digest)

    def test_worker_preflight_checks_exact_owner_source_and_option_type(self):
        check, tree = worker_preflight()
        pins = commands.source_dependencies(_XP1_PROFILE)
        exact = SimpleNamespace(reference=REFERENCE)
        check(True, True, True, exact, _XP1_PROFILE, dict(pins=pins))
        for query, xp1, selected, image, closure in (
                (False,True,exact,_XP1_PROFILE,dict(pins=pins)),
                (True,False,exact,_XP1_PROFILE,dict(pins=pins)),
                (True,True,exact,None,dict(pins=pins)),
                (True,True,SimpleNamespace(reference=('foreign','0'*64)),_XP1_PROFILE,dict(pins=pins)),
                (True,True,exact,_XP1_PROFILE,dict(pins={})),
        ):
            with self.assertRaises(ValueError):
                check(True, query, xp1, selected, image, closure)
        check(False, False, False, None, None, {})
        reject_pins = commands.source_dependencies(_XP1_PROFILE,include_reject=True)
        check(True,True,True,exact,_XP1_PROFILE,dict(pins=reject_pins),True)
        for actions, query, xp1, selected, image, closure in (
                (False,True,True,exact,_XP1_PROFILE,dict(pins=reject_pins)),
                (True,False,True,exact,_XP1_PROFILE,dict(pins=reject_pins)),
                (True,True,False,exact,_XP1_PROFILE,dict(pins=reject_pins)),
                (True,True,True,exact,None,dict(pins=reject_pins)),
                (True,True,True,SimpleNamespace(reference=('foreign','0'*64)),_XP1_PROFILE,dict(pins=reject_pins)),
                (True,True,True,exact,_XP1_PROFILE,dict(pins=pins))):
            with self.subTest(reject_preflight=(actions,query,xp1,image)),self.assertRaises(ValueError):
                check(actions,query,xp1,selected,image,closure,True)
        for option in ('xp1_great_people_actions','xp1_great_people_reject'):
            expression, = [node for node in ast.walk(tree) if isinstance(node,ast.Compare)
                           and ast.unparse(node)==f"type(closure.get('{option}', False)) is not bool"]
            compiled = compile(ast.Expression(expression),str(worker.__file__),'eval')
            for flag in (True,False,1,0,None,'true'):
                self.assertIs(eval(compiled,{'closure':{option:flag}}),type(flag) is not bool)
        assignment, = [node for node in ast.walk(tree) if isinstance(node,ast.Assign)
                       and ast.unparse(node)=='saved.xp1_great_people_reject = xp1_great_people_reject']
        saved = SimpleNamespace()
        exec(compile(ast.Module(body=[assignment],type_ignores=[]),str(worker.__file__),'exec'),
             {'saved':saved,'xp1_great_people_reject':True})
        self.assertIs(saved.xp1_great_people_reject,True)

    def test_view_reads_once_preserves_reader_and_refuses_closed_or_waiting(self):
        f = self.fixture(reject=True)
        observation, _, _, decisions = religion_fixture()
        f.mutation = f'\ncfg.turn={observation["turn"]}'.encode('ascii')
        before = deepcopy(decisions)
        view._add_xp1_great_people(f.saved, observation, decisions)
        wrap_view(f.saved,decisions)
        self.assertTrue(decisions['schema'].endswith('.great-people-actions.v1.great-people-reject.v1'))
        self.assertEqual(f.evaluations,[b'@xp1_public_great_people'])
        self.assertEqual(decisions['great_people'],f.saved.explicit_great_people_actions)
        self.assertEqual(decisions['candidates'][:len(before['candidates'])],before['candidates'])
        offers = public.actions(decisions['great_people'],include_reject=True)
        self.assertEqual(offers,commands.actions(f.saved.explicit_great_people_actions,include_reject=True))
        self.assertIn(REJECT,offers)
        legacy = deepcopy(before)
        view._add_xp1_great_people(f.saved,observation,legacy)
        f.saved.xp1_great_people_reject = False
        wrap_view(f.saved,legacy)
        self.assertNotIn(public.REJECT,legacy['families'])
        self.assertNotIn(REJECT,[row['action'] for row in legacy['candidates']])
        f.saved.xp1_great_people_reject = True
        self.assertTrue(offers)
        seal(decisions)
        network_turn.validate_capability_catalogue(decisions,
            SimpleNamespace(episode_id=decisions['episode_id'],game_generation=decisions['game_generation']),
            decisions['sequence'],observation['turn'],player_id=observation['player_id'],observation=observation)
        for mode in ('waiting','closed','reduced'):
            with self.subTest(mode=mode):
                prior = terminal_v11(deepcopy(before)) if mode=='reduced' else deepcopy(before)
                if mode=='waiting':
                    prior['turn_controls'].update(active=False,active_complete=False)
                view._add_xp1_great_people(f.saved, observation, prior, actions_closed=mode!='waiting')
                self.assertIsNone(f.saved.explicit_great_people_actions)
                self.assertEqual(f.evaluations,[b'@xp1_public_great_people']*2)
                if mode=='reduced':
                    self.assertNotIn('great_people',prior)
                    self.assertNotIn(public.RECRUIT,prior['families'])
                else:
                    wrap_view(f.saved,prior,actions_closed=mode=='closed')
                    self.assertIsNone(prior['great_people'])
                    self.assertEqual(prior['families'][public.RECRUIT]['status'],'unqualified')
                    self.assertEqual(prior['families'][public.REJECT]['status'],'unqualified')

    def test_continuation_requires_both_scopes_and_strict_public_parameters(self):
        for mode in ('disabled','read_disabled','xp2','foreign_index','missing_currency'):
            with self.subTest(mode=mode):
                f = self.fixture()
                action = dict(_GOLD)
                if mode=='disabled':
                    f.saved.xp1_great_people_actions = False
                elif mode=='read_disabled':
                    f.saved.xp1_great_people = False
                elif mode=='xp2':
                    f.backend.load_abi = SimpleNamespace(core_sha256=XP2_CORE_SHA256)
                elif mode=='foreign_index':
                    action['individual_index'] = True
                else:
                    action.pop('currency')
                with self.assertRaises(ValueError):
                    f.token.execute(action,session=f.saved)
                self.assertEqual(f.machine,[])
                self.assertFalse(f.requested)
        for mode in ('reject_disabled','actions_disabled','read_disabled','xp2','bool_index','bool_cost','currency'):
            with self.subTest(reject=mode):
                f = self.fixture(reject=True)
                action = dict(REJECT)
                if mode=='reject_disabled': f.saved.xp1_great_people_reject=False
                elif mode=='actions_disabled': f.saved.xp1_great_people_actions=False
                elif mode=='read_disabled': f.saved.xp1_great_people=False
                elif mode=='xp2': f.backend.load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)
                elif mode=='bool_index': action['individual_index']=True
                elif mode=='bool_cost': action['cost']=True
                else: action['currency']='YIELD_GOLD'
                with self.assertRaises(ValueError): f.token.execute(action,session=f.saved)
                self.assertEqual(f.machine,[])
                self.assertFalse(f.requested)

    def exercise(self, action, *, allowed=True, available=True, alter=None, points_after=None):
        reject = action['kind']==public.REJECT
        f = self.fixture(reject=reject)
        self.assertIs(type(f.saved), SavedLoadOwner)
        self.assertIs(type(f.backend.prefix), SavedLoadServices)
        self.assertIs(type(f.token), SavedContinuation)
        f.choice = f.chosen = action
        from test_xp1_great_people_commands import packet
        if not reject:
            f.payload = packet(action)
        elif action['cost'] != REJECT['cost']:
            f.mutation=f'\ngreat.GetRejectCost=function()return {action["cost"]} end\n'.encode('ascii')
            expected=max(0,commands._signed32(40*256+64+commands._signed32(-action['cost']*256)))/256
            end = expected if points_after is None else points_after
            cost = max(0,commands._signed32(40-action['cost']))
            f.after=(f'\nrejectCurrent=false; rows[3].Claimant=nil; rows[3].Cost={cost};\n'
                     f'points.GetPointsTotal=function()return {end} end\n').encode('ascii')
        f.observation.update(width=f.token.observation['width'], height=f.token.observation['height'])
        f.token.observation = f.observation
        f.can_start = allowed
        state = commands.catalogue(f.saved,f.observation)
        f.saved._running = False
        choices = [dict(action=a) for a in commands.actions(state,include_reject=reject)] if available else []
        original = f.saved.execute

        def execute(selected):
            result = original(selected)
            return result if alter is None else alter(result)

        with (patch.object(view,'read',return_value=({},f.observation,dict(candidates=choices))),
              patch.object(xp1_session_inputs,'_write_once',return_value={'fixture':True}),
              patch.object(xp1_load_capability,'capability_source_scope',return_value=nullcontext()),
              patch.object(native_player_observation,'observe_player',side_effect=f.collect),
              patch.object(f.saved,'execute',side_effect=execute) as called):
            result = worker._execute_xp1(f.saved,action,0,0,Path(__file__).with_name('fixture-closure.json'))
        self.assertEqual(called.call_count,int(available))
        self.assertEqual(f.token.sequence,int(available))
        self.assertIs(f.backend.busy,False)
        self.assertIs(f.saved.poisoned,False)
        self.assertFalse(f.token.transport.pending)
        self.assertFalse(f.deferred.pending)
        if reject and (not allowed or not available):
            self.assertEqual(f.token.publication_count,0)
            self.assertIsNone(f.granted)
        elif reject:
            self.assertEqual(f.token.publication_count,1)
        return result

    def test_transition_and_worker_return_only_model_safe_status(self):
        for action in (_RECRUIT,_GOLD,_FAITH,REJECT,dict(REJECT,cost=0),dict(REJECT,cost=-2),dict(REJECT,cost=40)):
            with self.subTest(action=action):
                self.assertEqual(self.exercise(action),dict(status='completed',reason=None,requested_action=action))
        self.assertEqual(self.exercise(_GOLD,allowed=False),dict(status='refused',
            reason='native_great_person_can_start_false',requested_action=_GOLD))
        self.assertEqual(self.exercise(_FAITH,available=False),dict(status='refused',
            reason='native_action_no_longer_available',requested_action=_FAITH))
        self.assertEqual(self.exercise(REJECT,allowed=False),dict(status='refused',
            reason='native_great_person_can_start_false',requested_action=REJECT))
        self.assertEqual(self.exercise(REJECT,available=False),dict(status='refused',
            reason='native_action_no_longer_available',requested_action=REJECT))
        action=dict(REJECT,cost=-2)
        self.assertEqual(self.exercise(action,points_after=40.25),
                         dict(status='completed',reason=None,requested_action=action))

    def test_worker_rejects_corrupt_source_native_grant_and_currency(self):
        def mutate(outer, key, value):
            outer['effect']['effect'][key] = value
            return outer

        for key, value in (('individual_index',True),('unit_id',99),('instances_after',88),
                           ('archive_sha256','z'*64),('parameters',{}),('size_bytes',46),('amount_paid',549)):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError,'archive and own grant|patronage debit'):
                self.exercise(_GOLD,alter=lambda outer:mutate(outer,key,value))
        def invalid_pin(result):
            result['effect']['source_sha256']='0'*64
            return result
        with self.assertRaisesRegex(RuntimeError,'qualified source'):
            self.exercise(_GOLD,alter=invalid_pin)

    def test_rejection_worker_requires_private_effect_and_exact_refusal(self):
        def mutate(result,key,value):
            result['effect']['effect'][key]=value
            return result
        for key,value in (('individual_index',True),('class_index',False),('player_id',1),('turn',9),
                          ('cost',3),('own_receipts_after',1),('own_receipts_before',-1),
                          ('archive_sha256','z'*64),('parameters',{}),('size_bytes',True),
                          ('points_before',True),('points_after',float('nan')),
                          ('points_after',40.25),('points_after',38.251)):
            with self.subTest(key=key,value=value),self.assertRaisesRegex(RuntimeError,'Great Person rejection'):
                self.exercise(REJECT,alter=lambda result:mutate(result,key,value))
        def invalid_pin(result):
            result['effect']['source_sha256']=commands.SOURCE[1]
            return result
        with self.assertRaisesRegex(RuntimeError,'qualified source'):
            self.exercise(REJECT,alter=invalid_pin)
        def invalid_refusal(result):
            result['effect']['request']['request_invoked']=True
            return result
        with self.assertRaisesRegex(RuntimeError,'native CanStart'):
            self.exercise(REJECT,allowed=False,alter=invalid_refusal)


if __name__=='__main__':
    unittest.main()

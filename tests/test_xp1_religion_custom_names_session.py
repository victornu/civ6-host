"""Custom-name session composition; fixture machine calls, no process or DLL."""
import ast
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from lupa.lua51 import LuaRuntime  # Load before the worker import boundary.

from civ6_host.contracts import network_turn, religion_custom_names as public
from civ6_host.runtime import xp1_religion_custom_names as adapter
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
from test_xp1_religion_founding import Fixture as FoundationFixture
from test_xp1_religion_name_transport import fixture_archive, _XP1_FOUNDATION
from test_xp1_religion_custom_names_public import native_state, state, preceding
from test_xp1_religion_beliefs_public import terminal_v11, validate, unavailable
from civ6_host.contracts.religion_beliefs import _NATIVE_META
from test_xp1_city_religion import religion_fixture
from test_session_capabilities import seal


class Fixture(FoundationFixture):
    """Real saved owner/queues, with text and command machine boundaries doubled."""
    def __init__(self):
        super().__init__()
        self.saved.xp1_religion_founding = True
        self.saved.xp1_religion_custom_names = True
        self.token.world_input_prompts = {}
        self.token.trade_feedback = None
        self.rename = True
        self.placeholder = 'Saisissez le nom'
        self.default = 'Nom officiel'
        self.choice = dict(kind=public.KIND, index=9, hash=0xffffffff, custom_name='Église e\u0301 山 🌙')
        self.name_after = None
        from civ6_host.runtime.unit_operation_ui_profile import verify_live
        self.token.unit_source = verify_live(self.backend.core._handle, self.backend.runtime.read,
                                            core_sha256=XP1_CORE_SHA256)
        self.stack.enter_context(patch.object(adapter, '_catalogue', side_effect=self.catalogue))
        self.stack.enter_context(patch.object(adapter, '_uppercase', side_effect=lambda p,s:s.upper().encode('utf-8')))
        self.stack.enter_context(patch.object(adapter, '_read_own_custom_name', side_effect=self.read_name))
        self.stack.enter_context(patch.object(adapter, 'request_player_operation', side_effect=self.request))
        self.stack.enter_context(patch.object(adapter, 'observe_player', self.observe_native))

    def catalogue(self, prefix, observation):
        if prefix is not self.backend.prefix:
            raise AssertionError('Foreign prefix')
        own = prefix.inspect_own_religion_snapshot(observation['player_id'])
        name = '-' if self.name_after is None or self.created < 0 else self.name_after.encode('utf-8').hex()
        wire = f'{int(self.rename)}|{self.placeholder.encode("utf-8").hex()}|{name}'
        if self.created < 0 and not self.claimed:
            wire += f'|9:4294967295:{self.default.encode("utf-8").hex()}'
        return adapter._parse_catalog(wire.encode('ascii'), own)

    def read_name(self, prefix, own, pid, turn, *, expected_hash=None):
        if (prefix is not self.backend.prefix or (pid,turn)!=(0,8)
                or expected_hash!=self.choice['hash'] or own['religion_type_created']!=self.created):
            raise AssertionError('Custom name readback changed its owner or selected hash')
        return self.name_after

    def request(self, core, context, player, operation, parameters, **kwargs):
        transport = adapter.transport
        expected = {transport.PARAM_INSERT_MODE:transport.VALUE_EXCLUSIVE,
                    transport.PARAM_RELIGION_TYPE:self.choice['hash'],
                    transport.PARAM_RELIGION_CUSTOM_NAME:self.choice['custom_name'].encode('utf-8')}
        if (core is not self.backend.core or context != self.backend.prefix.context or player != 0
                or operation != transport.FOUND_RELIGION or parameters != expected
                or kwargs['core_sha256'] != XP1_CORE_SHA256 or kwargs['allow_religion_name'] is not True
                or kwargs['read'] != self.backend.runtime.read):
            raise AssertionError('Custom religion request crossed the qualified boundary')
        self.machine.append(('can_start',))
        if self.can_start:
            self.machine.append(('request',))
            # Existing transport test constructs the string variant from the
            # retained scalar archive. The real decoder and FIFO remain active.
            header = _XP1_FOUNDATION[:-4] + self.choice['hash'].to_bytes(4,'little')
            self.token.transport.pending.append(fixture_archive(expected[transport.PARAM_RELIGION_CUSTOM_NAME],header=header))
            self.name_after = self.choice['custom_name']
        return dict(can_start=self.can_start, request_invoked=self.can_start)


def worker_preflight():
    tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_open_xp1')
    blocks=[n for n in function.body if isinstance(n,ast.If)
            and isinstance(n.test,ast.Name) and n.test.id=='xp1_religion_custom_names']
    if len(blocks)!=1:raise AssertionError('Expected one custom-name preflight')
    wrapper=ast.parse('def check(xp1_religion_custom_names,xp1_religion_founding,xp1_dedications,selected,occupation_image,closure):\n pass').body[0]
    wrapper.body=blocks
    namespace={'_Path':Path}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[])),str(worker.__file__),'exec'),namespace)
    return namespace['check']


class CustomNameSessionTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_parent_flag_exact_profile_and_actual_source_closure(self):
        with ParentFixture() as f:
            original=f.session()
            self.assertIs(type(original),NativeNetworkSession)
            self.assertFalse(original.xp1_religion_custom_names)
            for options in ({'xp1_religion_custom_names':v} for v in (0,1,None,'true',True)):
                with self.subTest(options=options),self.assertRaises(ValueError):f.session(**options)
            with self.assertRaisesRegex(ValueError,'exact installed'):
                f.session(xp1_religion_founding=True,xp1_religion_custom_names=True)
            options=dict(xp1_religion_founding=True,xp1_religion_custom_names=True,
                         execution_image_profile=_XP1_PROFILE.id)
            with patch.object(adapter,'require_actions',side_effect=ValueError('source unqualified')):
                with self.assertRaisesRegex(ValueError,'source unqualified'):f.session(**options)
            current=f.session(**options)
            current.reset()
            path=current.run/'closure.json';self.assertLess(path.stat().st_size,8*1024*1024)
            closure=json.loads(path.read_text(encoding='utf-8'))
            self.assertTrue(closure['xp1_religion_founding']);self.assertTrue(closure['xp1_religion_custom_names'])
            self.assertFalse(closure.get('xp1_great_people_reject',False))
            for path,digest in adapter.source_dependencies(_XP1_PROFILE).items():
                self.assertEqual(closure['pins'][str(Path(path).resolve())],digest)
            self.assertEqual(len(f.spawns),1)  # OS launch replaced by ParentFixture.

    def test_worker_preflight_source_dependencies_and_wire_flag(self):
        check=worker_preflight();pins=adapter.source_dependencies(_XP1_PROFILE)
        selected=SimpleNamespace(reference=REFERENCE)
        check(True,True,True,selected,_XP1_PROFILE,dict(pins=pins))
        for foundation,dedications,reference,image,retained in (
                (False,True,REFERENCE,_XP1_PROFILE,pins),(True,False,REFERENCE,_XP1_PROFILE,pins),
                (True,True,('foreign','0'*64),_XP1_PROFILE,pins),(True,True,REFERENCE,None,pins),
                (True,True,REFERENCE,_XP1_PROFILE,{})):
            with self.subTest(foundation=foundation,dedications=dedications,image=image is None,pins=bool(retained)),self.assertRaises(ValueError):
                check(True,foundation,dedications,SimpleNamespace(reference=reference),image,dict(pins=retained))
        with patch.object(adapter,'require_actions',side_effect=ValueError('source unqualified')):
            with self.assertRaisesRegex(ValueError,'source unqualified'):
                check(True,True,True,selected,_XP1_PROFILE,dict(pins=pins))
        check(False,False,False,None,None,{})
        tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
        expressions=[n for n in ast.walk(tree) if isinstance(n,ast.Compare)
            and ast.unparse(n)=="type(closure.get('xp1_religion_custom_names', False)) is not bool"]
        self.assertEqual(len(expressions),1)
        expr=compile(ast.Expression(expressions[0]),str(worker.__file__),'eval')
        for flag in (True,False,0,1,None,'true'):
            self.assertEqual(eval(expr,{'closure':{'xp1_religion_custom_names':flag}}),type(flag) is not bool)
        assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)
                     and ast.unparse(n)=='saved.xp1_religion_custom_names = xp1_religion_custom_names']
        self.assertEqual(len(assignments),1)

    def test_view_last_wrapper_projection_waiting_closed_and_checkpoint(self):
        for mode in ('offered','no_site','already_founded','waiting','closed'):
            for options in ((False,False,0,False),(True,True,3,True)):
                with self.subTest(mode=mode,options=options):
                    obs,_,_,city=religion_fixture();decisions=deepcopy(city)
                    inactive=mode in ('waiting','closed')
                    if inactive:unavailable(decisions)
                    preceding(decisions,obs,options,waiting=inactive)
                    raw=native_state(obs,mode='offered' if inactive else mode)
                    if mode=='already_founded':raw['own_custom_name']=None
                    if mode in ('no_site','already_founded'):
                        decisions['religion_founding'].update(
                            own=public.project(raw,obs['player_id'],obs['turn'],observation=obs)['own'],foundation=None)
                        decisions['candidates']=[r for r in decisions['candidates'] if r['action']['kind']!='found_religion']
                        decisions['families']['found_religion']['candidate_ids']=[]
                        seal(decisions)
                    prior=deepcopy(decisions)
                    untouched=deepcopy(raw)
                    saved=SavedLoadOwner.__new__(SavedLoadOwner);saved.explicit_religion_custom_names={'stale':True}
                    def query(actual,observation):
                        self.assertIs(actual,saved);self.assertIs(observation,obs)
                        saved.explicit_religion_custom_names=deepcopy(raw);return raw
                    with patch.object(adapter,'catalogue',side_effect=query) as queried:
                        view._add_xp1_religion_custom_names(saved,obs,decisions,actions_closed=mode=='closed')
                    validate(obs,decisions,closed=mode=='closed')
                    self.assertIn(decisions['schema'],network_turn.XP1_RELIGION_CUSTOM_NAMES_SCHEMAS)
                    self.assertEqual(raw,untouched)
                    if inactive:
                        queried.assert_not_called();self.assertIsNone(saved.explicit_religion_custom_names)
                        self.assertIsNone(decisions['religion_custom_names'])
                    else:
                        queried.assert_called_once()
                        projected=decisions['religion_custom_names']
                        self.assertFalse(set(projected['own'])&_NATIVE_META)
                        self.assertEqual(projected['own_custom_name'],raw['own_custom_name'])
                        self.assertEqual(public.actions(projected),adapter.actions(raw))
                        restored,receipt=network_turn.checkpoint_catalogue(decisions,prior,obs,core_sha256=XP1_CORE_SHA256)
                        self.assertEqual(restored,prior)
                        self.assertEqual(receipt['added_public_fields'],['religion_custom_names'])
                        self.assertEqual(receipt['added_action_families'],[public.KIND])
                    self.assertEqual({k:v for k,v in decisions['families'].items() if k!=public.KIND},prior['families'])
        obs,_,_,city=religion_fixture();decisions=terminal_v11(city);prior=deepcopy(decisions)
        saved.explicit_religion_custom_names={'stale':True}
        with patch.object(adapter,'catalogue',side_effect=AssertionError('Closed native query')):
            view._add_xp1_religion_custom_names(saved,obs,decisions,actions_closed=True)
        self.assertEqual(decisions,prior);self.assertIsNone(saved.explicit_religion_custom_names)

    def test_real_saved_owner_fifo_completed_native_refusal_and_ui_refusal(self):
        for mode in ('completed','native_refusal','ui_refusal'):
            with self.subTest(mode=mode):
                f=self.fixture()
                self.assertIs(type(f.saved),SavedLoadOwner);self.assertIs(type(f.token),SavedContinuation)
                self.assertIs(type(f.backend.prefix),SavedLoadServices)
                if mode=='ui_refusal':f.choice['custom_name']=f.placeholder.lower()
                f.can_start=mode!='native_refusal'
                adapter.catalogue(f.saved,f.token.observation)
                f.saved._running=False
                with (patch.object(xp1_load_capability,'capability_source_scope',return_value=nullcontext()),
                      patch.object(f.backend.prefix,'emit',wraps=f.backend.prefix.emit) as emitted):
                    result=f.saved.execute(f.choice)
                effect=result['effect']
                self.assertEqual(result['action'],f.choice)
                self.assertEqual(effect['status'],'completed' if mode=='completed' else 'refused')
                self.assertEqual(effect['observation'],result['observation_after'])
                self.assertEqual(effect['source_sha256'],adapter.SOURCE[1])
                if mode=='completed':
                    self.assertEqual(effect['custom_name'],f.choice['custom_name'])
                    effects=[c for c in emitted.call_args_list if c.args[0]=='official_explicit_religion_custom_name_effect']
                    self.assertEqual(len(effects),1)
                else:
                    self.assertEqual(effect['refusal_code'],adapter.UI_INVALID if mode=='ui_refusal' else adapter.NATIVE_REFUSED)
                    self.assertEqual(result['observation_before'],result['observation_after'])
                    self.assertNotIn(('request',),f.machine)
                    if mode=='ui_refusal':
                        self.assertIsNone(effect['request']);self.assertNotIn(('can_start',),f.machine)
                    else:self.assertEqual(effect['request'],dict(can_start=False,request_invoked=False))
                self.assertEqual(f.token.sequence,1)
                self.assertFalse(f.backend.busy);self.assertFalse(f.saved.poisoned)
                self.assertEqual(f.token.transport.pending,[]);self.assertEqual(f.deferred.pending,[])
                with f.saved._attempt():after=adapter.catalogue(f.saved,f.token.observation)
                self.assertEqual(after['own_custom_name'],f.choice['custom_name'] if mode=='completed' else None)
                f.close()

    def test_continuation_rejects_unadmitted_and_malformed_actions(self):
        for mode in ('disabled','no_foundation','xp2','bool_index','bool_hash','no_name','extra'):
            f=self.fixture();action=deepcopy(f.choice)
            if mode=='disabled':f.saved.xp1_religion_custom_names=False
            elif mode=='no_foundation':f.saved.xp1_religion_founding=False
            elif mode=='xp2':f.backend.load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)
            elif mode=='bool_index':action['index']=True
            elif mode=='bool_hash':action['hash']=True
            elif mode=='no_name':del action['custom_name']
            else:action['name']='implicit'
            with self.subTest(mode=mode),self.assertRaises(ValueError):f.token.execute(action,session=f.saved)
            self.assertEqual(f.machine,[]);f.close()

    def command_result(self,effect,*,available=True,rename=True,action_name=None,after_change=None):
        f=self.fixture();action=deepcopy(f.choice)
        if action_name is not None:action['custom_name']=action_name
        before=deepcopy(f.token.observation);after=deepcopy(before)
        if after_change:after_change(after)
        effect=deepcopy(effect)
        if isinstance(effect,dict):effect.setdefault('observation',deepcopy(after))
        result=dict(action=deepcopy(action),effect=effect,observation_before=before,observation_after=after)
        raw=f.catalogue(f.backend.prefix,before);raw['rename_allowed']=rename
        # The owner fixture has an intentionally minimal observation. Public
        # city membership is independently covered by the view composition.
        projected=public.project(raw,before['player_id'],before['turn'])
        template={k:action[k] for k in ('kind','index','hash')}
        decisions=dict(candidates=[dict(action=template)] if available else [],religion_custom_names=projected)
        from civ6_host.runtime import xp1_session_inputs
        with (patch.object(view,'read',return_value=({},f.token.observation,decisions)),
              patch.object(f.saved,'execute',return_value=result) as execute,
              patch.object(xp1_session_inputs,'_write_once',return_value={'fixture':True})):
            value=worker._execute_xp1(f.saved,action,0,0,Path(__file__).parent/'fixture-closure.json')
        count=execute.call_count;f.close();return value,count

    def test_worker_parameterized_candidate_recheck_and_exact_default(self):
        completed=dict(status='completed',selected_index=9,selected_hash=0xffffffff,
                       custom_name='Église e\u0301 山 🌙',source_sha256=adapter.SOURCE[1])
        value,count=self.command_result(completed)
        self.assertEqual((value['status'],count),('completed',1))
        self.assertEqual(value['requested_action']['custom_name'],completed['custom_name'])
        for options in (dict(available=False),dict(rename=False)):
            value,count=self.command_result(completed,**options)
            self.assertEqual((value['reason'],count),('native_action_no_longer_available',0))
        value,count=self.command_result(dict(completed,custom_name='Nom officiel'),rename=False,action_name='Nom officiel')
        self.assertEqual((value['status'],count),('completed',1))

    def test_worker_native_and_ui_refusals_and_corrupt_receipts(self):
        completed=dict(status='completed',selected_index=9,selected_hash=0xffffffff,
                       custom_name='Église e\u0301 山 🌙',source_sha256=adapter.SOURCE[1])
        ui=dict(status='refused',refusal_code=adapter.UI_INVALID,request=None,source_sha256=adapter.SOURCE[1])
        native=dict(ui,refusal_code=adapter.NATIVE_REFUSED,request=dict(can_start=False,request_invoked=False))
        for effect in (ui,native):
            value,count=self.command_result(effect)
            self.assertEqual((value['status'],value['reason'],count),('refused',effect['refusal_code'],1))
        bad=[None,[],dict(completed,source_sha256='0'*64),dict(completed,selected_index=True),
             dict(completed,selected_hash=True),dict(completed,custom_name='Église é 山 🌙'),
             dict(completed,status='pending'),dict(completed,observation={}),
             {k:v for k,v in ui.items() if k!='request'},dict(ui,request=native['request']),
             dict(native,request=None),dict(native,request=dict(can_start=0,request_invoked=False)),
             dict(native,request=dict(can_start=False,request_invoked=True)),dict(ui,refusal_code='invented')]
        for effect in bad:
            with self.subTest(effect=effect),self.assertRaises(RuntimeError):self.command_result(effect)
        with self.assertRaises(RuntimeError):
            self.command_result(completed,after_change=lambda obs:obs.update(player_id=1))
        with self.assertRaises(RuntimeError):
            self.command_result(ui,after_change=lambda obs:obs.update(economy=dict(gold=999)))


if __name__=='__main__':unittest.main()

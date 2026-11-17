"""Portable session composition for explicit GP activation; no native process."""
import ast
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from lupa.lua51 import LuaRuntime

from civ6_host.contracts import network_turn, great_person_activation as public
from civ6_host.runtime import xp1_great_person_activation as adapter
from civ6_host.runtime import xp1_great_person_activation_source as source
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
from test_xp1_great_person_activation import Fixture as RuntimeFixture
from test_xp1_great_person_activation_public import native_state, preceding
from test_xp1_religion_beliefs_public import terminal_v11, validate, unavailable
from test_xp1_city_religion import religion_fixture


def worker_preflight():
    tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
    body=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_open_xp1').body
    blocks=[n for n in body if isinstance(n,ast.If) and isinstance(n.test,ast.Name)
            and n.test.id=='xp1_great_person_activation']
    if len(blocks)!=1:raise AssertionError('Expected one GP activation preflight')
    wrapper=ast.parse('def check(xp1_great_person_activation,xp1_dedications,selected,occupation_image,closure):\n pass').body[0]
    wrapper.body=blocks;scope={'_Path':Path}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[])),str(worker.__file__),'exec'),scope)
    return scope['check']


class GreatPersonActivationSessionTests(unittest.TestCase):
    def fixture(self):
        f=RuntimeFixture();self.addCleanup(f.close)
        f.token.world_input_prompts={};f.token.trade_feedback=None
        from civ6_host.runtime.unit_operation_ui_profile import verify_live
        f.token.unit_source=verify_live(f.backend.core._handle,f.backend.runtime.read,core_sha256=XP1_CORE_SHA256)
        return f

    def test_parent_default_independence_exact_image_and_actual_closure(self):
        with ParentFixture() as f:
            old=f.session();self.assertIs(type(old),NativeNetworkSession)
            self.assertFalse(old.xp1_great_person_activation)
            for flag in (0,1,None,'true'):
                with self.subTest(flag=flag),self.assertRaises(ValueError):f.session(xp1_great_person_activation=flag)
            with self.assertRaisesRegex(ValueError,'exact installed'):f.session(xp1_great_person_activation=True)
            options=dict(xp1_great_person_activation=True,execution_image_profile=_XP1_PROFILE.id)
            with patch.object(source,'require_actions',side_effect=ValueError('source refused')):
                with self.assertRaisesRegex(ValueError,'source refused'):f.session(**options)
            current=f.session(**options)
            for name in ('xp1_prophet_activation','xp1_great_people','xp1_great_people_actions',
                         'xp1_great_people_reject','xp1_religion_founding','xp1_religion_custom_names'):
                self.assertFalse(getattr(current,name))
            current.reset()
            path=current.run/'closure.json';self.assertLess(path.stat().st_size,8*1024*1024)
            closure=json.loads(path.read_text(encoding='utf-8'))
            self.assertTrue(closure['xp1_great_person_activation'])
            self.assertEqual(len(f.spawns),1)  # ParentFixture replaces OS launch.
            for path,digest in source.source_dependencies(_XP1_PROFILE).items():
                self.assertEqual(closure['pins'][str(Path(path).resolve())],digest)

    def test_worker_preflight_pins_wire_type_and_continued_flag(self):
        check=worker_preflight();pins=source.source_dependencies(_XP1_PROFILE)
        check(True,True,SimpleNamespace(reference=REFERENCE),_XP1_PROFILE,dict(pins=pins))
        for image,dedications,reference,retained in ((None,True,REFERENCE,pins),
                (_XP1_PROFILE,False,REFERENCE,pins),(_XP1_PROFILE,True,('other','0'*64),pins),
                (_XP1_PROFILE,True,REFERENCE,{})):
            with self.subTest(image=image is None,dedications=dedications,pins=bool(retained)),self.assertRaises(ValueError):
                check(True,dedications,SimpleNamespace(reference=reference),image,dict(pins=retained))
        check(False,False,None,None,{})
        tree=ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
        entries=[n for n in ast.walk(tree) if isinstance(n,ast.Compare)
            and ast.unparse(n)=="type(closure.get('xp1_great_person_activation', False)) is not bool"]
        self.assertEqual(len(entries),1);expr=compile(ast.Expression(entries[0]),str(worker.__file__),'eval')
        for flag in (True,False,0,1,None,'true'):
            self.assertEqual(eval(expr,{'closure':dict(xp1_great_person_activation=flag)}),type(flag) is not bool)
        entries=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)
            and ast.unparse(n)=='saved.xp1_great_person_activation = xp1_great_person_activation']
        self.assertEqual(len(entries),1)

    def test_view_last_optional_wrapper_waiting_closed_terminal_and_checkpoints(self):
        for mode in ('offered','empty','hidden','blocked','waiting','closed'):
            for options in ((False,False,False,0,False,False),(True,True,True,3,True,True)):
                with self.subTest(mode=mode,options=options):
                    obs,_,_,city=religion_fixture();decisions=deepcopy(city)
                    inactive=mode in ('waiting','closed')
                    if inactive:unavailable(decisions)
                    preceding(decisions,obs,options,waiting=inactive);prior=deepcopy(decisions)
                    native=native_state(obs,'offered' if inactive else mode);unchanged=deepcopy(native)
                    saved=SavedLoadOwner.__new__(SavedLoadOwner);saved.explicit_great_person_activation={'stale':True}
                    def query(actual,observation):
                        self.assertIs(actual,saved);self.assertIs(observation,obs)
                        saved.explicit_great_person_activation=deepcopy(native);return native
                    with patch.object(adapter,'catalogue',side_effect=query) as queried:
                        view._add_xp1_great_person_activation(saved,obs,decisions,actions_closed=mode=='closed')
                    validate(obs,decisions,closed=mode=='closed')
                    self.assertIn(decisions['schema'],network_turn.XP1_GREAT_PERSON_ACTIVATION_SCHEMAS)
                    self.assertEqual(native,unchanged)
                    self.assertEqual({k:v for k,v in decisions['families'].items() if k!=public.KIND},prior['families'])
                    if inactive:
                        queried.assert_not_called();self.assertIsNone(saved.explicit_great_person_activation)
                        self.assertIsNone(decisions['great_person_activation'])
                    else:
                        queried.assert_called_once();self.assertEqual(public.actions(decisions['great_person_activation']),adapter.actions(native))
                        restored,receipt=network_turn.checkpoint_catalogue(decisions,prior,obs,core_sha256=XP1_CORE_SHA256)
                        self.assertEqual(restored,prior)
                        self.assertEqual(receipt['added_public_fields'],['great_person_activation'])
                        self.assertEqual(receipt['added_action_families'],[public.KIND])
        obs,_,_,city=religion_fixture();decisions=terminal_v11(city);prior=deepcopy(decisions)
        saved.explicit_great_person_activation={'stale':True}
        with patch.object(adapter,'catalogue',side_effect=AssertionError('Closed native query')):
            view._add_xp1_great_person_activation(saved,obs,decisions,actions_closed=True)
        self.assertEqual(decisions,prior);self.assertIsNone(saved.explicit_great_person_activation)

    def test_actual_continuation_and_worker_complete_survive_consume_or_refuse(self):
        from civ6_host.runtime import xp1_session_inputs
        for mode in ('survive','consume','unchanged','work','refused'):
            with self.subTest(mode=mode):
                f=self.fixture();f.effect_mode='survive' if mode=='refused' else mode
                if mode in ('unchanged','work'):f.choice.update(unit_id=19,x=2)
                f.deny_request=mode=='refused'
                raw=adapter.catalogue(f.saved,f.token.observation)
                decisions=dict(candidates=[dict(action=a) for a in adapter.actions(raw)])
                f.saved._running=False
                self.assertIs(type(f.saved),SavedLoadOwner);self.assertIs(type(f.token),SavedContinuation)
                self.assertIs(type(f.backend.prefix),SavedLoadServices)
                with (patch.object(view,'read',return_value=({},f.token.observation,decisions)),
                      patch.object(xp1_load_capability,'capability_source_scope',return_value=nullcontext()),
                      patch.object(xp1_session_inputs,'_write_once',return_value={'fixture':True}),
                      patch.object(f.saved,'execute',wraps=f.saved.execute) as execute):
                    value=worker._execute_xp1(f.saved,f.choice,0,0,Path(__file__).parent/'fixture-closure.json')
                self.assertEqual(value,dict(status='refused' if mode=='refused' else 'submitted' if mode=='unchanged' else 'completed',
                    reason=adapter.REFUSED if mode=='refused' else adapter.UNCONFIRMED if mode=='unchanged' else None,requested_action=f.choice))
                execute.assert_called_once_with(f.choice)
                self.assertEqual(f.token.sequence,1)
                self.assertFalse(f.backend.busy);self.assertFalse(f.saved.poisoned)
                self.assertEqual(f.token.transport.pending,[]);self.assertEqual(f.deferred.pending,[])
                with f.saved._attempt():after=adapter.catalogue(f.saved,f.token.observation)
                f.token.check_close()
                ids=[r['unit_id'] for r in after['units']]
                self.assertEqual(f.choice['unit_id'] in ids,mode!='consume')
                if mode=='refused':self.assertFalse(any(r[0]=='request' for r in f.machine))
                f.close()

    def test_continuation_rejects_disabled_wrong_engine_and_extra_parameters(self):
        for mode in ('disabled','xp2','bool_id','bool_x','target'):
            f=self.fixture();action=deepcopy(f.choice)
            if mode=='disabled':f.saved.xp1_great_person_activation=False
            elif mode=='xp2':f.backend.load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)
            elif mode=='bool_id':action['unit_id']=True
            elif mode=='bool_x':action['x']=True
            else:action['target_id']=19
            with self.subTest(mode=mode),self.assertRaises(ValueError):f.token.execute(action,session=f.saved)
            self.assertEqual(f.machine,[]);f.close()

    def command_result(self, mutate=None, *, status='completed', consumed=False, available=True):
        f=self.fixture();before=deepcopy(f.token.observation);after=deepcopy(before)
        raw=adapter.catalogue(f.saved,f.token.observation);old=deepcopy(raw['units'][0]);new=deepcopy(old)
        if consumed:
            after['units']=[u for u in after['units'] if u['id']!=f.choice['unit_id']];new=None
        else:new['charges']=old['charges']-1
        receipt=dict(archive_sha256='a'*64,size_bytes=20,normalized_command_index=7,command_hash=public.OPERATION,
                     parameters={},post_command_sequence=1,native_archive_delivered=True,native_command_processed=True,
                     unit_before=old,unit_after=new,deferred_start_sequence=0,great_work_records=[],
                     completion_source_sha256=source.COMPLETION_SOURCE[1],effect_confirmed=True,
                     confirmation_basis='unit_consumed' if consumed else 'charges_consumed')
        if status=='completed':
            effect=dict(status=status,reason=None,observation=deepcopy(after),unit_id=17,x=0,y=0,
                        individual_index=old['individual_index'],class_index=old['class_index'],
                        charges_before=old['charges'],charges_after=None if consumed else new['charges'],
                        unit_consumed=consumed,source_sha256=source.SOURCE[1],receipt=receipt)
        else:
            after=deepcopy(before)
            effect=dict(status='refused',observation=deepcopy(before),refusal_code=adapter.REFUSED,
                        request=dict(can_start=False,request_invoked=False),source_sha256=source.SOURCE[1])
        result=dict(action=deepcopy(f.choice),effect=effect,observation_before=before,observation_after=after)
        if mutate:mutate(result)
        decisions=dict(candidates=[dict(action=f.choice)] if available else [])
        from civ6_host.runtime import xp1_session_inputs
        with (patch.object(view,'read',return_value=({},f.token.observation,decisions)),
              patch.object(f.saved,'execute',return_value=result) as execute,
              patch.object(xp1_session_inputs,'_write_once',return_value={'fixture':True})):
            value=worker._execute_xp1(f.saved,f.choice,0,0,Path(__file__).parent/'fixture-closure.json')
        count=execute.call_count;f.close();return value,count

    def test_worker_exact_source_archive_marker_charge_and_identity_receipts(self):
        for options in (dict(),dict(consumed=True),dict(status='refused')):
            result,count=self.command_result(**options)
            self.assertEqual(result['status'],options.get('status','completed'));self.assertEqual(count,1)
        result,count=self.command_result(available=False)
        self.assertEqual((result['reason'],count),('native_action_no_longer_available',0))
        changes=[lambda r:r.update(effect=None),lambda r:r['effect'].update(source_sha256='0'*64),
                 lambda r:r['effect'].update(unit_id=True),lambda r:r['effect'].update(charges_before=True),
                 lambda r:r['effect'].update(charges_after=2**31),lambda r:r['effect'].update(unit_consumed=1),
                 lambda r:r['effect'].update(charges_after=None),lambda r:r['effect'].update(individual_index=1),
                 lambda r:r['effect']['receipt'].update(native_command_processed=False),
                 lambda r:r['effect']['receipt'].update(post_command_sequence=True),
                 lambda r:r['effect']['receipt'].update(parameters={'x':0}),
                 lambda r:r['effect']['receipt'].update(size_bytes=24),
                 lambda r:r['effect']['receipt'].update(normalized_command_index=True),
                 lambda r:r['effect']['receipt'].update(archive_sha256='G'*64),
                 lambda r:r['effect']['receipt']['unit_after'].update(charges=9),
                 lambda r:r['effect']['receipt']['unit_before'].update(available=False),
                 lambda r:r['observation_before'].update(turn=9)]
        for number,mutate in enumerate(changes):
            with self.subTest(corruption=number),self.assertRaises(RuntimeError):self.command_result(mutate)
        with self.assertRaises(RuntimeError):
            self.command_result(lambda r:r['effect']['request'].update(can_start=0),status='refused')
        with self.assertRaises(RuntimeError):
            self.command_result(lambda r:r['effect']['request'].update(request_invoked=True),status='refused')
        with self.assertRaises(RuntimeError):
            self.command_result(lambda r:r['effect']['receipt'].update(unit_after=None))

    def test_worker_never_upgrades_processed_only_or_foreign_work_to_completed(self):
        from civ6_host.runtime.native import native_event_great_work as codec
        from civ6_host.runtime import xp1_great_work_source as works
        import struct
        from hashlib import sha256
        def unchanged(result):
            effect=result['effect'];receipt=effect['receipt']
            effect['charges_after']=effect['charges_before'];receipt['unit_after']['charges']=effect['charges_before']
        with self.assertRaisesRegex(RuntimeError,'confused command processing'):
            self.command_result(unchanged)
        def work(result,mode):
            unchanged(result);effect=result['effect'];receipt=effect['receipt']
            sequence=2;receipt.update(deferred_start_sequence=1,post_command_sequence=3,
                confirmation_basis='great_work_created')
            x,y,owner,typ,uid=3,0,0,1,17
            if mode=='owner':owner=1
            elif mode=='type':typ=2
            elif mode=='unit':uid=18
            elif mode=='position':x=0
            elif mode=='old':sequence=1
            elif mode=='late':sequence=4
            raw=codec.encode_record(sequence,dict(position_bytes=struct.pack('<ii',x,y),x=x,y=y,
                selector=0,source_value=7,descriptor_tail=11),struct.pack('<HHI',owner,typ,uid),
                dict(owner=0,city_id=65537 if mode=='city' else 65536,district_id=0))
            receipt['great_work_records']=[dict(record_hex=raw.hex(),record_sha256=sha256(raw).hexdigest(),
                source_sha256='0'*64 if mode=='source' else works.UNIT_PRODUCER_SOURCE[1])]
        self.assertEqual(self.command_result(lambda r:work(r,'exact'))[0]['status'],'completed')
        for mode in ('owner','type','unit','position','city','old','late','source'):
            with self.subTest(mode=mode),self.assertRaises(RuntimeError):self.command_result(lambda r:work(r,mode))

    def test_submitted_processed_reply_keeps_client_choices_and_checkpoint_projection(self):
        from civ6_host import SessionClient
        from test_xp1_great_person_activation_public import ActivationBackend
        class ProcessedBackend(ActivationBackend):
            def _reply(self,operation,sequence,player,requested=None):
                value=super()._reply(operation,sequence,player,requested)
                if operation=='act' and self.status=='submitted':
                    value['command_result']['reason']=adapter.UNCONFIRMED
                return value
        backend=ProcessedBackend();backend.status='submitted'
        client=SessionClient(backend);frame=client.reset()
        row=next(r for r in frame['decisions']['candidates'] if r['action']['kind']==public.KIND)
        frame=client.act(0,frame['decisions']['decision_id'],row['candidate_id'])
        self.assertEqual(client.command_result['reason'],adapter.UNCONFIRMED)
        self.assertIsNone(frame['applied_action']);self.assertEqual(len(backend.calls),1)
        client.information('great_person_activation')
        observed=client.observe(0);self.assertEqual(len(backend.calls),2)
        obs,dec=observed['observation'],observed['decisions']
        original=deepcopy(dec)
        # Use the same retained historical catalogue projection as the routes.
        from test_xp1_city_religion import ReligionBackend
        prior=preceding(ReligionBackend._reply(backend,'observe',observed['sequence'],0)['decisions'],obs)
        projected,_=network_turn.checkpoint_catalogue(dec,prior,obs,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected,prior);self.assertEqual(dec,original)
        other=next(r for r in dec['candidates'] if r['action']['kind'] not in
                   (public.KIND,'policies','confirm_dedications','found_custom_religion'))
        backend.status='completed'
        reply=client.act(0,dec['decision_id'],other['candidate_id'])
        self.assertEqual(client.command_result['status'],'completed');self.assertEqual(len(backend.calls),3)
        self.assertEqual(reply['applied_action'],other['action'])
        client.close()


if __name__=='__main__':unittest.main()

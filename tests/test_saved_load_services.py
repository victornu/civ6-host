import ast
import ctypes as C
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.native.native_official_load import SavedConfigurationReadback,OfficialPrefix
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256


class SavedLoadServicesTests(unittest.TestCase):
    def fixture(self):
        from test_script_event_service import Host
        h=Host();h.pointer=123;flag=[0]
        def read(p,n):
            if (p,n)==(0x1008,8):return (0x2000).to_bytes(8,'little')
            if (p,n)==(0x2060,8):return (0x3000).to_bytes(8,'little')
            if (p,n)==(0x32A4,1):return bytes(flag)
            raise ValueError((p,n))
        b=NS(core=NS(_handle=0x5000),context=0x1000,host=h,emit=Mock(),destroyed=False,
             runtime=NS(read=read),configuration_abi=NS(core_sha256=XP1_CORE_SHA256))
        rt=NS(registry=NS(validate=Mock(),_check=Mock()),service_owner=h,
              database_bound=True,configuration_bound=True,locale_bound=True,execute=Mock())
        order=[];owners={}
        def factory(name):
            def create(*args,**kwargs):
                o=NS(close=lambda:order.append(name));owners[name]=o;return o
            return create
        module='civ6_host.runtime.saved_load_services.'
        patches=[patch(module+n,side_effect=factory(n)) for n in (
            'ScalarService','MapService','MapArgumentFactory','ScriptEventService','ScriptContextService')]
        patches += [patch(module+n,return_value={}) for n in ('verify_configuration','verify_contexts','verify_events')]
        for p in patches:p.start();self.addCleanup(p.stop)
        child=NS(pointer=100)
        service=SavedLoadServices(b,rt,child,object(),core_sha256=XP1_CORE_SHA256,
            script_hashes={},bootstrap=Mock(),saved_map_values=(('MAP_SIZE',1),),saved_config_sha='a'*64)
        owners['MapArgumentFactory'].live={}
        owners['ScriptEventService'].script_arguments=NS(live_count=0)
        owners['ScriptEventService'].dispatch_depth=0
        o=owners['ScriptContextService'];o.names={};o.depth=o.lock_depth=0;o.quarantined=False
        return b,rt,service,order,flag

    def test_base_readback_method_is_the_same_extracted_ast(self):
        old=ast.parse((resource_root()/'civ6rl/native_official_load.py').read_text(encoding='utf-8'))
        new=ast.parse(Path(__import__(OfficialPrefix.__module__,fromlist=['x']).__file__).read_text(encoding='utf-8'))
        def method(tree,cls):
            c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
            return next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='verify_configuration_scalar_marshalling')
        self.assertEqual(ast.dump(method(old,'OfficialPrefix')),ast.dump(method(new,'SavedConfigurationReadback')))
        self.assertIs(OfficialPrefix.verify_configuration_scalar_marshalling,SavedConfigurationReadback.verify_configuration_scalar_marshalling)

    def test_attach_is_owned_phase_bound_and_does_not_admit_game_load(self):
        b,rt,s,order,flag=self.fixture()
        target=NS(core=b.core,context=b.context,host=b.host,load_abi=b.configuration_abi,
            stage='prepared',prefix=None,check_thread=Mock(),game_flag=Mock(return_value=0))
        s.attach(target)
        self.assertIs(target.prefix,s);self.assertEqual(target.stage,'prefix-installed')
        self.assertFalse(hasattr(s,'deferred_events'))
        self.assertFalse(hasattr(s,'actions'))
        with self.assertRaisesRegex(ValueError,'mismatch'):s.attach(target)
        s.close();self.assertEqual(order,['ScriptContextService','ScriptEventService','MapArgumentFactory','MapService','ScalarService'])
        self.assertFalse(rt.execute.called)

    def test_loaded_game_retained_payload_and_child_prevent_early_close(self):
        b,rt,s,order,flag=self.fixture();flag[0]=1
        with self.assertRaisesRegex(RuntimeError,'teardown'):s.close()
        self.assertEqual(order,[])
        flag[0]=0;s.map_arguments.live[1]=object()
        with self.assertRaisesRegex(RuntimeError,'retained'):s.close()
        s.map_arguments.live.clear();s.contexts.names[1]=b'child'
        with self.assertRaisesRegex(RuntimeError,'retained'):s.close()
        s.contexts.names.clear();s.close();s.close()
        self.assertEqual(len(order),5)
        self.assertIsNone(b.host._saved_load_services)

    def test_successful_readback_shared_once_failure_quarantines(self):
        b,rt,s,order,flag=self.fixture()
        s.verify_configuration_scalar_marshalling()
        self.assertTrue(s.configuration_readback_verified)
        self.assertEqual(rt.execute.call_count,1)
        self.assertIn(b"MapConfiguration.GetValue('MAP_SIZE')==1",rt.execute.call_args.args[1])
        with self.assertRaisesRegex(ValueError,'already'):s.verify_configuration_scalar_marshalling()
        self.assertTrue(s.quarantined)
        with self.assertRaisesRegex(RuntimeError,'quarantined'):s.close()

    def test_unknown_engine_and_foreign_database_refused_before_install(self):
        b,rt,s,order,flag=self.fixture();s.close()
        args=dict(core_sha256='0'*64,script_hashes={},bootstrap=Mock(),saved_map_values=(('MAP_SIZE',1),),saved_config_sha='a'*64)
        with self.assertRaisesRegex(ValueError,'engine'):SavedLoadServices(b,rt,object(),object(),**args)
        args['core_sha256']=XP1_CORE_SHA256;rt.service_owner=object()
        with self.assertRaisesRegex(ValueError,'borrow'):SavedLoadServices(b,rt,object(),object(),**args)

    def test_deferred_owner_is_optional_explicit_and_released_before_shared_services(self):
        b,rt,s,order,flag=self.fixture()
        owner=NS(close=lambda:order.append('DeferredService'))
        with patch('civ6_host.runtime.deferred_service.DeferredService',return_value=owner) as create:
            self.assertIs(s.install_deferred_events(optional_preprocessor=None,queue_metadata_service=None),owner)
            self.assertEqual(create.call_args.kwargs['core_sha256'],XP1_CORE_SHA256)
            self.assertIs(create.call_args.kwargs['read'],b.runtime.read)
            with self.assertRaisesRegex(ValueError,'already'):s.install_deferred_events(optional_preprocessor=None,queue_metadata_service=None)
        s.close()
        self.assertEqual(order[0],'DeferredService')

    def test_failed_deferred_install_quarantines_combined_owner(self):
        b,rt,s,order,flag=self.fixture()
        with patch('civ6_host.runtime.deferred_service.DeferredService',side_effect=ValueError('profile mismatch')):
            with self.assertRaisesRegex(ValueError,'profile mismatch'):
                s.install_deferred_events(optional_preprocessor=None,queue_metadata_service=None)
        self.assertTrue(s.quarantined);self.assertEqual(order,[])

    def test_control_inputs_share_the_deferred_owner_and_close_first(self):
        b,rt,s,order,flag=self.fixture()
        with self.assertRaisesRegex(ValueError,'existing deferred'):
            s.install_control_inputs(local_player_id=7)
        d=NS(close=lambda:order.append('deferred'))
        s.deferred_events=d
        controller=NS(close=lambda:order.append('controller'))
        with patch('civ6_host.runtime.control_input_service.ControlInputService',return_value=controller) as create:
            self.assertIs(s.install_control_inputs(local_player_id=7),controller)
            self.assertIs(create.call_args.args[3],d)
            self.assertEqual(create.call_args.kwargs['local_player_id'],7)
        s.close();self.assertEqual(order[:2],['controller','deferred'])

    def test_argument_owner_uses_the_same_deferred_queue_and_closes_before_it(self):
        b,rt,s,order,flag=self.fixture()
        s.deferred_events=NS(close=lambda:order.append('deferred'))
        arguments=NS(close=lambda:order.append('arguments'))
        with patch('civ6_host.runtime.event_argument_service.EventArgumentService',return_value=arguments) as create:
            self.assertIs(s.install_event_arguments(normalizer_transform=None,dynamic_registrations=()),arguments)
            self.assertIs(create.call_args.args[3],s.deferred_events)
        s.close();self.assertEqual(order[:2],['arguments','deferred'])

    def test_status_owner_borrows_arguments_and_closes_before_the_reader(self):
        b,rt,s,order,flag=self.fixture()
        with self.assertRaisesRegex(ValueError,'event argument'):
            s.install_status_messages(receiver_state={},writer_metadata_service=None,per_thread_hook=None)
        s.deferred_events=NS(close=lambda:order.append('deferred'))
        s.event_arguments=NS(close=lambda:order.append('arguments'))
        status=NS(close=lambda:order.append('status'))
        with patch('civ6_host.runtime.status_message_service.StatusMessageService',return_value=status) as create:
            self.assertIs(s.install_status_messages(receiver_state={},writer_metadata_service=None,per_thread_hook=None),status)
            self.assertIs(create.call_args.args[3],s.event_arguments)
            self.assertTrue(create.call_args.kwargs['context_alive']())
        s.close();self.assertEqual(order[:3],['status','arguments','deferred'])

    def test_cache_facades_use_same_context_and_release_after_event_consumers(self):
        b,rt,s,order,flag=self.fixture()
        s.deferred_events=NS(close=lambda:order.append('deferred'))
        facades=NS(close=lambda:order.append('facades'))
        with patch('civ6_host.runtime.cache_facade_service.CacheFacadeService',return_value=facades) as create:
            self.assertIs(s.install_cache_facades(),facades)
            self.assertEqual(create.call_args.args,(b.core,b.context))
            self.assertIs(create.call_args.kwargs['read'],b.runtime.read)
            self.assertTrue(create.call_args.kwargs['context_alive']())
            with self.assertRaisesRegex(ValueError,'already'):s.install_cache_facades()
        s.close();self.assertEqual(order[:3],['deferred','facades','ScriptContextService'])

    def test_uncertain_cache_acquisition_quarantines_saved_services(self):
        b,rt,s,order,flag=self.fixture()
        with patch('civ6_host.runtime.cache_facade_service.CacheFacadeService',side_effect=RuntimeError('uncertain factory')):
            with self.assertRaisesRegex(RuntimeError,'uncertain'):s.install_cache_facades()
        self.assertTrue(s.quarantined);self.assertEqual(order,[])

    def test_player_query_owner_is_shared_and_closed_after_event_borrowers(self):
        b,rt,s,order,flag=self.fixture()
        s.event_arguments=NS(close=lambda:order.append('arguments'))
        query=NS(close=lambda:order.append('queries'));lock=object()
        with patch('civ6_host.runtime.player_notification_service.PlayerNotificationService',return_value=query) as create:
            self.assertIs(s.install_player_queries(core_lock=lock),query)
            self.assertEqual(create.call_args.args,(b.host,b.core,b.context))
            self.assertIs(create.call_args.kwargs['core_lock'],lock)
            with self.assertRaises(ValueError):s.install_player_queries(core_lock=lock)
        s.close();self.assertEqual(order[:3],['arguments','queries','ScriptContextService'])

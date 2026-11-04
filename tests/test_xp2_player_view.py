"""Composed saved-view ownership; fixtures do not qualify native UI execution."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,call,patch

from civ6_host.runtime import xp1_ui_binding as view
from civ6_host.runtime import xp1_cache_publication as publication
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.saved_load_profiles import profile_for_sha
from civ6_host.runtime.native.native_official_postload import OfficialPost160Backend
from civ6_host.runtime.native.native_player_view import NativePlayerViewPublisher
from civ6_host.runtime.native.native_ui_cache_backend import NativeCacheFacadeBackend
from civ6_host.runtime.saved_load_job_observer import SavedLoadJobObserver
import test_xp2_cache_publication as cache_fixtures
from test_xp1_loaded_lifetime import snapshot


class PlayerViewTests(unittest.TestCase):
    def graph(self):
        f,a,lease=cache_fixtures.XP2CacheTests().graph();b=a.owner;p=b.prefix;rt=p.runtime
        p.game_child=object();p.closed=False
        p.view_publisher=publisher=NativePlayerViewPublisher(b.core,b.context,Mock(),read=f.read,
            core_sha256=XP2_CORE_SHA256)
        a.publisher=publisher
        backend=NativeCacheFacadeBackend(b.core,Mock(),context_alive=lambda:True,read=f.read,
            core_sha256=XP2_CORE_SHA256,publication_owner=lease)
        lease.attach(publisher,backend)
        rt.registry=NS(validate=Mock(return_value=1));rt.acquire=Mock(return_value=object())
        rt.attach_standard_libraries=Mock();rt.attach_ui_enums=Mock()
        rt.namespaces=NS(register=Mock());rt.execute=Mock()
        rt.bind_native_ui_api=Mock(return_value={'native_ui_registration_returned':True})
        a.publication_owner=lease;lease.entered=lease.returned=lease.copied=True
        b.stage='facades-candidate-observed';b.busy=False
        post=OfficialPost160Backend.__new__(OfficialPost160Backend)
        post.owner=b;post.facade=a;post.postload_mode='candidate';post._candidate_cache_lease=lease
        post.attempted=post.native_call_attempted=True
        post.candidate_diagnostics={'void_return_ignored':True}
        b._xp1_post160_attempt=post
        lease.begin_post160(post);lease.finish_post160(post)
        b.stage=publication.FINISHED_STAGE;b.busy=False
        pub=publication.SavedCachePublication(post)
        lease.begin_publication(pub);lease.finish_publication(pub)
        pub.completed=pub.native_returned=True;pub.result={}
        b.loaded_readback.update(player_id=0)
        observed=dict(turn=0,width=74,height=46,player_id=0)
        state=snapshot();state['source_proof_sha256']=__import__(
            'civ6_host.runtime.saved_load_job_observer',fromlist=['XP2_SOURCE']).XP2_SOURCE[1]
        state['core_identity']={'sha256':XP2_CORE_SHA256,'profile':3}
        b.jobs_snapshot=Mock(return_value=state);b.control=Mock(return_value={})
        return b,lease,pub,observed

    def test_same_stage_owner_selects_xp2_and_preserves_gameplay_child(self):
        b,lease,pub,observed=self.graph();v=view.SavedPlayerView(pub)
        rt=b.prefix.runtime
        with patch('civ6_host.runtime.native.native_player_observation.observe_player',return_value=observed) as collect:
            result=v.run()
        self.assertIs(result['observation'],observed)
        self.assertEqual(result['core_sha256'],XP2_CORE_SHA256)
        self.assertIs(b.prefix.ui_child,v.child)
        self.assertEqual(rt.namespaces.register.call_args_list,
                         [call(v.child, 'GameInfo'), call(v.child, 'Locale')])
        rt.bind_native_ui_api.assert_called_once_with(b.prefix.game_child,v.child,b.context,b.core,
            core_sha256=XP2_CORE_SHA256)
        collect.assert_called_once_with(rt,v.child,0)
        self.assertIs(rt.execute.call_args.args[0],b.prefix.game_child)
        self.assertEqual(b.stage,publication.COMPLETED_STAGE)
        self.assertFalse(result['public_runtime_admitted'])
        self.assertFalse(lease.poisoned)
        with self.assertRaisesRegex(ValueError,'cannot retry'):v.run()

    def test_actual_job_observer_refuses_replaced_view_or_engine(self):
        b,lease,pub,_=self.graph();v=view.SavedPlayerView(pub)
        b.stage=view.ACTIVE_STAGE;b.busy=True;b.snapshot_phase='before'
        observer=SavedLoadJobObserver.__new__(SavedLoadJobObserver);observer.backend=b
        self.assertTrue(observer._exclusive())
        b.load_abi=profile_for_sha(XP1_CORE_SHA256)
        with self.assertRaisesRegex(ValueError,'ownership'):observer._exclusive()
        b.load_abi=profile_for_sha(XP2_CORE_SHA256);b._xp1_player_view=NS(owner=b)
        self.assertFalse(observer._exclusive())

    def test_wrong_perspective_poisoned_without_substitution(self):
        b,lease,pub,_=self.graph();v=view.SavedPlayerView(pub)
        with patch('civ6_host.runtime.native.native_player_observation.observe_player',side_effect=ValueError('observer differs')):
            with self.assertRaisesRegex(ValueError,'observer differs'):v.run()
        self.assertTrue(lease.poisoned);self.assertEqual(b.stage,'poisoned')
        self.assertFalse(v.completed);self.assertIsNone(v.result)
        b.prefix.runtime.execute.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)

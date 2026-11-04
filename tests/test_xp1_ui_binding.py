"""Source/ownership regression checks; fixtures are not native qualification."""
import ast
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch
from civ6_host.runtime import xp1_ui_binding as ui
from civ6_host.runtime import xp1_cache_publication as publication
from civ6_host.runtime import saved_load_job_observer as jobs
import test_xp1_loaded_lifetime as fixtures

class UIBindingTests(unittest.TestCase):
    def graph(self):
        b,a,lease,post=fixtures.graph()
        pub=publication.SavedCachePublication(post)
        lease.begin_publication(pub);lease.finish_publication(pub)
        pub.completed=pub.native_returned=True;pub.result={}
        b.prefix.deferred_events=NS(ui_cache_callbacks_enabled=False)
        b.prefix.runtime.registry.validate=Mock(return_value=1)
        return b,a,lease,pub

    def test_source_instructions_and_ui_slot_are_enforced(self):
        p=ui.source();base=0x200000000;memory={}
        for body in p['functions']['xp1'].values():
            for f in ui._body(body)['fragments']:
                for i in f['instructions']:
                    at=base+int(i['va'],16)-0x180000000
                    memory.update((at+n,v) for n,v in enumerate(bytes.fromhex(i['bytes'])))
        for r in p['slots']['xp1']:
            memory.update((base+r['table_rva']+r['slot']+n,v)
                          for n,v in enumerate((base+r['target_rva']).to_bytes(8,'little')))
        read=lambda at,n:bytes(memory[at+i] for i in range(n))
        ui.verify_live(base,read)
        memory[base+0x8aaf10+0x18]^=1
        with self.assertRaisesRegex(ValueError,'slot changed'):ui.verify_live(base,read)

    def test_base_method_body_is_preserved_by_extraction(self):
        import extraction_xp1_ui_binding as hook
        raw='class NativeScriptRuntime:\n    def bind_native_ui_api(self,a,b,c,d):\n        return original(a,b,c,d)\n'
        tree=ast.parse(hook.parameterize('civ6rl.native_script_runtime',raw))
        fn=tree.body[0].body[0]
        old=ast.parse(raw).body[0].body[0]
        self.assertEqual(ast.dump(fn.body[-1]),ast.dump(old.body[0]))
        self.assertEqual(ast.literal_eval(fn.args.kw_defaults[0]),hook.BASE)
        self.assertIn('engine is not admitted',ast.unparse(fn))

    def test_exact_finished_owner_and_single_attempt(self):
        b,a,lease,pub=self.graph();pub.completed=False
        with self.assertRaisesRegex(ValueError,'completed native'):ui.SavedPlayerView(pub)
        pub.completed=True;v=ui.SavedPlayerView(pub)
        with self.assertRaisesRegex(ValueError,'already used'):ui.SavedPlayerView(pub)
        b.stage=ui.ACTIVE_STAGE;b.busy=True;v.check_active()
        del b.prefix.deferred_events.ui_cache_callbacks_enabled
        v.check_active() # Actual SavedLoadServices has no Base-only UI gate.
        a.publisher.native_cache_gate=True
        with self.assertRaisesRegex(ValueError,'candidate gates'):v.check_active()
        a.publisher.native_cache_gate=False;b.prefix.deferred_events.ui_cache_callbacks_enabled=True
        with self.assertRaisesRegex(ValueError,'candidate gates'):v.check_active()

    def test_job_observer_requires_exact_player_view_owner(self):
        b,a,lease,pub=self.graph();v=ui.SavedPlayerView(pub)
        b.stage=ui.ACTIVE_STAGE;b.busy=True;b.snapshot_phase='before'
        observer=jobs.SavedLoadJobObserver.__new__(jobs.SavedLoadJobObserver);observer.backend=b
        self.assertTrue(observer._exclusive())
        b._xp1_player_view=NS(owner=b,check_active=Mock())
        self.assertFalse(observer._exclusive())

    def test_bind_refuses_aliases_before_native_registration(self):
        rt=NS(registry=NS(validate=lambda child:1),host=NS(),lua={'gettop':lambda ptr:0},
              _xp1_script_bind_entered=True,database_bound=True,configuration_bound=True,locale_bound=True)
        with self.assertRaisesRegex(ValueError,'distinct owned children'):
            ui.bind_xp1_ui_api(rt,object(),object(),1,NS())

    def test_shared_observation_failure_is_never_replaced(self):
        b,a,lease,pub=self.graph();v=ui.SavedPlayerView(pub);rt=v.runtime
        rt.acquire=Mock(return_value=object());rt.attach_standard_libraries=Mock()
        rt.attach_ui_enums=Mock();rt.namespaces=NS(register=Mock());rt.bind_native_ui_api=Mock(return_value={})
        rt.execute=Mock();b.loaded_readback['player_id']=0
        b.jobs_snapshot=Mock(return_value=fixtures.snapshot())
        with patch('civ6_host.runtime.native.native_player_observation.observe_player',side_effect=ValueError('observer differs')):
            with self.assertRaisesRegex(ValueError,'observer differs'):v.run()
        self.assertTrue(lease.poisoned);self.assertFalse(v.completed)
        self.assertEqual(b.stage,'poisoned');rt.execute.assert_not_called()
        self.assertFalse(a.publisher.native_cache_gate)
        with self.assertRaisesRegex(ValueError,'cannot retry'):v.run()

if __name__=='__main__':unittest.main(verbosity=2)

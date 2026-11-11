"""Exact source/extraction and shared Lua checks; no GameCore invocation."""
import ast
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp1_unit_attack_profile as profile
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as BASE, XP1_CORE_SHA256 as XP1
from civ6_host.runtime.paths import resource_root

HOST=Path(__file__).resolve().parents[1];LAB=resource_root()
sys.path.append(str(LAB/'work/lua-test-deps'))
from lupa.lua51 import LuaRuntime


def helper(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


HOOK=helper('selected_unit_attack_hook',HOST/'tools/extraction_xp1_unit_attacks.py')
WORLD=helper('selected_attack_world_hook',HOST/'tools/extraction_xp1_world_input.py')


def transformed(name):
    raw=(LAB/'civ6rl'/f'{name}.py').read_text()
    return HOOK.parameterize('civ6rl.'+name,WORLD.parameterize('civ6rl.'+name,raw))


@contextmanager
def selected_modules():
    """Run authored transforms with real shared bodies, isolated from installation."""
    import civ6_host.runtime.native as package
    order=('native_combat_actions','native_saved_city_targets','native_saved_combat')
    modules={name:types.ModuleType(package.__name__+'.'+name) for name in order}
    with ExitStack() as stack:
        stack.enter_context(patch.dict(sys.modules,{m.__name__:m for m in modules.values()}))
        for name,module in modules.items():
            stack.enter_context(patch.object(package,name,module,create=True))
            module.__file__=str(LAB/'civ6rl'/f'{name}.py')
        for name in order:
            tree=ast.parse(transformed(name))
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith('civ6rl'):
                    node.module=node.module.replace('civ6rl','civ6_host.runtime.native',1)
            exec(compile(ast.fix_missing_locations(tree),modules[name].__file__,'exec'),modules[name].__dict__)
        yield modules


def city_harness():
    tree=ast.parse((LAB/'tests/test_native_city_targets936.py').read_text())
    return ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='HARNESS' for t in n.targets))).encode()


def state():
    units=[dict(unit_id=17,unit_type=21,x=0,y=0,damage=0,moves=2,attacks_remaining=1)]
    obs=dict(player_id=0,turn=7,width=3,height=2,
        units=[dict(id=17,type=21,x=0,y=0,damage=0,moves=2)],
        visible_enemy_units=[dict(owner=1,id=9,type=21,x=1,y=0,damage=0,visible=True)])
    action=dict(kind='unit_attack',unit_id=17,operation='MOVE_TO',input_route='enemy_flag',plot_id=1,x=1,y=0)
    return obs,units,action


class AttackSourceTests(unittest.TestCase):
    def test_source_closure_exact_callbacks_and_live_guards(self):
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        from civ6_host.runtime.xp1_session_inputs import materialize_xp1_session_pins

        p=profile.verify_source();self.assertEqual(len(p['bindings']),53)
        self.assertEqual(p['bindings']['Unit.GetType']['callback_rva'],p['bindings']['Unit.GetUnitType']['callback_rva'])
        self.assertEqual(p['ui_resolution']['qualified_attack_handlers_overridden'],False)
        pins = materialize_xp1_session_pins(profile.source_dependencies(), _XP1_PROFILE)
        for path,sha in pins.items():
            with Path(path).open('rb') as stream:
                self.assertEqual(hashlib.file_digest(stream,'sha256').hexdigest(),sha,path)
        sys.path.insert(0,str(LAB/'tools'))
        from extract_phase31_next_export import pefile
        image=pefile.PE(_XP1_PROFILE.path,fast_load=True);self.addCleanup(image.close)
        base=0x190000000
        read=lambda address,size:image.get_data(address-base,size)
        self.assertGreater(profile.verify_live(base,read),0)
        with self.assertRaises(ValueError):profile.verify_live(base,lambda address,size:bytes(size))
        with self.assertRaises(ValueError):profile.verify_source(BASE)

    def test_hook_contract_delegation_and_all_native_calls_forward_engine(self):
        expected_pure={'native_saved_combat':('validate_action','validate_units','verify_observation','validate_relationships'),
                       'native_saved_city_targets':('validate_cities',)}
        cross={'native.verify_source_evidence','native.candidate_source','native.parse_candidates','native.request_source',
               'city_targets.catalog','city_targets.request_source','queued_destination'}
        for name in ('native_combat_actions','native_saved_combat','native_saved_city_targets'):
            tree=ast.parse(transformed(name));functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
            for pure in expected_pure.get(name,()):self.assertNotIn(pure,functions)
            targets=HOOK.TARGETS['civ6rl.'+name]
            for target in targets:
                fn=functions[target];self.assertIn('core_sha256',[a.arg for a in fn.args.kwonlyargs])
                for call in (n for n in ast.walk(fn) if isinstance(n,ast.Call)):
                    if ast.unparse(call.func) in cross or isinstance(call.func,ast.Name) and call.func.id in targets:
                        self.assertEqual([ast.unparse(k.value) for k in call.keywords if k.arg=='core_sha256'],['core_sha256'])
            if name=='native_saved_combat':
                self.assertIn('core_sha256',[a.arg for a in functions['queued_destination'].args.kwonlyargs])
                citations=[(n.arg,ast.unparse(n.value)) for n in ast.walk(functions['apply'])
                           if isinstance(n,ast.keyword) and n.arg in ('queued_source_sha256','source_proof_sha256','city_target_source_sha256')]
                self.assertEqual(len(citations),3)
                self.assertTrue(any('selected_queued_proof' in value for key,value in citations if key=='queued_source_sha256'))
        raw=(LAB/'civ6rl/native_saved_combat.py').read_text().replace("'Malformed own combat state'","'changed contract'")
        with self.assertRaisesRegex(ValueError,'validator differs'):HOOK.parameterize('civ6rl.native_saved_combat',raw)

    def test_base_default_and_xp1_lua_only_differ_by_proven_readiness_without_base_fallback(self):
        with selected_modules() as modules:
            native=modules['native_combat_actions'];combat=modules['native_saved_combat'];cities=modules['native_saved_city_targets']
            candidate=dict(unit_id=17,operation='RANGE_ATTACK',target_owner=1,target_id=9,x=1,y=0)
            with patch.object(profile,'verify_source',side_effect=AssertionError('Base consulted XP1')):
                base_candidate=native.candidate_source(0,7)
                base_request=native.request_source(0,7,candidate,width=3,height=2)
                base_units=combat.unit_state_source(7)
                base_city=cities.source(7)
            # Selecting XP1 must not load the old action/city proof as its ABI.
            with (patch.object(native,'load_pinned_json',side_effect=AssertionError('XP1 loaded Base action ABI')),
                  patch.object(cities,'load_pinned_json',side_effect=AssertionError('XP1 loaded Base city ABI'))):
                self.assertEqual(native.candidate_source(0,7,core_sha256=XP1),
                    base_candidate.replace(b'if unit:IsReadyToSelect()==true then',b'do',1))
                self.assertEqual(native.request_source(0,7,candidate,width=3,height=2,core_sha256=XP1),
                    base_request.replace(b"assert(unit~=nil and unit:IsReadyToSelect()==true,'own combat unit is no longer ready')",
                                         b"assert(unit~=nil,'own combat unit is no longer present')",1))
                self.assertEqual(combat.unit_state_source(7,core_sha256=XP1),base_units)
                self.assertEqual(cities.source(7,core_sha256=XP1),
                    base_city.replace(b'if u:IsReadyToSelect() then',b'do',1))
            with self.assertRaises(ValueError):native.candidate_source(0,7,core_sha256='foreign')

    def test_shared_unit_target_lua_visibility_and_both_ranged_variants(self):
        with selected_modules() as modules:
            native=modules['native_combat_actions']
            prefix=native.build_guard_case(core_sha256=XP1).split(b'local ok,result=pcall(function()',1)[0]
            candidate=dict(unit_id=17,operation='RANGE_ATTACK',target_owner=1,target_id=9,x=1,y=0)
            for modifier in (False,True):
                with self.subTest(modifier=modifier):
                    expected=b'1' if modifier else b'nil'
                    source=prefix+b'\nUnitManager.CanStartOperation=function(u,op,none,p) assert(p.m=='+expected+b'); return true end\n'
                    source+=b'UnitManager.RequestOperation=function(u,op,p) assert(p.m=='+expected+b');submitted=submitted+1 end\n'
                    source+=b'local function collect()\n'+native.candidate_source(0,7,ranged_modifier=modifier,core_sha256=XP1)+b'\nend\n'
                    source+=b'local function request()\n'+native.request_source(0,7,candidate,width=3,height=2,ranged_modifier=modifier,core_sha256=XP1)+b'\nend\n'
                    source+=b"local value=collect();assert(request()=='submitted' and submitted==1 and forbidden==0)\nPlayersVisibility[0].IsUnitVisible=function() return false end\nassert(not pcall(request) and submitted==1);return value"
                    result=native.parse_candidates(LuaRuntime(encoding=None).execute(source),0,7,core_sha256=XP1)
                    self.assertEqual(len(result['candidates']),1)

    def test_shared_city_routes_and_defenses_use_original_lua(self):
        with selected_modules() as modules:
            cities=modules['native_saved_city_targets']
            for route,modifier,ranged in (('dedicated_ranged',None,True),('world_plot',0,True),('world_plot',3,False)):
                with self.subTest(route=route,modifier=modifier):
                    lua=LuaRuntime(encoding=None);lua.execute(city_harness())
                    if not ranged:lua.execute(b'ranged=false')
                    value=cities.parse(lua.execute(cities.source(7,core_sha256=XP1)),7,0)
                    row=next(r for r in value['candidates'] if r['input_route']==route)
                    action=dict(kind='unit_attack',unit_id=17,operation=row['operation'],input_route=route,plot_id=1,x=1,y=0)
                    self.assertEqual(lua.execute(cities.request_source(7,action,value['cities'][0],core_sha256=XP1)),b'submitted')
                    self.assertEqual(lua.globals().submittedModifier,modifier)
                    self.assertEqual(lua.globals().hiddenReads,0)
                    self.assertEqual(lua.globals().requests,1)
                    lua.execute(b'damage=21')
                    with self.assertRaises(Exception):lua.execute(cities.request_source(7,action,value['cities'][0],core_sha256=XP1))
                    self.assertEqual(lua.globals().requests,1)
            for setup in (b'war=false',b'extraWar=true',b'ranged=false;coastal=true',b'ranged=false;swap=true',b'show=false'):
                lua=LuaRuntime(encoding=None);lua.execute(city_harness());lua.execute(setup)
                value=cities.parse(lua.execute(cities.source(7,core_sha256=XP1)),7,0)
                self.assertEqual(value['candidates'],[])
                self.assertEqual(lua.globals().requests,0)

    def test_observed_effect_keeps_native_facts_but_no_change_cannot_use_base_lifecycle(self):
        from civ6_host.runtime.native import native_operation_lifecycle as lifecycle
        with selected_modules() as modules:
            combat=modules['native_saved_combat'];before,units,action=state()
            after=deepcopy(before);after['visible_enemy_units'][0]['damage']=27
            with patch.object(lifecycle,'completed_cycle',side_effect=AssertionError('Base lifecycle invoked')):
                effect=combat.effect(before,after,units,units,action,core_sha256=XP1,delivery_window=object())
                self.assertTrue(effect['observable_native_change'])
                self.assertFalse(effect['selected_defender_claimed'])
                self.assertFalse(effect['death_or_capture_inferred_from_absence'])
                with self.assertRaisesRegex(RuntimeError,'lifecycle-only.*unqualified'):
                    combat.effect(before,before,units,units,action,core_sha256=XP1,delivery_window=object())
            self.assertEqual(profile.selected_proof('old',BASE),'old')
            self.assertEqual(profile.selected_proof('old',XP1),profile.SOURCE[1])
            from civ6_host.runtime.xp1_world_input_profile import SOURCE as queued
            self.assertEqual(profile.selected_queued_proof('old',XP1),queued[1])


class RangedSubmissionTests(unittest.TestCase):
    def test_native_addition_must_match_the_single_selected_ranged_archive(self):
        from civ6_host.runtime import xp2_unit_attack_source as xp2
        from civ6_host.runtime.native.native_operation_lifecycle import DeliveryWindow
        from civ6_host.runtime.native.native_event_15c35863 import (
            EventFields, encode_fields, encode_queue_record,
        )

        action = dict(kind='unit_attack', unit_id=19, operation='RANGE_ATTACK',
                      input_route='dedicated_ranged', plot_id=8, x=2, y=3)
        descriptor = struct.pack('<HHI', 0, 1, 19)
        archive = struct.pack('<IHH9I', 0x8c0f3f36, 0, 1, 19, 26, 0xffffffff, 0, 1, 2, 3, 0, 0)
        added = encode_queue_record(11, encode_fields(EventFields(0, 26, 1, descriptor)),
                                    blob_contents=descriptor, padding_policy='headless-zero-initialization')
        prefix = types.SimpleNamespace(ui_child=object(), runtime=types.SimpleNamespace(
            evaluate_text=lambda *args, **kwargs: b'26'))
        source = xp2._source(xp2.CURRENT_XP2_RANGE_ADDED)
        span = b'test live code'
        source = dict(source, body_spans={'fixture': dict(rva=8, bytes=len(span),
            sha256=hashlib.sha256(span).hexdigest())})
        core = types.SimpleNamespace(_handle=100)
        with patch.object(xp2, '_source', return_value=source):
            def read(window, selected=action):
                return xp2._ranged_submission(window, selected, 0, core, lambda *_: span, prefix)

            window = DeliveryWindow(archive, (added,), 10, 11)
            result = read(window)
            self.assertEqual(result['status'], 'RANGE_ATTACK_added')
            self.assertIsNone(result['operation_success'])
            self.assertFalse(result['combat_resolution_inferred'])
            self.assertIsNone(read(window, dict(action, x=4)))
            self.assertIsNone(read(DeliveryWindow(archive, (), 10, 10)))
            self.assertIsNone(read(DeliveryWindow(archive, (added,), 10, 12)))
            prefix.runtime.evaluate_text = lambda *args, **kwargs: b'27'
            with self.assertRaisesRegex(ValueError, 'selected native operation'):
                read(window)


if __name__=='__main__':unittest.main()

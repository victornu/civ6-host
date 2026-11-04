"""Source/ABI selection fixtures only: no DLL execution or native action claim."""
import ast
import ctypes as C
import importlib.util
from pathlib import Path
import struct
import sys
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from civ6_host.runtime import xp1_research_profile as profile
from civ6_host.runtime import native as native_package

spec=importlib.util.spec_from_file_location('research_extraction',ROOT/'tools/extraction_xp1_research.py')
hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)
BASE=profile.BASE_CORE_SHA256;XP1=profile.XP1_CORE_SHA256


def transformed(name):
    path=ROOT/'src/civ6_host/runtime/native'/f'{name}.py';raw=path.read_text()
    # Tests also run after the parent invokes the common extractor.
    selected=any(isinstance(n,ast.FunctionDef) and n.name in ('verify_source','verify_source_evidence','catalog_source')
        and any(a.arg=='core_sha256' for a in n.args.kwonlyargs) for n in ast.parse(raw).body)
    source=raw if selected else hook.parameterize(name,raw)
    module=ModuleType('civ6_host.runtime.native.'+name);module.__file__=str(path)
    exec(compile(source,str(path)+' <selected-source fixture>','exec'),module.__dict__)
    return module,source


class RequestFixture:
    """Real shared scalar storage algorithm with fixture callables, no DLL."""
    def __init__(self,module,core=XP1):
        self.module=module;self.core=core;self.base=0x25000000000;self.context=0x12345000
        self.abi=profile.player_operation_abi(core,module._METHODS)
        self.memory={};self.buffers={};self.calls=[];self.allowed=1;self.fail_request=False
        self.write(self.context,struct.pack('<Q',self.base+self.abi.outer))
        if core==XP1:
            for body in profile.verify_source()['functions'].values():
                for fragment in body.get('fragments') or (body,):
                    for row in fragment['instructions']:
                        self.write(self.base+int(row['va'],16)-0x180000000,bytes.fromhex(row['bytes']))
        for table,offset,target in self.abi.slots:self.write(self.base+table+offset,struct.pack('<Q',self.base+target))
        def ctor(pointer,vt,name):
            self.calls.append(name);C.memmove(pointer,struct.pack('<Q',self.base+vt),8);return pointer
        def put(pointer,key,value):
            self.calls.append('set');cell=C.create_string_buffer(struct.pack('<H6xI12x',2,value))
            self.buffers[key]=cell;return C.addressof(cell)
        def can(context,pid,op,params,visible,reasons):
            self.calls.append('can');self.legality=(context,pid,op,visible);return self.allowed
        def request(context,pid,op,params):
            self.calls.append('request')
            if self.fail_request:raise RuntimeError('fixture native callback failure')
            return 0
        self.api={'parameter_ctor':lambda p:ctor(p,self.abi.parameters,'parameter_ctor'),
            'parameter_dtor':lambda p:self.calls.append('parameter_dtor'),
            'reason_ctor':lambda p:ctor(p,self.abi.reasons,'reason_ctor'),
            'reason_dtor':lambda p:self.calls.append('reason_dtor'),
            'lookup':lambda p,k:C.addressof(self.buffers[k]) if k in self.buffers else 0,
            'set_u32':put,'can_start':can,'request':request}

    def write(self,address,raw):self.memory.update({address+i:b for i,b in enumerate(raw)})
    def read(self,address,size):
        if not 0<size<=6784:
            raise ValueError('Invalid bounded native inspection request')
        if address in self.memory:return bytes(self.memory[address+i] for i in range(size))
        # Only caller-owned ctypes allocations reach here in this fixture.
        if address>=self.base and address<self.base+0x1000000:raise AssertionError('Uncaptured fixture module read')
        return C.string_at(address,size)
    def invoke(self,**kwargs):
        return self.module.request_player_operation(SimpleNamespace(_handle=self.base),self.context,0,
            1848062833,{347601064:2498335618,2888817673:2550048198},read=self.read,
            native_api=self.api,core_sha256=self.core,**kwargs)


class ResearchProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actions,cls.actions_source=transformed('native_research_actions')
        with patch.dict(sys.modules,{'civ6_host.runtime.native.native_research_actions':cls.actions}):
            cls.catalog,cls.catalog_source=transformed('native_research_catalog')
        cls.request,cls.request_source=transformed('native_player_operation_request')

    def test_exact_sources_and_closure(self):
        p=profile.verify_source();self.assertEqual(len(p['bindings']),6)
        self.assertEqual(set(p['enums']),set(profile.ENUMS))
        pins=profile.source_dependencies();self.assertIn(profile.SOURCE[1],pins.values())
        self.assertFalse(p['base_intervals']['xp1_behavior_proven'])
        self.assertEqual([r['kind'] for r in p['base_intervals']['intervals']],['civic','research'])

    def test_lua_is_byte_identical_for_both_sources_and_replacement_is_not_filtered(self):
        for kind in ('research','civic'):
            self.assertEqual(self.actions.effect_source(0,kind,1),self.actions.effect_source(0,kind,1,core_sha256=XP1))
            self.assertEqual(self.catalog.catalog_source(0,kind,5),self.catalog.catalog_source(0,kind,5,core_sha256=XP1))
        self.assertNotIn(b'GetResearchingTech',self.catalog.catalog_source(0,'research',5,core_sha256=XP1))
        self.assertNotIn(b'GetProgressingCivic',self.catalog.catalog_source(0,'civic',5,core_sha256=XP1))
        for module,names in ((self.actions,('parse_candidate','parse_effect')),(self.catalog,('parse_catalog','choose','parse_revalidated_choice'))):
            historical=Path('../civ6-rl-lab/civ6rl')/(module.__name__.rsplit('.',1)[-1]+'.py')
            original=ast.parse(historical.read_text());selected=ast.parse(self.actions_source if module is self.actions else self.catalog_source)
            for name in names:
                a=next(n for n in original.body if isinstance(n,ast.FunctionDef) and n.name==name)
                b=next(n for n in selected.body if isinstance(n,ast.FunctionDef) and n.name==name)
                self.assertEqual(ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False))

    def test_unknown_core_is_refused_before_native(self):
        with self.assertRaises(ValueError):self.catalog.catalog_source(0,'research',1,core_sha256='unknown')
        with self.assertRaises(ValueError):profile.player_operation_abi('unknown',self.request._METHODS)

    def test_xp1_selected_abi_preserves_shared_algorithm_and_void_semantics(self):
        f=RequestFixture(self.request);result=f.invoke()
        self.assertEqual(f.calls,['parameter_ctor','set','set','reason_ctor','can','request','reason_dtor','parameter_dtor'])
        self.assertEqual(f.legality,(f.context,0,1848062833,False))
        self.assertEqual(result['native_parameter_vtable_rva'],'0x93fe28')
        self.assertEqual(result['source_sha256'],profile.SOURCE[1])
        self.assertTrue(result['request_invoked']);self.assertFalse(result['request_return_interpreted'])
        self.assertFalse(result['gameplay_outcome_verified']);self.assertFalse(result['archive_fabricated'])

    def test_base_default_abi_preserved(self):
        f=RequestFixture(self.request,BASE);result=f.invoke()
        self.assertEqual(result['native_parameter_vtable_rva'],'0x81d838')
        self.assertEqual(result['source_sha256'],profile.BASE_REQUEST_SOURCE)

    def test_false_legality_or_read_only_does_not_submit(self):
        for allowed,submit in ((0,True),(1,False)):
            f=RequestFixture(self.request);f.allowed=allowed;result=f.invoke(submit=submit)
            self.assertFalse(result['request_invoked']);self.assertNotIn('request',f.calls)
            self.assertEqual(f.calls[-2:],['reason_dtor','parameter_dtor'])

    def test_native_callback_failure_still_destroys_both_owned_maps(self):
        f=RequestFixture(self.request);f.fail_request=True
        with self.assertRaisesRegex(RuntimeError,'callback failure'):f.invoke()
        self.assertEqual(f.calls[-2:],['reason_dtor','parameter_dtor'])

    def test_changed_code_or_slot_refused_before_native_calls(self):
        for address in (0x4be350,0x8a8df0+0x218):
            f=RequestFixture(self.request);f.memory[f.base+address]^=1
            with self.assertRaises(ValueError):f.invoke()
            self.assertEqual(f.calls,[])

    def test_live_source_receipt_cannot_cross_owner_or_module_lifetime(self):
        f=RequestFixture(self.request);core=SimpleNamespace(_handle=f.base)
        owner=SimpleNamespace(core=core,load_abi=SimpleNamespace(core_sha256=XP1),check_thread=lambda:None)
        first=profile.bind_owner(owner,core,f.read)
        self.assertIs(profile.bind_owner(owner,core,lambda *a:(_ for _ in ()).throw(AssertionError('unexpected reread'))),first)
        other=SimpleNamespace(core=core,load_abi=owner.load_abi,check_thread=lambda:None,
                              _xp1_research_source_receipt=first)
        with self.assertRaisesRegex(ValueError,'another lifetime'):profile.bind_owner(other,core,f.read)
        core._handle+=0x100000000
        with self.assertRaisesRegex(ValueError,'another lifetime'):profile.bind_owner(owner,core,f.read)

    def test_map_script_hook_preserves_algorithm_and_opt_in_preselected_submission(self):
        raw=(ROOT.parent/'civ6-rl-lab/civ6rl/native_map_script.py').read_text()
        transformed_source=hook.parameterize('native_map_script',raw)
        a=ast.parse(raw);b=ast.parse(transformed_source);calls=[]
        for node in ast.walk(b):
            if isinstance(node,ast.Call):
                extra=[k for k in node.keywords if k.arg=='core_sha256']
                if extra:calls.append(ast.unparse(node.func));node.keywords=[k for k in node.keywords if k.arg!='core_sha256']
        self.assertEqual(sorted(calls),sorted(['catalog_source','effect_source','revalidate_choice_source','request_player_operation']))
        fn=next(n for n in ast.walk(b) if isinstance(n,ast.FunctionDef) and n.name=='inspect_player_research_choice')
        self.assertEqual(fn.args.kwonlyargs[-1].arg,'submit_preselected')
        self.assertIs(fn.args.kw_defaults[-1].value,False)
        fn.args.kwonlyargs.pop();fn.args.kw_defaults.pop()
        guard=next(n for n in fn.body if isinstance(n,ast.If)
                   and ast.unparse(n.test)=="before['confirmed'] and (not submit_preselected)")
        guard.test=ast.parse("before['confirmed']",mode='eval').body
        self.assertEqual(ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False))

    def test_explicit_current_civic_goes_through_native_request_not_diagnostic_shortcut(self):
        from contextlib import ExitStack
        from civ6_host.runtime.explicit_saved_operations import ExplicitSavedOperations
        from unittest.mock import Mock
        emitted=[];pending=[]
        def evaluate(child,source,label,**kwargs):
            return {b'@native_research_turn':b'1',
                b'@native_research_catalog':b'civic,0,1,7,11,12,90,1,0:123',
                b'@native_research_before':b'civic,0,1,0,0',
                b'@native_research_revalidation':b'civic,0,1,0,123,7,11,12,90',
                b'@native_research_after':b'civic,0,1,0,0'}[label]
        def request(*args,**kwargs):
            pending.append(struct.pack('<I',3294486831));return dict(can_start=True,request_invoked=True)
        p=SimpleNamespace(ui_child=object(),core=object(),context=10,operation_core_sha256=XP1,
            runtime=SimpleNamespace(evaluate_text=evaluate),
            actions=SimpleNamespace(pending=pending,deliver_one=lambda:pending.pop()),
            deferred_events=SimpleNamespace(pending=[],drain_empty_receivers=Mock()),
            view_publisher=SimpleNamespace(publish=Mock()),emit=lambda stage,**fields:emitted.append((stage,fields)))
        with ExitStack() as stack:
            stack.enter_context(patch('civ6_host.runtime.xp1_research_profile.verify_source'))
            called=stack.enter_context(patch('civ6_host.runtime.native.native_player_operation_request.request_player_operation',side_effect=request))
            ExplicitSavedOperations.inspect_player_research_choice(p,0,'civic',selected_index=0)
        called.assert_called_once();p.view_publisher.publish.assert_called_once()
        self.assertEqual(emitted[-1][0],'native_player_research_effect_verified')
        self.assertFalse(any(s=='native_player_research_preselected_observed' for s,_ in emitted))

if __name__=='__main__':unittest.main()

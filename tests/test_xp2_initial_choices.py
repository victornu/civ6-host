"""XP2 initial-choice source/owner/ABI fixtures; no DLL or gameplay execution."""
import ast
import copy
import ctypes as C
from pathlib import Path
import struct
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_initial_choice_source as selected
from civ6_host.runtime import xp1_status_profiles as status,xp1_research_profile as research,xp1_production_profile as production
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256 as XP2,XP1_CORE_SHA256 as XP1
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.native import native_research_actions as actions,native_research_catalog as catalog
from civ6_host.runtime.native import native_production_catalog as production_catalog,native_city_production_observation as queues
import extraction_xp1_research as hook
import test_xp1_research_profile as prior

ROOT=Path(__file__).resolve().parents[1]


def selected_request():
    path=ROOT.parent/'civ6-rl-lab/civ6rl/native_player_operation_request.py'
    raw=path.read_text(encoding='utf-8')
    rendered=hook.parameterize('civ6rl.native_player_operation_request',raw)
    # Only import namespace relocation, as in extraction; no helper replacement.
    rendered=rendered.replace('from civ6rl.','from civ6_host.runtime.native.')
    module=ModuleType('civ6_host.runtime.native._xp2_request_fixture');module.__file__=str(path);module.__package__='civ6_host.runtime.native'
    exec(compile(rendered,str(path)+' <selected XP2 hook>','exec'),module.__dict__)
    return module,rendered


def populate(write,base,p):
    for b in p['functions'].values():
        for f in b['fragments']:write(base+int(f['start_rva'],16),bytes.fromhex(f['raw_hex']))
    for table,offset,target in selected.SLOTS:write(base+table+offset,struct.pack('<Q',base+target))
    for name,b in p['bindings'].items():write(base+b['name_rva'],name.split('.')[1].encode()+b'\0')
    for address,b in p['literals'].items():write(base+int(address,16),bytes.fromhex(b['raw_hex']))
    for name,b in p['enums'].items():write(base+b['name_rva'],name.split('.')[1].encode()+b'\0')


class InitialChoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=selected.source('status');cls.request,cls.rendered=selected_request()

    def fixture(self):
        f=prior.RequestFixture(self.request,XP2);populate(f.write,f.base,self.proof);return f

    def owner(self,f):
        # Actual backend class and check_thread, with only runtime/memory replaced.
        owner=OfficialLoadBackend.__new__(OfficialLoadBackend)
        owner.core=SimpleNamespace(_handle=f.base)
        owner.load_abi=SimpleNamespace(core_sha256=XP2)
        owner.thread=(11,19);owner.runtime=SimpleNamespace(thread=lambda:owner.thread)
        owner.poisoned=owner.destroyed=False
        return owner

    def test_exact_named_families_complete_functions_slots_and_dependencies(self):
        self.assertEqual({k:len(v) for k,v in selected.CALLBACKS.items()},dict(status=19,research=6,production=27))
        for module in (status,research,production):
            self.assertEqual(module.source_reference(XP2),selected.SOURCE)
            self.assertEqual(module.verify_source(XP2)['image']['sha256'],XP2)
        self.assertEqual(self.proof['validation']['function_count'],304)
        self.assertGreater(sum(len(b['fragments']) for b in self.proof['functions'].values()),304)
        pins=status.source_dependencies(XP2)
        self.assertIn(selected.SOURCE[1],pins.values())
        self.assertTrue(any('xp2-ui-binding-static' in name for name in pins))
        self.assertTrue(set(pins.items())<=set(research.source_dependencies(XP2).items()))
        self.assertTrue(any('xp2-action-transport' in name for name in production.source_dependencies(XP2)))

    def test_no_xp1_fallback_and_exact_ctypes_arguments(self):
        abi=research.player_operation_abi(XP2,self.request._METHODS)
        self.assertEqual((abi.outer,abi.parameters,abi.reasons),(0xa101e8,0xabf918,0xabf080))
        self.assertEqual({k:v[0] for k,v in abi.methods.items()},selected.ENTRIES)
        for name,value in abi.methods.items():self.assertEqual(value[1:],self.request._METHODS[name][1:])
        self.assertIsNone(abi.methods['request'][1]);self.assertIs(abi.methods['can_start'][1],C.c_uint8)
        for module in (status,research,production):
            self.assertEqual(module.source_reference(),module.SOURCE)
            with self.assertRaises(ValueError):module.verify_source('unknown')
            with self.assertRaises(ValueError):module.verify_live(0x180000000,lambda *a:None,core_sha256='unknown')
            with self.assertRaises(ValueError):module.source_dependencies('unknown')

    def test_real_shared_request_returns_submission_only_then_destroys_owned_maps(self):
        f=self.fixture();result=f.invoke()
        self.assertEqual(f.calls,['parameter_ctor','set','set','reason_ctor','can','request','reason_dtor','parameter_dtor'])
        self.assertEqual(f.legality,(f.context,0,1848062833,False))
        self.assertEqual(result['source_sha256'],selected.SOURCE[1])
        self.assertEqual(result['native_parameter_vtable_rva'],'0xabf918')
        self.assertTrue(result['request_invoked'])
        for flag in ('request_return_interpreted','gameplay_outcome_verified','archive_fabricated','eligible_for_training'):
            self.assertFalse(result[flag])

    def test_false_legality_and_read_only_never_submit(self):
        for allowed,submit in ((0,True),(1,False)):
            f=self.fixture();f.allowed=allowed;result=f.invoke(submit=submit)
            self.assertFalse(result['request_invoked']);self.assertNotIn('request',f.calls)
            self.assertEqual(f.calls[-2:],['reason_dtor','parameter_dtor'])

    def test_callback_failure_always_releases_both_maps(self):
        f=self.fixture();f.fail_request=True
        with self.assertRaisesRegex(RuntimeError,'callback failure'):f.invoke()
        self.assertEqual(f.calls[-2:],['reason_dtor','parameter_dtor'])

    def test_instruction_tail_slot_and_native_name_changes_refuse_before_calls(self):
        b=self.proof['functions']['0x9a5d50'];last=b['fragments'][-1]
        addresses=[int(last['start_rva'],16)+last['length']-1,0xabf918+0x130,
                   self.proof['bindings']['BuildQueue.CanProduce']['name_rva']]
        for rva in addresses:
            f=self.fixture();f.memory[f.base+rva]^=1
            with self.subTest(rva=hex(rva)),self.assertRaises(ValueError):f.invoke()
            self.assertEqual(f.calls,[])

    def test_variant_and_storage_guards_use_real_shared_algorithm(self):
        f=self.fixture();put=f.api['set_u32']
        def bad_variant(*args):
            ptr=put(*args);C.memmove(ptr,struct.pack('<H',3),2);return ptr
        f.api['set_u32']=bad_variant
        with self.assertRaisesRegex(RuntimeError,'DWORD input'):f.invoke()
        self.assertEqual(f.calls[-1],'parameter_dtor');self.assertNotIn('request',f.calls)
        f=self.fixture();ctor=f.api['parameter_ctor']
        def overflow(ptr):
            result=ctor(ptr);C.memset(ptr+72,0,1);return result
        f.api['parameter_ctor']=overflow
        with self.assertRaisesRegex(RuntimeError,'source-sized storage'):f.invoke()
        self.assertNotIn('can',f.calls)

    def test_real_backend_owner_source_receipts_cannot_cross_lifetimes(self):
        f=self.fixture();owner=self.owner(f)
        for module,attr in ((status,'_xp1_status_source_receipt'),(research,'_xp1_research_source_receipt'),(production,'_xp1_production_source_receipt')):
            receipt=module.bind_owner(owner,owner.core,f.read)
            self.assertEqual(receipt.source_sha256,selected.SOURCE[1])
            self.assertIs(module.bind_owner(owner,owner.core,lambda *a:(_ for _ in ()).throw(AssertionError('reread'))),receipt)
            foreign=self.owner(f);foreign.core=owner.core;setattr(foreign,attr,receipt)
            with self.assertRaisesRegex(ValueError,'another lifetime'):module.bind_owner(foreign,foreign.core,f.read)
        owner.poisoned=True
        with self.assertRaisesRegex(RuntimeError,'poisoned'):status.bind_owner(owner,owner.core,f.read)

    def test_shared_collectors_are_byte_identical_after_source_selection(self):
        for kind in ('research','civic'):
            self.assertEqual(catalog.catalog_source(0,kind,1,core_sha256=XP1),catalog.catalog_source(0,kind,1,core_sha256=XP2))
            self.assertEqual(actions.effect_source(0,kind,1,core_sha256=XP1),actions.effect_source(0,kind,1,core_sha256=XP2))
        self.assertEqual(production_catalog.catalog_source(0,65536,1,replace_current=True,core_sha256=XP1),
                         production_catalog.catalog_source(0,65536,1,replace_current=True,core_sha256=XP2))
        self.assertEqual(queues.production_snapshot_source(0,core_sha256=XP1),queues.production_snapshot_source(0,core_sha256=XP2))
        payload=b'production-v1|0|5|4|catalog|3|7|12|90|13|11|14|15|16|3|unit:UNIT_SETTLER:22:99|building:BUILDING_GRANARY:0:100|project:PROJECT_TEST:0:103'
        choice=production_catalog.choose(production_catalog.parse_catalog(payload,0,5,4),'unit',22)
        self.assertEqual(production_catalog.request_source(choice,replace_current=True,core_sha256=XP1),
                         production_catalog.request_source(choice,replace_current=True,core_sha256=XP2))

    def test_hook_forwards_exact_engine_to_live_guard(self):
        tree=ast.parse(self.rendered)
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='verify_live']
        self.assertEqual(len(calls),1)
        self.assertEqual([(k.arg,ast.unparse(k.value)) for k in calls[0].keywords],[('core_sha256','core_sha256')])

if __name__=='__main__':unittest.main()

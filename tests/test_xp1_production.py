"""Static source and extraction fixtures only; no GameCore execution."""
import ast
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HOST=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HOST/'src'));sys.path.insert(0,str(HOST/'tools'))
from extraction_xp1_production import parameterize
from civ6_host.runtime import xp1_production_profile as profile
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, BASE_CORE_SHA256
from civ6_host.runtime.xp1_status_profiles import _instruction_spans
from civ6_host.runtime.native import native_production_catalog as catalog
from civ6_host.runtime.native import native_city_production_observation as observation
from civ6_host.runtime.native import native_saved_actions as actions


def namespace(module, name):
    raw=Path(module.__file__).read_text(encoding='utf-8')
    tree=ast.parse(raw)
    target=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verify_source')
    if any(a.arg=='core_sha256' for a in target.args.kwonlyargs):
        return module.__dict__,raw,None
    transformed=parameterize(name,raw);result={'__name__':'_production_extraction_fixture'}
    exec(compile(transformed,'<production-extraction>','exec'),result)
    return result,raw,transformed


class SourceProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=profile.verify_source()
        cls.spans=_instruction_spans(cls.proof)

    def reader(self, base, *, corrupt=None):
        memory={}
        for rva,raw in self.spans:
            for i,value in enumerate(raw):memory[base+rva+i]=value
        table,entries=profile.CITY_MESSAGE
        data=b''.join((base+v).to_bytes(8,'little') for v in entries)
        for i,value in enumerate(data):memory[base+table+i]=value
        for name,row in self.proof['bindings'].items():
            address=base+int(row['name_va'],16)-0x180000000
            for i,value in enumerate(name.split('.')[1].encode()+b'\0'):memory[address+i]=value
        if corrupt is not None:memory[base+corrupt]^=1
        return Mock(side_effect=lambda address,size:bytes(memory[address+i] for i in range(size)))

    def test_exact_bindings_and_native_city_archive(self):
        self.assertEqual(len(self.proof['bindings']),27)
        self.assertEqual(self.proof['image']['sha256'],XP1_CORE_SHA256)
        ctor=self.proof['functions']['0x2af50']['instructions']
        self.assertTrue(any(row['text']=='mov dword ptr [rcx + 8], 0x7ce9adc2' for row in ctor))
        self.assertEqual(ctor[-1]['text'],'ret')
        self.assertIn('PROD_QUEUE',self.proof['contracts']['current_item'])
        with self.assertRaises(ValueError):profile.verify_source(BASE_CORE_SHA256)

    def test_live_guards_are_coalesced_and_relocation_aware(self):
        base=0x7ff700000000
        read=self.reader(base)
        self.assertEqual(profile.verify_live(base,read),len(self.spans))
        self.assertLess(read.call_count,150)
        self.assertGreater(len(profile.source_dependencies()),18)

    def test_mutated_instruction_table_and_name_are_refused(self):
        base=0x180000000
        first=next(iter(self.proof['bindings'].values()))
        for changed in (self.spans[0][0],profile.CITY_MESSAGE[0],int(first['name_va'],16)-base):
            with self.subTest(changed=hex(changed)),self.assertRaises(ValueError):
                profile.verify_live(base,self.reader(base,corrupt=changed))

    def test_owner_receipt_caches_source_only_and_rejects_foreign_lifetime(self):
        core=SimpleNamespace(_handle=0x180000000)
        owner=SimpleNamespace(core=core,load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),check_thread=Mock())
        read=self.reader(core._handle)
        with patch('civ6_host.runtime.xp1_status_profiles.bind_owner'):
            first=profile.bind_owner(owner,core,read);count=read.call_count
            self.assertIs(profile.bind_owner(owner,core,read),first)
            self.assertEqual(read.call_count,count)
            owner.core=SimpleNamespace(_handle=core._handle)
            with self.assertRaises(ValueError):profile.bind_owner(owner,owner.core,read)


class ExtractionTests(unittest.TestCase):
    def test_lua_and_parsers_are_shared_with_explicit_engine_selection(self):
        cat,old_cat,new_cat=namespace(catalog,'civ6rl.native_production_catalog')
        obs,old_obs,new_obs=namespace(observation,'civ6rl.native_city_production_observation')
        payload=b'production-v1|0|5|4|catalog|3|7|12|90|13|11|14|15|16|3|unit:UNIT_SETTLER:22:99|building:BUILDING_GRANARY:0:100|project:PROJECT_TEST:0:103'
        parsed=cat['parse_catalog'](payload,0,5,4)
        choice=cat['choose'](parsed,'unit',22)
        # Patch only evidence lookup, not the selected Lua or parser algorithm.
        with patch('civ6_host.runtime.xp1_production_profile.verify_source') as xp1:
            base_cat=cat['verify_source'];base_replace=cat['verify_replacement_source'];base_obs=obs['verify_source']
            cat['verify_source']=Mock();cat['verify_replacement_source']=Mock();obs['verify_source']=Mock()
            try:
                original=(cat['catalog_source'](0,5,4,replace_current=True),
                          cat['request_source'](choice,replace_current=True),
                          obs['production_snapshot_source'](0))
            finally:
                cat['verify_source']=base_cat;cat['verify_replacement_source']=base_replace;obs['verify_source']=base_obs
            actual=(cat['catalog_source'](0,5,4,replace_current=True,core_sha256=XP1_CORE_SHA256),
                    cat['request_source'](choice,replace_current=True,core_sha256=XP1_CORE_SHA256),
                    obs['production_snapshot_source'](0,core_sha256=XP1_CORE_SHA256))
            self.assertEqual(actual,original)
            self.assertEqual(xp1.call_count,5)
            for call in xp1.call_args_list:self.assertEqual(call.args,(XP1_CORE_SHA256,))
        self.assertIn(b'queue:CanProduce(input,true)',actual[0])
        self.assertIn(b'queue:CanProduce(input,false,true)',actual[0])
        self.assertIn(b'CityManager.RequestOperation',actual[1])
        for old,new,unchanged in ((old_cat,new_cat,('parse_catalog','choose','_validate_choice')),
                                  (old_obs,new_obs,('parse_production_snapshot','diff_production_observations'))):
            if new is None:continue
            before={n.name:ast.dump(n) for n in ast.parse(old).body if isinstance(n,ast.FunctionDef)}
            after={n.name:ast.dump(n) for n in ast.parse(new).body if isinstance(n,ast.FunctionDef)}
            for name in unchanged:self.assertEqual(before[name],after[name])
        with self.assertRaises(ValueError):cat['catalog_source'](0,5,4,core_sha256='f'*64)

    def test_ordinary_execution_delegates_once_and_placements_remain(self):
        raw=Path(actions.__file__).read_text(encoding='utf-8')
        if 'from civ6_host.runtime.explicit_production_operation import apply' in raw:
            tree=ast.parse(raw)
        else:tree=ast.parse(parameterize('civ6rl.native_saved_actions',raw))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_apply_choice_without_context')
        delegated=[n for n in ast.walk(fn) if isinstance(n,ast.Call)
                   and isinstance(n.func,ast.Name) and n.func.id=='apply_production']
        self.assertEqual(len(delegated),1)
        self.assertEqual(ast.unparse(delegated[0]),'apply_production(owner, p, action, turn, player_id=pid)')
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
            and isinstance(n.func.value,ast.Name) and n.func.value.id=='production'
            and n.func.attr in ('catalog_source','request_source') for n in ast.walk(fn)))
        placements=[n for n in ast.walk(fn) if isinstance(n,ast.Call)
                    and isinstance(n.func,ast.Name) and n.func.id=='apply_placement']
        self.assertEqual(len(placements),1)
        self.assertEqual(ast.unparse(placements[0]),
                         'apply_placement(owner, p, action, turn, current, player_id=pid)')
        # This historical Base entry keeps its default engine. The selected
        # helper forwards the explicit engine through every nested operation.
        helper=ast.parse((HOST/'src/civ6_host/runtime/explicit_production_operation.py').read_text())
        placed=next(n for n in helper.body if isinstance(n,ast.FunctionDef) and n.name=='apply_placement')
        calls=[n for n in ast.walk(placed) if isinstance(n,ast.Call)]
        expected=['placed.selected','placed.placement.request_source','placed.item_progress',
                  'placed.item_progress','placed.progress','placed.progress',
                  'queues.production_snapshot_source','queues.production_snapshot_source',
                  'placed.placement.effect_source']
        selected=[n for n in calls if ast.unparse(n.func) in set(expected)]
        self.assertEqual(sorted(ast.unparse(n.func) for n in selected),sorted(expected))
        for call in selected:
            self.assertEqual([(k.arg,ast.unparse(k.value)) for k in call.keywords if k.arg=='core_sha256'],
                             [('core_sha256','core_sha256')])
        self.assertEqual(sum(ast.unparse(n.func)=='p.actions.deliver_one' for n in calls),1)
        self.assertEqual(sum(ast.unparse(n.func)=='p.view_publisher.publish' for n in calls),1)

    def test_hook_does_not_change_unrelated_module(self):
        self.assertEqual(parameterize('unrelated','unchanged'),'unchanged')


if __name__=='__main__':unittest.main()

"""Actual source bytes and saved-owner guards; no native execution."""
from dataclasses import replace
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'work/python-deps'))
import pefile
from civ6_host.runtime import xp2_production_placement_source as placement
from civ6_host.runtime import xp2_placement_inventory_source as inventory
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as XP1, XP2_CORE_SHA256 as XP2, _copy


class PlacementSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=placement.verify_source();cls.inventory=inventory.verify_source()
        raw=Path(cls.proof['image']['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=XP2:raise AssertionError('Independent PE identity differs')
        pe=pefile.PE(data=raw);cls.base=pe.OPTIONAL_HEADER.ImageBase
        cls.image=pe.get_memory_mapped_image();pe.close()

    def reader(self,mutation=None):
        reads=[]
        def read(address,size):
            self.assertTrue(0<size<=4096)
            start=address-self.base;self.assertTrue(0<=start<start+size<=len(self.image))
            raw=self.image[start:start+size];reads.append((start,size))
            if mutation is not None and start<=mutation<start+size:
                off=mutation-start;raw=raw[:off]+bytes([raw[off]^1])+raw[off+1:]
            return raw
        return read,reads

    def graph(self):
        import test_xp2_production_queue_source as fixture
        from civ6_host.runtime import xp2_world_input_source as world
        from civ6_host.runtime import xp2_action_transport_source as operation
        setup=fixture.QueueSourceTests();setup.proof=fixture.profile.verify_source();setup.base=self.base
        self.addCleanup(setup.doCleanups)
        f,b,c=setup.graph()
        # Keep the actual continuation/publication/lease; put independent PE
        # bytes at the live source addresses, retaining dynamic fixture memory.
        for proof in (self.proof,self.inventory,world.verify_source(),operation.source()):
            for body in proof['functions'].values():
                for frag in body.get('fragments',()):
                    start=frag.get('start_rva')
                    if start is not None:
                        rva=int(start,16);raw=bytes.fromhex(frag['raw_hex'])
                        f.put(f.core_base+rva,self.image[rva:rva+len(raw)])
                for row in body.get('instructions',()):
                    rva=int(row.get('va',hex(self.base+int(row.get('rva','0'),16))),16)-self.base
                    raw=bytes.fromhex(row['bytes']);f.put(f.core_base+rva,self.image[rva:rva+len(raw)])
            for name,row in proof.get('bindings',{}).items():
                if 'name_va' in row:
                    rva=int(row['name_va'],16)-self.base
                    raw=name.split('.')[-1].encode()+b'\0';f.put(f.core_base+rva,self.image[rva:rva+len(raw)])
            for row in proof.get('embedded_tables',{}).values():
                rva=int(row['rva'],16);f.put(f.core_base+rva,self.image[rva:rva+row['length']])
        p=world.verify_source()['data']['plot_type_name']
        rva=int(p['rva'],16);f.put(f.core_base+rva,p['text'].encode()+b'\0')
        enums=placement.enum_source()
        for entry in (*enums['owners'].values(),*enums['enums'].values()):
            rva=entry['name_rva'];raw=bytes.fromhex(entry['name_raw_hex'])
            f.put(f.core_base+rva,self.image[rva:rva+len(raw)])
        return f,b,c

    def test_actual_pe_registration_and_all_fragments_in_bounded_reads(self):
        read,reads=self.reader()
        placement.verify_live(self.base,read);inventory.verify_live(self.base,read)
        self.assertEqual(len(self.proof['bindings']),11)
        self.assertEqual(len(self.inventory['bindings']),24)
        self.assertEqual(len(self.inventory['functions']),11)
        self.assertIn((0x1B2E0+4096,145),reads)
        for name,b in self.proof['bindings'].items():
            address=int(b['callback_reference_va'],16);raw=read(address,7)
            self.assertEqual(raw[:3],bytes.fromhex('488d15'))
            self.assertEqual(address+7+int.from_bytes(raw[3:],'little',signed=True),self.base+placement.CALLBACKS[name])
        covered={rva+i for rva,n in reads for i in range(n)}
        for proof in (self.proof,self.inventory):
            for body in proof['functions'].values():
                for frag in body['fragments']:
                    rva=int(frag['start_rva'],16)
                    self.assertTrue(all(rva+i in covered for i in range(frag['length'])))

    def test_second_chunk_return_tails_and_service_contract_mutations_refuse(self):
        for rva in (0x1C370,0x717A2,0x5E759,0x6BD95,0x6919C8,0x1B02B4,0xD9D3,0x5B0A92,0xA15478):
            with self.subTest(rva=hex(rva)),self.assertRaises(ValueError):
                placement.verify_live(self.base,self.reader(rva)[0])
        for rva in (0x1B02B4,0x1B05D4,0x714EB):
            with self.subTest(inventory=hex(rva)),self.assertRaises(ValueError):
                inventory.verify_live(self.base,self.reader(rva)[0])
        for mod in (placement,inventory):
            for bad in (lambda a,n:b'',lambda a,n:memoryview(self.image[a-self.base:a-self.base+n])):
                with self.assertRaises(ValueError):mod.verify_live(self.base,bad)

    def test_source_semantics_not_only_hash_or_symbol_names(self):
        for mod in (placement,inventory):
            with self.assertRaises(ValueError):mod.verify_source(XP1)
            with patch.object(mod,'SOURCE',(mod.SOURCE[0],'0'*64)):
                with self.assertRaises((RuntimeError,ValueError)):mod.verify_source()
        original=placement._source
        for mutation in ('registration','service','completion','sentinel'):
            p=_copy(self.proof)
            if mutation=='registration':p['bindings']['Plot.GetWonderType']['callback_rva']='0x1c5a0'
            else:
                body,at,text={'service':(0x691840,0x6919C8,'call qword ptr [r10 + 0xb0]'),
                    'completion':(0x716C0,0x71701,'movzx eax, byte ptr [rax + 0x35]'),
                    'sentinel':(0x5E720,0x5E759,'xor eax, eax')}[mutation]
                b=p['functions'][hex(body)]
                for rows in (b['instructions'],*[f['instructions'] for f in b['fragments']]):
                    for r in rows:
                        if r['rva']==hex(at):r['text']=text
            with self.subTest(mutation=mutation),patch.object(placement,'_source',side_effect=lambda r:p if r==placement.SOURCE else original(r)):
                with self.assertRaises(ValueError):placement.verify_source()

    def test_actual_saved_owner_joins_sources_and_refuses_foreign_lifetime(self):
        f,b,c=self.graph()
        with self.assertRaises(ValueError):placement.gate_admitted(c)
        receipt=inventory.bind_owner(b,b.core,b.runtime.read)
        self.assertIs(receipt.placement_receipt,b._xp2_production_placement_source_receipt)
        self.assertIs(receipt.placement_receipt.queue_receipt,b._xp2_production_queue_source_receipt)
        self.assertIs(receipt.placement_receipt.world_receipt,b._xp2_world_input_source_receipt)
        self.assertTrue(placement.gate_admitted(c))
        self.assertIs(inventory.bind_owner(b,b.core,b.runtime.read),receipt)
        b._xp2_placement_inventory_source_receipt=replace(receipt,placement_receipt=object())
        with self.assertRaises(ValueError):inventory.bind_owner(b,b.core,b.runtime.read)
        b._xp2_placement_inventory_source_receipt=receipt
        q=b._xp2_production_queue_source_receipt
        b._xp2_production_queue_source_receipt=replace(q,inputs=replace(q.inputs))
        with self.assertRaises(ValueError):inventory.bind_owner(b,b.core,b.runtime.read)
        b._xp2_production_queue_source_receipt=q
        b.poisoned=True
        with self.assertRaises((ValueError,RuntimeError)):inventory.bind_owner(b,b.core,b.runtime.read)

    def test_composed_native_helper_mutation_never_installs_inventory_receipt(self):
        f,b,c=self.graph()
        f.memory[f.core_base+0x717A2]^=1
        with self.assertRaises(ValueError):inventory.bind_owner(b,b.core,b.runtime.read)
        self.assertFalse(hasattr(b,'_xp2_placement_inventory_source_receipt'))
        self.assertFalse(hasattr(b,'_xp2_production_placement_source_receipt'))

    def test_pin_closure_and_official_xp2_route_preserve_limits(self):
        pins=inventory.source_dependencies()
        for mod in (placement,inventory):self.assertIn(mod.SOURCE[1],pins.values())
        self.assertIn(placement.ENUM_SOURCE[1],pins.values())
        self.assertTrue(any('xp2-aux-map' in name for name in pins))
        self.assertTrue(any('xp2-gs-lan-rows-20261102-04' in name for name in pins))
        for path,digest in pins.items():self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)
        self.assertFalse(self.proof['contracts']['effects_admitted'])
        self.assertEqual(self.proof['services']['map_output']['slot'],'0xa8')
        self.assertFalse(self.inventory['facts']['district_complete']['nonnegative_plot_argument_checks_type'])
        self.assertEqual(self.inventory['facts']['wonder_type_absent']['value_kind'],'GameInfo.Buildings.Index')
        self.assertFalse(self.inventory['read_contract']['placement_turn_inferred'])

    def test_native_enum_namespace_value_and_full_body_reference(self):
        proof=placement.enum_source();original=placement._source
        self.assertEqual(placement.ENUMS,{'CityOperationTypes.PARAM_X':0x53777B05,
            'CityOperationTypes.PARAM_Y':0x4A6C4A44,'CityOperationResults.PLOTS':0x7341AB55})
        for mutation in ('value','namespace','name'):
            p=_copy(proof);entry=p['enums']['CityOperationResults.PLOTS']
            if mutation=='value':entry['u32_value']=0
            elif mutation=='namespace':entry['site_rva']=0x5AFE39 # Same name, wrong owner.
            else:entry['name_raw_hex']=(b'PLOTS_BAD\0').hex()
            with self.subTest(mutation=mutation),patch.object(placement,'_source',side_effect=lambda r:p if r==placement.ENUM_SOURCE else original(r)):
                with self.assertRaises(ValueError):placement.enum_source()


if __name__=='__main__':unittest.main()

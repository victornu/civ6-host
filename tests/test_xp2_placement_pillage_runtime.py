"""Pillage inventory checks against the pinned PE and bounded getter doubles."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pefile
import test_xp1_placement_inventory as fixture

from civ6_host.contracts import placement_inventory as contract
from civ6_host.runtime import placement_inventory as collector
from civ6_host.runtime import placement_inventory_profile as shared
from civ6_host.runtime import xp2_placement_inventory_source as profile
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as XP1, XP2_CORE_SHA256 as XP2
from civ6_host.runtime.execution_images import _PROFILE
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.resource_resolution import resolve_path
from civ6_host.runtime.paths import resource_root


_PILLAGE_GETTERS=r'''
state.pillageCalls={}
plots[1].pillaged=false
plots[3].pillaged=true
for _,city in pairs(cities) do
 local build=city.GetDistricts
 city.GetDistricts=function()
  local districts=build()
  districts.IsPillaged=function(_,kind,plotIndex)
   local plot=plots[plotIndex]
   assert(plot and plot.owner==0 and plot.city==city.id and plot.district==kind and
          not state.hidden[plotIndex] and not state.unrevealed[plotIndex],
          'pillage read outside its direct own visible placement')
   state.pillageCalls[#state.pillageCalls+1]={kind,plotIndex}
   if state.afterPillage then state.afterPillage() end
   return plot.pillaged
  end
  return districts
 end
end
'''


class XP2PlacementPillageTests(unittest.TestCase):
    def new_fixture(self,*,indices_differ=False):
        f=fixture.Fixture()
        f.lua.execute(_PILLAGE_GETTERS)
        if indices_differ:
            f.lua.execute("GameInfo.Districts[1].Index=6;GameInfo.Districts[6]=GameInfo.Districts[1];"
                          "plots[1].district=6")
        return f

    def collect(self,f,*,include_pillage=True):
        source=collector.readback_source(0,42,f.observation,core_sha256=XP2,
                                         include_pillage=include_pillage)
        payload=f.evaluate_text(f.child,source,b'@native_placement_inventory',capacity=5760)
        return payload,collector.parse_readback(payload,0,42,f.observation,
                                                include_pillage=include_pillage)

    def test_native_type_and_plot_arguments_preserve_complete_and_exact_legacy(self):
        f=self.new_fixture(indices_differ=True)
        _,details=self.collect(f)
        self.assertEqual(details['schema'],contract.DETAILS_SCHEMA)
        self.assertEqual([(row['plot_id'],row['complete'],row['pillaged']) for row in details['rows']],
            [(2,False,None),(9,False,None),(1,False,False),(4,True,None),(3,True,True)])
        self.assertEqual([(f.lua.eval(f'state.pillageCalls[{i}][1]'),
                           f.lua.eval(f'state.pillageCalls[{i}][2]')) for i in (1,2)],[(6,1),(3,3)])
        self.assertEqual(f.lua.eval('#state.pillageCalls'),2)
        _,legacy=self.collect(f,include_pillage=False)
        self.assertEqual(f.lua.eval('#state.pillageCalls'),2)
        self.assertEqual(legacy,contract.project_legacy(details,0,42,observation=f.observation))

    def test_reread_scope_and_result_type_refuse_before_publication(self):
        for mutation,count in (
            ('state.hidden[1]=true',0),
            ('plots[1].city=17',0),
            ('state.afterComplete=function() state.hidden[1]=true end',0),
            ('state.afterComplete=function() plots[1].owner=1 end',0),
            ('state.afterComplete=function() plots[1].id=88 end',0),
            ('state.afterPillage=function() plots[1].district=3 end',1),
            ('plots[1].pillaged=0',1),
            ('plots[1].pillaged=nil',1),
            ('cities[5].GetDistricts=function() return {IsComplete=function()return false end} end',0),
        ):
            f=self.new_fixture()
            f.lua.execute(mutation)
            with self.subTest(mutation=mutation):
                with self.assertRaises(Exception):
                    self.collect(f)
                self.assertEqual(f.lua.eval('#state.pillageCalls'),count)

    def test_wire_version_and_categories_cannot_substitute_unknown_for_pillage(self):
        f=self.new_fixture()
        raw,_=self.collect(f)
        lines=raw.split(b'\n')
        for offset,suffix in ((1,b'|0'),(3,b'|-'),(3,b'|true')):
            wrong=lines.copy()
            wrong[offset]=wrong[offset].rsplit(b'|',1)[0]+suffix
            with self.subTest(offset=offset,suffix=suffix),self.assertRaises(ValueError):
                collector.parse_readback(b'\n'.join(wrong),0,42,f.observation,include_pillage=True)
        with self.assertRaises(ValueError):
            collector.parse_readback(raw,0,42,f.observation)
        legacy,_=self.collect(f,include_pillage=False)
        with self.assertRaises(ValueError):
            collector.parse_readback(legacy,0,42,f.observation,include_pillage=True)

    def test_canonical_image_closure_and_independent_live_spans(self):
        self.assertEqual(shared.source_reference(XP2,include_pillage=True),profile.PILLAGE_SOURCE)
        with self.assertRaises(ValueError):
            shared.source_reference(XP1,include_pillage=True)
        with self.assertRaises(ValueError):
            shared.source_reference(XP2,include_pillage=1)
        with self.assertRaises(ValueError):
            shared.source_dependencies(XP2,include_pillage=True)
        proof=Path(resolve_path(resource_root()/profile.PILLAGE_SOURCE[0])).resolve()
        pins=shared.source_dependencies(XP2,execution_image=_PROFILE,include_pillage=True)
        self.assertEqual(pins[str(proof)],profile.PILLAGE_SOURCE[1])
        self.assertEqual(pins[str(Path(_PROFILE.path).resolve())],_PROFILE.image_sha256)
        pe=pefile.PE(str(resolve_path(_PROFILE.path)),fast_load=True)
        self.addCleanup(pe.close)
        base=pe.OPTIONAL_HEADER.ImageBase
        self.assertEqual(profile.verify_pillage_live(base,lambda address,size:pe.get_data(address-base,size)),10)
        for target in (0x68ea43,0x68eea0,0xa2f938):
            def damaged(address,size):
                start=address-base
                raw=pe.get_data(start,size)
                if start <= target < start+size:
                    index=target-start
                    return raw[:index]+bytes([raw[index]^1])+raw[index+1:]
                return raw
            with self.subTest(target=target),self.assertRaises(ValueError):
                profile.verify_pillage_live(base,damaged)

    def test_read_needs_bound_profile_before_evaluating_lua(self):
        f=self.new_fixture()
        backend=OfficialLoadBackend.__new__(OfficialLoadBackend)
        backend.check_thread=lambda:None
        backend.destroyed=False
        backend.poisoned=False
        backend.core=SimpleNamespace(_handle=0x180000000,_civ6_host_execution_image=_PROFILE)
        backend.load_abi=SimpleNamespace(core_sha256=XP2)
        def evaluate(child, source, name, *, capacity):
            if name==b'@native_placement_inventory':
                return f.evaluate_text(child, source, name, capacity=capacity)
            self.assertIs(child,f.child)
            self.assertEqual((name,capacity),(b'@native_own_city_building',256))
            raw=f.lua.execute(source.decode('ascii')).encode('ascii')
            self.assertLess(len(raw),capacity)
            f.calls.append(dict(name=name,capacity=capacity))
            return raw
        prefix=SimpleNamespace(backend=backend,runtime=SimpleNamespace(evaluate_text=evaluate),ui_child=f.child)
        backend._xp2_production_placement_source_receipt=object()
        with self.assertRaises(ValueError):
            collector.read(prefix,0,42,f.observation,core_sha256=XP2,include_pillage=True)
        with self.assertRaises(ValueError):
            collector.read_building_presence(prefix,0,42,f.observation,9,'BUILDING_TEST_4',core_sha256=XP2)
        self.assertEqual(f.calls,[])
        backend._xp2_placement_inventory_source_receipt=base=profile.VerifiedInventorySource(
            backend,backend.core,backend.core._handle,profile.SOURCE[1],XP2,
            backend._xp2_production_placement_source_receipt,11)
        with patch.object(profile.placement,'bind_owner',
                          return_value=backend._xp2_production_placement_source_receipt):
            with patch.object(profile,'verify_pillage_live',return_value=10) as live:
                receipt=profile.bind_owner(backend,backend.core,None,include_pillage=True)
                self.assertIs(profile.bind_owner(backend,backend.core,None,include_pillage=True),receipt)
                self.assertIs(profile.bind_owner(backend,backend.core,None),base)
                live.assert_called_once_with(backend.core._handle,None)
        f.lua.execute("GameInfo.Buildings['BUILDING_TEST_4']=GameInfo.Buildings[4]")
        with patch.object(collector,'verify_source',side_effect=AssertionError('static source reloaded')):
            inventory=collector.read(prefix,0,42,f.observation,core_sha256=XP2,include_pillage=True)
            building=collector.read_building_presence(prefix,0,42,f.observation,9,'BUILDING_TEST_4',core_sha256=XP2)
        self.assertIs(inventory['rows'][-1]['pillaged'],True)
        self.assertEqual(building,dict(city_id=9,building_type='BUILDING_TEST_4',index=4,hash=2004,present=True))
        self.assertEqual(len(f.calls),2)
        backend.core._civ6_host_execution_image=None
        with self.assertRaises(ValueError):
            collector.read(prefix,0,42,f.observation,core_sha256=XP2,include_pillage=True)
        self.assertEqual(len(f.calls),2)
        backend.poisoned=True
        with self.assertRaisesRegex(ValueError,'selected XP2 lifetime'):
            collector.read_building_presence(prefix,0,42,f.observation,9,'BUILDING_TEST_4',core_sha256=XP2)
        self.assertEqual(len(f.calls),2)


if __name__=='__main__':unittest.main()

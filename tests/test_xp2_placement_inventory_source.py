"""The shared Lua inventory with the XP2 source selector and typed data."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_xp1_placement_inventory as fixture
from civ6_host.runtime import placement_inventory as collector
from civ6_host.runtime import placement_inventory_profile as shared
from civ6_host.runtime import xp2_placement_inventory_source as selected
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as XP1, XP2_CORE_SHA256 as XP2, _copy


class XP2InventoryTests(unittest.TestCase):
    def read(self,f):
        return collector.read(SimpleNamespace(runtime=f,ui_child=f.child),0,42,f.observation,core_sha256=XP2)

    def test_actual_shared_lua_categories_index_hash_and_selected_provenance(self):
        f=fixture.Fixture();result=self.read(f)
        self.assertEqual([(r['city_id'],r['category'],r['plot_id'],r['complete']) for r in result['rows']],
            [(5,'building',2,False),(5,'building',9,False),(5,'district',1,False),
             (9,'building',4,True),(9,'district',3,True)])
        self.assertEqual(result['rows'][2]['hash'],0xFFFFFFFF)
        self.assertEqual(result['rows'][2]['district_id'],7)
        self.assertEqual(f.lua.eval('state.completionCalls'),5)
        self.assertIsNone(f.lua.eval('state.detailReads[7]'))
        self.assertIsNone(f.lua.eval('state.detailReads[8]'))
        self.assertEqual(shared.source_reference(XP2),selected.SOURCE)
        self.assertEqual(shared.verify_source()['image']['sha256'],XP1)
        self.assertEqual(shared.verify_source(XP2)['image']['sha256'],XP2)
        self.assertNotIn('placement_turn',str(result))

    def test_visibility_owner_and_type_checks_stay_before_sensitive_detail(self):
        for mutation,field in (('state.hidden[1]=true','state.plotReads[1]'),
                ('state.unrevealed[1]=true','state.plotReads[1]'),
                ('plots[1].owner=1','state.detailReads[1]'),
                ('plots[1].city=17','state.detailReads[1]')):
            f=fixture.Fixture();f.lua.execute(mutation)
            with self.subTest(mutation=mutation),self.assertRaises(Exception):self.read(f)
            self.assertIsNone(f.lua.eval(field))
            self.assertEqual(f.lua.eval('state.completionCalls'),0)
        for mutation in ('GameInfo.Districts[1].Index=7','plots[1].district=-2','plots[2].wonder=-2',
                'plots[1].id=-1',"GameInfo.Districts[1].DistrictType='BUILDING_WRONG'"):
            f=fixture.Fixture();f.lua.execute(mutation)
            with self.subTest(mutation=mutation),self.assertRaises(Exception):self.read(f)

    def test_after_completion_mutation_and_sentinel_handling(self):
        f=fixture.Fixture();f.lua.execute('plots[1].district=nil;plots[2].wonder=nil')
        self.assertEqual(len(self.read(f)['rows']),3)
        for mutation in ('plots[1].district=3','plots[1].id=19','plots[1].city=9',
                         'plots[1].owner=1','state.hidden[1]=true'):
            f=fixture.Fixture();f.lua.execute('state.afterComplete=function() '+mutation+' end')
            with self.subTest(mutation=mutation),self.assertRaises(Exception):self.read(f)

    def test_inventory_contract_and_cross_profile_source_join_mutations_refuse(self):
        original=selected._source;proof=selected.verify_source()
        for mutation in ('index','typecheck','visibility','source','callback'):
            p=_copy(proof)
            if mutation=='index':p['facts']['wonder_type_absent']['value_kind']='GameInfo.Buildings.Hash'
            elif mutation=='typecheck':p['facts']['district_complete']['nonnegative_plot_argument_checks_type']=True
            elif mutation=='visibility':p['read_contract']['hidden_plots_read']=True
            elif mutation=='source':p['bindings']['City.GetOwner']['source']['sha256']='0'*64
            else:p['bindings']['City.GetOwner']['callback_rva']='0x5a6d00'
            with self.subTest(mutation=mutation),patch.object(selected,'_source',side_effect=lambda r:p if r==selected.SOURCE else original(r)):
                with self.assertRaises(ValueError):selected.verify_source()


if __name__=='__main__':unittest.main()

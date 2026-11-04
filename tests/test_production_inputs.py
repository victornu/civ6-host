import copy
import json
import unittest
from civ6_host.contracts import production_info988 as legacy,production_inputs as public,network_turn
from civ6_host.runtime import production_inputs as runtime


def quote(unit=False,progress=4):
    category='unit' if unit else 'building'
    row=dict(city_id=11,category=category,index=1,hash=100,item_type=category.upper()+'_FIXTURE',
        raw=dict(cost=30,progress=progress,turns_left=4,formation_type=None,
                 base_cost=50 if unit else None,base_cost_visible=unit),
        public=dict(cost=50 if unit else 30,progress=None if unit or progress==0 else progress,
                    turns_left=4,never_completes=False,cost_kind='base' if unit else 'production'))
    return dict(schema=legacy.SCHEMA,player_id=0,turn=7,source_sha256=legacy.PROOF_SHA256,
        ui_sha256=legacy.PANEL_SHA256,tooltip_sha256=legacy.TOOLTIP_SHA256,rows=[row])


def fixture(*,category='building',current=100,previous=0,formation=0,progress=4,cost=30,turns=4,xp2=False):
    from lupa.lua51 import LuaRuntime
    lua=LuaRuntime(encoding=None)
    lua.globals().s=lua.table_from({k.encode():v.encode() if isinstance(v,str) else v
        for k,v in locals().copy().items() if k in ('category','current','previous','formation','progress','cost','turns','xp2')})
    lua.execute(rb'''
Game={GetLocalPlayer=function()return 0 end,GetLocalObserver=function()return 0 end,GetCurrentGameTurn=function()return 7 end}
MilitaryFormationTypes={STANDARD_FORMATION=0,CORPS_FORMATION=1,ARMY_FORMATION=2}
Locale={Lookup=function(v)return v end}
local row={Index=1,Hash=100,Name='Named item',Domain='DOMAIN_LAND'}
GameInfo={Buildings={},Units={},Districts={},Projects={}}
local q={GetCurrentProductionTypeHash=function()return s.current end,GetPreviousProductionTypeHash=function()return s.previous end,
 GetCurrentProductionTypeModifier=function()return s.formation end,GetTurnsLeft=function(self,value,...)
  assert(type(value)=='string')
  if s.xp2 and s.category=='unit' then
   assert(select('#',...)==1 and (...)==s.formation)
  else assert(select('#',...)==0) end
  return s.turns
 end,
 GetUnitCorpsCost=function()return s.cost*2 end,GetUnitArmyCost=function()return s.cost*3 end}
local specs={building={'Buildings','Building'},unit={'Units','Unit'},district={'Districts','District'},project={'Projects','Project'}}
local spec=specs[s.category];row[spec[2]..'Type']=string.upper(s.category)..'_FIXTURE';GameInfo[spec[1]][100]=row
q['Get'..spec[2]..'Progress']=function()return s.progress end;q['Get'..spec[2]..'Cost']=function()return s.cost end
local city={GetID=function()return 11 end,GetOwner=function()return 0 end,GetBuildQueue=function()return q end}
Players={[0]={GetCities=function()return {Members=function()return ipairs({city}) end} end}}
''')
    return runtime.parse(lua.execute(runtime.source(0,7,xp2=xp2)),0,7)


class ProductionInputsTests(unittest.TestCase):
    def test_quotes_keep_visible_values_and_remove_raw_without_mutation(self):
        value=quote();before=copy.deepcopy(value);out=public.project_quotes(value,0,7)
        self.assertEqual(out['rows'][0]['public'],value['rows'][0]['public'])
        self.assertNotIn('raw',out['rows'][0]);self.assertEqual(value,before)
        self.assertNotIn('base_cost',json.dumps(out))

    def test_hidden_candidate_stock_does_not_change_public_quote(self):
        self.assertEqual(public.project_quotes(quote(unit=True,progress=4),0,7),
                         public.project_quotes(quote(unit=True,progress=19),0,7))

    def test_public_raw_injection_unknown_schema_and_candidate_mismatch_refused(self):
        out=public.project_quotes(quote(),0,7)
        leak=copy.deepcopy(out);leak['rows'][0]['raw']=quote()['rows'][0]['raw']
        with self.assertRaises(ValueError):public.validate_quotes(leak,0,7)
        with self.assertRaises(ValueError):public.validate_quotes(out,0,7,candidates=[])
        with self.assertRaises(ValueError):public.validate_quotes(quote(),0,7)
        with self.assertRaises(ValueError):public.validate_quotes(out,1,7)

    def test_actual_getter_projection_for_all_categories_and_formations(self):
        for category in ['building','district','project','unit']:
            row=fixture(category=category)['cities'][0]
            self.assertEqual(row['state'],'current');self.assertEqual(row['item']['progress'],4)
            self.assertEqual(row['item']['cost'],30);self.assertEqual(row['item']['turns_left'],4)
        for formation,name,cost in [(1,'corps',60),(2,'army',90)]:
            item=fixture(category='unit',formation=formation)['cities'][0]['item']
            self.assertEqual(item['formation'],name);self.assertEqual(item['cost'],cost)
            self.assertIn(name.upper(),item['name'])
        unusual=fixture(category='unit',formation=99)['cities'][0]['item']
        self.assertEqual(unusual['formation'],'unsuffixed');self.assertEqual(unusual['cost'],0)

    def test_previous_item_and_unproductive_countdown_are_official_branches(self):
        row=fixture(current=0,previous=100,turns=-1)['cities'][0]
        self.assertEqual(row['state'],'completed');self.assertIsNone(row['item']['turns_left'])
        self.assertTrue(row['item']['never_completes'])
        self.assertEqual(fixture(current=0)['cities'],[dict(city_id=11,state='empty',item=None)])

    def test_exact_own_city_and_queue_head_join(self):
        out=fixture();obs=dict(player_id=0,turn=7,cities=[dict(id=11,owner=0)])
        queues=[dict(city_id=11,entries=[dict(category='building',index=1,hash=100)])]
        public.validate_current(out,0,7,observation=obs,queues=queues)
        with self.assertRaises(ValueError):public.validate_current(out,0,7,queues=[dict(city_id=11,entries=[])])
        with self.assertRaises(ValueError):public.validate_current(out,0,7,observation=dict(obs,cities=[dict(id=11,owner=1)]))
        leaked=copy.deepcopy(out);leaked['cities'][0]['item']['overflow']=4
        with self.assertRaises(ValueError):public.validate_current(leaked,0,7)

    def test_xp2_public_current_uses_formation_aware_countdown_and_exact_queue(self):
        from civ6_host.contracts.information import project, CURRENT_PRODUCTION_GROUP_SCHEMA
        current=fixture(category='unit',formation=1,xp2=True,turns=3)
        self.assertEqual(fixture(xp2=True), fixture())
        obs=dict(player_id=0,turn=7,cities=[dict(id=11,owner=0)])
        decisions=dict(schema=network_turn.CAPABILITY_CURRENT_PRODUCTION_SCHEMA,
            production_current=current,
            production_queues=[dict(city_id=11,entries=[dict(category='unit',index=1,hash=100)])])
        info=project('production',obs,decisions)
        self.assertEqual(info['schema'],CURRENT_PRODUCTION_GROUP_SCHEMA)
        self.assertEqual(info['current']['cities'][0]['item']['turns_left'],3)
        self.assertNotIn('quotes',info)
        decisions['production_queues'][0]['entries'][0]['hash']=101
        with self.assertRaisesRegex(ValueError,'differs from queue head'):
            project('production',obs,decisions)

    def test_checkpoint_preserves_actual_old_raw_fields_and_requires_exact_evidence(self):
        obs=dict(player_id=0,turn=7,cities=[dict(id=11,owner=0)])
        identity=dict(episode_id='episode',game_generation='generation',sequence=0,player_id=0,turn=7)
        old=dict(schema=network_turn.GROWTH_SCHEMA,base_schema='native',production={'native_snapshot':1},
                 production_info=quote(),candidates=[],**identity)
        old['decision_id']=network_turn.digest(old)
        current=dict(old,schema=network_turn.PRODUCTION_SCHEMA,production=fixture(),production_info=public.project_quotes(quote(),0,7))
        current['decision_id']=network_turn.digest({k:v for k,v in current.items() if k!='decision_id'})
        evidence=dict(**identity,actor_channel=False,production=old['production'],production_info=quote(),public_production=fixture())
        comparable,transition=network_turn.checkpoint_catalogue(current,old,obs,production_evidence=evidence)
        self.assertEqual(comparable,old);self.assertTrue(transition['legacy_raw_values_compared_from_administrative_readback'])
        for wrong in [None,dict(evidence,sequence=1),dict(evidence,game_generation='foreign'),dict(evidence,actor_channel=True)]:
            with self.assertRaises(ValueError):network_turn.checkpoint_catalogue(current,old,obs,production_evidence=wrong)
        changed=copy.deepcopy(evidence);changed['production']['native_snapshot']=2
        comparable,_=network_turn.checkpoint_catalogue(current,old,obs,production_evidence=changed)
        self.assertNotEqual(comparable,old)


if __name__=='__main__':unittest.main()

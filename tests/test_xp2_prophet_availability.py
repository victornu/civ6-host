"""Focused portable checks for the XP2 prophet optional-result readback."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp1_prophet_activation as adapter
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.native import native_prophet_activation as builders

OWN = ((17,0,0),(18,1,0),(19,2,0))
ENV = b"""
local moves={0,2,3.25}
local members={}
for i,m in ipairs(moves) do
 local id,x=16+i,i-1
 members[i]={GetID=function() return id end, GetOwner=function() return 0 end,
  GetType=function() return 13 end, GetX=function() return x end,
  GetY=function() return 0 end, GetMovesRemaining=function() return m end}
end
local collection={Members=function()
 local at=0
 return function() at=at+1; if members[at] then return at,members[at] end end
end}
local actor={GetID=function() return 0 end,IsAlive=function() return true end,
 IsTurnActive=function() return true end,IsTurnActiveComplete=function() return true end,
 GetUnits=function() return collection end}
local Players={[0]=actor}
local Game={GetLocalPlayer=function() return 0 end,GetLocalObserver=function() return 0 end,
 GetCurrentGameTurn=function() return 73 end,IsAllowStrategicCommands=function() return true end}
local GameInfo={Units={UNIT_GREAT_PROPHET={UnitType='UNIT_GREAT_PROPHET',Index=13}},
 UnitOperations={UNITOPERATION_FOUND_RELIGION={
 OperationType='UNITOPERATION_FOUND_RELIGION',Hash=-953161477,Index=15,VisibleInUI=true}}}
local UnitOperationResults={FAILURE_REASONS=-2028665063}
local OperationResultsTypes={NO_TARGETS=2}
local UnitManager={CanStartOperation=function(unit,hash,target,...)
 assert(hash==-953161477 and target==nil,'wrong official request')
 local uid=unit:GetID()
 local loose, mode=...
 if loose then
  assert(select('#',...)==1)
  record(uid,true,0)
  return uid==19
 end
 assert(uid==19 and select('#',...)==2 and mode==2,'strict before native loose result')
 record(uid,false,mode)
 return false, REASON_MAP
end, RequestOperation=function() error('diagnostic must not submit a native operation') end}
"""


class ProphetAvailabilityTests(unittest.TestCase):
    def test_exact_xp2_overload_returns_disabled_reason_without_querying_hidden_or_exhausted_units(self):
        from lupa.lua51 import LuaRuntime
        display = 'Lieu saint pillé 🧭,;|\n\t'
        for reasons,status,expected in (
            (b'nil','absent',None),
            (b'{}','absent',None),
            (b'{[-2028665063]={}}','available',[]),
            (b'{[-2028665063]={display, -2147483648, "", 2147483647}}',
             'available',[dict(type='string',value=display),
                 dict(type='signed32',value=-2147483648),dict(type='string',value=''),
                 dict(type='signed32',value=2147483647)]),
        ):
            with self.subTest(reasons=reasons):
                lua = LuaRuntime(encoding=None)
                calls=[]
                lua.globals()[b'record'] = lambda uid,loose,mode:calls.append((uid,loose,mode))
                lua.globals()[b'display'] = display.encode('utf-8')
                payload = lua.execute(ENV.replace(b'REASON_MAP',reasons)
                    +builders.availability_source(0,73,OWN,core_sha256=XP2_CORE_SHA256))
                visible,actual = builders.parse_availability(payload,0,73,OWN)
                self.assertTrue(visible)
                self.assertEqual(calls,[(18,True,0),(19,True,0),(19,False,2)])
                self.assertEqual([(r['visible'],r['strict'],r['result_map']) for r in actual],
                                 [(None,None,None),(False,None,None),(True,False,reasons!=b'nil')])
                self.assertEqual((actual[2]['reason_status'],actual[2]['reason_issue'],actual[2]['reasons']),
                                 (status,None,expected))
        with self.assertRaises(ValueError):
            builders.availability_source(0,73,OWN,core_sha256=XP1_CORE_SHA256)

    def test_optional_details_outside_wire_domain_preserve_native_refusal(self):
        from lupa.lua51 import LuaRuntime
        for reasons,issue,expected in (
            (b'false','field_type:boolean',None),
            (b'{[2]="sparse"}','list_shape_or_bound',None),
            (b'{["key"]="dictionary"}','list_shape_or_bound',None),
            (b'{[9]="oversized list"}','list_shape_or_bound',None),
            (b'{false, math.huge, string.rep("x",241), string.char(255),"retained"}',None,
             [dict(type='unsupported',native_type='boolean',issue='value_type'),
              dict(type='unsupported',native_type='number',issue='numeric_domain'),
              dict(type='unsupported',native_type='string',issue='byte_bound',byte_length=241),
              dict(type='string_bytes',encoding='hex',value='ff'),
              dict(type='string',value='retained')]),
        ):
            with self.subTest(reasons=reasons):
                lua = LuaRuntime(encoding=None)
                lua.globals()[b'record'] = lambda *_:None
                payload = lua.execute(ENV.replace(b'REASON_MAP',b'{[-2028665063]='+reasons+b'}')
                    + builders.availability_source(0,73,OWN,core_sha256=XP2_CORE_SHA256))
                _,rows = builders.parse_availability(payload,0,73,OWN)
                row = rows[-1]
                self.assertEqual((row['visible'],row['strict'],row['result_map']), (True,False,True))
                self.assertEqual((row['reason_status'],row['reason_issue'],row['reasons']),
                                 ('unsupported',issue,expected))

    def test_parser_refuses_unrelated_units_or_unqueried_reasons(self):
        valid=b'availability-v2,0,73,1,1;17,0,0,1,1,0,1,Ls4c4f43|i0'
        self.assertTrue(builders.parse_availability(valid,0,73,OWN[:1])[0])
        for invalid in (valid.replace(b',73,',b',74,'),valid.replace(b';17,',b';18,'),
                        valid.replace(b',1,1,0,1,',b',1,0,0,1,'),
                        valid.replace(b',1,1,0,1,',b',1,1,0,0,'),
                        valid.replace(b'Ls4c4f43|i0',b'not-a-reason'),
                        valid.replace(b'Ls4c4f43|i0',b'Ls4cZZ|i0'),
                        valid.replace(b'Ls4c4f43|i0',b'Li2147483648')):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                builders.parse_availability(invalid,0,73,OWN[:1])

    def test_catalogue_emits_only_private_readback_on_empty_xp2_offer_with_own_prophet(self):
        identity=NS(episode_id='episode',game_generation='generation')
        state=NS(identity=identity,sequence=11,transport=NS(require_empty_native_queue=Mock()))
        evaluate=Mock(return_value=b'availability-v2,0,73,1,1;17,0,0,1,1,0,1,Ls4c4f435f424c4f434b4544')
        prefix=NS(runtime=NS(evaluate_text=evaluate),ui_child=object(),deferred_events=NS(pending=[]))
        saved=NS(_check_query=Mock(),prefix=prefix,continuation=state,emit=Mock())
        source_value=dict(own={},activation=dict(prophet_type_index=13,candidates=[]))
        observation=dict(player_id=0,turn=73,units=[dict(id=17,x=0,y=0,type=13,owner=0)])
        with (patch.object(adapter.source,'bind_prefix') as bind,
              patch.object(adapter.source,'bind_availability') as availability,
              patch.object(adapter.source,'core_for',return_value=XP2_CORE_SHA256) as engine,
              patch.object(adapter.shared,'activation_catalog',return_value=source_value)):
            self.assertEqual(adapter.catalogue(saved,observation),source_value)
            self.assertEqual(saved.explicit_prophet_activation,source_value)
            self.assertEqual(adapter.actions(source_value),[])
            self.assertEqual(evaluate.call_count,1)
            self.assertEqual(state.transport.require_empty_native_queue.call_count,2)
            bind.assert_called_with(prefix)
            availability.assert_called_once_with(prefix)
            name=saved.emit.call_args.args[0]
            fields=saved.emit.call_args.kwargs
            self.assertEqual(name,'xp2_prophet_availability_readback')
            self.assertFalse(fields['actor_channel'])
            self.assertEqual((fields['player_id'],fields['turn'],fields['sequence']),(0,73,11))
            self.assertEqual(fields['diagnostic_schema'],'civ6-host.xp2-prophet-availability.v2')
            self.assertEqual(fields['units'][0]['reasons'],[dict(type='string',value='LOC_BLOCKED')])

            source_value['activation']['candidates']=[dict(unit_id=17,x=0,y=0)]
            adapter.catalogue(saved,observation)
            source_value['activation']['candidates']=[]
            adapter.catalogue(saved,dict(observation,units=[]))
            engine.return_value=XP1_CORE_SHA256
            adapter.catalogue(saved,observation)
            self.assertEqual(evaluate.call_count,1)
            self.assertEqual(saved.emit.call_count,1)


if __name__=='__main__':
    unittest.main()

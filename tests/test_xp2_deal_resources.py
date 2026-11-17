import ctypes as C
import struct
from types import SimpleNamespace
import unittest
from zlib import crc32

from civ6_host.runtime import xp2_deal_gold as deal
from civ6_host.runtime import xp2_deal_peace as treaty
from civ6_host.runtime import xp2_deal_resources as resources
from civ6_host.runtime.xp2_deal_value import DealValueWriter, SLOT

try:
    from lupa.lua51 import LuaError, LuaRuntime
except ImportError:
    LuaRuntime = None


class XP2DealResourceTests(unittest.TestCase):
    def test_mixed_peace_archive_requires_both_locked_terms_and_the_exact_payment(self):
        terms = [dict(direction=side, duration=0, locked=True) for side in ('outgoing', 'incoming')]
        header = struct.pack('<I15xI', 5, 3)

        def agreement(giver, receiver, locked=1):
            return struct.pack('<I16xI4xIII2xBx8I', treaty.AGREEMENTS, treaty.MAKE_PEACE,
                               0, giver, receiver, locked, 1, 1, 0x234988CF, 2, 0, 0, 0xFFFFFFFF, 2)

        peace_out, peace_in = agreement(0,1), agreement(1,0)
        payment = struct.pack('<I24xIII16xI', 0x05eb0df7, 0, 0, 1, 17)

        def verify(payload):
            expected = deal._archive_items(0,1,17,0,(0,0),(),(),terms)
            deal._verify_archive_items(header + payload, expected)

        verify(peace_out + payment + peace_in)
        wrong_parameter = bytearray(peace_out)
        wrong_parameter[68] ^= 1
        for invalid in (agreement(0,1,0)+peace_in+payment, peace_out+peace_out+payment,
                        peace_out+agreement(1,2)+payment, wrong_parameter+peace_in+payment):
            with self.assertRaisesRegex(RuntimeError, 'locked peace term'):
                verify(invalid)

    @unittest.skipIf(LuaRuntime is None, 'Lua fixture unavailable')
    def test_native_directional_counts_include_both_locked_peace_terms_on_each_side(self):
        lua = LuaRuntime()
        lua.execute("""
DealProposalAction={ADJUSTED=3,EQUALIZE=6,EQUALIZE_FAILED=10}
give,receive=3,2
working={GetItemCount=function(_,player) return player==0 and give or receive end,
         IsValid=function() return true end,HasUnacceptableItems=function() return false end,
         IsGift=function() return false end}
""")
        source = (b'local deal,me,other,count,treatyCount=working,0,1,3,2\n'
                  b'local function u31(v) return v>=0 and v%1==0 end\n'
                  + deal._NEGOTIATION + b"\nreturn canEqualize('rejected')")
        self.assertTrue(lua.execute(source))
        lua.execute('give,receive=2,1')
        with self.assertRaisesRegex(LuaError, 'negotiation directions differ'):
            lua.execute(source)

    def test_demand_archive_must_come_from_the_counterparty_with_exact_terms(self):
        item = struct.pack('<I24xIII16xI', 0x05eb0df7,0,1,0,1)
        payload = struct.pack('<I15xI',5,1)+item

        class Transport:
            def __init__(self, archive):
                self.pending = [archive]
                self.delivered = []

            def deliver_one(self):
                self.delivered.append(self.pending.pop(0))

            def require_empty_native_queue(self):
                if self.pending:
                    raise ValueError('Native demand left a pending archive')

        for outcome, name in ((1,'accepted'),(2,'rejected')):
            valid = struct.pack('<4I',0xf06250e4,outcome,1,0)+payload
            transport = Transport(valid)
            self.assertEqual(deal.deliver_demand_reply(transport,0,1,(1,0),()),name)
            self.assertEqual(transport.delivered,[valid])
        for bad in (struct.pack('<4I',0xf06250e4,2,0,1)+payload,
                    valid[:-4]+struct.pack('<I',2), valid[:-1]):
            transport = Transport(bad)
            with self.assertRaisesRegex(RuntimeError,'Native (demand|deal|gold)'):
                deal.deliver_demand_reply(transport,0,1,(1,0),())
            self.assertEqual(transport.delivered,[])

    def test_value_scope_restores_original_auxiliary_binding_even_on_lua_failure(self):
        state, previous, installed = 42, (10,object()), (20,object())
        slot_key = (1,SLOT)
        host = SimpleNamespace(aux_vtable=(C.c_void_p*32)(),_slot_bindings={slot_key:previous})
        host.aux_vtable[SLOT//8] = previous[0]
        writer = DealValueWriter.__new__(DealValueWriter)
        writer.base, writer.owner, writer.havok = 1, 2, (3,4,5)
        writer.host,writer.slot_key,writer.previous,writer.installed = host,slot_key,previous,installed
        writer.begin = lambda *args: int(args == (1,2,state,3,4,5,31))
        writer.end = lambda owner,child: int((owner,child)==(2,state) and host._slot_bindings[slot_key]==previous)

        def protected(*args, **kwargs):
            self.assertEqual(host.aux_vtable[SLOT//8],installed[0])
            self.assertEqual(host._slot_bindings[slot_key],installed)
            raise RuntimeError('native Lua script failed')

        runtime = SimpleNamespace(registry=SimpleNamespace(validate=lambda child:state), service_owner=host,
                                  evaluate_text=protected)
        writer.prefix = SimpleNamespace(runtime=runtime,ui_child=object())
        with self.assertRaisesRegex(RuntimeError,'native Lua script failed'):
            writer.evaluate(b'select resource',31)
        self.assertEqual(host._slot_bindings[slot_key],previous)
        self.assertEqual(host.aux_vtable[SLOT//8],previous[0])

    def test_archive_joins_resource_type_quantity_and_both_endpoints(self):
        pid, target, sid = 0, 1, 6
        term = dict(direction='incoming', resource_index=7, resource_type='RESOURCE_SILK', amount=1, duration=30)
        resource_hash = crc32(b'RESOURCE_SILK') ^ 0xffffffff

        border = dict(direction='outgoing',duration=30)

        def archives(hash_value, giver=target, border_subtype=None):
            item = struct.pack('<I24xIII8xIII8xIII', resources.KIND, 30, giver, pid, 1,
                               resources.RESOURCE_HASH_KEY, 2, hash_value, 1, 1)
            self.assertEqual(len(item), resources.ITEM_BYTES)
            if border_subtype is not None:
                item += struct.pack('<I16xIIIII4xIII', 0x8bbf84cc,border_subtype,0xffffffff,
                                    border['duration'],pid,target,1,0,2)
            payload = struct.pack('<I15xI',5,1 + int(border_subtype is not None)) + item
            first = struct.pack('<IIII',0xf06250e4,1,pid,target) + payload
            values = ((0xbaef29be,3,0x84e9dc8a),(0x1226a98f,3,0xc20ef7ff),
                      (0x9bba1fc1,3,0x7332f7d6),(0x9c594aff,2,pid),(0x18383f56,2,target),
                      (0x3c255a0b,3,1),(0xfe1e2e5d,3,0))
            encoded = b''.join(struct.pack('<II8xI',*value) for value in values)
            second = (struct.pack('<III',0xa4172391,pid,sid)+encoded+payload).ljust(
                535 + (56 if border_subtype is not None else 0), b'\x00')
            return first, second

        deal.validate_acceptance(archives(resource_hash),pid,target,sid,0,resource_terms=(term,))
        for wire in (archives(resource_hash,giver=pid),archives(resource_hash+1)):
            with self.assertRaisesRegex(RuntimeError,'different terms'):
                deal.validate_acceptance(wire,pid,target,sid,0,resource_terms=(term,))
        deal.validate_acceptance(archives(resource_hash,border_subtype=0xf18dfd9a),
                                 pid,target,sid,0,resource_terms=(term,),border_terms=(border,))
        with self.assertRaisesRegex(RuntimeError,'different open-borders rights'):
            deal.validate_acceptance(archives(resource_hash,border_subtype=0xf18dfd9b),
                                     pid,target,sid,0,resource_terms=(term,),border_terms=(border,))

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture unavailable')
    def test_copy_adjusted_empty_deal_keeps_the_reply_and_declines_unknown_items(self):
        lua = LuaRuntime()
        lua.execute("""
DealItemTypes={GOLD=0,RESOURCES=-1069574269}; DealItemSubTypes={NONE=0}
DealDirection={INCOMING=2,OUTGOING=1}; DealProposalAction={ADJUSTED=3,EQUALIZE=6,EQUALIZE_FAILED=10}
local function working(count)
 return {GetItemCount=function(_,giver) if giver~=nil then return 0 end; return count end,
         FindItemsByType=function() return {} end}
end
inbound=working(0)
outbound=working(1)
copies=0
DealManager={
 GetWorkingDeal=function(direction) return direction==2 and inbound or outbound end,
 GetPossibleDealItems=function() return {} end,
 CopyIncomingToOutgoingWorkingDeal=function() outbound=working(0); copies=copies+1 end,
 AreWorkingDealsEqual=function() return outbound:GetItemCount()==inbound:GetItemCount() end
}
function installUnknownItem() inbound=working(1) end
""")
        prefix = b'local me,other,deal,queued=0,1,outbound,false\n'
        self.assertEqual(lua.execute(deal.copy_adjusted_source(prefix)), 'verified')
        raw = lua.execute(deal.read_source(prefix, 'adjusted', acceptance_ready=True,
                                           recurring=True, bilateral=True, include_resources=True, negotiation=True))
        _, state, _, _, _, equalize = deal.parse(raw.rsplit('|', 1)[0].encode('ascii'), 'adjusted',
                                                 recurring=True, bilateral=True, negotiation=True)
        self.assertIsNone(state['finalize'])
        self.assertFalse(equalize)
        lua.eval('installUnknownItem')()
        from lupa.lua51 import LuaError
        with self.assertRaisesRegex(LuaError, 'draft contains unqualified items'):
            lua.execute(deal.copy_adjusted_source(prefix))
        self.assertEqual(lua.globals().copies, 1)

    @unittest.skipIf(LuaRuntime is None, 'Lua 5.1 fixture unavailable')
    def test_resource_edit_updates_only_the_selected_working_deal_term(self):
        lua = LuaRuntime()
        lua.execute("""
DealItemTypes={GOLD=0,RESOURCES=-1069574269}; DealItemSubTypes={NONE=0}
DealDirection={INCOMING=2}; DealProposalAction={ACCEPTED=1,REJECTED=2,PROPOSED=4,INSPECT=7}
GameInfo={Resources={[7]={ResourceType='RESOURCE_SILK',ResourceClassType='RESOURCECLASS_LUXURY'}},
 Resource_Consumption={}}
Players={[0]={},[1]={GetResources=function() return {GetResourceAmount=function() return 2 end} end}}
local resource
working={
 GetItemCount=function() return resource and 1 or 0 end,
 FindItemsByType=function(_,kind,_,giver)
  if giver==1 and kind==DealItemTypes.RESOURCES and resource then return {resource} end
  return {}
 end,
 AddItemOfType=function(_,kind,giver)
  assert(giver==1 and kind==DealItemTypes.RESOURCES)
  local index,amount,turns
  resource={SetValueType=function(_,n) index=n end,GetValueType=function() return index end,
   SetAmount=function(_,n) amount=n end,GetAmount=function() return amount end,
   SetDuration=function(_,n) turns=n end,GetDuration=function() return turns end,
   GetMaxAmount=function() return 2 end,IsValid=function() return true end,GetID=function() return 77 end}
  return resource
 end,
 GetItemParent=function() return nil end,
 RemoveItemByID=function(_,id) assert(id==77); resource=nil end,
 Validate=function() end,IsValid=function() return resource~=nil end,
 HasUnacceptableItems=function() return false end
}
DealManager={
 GetPossibleDealItems=function(giver,receiver,kind,deal)
  if giver==1 and kind==DealItemTypes.RESOURCES then
   return {{ForType=7,MaxAmount=2,IsValid=true}}
  end
  return {}
 end,
 SendWorkingDeal=function(verb,me,other) assert(verb==7 and me==0 and other==1); return 1 end,
 GetWorkingDeal=function() return working end,
 CopyIncomingToOutgoingWorkingDeal=function() end,
 AreWorkingDealsEqual=function() return true end
}
""")
        prefix = b'local me,other,deal,queued=0,1,working,false\n'
        choice = 'CHOICE_SET_REQUESTED_DEAL_RESOURCE'
        self.assertEqual(lua.execute(deal.resource_edit_source(prefix,choice,7,3)), 'unavailable')
        self.assertEqual(lua.execute(deal.resource_edit_source(prefix,choice,7,2)), 'inspected')
        read = deal.read_source(prefix,'accepted',acceptance_ready=True,recurring=True,bilateral=True,
                                include_resources=True)
        row, = resources.parse(lua.execute(read).rsplit('|',1)[1])
        self.assertEqual((row['direction'],row['amount'],row['duration']), ('incoming',2,30))
        self.assertEqual(lua.execute(deal.copy_source(prefix,0,requested=(0,0),resource_terms=(row,))), 'verified')
        self.assertEqual(lua.execute(deal.resource_edit_source(prefix,choice,7,0)), 'removed')
        row, = resources.parse(lua.execute(read).rsplit('|',1)[1])
        self.assertEqual((row['amount'],row['duration']), (0,None))
        lua.execute("""
GameInfo.Resources[7]={ResourceType='RESOURCE_IRON',ResourceClassType='RESOURCECLASS_STRATEGIC'}
GameInfo.Resource_Consumption.RESOURCE_IRON={Accumulate=true}
""")
        self.assertEqual(lua.execute(deal.resource_edit_source(prefix,choice,7,2)), 'inspected')
        row, = resources.parse(lua.execute(read).rsplit('|',1)[1])
        self.assertEqual((row['resource_type'],row['amount'],row['duration']), ('RESOURCE_IRON',2,0))
        self.assertEqual(lua.execute(deal.copy_source(prefix,0,requested=(0,0),resource_terms=(row,))), 'verified')

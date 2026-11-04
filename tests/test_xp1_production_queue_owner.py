"""Actual saved owner, transport, FIFO and queue algorithm; native calls are fixtures."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
from test_xp1_unit_orders_owner import Fixture as OrderFixture
from test_xp1_unit_orders import LuaRuntime
from test_xp1_turn_a0 import scalar
from civ6_host.runtime import xp1_production_queue as adapter
from civ6_host.runtime.native import native_saved_production_queue as shared

HOST = Path(__file__).resolve().parents[1]
LAB = HOST.parent/'civ6-rl-lab'
# Reuse the existing isolated Lua fixture rather than fork its production model.
_tree = ast.parse((LAB/'tests/test_native_production_queue962.py').read_text(encoding='utf-8'))
LUA = ast.literal_eval(next(n.value for n in _tree.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'LUA_FIXTURE' for t in n.targets)))


class Fixture(OrderFixture):
    def __init__(self):
        super().__init__()
        self.lua = LuaRuntime(max_memory=4*1024*1024)
        self.lua.execute(LUA)
        self.lua.execute('s.current=0;s.turn=8')
        self.lua.globals().request_python = self.queue_request
        self.lua.execute('''
local prior=CityManager.RequestOperation
CityManager.RequestOperation=function(c,op,args)
 prior(c,op,args);request_python()
end
function drain_queue_fixture()
 local e=CityOperationTypes;local a=s.lastArgs;local mode=a[e.PARAM_INSERT_MODE]
 if mode==e.VALUE_REMOVE_AT then table.remove(s.entries,a[e.PARAM_QUEUE_LOCATION]+1)
 elseif mode==e.VALUE_SWAP then
  local i,j=a[e.PARAM_QUEUE_SOURCE_LOCATION]+1,a[e.PARAM_QUEUE_DESTINATION_LOCATION]+1
  s.entries[i],s.entries[j]=s.entries[j],s.entries[i]
 else
  local kinds={unit=e.PARAM_UNIT_TYPE,building=e.PARAM_BUILDING_TYPE,
               project=e.PARAM_PROJECT_TYPE,district=e.PARAM_DISTRICT_TYPE}
  local chosen=nil
  for k,v in pairs(kinds) do if a[v] then assert(not chosen);chosen=k;seed(k,a[v]) end end
  assert(chosen)
  if mode==e.VALUE_REPLACE_AT then
   local inserted=table.remove(s.entries);s.entries[a[e.PARAM_QUEUE_DESTINATION_LOCATION]+1]=inserted
  else assert(mode==e.VALUE_APPEND) end
 end
 if #s.entries==0 then s.current=0 else
  local v=s.entries[1]
  for _,spec in ipairs({{GameInfo.Units,'UnitType'},{GameInfo.Buildings,'BuildingType'},
                       {GameInfo.Projects,'ProjectType'},{GameInfo.Districts,'DistrictType'}}) do
   if v[spec[2]]~=nil then s.current=spec[1][v[spec[2]]].Hash end
  end
 end
end
''')
        self.token.observation['cities'] = [dict(id=5)]
        self.observation = deepcopy(self.token.observation)
        self.token.emit = self.emit
        self.stack.enter_context(patch.object(shared, 'observe_player', self.observe_native))
        # The real profile gate must be exercised, never replaced by True.
        from test_xp1_production_queue_profile import bind_gate_fixture
        bind_gate_fixture(self)

    def evaluate(self, child, source, name, **kwargs):
        if name in (b'@explicit_production_queue', b'@explicit_production_queue_request'):
            if child is not self.token.ui_child:
                raise AssertionError('Foreign queue Lua child')
            return self.lua.execute(source.decode()).encode()
        return super().evaluate(child, source, name, **kwargs)

    def queue_request(self):
        self.token.transport.pending.append(self.payload)
        self.emit('native_command_archive_queued', archive_hex=self.payload.hex(),
                  bytes=len(self.payload), delivery_pending=True)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva == self.token.transport.transport_abi.drain_rva:
            if core is not self.backend.core:
                raise AssertionError('Foreign queue Core')
            def drain(ctx):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                self.lua.execute('drain_queue_fixture()')
                descriptor = self.make_blob(struct.pack('<HHI', 0, 2, 5), 1024)
                # Real common producer/FIFO for the two queue-family callbacks.
                from civ6_host.runtime.native import native_event_92492f56 as queue_event
                fields = {queue_event.SELECTOR_KEY: scalar(3, 0), queue_event.DESCRIPTOR_KEY: descriptor,
                          queue_event.D6_KEY: scalar(2, 101), queue_event.A1FBC_KEY: scalar(2, 0)}
                self.owner.dispatch(queue_event.EVENT_KIND, fields, 0)
                from civ6_host.runtime.native import native_event_2842ce14 as head_event
                self.owner.dispatch(head_event.EVENT_KIND, fields, 0)
            return drain
        return super().virtual(core, pointer, slot, rva, result, *args)

    def offered(self):
        self.saved._running=True;self.set_active(False)
        state = shared.catalog(self.token.prefix, 5, 8, player_id=0, enabled=True,
                               core_sha256=self.backend.load_abi.core_sha256)
        entries=state['entries'];head=entries[0] if entries else None
        self.token.explicit_production_snapshot=dict(cities=[dict(city_id=5, queue_size=len(entries),
            kind={'unit':'U','building':'B','district':'D','project':'P'}[head['category']] if head else 'N',
            item_index=head['index'] if head else None,
            current_production_hash=head['hash'] if head else 0)])
        return adapter.read(self.saved,self.token.observation)

    def execute(self, action):
        self.saved._running=False
        return self.saved.execute(action)


class ProductionQueueOwnerTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_all_queue_gestures_use_real_continuation_transport_and_fifo(self):
        f=self.fixture();steps=0
        def submit(choose):
            nonlocal steps
            offers=f.offered();action=choose(offers['actions']);result=f.execute(action)
            effect=result['effect'];steps+=1
            self.assertEqual(effect['receipt']['action'],action)
            self.assertEqual(result['observation_after'],effect['observation'])
            self.assertEqual(f.token.publication_count,steps)
            self.assertEqual(f.token.sequence,steps)
            self.assertEqual(f.deferred.consumed_count,2*steps)
            self.assertEqual(f.deferred.pending,[])
            self.assertIsNone(f.token.explicit_production_queues)
            self.assertIsNone(f.token._xp1_production_queue_catalogue)
            return effect['receipt']
        for i in range(8):
            receipt=submit(lambda offers:next(a for a in offers if a['kind']=='queue_append'
                                             and a['hash']==(101 if i%2==0 else 102)))
            self.assertEqual(len(receipt['queue_after']['entries']),i+1)
        for kind in ('queue_swap','queue_append','queue_remove'):
            receipt=submit(lambda offers:next(a for a in offers if a['kind']==kind))
            if kind=='queue_append':self.assertEqual(receipt['action']['mode'],'replace_tail')
        self.assertEqual(len(receipt['queue_after']['entries']),7)

    def test_stale_catalogue_and_foreign_owner_refuse_before_request(self):
        for change in ('sequence','owner','catalogue','action'):
            with self.subTest(change=change):
                f=self.fixture();offers=f.offered();action=deepcopy(offers['actions'][0]);f.set_active(True)
                if change=='sequence':f.token.sequence+=1
                elif change=='owner':f.saved._backend=object()
                elif change=='catalogue':f.token.explicit_production_queues=[]
                else:action['city_id']=True
                with self.assertRaises((ValueError,RuntimeError)):
                    adapter.apply(f.saved,action,f.token.observation)
                self.assertEqual(f.machine,[]);self.assertEqual(f.lua.globals().s.requests,0)
                f.close()

    def test_shared_lua_and_engine_selection_preserve_base_algorithm(self):
        from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256 as xp1
        self.assertEqual(shared.source(0,5,8,True),shared.source(0,5,8,True,core_sha256=xp1))
        historical=ast.parse((LAB/'civ6rl/native_saved_production_queue.py').read_text(encoding='utf-8'))
        lua=ast.literal_eval(next(n.value for n in historical.body if isinstance(n,ast.Assign)
                                and any(isinstance(t,ast.Name) and t.id=='LUA' for t in n.targets)))
        self.assertEqual(shared.LUA,lua)
        from civ6_host.contracts import production_queue as portable
        for name in ('uint','validate_action','action_wire','validate_catalog','catalog_wire',
                     'validate_all','check_heads','check_effect'):
            self.assertIs(getattr(shared,name),getattr(portable,name))
        targets={'verify_source','source','catalog','request_source','apply'}
        for fn in ast.parse(Path(shared.__file__).read_text()).body:
            if not isinstance(fn,ast.FunctionDef) or fn.name not in targets:continue
            for call in ast.walk(fn):
                if not isinstance(call,ast.Call):continue
                selected=(isinstance(call.func,ast.Name) and call.func.id in targets)
                selected|=(isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name)
                           and call.func.value.id=='production' and call.func.attr=='_preamble')
                if selected:
                    self.assertEqual([(kw.arg,ast.unparse(kw.value)) for kw in call.keywords if kw.arg=='core_sha256'],
                                     [('core_sha256','core_sha256')])


if __name__=='__main__':unittest.main()

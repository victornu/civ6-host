"""FaithChanged uses the real saved owner, shared lease, selected ABI and FIFO."""
import ctypes as C
import struct
import unittest
from test_xp1_placement_events import Fixture as PlacementFixture
from test_xp1_turn_a0 import scalar
from civ6_host.runtime import faith_event_profile as source
from civ6_host.runtime.native import native_event_b3495127 as event


class ObservedFIFO(list):
    """Observe the real DeferredHostQueue append without replacing its method."""
    def __init__(self,fixture):super().__init__();self.fixture=fixture
    def append(self,record):
        f=self.fixture
        if struct.unpack_from('<I',record,4)[0]==194:
            assert f.live['player']==f.live['faith']==1
            f.calls.append(('enqueue_faith',))
        return super().append(record)


class Fixture(PlacementFixture):
    def __init__(self):
        super().__init__();self.route='live';self.player_id=2
        self.objects['faith']=0x76600000
        self.memory.put(self.objects['player'],struct.pack('<QQQI',self.memory.base+source.TABLES['player'][0],0x76601000,0,1))
        self.memory.put(self.objects['faith'],struct.pack('<QQQI',self.memory.base+source.TABLES['facade'][0],0x76602000,0,1))
        self.deferred.pending=ObservedFIFO(self)

    def set_cached(self):
        self.route='cached'
        for name,table in (('player','player'),('faith','facade')):
            self.memory.put(self.objects[name],struct.pack('<QQQI',self.memory.base+source.TABLES[table][0],0,0x76603000,1))

    def factory(self,result,*args):
        fallback=super().factory(result,*args)
        def bind(target):
            if callable(target):return fallback(target)
            base=self.backend.core._handle
            found=[n for n,(table,slot) in source.OPS.items() if target==base+source.TABLES[table][1][slot]]
            if not found:return fallback(target)
            name=found[0]
            expected={'get_player':(C.c_void_p,(C.c_void_p,C.c_int32)),
                      'get_facade':(C.c_void_p,(C.c_void_p,)),
                      'get_slot18':(C.c_void_p,(C.c_void_p,C.c_void_p)),
                      'get_slot10':(C.c_void_p,(C.c_void_p,C.c_void_p))}.get(name,(None,(C.c_void_p,)))
            assert (result,args)==expected
            return lambda *values:self.faith_native(name,*values)
        return bind

    def faith_native(self,name,pointer,*args):
        self.calls.append((name,pointer,*args));o=self.objects
        if name=='get_player':
            assert pointer==self.backend.context and args==(self.player_id,)
            return None if self.route=='player-null' else self.acquire('player')
        if name=='release_context':assert pointer==self.backend.context;return None
        if name=='get_facade':
            assert pointer==o['player'] and self.live['player']==1
            return None if self.route=='facade-null' else self.acquire('faith')
        if name in ('release_facade','release_player'):
            label='faith' if name=='release_facade' else 'player'
            assert pointer==o[label] and self.live[label]==1;self.live[label]-=1;return None
        if name in ('get_slot18','get_slot10'):
            assert pointer==o['faith'];out=args[0]
            C.memmove(out,struct.pack('<I',268 if name=='get_slot18' else 269),4)
            if self.route=='bad_output' and name=='get_slot10':return out+4
            return out
        raise AssertionError(name)

    def fields(self):return {event.SELECTOR_KEY:scalar(3,0),event.PLAYER_KEY:scalar(2,self.player_id)}


class FaithEventTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_selected_seven_operations_retained_until_actual_fifo_live_and_cached(self):
        for cached in (False,True):
            with self.subTest(cached=cached):
                f=self.fixture()
                if cached:f.set_cached()
                self.assertEqual(f.owner.dispatch(source.EVENT_KIND,f.fields(),0),0)
                self.assertEqual([r[0] for r in f.calls],['get_player','release_context','get_facade','get_slot18','get_slot10','enqueue_faith','release_facade','release_player'])
                self.assertFalse(any(f.live.values()));self.assertEqual(len(f.deferred.pending),1)
                self.assertEqual(struct.unpack_from('<IIII',f.deferred.pending[0],80),(1,2,269,268))
                self.assertEqual(f.deferred.drain(),1);self.assertIsNone(f.owner._foundation_borrow)

    def test_source_null_and_bad_output_branches_preserve_release_and_no_fake_record(self):
        for route in ('player-null','facade-null','bad_output'):
            with self.subTest(route=route):
                f=self.fixture();f.route=route
                if route=='bad_output':
                    with self.assertRaisesRegex(RuntimeError,'output pointer'):f.owner.dispatch(source.EVENT_KIND,f.fields(),0)
                    self.assertTrue(f.owner.quarantined)
                else:self.assertEqual(f.owner.dispatch(source.EVENT_KIND,f.fields(),0),0)
                self.assertEqual(f.deferred.pending,[]);self.assertFalse(any(f.live.values()))
                self.assertEqual(sum(x[0]=='release_context' for x in f.calls),1)
                self.assertEqual(sum(x[0]=='release_player' for x in f.calls),int(route!='player-null'))
                self.assertEqual(sum(x[0]=='release_facade' for x in f.calls),int(route=='bad_output'))
                self.assertIsNone(f.owner._foundation_borrow)

    def test_source_owner_tables_and_unqualified_engine_refused(self):
        f=self.fixture();source.bind_owner(f.backend,f.backend.core,f.read)
        self.assertIs(source.select_tables(source.BASE_CORE_SHA256,event._TABLES),event._TABLES)
        with self.assertRaises(ValueError):source.select_tables('0'*64,event._TABLES)
        with self.assertRaises(ValueError):source.bind_owner(f.backend,object(),f.read)
        table=source.TABLES['facade'][0];f.memory.put(f.memory.base+table+0x18,bytes(8))
        with self.assertRaisesRegex(ValueError,'table changed'):source.bind_owner(f.backend,f.backend.core,f.read)


if __name__=='__main__':unittest.main()

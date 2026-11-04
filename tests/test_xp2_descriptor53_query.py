"""Offline DroughtAddedToMap getter selection on the existing query owner."""
import ctypes as C
import hashlib
from pathlib import Path
import struct
import unittest

from test_xp2_storm_query import _Graph
from civ6_host.runtime import xp2_descriptor53_query as drought
from civ6_host.runtime import xp2_storm_query as storm


KEY = struct.pack('<HHI',0xFFFF,0x53,7)


class DroughtGraph(_Graph):
    def __init__(self):
        super().__init__()
        self.native_calls.pop('query_pair')

    def _install_sources_and_tables(self):
        super()._install_sources_and_tables()
        for fn in drought.source()['functions'].values():
            self._install_body(fn['body'])
            for tail in fn['out_of_line_tail_jumps']:
                self._install_body(tail['body'])
        self.memory.qword(self.base+0xA110F0+0x140,self.base+0x5980E0)

    def query_values(self,target,service,key_pointer,vector_pointer):
        self.order.append(('query_values',target,service))
        self.assertEqual(target,self.base+0x5980E0)
        self.assertEqual(service,self.service)
        self.assertEqual(C.string_at(key_pointer,8),KEY)
        vector = C.cast(vector_pointer,C.POINTER(storm._Vector)).contents
        if self.item_values:
            raw = struct.pack('<'+'I'*len(self.item_values),*self.item_values)
            self.memory.put(self.data,raw)
            vector.begin = self.data
            vector.end = vector.capacity = self.data+len(raw)
        # The EXE consumes the filled vector, not this native return DWORD.
        return 0xFFFFFFFF


class Descriptor53QueryTests(unittest.TestCase):
    def test_native_getter_corresponds_to_distinct_exe_helper_and_writer(self):
        p = drought.source()
        helper = {row['va']:row['text'] for row in drought._rows(p['exe_functions']['0x146b30'])}
        callback = {row['va']:row['text'] for row in drought._rows(p['exe_functions']['0x145650'])}
        self.assertEqual(callback['0x140145686'],'mov r14d, 0x53')
        self.assertEqual(callback['0x1401456eb'],'call 0x140146b30')
        self.assertEqual(callback['0x140145796'],'call 0x140125710')
        self.assertEqual(helper['0x140146bd7'],'call qword ptr [rax + 0x140]')
        self.assertEqual(helper['0x140146caa'],'call 0x1400f1c00')
        self.assertFalse(any('0x110]' in value for value in helper.values()))
        native = {row['rva']:row['text'] for row in drought._rows(p['functions']['0x5980e0']['body'])}
        self.assertEqual(native['0x598141'],'call 0x1801bdb60')
        self.assertEqual(native['0x59819e'],'call 0x1801bdb60')
        self.assertEqual(p['selection']['record_type'],0x13B)
        self.assertEqual(tuple(map(tuple,p['contract']['undefined_when_vector_empty'])),((100,112),))
        for path,digest in drought.source_dependencies().items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)

    def test_list_conversion_order_and_release_reuse_without_pair_query(self):
        graph = DroughtGraph()
        def convert(core,context,value,*,read):
            self.assertIs(core,graph.core)
            self.assertEqual(context,graph.context)
            graph.order.append(('position',value))
            return struct.pack('<ii',31,19)
        result = drought.query_descriptor53_objects(graph.core,graph.context,KEY,
            read=graph.memory.read,native_calls=graph.native_calls,index_to_position=convert)
        self.assertEqual(result.items,(11,29))
        self.assertEqual(result.positions,(struct.pack('<ii',31,19),)*2)
        self.assertIsNone(result.position)
        self.assertEqual([row[0] for row in graph.order],['get_game','get_service',
            'query_values','position','position','free_vector','release_service','release_game'])

    def test_empty_query_has_no_pair_or_coordinate_substitute(self):
        graph = DroughtGraph()
        graph.item_values = ()
        result = drought.query_descriptor53_objects(graph.core,graph.context,KEY,
            read=graph.memory.read,native_calls=graph.native_calls,
            index_to_position=lambda *args,**kwargs:self.fail('no index exists'))
        self.assertEqual(result.items,())
        self.assertEqual(result.positions,())
        self.assertIsNone(result.position)
        self.assertEqual([row[0] for row in graph.order],['get_game','get_service',
            'query_values','release_service','release_game'])

    def test_new_bytes_and_slot_cannot_reuse_cached_storm_verification(self):
        for defect in ('body','slot'):
            graph = DroughtGraph()
            storm._verify_live_once(graph.core,graph.base,graph.memory.read)
            self.assertTrue(hasattr(graph.core,'_civ6_host_xp2_storm_source_verification'))
            if defect == 'body':
                graph.memory.put(graph.base+0x5980E0,b'\x90')
            else:
                graph.memory.qword(graph.base+0xA110F0+0x140,graph.base+storm.SERVICE_LIST_RVA)
            with self.subTest(defect=defect),self.assertRaises(ValueError):
                drought.query_descriptor53_objects(graph.core,graph.context,KEY,
                    read=graph.memory.read,native_calls=graph.native_calls,
                    index_to_position=lambda *args,**kwargs:bytes(8))
            self.assertEqual(graph.order,[])

    def test_conversion_failure_frees_vector_then_releases_owners(self):
        graph = DroughtGraph()
        def convert(*args,**kwargs):
            raise ValueError('invalid native index')
        with self.assertRaisesRegex(ValueError,'invalid native index'):
            drought.query_descriptor53_objects(graph.core,graph.context,KEY,
                read=graph.memory.read,native_calls=graph.native_calls,index_to_position=convert)
        self.assertEqual([row[0] for row in graph.order][-3:],
                         ['free_vector','release_service','release_game'])

    def test_wrong_descriptor_or_extra_pair_operation_refused(self):
        graph = DroughtGraph()
        for key in (b'bad',struct.pack('<HHI',0xFFFF,0x52,7)):
            with self.subTest(key=key),self.assertRaises(ValueError):
                drought.query_descriptor53_objects(graph.core,graph.context,key,
                    read=graph.memory.read,native_calls=graph.native_calls)
        with self.assertRaises(ValueError):
            drought.query_descriptor53_objects(graph.core,graph.context,KEY,
                read=graph.memory.read,native_calls=dict(graph.native_calls,
                                                       query_pair=lambda *args:1))
        self.assertEqual(graph.order,[])


if __name__ == '__main__':
    unittest.main()

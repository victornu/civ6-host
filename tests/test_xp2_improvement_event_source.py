"""Exact installed-source and shared query/codec fixtures, no engine execution."""
import ctypes as C
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_improvement_event_source as source
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.native import native_event_a625c726 as improvement_query
from civ6_host.runtime.native import native_event_5d0f4014 as route_query
import test_xp2_turn_notifications as composed


def inputs(kind, memory, position=(3,4)):
    address = 0xa30000
    memory.put(address,struct.pack('<ii',*position))
    scalar = lambda tag,value:struct.pack('<IIQII',tag,0,value,0,0)
    fields = {0xa1e5a149:scalar(3,0xa5eea1c0),
              0x8c468e3c:struct.pack('<IIQII',0,0,address,8,0x21000001)}
    if kind == source.ROUTE_CHANGED:
        fields.update({0xd6fcf3e4:scalar(2,12),0xa1fbc372:scalar(2,11)})
    return fields


def guard_options(owner, kind):
    options = dict(normalizer_transform_present=False,thread_hook_present=False,
        writer_metadata_callback_present=False,padding_policy='zero-unread-empty-receiver-payload',
        empty_receiver_state=owner.empty_receiver_state)
    if kind == source.IMPROVEMENT_CHANGED:
        options['entity_listener_count'] = owner.entity_listener_count
    return options


class ImprovementSourceTests(unittest.TestCase):
    def test_exact_full_source_selection_and_dependency_hashes(self):
        p = source.source()
        self.assertEqual(len(p['functions']),42)
        self.assertEqual(len(p['callsites']),8)
        self.assertEqual(p['contract']['policy'],'shared-native-query-and-fifo')
        self.assertFalse(p['contract']['omission_admitted'])
        self.assertEqual(dict(source.event_profile().record_sizes),{144:144,153:128})
        self.assertIn(source.SOURCE[1],source.source_dependencies().values())
        # Independent image read confirms every Core byte, including all unwind
        # fragments and the second return after the builder's first RET.
        sys.path.insert(0,str(resource_root()/'tools'))
        from extract_phase31_next_export import pefile
        pe = pefile.PE(p['images']['core']['path'],fast_load=True)
        self.addCleanup(pe.close)
        calls=[]
        def read(address,size):
            self.assertLessEqual(size,4096)
            calls.append((address,size))
            return pe.get_data(address-0x190000000,size)
        self.assertEqual(source.verify_live(0x190000000,read),len(calls))
        for at in (0x5fab12,0x5fad0f,0x376310):
            def changed(address,size):
                raw=bytearray(read(address,size));index=0x190000000+at-address
                if 0 <= index < size:raw[index]^=1
                return bytes(raw)
            with self.assertRaisesRegex(ValueError,'live producer'):
                source.verify_live(0x190000000,changed)

    def test_typed_callsites_records_and_receiver_mutations_are_rejected(self):
        def replace_text(p,key,rva,text):
            for fragment in p['functions'][key]['capture']['fragments']:
                for row in fragment['instructions']:
                    if row.get('rva') == hex(rva):row['text']=text;return
            raise AssertionError('missing exact source instruction')
        for mutate in (
            lambda p:p['families']['0x30ae2a3d']['fields'].__setitem__('0xa1e5a149',2),
            lambda p:p['families']['0x7b65ff2e'].__setitem__('record_type',152),
            lambda p:p['callsites'][0].__setitem__('return_consumed',True),
            lambda p:p['contract'].__setitem__('omission_admitted',True),
            lambda p:p['receiver_rows']['0x90'].__setitem__('handler_rva','0xd9850'),
            lambda p:replace_text(p,'core_0x9a0000',0x9a0079,'mov dword ptr [rbx], 2'),
            lambda p:replace_text(p,'core_0x5fac20',0x5facbb,'call 0x1809a0000'),
            lambda p:replace_text(p,'core_0x5faa50',0x5faada,'call 0x180000000'),
        ):
            p=json.loads((resource_root()/source.SOURCE[0]).read_text())
            mutate(p)
            with self.assertRaises(ValueError):source._verify(p)

    def test_existing_codecs_copy_exact_typed_fields_and_refuse_unknowns(self):
        values={}
        class Memory:
            def put(self,address,raw):values[address]=raw
            def read(self,address,size):return values[address][:size]
        memory=Memory()
        for kind in source.KINDS:
            raw=inputs(kind,memory,(-3,4))
            decoded=source.decode_fields(kind,raw,memory.read)
            values.clear()
            self.assertEqual(decoded.position_bytes if kind == source.IMPROVEMENT_CHANGED
                             else decoded['position_bytes'],struct.pack('<ii',-3,4))
            for key in raw:
                changed=dict(raw);bad=bytearray(changed[key]);bad[0]=3 if key != 0xa1e5a149 else 2
                changed[key]=bytes(bad)
                with self.assertRaises(ValueError):source.decode_fields(kind,changed,memory.read)
        with self.assertRaises(ValueError):source.decode_fields(0x12345678,{},memory.read)


class ImprovementQueriesTests(unittest.TestCase):
    def graph(self):
        g=composed.XP2ComposedNotifications().graph()
        def cleanup():
            if g.owner.quarantined or g.owner.empty_receiver_state != g.owner._receiver_profile:
                # A failed native producer/changed receiver intentionally cannot
                # claim a clean close. This fixture owns no engine allocation.
                with self.assertRaises(RuntimeError):g.owner.close()
            else:g.owner.close()
        self.addCleanup(cleanup)
        from civ6_host.runtime.foundation_facade_profiles import query_abi
        abi=query_abi(XP2_CORE_SHA256,resource_root())
        # Preserve the real publication/continuation/A0 owners and use the
        # already-qualified ten-entry facade graph. Only native calls are fake.
        objects={'outer':g.backend.context}
        from civ6_host.runtime.xp2_turn_notification_source import TABLES
        objects.update({name:0x800000+0x1000*i for i,name in enumerate(TABLES) if name!='outer'})
        objects['type_service']=objects['data'];objects['position']=0xb00000
        for name in abi.tables:
            if name not in objects:continue
            g.memory.q(objects[name],g.memory.core_base+abi.table(name))
        g.memory.q(objects['position']+8,0xb01000)
        for op in abi.operations.values():
            if 'table' in op:g.memory.q(g.memory.core_base+abi.table(op['table'])+op['slot'],g.memory.core_base+op['rva'])
        # Read-only installed PE fallback fills complete source code, while
        # fixture memory owns relocation-adjusted vtables/cache/objects.
        sys.path.insert(0,str(resource_root()/'tools'))
        from extract_phase31_next_export import pefile
        pe=pefile.PE(source.source()['images']['core']['path'],fast_load=True)
        self.addCleanup(pe.close)
        old=g.memory.read
        def read(address,size):
            if size>4096:raise AssertionError('reader bound exceeded')
            try:return old(address,size)
            except (KeyError,ValueError):
                rva=address-g.memory.core_base
                if 0<=rva<pe.OPTIONAL_HEADER.SizeOfImage:
                    raw=pe.get_data(rva,size)
                    if len(raw)==size:return raw
                raise
        g.owner.read=g.event.arguments.reader.read=read
        for rva,raw in source.core_fragments():g.memory.put(g.memory.core_base+rva,raw)
        receipt=source.bind_owner(g.backend,g.backend.core,read)
        self.assertIs(receipt.owner,g.backend)
        self.assertIs(source.bind_owner(g.backend,g.backend.core,read),receipt)
        original_factory=g.factory;g.fail_query=None;g.overrun=False
        live={name:0 for name in ('map','plot','component','type_service','game','position','player')}
        acquire={'outer_map':'map','get_plot':'plot','plot_component':'component',
                 'outer_service':'type_service','get_player':'player','outer_game':'game','position_service':'position'}
        release={'release_'+name:name for name in ('map','plot','component','game','position','player')}
        release['release_service']='type_service'
        from civ6_host.runtime import turn_unit_event_profile as turn
        addresses={g.memory.core_base+op['rva']:name for name,op in abi.operations.items()}
        selected=turn.select_specs(XP2_CORE_SHA256,{n:(0,None,()) for n in
            ('plot_component','release_component','component10','component18','component30','plotc8','plotc0','plote0')})
        addresses.update({g.memory.core_base+values[0]:name for name,values in selected.items()})
        def factory(result,*types):
            fallback=original_factory(result,*types)
            def bind(target):
                name=addresses.get(target)
                if name is None:return fallback(target)
                original=fallback(target)
                def invoke(*values):
                    g.calls.append((name,values))
                    if name==g.fail_query:raise RuntimeError('fixture native query failed')
                    if name in acquire:
                        label=acquire[name];live[label]+=1;return objects[label]
                    if name in release:
                        label=release[name];self.assertEqual(values[0],objects[label])
                        self.assertGreater(live[label],0);live[label]-=1;return None
                    if name in ('plot_snapshot178','plot_snapshot180'):
                        raw=bytearray(24)
                        if name.endswith('180'):
                            struct.pack_into('<h',raw,4,-5);raw[11]=1;raw[12]=3;raw[17]=6
                        else:struct.pack_into('<I',raw,4,44);raw[20]=2
                        C.memmove(values[1],bytes(raw),24)
                        if g.overrun:C.memset(values[1]+24,0,1)
                        return 0
                    if name=='position_value':self.assertEqual(C.string_at(values[1],8),struct.pack('<ii',3,4));return 0x100000003
                    if name=='position_flag':return 1
                    return original(*values)
                return invoke
            return bind
        g.factory=factory;g.live=live;g.objects=objects
        return g

    def produce(self,g,kind,sequence):
        fields=source.decode_fields(kind,inputs(kind,g.memory),g.owner.read)
        from civ6_host.runtime import xp1_load_capability as capability
        with composed.pending_civilization_render(),patch.object(C,'WINFUNCTYPE',g.factory),capability.capability_source_scope(g.backend,'continuation'):
            if kind==source.IMPROVEMENT_CHANGED:
                values=improvement_query.query_native_values_at_position(g.backend.core,g.backend.context,
                    fields.position_bytes,read=g.owner.read,core_sha256=XP2_CORE_SHA256)
            else:
                values=route_query.query_descriptor(g.backend.core,g.backend.context,fields,
                    read=g.owner.read,core_sha256=XP2_CORE_SHA256)
        self.assertFalse(any(g.live.values()))
        return source.encode_record(kind,sequence,fields,values,**guard_options(g.owner,kind))

    def enable(self,g):
        from civ6_host.runtime import a0_foundation_events as foundation
        from civ6_host.runtime import a0_improvement_changes as admission
        b=g.backend;stage,prefix=b.stage,b.prefix
        b.stage='prepared';b.prefix=None
        try:
            foundation.enable(g.owner,b)
            admission.enable(g.owner,b)
        finally:
            b.stage=stage;b.prefix=prefix
        self.assertIs(g.owner.improvement_change_profile,source.event_profile())

    def dispatch(self,g,kind):
        from civ6_host.runtime import xp1_load_capability as capability
        with composed.pending_civilization_render(),patch.object(C,'WINFUNCTYPE',g.factory),capability.capability_source_scope(g.backend,'continuation'):
            return g.owner.dispatch(kind,inputs(kind,g.memory),0)

    def test_shared_queries_preserve_real_owner_releases_and_exact_record_payloads(self):
        g=self.graph()
        self.enable(g)
        self.assertEqual(self.dispatch(g,source.IMPROVEMENT_CHANGED),0)
        self.assertEqual(self.dispatch(g,source.ROUTE_CHANGED),0)
        first,second=g.event.deferred.pending
        self.assertEqual(struct.unpack_from('<III',first),(144,144,1))
        self.assertEqual(struct.unpack_from('<III',second),(128,153,2))
        self.assertEqual(struct.unpack_from('<IIIIIII',first,104),(6,1,8,12,777,0xfffffffb,10))
        self.assertEqual(struct.unpack_from('<iiQII',second,96),(1,12,0x100000003,11,12))
        self.assertEqual(second[120:124],bytes((1,1,1,1)))
        releases=[name for name,_ in g.calls if isinstance(name,str) and name.startswith('release_')]
        self.assertEqual(releases[-5:],['release_map','release_position','release_game','release_service','release_plot'])
        self.assertTrue(g.config_calls)
        self.assertFalse(any(g.live.values()))
        self.assertIsNone(g.owner._foundation_borrow)
        self.assertEqual(g.event.deferred.drain(),2)
        self.assertEqual(g.event.deferred.pending,[])
        self.assertEqual(g.event.deferred.consumed_count,2)

    def test_failure_and_canary_preserve_releases_no_record_no_synthetic_result(self):
        for kind,failure,overrun in ((source.IMPROVEMENT_CHANGED,'component18',False),
                                    (source.ROUTE_CHANGED,'position_flag',False),
                                    (source.ROUTE_CHANGED,None,True)):
            g=self.graph();self.enable(g);g.fail_query=failure;g.overrun=overrun
            with self.assertRaises((ValueError,RuntimeError)):self.dispatch(g,kind)
            self.assertFalse(any(g.live.values()))
            self.assertEqual(g.event.deferred.pending,[])
            self.assertTrue(g.owner.quarantined)
            self.assertIsNone(g.owner._foundation_borrow)

    def test_shared_encoder_optional_hooks_receiver_and_native_values_remain_strict(self):
        g=self.graph()
        # API-level encoding still executes the shared source-guarded query.
        for kind in source.KINDS:
            record=self.produce(g,kind,1)
            self.assertEqual(struct.unpack_from('<II',record),(source.SIZES[source.KINDS[kind]],source.KINDS[kind]))
            fields=source.decode_fields(kind,inputs(kind,g.memory),g.owner.read)
            options=guard_options(g.owner,kind)
            for key in ('normalizer_transform_present','thread_hook_present','writer_metadata_callback_present'):
                bad={**options,key:True}
                with self.assertRaises(ValueError):source.encode_record(kind,1,fields,None,**bad)
            with self.assertRaises(ValueError):source.encode_record(kind,1,fields,None,**options)

    def test_foreign_borrower_and_nonempty_receiver_fail_before_queries(self):
        for change in ('borrower','receiver'):
            g=self.graph();self.enable(g)
            if change=='borrower':g.backend._xp1_continuation=object()
            else:g.owner.empty_receiver_state['subscriber_count']=1
            before=list(g.calls)
            with self.assertRaises((ValueError,RuntimeError)):self.dispatch(g,source.IMPROVEMENT_CHANGED)
            self.assertEqual(g.calls,before)
            self.assertEqual(g.event.deferred.pending,[])
            self.assertIsNone(g.owner._foundation_borrow)

    def test_source_receipt_requires_original_core_engine_and_byte_identity(self):
        g=self.graph()
        with self.assertRaisesRegex(ValueError,'owner mismatch'):source.bind_owner(g.backend,object(),g.owner.read)
        old=g.backend.load_abi
        from types import SimpleNamespace
        g.backend.load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256)
        with self.assertRaisesRegex(ValueError,'owner mismatch'):source.bind_owner(g.backend,g.backend.core,g.owner.read)
        g.backend.load_abi=old
        g.memory.put(g.memory.core_base+0x5fab12,b'\0')
        with self.assertRaisesRegex(ValueError,'live producer'):source.bind_owner(g.backend,g.backend.core,g.owner.read)


if __name__=='__main__':unittest.main()

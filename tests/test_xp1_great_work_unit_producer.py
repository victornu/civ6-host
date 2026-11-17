"""Exact XP1 unit producer source, shared argument owner, descriptor and FIFO."""
from contextlib import contextmanager
from copy import deepcopy
import struct
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import pefile

from civ6_host.runtime import a0_foundation_events as foundation, xp1_great_work_source as source
from civ6_host.runtime.a0_family_source import family_profile
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native import native_event_great_work as codec
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.xp1_continuation import SavedContinuation
import test_a0_family_service as family_fixtures
from test_a0_family_service import scalar


class XP1GreatWorkUnitProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = family_profile()

    def graph(self):
        fixture = family_fixtures.A0FamilyServiceTests()
        fixture.profile = self.profile
        self.addCleanup(fixture.doCleanups)
        host, deferred, arguments, owner, reader, _, _ = fixture.fixture(execution_image=_XP1_PROFILE)
        image = pefile.PE(str(_XP1_PROFILE.path), fast_load=True)
        self.addCleanup(image.close)
        backend = OfficialLoadBackend.__new__(OfficialLoadBackend)
        backend.host, backend.core, backend.context = host, deferred.core, deferred.context
        backend.prefix, backend.stage = None, 'prepared'
        backend._xp1_commands_requested = True
        backend.load_abi = SimpleNamespace(core_sha256=XP1_CORE_SHA256)
        backend.thread = threading.get_ident()
        backend.poisoned = backend.destroyed = False
        backend.runtime = SimpleNamespace(thread=threading.get_ident, read=reader.read)
        token = SavedContinuation.__new__(SavedContinuation)
        token.owner = backend
        backend._xp1_continuation = token
        position, descriptor = 0x90000, 0x90010
        memory = {position:struct.pack('<ii',3,4), descriptor:struct.pack('<HHI',0,1,0xffffffff)}
        reader.read.side_effect = lambda address,size: (
            memory[address][:size] if address in memory else image.get_data(address-backend.core._handle,size))
        fields = {0x8c468e3c:struct.pack('<H6xQII',0,position,8,0x21000001),
                  0xa1e5a149:scalar(3,0), 0xa1fbc372:scalar(2,7), 0xd6fcf3e4:scalar(2,11),
                  0xf0548bb7:struct.pack('<H6xQII',1024,descriptor,8,0x21000001)}
        reader.fields.return_value = fields
        with patch('civ6_host.runtime.foundation_facade_profiles.verify_xp1_once'):
            foundation.enable(owner,backend)
        calls=[]

        @contextmanager
        def plot(core,context,decoded,*,read,include_flag148,core_sha256):
            self.assertEqual((core,context,read),(backend.core,backend.context,reader.read))
            self.assertEqual((include_flag148,core_sha256),(False,XP1_CORE_SHA256))
            self.assertEqual(decoded['position_bytes'],memory[position])
            before=len(deferred.pending)
            calls.append('borrow')
            yield dict(owner=0,city_id=44,district_id=0)
            self.assertEqual(len(deferred.pending),before+1)
            calls.append('release')

        self.enterContext(patch.object(SavedContinuation,'check',autospec=True))
        self.enterContext(patch('civ6_host.runtime.xp1_visibility_cache_gate.require_internal_cache',
                                return_value={'callback_gate_enabled':True}))
        self.enterContext(patch('civ6_host.runtime.native.native_event_07c83dae.plot_snapshot',plot))
        return SimpleNamespace(host=host,deferred=deferred,arguments=arguments,owner=owner,reader=reader,
                               backend=backend,token=token,image=image,memory=memory,position=position,
                               descriptor=descriptor,fields=fields,calls=calls)

    def test_full_source_pins_retain_legacy_and_both_installed_producers(self):
        legacy = source.source(_XP1_PROFILE)
        extra = source.unit_source(_XP1_PROFILE)
        self.assertEqual(legacy['contract']['descriptor_id'],0xffffffff)
        self.assertEqual(extra['contract']['descriptor_id_bits'],32)
        self.assertEqual(sum(row['length'] for row in extra['producer']['fragments']),504)
        self.assertEqual(len(extra['consumer_full_bodies_reused']),6)
        pins = source.source_dependencies(_XP1_PROFILE)
        self.assertTrue({source.SOURCE[1],source.UNIT_PRODUCER_SOURCE[1],source.RECEIVER_SOURCE[1]}.issubset(pins.values()))
        for image in (None,deepcopy(_XP1_PROFILE)):
            with self.assertRaisesRegex(ValueError,'registered Rise and Fall'):
                source.unit_source(image)

    def test_real_owner_copies_full_dword_and_owner_word_then_drains_fifo(self):
        g = self.graph()
        ids = (0xffffffff,0,1,65543,0x7fffffff,0x80000000,0xfffffffe)
        records=[]
        for sequence,identifier in enumerate(ids,1):
            owner_word = (0,63,0xffff)[(sequence-1)%3]
            raw=struct.pack('<HHI',owner_word,1,identifier)
            g.memory[g.descriptor]=raw
            self.assertEqual(g.arguments.dispatch(g.host.pointer,codec.EVENT_KIND,0x9000),0)
            record=g.deferred.pending[-1]
            self.assertEqual(struct.unpack_from('<III',record),(160,220,sequence))
            self.assertEqual(record[144:152],raw)
            self.assertEqual(struct.unpack_from('<ii',record,88),(3,4))
            self.assertEqual(struct.unpack_from('<HHI',record,96),(0,2,44))
            self.assertEqual(struct.unpack_from('<I',record,116)[0],7)
            self.assertEqual(struct.unpack_from('<I',record,136)[0],11)
            self.assertEqual(g.owner._foundation_borrow,None)
            records.append(record)
        g.memory[g.descriptor]=b'\0'*8
        self.assertEqual(g.deferred.pending,records)
        self.assertEqual(g.calls,['borrow','release']*len(ids))
        self.assertEqual(g.deferred.drain(),len(ids))
        self.assertEqual((g.deferred.consumed_count,g.deferred.pending),(len(ids),[]))
        events=[call.kwargs for call in g.owner.emit.call_args_list
                if call.args and call.args[0]=='native_deferred_host_event_enqueued']
        self.assertEqual(len(events),len(ids))
        self.assertTrue(all(e['source_proof_sha256']==source.UNIT_PRODUCER_SOURCE[1] for e in events))

    def test_types_selector_field_set_tags_and_sizes_still_refuse_before_plot(self):
        for mutation in ('type0','type2','typeffff','selector','tag','size','missing','extra'):
            with self.subTest(mutation=mutation):
                g=self.graph()
                if mutation.startswith('type'):
                    kind={'type0':0,'type2':2,'typeffff':0xffff}[mutation]
                    g.memory[g.descriptor]=struct.pack('<HHI',0,kind,65543)
                elif mutation=='selector':g.fields[0xa1e5a149]=scalar(3,1)
                elif mutation=='tag':g.fields[0xf0548bb7]=struct.pack('<H6xQII',3,g.descriptor,8,0x21000001)
                elif mutation=='size':g.fields[0xf0548bb7]=struct.pack('<H6xQII',1024,g.descriptor,4,0x21000001)
                elif mutation=='missing':del g.fields[0xd6fcf3e4]
                else:g.fields[0x12345678]=scalar(2,1)
                with self.assertRaises((ValueError,RuntimeError)):
                    g.owner.dispatch(codec.EVENT_KIND,g.fields,0)
                self.assertEqual((g.calls,g.deferred.pending,g.owner._foundation_borrow),([],[],None))
                self.doCleanups()

    def test_live_unit_old_producer_and_builder_byte_mismatches_refuse(self):
        image=pefile.PE(str(_XP1_PROFILE.path),fast_load=True)
        self.addCleanup(image.close)
        core=SimpleNamespace(_handle=0x190000000,_civ6_host_execution_image=_XP1_PROFILE)
        read=lambda address,size:image.get_data(address-core._handle,size)
        source.verify_live(core,read)
        for site in (0x177fa0,0x178001,0x178129,0x178186,0x17818b,0x2955e2,0x5186f1):
            def corrupt(address,size,site=site):
                raw=bytearray(read(address,size));offset=core._handle+site-address
                if 0<=offset<len(raw):raw[offset]^=1
                return bytes(raw)
            with self.subTest(site=hex(site)),self.assertRaisesRegex(ValueError,'live.*producer differs'):
                source.verify_live(core,corrupt)

    def test_exact_borrower_and_owned_empty_receiver_are_still_required(self):
        g=self.graph()
        with self.assertRaisesRegex(ValueError,'active native borrower'):
            source.dispatch(g.owner,g.fields)
        g.token.owner=object()
        with self.assertRaisesRegex(ValueError,'exact synchronous continuation'):
            g.owner.dispatch(codec.EVENT_KIND,g.fields,0)
        g.token.owner=g.backend
        g.owner.empty_receiver_state['subscriber_count']=1
        with self.assertRaises((ValueError,RuntimeError)):
            g.owner.dispatch(codec.EVENT_KIND,g.fields,0)
        self.assertEqual((g.calls,g.deferred.pending,g.owner._foundation_borrow),([],[],None))


if __name__ == '__main__':
    unittest.main()

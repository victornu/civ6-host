"""History/era codecs on the actual saved owner, producer and deferred FIFO."""
import ast
import hashlib
from pathlib import Path
import struct
import unittest
from test_xp1_placement_events import Fixture as PlacementFixture, LAB
from test_xp1_turn_a0 import scalar
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime import game_history_event_profile as source
from civ6_host.runtime import a0_game_history_events as events
from civ6_host.runtime.native import native_scalar_event_encoder as shared
from civ6_host.runtime.native import native_two_value_event_family as two
from civ6_host.runtime.native.native_deferred_empty_profile import validate_empty_profile_record


class Fixture(PlacementFixture):
    def set_active(self,value):
        # The inherited fixture constructs SavedLoadOwner via __new__. Supply
        # _bind_loaded's exact identities once, before its first real guard.
        if not hasattr(self.saved,'_engine_sha256'):
            self.saved._engine_sha256=XP1_CORE_SHA256
            self.backend._saved_stage_owner=self.saved
        return super().set_active(value)


def fields(a=7,b=0xffffffff):
    return {0xa1e5a149:scalar(3,0),0xd6fcf3e4:scalar(2,a),0xa1fbc372:scalar(2,b)}


class GameHistoryTests(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_actual_saved_owner_two_kinds_preserve_scope_and_single_fifo_consumption(self):
        f=self.fixture();f.deferred.host_notification_counter=2;f.deferred.host_metadata_counter=17
        before_fields=fields()
        for sequence,(kind,(record,flag,*_)) in enumerate(source.EVENTS.items(),1):
            with self.subTest(kind=hex(kind)):
                self.assertEqual(f.owner.dispatch(kind,before_fields,0),0)
                self.assertEqual(len(f.deferred.pending),1)
                data=f.deferred.pending[0]
                self.assertEqual(struct.unpack_from('<4I',data),(96,record,sequence,0))
                self.assertEqual(struct.unpack_from('<I',data,72)[0],flag)
                self.assertEqual(struct.unpack_from('<3I',data,80),(sequence,7,0xffffffff))
                self.assertEqual(data[92:],bytes(4))
                self.assertEqual((f.owner.host_notification_counter,f.owner.host_metadata_counter),(2,17))
                self.assertEqual(f.deferred.drain(),1)
                self.assertEqual(f.deferred.consumed_count,sequence)
                self.assertIsNone(f.owner._foundation_borrow)
                self.assertIsNone(f.owner.active_kind)
        self.assertEqual(before_fields,fields());self.assertEqual(f.calls,[])
        self.assertEqual(f.deferred.drain(),0)
        self.assertFalse(f.owner.handles_kind(0x4082a91e))
        self.assertFalse(f.owner.handles_record(0x106))
        emitted=[r for stage,r in f.emitted if stage=='native_deferred_host_event_enqueued'
                 and r.get('dispatch_kind') in ('0x4710f1a4','0xf50673b7')]
        self.assertEqual(len(emitted),2)
        self.assertEqual([r['source_proof_sha256'] for r in emitted],[source.SOURCE[1],source.ERA_SOURCE[1]])

    def test_reject_malformed_fields_before_enqueue_and_keep_borrow_cleanup(self):
        f=self.fixture();bad=fields();del bad[0xa1fbc372]
        with self.assertRaisesRegex(ValueError,'argument keys'):
            f.owner.dispatch(source.HISTORY_KIND,bad,0)
        self.assertEqual(f.deferred.pending,[]);self.assertEqual(f.deferred._sequence,0)
        self.assertTrue(f.owner.quarantined);self.assertIsNone(f.owner._foundation_borrow)
        for mode in ('selector','tag','flags','extra','optional','transform','metadata'):
            with self.subTest(mode=mode):
                raw=fields();args=dict(normalizer_transform_present=False,optional_callback_present=False,queue_metadata_service=None)
                if mode=='selector':raw[0xa1e5a149]=scalar(3,1)
                if mode=='tag':raw[0xd6fcf3e4]=scalar(3,7)
                if mode=='flags':
                    v=bytearray(raw[0xd6fcf3e4]);struct.pack_into('<I',v,20,1);raw[0xd6fcf3e4]=bytes(v)
                if mode=='extra':raw[1]=scalar(2,0)
                if mode=='optional':args['optional_callback_present']=True
                if mode=='transform':args['normalizer_transform_present']=True
                if mode=='metadata':args['queue_metadata_service']=object()
                with self.assertRaises(ValueError):events.encode(source.HISTORY_KIND,raw,1,**args)

    def test_installed_governor_establishment_preserves_descriptor_and_scalar_order(self):
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        from civ6_host.runtime.xp1_governors_source import ESTABLISHED

        ptr = 0x1234000
        copied = struct.pack('<HHI', 4, 2, 65536)
        reads = []

        def read(address, size):
            reads.append((address, size))
            return copied

        raw = fields(7, 9)
        raw[0x23739f42] = struct.pack('<H6xQII', 1024, ptr, 8, 0x21000001)
        record = events.encode(ESTABLISHED, raw, 2,
            normalizer_transform_present=False, optional_callback_present=False,
            queue_metadata_service=None, core_sha256=XP1_CORE_SHA256, read=read)
        self.assertEqual(reads, [(ptr, 8)])
        self.assertEqual(struct.unpack_from('<4I', record), (112, 0xe3, 2, 0))
        self.assertEqual(struct.unpack_from('<HHIII', record, 88), (4, 2, 65536, 7, 9))
        self.assertEqual(record[104:], bytes(8))
        state = dict(observer_registered=False, state_pointer_nonnull=True, pre_hook=None,
                     post_hook=None, subscriber_count=0, state_flags=0, execution_image=_XP1_PROFILE)
        self.assertEqual(validate_empty_profile_record(record, **state)['event_name'],
                         'GameCoreEvent::GovernorEstablished')

    def test_installed_turn_history_scalar_record_uses_selected_empty_receiver(self):
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        from civ6_host.runtime.xp1_turn_history_source import KIND

        record = events.encode(KIND, fields(0, 10), 3, normalizer_transform_present=False,
                               optional_callback_present=False, queue_metadata_service=None)
        self.assertEqual(struct.unpack_from('<4I', record), (96, 0x10b, 3, 0))
        self.assertEqual(struct.unpack_from('<I', record, 72), (6,))
        self.assertEqual(struct.unpack_from('<3I', record, 80), (3, 0, 10))
        state = dict(observer_registered=False, state_pointer_nonnull=True, pre_hook=None,
                     post_hook=None, subscriber_count=0, state_flags=0, execution_image=_XP1_PROFILE)
        row = validate_empty_profile_record(record, **state)
        self.assertEqual(row['handler_va'], '0x1400d4670')
        with self.assertRaises(ValueError):
            validate_empty_profile_record(record, **dict(state, subscriber_count=1))

    def test_installed_age_family_uses_exact_public_session_fifo(self):
        from civ6_host.runtime import xp1_player_age_source as age
        from civ6_host.runtime.a0_family_source import A0FamilyProfile
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        import pefile

        f = self.fixture()
        core = f.backend.core
        core._civ6_host_execution_image = _XP1_PROFILE
        pe = pefile.PE(_XP1_PROFILE.path, fast_load=True)
        self.addCleanup(pe.close)
        age.verify_live(core, lambda address, size: pe.get_data(address - core._handle, size))
        with self.assertRaisesRegex(ValueError, 'Live Rise and Fall player-age source differs'):
            age.verify_live(core, lambda address, size: bytes(size))
        self.assertIn(age.SOURCE[1], age.source_dependencies(_XP1_PROFILE).values())

        records = {kind: frozenset((record,)) for kind, (record, _) in age.EVENTS.items()}
        sizes = {record: age.SIZE for record, _ in age.EVENTS.values()}
        profile = A0FamilyProfile(records, sizes, age.SOURCE[1])
        f.owner.history_event_profile = f.owner._history_event_profile = profile
        f.deferred.host_notification_counter = 2
        f.deferred.host_metadata_counter = 3
        args = dict(normalizer_transform_present=False, optional_callback_present=False,
                    queue_metadata_service=None)
        short = {0xa1e5a149: scalar(3, 0), 0xd6fcf3e4: scalar(2, 0xffffffff)}
        for sequence, (kind, (record_type, flag)) in enumerate(age.EVENTS.items(), 1):
            with self.subTest(kind=hex(kind)):
                with self.assertRaisesRegex(ValueError, 'exact installed Rise and Fall'):
                    events.encode(kind, short, sequence, **args)
                with self.assertRaisesRegex(ValueError, 'argument keys'):
                    events.encode(kind, fields(), sequence, execution_image=_XP1_PROFILE, **args)
                with self.assertRaisesRegex(ValueError, 'selector-zero'):
                    events.encode(kind, {**short, 0xa1e5a149: scalar(3, 1)}, sequence,
                                  execution_image=_XP1_PROFILE, **args)
                self.assertEqual(f.owner.dispatch(kind, short, 0), 0)
                record, = f.deferred.pending
                self.assertEqual(struct.unpack_from('<IIQ', record), (96, record_type, sequence))
                self.assertEqual(struct.unpack_from('<I', record, 72), (flag,))
                self.assertEqual(struct.unpack_from('<3I', record, 80), (sequence, 0xffffffff, 0))
                state = dict(f.owner.empty_receiver_state, execution_image=_XP1_PROFILE)
                self.assertEqual(validate_empty_profile_record(record, **state)['handler_va'],
                                 age.receiver_row(record_type)['handler_va'])
                with self.assertRaisesRegex(ValueError, 'subscriber'):
                    validate_empty_profile_record(record, **dict(state, subscriber_count=1))
                self.assertEqual(f.deferred.drain(), 1)
        self.assertEqual((f.owner.host_notification_counter, f.owner.host_metadata_counter), (2, 3))
        self.assertEqual(f.deferred.consumed_count, len(age.EVENTS))
        self.assertIsNone(f.owner._foundation_borrow)
        self.assertEqual(f.calls, [])

    def test_live_source_foreign_owner_and_receiver_listeners_are_refused(self):
        f=self.fixture()
        self.assertEqual(f.saved._engine_sha256,XP1_CORE_SHA256)
        self.assertIs(f.backend._saved_stage_owner,f.saved)
        for owner,field,value in ((f.saved,'_engine_sha256',XP2_CORE_SHA256),
                                  (f.backend,'_saved_stage_owner',object())):
            original=getattr(owner,field);setattr(owner,field,value)
            try:
                with self.assertRaisesRegex(ValueError,'original live backend graph'):
                    f.set_active(True)
            finally:setattr(owner,field,original)
        f.saved._check_active()
        source.bind_owner(f.backend,f.backend.core,f.read)
        with self.assertRaisesRegex(ValueError,'owner mismatch'):source.bind_owner(f.backend,object(),f.read)
        # The bounded fixture must cover the complete requested instruction;
        # a one-byte block would intentionally fall back to immutable PE data.
        f.memory.put(f.memory.base+0x519650,b'\x90'*5)
        with self.assertRaisesRegex(ValueError,'live source changed'):source.bind_owner(f.backend,f.backend.core,f.read)
        data=events.encode(source.HISTORY_KIND,fields(),1,normalizer_transform_present=False,
            optional_callback_present=False,queue_metadata_service=None)
        for key,value in (('subscriber_count',1),('pre_hook',1),('post_hook',1),('observer_registered',True),
                          ('state_pointer_nonnull',False),('state_flags',2)):
            state={**f.owner.empty_receiver_state,key:value}
            with self.subTest(key=key),self.assertRaises(ValueError):validate_empty_profile_record(data,**state)
        f.owner.empty_receiver_state['subscriber_count']=1
        with self.assertRaisesRegex(RuntimeError,'receiver or registration'):
            f.owner.dispatch(source.HISTORY_KIND,fields(),0)
        self.assertEqual(f.deferred.pending,[])

    def test_source_closure_closed_catalogs_and_extracted_algorithms_unchanged(self):
        source.verify_source()
        for path,expected in source.source_dependencies().items():
            with Path(path).open('rb') as stream:self.assertEqual(hashlib.file_digest(stream,'sha256').hexdigest(),expected)
        self.assertEqual(len(shared.SCALAR_EVENT_CANDIDATES),38);self.assertEqual(len(two.MEMBERS),25)
        for kind in source.EVENTS:
            with self.assertRaises(ValueError):shared.candidate_for(kind)
            with self.assertRaises(ValueError):two.decode_core_fields(kind,fields())
        old=ast.parse((LAB/'civ6rl/native_scalar_event_encoder.py').read_text(encoding='utf8'))
        new=ast.parse(Path(shared.__file__).read_text(encoding='utf8'))
        old_f={n.name:n for n in old.body if isinstance(n,ast.FunctionDef)}
        new_f={n.name:n for n in new.body if isinstance(n,ast.FunctionDef)}
        for original,extracted in (('decode_core_fields','_decode_profile_fields'),('encode_record','_encode_profile_record')):
            before=[n for n in old_f[original].body if not isinstance(n,ast.Assign)
                    or ast.unparse(n)!='row = candidate_for(event_kind)']
            self.assertEqual([ast.dump(n) for n in before],[ast.dump(n) for n in new_f[extracted].body])
        self.assertIn('candidate_for(event_kind)',ast.unparse(new_f['encode_record']))


if __name__=='__main__':unittest.main()

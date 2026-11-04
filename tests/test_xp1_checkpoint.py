"""Selected Save bodies on the actual saved owner/FIFO; no engine is loaded."""
from copy import deepcopy
import ctypes as C
import importlib.util
import inspect
from pathlib import Path
import struct
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from test_xp1_world_input_owner import Fixture
from civ6_host.runtime import xp1_checkpoint_profile as profile
from civ6_host.runtime.native import native_checkpoint_diagnostic as installed_diagnostic
from civ6_host.runtime.native import native_checkpoint_retained_save as installed_retained
from civ6_host.runtime.native.native_session_checkpoint import run_sequence

HOST = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('checkpoint_hook', HOST/'tools/extraction_xp1_checkpoint.py')
hook = importlib.util.module_from_spec(spec); spec.loader.exec_module(hook)
NATIVE_CALLBACK = C.WINFUNCTYPE


def transformed(name, module):
    if name == hook.MODULES[0] and 'core_sha256' in inspect.signature(module.bind_save).parameters:
        return module
    if name == hook.MODULES[1] and 'selected_checkpoint' in inspect.getsource(module.NativeRetainedSaveBackend.validate_return):
        return module
    key = '_test_xp1_checkpoint_'+name.rsplit('.', 1)[-1]
    result = ModuleType(key); result.__file__ = module.__file__; sys.modules[key] = result
    source = hook.parameterize(name, Path(module.__file__).read_text(encoding='utf8'))
    exec(compile(source, module.__file__, 'exec'), result.__dict__)
    return result


class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diagnostic = transformed(hook.MODULES[0], installed_diagnostic)
        cls.retained = transformed(hook.MODULES[1], installed_retained)
        cls.retained.diagnostic = cls.diagnostic

    def fixture(self):
        f = Fixture(); self.addCleanup(f.close)
        inner = int.from_bytes(f.read(f.backend.context+8, 8), 'little')
        f.memory.put(inner, struct.pack('<Q', f.memory.base+profile.XP1.inner_vtable_rva))
        # The actual composed fixture has no enabled private notification bank.
        # Admission is explicit and its absent state is measured, not installed.
        self.assertIsNone(f.owner.private_notification_profile)
        return f

    def factory(self, f, backend=None, initialized=True):
        def callback(result, *args):
            def bind(target):
                if callable(target):
                    return NATIVE_CALLBACK(result, *args)(target)
                if target == f.memory.base+profile.XP1.initialized_rva:
                    def get(context):
                        self.assertEqual(context, f.backend.context)
                        f.machine.append(('initialized',)); return initialized
                    return get
                if target == f.memory.base+profile.XP1.outer_save_rva:
                    def save(context, stream):
                        self.assertEqual((context, stream), (f.backend.context, backend.stream.pointer))
                        f.machine.append(('save',))
                        data = C.create_string_buffer(b'\x05\0\0\0native-save-fixture')
                        backend.stream._write(C.addressof(data), len(data)-1)
                        return 0
                    return save
                raise AssertionError('Unexpected machine address '+hex(target))
            return bind
        return callback

    def test_source_and_base_independence(self):
        self.assertEqual(profile.verify_source()['image']['sha256'], profile.XP1_CORE_SHA256)
        self.assertIn(profile.SOURCE[1], profile.source_dependencies().values())
        with patch.object(profile, '_source', side_effect=AssertionError('Base loaded XP1 source')):
            self.assertIs(profile.save_abi(profile.BASE_CORE_SHA256), profile.BASE)
            self.assertEqual(profile.provider_proof(profile.BASE_CORE_SHA256), installed_retained.provider.PROOF_SHA256)
        with self.assertRaises(ValueError): profile.save_abi('unknown')

    def test_shared_bind_uses_xp1_bodies_and_rejects_bad_slots_or_initialization(self):
        f = self.fixture()
        with patch.object(C, 'WINFUNCTYPE', self.factory(f)):
            call, identity = self.diagnostic.bind_save(f.backend.prefix, f.memory, core_sha256=profile.XP1_CORE_SHA256)
        self.assertTrue(callable(call))
        self.assertEqual(identity['game'], int.from_bytes(f.read(identity['inner']+96, 8), 'little'))
        self.assertEqual(f.machine, [('initialized',)])
        with patch.object(C, 'WINFUNCTYPE', self.factory(f, initialized=False)):
            with self.assertRaisesRegex(RuntimeError, 'initialization getter'):
                self.diagnostic.bind_save(f.backend.prefix, f.memory, core_sha256=profile.XP1_CORE_SHA256)
        f.memory.put(f.memory.base+profile.XP1.outer_vtable_rva+0x168, struct.pack('<Q', f.memory.base+profile.BASE.outer_save_rva))
        with self.assertRaisesRegex(RuntimeError, 'virtual targets'):
            self.diagnostic.bind_save(f.backend.prefix, f.memory, core_sha256=profile.XP1_CORE_SHA256)

    def test_actual_control_rejects_pending_fifo_foreign_graph_and_missing_private_admission(self):
        f = self.fixture(); p = f.backend.prefix
        read = lambda: self.diagnostic.check_control_boundary(p, f.read,
            core_sha256=profile.XP1_CORE_SHA256, allow_uninitialized_private=True)
        before = deepcopy(f.memory.blocks); observed = read()
        self.assertEqual(observed['processor_flags'], [0, 0, 0, 0])
        self.assertEqual(observed['public_sequence'], observed['consumed_count'])
        self.assertEqual(f.memory.blocks, before)
        with self.assertRaisesRegex(RuntimeError, 'initialized private'):
            self.diagnostic.check_control_boundary(p, f.read, core_sha256=profile.XP1_CORE_SHA256)
        f.token.transport.pending.append(b'pending')
        with self.assertRaises((RuntimeError, ValueError)): read()
        f.token.transport.pending.clear()
        p.backend.prefix = object()
        with self.assertRaisesRegex(ValueError, 'exact XP1 owner'): read()

    def test_initialized_private_bank_is_the_real_a0_owner_bank(self):
        f = self.fixture()
        from civ6_host.runtime import a0_private_notifications as private
        # DeferredService.__init__ stores this selected engine; the retained
        # earlier world-input fixture did not yet exercise the private bank.
        f.deferred.cache_core_sha256 = f.backend.load_abi.core_sha256
        private.enable(f.owner)
        ring = private.get_ring(f.owner)
        read = lambda: self.diagnostic.check_control_boundary(f.backend.prefix, f.read,
            core_sha256=profile.XP1_CORE_SHA256)
        value = read()
        self.assertEqual(value['private_selector'], ring.selector)
        self.assertEqual(value['private_cursors'], list(ring.cursors))
        ring._cursors[ring.selector & 1] = 128
        with self.assertRaisesRegex(RuntimeError, 'consumed private'): read()

    def test_shared_sequence_real_stream_selected_jobs_configuration_proof_and_closed_lifetime(self):
        f = self.fixture(); test = self; retained = self.retained
        class Backend(retained.NativeRetainedSaveBackend):
            core_sha256 = profile.XP1_CORE_SHA256
            def enter(self):
                f.set_active(True)
            def observe(self):
                f.saved._check_active()
                return (id(f.backend), f.backend.context, id(f.token))
            def state(self):
                f.saved._check_active()
                return deepcopy(f.token.observation)
            def publish(self, data, configuration, receipt, control, before, after):
                test.assertTrue(self.stream.transport.closed)
                test.assertEqual(before, after)
                return dict(data=data, configuration=configuration, control=control)
            def finish(self):
                f.backend.snapshot_phase='idle'; f.set_active(False)
        b = Backend.__new__(Backend)
        b.owner=f.backend; b.prefix=f.backend.prefix; b.memory=f.memory
        b.attempted=b.native_call_attempted=False; b.stream=b.save_call=None
        b.allow_uninitialized_private=True; b.stream_call_limit=100
        f.backend.streams=[]
        raw=b'configuration-fixture'
        receipt=dict(operation='serialize', bytes=len(raw), sha256=retained.sha(raw),
            proof_sha256=profile.provider_proof(profile.XP1_CORE_SHA256),
            native_return_interpreted=False, identity_checked_before_after=True)
        with patch.object(C,'WINFUNCTYPE',self.factory(f,b)), \
                patch.object(retained.provider,'serialize_provider',return_value=(raw,receipt)) as provider:
            result=run_sequence(b,f.emit)
        self.assertEqual(result['data'],b'\x05\0\0\0native-save-fixture')
        self.assertEqual(f.machine,[('initialized',),('save',),('initialized',)])
        self.assertEqual(provider.call_count,1)
        self.assertEqual(len(f.backend.streams),1)
        self.assertTrue(b.stream.transport.closed)
        self.assertFalse(f.backend.busy)
        self.assertEqual(f.token.publication_count,0)
        self.assertEqual(f.token.transport.pending,[])
        with self.assertRaisesRegex(RuntimeError,'cannot be retried'): run_sequence(b,f.emit)
        wrong=dict(receipt, proof_sha256=retained.provider.PROOF_SHA256)
        with patch.object(retained.provider,'serialize_provider',return_value=(raw,wrong)):
            with self.assertRaisesRegex(RuntimeError,'exact receipt'): b.serialize_configuration()


if __name__ == '__main__': unittest.main()

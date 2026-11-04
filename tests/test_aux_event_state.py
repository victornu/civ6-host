"""Snapshot state admission and strict refusal, with native calls stubbed."""
import ctypes as C
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from civ6_host.runtime.native.native_aux_map_adapter import NativeAuxMapAdapter
from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
from test_xp2_aux_maps import memory
from test_aux_map_profiles import retained,evaluate


class AuxEventStateTests(unittest.TestCase):
    def fixture(self,validator,refusal=None):
        m=memory({7:retained.scalar(2,17)})
        host=NS(LAB_AuxMapInstall=Mock(return_value=1),LAB_AuxMapTransportVersion=Mock(return_value=2))
        runtime=NS(registry=NS(contexts={},validate=Mock(side_effect=AssertionError('not a managed child'))))
        adapter=NativeAuxMapAdapter(host,runtime,NS(_handle=m.base),0x70000,Mock(),read=m.read,
            core_sha256=XP2_CORE_SHA256,state_validator=validator,on_refusal=refusal)
        adapter.install();self.addCleanup(adapter.close)
        return m,adapter,runtime

    def snapshot(self,m,adapter,state):
        output,count=C.c_void_p(),C.c_uint32()
        status=adapter._snapshot_callback(0x70000,state,m.map,0,C.pointer(output),C.pointer(count))
        return status,output.value,count.value

    def test_temporary_state_requires_fresh_scope_query_and_expires(self):
        active=[True];validator=Mock(side_effect=lambda state:active[0]);refusal=Mock()
        m,adapter,runtime=self.fixture(validator,refusal)
        status,pointer,count=self.snapshot(m,adapter,0x80000)
        self.assertEqual(status,1);self.assertEqual(evaluate(C.string_at(pointer,count*16)),{7:17})
        runtime.registry.validate.assert_not_called()
        active[0]=False
        self.assertEqual(self.snapshot(m,adapter,0x80000),(0,None,0))
        self.assertEqual(validator.call_count,2)
        refusal.assert_called_once();self.assertIn('event frame',refusal.call_args.args[0])

    def test_scope_query_cannot_resurrect_an_invalid_managed_child(self):
        validator=Mock(return_value=True);refusal=Mock()
        m,adapter,runtime=self.fixture(validator,refusal)
        runtime.registry.contexts[0x80000]=object()
        self.assertEqual(self.snapshot(m,adapter,0x80000),(0,None,0))
        validator.assert_not_called();refusal.assert_called_once()

    def test_nonboolean_scope_answer_and_query_errors_are_explicit_refusals(self):
        for answer in (1,None):
            validator=Mock(return_value=answer);refusal=Mock()
            m,adapter,_runtime=self.fixture(validator,refusal)
            self.assertEqual(self.snapshot(m,adapter,0x80000),(0,None,0))
            refusal.assert_called_once()
        validator=Mock(side_effect=RuntimeError('scope owner changed'));refusal=Mock()
        m,adapter,_runtime=self.fixture(validator,refusal)
        self.assertEqual(self.snapshot(m,adapter,0x80000),(0,None,0))
        self.assertIn('scope owner changed',refusal.call_args.args[0])


if __name__=='__main__':unittest.main()

"""Length/lifetime contract, with no game library loaded in these fixtures."""
import ctypes as C
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from civ6_host.runtime.native import native_locale_diagnostic as oracle


class NativeTextViewTests(unittest.TestCase):
    def lookup(self,explicit_length,*,oversized=False):
        text='Bâtisseur|Bâtisseurs'.encode('utf-8');storage=C.create_string_buffer(text)
        size=len('Bâtisseur'.encode('utf-8'));destroyed=[]
        class Fn:
            def __init__(self,name):self.name=name
            def __call__(self,*args):
                if self.name==oracle._LOOKUP:return args[0].value
                if self.name==oracle._TO_UTF8:
                    args[1]._obj.value=oracle._LOOKUP_MAX_BYTES+1 if oversized else size
                    return C.addressof(storage)
                if self.name==oracle._DESTROY:destroyed.append(True)
                return 1
        lib=SimpleNamespace(_handle=0x180000000)
        for name in oracle._EXPORT_RVAS:setattr(lib,name,Fn(name))
        addresses=lambda fn,typ:SimpleNamespace(value=lib._handle+oracle._EXPORT_RVAS[fn.name])
        try:
            with patch.object(oracle.C,'cast',side_effect=addresses):
                return oracle._native_lookup(lib,b'LOC_UNIT_BUILDER_NAME',explicit_length=explicit_length)
        finally:
            self.assertEqual(destroyed,[True])

    def test_exact_native_view_does_not_require_a_terminator_after_it(self):
        self.assertEqual(self.lookup(True),'Bâtisseur'.encode('utf-8'))
        with self.assertRaisesRegex(RuntimeError,'terminator'):
            self.lookup(False)  # historical behavior retained explicitly

    def test_native_length_bound_still_precedes_the_read(self):
        with self.assertRaisesRegex(RuntimeError,'bounds'):self.lookup(True,oversized=True)


if __name__=='__main__':unittest.main()

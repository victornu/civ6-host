import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace as NS,MappingProxyType
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime import xp1_load_options as options
from civ6_host.runtime.native import native_xp1_performance as performance


class RecordedOptionsTests(unittest.TestCase):
    def backend(self):
        return NS(owner=object(),captured_bundle=object(),busy=True,destroyed=False,check_thread=Mock(),
                  core=NS(_handle=0x180000000),runtime=NS(read=Mock()))

    def receipt(self,backend):
        with patch.object(options,'_owner'):return options.recorded_input(backend)

    def test_actual_frozen_sources_and_three_recorded_values(self):
        p,q=options.source_profile()
        self.assertIsInstance(p,MappingProxyType);self.assertIsInstance(q['contract']['keys'],tuple)
        backend=self.backend();receipt=self.receipt(backend)
        self.assertEqual(receipt.values,tuple((k,5) for k in options.KEYS))
        self.assertEqual(dict(receipt.raw_settings),dict.fromkeys(options.INPUTS,-1))
        self.assertFalse(p['capture_association']['atomic_performance_map_capture'])
        self.assertIn('log itself has no PID',p['capture_association']['association_kind'])
        deps=options.source_dependencies()
        self.assertTrue(all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha for path,sha in deps.items()))

    def test_recorded_input_is_not_automatic_derivation_or_legacy_diagnostic(self):
        with self.assertRaisesRegex(ValueError,'Automatic hardware'):
            performance.derive(dict.fromkeys(options.INPUTS,-1))
        self.assertEqual(set(performance.derive(dict(zip(options.INPUTS,(2,1,0,1,1))))['values'].values()),{1})
        backend=self.backend();receipt=self.receipt(backend);borrower=options._LoadOptionsBorrower(backend)
        with patch.object(options,'_owner'):
            self.assertEqual(set(options.recorded_values(receipt,borrower).values()),{5})
            with self.assertRaisesRegex(ValueError,'exact native borrower'):
                options.recorded_values(receipt,options._LoadOptionsBorrower(self.backend()))

    def test_wrong_input_log_or_capture_join_is_refused(self):
        backend=self.backend();original=options._snapshot
        def changed(p,name):
            value=original(p,name)
            return value.replace('Game Core Thread Count = 5.','Game Core Thread Count = 1.')
        with patch.object(options,'_owner'),patch.object(options,'_snapshot',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'native Performance value differs'):options.recorded_input(backend)

    def test_pinned_consumers_use_only_interface_getter_before_variant_read(self):
        p,_=options.source_profile()
        self.assertEqual(set(p['consumers']),{'unit','trade'})
        for body in p['consumers'].values():
            rows=[row['text'] for fragment in body['fragments'] for row in fragment['instructions']]
            self.assertEqual([row for row in rows if row.startswith('call ')],
                             ['call 0x1800426e0','call qword ptr [r8 + 0x68]'])
            index=rows.index('call qword ptr [r8 + 0x68]')
            self.assertEqual(rows[index-2:index],['mov rcx, rax','mov r8, qword ptr [rax]'])
            self.assertEqual(rows[index+1],'mov edx, dword ptr [rax + 0x14]')

    def test_uncertain_native_allocation_is_quarantined(self):
        backend=self.backend();receipt=self.receipt(backend);borrower=options._LoadOptionsBorrower(backend)
        borrower._invoke=Mock(side_effect=RuntimeError('native allocation uncertain'))
        count=len(performance._QUARANTINE)
        with patch.object(options,'_owner'),patch.object(performance,'verify_code'):
            with self.assertRaisesRegex(performance.UnsafeOwnership,'construction uncertain'):
                performance.PerformanceDomain(borrower,root=options.resource_root(),recorded_input=receipt)
        self.assertEqual(len(performance._QUARANTINE),count+1)
        self.assertTrue(performance._QUARANTINE[-1].poisoned)

    def test_strict_proxy_keeps_borrowed_native_values_and_refuses_unknown(self):
        service=options._OptionsService();service._check=Mock()
        service.backend=NS(host=NS(_check=Mock(),emit=Mock()));service.object=(C.c_void_p*1)(123)
        service.provider=NS(pointer=0x1000,snapshot=Mock())
        raw=struct.pack('<I4xQ8x',2,5)
        service.borrower=NS(_invoke=Mock(return_value=0x2000),read=Mock(return_value=raw))
        service.input=NS(values=tuple((key,5) for key in options.KEYS));service.domain_calls=service.value_calls=0
        service.observed_keys=set()
        self.assertEqual(service.get_domain(123,options.DOMAIN),C.addressof(service.object))
        self.assertEqual(service.get_value(C.addressof(service.object),options.KEYS[0]),0x2000)
        for key in (0,True,-1,0xffffffff):
            with self.assertRaisesRegex(ValueError,'receiver/key'):
                service.get_value(C.addressof(service.object),key)
        with self.assertRaisesRegex(ValueError,'domain'):service.get_domain(123,0)
        self.assertEqual(service.borrower._invoke.call_count,1)
        service.borrower.read.return_value=struct.pack('<I4xQ8x',2,1)
        with self.assertRaisesRegex(ValueError,'native value changed'):
            service.get_value(C.addressof(service.object),options.KEYS[0])

    def test_reused_owner_calls_original_constructor_three_setters_and_getters(self):
        backend=self.backend();receipt=self.receipt(backend);borrower=options._LoadOptionsBorrower(backend)
        memory={};values={};calls=[]
        def read(address,size):
            if address in memory:return memory[address][:size]
            return C.string_at(address,size)
        borrower.read=read;backend.runtime.read=read
        def invoke(rva,result,arg_types,*args):
            calls.append((rva,args));pointer=args[0]
            if rva==0x844460:
                C.memmove(pointer,struct.pack('<Q',borrower.base+0x93f590),8);return pointer
            if rva==0x845e90:
                values[args[1]]=args[2];C.memmove(pointer+0x50,struct.pack('<I',len(values)),4);return 0x1234
            if rva==0x845600:
                address=0x100000+args[1];memory[address]=struct.pack('<I4xQ8x',2,values[args[1]]);return address
            if rva==0x844580:return None
            raise AssertionError(hex(rva))
        borrower._invoke=invoke
        with patch.object(options,'_owner'),patch.object(performance,'verify_code'), \
             patch.object(performance,'derive',side_effect=AssertionError('candidate called derive')):
            owner=performance.PerformanceDomain(borrower,root=options.resource_root(),recorded_input=receipt)
            self.assertEqual([rva for rva,args in calls],[0x844460]+[0x845e90]*3+[0x845600]*3)
            self.assertEqual(set(owner.snapshot().values()),{5})
            owner.bound=True
            with self.assertRaisesRegex(ValueError,'outlive the Core context'):owner.close()
            owner.close(context_destroyed=True)
            self.assertEqual(calls[-1][0],0x844580)
            self.assertTrue(owner.closed)

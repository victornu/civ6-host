"""Shared owner paths with XP2 source selection; native memory/calls are fixtures.

The pending generated Performance owner is rendered in memory from the retained
module and this group's transformation. No generated product file is rewritten.
"""
import ctypes as C
from pathlib import Path
import struct
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp1_load_capability as capability, xp1_load_options as options
from civ6_host.runtime import xp2_load_options_capability_profile as selected
from civ6_host.runtime.configuration_profiles import configuration_abi, _body
from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.native import native_app_ownership as ownership
from extraction_xp1_load_options import parameterize
from extraction_xp1_load_capability import select_candidate_profile


def rendered_performance():
    module=ModuleType('civ6_host.runtime.native._xp2_performance_fixture')
    module.__package__='civ6_host.runtime.native'
    raw=(resource_root()/'civ6rl/native_xp1_performance.py').read_text()
    exec(compile(parameterize('civ6rl.native_xp1_performance',raw),'<in-memory Performance extraction>','exec'),module.__dict__)
    return module


class XP2OptionsCapabilityTests(unittest.TestCase):
    def test_performance_selector_uses_captured_abi_with_explicit_runtime_identity(self):
        from civ6_host.runtime.execution_images import select, known_path
        image=select('xp2-gamecore-current-092abfbb',
                     core_path=known_path('xp2-gamecore-current-092abfbb'))
        b=self.backend()
        b.profile=NS(core_sha256=image.image_sha256,
                     source_core_sha256=image.reference_core_sha256)
        fallback=Mock(side_effect=AssertionError('XP1 fallback must not handle XP2'))
        self.assertEqual(selected.performance_select(options._LoadOptionsBorrower(b),
            resource_root(),fallback),selected.performance_profile()[1])
        fallback.assert_not_called()
        b.profile=NS(core_sha256=image.image_sha256,source_core_sha256='unknown')
        with self.assertRaisesRegex(ValueError,'Unknown Performance'):
            selected.performance_select(options._LoadOptionsBorrower(b),resource_root(),fallback)

    def backend(self):
        from civ6_host.runtime.xp2_saved_init import REFERENCE
        b=NS(profile=NS(core_sha256=XP2_CORE_SHA256), owner=NS(), captured_bundle=NS(reference=REFERENCE),
             busy=True,destroyed=False,stage='prepared',prefix=None,check_thread=Mock(),
             core=NS(_handle=0x180000000),runtime=NS(read=Mock()))
        return b

    def test_source_has_exact_extended_catalogue_and_real_provider(self):
        p=selected.source();c,caller=capability.source_profile(core_sha256=XP2_CORE_SHA256)
        self.assertEqual(len(c['catalogue_rows']),97)
        self.assertEqual(caller['host_global_rva'],0xb8aa80)
        self.assertEqual(c['slots']['0x68']['target_rva'],0x99f680)
        self.assertEqual(c['configuration_vtable_rva'],configuration_abi(XP2_CORE_SHA256).vtable_rva)
        self.assertEqual(len(p['capabilities']['closed_registry_extension']['additional_rows']),5)
        self.assertFalse(p['capabilities']['closed_registry_extension']['base_profile_reused_as_whitelist'])
        with self.assertRaisesRegex(ValueError,'Unknown capability'):capability.source_profile(core_sha256='unknown')

    def test_actual_receipt_cache_uses_xp2_player_keys_live_code_and_labels(self):
        b=self.backend()
        with patch.object(capability,'_owner'):
            receipt=capability._bind_source_receipt(b)
            self.assertEqual(len(receipt.player_keys),64)
            self.assertIn(0x4887e,dict(receipt.live_code))
            self.assertNotIn(0x3f75e,dict(receipt.live_code))
            with capability.capability_source_scope(b,'install'):
                self.assertIs(capability.source_profile(b),receipt.profile)
                for row in selected.source()['capabilities']['closed_registry_extension']['additional_rows']:
                    details=capability.candidate_details(b,0,row['hash_u32'])
                    self.assertEqual(details['catalogue_name'],row['name'])
                    self.assertEqual(details['candidate_family'],'xp2-lan')
                    self.assertIsNone(details['base_catalogue_sha256'])
                self.assertEqual(capability.candidate_player_key(b.owner,0,b),receipt.player_keys[0])
            with self.assertRaisesRegex(ValueError,'active verified owner'):capability.source_profile(b)

    def test_real_shared_mode_algorithm_reads_xp2_both_native_getters(self):
        b=self.backend();app=b.owner;app.base=b.core._handle;app.pointer=0x10000
        app._configuration_abi=configuration_abi(XP2_CORE_SHA256);table=app.base+app._configuration_abi.vtable_rva
        memory={app.pointer:struct.pack('<Q',table),table+0x58:struct.pack('<Q',app.base+0x99f570),
                table+0x68:struct.pack('<Q',app.base+0x99f680),app.base+0xb8c400:struct.pack('<I',0x871d5b63),
                app.base+0xb8c44c:struct.pack('<I',0x0623e593),0x20000:struct.pack('<H6xQ4xI',10,0x30000,0x05000000),
                0x30000:struct.pack('<Q',table),0x40000:struct.pack('<H6xQ4xI',2,0x0138409a,0)}
        app.read=lambda address,size:memory[address][:size]
        app.call=Mock(side_effect=lambda address,*args:0x20000 if address==app.base+0x99f570 else 0x40000)
        with patch.object(capability,'_owner'):
            capability._bind_source_receipt(b)
            with capability.capability_source_scope(b,'install'):
                self.assertEqual(capability.read_mode(app,b),0x0138409a)
                self.assertEqual([x.args[0] for x in app.call.call_args_list],[app.base+0x99f570,app.base+0x99f680])
                memory[table+0x68]=struct.pack('<Q',app.base+0x845600)
                with self.assertRaisesRegex(ValueError,'mode provider changed'):capability.read_mode(app,b)

    def test_explicit_host_input_cannot_be_replayed_as_recorded_xp1(self):
        b=self.backend();borrower=options._LoadOptionsBorrower(b)
        with patch.object(options,'_owner'):
            receipt=options.explicit_input(b)
            self.assertEqual(options.recorded_values(receipt,borrower),dict.fromkeys(options.KEYS,1))
            self.assertEqual(receipt.kind,'explicit_host_configuration')
            b.profile=NS(core_sha256=capability.XP1_CORE_SHA256)
            with self.assertRaisesRegex(ValueError,'values changed'):options.recorded_values(receipt,borrower)

    def test_rendered_shared_native_owner_uses_all_xp2_operations_and_code_guards(self):
        performance=rendered_performance();b=self.backend();borrower=options._LoadOptionsBorrower(b)
        memory={};values={};calls=[]
        _,proof=selected.performance_profile()
        for body in [proof['xp1_consumer'],proof['xp1_dispatch'],proof['xp1_numeric_setter'],
                     *proof['xp1_owner_bodies'].values(),*proof['xp1_getter_bodies'].values()]:
            for fragment in _body(body)['fragments']:
                for row in fragment['instructions']:memory[b.core._handle+int(row['va'],16)-0x180000000]=bytes.fromhex(row['bytes'])
        for slot,rva in proof['contract']['slots'].items():memory[b.core._handle+0xabf080+int(slot,16)]=struct.pack('<Q',b.core._handle+rva)
        def read(address,size):
            if address in memory:return memory[address][:size]
            return C.string_at(address,size)
        borrower.read=read;b.runtime.read=read
        def invoke(rva,result,argspec,*args):
            calls.append(rva);pointer=args[0]
            if rva==0x99e4b0:C.memmove(pointer,struct.pack('<Q',b.core._handle+0xabf080),8);return pointer
            if rva==0x99fee0:
                values[args[1]]=args[2];C.memmove(pointer+0x50,struct.pack('<I',len(values)),4);return pointer
            if rva==0x99f680:
                address=0x100000000+args[1];memory[address]=struct.pack('<I4xQ8x',2,values[args[1]]);return address
            if rva==0x99e5d0:return None
            raise AssertionError('Wrong native operation '+hex(rva))
        borrower._invoke=invoke
        with patch.object(options,'_owner'):
            receipt=options.explicit_input(b)
            owner=performance.PerformanceDomain(borrower,root=resource_root(),recorded_input=receipt)
            self.assertEqual(calls,[0x99e4b0]+[0x99fee0]*3+[0x99f680]*3)
            self.assertTrue(owner.derived['explicit_host_configuration'])
            self.assertNotIn('recorded_native_values',owner.derived)
            owner.bound=True
            with self.assertRaisesRegex(ValueError,'outlive'):owner.close()
            owner.close(context_destroyed=True)
            self.assertEqual(calls[-1],0x99e5d0)
            # A real live-code comparison, not an outer SHA-only gate.
            memory[b.core._handle+0x99f680]=b'\x90'*len(memory[b.core._handle+0x99f680])
            with self.assertRaisesRegex(ValueError,'native code differs'):performance.verify_code(b.core._handle,read,proof)

    def test_existing_closed_status_admits_new_named_rows_but_refuses_unknown(self):
        b=self.backend();p=selected.source();obj=ownership.ClosedBaseOwnership.__new__(ownership.ClosedBaseOwnership)
        obj.application=b.owner;obj.candidate_backend=b;obj.required_mode=0x0138409a;obj.mode_name='LAN'
        obj.allowed=frozenset(p['capabilities']['admitted_capability_hashes']);obj.restricted=frozenset();obj.entries=()
        obj.lan_branch=NS(details=Mock(return_value={'category':3}))
        with patch.object(capability,'_owner'),patch.object(ownership,'read_application_mode',return_value=0x0138409a):
            capability._bind_source_receipt(b)
            with capability.capability_source_scope(b,'install'):
                for row in p['capabilities']['closed_registry_extension']['additional_rows']:
                    self.assertEqual(obj.status(0,row['hash_u32'])[0],1)
                with self.assertRaisesRegex(ValueError,'unsupported content'):obj.status(0,0)

    def test_pending_shared_registry_constructor_selects_exact_97_real_database(self):
        pending=ModuleType('civ6_host.runtime.native._xp2_ownership_fixture')
        pending.__package__='civ6_host.runtime.native'
        raw=Path(ownership.__file__).read_text()
        rendered=raw if "expected_count = catalogue.get('admitted_count', 92)" in raw else select_candidate_profile(raw)
        exec(compile(rendered,'<in-memory ownership selection>','exec'),pending.__dict__)
        p=selected.source();c=p['capabilities'];b=self.backend()
        catalogue={'capabilities':c['catalogue_rows'],'admitted_count':97,
                   'profile_name':'official-captured-xp2-lan-candidate',
                   'fixture':{'gameplay_database_sha256':c['catalogue_database']['sha256']}}
        manifest={'databases':{'gameplay':{'path':c['catalogue_database']['path']}}}
        with patch.object(capability,'captured_catalogue',return_value=catalogue), \
             patch.object(capability,'verify_candidate_live'), \
             patch.object(pending,'read_fixed_inventory',return_value=tuple({'present':i<35} for i in range(65))), \
             patch.object(pending,'read_application_mode',return_value=0x0138409a), \
             patch.object(pending,'ClosedLanBranch',return_value=NS(details=Mock(return_value={'category':3}))):
            result=pending.ClosedBaseOwnership(b.owner,Path('.'),manifest,required_mode=0x0138409a,
                                              captured_bundle=b.captured_bundle,candidate_backend=b)
            self.assertEqual(len(result.allowed),97)
            self.assertEqual(result.database_profile,'official-captured-xp2-lan-candidate')
            catalogue['admitted_count']=92
            with self.assertRaisesRegex(ValueError,'names/types differ'):
                pending.ClosedBaseOwnership(b.owner,Path('.'),manifest,required_mode=0x0138409a,
                                            captured_bundle=b.captured_bundle,candidate_backend=b)


"""Source and argument guards for exact XP2 religious UnitOperations."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pefile
from lupa.lua51 import LuaError, LuaRuntime

from civ6_host.runtime import xp1_religious_unit_operations as adapter
from civ6_host.runtime import xp2_religious_unit_operations_source as source
from civ6_host.runtime import xp2_bundle_inputs, xp2_bbg_inputs
from civ6_host.runtime.execution_images import _PROFILE, _XP1_PROFILE
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.source_build_identity import (
    CURRENT_STRINGS_HOST_REFERENCE, CURRENT_UNSIGNED_LOG_HOST_REFERENCE,
)
from test_xp1_religious_unit_operations_runtime import _LUA


class GatheringStormReligiousOperationTests(unittest.TestCase):
    def test_dependencies_follow_exact_capture_and_engine(self):
        stock = xp2_bundle_inputs.REFERENCE
        bbg = xp2_bbg_inputs.REFERENCE
        self.assertTrue(adapter.supports(stock,_PROFILE))
        self.assertTrue(adapter.supports(bbg,_PROFILE))
        self.assertFalse(adapter.supports(stock,replace(_PROFILE)))
        self.assertFalse(adapter.supports(bbg,_XP1_PROFILE))
        self.assertFalse(adapter.supports(list(stock),_PROFILE))
        self.assertFalse(adapter.supports((stock[0],'0'*64),_PROFILE))
        self.assertEqual(adapter.source_for(_PROFILE),adapter.XP2_SOURCE)
        self.assertEqual(adapter.source_for(_XP1_PROFILE),adapter.SOURCE)
        for unknown in (None,(stock[0],'0'*64)):
            with self.assertRaisesRegex(ValueError,'capture'):
                adapter.source_dependencies(_PROFILE,reference=unknown)
        p_stock = adapter.source_dependencies(_PROFILE,reference=stock)
        p_bbg = adapter.source_dependencies(_PROFILE,reference=bbg)
        for pins,excluded,reference,host in (
            (p_stock,p_bbg,stock,CURRENT_UNSIGNED_LOG_HOST_REFERENCE),
            (p_bbg,p_stock,bbg,CURRENT_STRINGS_HOST_REFERENCE),
        ):
            self.assertIn(source.ORDINAL_SOURCE[1],pins.values())
            self.assertIn(_PROFILE.image_sha256,pins.values())
            for entry in (reference,host):
                key=str((resource_root()/entry[0]).resolve())
                self.assertEqual(pins[key],entry[1])
                self.assertNotIn(key,excluded)
        self.assertFalse(any('2865001760' in key for key in p_stock))
        self.assertTrue(any('2865001760' in key for key in p_bbg))
        self.assertIn('8fff3c3d0365ba2b6dd088d0f3c5f9a31ff069ec08613af99a8a4fe710b65331',p_stock.values())
        self.assertIn('7b38a8f1fb26d272278cd14b80abbe3b189a2474ec938c1ba7fff2edbcd9de83',p_bbg.values())
        self.assertNotIn('7b38a8f1fb26d272278cd14b80abbe3b189a2474ec938c1ba7fff2edbcd9de83',p_stock.values())

    def test_exact_installed_source_checks_real_pe_and_refuses_changed_manager(self):
        pe = pefile.PE(str(Path(_PROFILE.path)),fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        bad_address = base+0x9bf500+0xf8
        def read(address,size):
            return pe.get_data(address-base,size)
        with self.subTest('source and machine tables'):
            r = adapter.source.verify_live(base,read,image=_PROFILE)
            self.assertEqual(r['source_sha256'],adapter.XP2_SOURCE[1])
            self.assertGreater(r['complete_spans'],100)
            self.assertIs(r['native_execution'],False)
        def changed(address,size):
            return bytes(size) if address==bad_address else read(address,size)
        with self.assertRaisesRegex(ValueError,'operation manager table differs'):
            adapter.source.verify_live(base,changed,image=_PROFILE)

    def test_reused_request_refuses_stale_actual_gameinfo_ordinal_before_queue(self):
        action = dict(kind='evangelize_belief',unit_id=23,x=4,y=5)
        unit = dict(unit_id=23,x=4,y=5,moves_remaining=1.5,religion_type=2,spread_charges=3,
                    operations=[dict(operation=action['kind'],visible=True,available=True)])
        lua = LuaRuntime(encoding=None)
        bindings = lua.globals()
        bindings.unit_rows = lua.table_from([lua.table_from([23,4,5,1.5,2,3])])
        bindings.inquisition = False
        bindings.observer = lambda:0
        bindings.can_start = lambda *_:True
        calls = []
        bindings.request = lambda uid,op:calls.append((uid,op))
        p = source.verify_source()
        for reference,capture in zip((xp2_bundle_inputs.REFERENCE,xp2_bbg_inputs.REFERENCE),p['databases']):
            row = capture['rows'][action['kind']]['type_definition']
            ordinal = source.expected_ordinal(reference,action['kind'])
            definitions = lua.table()
            definition = lua.table_from({
                b'OperationType':row['Type'].encode('ascii'), b'Hash':row['Hash'],
                b'Index':ordinal, b'VisibleInUI':True,
            })
            definitions[row['Type'].encode('ascii')] = definition
            bindings.definitions = definitions
            query = _LUA+adapter.request_source(unit,action,0,8,expected_ordinal=ordinal)
            with self.subTest(capture=capture['family']):
                calls.clear()
                self.assertEqual(lua.execute(query),b'submitted|'+str(ordinal).encode('ascii'))
                self.assertEqual(calls,[(23,row['Hash'])])
                definition[b'Index'] = ordinal+1
                with self.assertRaisesRegex(LuaError,'GameInfo index differs'):
                    lua.execute(query)
                self.assertEqual(calls,[(23,row['Hash'])])

    def test_flags_admit_only_the_selected_engine_and_reject_non_boolean(self):
        saved = SimpleNamespace(prefix=SimpleNamespace(
            core=SimpleNamespace(_civ6_host_execution_image=_PROFILE),
            ui_child=object(), actions=SimpleNamespace(pending=[]),
            deferred_events=SimpleNamespace(pending=[]),
        ),_check_query=lambda: None)
        with patch.object(adapter.source,'bind_prefix') as bind:
            for xp1,xp2 in ((False,False),(True,False),(True,True),(False,1),(0,True)):
                with self.subTest(xp1=xp1,xp2=xp2), self.assertRaisesRegex(ValueError,'engine owner'):
                    saved.xp1_religious_unit_operations=xp1
                    saved.xp2_religious_unit_operations=xp2
                    adapter._bind(saved)
            bind.assert_not_called()
            saved.xp1_religious_unit_operations=False
            saved.xp2_religious_unit_operations=True
            self.assertIs(adapter._bind(saved),saved.prefix)
            bind.assert_called_once_with(saved.prefix,action=False)


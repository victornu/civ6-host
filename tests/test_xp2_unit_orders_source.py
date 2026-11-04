"""XP2 order registration/transport/UI/owner checks; no native engine calls."""
import hashlib
from pathlib import Path
import struct
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_unit_orders_source as selected
from civ6_host.runtime import xp2_initial_choice_source as status
from civ6_host.runtime.configuration_profiles import _source,_copy,XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.native import native_saved_unit_orders as shared
from test_xp2_action_transport import Memory
from test_xp2_initial_choices import populate
from test_xp1_unit_orders import LuaRuntime,LUA_SETUP


class OrderMemory(Memory):
    base=0x260000000
    def __init__(self):
        super().__init__()
        populate(self.put,self.base,status.source('status'))
        self.order=selected.source()
        for p in (self.order,_source(selected.TRANSPORT_SOURCE)):
            for body in p['functions'].values():
                for f in body['fragments']:self.put(self.base+int(f['start_rva'],16),bytes.fromhex(f['raw_hex']))
        for name,row in self.order['bindings'].items():
            self.put(self.base+int(row['name_va'],16)-0x180000000,name.split('.')[1].encode()+b'\0')
        for rva,row in self.order['literals'].items():self.put(self.base+int(rva,16),bytes.fromhex(row['raw_hex']))
        self.put(self.base+selected.COMMAND_TABLE[0],b''.join(struct.pack('<Q',self.base+r) for r in selected.COMMAND_TABLE[1]))


class XP2UnitOrdersSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=selected.source();cls.transport=_source(selected.TRANSPORT_SOURCE)

    def test_registered_pairs_and_archive_slots_match_independent_disk_pe(self):
        raw=Path(self.proof['image']['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),XP2_CORE_SHA256)
        pe=struct.unpack_from('<I',raw,0x3c)[0];sections=struct.unpack_from('<H',raw,pe+6)[0]
        section_at=pe+24+struct.unpack_from('<H',raw,pe+20)[0]
        def disk(rva,size):
            for i in range(sections):
                at=section_at+40*i;virtual_size,va,length,offset=struct.unpack_from('<IIII',raw,at+8)
                if va<=rva and rva+size<=va+length:return raw[offset+rva-va:offset+rva-va+size]
            raise AssertionError('Unmapped PE RVA')
        for p in (self.proof,self.transport):
            for body in p['functions'].values():
                for f in body['fragments']:
                    self.assertEqual(disk(int(f['start_rva'],16),f['length']),bytes.fromhex(f['raw_hex']))
        for name,row in self.proof['bindings'].items():
            text=name.split('.')[1].encode()+b'\0'
            self.assertEqual(disk(int(row['name_va'],16)-0x180000000,len(text)),text)
            load=next(r for r in row['registration_instructions'] if r['text'].startswith('lea rdx, [rip'))
            rva=int(load['rva'],16);instruction=disk(rva,7)
            self.assertEqual(instruction[:3],b'\x48\x8d\x15')
            self.assertEqual(rva+7+struct.unpack_from('<i',instruction,3)[0],selected.CALLBACKS[name])
        table,entries=selected.COMMAND_TABLE
        self.assertEqual(struct.unpack('<7Q',disk(table,56)),tuple(0x180000000+r for r in entries))
        self.assertEqual(self.transport['contracts']['command_message'],'0x493830af')
        self.assertEqual(dict(self.proof['contracts']['manager_slots']),dict(convert=0x90,can_start=0x48,execute=0x58,deserialize=0x98))

    def test_pins_include_ui_chain_prior_interval_and_selected_existing_services(self):
        pins=selected.source_dependencies()
        for digest in (selected.SOURCE[1],selected.TRANSPORT_SOURCE[1],selected.UI_SOURCE[1]):self.assertIn(digest,pins.values())
        self.assertTrue(any('xp2-action-transport' in path for path in pins))
        self.assertTrue(any('xp2-aux-map' in path for path in pins))
        self.assertTrue(any('native-session12' in path for path in pins))
        definitions, = (Path(path) for path, digest in pins.items() if digest == selected.SKIP_OPERATIONS_SHA256)
        import xml.etree.ElementTree as ET
        skip = ET.parse(definitions).find(".//UnitOperations/Row[@OperationType='UNITOPERATION_SKIP_TURN']")
        self.assertIsNotNone(skip)
        self.assertEqual((skip.get('VisibleInUI'), skip.get('HotkeyId')), ('true', 'SkipTurn'))
        ui=_source(selected.UI_SOURCE)
        self.assertEqual(ui['replacement_criteria'],'Expansion2')
        self.assertTrue(ui['replacement_has_overrides'])
        self.assertIn('Expansion2',ui['sources']['delegate']['path'])
        self.assertNotIn('GetUnitActionsTable',ui['replacement_overrides'])
        self.assertNotIn('OnUnitActionClicked',ui['replacement_overrides'])
        self.assertFalse(ui['spy_cancel_dialogue_admitted'])
        with self.assertRaises(ValueError):selected.verify_source(XP1_CORE_SHA256)

    def test_complete_body_name_literal_and_relocated_table_guards(self):
        memory=OrderMemory();self.assertGreater(selected.verify_live(memory.base,memory.read),0)
        self.assertLessEqual(max(size for _,size in memory.reads),4096)
        body=self.proof['functions']['0x6bb990'];tail=body['fragments'][-1]
        rvas=(int(tail['end_rva_exclusive'],16)-1,selected.COMMAND_TABLE[0]+0x20,
              int(self.proof['bindings']['Unit.GetFortifyTurns']['name_va'],16)-0x180000000,0x9c09f8)
        for rva in rvas:
            with self.subTest(rva=hex(rva)):
                memory.bytes[memory.base+rva]^=1
                try:
                    with self.assertRaises(ValueError):selected.verify_live(memory.base,memory.read)
                finally:memory.bytes[memory.base+rva]^=1
        for base in (True,0,-1):
            with self.assertRaises(ValueError):selected.verify_live(base,memory.read)
        with self.assertRaises(ValueError):selected.verify_live(memory.base,lambda at,size:b'')

    def test_source_contract_rejects_misbound_registrar_table_and_ui_claim(self):
        for reference,mutate in (
            (selected.SOURCE,lambda p:p['bindings']['Unit.GetFortifyTurns'].update(callback_rva='0x6bd020')),
            (selected.SOURCE,lambda p:p['contracts']['manager_slots'].update(deserialize=0x88)),
            (selected.SOURCE,lambda p:p['functions']['0xd0140']['fragments'][0].update(raw_hex='00')),
            (selected.TRANSPORT_SOURCE,lambda p:p['table']['entries'].__setitem__(4,'0x3a600')),
            (selected.TRANSPORT_SOURCE,lambda p:p['contracts'].update(command_message='0x8c0f3f36')),
            (selected.UI_SOURCE,lambda p:p.update(spy_cancel_dialogue_admitted=True)),
            (selected.UI_SOURCE,lambda p:p['replacement_overrides'].append('OnUnitActionClicked'))):
            changed=_copy(_source(reference));mutate(changed)
            with self.subTest(reference=reference[0]),patch.object(selected,'_source',side_effect=lambda ref:changed if ref==reference else _source(ref)):
                with self.assertRaises(ValueError):selected.source()

    def owner(self,memory):
        owner=OfficialLoadBackend.__new__(OfficialLoadBackend)
        owner.core=SimpleNamespace(_handle=memory.base);owner.load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)
        owner.thread=threading.get_ident();owner.runtime=SimpleNamespace(thread=threading.get_ident)
        owner.poisoned=owner.destroyed=False
        return owner

    def test_owned_status_operation_and_order_guards_compose_in_one_lifetime(self):
        memory=OrderMemory();owner=self.owner(memory)
        receipt=selected.bind_owner(owner,owner.core,memory.read)
        self.assertEqual(receipt.source_sha256,selected.SOURCE[1])
        self.assertEqual(receipt.transport_sha256,selected.TRANSPORT_SOURCE[1])
        self.assertEqual(owner._xp1_status_source_receipt.core_sha256,XP2_CORE_SHA256)
        self.assertLessEqual(max(size for _,size in memory.reads),4096)
        self.assertIs(selected.bind_owner(owner,owner.core,lambda *args:self.fail('cached lifetime reread')),receipt)
        foreign=self.owner(memory);foreign._xp2_unit_orders_source_receipt=receipt
        with self.assertRaisesRegex(ValueError,'another lifetime'):selected.bind_owner(foreign,foreign.core,memory.read)
        owner.poisoned=True
        with self.assertRaisesRegex(RuntimeError,'poisoned'):selected.bind_owner(owner,owner.core,memory.read)

    def test_shared_lua_remains_parameterless_with_native_legality_and_spy_refusal(self):
        # Exercise the actual shared Lua using its existing Base source gate;
        # root owns selection/admission, while this delivery proves delegation.
        for item in (*selected._COMMANDS,*selected._OPERATIONS):
            with self.subTest(item=item):
                lua=LuaRuntime(max_memory=4*1024*1024);lua.execute(LUA_SETUP)
                state=shared.parse_catalog(lua.execute(shared.catalog_source(0,8,include_cancel=True).decode()).encode(),0,8)
                action=next(a for a in shared.actions(state) if a['item_type']==item)
                self.assertEqual(lua.execute(shared.request_source(action,0,8,include_cancel=True).decode()),'submitted')
                self.assertEqual(lua.globals().requests,1)
        lua=LuaRuntime(max_memory=4*1024*1024);lua.execute(LUA_SETUP)
        lua.execute('moves=0; GameInfo.Units[3].Spy=true')
        state=shared.parse_catalog(lua.execute(shared.catalog_source(0,8,include_cancel=True).decode()).encode(),0,8)
        self.assertEqual({a['item_type'] for a in shared.actions(state)},{'UNITCOMMAND_WAKE'})

    def test_xp2_skip_uses_native_legality_and_rechecks_before_request(self):
        from civ6_host.contracts.capability_unit_orders import SKIP_TURN
        lua = LuaRuntime(max_memory=4*1024*1024)
        lua.execute(LUA_SETUP)
        lua.execute(f'GameInfo.UnitOperations.{SKIP_TURN}={{Hash=7,VisibleInUI=true}}')
        raw = lua.execute(shared.catalog_source(0, 8, core_sha256=XP2_CORE_SHA256).decode()).encode()
        action = next(a for a in shared.actions(shared.parse_catalog(raw, 0, 8)) if a['item_type'] == SKIP_TURN)
        request = shared.request_source(action, 0, 8, core_sha256=XP2_CORE_SHA256).decode()
        lua.execute('UnitManager.CanStartOperation=function(u,h,p,v,r) return v or h~=7 end')
        with self.assertRaisesRegex(Exception, 'order is stale or unavailable'):
            lua.execute(request)
        self.assertEqual(lua.globals().requests, 0)
        lua.execute('UnitManager.CanStartOperation=function() return true end')
        self.assertEqual(lua.execute(request), 'submitted')
        self.assertEqual(lua.globals().requests, 1)


if __name__=='__main__':unittest.main()

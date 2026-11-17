"""XP1 religion name transport with ABI doubles and synthetic wire fixtures."""

import ctypes as C
from hashlib import sha256
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp1_religion_name_transport as transport
from civ6_host.runtime import xp1_research_profile as research
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.native import native_player_operation_request as request


_BASE = 0x180000000
_OUTER = 0x120000
_TEXT = 'Église e\u0301 山 🌙'.encode('utf-8')
_SYNTHETIC_RELIGION = 0xAD12E773
_HEADER = struct.Struct('<6I')
_ENTRY = struct.Struct('<IHHHII')


def _scalar(key, value):
    return _ENTRY.pack(key,0,2,0,0,0) + struct.pack('<I',value)


# Assemble from the independently specified wire format, with a made-up
# religion hash. These fixtures contain no archive bytes from a played game.
_XP1_FOUNDATION = (_HEADER.pack(0xc45de12f,0,0xa4daffb5,0,0x80000001,2)
    + _scalar(0xac2fdc09,0x97fea5c6) + _scalar(0x22a25b8b,_SYNTHETIC_RELIGION))


def parameters(name=_TEXT):
    return {transport.PARAM_INSERT_MODE:transport.VALUE_EXCLUSIVE,transport.PARAM_RELIGION_TYPE:_SYNTHETIC_RELIGION,
            transport.PARAM_RELIGION_CUSTOM_NAME:name}


def fixture_archive(name=_TEXT, *, header=_XP1_FOUNDATION, entry_tail=None):
    """Build a synthetic three-entry record for the pure verification test."""
    if entry_tail is None:
        entry_tail = _ENTRY.pack(0x0addd95f,0,5,0,0x21000000 + len(name) + 1,1) + name + b'\0'
    return header[:20] + b'\3\0\0\0' + header[24:] + entry_tail


class Fixture:
    def __init__(self, name=_TEXT):
        self.name = name
        self.calls, self.cells = [], {}
        self.text_input = self.blob = None
        self.allowed = True
        self.alias = self.bad_count = self.changed_after_gate = False
        self.changed_after_request = self.null = self.request_error = False
        self.input_corrupt = False
        self.name_storage = self.reasons_storage = None
        self.core = SimpleNamespace(_handle=_BASE, _civ6_host_execution_image=_XP1_PROFILE)
        self.abi = research.player_operation_abi(transport.XP1_CORE_SHA256, request._METHODS)
        self.memory = {_OUTER:struct.pack('<Q',_BASE+self.abi.outer)}
        for table, slot, target in self.abi.slots:
            self.memory[_BASE+table+slot] = struct.pack('<Q',_BASE+target)
        for slot,target in transport._PROFILE_SLOTS.items():
            self.memory[_BASE+transport.VECTOR_VTABLE+slot] = struct.pack('<Q',_BASE+target)
        proof, archive = transport.verify_source()
        for table in archive['vtable_slots'].values():
            for row in table.values():
                self.memory[_BASE+row['rva']] = struct.pack('<Q',_BASE+row['target_rva'])
        spans = [row for name in transport._LIVE_BODIES
                 for row in proof['new_complete_code_spans'][name]['fragments']] + list(archive['body_spans'])
        for row in spans:
            rva = int(row['rva'],16) if type(row['rva']) is str else row['rva']
            self.memory[_BASE+rva] = bytes.fromhex(row['raw_hex'])
        self.api = {func:getattr(self,func) for func in self.abi.methods}
        self.api['set_cstring'] = self.set_cstring

    def read(self, address, size):
        if address in self.memory:
            return self.memory[address][:size]
        return C.string_at(address,size)

    def parameter_ctor(self,p):
        self.calls.append('parameter_ctor')
        self.name_storage=p
        C.memmove(p,struct.pack('<Q',_BASE+self.abi.parameters),8)
        return p

    def parameter_dtor(self,p):
        self.calls.append('parameter_dtor')
        self.cells.clear()
        self.blob=None

    def reason_ctor(self,p):
        self.calls.append('reason_ctor')
        self.reasons_storage=p
        C.memmove(p,struct.pack('<Q',_BASE+self.abi.reasons),8)
        return p

    def reason_dtor(self,p):
        self.calls.append('reason_dtor')

    def lookup(self,p,key):
        if key in self.cells:
            return C.addressof(self.cells[key])
        return None

    def set_u32(self,p,key,value):
        self.calls.append('set_u32')
        raw=struct.pack('<H6xI12x',2,value)
        self.cells[key]=C.create_string_buffer(raw,len(raw))
        return C.addressof(self.cells[key])

    def set_cstring(self,p,key,pointer):
        self.calls.append('set_cstring')
        self.text_input=pointer
        if C.string_at(pointer,len(self.name)+1) != self.name+b'\0':
            raise AssertionError('Caller changed the submitted bytes')
        if self.input_corrupt:
            C.memmove(pointer+len(self.name)+1,b'X',1)
        if self.null:
            return None
        self.blob=C.create_string_buffer(self.name+b'\0',len(self.name)+1)
        flags=0x21000000 + len(self.name) + 1 + int(self.bad_count)
        raw=struct.pack('<HH4xQII',5,0,pointer if self.alias else C.addressof(self.blob),1,flags)
        self.cells[key]=C.create_string_buffer(raw,len(raw))
        return C.addressof(self.cells[key])

    def verify_call(self, ctxt, player, operation, p):
        if (ctxt,player,operation,p)!=(_OUTER,0,transport.FOUND_RELIGION,self.name_storage):
            raise AssertionError('Caller changed native request identity')
        if C.string_at(self.text_input,len(self.name)+1)!=self.name+b'\0':
            raise AssertionError('Input no longer lives during native Request')
        if self.blob.raw!=self.name+b'\0':
            raise AssertionError('Map copy no longer lives during native Request')

    def can_start(self,ctxt,player,operation,p,visible,r):
        self.calls.append('can_start')
        self.verify_call(ctxt,player,operation,p)
        if (visible,r)!=(False,self.reasons_storage):
            raise AssertionError('CanStart used a foreign reason map')
        if self.changed_after_gate:
            C.memmove(C.addressof(self.blob),b'X',1)
        return self.allowed

    def request(self,ctxt,player,operation,p):
        self.calls.append('request')
        self.verify_call(ctxt,player,operation,p)
        if self.changed_after_request:
            C.memmove(C.addressof(self.blob),b'X',1)
        if self.request_error:
            raise RuntimeError('source-sized request exception')
        return None

    def invoke(self, **changes):
        values=dict(core=self.core,context=_OUTER,player=0,operation=transport.FOUND_RELIGION,
                    parameters=parameters(self.name),read=self.read,native_api=self.api,
                    core_sha256=transport.XP1_CORE_SHA256,allow_religion_name=True)
        values.update(changes)
        with patch.object(research,'verify_live',return_value=None):
            return request.request_player_operation(**values)


class ReligionNameTransportTests(unittest.TestCase):
    def test_copies_native_string_and_keeps_both_owned_values_alive(self):
        fixture=Fixture()
        result=fixture.invoke()
        self.assertEqual(fixture.calls,['parameter_ctor','set_u32','set_u32','set_cstring',
                                       'reason_ctor','can_start','request','reason_dtor','parameter_dtor'])
        self.assertTrue(result['request_invoked'])
        self.assertTrue(result['text_parameter_owned_copy_verified'])
        self.assertEqual(result['text_byte_count'],len(_TEXT))
        self.assertEqual(result['text_source_sha256'],transport.SOURCE[1])
        self.assertFalse(result['gameplay_outcome_verified'])
        self.assertFalse(result['archive_fabricated'])
        self.assertNotIn('name',result)
        self.assertIsNone(fixture.blob)
        self.assertEqual(fixture.cells,{})

    def test_legality_refusal_readonly_and_request_exception_cleanup(self):
        cases=[(False,True,False),(True,False,False),(True,True,True)]
        for allowed,submit,exception in cases:
            with self.subTest(allowed=allowed,submit=submit,exception=exception):
                f=Fixture()
                f.allowed,f.request_error=allowed,exception
                if exception:
                    with self.assertRaisesRegex(RuntimeError,'request exception'):
                        f.invoke(submit=submit)
                else:
                    result=f.invoke(submit=submit)
                    self.assertFalse(result['request_invoked'])
                    self.assertIs(result['can_start'],allowed)
                    self.assertNotIn('request',f.calls)
                self.assertEqual(f.calls[-2:],['reason_dtor','parameter_dtor'])

    def test_alias_bad_flags_mutation_out_of_bounds_and_null_fail_closed(self):
        for field in ('alias','bad_count','changed_after_gate','changed_after_request','input_corrupt','null'):
            with self.subTest(field=field):
                f=Fixture()
                setattr(f,field,True)
                with self.assertRaisesRegex(RuntimeError,'owned byte input|source-sized storage|setter returned null'):
                    f.invoke()
                self.assertEqual(f.calls[-1],'parameter_dtor')
                self.assertEqual('request' in f.calls,field=='changed_after_request')

    def test_exact_profile_slots_map_and_dimension_admitted_before_native_calls(self):
        f=Fixture()
        for options in (dict(allow_religion_name=1),dict(allow_religion_name=False),dict(operation=1),
                        dict(parameters={**parameters(),7:1}),dict(parameters=parameters('nom')),
                        dict(parameters=parameters(b'name\0more')),dict(parameters=parameters(b'')),
                        dict(parameters=parameters(b'x'*(transport._MAX_NAME_BYTES + 1))),
                        dict(parameters={**parameters(),transport.PARAM_INSERT_MODE:1}),dict(allow_empty=True),
                        dict(dedication_permit=object())):
            with self.subTest(change=str(options)[:70]),self.assertRaises(ValueError):
                f.invoke(**options)
        self.assertEqual(f.calls,[])
        f.core._civ6_host_execution_image=None
        with self.assertRaisesRegex(ValueError,'exact installed'):
            f.invoke()
        f.core._civ6_host_execution_image=_XP1_PROFILE
        address=_BASE+transport.VECTOR_VTABLE+0x108
        f.memory[address]=bytes(8)
        with self.assertRaisesRegex(ValueError,'parameter slot differs'):
            f.invoke()
        self.assertFalse(f.calls)

    def test_archive_reader_reuses_scalar_and_exact_counted_utf8_record(self):
        raw=fixture_archive()
        result=transport.verify_archive(raw,0,parameters())
        self.assertEqual(result['archive_sha256'],sha256(raw).hexdigest())
        self.assertEqual(result['name_bytes_sha256'],sha256(_TEXT).hexdigest())
        wrong_operation = raw[:8] + struct.pack('<I',0x91ac3737) + raw[12:]
        for bad in (raw[:-1],raw+b'\0',_XP1_FOUNDATION,wrong_operation,raw[:-2]+b'XX',
                    raw[:4]+b'\1'+raw[5:],raw[:12]+b'\2'+raw[13:],
                    raw[:72]+b'\1'+raw[73:],raw[:74]+b'\2'+raw[75:],
                    raw[:78]+b'\0'*4+raw[82:],raw[:82]+b'\2'+raw[83:]):
            with self.subTest(bad=bad[-32:]),self.assertRaises(RuntimeError):
                transport.verify_archive(bad,0,parameters())
        # Limit here is transport capacity, not the application's UI length.
        name=b'x'*transport._MAX_NAME_BYTES
        self.assertEqual(len(fixture_archive(name)),6784)
        self.assertEqual(transport.verify_archive(fixture_archive(name),0,parameters(name))['size_bytes'],6784)

    def test_profile_pins_relocated_copied_abi_and_keeps_ui_semantics_unqualified(self):
        pins=transport.source_dependencies(_XP1_PROFILE)
        self.assertIn(transport.SOURCE[1],pins.values())
        self.assertIn(transport.ARCHIVE_SOURCE[1],pins.values())
        self.assertFalse(transport.verify_source()[0]['ui_unicode_length_qualified'])
        with self.assertRaises(ValueError):
            transport.source_dependencies(None)


if __name__=='__main__':
    unittest.main()

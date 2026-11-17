"""Static PE and composed Python fixtures for XP1 optional platform boundaries."""
import ctypes as C
import hashlib
from pathlib import Path
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import capstone
import pefile

from civ6_host.runtime import xp1_host_slot20_source as source
from civ6_host.runtime import xp2_host_achievement_service as service
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE, _PROFILE
from civ6_host.runtime.xp1_continuation import SavedContinuation
from test_xp2_host_achievement_service import fixture

BASE = 0x180000000
HOST = 0x12345678


def frames(prefix):
    return [dict(module=source.CORE_MODULE, rva=rva) for rva in prefix]


def prefixes():
    return [source.CONTACT_NOTIFICATION_PREFIX, source.LUA_UNLOCK_PREFIX,
            *((source.CALLER_PREFIX[0], site, *source.GOVERNMENT_NOTIFICATION_TAIL)
              for site in source.GOVERNMENT_LISTENER_TAGS)]


class XP1SharedPlatformBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = Path(_XP1_PROFILE.path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == _XP1_PROFILE.image_sha256
        cls.image = pefile.PE(data=raw, fast_load=False)
        cls.proof = source.source(_XP1_PROFILE)
        cls.shared = source._shared_boundary_source(_XP1_PROFILE, cls.proof)

    @classmethod
    def tearDownClass(cls):
        cls.image.close()

    def reader(self, host=HOST, corrupt=None):
        pointer_rva = self.proof['host_pointer_rva']
        def read(address, size):
            rva = address - BASE
            if (rva, size) == (pointer_rva, 8):
                return struct.pack('<Q', host)
            data = bytearray(self.image.get_data(rva, size))
            if corrupt is not None and rva <= corrupt < rva + len(data):
                data[corrupt - rva] ^= 1
            return bytes(data)
        return read

    def select(self, rows, **options):
        return source.select_contract(rows, service_installed=options.get('service_installed', False),
                                      execution_image=options.get('execution_image', _XP1_PROFILE))

    def test_exact_boundaries_allow_varying_outer_origins(self):
        for prefix in prefixes():
            for suffix in ((), ('0x123456',), ('0x123456', '0x654321')):
                with self.subTest(prefix=prefix, suffix=suffix):
                    self.assertEqual(self.select(frames((*prefix, *suffix))),
                                     source.SHARED_BOUNDARY_SOURCE[1])

    def test_missing_changed_and_propagating_boundaries_refuse(self):
        for prefix in prefixes():
            invalid = [prefix[:-1]]
            invalid.extend(prefix[:i] + (hex(int(rva, 16) + 1),) + prefix[i+1:]
                           for i, rva in enumerate(prefix))
            for row in invalid:
                with self.subTest(prefix=prefix, changed=row), self.assertRaises(ValueError):
                    self.select(frames(row))
        for site in ('0x1435ab', '0x143819', '0x143a97', '0x13b6e3'):
            with self.subTest(site=site), self.assertRaises(ValueError):
                self.select(frames(('0x142cc8', site)))

    def test_foreign_image_service_and_malformed_frames_refuse(self):
        rows = frames(source.LUA_UNLOCK_PREFIX)
        for image in (None, object(), _PROFILE):
            with self.subTest(image=image), self.assertRaises(ValueError):
                self.select(rows, execution_image=image)
        for installed in (True, None, 0, 'false'):
            with self.subTest(installed=installed), self.assertRaises(ValueError):
                self.select(rows, service_installed=installed)
        bad = [[], tuple(rows), [dict(rows[0], slot='0x20'), rows[1]],
               [dict(rows[0], module='GameCore_XP2_FinalRelease.dll'), rows[1]],
               [rows[0], dict(rows[1], rva=0x5f3bdd)]]
        for row in bad:
            with self.subTest(rows=row), self.assertRaises(ValueError):
                self.select(row)

    def test_source_dependencies_preserve_parents_and_pin_supplement_candidate(self):
        pins = source.source_dependencies(execution_image=_XP1_PROFILE)
        for reference in (source.SOURCE, source.ORIGINAL_SOURCE,
                          source.ENVOY_NOTIFICATION_SOURCE, source.CITY_STATE_CONTACT_SOURCE,
                          source.GOVERNMENT_LISTENER_SOURCE, source.SHARED_BOUNDARY_SOURCE,
                          source.BOUNDARY_CANDIDATE):
            self.assertEqual(pins[str(source._path(reference[0]).resolve())], reference[1])
        self.assertEqual(source.ENVOY_NOTIFICATION_SOURCE[1],
                         'e3c9bde32ed312485f85803551f2c695c9f97139a5709b35e4fcf4f34040da06')

    def test_real_pe_live_spans_and_final_ret_are_required(self):
        receipt = source.verify_live(BASE, self.reader(), host_pointer=HOST,
                                     execution_image=_XP1_PROFILE)
        self.assertGreater(receipt['verified_spans'], 40)
        self.assertEqual(self.image.get_data(0x183e26, 1), b'\xc3')
        for rva in (0x142cc7, 0x2763ba, 0x279e00, 0x100fd5, 0x10106f,
                    0x183e26, 0x21c6cd, 0x5f3bdd, 0x5f3be9, 0x5f1ea6,
                    0x8d00f8, 0x8d0110, 0x856036, 0x856042, 0x855fe8):
            with self.subTest(rva=hex(rva)), self.assertRaises(ValueError):
                source.verify_live(BASE, self.reader(corrupt=rva), host_pointer=HOST,
                                   execution_image=_XP1_PROFILE)
        with self.assertRaises(ValueError):
            source.verify_live(BASE, self.reader(), host_pointer=HOST+8,
                               execution_image=_XP1_PROFILE)

    def test_source_contract_slot_and_boundary_changes_refuse(self):
        real = source._source
        for field, value in (('slot', 0x28), ('platform_success_reported', True),
                             ('other_callers_admitted', True)):
            bad = dict(self.shared)
            bad['contract'] = dict(self.shared['contract'], **{field: value})
            with patch.object(source, '_source', side_effect=lambda ref:
                              bad if ref == source.SHARED_BOUNDARY_SOURCE else real(ref)):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    self.select(frames(source.LUA_UNLOCK_PREFIX))

    def test_independent_pe_call_targets_and_lua_binding_return(self):
        cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        ranges = [(0x142c90, 0x142d37), (0x279dea, 0x279e32),
                  (0x21c6a5, 0x21c712), (0x5f3b80, 0x5f3bea),
                  (0x5f1e98, 0x5f1ed1)]
        rows = {i.address: (i.mnemonic, i.op_str)
                for a,b in ranges for i in cs.disasm(self.image.get_data(a,b-a),a)}
        expected = {0x142cc5: ('call', 'qword ptr [rax + 0x20]'),
                    0x142cce: ('je', '0x142d21'),
                    0x279dfb: ('call', '0x276280'),
                    0x279e00: ('mov', 'rax, qword ptr [r15 + 0x450]'),
                    0x21c6c8: ('call', '0x100f90'),
                    0x21c6cd: ('mov', 'rax, qword ptr [rdi + 0x90]'),
                    0x5f3bd8: ('call', '0x142c90'),
                    0x5f3bdd: ('xor', 'eax, eax'), 0x5f3be9: ('ret', '')}
        self.assertEqual({a:rows[a] for a in expected}, expected)
        self.assertEqual(0x5f1ea6 + 7 + 0x1cd3, 0x5f3b80)
        self.assertEqual(self.image.get_data(0x8d00f8,18), b'UnlockAchievement\0')
        self.assertEqual(self.image.get_data(0x8d0110,20).split(b'\0')[0],
                         b'DLC3_ACHIEVEMENT_10')
        names = set()
        for rva in (0x856036, 0x856042, 0x855fe8):
            code = self.image.get_data(rva,6)
            self.assertEqual(code[:2], b'\xff%')
            target = rva+6+struct.unpack_from('<i',code,2)[0]
            names.update(i.name.decode() for d in self.image.DIRECTORY_ENTRY_IMPORT
                         for i in d.imports if i.address-self.image.OPTIONAL_HEADER.ImageBase==target)
        self.assertEqual(names, {'?luaL_checkinteger@@YAHPEAUlua_State@@H@Z',
                                '?luaL_checklstring@@YAPEBDPEAUlua_State@@HPEA_K@Z',
                                '?hks_pushnamedcclosure@@YAXPEAUlua_State@@P6AH0@ZHPEBDH@Z'})

    def backend(self):
        backend = fixture()
        backend.load_abi.core_sha256 = XP1_CORE_SHA256
        backend.configuration_abi = NS(core_sha256=XP1_CORE_SHA256)
        backend.core._civ6_host_execution_image = _XP1_PROFILE
        backend.runtime.read.side_effect = self.reader(host=backend.host.pointer)
        token = SavedContinuation.__new__(SavedContinuation)
        token.owner = backend
        backend._xp1_continuation = token
        return backend

    def test_composed_owner_binds_only20_and_reports_no_platform_success(self):
        backend = self.backend()
        before = dict(backend.host._slot_bindings)
        with (patch('civ6_host.runtime.native.native_absent_achievements.capture_stack') as stack,
              patch.object(SavedContinuation, 'check', autospec=True) as active):
            service.install_xp1(backend)
            callback = backend._xp1_host20[1]
            changes = {k for k,v in backend.host._slot_bindings.items() if before.get(k)!=v}
            self.assertEqual(changes, {(C.addressof(backend.host.vtable), 0x20)})
            for prefix in prefixes():
                stack.return_value = frames((*prefix, '0x123456'))
                self.assertIsNone(callback(backend.host.pointer))
                event = backend.emit.call_args.kwargs
                self.assertEqual(event['source_proof_sha256'], source.SHARED_BOUNDARY_SOURCE[1])
                self.assertIs(event['platform_request_submitted'], False)
                self.assertIs(event['platform_success_reported'], False)
            self.assertEqual(active.call_count, len(prefixes()))
            backend.host.achievement_service_installed = True
            with self.assertRaises(ValueError): callback(backend.host.pointer)
            backend.host.achievement_service_installed = False
            del backend._xp1_continuation
            with self.assertRaisesRegex(ValueError, 'active saved-game owner'):
                callback(backend.host.pointer)

    def test_foreign_host_slot_and_owner_refuse(self):
        backend = self.backend()
        previous = backend.host._slot_bindings[(C.addressof(backend.host.vtable),0x20)][1]
        previous._native_unavailable = ('host', 0x28)
        with self.assertRaisesRegex(ValueError, 'foreign or already admitted'):
            service.install_xp1(backend)
        backend = self.backend()
        backend.configuration_abi.core_sha256 = 'unknown'
        with self.assertRaisesRegex(ValueError, 'actual saved configuration owner'):
            service.install_xp1(backend)


if __name__ == '__main__':
    unittest.main()

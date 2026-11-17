"""Check the exact Rise and Fall callback profile without starting GameCore."""

import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pefile

from civ6_host.runtime import xp1_wmd_fallout_source as source
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE


class FalloutTests(unittest.TestCase):
    def test_current_producer_binding_checks_spans_pointer_and_capture(self):
        proof = source.source()
        pins = source.source_dependencies()
        self.assertIn(source.SOURCE[1], pins.values())
        self.assertNotIn(source.shared._CORE_SHA, pins.values())
        self.assertEqual(proof['capture']['gameplay_scripts'], source._SCRIPT_PROFILE)
        pe = pefile.PE(_XP1_PROFILE.path, fast_load=True)
        self.addCleanup(pe.close)
        base = pe.OPTIONAL_HEADER.ImageBase
        core = SimpleNamespace(_handle=base, _civ6_host_execution_image=_XP1_PROFILE)
        backend = SimpleNamespace(core=core, check_thread=lambda: None, stage='prepared',
            poisoned=False, destroyed=False, load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),
            inputs=SimpleNamespace(official_bundle=source.REFERENCE),
            captured_bundle=SimpleNamespace(reference=source.REFERENCE,
                content_profile={'gameplay_scripts': source._SCRIPT_PROFILE.copy()}))
        capture = proof['capture']['prepared_capture']
        selected = dict(path=str(source._path(capture['path']).resolve()), sha256=capture['sha256'])

        def read(address, size):
            return pe.get_data(address - base, size)

        with patch('civ6_host.runtime.capture_admission.configured_reference', return_value=selected):
            self.assertEqual(source.bind_owner(backend, core, read), source.SOURCE[1])
            self.assertIs(backend._xp1_wmd_fallout_core, core)
            slot = base + proof['core_blob_vtable_slot']['rva']
            with self.assertRaisesRegex(ValueError, 'blob setter differs'):
                source.bind_owner(backend, core,
                    lambda address, size: bytes(size) if address == slot else read(address, size))
            with self.assertRaisesRegex(ValueError, 'producer differs'):
                source.bind_owner(backend, core, lambda address, size: bytes(size))
            backend.captured_bundle.content_profile['gameplay_scripts']['active_count'] = 1
            with self.assertRaisesRegex(ValueError, 'exact prepared Rise and Fall owner'):
                source.bind_owner(backend, core, read)

    def test_position_is_copied_under_the_shared_wire_contract(self):
        shared = source.shared
        address = 0x123000
        position = struct.pack('<ii', -17, 32)

        def read(pointer, size):
            self.assertEqual((pointer, size), (address, 8))
            return position

        fields = {
            shared.SELECTOR_KEY: struct.pack('<I4xI12x', 3, 0),
            shared.POSITION_KEY: struct.pack('<H6xQII', 0, address, 8, 0x21000001),
            shared.VALUE_KEY: struct.pack('<I4xI12x', 2, 0xffffffff),
            shared.STATE_KEY: struct.pack('<I4xI12x', 2, 31),
        }
        decoded = source.decode_fields(shared.KIND, fields, read)
        self.assertEqual((decoded.position, decoded.value, decoded.state), ((-17, 32), 0xffffffff, 31))
        self.assertFalse(decoded.to_admin()['borrowed_pointer_retained'])
        wrong = dict(fields)
        wrong[shared.POSITION_KEY] = struct.pack('<H6xQII', 13, address, 8, 0x21000001)
        with self.assertRaisesRegex(ValueError, 'borrowed coordinate header differs'):
            source.decode_fields(shared.KIND, wrong, read)

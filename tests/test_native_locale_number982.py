"""Offline admission tests for the current XP2 Locale.ToNumber dependency."""
import hashlib
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from civ6_host.runtime.native import native_locale_number982 as number
from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.paths import resource_root


ROOT = resource_root()
IMAGE = select('xp2-gamecore-current-092abfbb',
               core_path=known_path('xp2-gamecore-current-092abfbb'))
FIXTURE_PATH = ROOT / number._CURRENT_LOCALE_BODY_PROOF[0]
EXPORTS = number._EXPORT_RVAS


class NativeLocaleNumber982Tests(unittest.TestCase):
    def test_explicit_current_image_pins_current_localization_and_evidence(self):
        files = number.verified_files(execution_image=IMAGE)
        current_dll = next(path for path, digest in files.items()
                           if digest == number._CURRENT_LOCALIZATION_IMAGE_SHA256)
        self.assertEqual(current_dll.name, 'Localization_FinalRelease.dll')
        self.assertEqual(hashlib.sha256(current_dll.read_bytes()).hexdigest(),
                         number._CURRENT_LOCALIZATION_IMAGE_SHA256)
        self.assertEqual(files[FIXTURE_PATH], number._CURRENT_LOCALE_BODY_PROOF[1])
        self.assertIn(ROOT / number._CURRENT_SHARED_BINDINGS_PROOF[0], files)

    def test_current_branch_rejects_unrecognized_image_and_wrong_library(self):
        with self.assertRaises((RuntimeError, ValueError)):
            number.verified_files(execution_image=object())
        files = number.verified_files(execution_image=IMAGE)
        profile = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
        official = Path(profile['current_image']['path'])
        number._check_library(SimpleNamespace(_name=str(official)), files,
                              execution_image=IMAGE)
        with self.assertRaisesRegex(RuntimeError, 'Loaded Localization library path'):
            number._check_library(SimpleNamespace(_name=str(official.with_name('other.dll'))),
                                  files, execution_image=IMAGE)

    def test_current_fixture_matches_real_exports_and_complete_pdata_bodies(self):
        import pefile
        from capstone import Cs, CS_ARCH_X86, CS_MODE_64

        fixture = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
        image_path = Path(fixture['current_image']['path'])
        raw = image_path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         number._CURRENT_LOCALIZATION_IMAGE_SHA256)
        pe = pefile.PE(data=raw, fast_load=False)
        exports = {entry.name.decode('ascii'): entry.address
                   for entry in pe.DIRECTORY_ENTRY_EXPORT.symbols if entry.name}
        pdata = pe.DIRECTORY_ENTRY_EXCEPTION
        functions = {row.struct.BeginAddress: row.struct.EndAddress for row in pdata}
        decoder = Cs(CS_ARCH_X86, CS_MODE_64)
        rows = fixture['exports']
        self.assertEqual(set(rows), set(EXPORTS))
        for name, rva in EXPORTS.items():
            with self.subTest(export=name):
                row = rows[name]
                body = row['current_function']
                self.assertEqual(exports[name], rva)
                self.assertEqual(int(body['start_rva'], 16), rva)
                self.assertEqual(functions[rva], int(body['end_rva_exclusive'], 16))
                start = pe.get_offset_from_rva(rva)
                actual = raw[start:start + body['bytes']]
                self.assertEqual(actual.hex(), body['body_hex'])
                self.assertEqual(hashlib.sha256(actual).hexdigest(), body['sha256'])
                decoded = list(decoder.disasm(actual, rva))
                self.assertEqual(sum(insn.size for insn in decoded), len(actual))
                self.assertEqual(body['capstone_decoded_bytes'], len(actual))
        phase43 = json.loads((ROOT / 'evidence/phase43-locale-string-abi.json')
                             .read_text(encoding='utf-8'))
        for key, export in (('constructor', number._CTOR_CSTR),
                            ('to_utf8', number._TO_UTF8),
                            ('destructor', number._DESTRUCTOR)):
            self.assertEqual(rows[export]['reference_body_sha256'],
                             phase43['localization_exports'][key]['body']['raw_sha256'])
        self.assertIsNone(rows[number._CTOR_SIZED]['reference_body_sha256'])
        self.assertIsNone(rows[number._PUSH_DOUBLE]['reference_body_sha256'])

    def test_format_number_forwards_image_without_loading_native_code(self):
        ctypes = __import__('ctypes')
        buffer = ctypes.create_string_buffer(b'12.5\0')
        def to_utf8(ptr, length, mode):
            ctypes.cast(length, ctypes.POINTER(ctypes.c_uint)).contents.value = 4
            return ctypes.addressof(buffer)
        funcs = {
            number._CTOR_CSTR: lambda ptr, template: ptr.value,
            number._CTOR_SIZED: lambda ptr, template, size: ptr.value,
            number._PUSH_DOUBLE: lambda ptr, value: 1,
            number._TO_UTF8: to_utf8,
            number._DESTRUCTOR: lambda ptr: None,
        }
        with patch.object(number, 'verified_files', return_value={}) as verified, \
             patch.object(number, '_check_library') as check, \
             patch.object(number, '_bind', side_effect=lambda lib, name, *args: funcs[name]):
            self.assertEqual(number.format_number(object(), 12.5, execution_image=IMAGE), '12.5')
        self.assertEqual(verified.call_args.kwargs, {'execution_image': IMAGE})
        self.assertEqual(check.call_args.kwargs, {'execution_image': IMAGE})


if __name__ == '__main__':
    unittest.main()

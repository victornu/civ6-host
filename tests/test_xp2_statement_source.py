"""XP2 statement source is checked against the installed PE, without loading it."""
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'work' / 'python-deps'))
import pefile

from civ6_host.runtime import execution_images, xp2_statement_source as source


class XP2StatementSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.execution_image = execution_images.select(
            'xp2-gamecore-current-092abfbb',
            core_path=execution_images.known_path('xp2-gamecore-current-092abfbb'))
        raw = Path(cls.execution_image.path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != cls.execution_image.image_sha256:
            raise AssertionError('Installed XP2 PE differs from its selected execution image')
        pe = pefile.PE(data=raw)
        cls.base = 0x180000000
        if pe.OPTIONAL_HEADER.ImageBase != cls.base:
            raise AssertionError('XP2 PE preferred base differs from the captured live-reader base')
        cls.memory = pe.get_memory_mapped_image()
        pe.close()

    def read(self, address, size):
        offset = address - self.base
        if not 0 < size <= 4096 or offset < 0 or offset + size > len(self.memory):
            raise AssertionError('Source verifier requested bytes outside the mapped XP2 PE')
        return self.memory[offset:offset + size]

    def test_entire_captured_request_branch_and_vtable_match_installed_pe(self):
        profile = source.verify_live(self.base, self.read, execution_image=self.execution_image)
        proof = source.source(execution_image=self.execution_image)
        request = proof['functions']['request_start']
        self.assertEqual(sum(len(bytes.fromhex(row['raw_hex'])) for row in request['fragments']), 579)
        self.assertEqual(request['fragment_count'], 3)
        self.assertIs(profile, source.PROFILE)

    def test_second_request_fragment_and_message_slot_mutations_are_refused(self):
        proof = source.source(execution_image=self.execution_image)
        fragment = proof['functions']['request_start']['fragments'][1]
        offset = int(fragment['start_rva'], 16)
        memory = bytearray(self.memory)
        memory[offset + 3] ^= 1
        def altered(address, size):
            at = address - self.base
            return bytes(memory[at:at + size])
        with self.assertRaisesRegex(ValueError, 'instructions changed'):
            source.verify_live(self.base, altered, execution_image=self.execution_image)

        memory = bytearray(self.memory)
        slot = int(proof['message_vtable_rva'], 16) + 0x18
        memory[slot] ^= 1
        with self.assertRaisesRegex(ValueError, 'message interface changed'):
            source.verify_live(self.base, lambda a, n: bytes(memory[a-self.base:a-self.base+n]),
                               execution_image=self.execution_image)

    def test_foreign_and_unselected_execution_images_are_refused(self):
        for image in (None, object()):
            with self.subTest(image=image), self.assertRaises((ValueError, TypeError, AttributeError)):
                source.verify_live(self.base, self.read, execution_image=image)
        with self.assertRaises(ValueError):
            source.source(execution_image=execution_images.select(
                'xp2-gamecore-current-092abfbb', core_path='C:/foreign/GameCore.dll'))

    def test_source_and_dependency_hash_audit_is_complete(self):
        pins = source.source_dependencies(execution_image=self.execution_image)
        self.assertIn(source.SOURCE[1], pins.values())
        self.assertIn(source.PRESENTATION[1], pins.values())
        self.assertGreaterEqual(len(pins), 6)
        for path, expected in pins.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()

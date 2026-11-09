"""XP2 diplomacy display callbacks are checked against the selected PE."""
from dataclasses import replace
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'work' / 'python-deps'))
import pefile

from civ6_host.runtime import execution_images, xp2_diplomacy_display_source as source


class XP2DiplomacyDisplaySourceTests(unittest.TestCase):
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
            raise AssertionError('XP2 PE preferred base differs from the captured callback base')
        cls.memory = pe.get_memory_mapped_image()
        pe.close()

    def read(self, address, size):
        offset = address - self.base
        if not 0 < size <= 4096 or offset < 0 or offset + size > len(self.memory):
            raise AssertionError('Source verifier requested bytes outside the mapped XP2 PE')
        return self.memory[offset:offset + size]

    def test_captured_bindings_functions_and_current_image_are_exact(self):
        value = source.verify_live(self.base, self.read,
                                   execution_image=self.execution_image)
        self.assertIs(value, source.source(execution_image=self.execution_image))
        self.assertEqual(self.execution_image.id, 'xp2-gamecore-current-092abfbb')
        self.assertEqual(value['actual_image']['sha256'], self.execution_image.image_sha256)
        self.assertEqual(value['reference_core_sha256'],
                         self.execution_image.reference_core_sha256)
        self.assertEqual(len(value['bindings']), 14)
        self.assertEqual({row['name'] for row in value['bindings']}, source.NAMES)
        self.assertEqual(len(source.NAMES), 13)
        self.assertEqual(len(value['functions']), 20)
        self.assertTrue(all(row['fragments'] for row in value['functions'].values()))

    def test_foreign_and_missing_execution_images_are_refused(self):
        for image in (None, object(), replace(self.execution_image, id='xp2-gamecore-foreign')):
            with self.subTest(image=image), self.assertRaises((ValueError, TypeError)):
                source.verify_live(self.base, self.read, execution_image=image)
            with self.subTest(source_image=image), self.assertRaises((ValueError, TypeError)):
                source.source(execution_image=image)

    def test_find_text_key_callback_mutation_is_refused(self):
        value = source.source(execution_image=self.execution_image)
        binding = next(row for row in value['bindings'] if row['name'] == 'FindTextKey')
        address = self.base + int(binding['callback_rva'], 16)
        mutated = bytearray(self.memory)
        mutated[address - self.base] ^= 1

        def altered_read(requested_address, size):
            offset = requested_address - self.base
            if not 0 < size <= 4096 or offset < 0 or offset + size > len(mutated):
                raise AssertionError('Source verifier requested bytes outside the mapped XP2 PE')
            return bytes(mutated[offset:offset + size])

        with self.assertRaisesRegex(ValueError, 'XP2 dialogue Lua binding changed: 0x694da0'):
            source.verify_live(self.base, altered_read,
                               execution_image=self.execution_image)

    def test_source_and_all_official_shared_dependencies_are_pinned(self):
        pins = source.source_dependencies(execution_image=self.execution_image)
        self.assertIn(source.SOURCE[1], pins.values())
        required_names = {
            'DiplomacyActionView.lua', 'DiplomacyStatementSupport.lua',
            'native_diplomacy_default.py', 'native_saved_player_map.py',
            'native_revealed_plot_observation.py',
        }
        self.assertTrue(required_names.issubset({Path(path).name for path in pins}))
        for path, expected in pins.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()

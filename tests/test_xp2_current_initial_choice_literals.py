"""Current PE bytes versus captured ABI; no DLL loading or code execution."""
import unittest
from pathlib import Path
import pefile

from civ6_host.runtime import xp2_initial_choice_source as source
from civ6_host.runtime.execution_images import select, known_path


class CurrentInitialChoiceLiteralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = select('xp2-gamecore-current-092abfbb',
                           core_path=known_path('xp2-gamecore-current-092abfbb'))
        cls.pe = pefile.PE(cls.image.path, fast_load=True)
        cls.base = cls.pe.OPTIONAL_HEADER.ImageBase

    @classmethod
    def tearDownClass(cls):
        cls.pe.close()

    def read(self, address, size):
        return self.pe.get_data(address-self.base, size)

    def test_all_three_families_verify_against_the_current_file(self):
        for family in ('status', 'research', 'production'):
            with self.subTest(family=family):
                self.assertGreater(source.verify_live(self.base, self.read, family,
                    execution_image=self.image), 0)
        self.assertEqual(len(source._execution_literal_spans(source.source('status'),
                                                            self.image)), 5)

    def test_default_reference_and_foreign_selection_remain_strict(self):
        with self.assertRaisesRegex(ValueError, 'literal changed'):
            source.verify_live(self.base, self.read, 'status')
        with self.assertRaises((ValueError, TypeError)):
            source._execution_literal_spans(source.source('status'), object())

    def test_unlisted_literal_corruption_still_refuses(self):
        original = source.source('status')
        selected = source._execution_literal_spans(original, self.image)
        rva = next(int(r,16) for r,b in original['literals'].items()
                   if int(r,16) not in selected and b['bytes'] > 2)

        def changed(address, size):
            raw = self.read(address, size)
            return bytes([raw[0]^1])+raw[1:] if address == self.base+rva else raw

        with self.assertRaises(ValueError):
            source.verify_live(self.base, changed, 'status', execution_image=self.image)


if __name__ == '__main__':
    unittest.main()

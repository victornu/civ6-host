"""Keep captured image provenance distinct from files executed by city queries."""
from pathlib import Path
import unittest
from civ6_host.runtime import expansion_city_controls_profile as source
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.execution_images import select,known_path


class CityCurrentSourceTests(unittest.TestCase):
    def test_current_profile_preserves_proofs_and_omits_captured_executable(self):
        image=select('xp2-gamecore-current-092abfbb',
                     core_path=known_path('xp2-gamecore-current-092abfbb'))
        legacy=source.source_dependencies(XP2_CORE_SHA256)
        current=source.source_dependencies(XP2_CORE_SHA256,execution_image=image)
        proof,_,selected=source.verify_source(XP2_CORE_SHA256)
        exe=str(Path(proof['exe']['path']).resolve())
        self.assertEqual(legacy[exe],source.EXE_SHA)
        self.assertNotIn(exe,current)
        self.assertEqual(current[image.path],image.image_sha256)
        self.assertEqual(selected['image']['sha256'],image.reference_core_sha256)
        for path,digest in legacy.items():
            if path not in (exe,image.path):self.assertEqual(current[path],digest)

    def test_execution_image_does_not_authorize_another_core(self):
        image=select('xp2-gamecore-current-092abfbb',
                     core_path=known_path('xp2-gamecore-current-092abfbb'))
        with self.assertRaisesRegex(ValueError,'requires XP2'):
            source.source_dependencies(XP1_CORE_SHA256,execution_image=image)


if __name__=='__main__':unittest.main()

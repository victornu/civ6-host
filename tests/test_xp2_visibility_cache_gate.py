import hashlib
from pathlib import Path
import unittest

from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
from civ6_host.runtime import loaded_cache_profiles
from civ6_host.runtime import xp1_visibility_cache_gate as gate
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.resource_resolution import resolve_path
from civ6_host.runtime.xp2_cache_source import SOURCE as XP2_SOURCE


class XP2VisibilityCacheGateTests(unittest.TestCase):
    def test_source_dependencies_select_the_xp2_cache_profile(self):
        pins = gate.source_dependencies(core_sha256=XP2_CORE_SHA256)
        xp2_path = str(resolve_path(resource_root() / XP2_SOURCE[0]).resolve())
        xp1_path = str(resolve_path(resource_root() / loaded_cache_profiles.SOURCE[0]).resolve())
        self.assertEqual(pins[xp2_path], XP2_SOURCE[1])
        self.assertNotIn(xp1_path, pins)
        for path, digest in pins.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)

    def test_unknown_engine_does_not_fall_back_to_xp1(self):
        with self.assertRaisesRegex(ValueError, 'Unknown internal-cache engine'):
            gate.source_dependencies(core_sha256='0' * 64)


if __name__ == '__main__':
    unittest.main()

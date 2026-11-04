"""Actual source/preflight calls; no GameCore process or native entry points."""
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.runtime import application_mirror_profiles as mirror
from civ6_host.runtime import xp1_session_inputs as inputs
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class ApplicationPreludeTransitionTests(unittest.TestCase):
    def test_original_proof_and_source_preserved_current_source_separately_pinned(self):
        original = resource_root()/mirror.PRELUDE_SOURCE[0]
        before = original.read_bytes()
        proof = mirror._prelude_document()
        transition = mirror._source(mirror.CONFIGURATION_TRANSITION)
        pins = mirror.source_dependencies(XP1_CORE_SHA256)
        current = Path(mirror.__file__).with_name('configuration_profiles.py').resolve()
        historical = (resource_root()/transition['preserved_source']['path']).resolve()
        self.assertEqual(proof['source_refs']['configuration_profile']['sha256'],pins[str(historical)])
        self.assertNotEqual(pins[str(current)],pins[str(historical)])
        self.assertEqual(pins[str(current)],transition['current_source']['sha256'])
        self.assertTrue(all(digest(Path(path).read_bytes())==expected for path,expected in pins.items()))
        self.assertEqual(original.read_bytes(),before)
        self.assertEqual(digest(before),mirror.PRELUDE_SOURCE[1])
        self.assertEqual(mirror._xp1_abi().variant_assign_rva,0x8473E0)
        self.assertEqual(mirror.mirror_abi(BASE_CORE_SHA256).variant_assign_rva,0x747AE0)
        self.assertTrue(mirror.source_dependencies(XP2_CORE_SHA256))

    def test_future_current_module_or_historical_bytes_are_not_rehashed_into_acceptance(self):
        transition=mirror._source(mirror.CONFIGURATION_TRANSITION)
        historical=(resource_root()/transition['preserved_source']['path']).resolve()
        current=Path(mirror.__file__).with_name('configuration_profiles.py').resolve()
        original_read=Path.read_bytes
        for corrupted in (current,historical):
            with self.subTest(path=corrupted):
                def read(path):
                    raw=original_read(path)
                    return raw+b'\n# unreviewed change\n' if path.resolve()==corrupted else raw
                with patch.object(Path,'read_bytes',read):
                    with self.assertRaisesRegex(ValueError,'Prelude source dependency changed'):
                        mirror._prelude_document()

    def test_transition_cannot_relabel_another_historical_dependency(self):
        ref=dict(mirror._source(mirror.PRELUDE_SOURCE)['source_refs']['configuration_profile'])
        for key,value in (('path','another-configuration.py'),('sha256','0'*64)):
            bad=dict(ref);bad[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'transition differs'):
                mirror._configuration_reference_pins(bad)

    def test_full_parent_source_preflight_calls_mirror_and_pins_both_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            package=Path(folder)/'fixture-prepared-input.json'
            package.write_bytes(b'{"fixture":"source-preflight-only"}')
            # The captured input itself is an explicit fixture. Every phase's
            # source provider, file hash and executable-build check is real.
            with patch.object(mirror,'source_dependencies',wraps=mirror.source_dependencies) as checked:
                pins,executable=inputs.prepare_sources(NS(dependencies={}),
                    {'path':str(package),'sha256':digest(package.read_bytes())},
                    postload160=True,publish_cache=True,close_loaded=True,
                    observe_player=True,unit_commands=True)
            checked.assert_called_once_with()
            self.assertTrue(executable.is_file())
            self.assertEqual({p:pins[p] for p in mirror.source_dependencies()},mirror.source_dependencies())
            self.assertGreater(len(pins),900)

    def test_parent_preflight_fails_before_executable_preparation_when_source_changes(self):
        with patch.object(mirror,'source_dependencies',side_effect=ValueError('unreviewed source')):
            with patch.object(inputs,'saved_load_build_pins') as build:
                with self.assertRaisesRegex(ValueError,'unreviewed source'):
                    inputs.prepare_sources(NS(dependencies={}),{},postload160=False,
                        publish_cache=False,close_loaded=False,observe_player=False,unit_commands=False)
                build.assert_not_called()


if __name__=='__main__':unittest.main()

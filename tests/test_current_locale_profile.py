"""Exact repaired runtime selection and C bridge guards; no native calls."""
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import pefile

from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime import locale_text
from civ6_host.runtime.native import native_locale_arguments as arguments
from civ6_host.runtime.native.native_shared_dependency_profiles import profile_for_shared_dependencies
from civ6_host.runtime.provenance import resource_root


class CurrentLocaleProfileTests(unittest.TestCase):
    def setUp(self):
        self.image=select('xp2-gamecore-current-092abfbb',
                          core_path=known_path('xp2-gamecore-current-092abfbb'))
        self.directory=Path(self.image.shared_dependencies[0].path).parent
        self.shared=profile_for_shared_dependencies(self.directory,
            actual_image_sha256=self.image.image_sha256,
            interface_reference_sha256=self.image.reference_core_sha256)
        self.runtime=SimpleNamespace(shared_dependency_profile=self.shared,
            library=SimpleNamespace(_name=str(self.directory/'HavokScript_FinalRelease.dll')),
            service_owner=SimpleNamespace(localization_library=SimpleNamespace(
                _name=str(self.directory/'Localization_FinalRelease.dll'))))

    def test_explicit_current_pair_and_reference_remain_separate(self):
        _,original=arguments.verified_files()
        self.assertIs(arguments.verify_runtime_images(self.runtime,original),self.image)
        self.runtime.shared_dependency_profile=None
        with self.assertRaisesRegex(RuntimeError,'loaded image differs'):
            arguments.verify_runtime_images(self.runtime,original)
        self.runtime.shared_dependency_profile=object()
        with self.assertRaisesRegex(ValueError,'explicit shared'):
            arguments.verify_runtime_images(self.runtime,original)

    def test_selected_c_bridge_guards_match_actual_exports_without_algorithm_change(self):
        pins,proof=locale_text.source_files(execution_image=self.image)
        _,old=locale_text.source_files()
        self.assertNotEqual(proof['dll']['sha256'],old['dll']['sha256'])
        current=(resource_root()/next(r['path'] for r in proof['files']
                    if r['path'].endswith('/native/locale_arguments967.c'))).read_text()
        pattern=r'(BIND\(\w+, "([^"]+)", )(0x[0-9a-fA-F]+)(\);)'
        exports={row.name.decode():row.address for row in pefile.PE(
            str(self.directory/'HavokScript_FinalRelease.dll')).DIRECTORY_ENTRY_EXPORT.symbols if row.name}
        guards=re.findall(pattern,current)
        self.assertEqual(len(guards),17)
        for _,name,rva,_ in guards:self.assertEqual(int(rva,16),exports[name])
        replacements={row['name']:row['reference_rva'] for row in proof['export_guard_changes']}
        restored=re.sub(pattern,lambda m:m[1]+replacements[m[2]]+m[4],current)
        original=(resource_root()/'work/host-simultaneous/city-management/locale-length-revision/native/locale_arguments967.c').read_text()
        self.assertEqual(restored,original)
        self.assertIn(str(resource_root()/locale_text.CURRENT_SOURCE[0]),pins)

    def test_foreign_library_and_profile_refuse_before_bridge_installation(self):
        _,original=arguments.verified_files()
        original=dict(original)
        self.runtime.library._name=str(self.directory/'unselected.dll')
        with self.assertRaises(ValueError):arguments.verify_runtime_images(self.runtime,original)
        with self.assertRaises((ValueError,TypeError)):
            locale_text.source_files(execution_image=object())
        self.runtime.library._name=str(self.directory/'HavokScript_FinalRelease.dll')
        original['havok']=dict(original['havok'],sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'source ABI reference'):
            arguments.verify_runtime_images(self.runtime,original)

    def test_numeric_attach_reuses_length_bridge_for_current_runtime(self):
        prefix=SimpleNamespace(runtime=self.runtime,ui_child=object())
        with patch.object(locale_text,'attach') as attach:
            arguments.attach(prefix)
        attach.assert_called_once_with(prefix)
        self.assertIs(prefix.numeric_locale_child,prefix.ui_child)


if __name__=='__main__':unittest.main()

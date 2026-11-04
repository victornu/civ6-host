"""Source-build association only; no DLL load or callback execution."""
import copy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from civ6_host.runtime import script_context_source as source
from civ6_host.runtime import source_build_identity as identity
from civ6_host.runtime.paths import resource_root

class ContextNotificationBuildTests(unittest.TestCase):
    def test_actual_build_and_unchanged_component_are_jointly_required(self):
        path=resource_root()/'work/native-host-xp1-postload-build01/civ6rl-native-python.exe'
        source.verify_notification_image(path)
        source.verify_notification_image(resource_root()/'work/native-host-xp1-jobs-build01/civ6rl-native-python.exe')
        original=json.loads((resource_root()/source.POSTLOAD_BUILD[0]).read_text(encoding='utf-8'))
        for key,value in [('compiler_reaped',False),('profile','other'),
                          ('source_manifest_sha256','0'*64),('compiler_exit_code',1)]:
            changed=copy.deepcopy(original);changed[key]=value
            with patch.object(identity,'_source',return_value=changed),self.assertRaises(ValueError):
                source.verify_notification_image(path)
        changed=copy.deepcopy(original)
        next(row for row in changed['sources'] if row['build_path']=='script_context_notify.inc')['sha256']='0'*64
        with patch.object(identity,'_source',return_value=changed),self.assertRaises(ValueError):
            source.verify_notification_image(path)
        with tempfile.TemporaryDirectory() as folder:
            unknown=Path(folder)/'unqualified.exe';unknown.write_bytes(b'not the reviewed native build')
            with patch.object(identity,'_source') as load,self.assertRaises(ValueError):
                source.verify_notification_image(unknown)
            load.assert_not_called()

if __name__=='__main__':unittest.main()

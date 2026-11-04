"""Prepared packages never silently replace a different capture or handoff."""
import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from civ6_host.runtime import capture_admission as admission


class CaptureAdmissionTests(unittest.TestCase):
    def test_retained_producer_requires_explicit_identity_and_unchanged_validators(self):
        producer={'schema':'test','runtime_sources':{'a':'old'},'original_validator_sources':{'proof':'pinned'}}
        consumer=dict(producer,runtime_sources={'a':'new'})
        digest=hashlib.sha256(json.dumps(producer,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,'not compatible'):
            admission.admit_producer(producer,consumer)
        with patch.object(admission,'_COMPATIBLE_PRODUCERS',{digest:{'qualification':'test'}}):
            self.assertEqual(admission.admit_producer(producer,consumer)['mode'],'retained_qualified_producer')
            with self.assertRaisesRegex(ValueError,'not compatible'):
                admission.admit_producer(producer,dict(consumer,original_validator_sources={'proof':'changed'}))
    def setUp(self):
        self.env=patch.dict(os.environ,{},clear=True);self.env.start();self.addCleanup(self.env.stop)
        self.setting=patch.object(admission,'_SETTING',admission._UNSET);self.setting.start();self.addCleanup(self.setting.stop)

    def test_unconfigured_path_preserves_original_validator(self):
        admission.configure(None)
        self.assertIsNone(admission.try_bundle({},input_profile='hotseat-four'))
        self.assertIsNone(admission.try_localization({},{}))
        self.assertFalse(admission.configure_prepared_closure({},None))

    def test_configuration_cannot_be_added_after_original_path_was_chosen(self):
        admission.configure(None)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            p=Path(directory)/'manifest.json';p.write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'configuration changed'):
                admission.configure({'path':str(p),'sha256':'a'*64})

    def test_missing_package_closure_pin_is_refused(self):
        reference={'path':'C:/private/manifest.json','sha256':'a'*64}
        with patch.object(admission,'configured_reference',return_value=reference):
            with self.assertRaisesRegex(ValueError,'pinned closure'):
                admission.consume_prepared_closure({'prepared_capture':reference,'pins':{}},environment={})

    def test_prepared_closure_without_configuration_is_refused(self):
        with self.assertRaisesRegex(ValueError,'no explicit package'):
            admission.consume_prepared_closure({'prepared_capture':{}})

    def test_legacy_handoff_cannot_be_mixed_with_package(self):
        reference={'path':'C:/private/manifest.json','sha256':'a'*64}
        with patch.object(admission,'configured_reference',return_value=reference):
            closure={'prepared_capture':reference,'pins':{reference['path']:reference['sha256']},'parent_localization_validation':{}}
            with self.assertRaisesRegex(ValueError,'cannot mix'):
                admission.consume_prepared_closure(closure,environment={})


if __name__=='__main__':unittest.main()

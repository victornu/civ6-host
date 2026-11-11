"""Versioned checkpoint identity and explicit runtime compatibility guards."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime.execution_images import _XP1_PROFILE, identity, select
from civ6_host.runtime import network_checkpoint as checkpoint
from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE
from civ6_host.runtime.xp2_bundle_inputs import XP2_LAN_PROFILE
from civ6_host.runtime.xp1_session_checkpoint import _validate_save_execution_identity


PROFILE_ID = 'xp2-gamecore-current-092abfbb'
CORE_PATH = (
    r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI"
    r"\DLC\Expansion2\Binaries\Win64\GameCore_XP2_FinalRelease.dll"
)
EXECUTION_IMAGE = select(PROFILE_ID, core_path=CORE_PATH)
REFERENCE = EXECUTION_IMAGE.reference_core_sha256
ORIGIN = (r'work\captured\bundle.json', 'a' * 64)
COMPATIBILITY = checkpoint.REFERENCE_CHECKPOINT_COMPATIBILITY


class CheckpointExecutionIdentityTests(unittest.TestCase):
    def test_v1_remains_creation_identity_and_requires_explicit_runtime_bridge(self):
        historical = dict(schema=checkpoint.SCHEMA,
                          input_profile=XP2_LAN_PROFILE.name,
                          core_sha256=REFERENCE)
        self.assertIsNone(checkpoint._checkpoint_execution_image(historical))
        checkpoint._require_checkpoint_runtime(historical, None)
        with self.assertRaisesRegex(ValueError, 'explicit XP2 reference-to-runtime'):
            checkpoint._require_checkpoint_runtime(historical, EXECUTION_IMAGE)
        checkpoint._require_checkpoint_runtime(historical, EXECUTION_IMAGE, COMPATIBILITY)
        from civ6_host.runtime.capture_profiles import LAN_PROFILE
        with self.assertRaisesRegex(ValueError, 'explicit XP2 reference-to-runtime'):
            checkpoint._require_checkpoint_runtime(
                dict(historical, input_profile=LAN_PROFILE.name), EXECUTION_IMAGE, COMPATIBILITY)

    def test_v2_requires_exact_actual_and_reference_runtime_identity(self):
        current = dict(schema=checkpoint.SCHEMA_V2,
            input_profile=XP2_LAN_PROFILE.name,
            core_sha256=REFERENCE, actual_image_sha256=EXECUTION_IMAGE.image_sha256,
            reference_core_sha256=REFERENCE, execution_image=identity(EXECUTION_IMAGE),
            checkpoint_compatibility=None)
        self.assertIs(checkpoint._checkpoint_execution_image(current), EXECUTION_IMAGE)
        checkpoint._require_checkpoint_runtime(current, EXECUTION_IMAGE)
        with self.assertRaisesRegex(ValueError, 'explicitly selected execution image'):
            checkpoint._require_checkpoint_runtime(current, None)
        with self.assertRaisesRegex(ValueError, 'actual/reference identities disagree'):
            checkpoint._checkpoint_execution_image(
                dict(current, actual_image_sha256=REFERENCE))
        with self.assertRaisesRegex(ValueError, 'compatibility override'):
            checkpoint._require_checkpoint_runtime(current, EXECUTION_IMAGE, COMPATIBILITY)

    def test_save_provenance_keeps_v1_default_and_emits_v2_only_with_selection(self):
        inputs = SimpleNamespace(official_bundle=ORIGIN, checkpoint=None,
                                 profile=XP2_LAN_PROFILE)
        closure = dict(official_bundle={'path': ORIGIN[0], 'sha256': ORIGIN[1]})
        with patch('civ6_host.runtime.native.native_official_bundle.normalize_reference',
                   return_value=ORIGIN):
            legacy = checkpoint.save_provenance(inputs, closure)
            versioned = checkpoint.save_provenance(
                inputs, closure, execution_image=EXECUTION_IMAGE)
        self.assertEqual(legacy['schema'], checkpoint.SCHEMA)
        self.assertNotIn('execution_image', legacy)
        self.assertEqual(versioned['schema'], checkpoint.SCHEMA_V2)
        self.assertEqual(versioned['actual_image_sha256'], EXECUTION_IMAGE.image_sha256)
        self.assertEqual(versioned['reference_core_sha256'], REFERENCE)
        self.assertEqual(versioned['execution_image'], identity(EXECUTION_IMAGE))

    def test_installed_xp1_checkpoint_preserves_its_own_runtime(self):
        inputs = SimpleNamespace(official_bundle=ORIGIN, checkpoint=None, profile=XP1_LAN_PROFILE)
        closure = dict(official_bundle={'path': ORIGIN[0], 'sha256': ORIGIN[1]})
        with patch('civ6_host.runtime.native.native_official_bundle.normalize_reference',
                   return_value=ORIGIN):
            provenance = checkpoint.save_provenance(inputs, closure, execution_image=_XP1_PROFILE)
        record = dict(provenance, input_profile=XP1_LAN_PROFILE.name,
                      core_sha256=_XP1_PROFILE.reference_core_sha256)
        checkpoint._require_checkpoint_runtime(record, _XP1_PROFILE)
        with self.assertRaisesRegex(ValueError, 'differs from selected runtime'):
            checkpoint._require_checkpoint_runtime(record, EXECUTION_IMAGE)
        with self.assertRaisesRegex(ValueError, 'identities disagree'):
            checkpoint._checkpoint_execution_image(dict(record, input_profile=XP2_LAN_PROFILE.name))
        historical = dict(schema=checkpoint.SCHEMA, input_profile=XP1_LAN_PROFILE.name,
                          core_sha256=_XP1_PROFILE.reference_core_sha256)
        with self.assertRaisesRegex(ValueError, 'explicit XP2 reference-to-runtime'):
            checkpoint._require_checkpoint_runtime(historical, _XP1_PROFILE, COMPATIBILITY)

    def test_installed_xp1_historical_combat_transition_requires_the_exact_pair(self):
        reference = checkpoint.XP1_COMBAT_CHECKPOINT
        compatibility = checkpoint.XP1_COMBAT_CHECKPOINT_COMPATIBILITY
        parent = dict(schema=checkpoint.SCHEMA, input_profile=XP1_LAN_PROFILE.name,
                      core_sha256=_XP1_PROFILE.reference_core_sha256)
        checkpoint._require_checkpoint_runtime(parent, _XP1_PROFILE, compatibility,
                                               reference=reference)
        with self.assertRaisesRegex(ValueError, 'exact retained reference'):
            checkpoint._require_checkpoint_runtime(parent, _XP1_PROFILE, compatibility,
                                                   reference=(reference[0], '0' * 64))
        with self.assertRaisesRegex(ValueError, 'exact retained reference'):
            checkpoint._require_checkpoint_runtime(parent, EXECUTION_IMAGE, compatibility,
                                                   reference=reference)
        child = dict(parent, schema=checkpoint.SCHEMA_V2, execution_image=identity(_XP1_PROFILE),
                     actual_image_sha256=_XP1_PROFILE.image_sha256,
                     reference_core_sha256=_XP1_PROFILE.reference_core_sha256,
                     parent_checkpoint=dict(zip(('path', 'sha256'), reference)),
                     checkpoint_compatibility=compatibility)
        checkpoint._validate_checkpoint_edge(child, parent)
        checkpoint._require_checkpoint_runtime(child, _XP1_PROFILE)
        with self.assertRaisesRegex(ValueError, 'identities disagree'):
            checkpoint._checkpoint_execution_image(dict(child, parent_checkpoint=None))

    def test_lineage_records_explicit_v1_parent_to_v2_runtime_transition(self):
        parent = dict(schema=checkpoint.SCHEMA,
            input_profile=XP2_LAN_PROFILE.name, core_sha256=REFERENCE)
        child = dict(schema=checkpoint.SCHEMA_V2,
            input_profile=XP2_LAN_PROFILE.name, core_sha256=REFERENCE,
            actual_image_sha256=EXECUTION_IMAGE.image_sha256,
            reference_core_sha256=REFERENCE,
            execution_image=identity(EXECUTION_IMAGE),
            checkpoint_compatibility=COMPATIBILITY)
        checkpoint._validate_checkpoint_edge(child, parent)
        with self.assertRaisesRegex(ValueError, 'explicit reference compatibility'):
            checkpoint._validate_checkpoint_edge(
                dict(child, checkpoint_compatibility=None), parent)

    def test_save_backend_keeps_live_092_profile_and_source_324_load_abi_separate(self):
        profile = SimpleNamespace(core_sha256=EXECUTION_IMAGE.image_sha256,
            source_core_sha256=REFERENCE, execution_image=EXECUTION_IMAGE)
        backend = SimpleNamespace(
            core=SimpleNamespace(_civ6_host_execution_image=EXECUTION_IMAGE),
            profile=profile, load_abi=SimpleNamespace(core_sha256=REFERENCE))
        self.assertIs(_validate_save_execution_identity(backend, REFERENCE),
                      EXECUTION_IMAGE)
        backend.load_abi.core_sha256 = EXECUTION_IMAGE.image_sha256
        with self.assertRaisesRegex(ValueError, 'actual image and Load ABI'):
            _validate_save_execution_identity(backend, REFERENCE)


if __name__ == '__main__':
    unittest.main()

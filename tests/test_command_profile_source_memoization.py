import unittest
from collections.abc import Mapping
from types import MappingProxyType
from types import SimpleNamespace
from unittest.mock import patch

from civ6_host.runtime import xp2_initial_choice_source as choices
from civ6_host.runtime import xp2_turn_notification_source as notifications


def _mutable(value):
    if isinstance(value, Mapping):
        return {key: _mutable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_mutable(item) for item in value]
    return value


def _frozen(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _frozen(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_frozen(item) for item in value)
    return value


class CommandProfileSourceMemoizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.choice_profile = choices._source(choices.SOURCE)
        cls.notification_profile = notifications._source(notifications.SOURCE)
        cls.filter_profile = notifications._source(notifications.FILTER_SOURCE)

    def setUp(self):
        choices._VALIDATED_BODY_PROFILE = None
        notifications._VALIDATED_BODY_PROFILES = None

    def test_initial_choice_hash_checks_skip_only_for_same_frozen_profile(self):
        choices._validate_complete_bodies(self.choice_profile)
        calls = []
        original = choices.hashlib.sha256
        with patch.object(choices.hashlib, 'sha256',
                          side_effect=lambda raw: (calls.append(len(raw)), original(raw))[1]):
            choices.source('research')
        self.assertEqual(calls, [])

    def test_changed_frozen_initial_choice_object_is_revalidated_and_rejected(self):
        choices._validate_complete_bodies(self.choice_profile)
        changed = _mutable(self.choice_profile)
        key = next(iter(changed['functions']))
        changed['functions'][key]['fragments'][0]['raw_hex'] = '00'
        changed = _frozen(changed)
        with patch.object(choices, '_source', return_value=changed):
            with self.assertRaisesRegex(ValueError, 'fragment changed|body changed'):
                choices.source('research')
        self.assertIs(choices._VALIDATED_BODY_PROFILE, self.choice_profile)

    def test_mutable_initial_choice_fixture_is_never_trusted_or_cached(self):
        mutable = _mutable(self.choice_profile)
        mutable['functions'][next(iter(mutable['functions']))]['fragments'][0]['raw_hex'] = '00'
        with self.assertRaisesRegex(ValueError, 'fragment changed|body changed'):
            choices._validate_complete_bodies(mutable)
        self.assertIs(choices._VALIDATED_BODY_PROFILE, None)

    def test_expected_initial_choice_header_constants_are_checked_on_cache_hit(self):
        choices._validate_complete_bodies(self.choice_profile)
        altered = dict(choices.VTABLES)
        altered['outer'] += 8
        with patch.object(choices, 'VTABLES', altered):
            with self.assertRaisesRegex(ValueError, 'source contract changed'):
                choices.source('research')

    def test_notification_body_hashing_skips_only_for_same_frozen_pair(self):
        notifications._validate_complete_bodies(self.notification_profile,
                                                self.filter_profile)
        calls = []
        original = notifications.hashlib.sha256
        digest_probe = SimpleNamespace(sha256=lambda raw:
            (calls.append(len(raw)), original(raw))[1])
        with patch.object(notifications, 'hashlib', digest_probe):
            notifications.source()
        self.assertEqual(calls, [])

    def test_changed_notification_filter_object_is_revalidated(self):
        notifications._validate_complete_bodies(self.notification_profile,
                                                self.filter_profile)
        changed_filter = _mutable(self.filter_profile)
        changed_filter['body']['fragments'][0]['raw_hex'] = '00'
        changed_filter = _frozen(changed_filter)
        with self.assertRaisesRegex(ValueError, 'fragment changed|body changed'):
            notifications._validate_complete_bodies(self.notification_profile,
                                                    changed_filter)
        self.assertIs(notifications._VALIDATED_BODY_PROFILES[1], self.filter_profile)

    def test_changed_frozen_notification_source_object_is_revalidated(self):
        notifications._validate_complete_bodies(self.notification_profile,
                                                self.filter_profile)
        changed = _mutable(self.notification_profile)
        key = next(iter(changed['functions']))
        changed['functions'][key]['fragments'][0]['raw_hex'] = '00'
        changed = _frozen(changed)
        with self.assertRaisesRegex(ValueError, 'fragment changed|body changed'):
            notifications._validate_complete_bodies(changed, self.filter_profile)
        self.assertIs(notifications._VALIDATED_BODY_PROFILES[0], self.notification_profile)

    def test_mutable_notification_profiles_are_never_trusted_or_cached(self):
        mutable_profile = _mutable(self.notification_profile)
        mutable_filter = _mutable(self.filter_profile)
        mutable_profile['functions'][next(iter(mutable_profile['functions']))]['fragments'][0]['raw_hex'] = '00'
        with self.assertRaisesRegex(ValueError, 'fragment changed|body changed'):
            notifications._validate_complete_bodies(mutable_profile, mutable_filter)
        self.assertIsNone(notifications._VALIDATED_BODY_PROFILES)

    def test_expected_notification_header_constants_are_checked_on_cache_hit(self):
        notifications._validate_complete_bodies(self.notification_profile,
                                                self.filter_profile)
        altered = dict(notifications.SNAPSHOT)
        altered['bytes'] += 1
        with patch.object(notifications, 'SNAPSHOT', altered):
            with self.assertRaisesRegex(ValueError, 'source contract changed'):
                notifications.source()

    def test_filter_and_private_dependency_checks_still_run_each_call(self):
        original_filter = notifications.filter_source
        filter_calls = []
        original_verify54 = None
        original_verify57 = None
        original_consumer = None
        from civ6_host.runtime.native import native_event_1be52206, native_event_66ade3b3
        from civ6_host.runtime.native import native_private_ring_consumer
        original_verify54 = native_event_1be52206.verify_source_evidence
        original_verify57 = native_event_66ade3b3.verify_source_evidence
        original_consumer = native_private_ring_consumer.verify_source_evidence
        verifies = [[], [], []]
        with patch.object(notifications, 'filter_source',
                          side_effect=lambda: (filter_calls.append(True), original_filter())[1]), \
             patch.object(native_event_1be52206, 'verify_source_evidence',
                          side_effect=lambda: (verifies[0].append(True), original_verify54())[1]), \
             patch.object(native_event_66ade3b3, 'verify_source_evidence',
                          side_effect=lambda: (verifies[1].append(True), original_verify57())[1]), \
             patch.object(native_private_ring_consumer, 'verify_source_evidence',
                          side_effect=lambda: (verifies[2].append(True), original_consumer())[1]):
            notifications.source()
            notifications.source()
        self.assertEqual(len(filter_calls), 2)
        self.assertEqual([len(rows) for rows in verifies], [2, 2, 2])

        pin_calls = []
        extracted_calls = []
        original_pins = notifications.verify_pinned_files
        original_extracted = notifications.verify_extracted_sources
        with patch.object(notifications, 'verify_pinned_files',
                          side_effect=lambda pins: (pin_calls.append(True), original_pins(pins))[1]), \
             patch.object(notifications, 'verify_extracted_sources',
                          side_effect=lambda refs: (extracted_calls.append(True), original_extracted(refs))[1]):
            notifications.source_dependencies()
            notifications.source_dependencies()
        self.assertEqual(len(pin_calls), 2)
        self.assertEqual(len(extracted_calls), 2)

    def test_notification_live_reader_is_still_invoked_after_body_memoization(self):
        notifications._validate_complete_bodies(self.notification_profile,
                                                self.filter_profile)
        reads = []
        def reader(address, size):
            reads.append((address, size))
            return b'\0' * size
        with patch.object(notifications, 'source', return_value=self.notification_profile):
            with self.assertRaisesRegex(ValueError, 'native code differs'):
                notifications.verify_live(0x10000000, reader)
        self.assertEqual(len(reads), 1)
        self.assertGreater(reads[0][1], 0)

    def test_initial_choice_live_reader_is_still_invoked_after_body_memoization(self):
        choices._validate_complete_bodies(self.choice_profile)
        reads = []
        def reader(address, size):
            reads.append((address, size))
            return b'\0' * size
        with patch.object(choices, 'source', return_value=self.choice_profile):
            with self.assertRaisesRegex(ValueError, 'native body changed'):
                choices.verify_live(0x10000000, reader, 'status')
        self.assertEqual(len(reads), 1)
        self.assertGreater(reads[0][1], 0)


if __name__ == '__main__':
    unittest.main()

import unittest
from collections import OrderedDict
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
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
        choices._RETAINED_SOURCE = None
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

    def test_initial_choice_proof_stays_bound_after_general_cache_eviction(self):
        from civ6_host.runtime.native import native_source_cache as cache

        proof = choices.source('status')
        selected = OrderedDict((key, value) for key, value in cache._CACHE.items() if value is proof)
        self.assertEqual(len(selected), 1)
        with patch.object(cache, '_CACHE', selected), patch.object(cache, '_MAX_ENTRIES', 1):
            choices._source(choices.CURRENT_LITERAL_SOURCE)
            self.assertFalse(any(key[1] == choices.SOURCE[1] for key in cache._CACHE))
            with patch.object(choices, '_source', side_effect=AssertionError('duplicate proof allocation')):
                for family in ('status', 'research', 'production'):
                    self.assertIs(choices.source(family), proof)

    def test_initial_choice_retained_proof_rechecks_file_identity(self):
        choices.source('status')
        original = choices._file_identity
        with (patch.object(choices, '_file_identity', side_effect=lambda path: (*original(path), 1)),
              patch.object(choices, '_source', side_effect=RuntimeError('contents changed')) as load):
            with self.assertRaisesRegex(RuntimeError, 'contents changed'):
                choices.source('status')
        load.assert_called_once_with(choices.SOURCE)

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


class SupervisorProofCacheTests(unittest.TestCase):
    def test_supervisor_bounds_retention_without_skipping_pins_or_changing_worker_policy(self):
        from civ6_host.runtime.native import native_source_cache as cache, network_session

        def write(directory, name, raw):
            path = Path(directory) / name
            path.write_bytes(raw)
            return path, sha256(raw).hexdigest()

        with TemporaryDirectory() as directory, patch.object(cache, '_CACHE', OrderedDict()):
            first = write(directory, 'first.json', b'{"value":"first"}')
            second = write(directory, 'second.json', b'{"value":"second"}')
            large = write(directory, 'large.json', b'{"value":"' + b'x' * 40 + b'"}')
            worker_cached = cache.load_pinned_json(*large)
            with patch.object(network_session, '_SUPERVISOR_PROOF_BYTES', 22):
                network_session._configure_supervisor_proof_cache()
                self.assertEqual(cache._cache_size_for_tests(), 0)
                first_value = cache.load_pinned_json(*first)
                parsed = cache.load_pinned_json(*large)
                self.assertEqual(parsed, worker_cached)
                self.assertIsNot(parsed, worker_cached)
                self.assertIs(cache.load_pinned_json(*first), first_value)
                second_value = cache.load_pinned_json(*second)
                self.assertEqual(cache._cache_size_for_tests(), 1)
                first[0].write_bytes(b'{}')
                with self.assertRaisesRegex(RuntimeError, 'SHA-256 mismatch'):
                    cache.load_pinned_json(*first)
                self.assertIs(cache.load_pinned_json(*second), second_value)
                network_session._configure_supervisor_proof_cache()
                self.assertIs(cache.load_pinned_json(*second), second_value)


if __name__ == '__main__':
    unittest.main()

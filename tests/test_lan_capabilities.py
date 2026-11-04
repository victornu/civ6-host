import hashlib
import struct
import unittest

from civ6_host.runtime.lan_capabilities import ClosedLanBranch, validate_record_shape


class LanCapabilityTests(unittest.TestCase):
    def vector(self, *, changed=None):
        raw = bytearray(64 * 64)
        for player in range(64):
            struct.pack_into('<I', raw, player * 64, player)
            struct.pack_into('<Q', raw, player * 64 + 24, 0x10000 + player * 16)
        if changed is not None:
            changed(raw)
        return dict(status='exact_64_record_span_verified', records_bytes_hex=raw.hex(),
                    records_sha256=hashlib.sha256(raw).hexdigest())

    def test_source_shape_requires_empty_vectors_and_valid_records(self):
        validate_record_shape(self.vector())
        for offset, value in [(32, 1), (40, 1), (48, 1), (24, 0), (64, 2)]:
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                validate_record_shape(self.vector(changed=lambda raw: struct.pack_into('<Q', raw, offset, value)))

    def test_record_hash_and_length_are_checked(self):
        vector = self.vector()
        vector['records_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            validate_record_shape(vector)
        vector = self.vector()
        vector['records_bytes_hex'] = vector['records_bytes_hex'][:-128]
        with self.assertRaises(ValueError):
            validate_record_shape(vector)

    def branch(self):
        branch = object.__new__(ClosedLanBranch)
        branch.players = tuple(0x10000 + p * 16 for p in range(64))
        branch._provider = lambda player: branch.players[player]
        return branch

    def test_all_record_ids_and_explicit_sentinel_are_bounded(self):
        branch = self.branch()
        for player in [*range(64), 0xFFFFFFFF]:
            result = branch.details(player)
            self.assertEqual(result['category'], 3)
            self.assertFalse(result['network_session_qualified'])
            self.assertFalse(result['steam_or_epic_entitlement_queried'])
        for player in [True, False, -1, 64, 0x100000000, '0', 0.0, None]:
            with self.subTest(player=player), self.assertRaises(ValueError):
                branch.details(player)

    def test_provider_change_refuses_before_reporting_a_result(self):
        branch = self.branch()
        branch._provider = lambda player: 0
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            branch.details(63)


if __name__ == '__main__':
    unittest.main()

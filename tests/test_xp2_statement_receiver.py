"""Composed A0 statement producer and deferred receiver with native edges stubbed."""
import struct
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native import native_diplomacy_statement as codec


def scalar(tag, value):
    return struct.pack('<H6xQII', tag, value, 0, 0)


def statement_fields():
    values = {
        'StatementType': 7, 'StatementSubType': 2, 'ResponseType': 0,
        'SessionID': 91, 'FromPlayer': 0, 'ToPlayer': 1, 'Initiator': 0,
        'FromPlayerMood': 3, 'ToPlayerMood': 4, 'AiReason': 8, 'AiModifier': 1,
    }
    fields = {key: scalar(1 if name == 'IsFirstStatementOfType' else
                          2 if name in ('FromPlayer', 'ToPlayer', 'Initiator') else 3,
                          int(name == 'IsFirstStatementOfType') if name == 'IsFirstStatementOfType' else value)
              for name, key in codec.NAMES.items()
              for value in (values.get(name, 0),)}
    fields[codec.OPAQUE_KEY] = scalar(3, 0xA0B1C2D3)
    fields[codec.BLOB_KEY] = struct.pack('<H6xQII', 13, 0xD10000, 8, 553648129)
    return fields


class XP2StatementReceiverTests(unittest.TestCase):
    def setUp(self):
        from test_a0_family_service import A0FamilyServiceTests
        self.base_fixture = A0FamilyServiceTests()
        self.base_fixture.setUpClass()
        self.addCleanup(self.base_fixture.doCleanups)
        h, d, a, c, reader, before, bindings = self.base_fixture.fixture(XP2_CORE_SHA256)
        self.host, self.deferred, self.arguments = h, d, a
        self.owner, self.reader = c, reader
        self.before, self.bindings = before, bindings
        self.backend = NS(core=d.core, host=h, context=d.context,
                          load_abi=NS(core_sha256=XP2_CORE_SHA256), stage='prepared', prefix=None,
                          check_thread=Mock(), destroyed=False, poisoned=False)
        self.backend.core._civ6_host_execution_image = NS(image_sha256='fixture-current-xp2')
        self.owner._foundation_backend = self.backend
        empty_profile = NS(record_types_by_kind={})
        self.owner.foundation_event_profile = self.owner._foundation_event_profile = empty_profile
        self.owner.combat_event_profile = self.owner._combat_event_profile = empty_profile
        self.owner.read = lambda address, size: bytes(size)
        self.reader.read.side_effect = lambda address, size: (
            struct.pack('<ii', 37, 12) if address == 0xD10000 and size == 8 else bytes(size))
        self.owner.arguments.reader.next_node = object()
        self.map_fields = statement_fields()
        self.clone_fields = {}
        self.map_owners = {}

        class FakeMap:
            def __init__(inner, core, borrowed, *, read, core_sha256):
                inner.core, inner.base = core, core._handle
                inner.source, inner.pointer = borrowed, 0x700000 + len(self.map_owners) * 0x1000
                inner.core_sha256 = core_sha256
                inner.closed = inner.poisoned = False
                self.clone_fields[inner.pointer] = dict(self.map_fields)
                self.map_owners[inner.pointer] = inner
            def close(inner):
                if inner.closed or inner.poisoned:
                    raise RuntimeError('fake map unavailable')
                inner.closed = True

        self.patches = patch.multiple(
            'civ6_host.runtime.a0_diplomacy_statement.source',
            source_dependencies=Mock(return_value={}), verify_live=Mock(return_value=__import__(
                'civ6_host.runtime.xp2_statement_source', fromlist=['PROFILE']).PROFILE))
        self.patches.start()
        self.addCleanup(self.patches.stop)
        from civ6_host.runtime import a0_diplomacy_statement as statement
        self.statement = statement
        # The real dispatch imports these names from their defining modules.
        self.native_patches = patch.multiple(
            'civ6_host.runtime.native.native_combat_map_owner',
            NativeCombatMapOwner=FakeMap)
        self.native_patches.start(); self.addCleanup(self.native_patches.stop)
        self.copy_patches = patch('civ6_host.runtime.native.native_event_argument_tree.read_event_fields',
                                  side_effect=lambda pointer, *args, **kwargs:
                                  dict(self.clone_fields[pointer]))
        self.copy_patches.start(); self.addCleanup(self.copy_patches.stop)
        from civ6_host.runtime.a0_diplomacy_statement import enable
        enable(self.owner, self.backend)
        # The owned continuation becomes available only after profile enable;
        # its identity then borrows this exact deferred queue.
        prefix = NS(deferred_events=d)
        self.backend.prefix = prefix
        from civ6_host.runtime.xp1_continuation import SavedContinuation
        token = object.__new__(SavedContinuation)
        token.owner, token.prefix = self.backend, prefix
        token.poisoned = False
        class Registry:
            def validate(inner, child):
                if child not in (prefix.ui_child, prefix.game_child):
                    raise ValueError('foreign continuation child')
        runtime = NS(registry=Registry())
        ui_child, game_child = object(), object()
        publisher = NS(_xp1_continuation=token)
        transport = NS(backend=self.backend)
        publication = NS(owner=self.backend, completed=True)
        lease = NS(owner=self.backend, prefix=prefix, continuation=token,
                   publication_attempt=publication, publication_finished=True)
        lease._check_state = lambda stage, busy: (
            None if (stage == 'xp1-continuation-active' and busy is True)
            else (_ for _ in ()).throw(ValueError('continuation lease stage differs')))
        view = NS(owner=self.backend, completed=True, publication=publication)
        publication.lease = lease
        prefix.runtime, prefix.ui_child, prefix.game_child = runtime, ui_child, game_child
        prefix.actions, prefix.view_publisher = transport, publisher
        publisher._xp1_continuation = token
        from civ6_host.runtime.native.native_episode_identity import initialize_episode
        identity = initialize_episode(prefix)
        token.runtime, token.ui_child, token.game_child = runtime, ui_child, game_child
        token.transport, token.publisher, token.view = transport, publisher, view
        token.publication, token.lease, token.identity = publication, lease, identity
        self.backend._xp1_player_view = view
        self.backend.stage, self.backend.busy = 'xp1-continuation-active', True
        self.backend._xp1_continuation = token
        lease.continuation = token
        lease.publication_attempt = publication
        self.saved = NS(backend=self.backend, continuation=token, prefix=prefix,
                        _check_active=lambda: token.check(active=True))
        from civ6_host.runtime.native.native_combat_map_owner import CombatMapRegistry
        d.combat_map_registry = CombatMapRegistry(limit=64, core_sha256=XP2_CORE_SHA256)

    def dispatch(self):
        self.reader.fields.return_value = {0x1234: scalar(3, 0)}
        return self.arguments.dispatch(self.host.pointer, codec.EVENT_KIND, 0x8000)

    def test_composed_enqueue_fifo_deep_copy_and_pointer_free_explicit_choice(self):
        from civ6_host.runtime.native.native_combat_map_owner import CombatMapRegistry
        from civ6_host.runtime.native.native_diplomacy_statement import StatementReceiver
        self.assertIs(type(self.deferred.combat_map_registry), CombatMapRegistry)
        self.assertEqual((self.owner.host_notification_counter, self.owner.host_metadata_counter), (0, 0))
        self.assertEqual(self.dispatch(), 0)
        first = self.deferred.pending[0]
        self.assertEqual(self.dispatch(), 0)
        self.assertEqual([int.from_bytes(row[8:12], 'little') for row in self.deferred.pending], [1, 2])
        self.assertEqual([int.from_bytes(row[4:8], 'little') for row in self.deferred.pending], [132, 132])
        # Mutating the producer's borrowed values after publication cannot alter
        # the cloned native map that the receiver later reads.
        self.map_fields[codec.NAMES['FromPlayer']] = scalar(2, 99)
        self.assertEqual(self.clone_fields[0x700000][codec.NAMES['FromPlayer']], scalar(2, 0))
        empty_state_before = dict(self.owner.empty_receiver_state)
        self.assertEqual(self.deferred.drain(), 2)
        self.assertEqual(self.deferred.pending, [])
        self.assertEqual(self.deferred.consumed_count, 2)
        self.assertEqual(len(self.deferred.pending_diplomacy_statements), 2)
        choice = self.deferred.pending_diplomacy_statements[0]
        self.assertEqual(choice['fields']['FromPlayer'], 0)
        self.assertEqual(choice['fields']['ToPlayer'], 1)
        self.assertEqual(choice['opaque_9ec5f4e8'], 0xA0B1C2D3)
        self.assertEqual(choice['opaque_a005ae08_hex'], struct.pack('<ii', 37, 12).hex())
        self.assertFalse(choice['automatic_response'])
        self.assertFalse(choice['learner_exposure_validated'])
        self.assertNotIn('pointer', choice)
        self.assertIs(type(self.deferred.statement_consumer), StatementReceiver)
        self.assertEqual(self.deferred.combat_map_registry.entries, {})
        self.assertEqual(self.deferred.statement_consumer.busy, False)
        self.assertEqual((self.owner.host_notification_counter, self.owner.host_metadata_counter), (0, 0))
        self.assertEqual(self.owner.empty_receiver_state, empty_state_before)
        self.assertNotIn('service_flags', self.owner.empty_receiver_state)
        self.assertEqual(self.owner._foundation_borrow, None)
        self.assertIsNone(self.owner.active_kind)
        self.assertTrue(first.startswith(struct.pack('<II', 112, 132)))

    def test_unqualified_foreign_owner_duplicate_and_foreign_registry_refuse_delivery(self):
        self.assertTrue(self.statement.require_receiver(self.saved))
        foreign = NS(backend=NS(), continuation=object(), prefix=self.saved.prefix,
                     _check_active=lambda: None)
        with self.assertRaises(ValueError):
            self.statement.require_receiver(foreign)
        self.assertEqual(self.deferred.pending_diplomacy_statements, [])

        self.dispatch()
        self.deferred.pending_diplomacy_statements.append(
            dict(event_sequence=1, fields={}, opaque_9ec5f4e8=0, opaque_a005ae08_hex=None,
                 source_proof_sha256=codec.PROOF_SHA256, learner_exposure_validated=False,
                 automatic_response=False))
        with self.assertRaises(ValueError):
            self.deferred.drain()
        self.assertTrue(self.deferred.statement_consumer.poisoned)
        self.assertEqual(len(self.deferred.pending), 1)
        self.assertTrue(self.deferred.combat_map_registry.entries)

    def test_foreign_registry_refuses_before_choice_delivery(self):
        from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
        from civ6_host.runtime.native.native_combat_map_owner import CombatMapRegistry
        self.dispatch()
        self.deferred.combat_map_registry = CombatMapRegistry(limit=64, core_sha256=XP1_CORE_SHA256)
        with self.assertRaises(ValueError):
            self.deferred.drain()
        self.assertEqual(self.deferred.pending_diplomacy_statements, [])
        self.assertEqual(len(self.deferred.pending), 1)
        self.assertIsNone(self.deferred.statement_consumer)

    def test_saved_continuation_surface_used_by_receiver_is_not_native_patched(self):
        # The runtime token itself is a real SavedContinuation instance and is
        # tied to this backend, prefix and A0 FIFO. Its public action-owner
        # _check_active method lives on SavedLoadOwner, not SavedContinuation.
        from civ6_host.runtime.xp1_continuation import SavedContinuation
        self.assertIs(type(self.backend._xp1_continuation), SavedContinuation)
        self.assertIs(self.backend._xp1_continuation.owner, self.backend)
        self.assertIs(self.backend._xp1_continuation.prefix.deferred_events, self.deferred)
        self.assertFalse(hasattr(SavedContinuation, '_check_active'))


if __name__ == '__main__':
    unittest.main()

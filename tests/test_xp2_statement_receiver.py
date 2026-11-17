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

    def test_deal_acknowledgement_preserves_the_owned_map_and_never_projects_its_pointer(self):
        from civ6_host.runtime.xp2_deal_draft import project_statement_fields, statement_scope

        extensions = {
            0x26f0905f: struct.pack('<H6xQII', 0x16, 0xD20000, 0, 0x41000000),
            0x3c255a0b: scalar(3, 0),
            0xfe1e2e5d: scalar(3, 0),
        }
        self.map_fields.update(extensions)
        for key, tag, value in (('StatementType', 3, 0x84e9dc8a),
                                ('StatementSubType', 3, 0xb6fa1284),
                                ('ResponseType', 3, 0xcaff10c3),
                                ('FromPlayer', 2, 1), ('ToPlayer', 2, 0)):
            self.map_fields[codec.NAMES[key]] = scalar(tag, value)
        token = self.saved.continuation
        with statement_scope(token, 0, 1):
            scope = token._xp2_deal_statement_scope
            self.assertIs(project_statement_fields(self.map_fields, None), self.map_fields)
            for field, variant in ((0xfe1e2e5d, scalar(3, 1)),
                                   (0x26f0905f, scalar(0x16, 0)),
                                   (codec.NAMES['FromPlayer'], scalar(2, 0)),
                                   (0x11111111, scalar(3, 0))):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    project_statement_fields({**self.map_fields, field: variant}, scope)
            self.assertEqual(self.dispatch(), 0)
            self.assertEqual(self.clone_fields[0x700000], self.map_fields)
            self.assertEqual(self.deferred.drain(), 1)
        self.assertFalse(hasattr(token, '_xp2_deal_statement_scope'))
        choice, = self.deferred.pending_diplomacy_statements
        self.assertEqual(choice['fields']['StatementType'], 0x84e9dc8a)
        self.assertEqual(set(choice['fields']), set(codec.NAMES))
        self.assertEqual(self.deferred.combat_map_registry.entries, {})

    def test_gold_inspection_response_is_joined_in_its_active_request_only(self):
        from civ6_host.runtime.xp2_deal_draft import project_statement_fields, statement_scope

        self.map_fields.update({
            0x26f0905f: struct.pack('<H6xQII', 0x16, 0xD20000, 0, 0x41000000),
            0x3c255a0b: scalar(3, 1),
            0xfe1e2e5d: scalar(3, 7),
        })
        for key, tag, value in (('StatementType', 3, 0x84e9dc8a),
                                ('StatementSubType', 3, 0x988a4fb4),
                                ('ResponseType', 3, 0x7332f7d6),
                                ('FromPlayer', 2, 1), ('ToPlayer', 2, 0)):
            self.map_fields[codec.NAMES[key]] = scalar(tag, value)
        token = self.saved.continuation
        with statement_scope(token, 0, 1, operation='propose'):
            with self.assertRaisesRegex(ValueError, 'current proposal'):
                project_statement_fields(self.map_fields, token._xp2_deal_statement_scope)
        with statement_scope(token, 0, 1, operation='inspect'):
            self.assertEqual(self.dispatch(), 0)
            self.assertEqual(self.deferred.drain(), 1)
        choice, = self.deferred.pending_diplomacy_statements
        self.assertEqual(choice['deal_reply'], dict(operation='inspect', outcome='accepted'))
        self.assertEqual(set(choice['fields']), set(codec.NAMES))
        self.assertEqual(self.deferred.combat_map_registry.entries, {})

    def test_equalize_replies_require_the_exact_native_action_and_statement_pair(self):
        from civ6_host.runtime.xp2_deal_draft import project_statement_fields, statement_scope

        self.map_fields.update({
            0x26f0905f: struct.pack('<H6xQII', 0x16, 0xD20000, 0, 0x41000000),
            0xfe1e2e5d: scalar(3, 6),
        })
        self.map_fields[codec.NAMES['StatementType']] = scalar(3, 0x84e9dc8a)
        self.map_fields[codec.NAMES['FromPlayer']] = scalar(2, 1)
        self.map_fields[codec.NAMES['ToPlayer']] = scalar(2, 0)
        token = self.saved.continuation
        with statement_scope(token, 0, 1, operation='equalize'):
            scope = token._xp2_deal_statement_scope
            for action, subtype, response, outcome in (
                    (3, 0x7332f7d6, 0x7332f7d6, 'adjusted'),
                    (10, 0xb6fa1284, 0, 'equalize_failed'),
                    (2, 0x6dce22fe, 0x164480cd, 'rejected')):
                with self.subTest(action=action):
                    fields = {**self.map_fields, 0x3c255a0b: scalar(3, action),
                              codec.NAMES['StatementSubType']: scalar(3, subtype),
                              codec.NAMES['ResponseType']: scalar(3, response)}
                    reply = {}
                    projected = project_statement_fields(fields, scope, reply=reply)
                    self.assertEqual(reply, dict(operation='equalize', outcome=outcome))
                    self.assertNotIn(0xfe1e2e5d, projected)
                    for changed in ({0xfe1e2e5d: scalar(3, 7)},
                                    {codec.NAMES['ResponseType']: scalar(3, response ^ 1)}):
                        with self.assertRaisesRegex(ValueError, 'Unknown native negotiation reply'):
                            project_statement_fields({**fields, **changed}, scope)

    def test_gold_transaction_and_positive_statement_must_agree_before_delivery(self):
        from civ6_host.runtime.xp2_deal_gold import validate_acceptance

        pid, target, sid, amount, per_turn = 2, 4, 5, 19, 6

        def item(duration, value, giver=pid, receiver=target):
            return struct.pack('<I24xIII16xI', 0x05eb0df7, duration, giver, receiver, value)

        def archives(*items):
            terms = struct.pack('<I15xI', 5, len(items)) + b''.join(items)
            deal = struct.pack('<IIII', 0xf06250e4, 1, pid, target) + terms
            confirm = (struct.pack('<III', 0xa4172391, pid, sid) + encoded + terms).ljust(455+60*len(items),b'\x00')
            return deal, confirm, terms
        values = ((0xbaef29be, 3, 0x84e9dc8a), (0x1226a98f, 3, 0xc20ef7ff),
                  (0x9bba1fc1, 3, 0x7332f7d6), (0x9c594aff, 2, pid),
                  (0x18383f56, 2, target), (0x3c255a0b, 3, 1), (0xfe1e2e5d, 3, 0))
        encoded = b''.join(struct.pack('<II8xI', *value) for value in values)
        deal, confirm, terms = archives(item(0,amount))
        validate_acceptance([deal, confirm], pid, target, sid, amount)
        changed = confirm.replace(terms, terms[:-1]+b'\x01')
        for pair in ([confirm,deal], [deal,changed], [deal], [deal,confirm,confirm]):
            with self.subTest(count=len(pair)), self.assertRaises(RuntimeError):
                validate_acceptance(pair, pid, target, sid, amount)
        with self.assertRaisesRegex(RuntimeError, 'different terms'):
            validate_acceptance([deal,confirm], pid, target, sid, amount+1)
        recurring = item(30,per_turn)
        deal, confirm, _ = archives(recurring,item(0,amount))
        validate_acceptance([deal,confirm], pid, target, sid, amount, per_turn)
        deal, confirm, _ = archives(recurring)
        validate_acceptance([deal,confirm], pid, target, sid, 0, per_turn)
        incoming = item(0,7,target,pid)
        deal, confirm, _ = archives(recurring,incoming)
        validate_acceptance([deal,confirm], pid, target, sid, 0, per_turn, requested=(7,0))
        with self.assertRaisesRegex(RuntimeError, 'different terms'):
            validate_acceptance([deal,confirm], pid, target, sid, 7, per_turn)
        for invalid in (item(29,per_turn), item(30,per_turn,giver=target), item(30,per_turn+1), item(0,per_turn)):
            deal, confirm, _ = archives(item(0,amount),invalid)
            with self.subTest(invalid=invalid), self.assertRaisesRegex(RuntimeError, 'different terms'):
                validate_acceptance([deal,confirm], pid, target, sid, amount, per_turn)

    def test_gold_confirmation_echo_joins_only_the_active_acceptance(self):
        from civ6_host.runtime.xp2_deal_draft import project_statement_fields, statement_scope

        self.map_fields.update({
            0x26f0905f: struct.pack('<H6xQII', 0x16, 0xD20000, 0, 0x41000000),
            0x3c255a0b: scalar(3, 0),
            0xfe1e2e5d: scalar(3, 0),
        })
        for key, tag, value in (('StatementType', 3, 0x84e9dc8a),
                                ('StatementSubType', 3, 0xc20ef7ff),
                                ('ResponseType', 3, 0x7332f7d6),
                                ('FromPlayer', 2, 1), ('ToPlayer', 2, 0)):
            self.map_fields[codec.NAMES[key]] = scalar(tag, value)
        token = self.saved.continuation
        with statement_scope(token, 0, 1, operation='inspect'):
            with self.assertRaises(ValueError):
                project_statement_fields(self.map_fields, token._xp2_deal_statement_scope)
        with statement_scope(token, 0, 1, operation='accept'):
            self.assertEqual(self.dispatch(), 0)
            self.assertEqual(self.deferred.drain(), 1)
        choice, = self.deferred.pending_diplomacy_statements
        self.assertEqual(choice['deal_reply'], dict(operation='accept', outcome='accepted'))
        self.assertEqual(self.deferred.combat_map_registry.entries, {})

    def test_saved_control_reads_only_one_settled_diplomacy_statement(self):
        from civ6_host.runtime import captured_saved_load
        from civ6_host.runtime.control_input_service import ControlInputService
        from civ6_host.runtime.saved_load_services import SavedLoadServices
        from civ6_host.runtime.xp1_action_transport import SavedActionTransport

        # Drive the actual XP2 A0 and DeferredService before exercising the
        # captured Load guard. The bundle hash and native endpoints are fixtures.
        self.dispatch()
        self.assertEqual(self.deferred.drain(), 1)
        deferred = self.deferred
        backend = self.backend
        backend.captured_bundle = object()
        services = SavedLoadServices.__new__(SavedLoadServices)
        controller = ControlInputService.__new__(ControlInputService)
        controller.deferred, controller.local_player_id, controller._check = deferred, 0, Mock()
        controller._a0_event_owner = self.owner
        controller.turn_begin_state = self.owner.turn_begin_state = object()
        self.owner.controller_owner = controller
        transport = SavedActionTransport.__new__(SavedActionTransport)
        transport.services, transport.pending, transport.check = services, [], Mock()
        services.backend, services.host = backend, self.host
        services.core_sha256, services.check = XP2_CORE_SHA256, Mock()
        services.deferred_events, services.control_inputs = deferred, controller
        services.event_arguments, services.actions = self.arguments, transport
        services.events = NS(_check=Mock(), dispatch_depth=0, script_arguments=NS(live_count=0))
        services.contexts = NS(check=Mock(), receiver=321, depth=0, lock_depth=0)
        services.map_arguments = NS(check=Mock(), live={})
        backend.prefix = services

        with patch.object(captured_saved_load, '_sha', return_value=XP2_CORE_SHA256):
            def inspect(**flags):
                return captured_saved_load.control_snapshot(backend, empty=True, **flags)

            with self.assertRaisesRegex(RuntimeError, 'unanswered diplomacy'):
                inspect()
            ledger = deferred.pending_diplomacy_statements
            statement = ledger[0]
            self.assertEqual(inspect(allow_diplomacy=True)['consumed'], statement['event_sequence'])
            self.assertEqual(ledger, [statement])
            with self.assertRaisesRegex(ValueError, 'action/interrupted-turn'):
                inspect(allow_diplomacy=True, pending_round_actor=0)
            deferred.statement_consumer.poisoned = True
            with self.assertRaisesRegex(RuntimeError, 'poisoned'):
                inspect(allow_diplomacy=True)
            deferred.statement_consumer.poisoned = False
            ledger.clear()
            self.assertEqual(inspect(allow_diplomacy=True), inspect())

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

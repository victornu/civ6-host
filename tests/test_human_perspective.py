import unittest
from unittest.mock import patch

from civ6_host.runtime import human_perspective as perspective
_REAL_SWITCH = perspective._switch


class _Events:
    def __init__(self, *, fail_drain=False):
        self.pending = []
        self.fail_drain = fail_drain
        self.drains = 0
        self.unregistered_player_events = []

    def drain_empty_receivers(self):
        self.drains += 1
        if self.fail_drain:
            raise RuntimeError('unknown native callback')


class _Actions:
    def __init__(self):
        self.pending = []
        self.updates = 0
        self.reads = 0

    def read(self, address, size):
        self.reads += 1
        if size != 4:
            raise AssertionError('unexpected native read size')
        return bytes(4)

    def update_game_once(self):
        self.updates += 1
        raise AssertionError('perspective collection must not update the game')


class _Publisher:
    _closed = False

    def __init__(self):
        self.publishes = 0

    def publish(self):
        self.publishes += 1


class _Runtime:
    def __init__(self, prefix, *, invalid_human=False):
        self.prefix = prefix
        self.invalid_human = invalid_human

    def execute(self, child, source, label):
        if child is not self.prefix.game_child:
            raise AssertionError('Setter is registered only in the gameplay child')
        text = source.decode('ascii')
        if b'SetLocalPlayerAndObserver' in source:
            import re
            match = re.search(r'local pid=(\d+); local observer=(\d+)', text)
            if match is None:
                raise AssertionError('setter target was not explicit')
            local = int(match.group(1))
            observer = int(match.group(2))
            self.prefix.local = local
            self.prefix.observer = observer
            return None
        raise AssertionError('Unexpected gameplay command')

    def evaluate_text(self, child, source, label, *, capacity):
        if child is not self.prefix.ui_child or b'SetLocalPlayerAndObserver' in source:
            raise AssertionError('Public observations must use the read-only UI child')
        if b'@human_perspective_state' in label:
            if self.invalid_human:
                raise RuntimeError('requested player is not a live human')
            ids = (0, 1, 2, 3)
            rows = ';'.join(f'{pid},1,{int(pid == 0)},{int(pid == 0)}' for pid in ids)
            return f'3|{self.prefix.local}|{self.prefix.observer}|{rows}'.encode('ascii')
        raise AssertionError(f'unexpected Lua evaluation: {label!r}')


class _Prefix:
    def __init__(self, *, fail_drain=False, invalid_human=False):
        self.core = type('Core', (), {'_handle': 0x180000000})()
        self.local = 0
        self.observer = 0
        self.actions = _Actions()
        self.deferred_events = _Events(fail_drain=fail_drain)
        self.view_publisher = _Publisher()
        self.runtime = _Runtime(self, invalid_human=invalid_human)
        self.ui_child = object()
        self.game_child = object()

    def inspect_player_view(self, *, player_ids):
        return {
            'current_game_turn': 3,
            'local_player': self.local,
            'players': [
                {'player_id': pid, 'active': pid == 0, 'complete': pid == 0}
                for pid in player_ids
            ],
        }


class _Owner:
    def __init__(self, prefix):
        self.prefix = prefix
        self.inputs = type('Inputs', (), {'profile': object()})()
        self.loaded_roster = b'3|74|46|0|1|2|3'
        self.hotseat_actor = 0
        self.hotseat_turn = 3
        self.stage = 'official-hotseat-decision-ready'
        self.busy = False
        self.poisoned = False
        self.destroyed = False
        self.events = []
        self.checks = 0

    def check_thread(self):
        self.checks += 1

    def control(self, *, empty):
        if empty is not True:
            raise AssertionError('empty control snapshot required')
        return {
            'pending_count': 0,
            'sequence': 0,
            'consumed': 0,
            'notification_counter': 0,
            'metadata_counter': 0,
        }

    def emit(self, event, **fields):
        self.events.append((event, fields))


class HumanPerspectiveTests(unittest.TestCase):
    def setUp(self):
        def switch(prefix, local, observer):
            prefix.local, prefix.observer = local, observer
        self.addCleanup(patch.stopall)
        patch.object(perspective, '_switch', side_effect=switch).start()

    def test_native_switch_uses_automatic_route_and_checks_result(self):
        from unittest.mock import Mock
        prefix = _Prefix()
        getter, update = Mock(return_value=0x123456), Mock(return_value=1)
        addresses = []
        def factory(*signature):
            def bind(address):
                addresses.append(address)
                return getter if address == prefix.core._handle + 0x2218e0 else update
            return bind
        with patch('ctypes.CFUNCTYPE', side_effect=factory):
            _REAL_SWITCH(prefix, 1, 1)
            self.assertEqual(addresses, [prefix.core._handle+0x2218e0,prefix.core._handle+0x2233a0])
            update.assert_called_once_with(0x123456, 1)
            update.return_value = 0
            with self.assertRaisesRegex(RuntimeError, 'update refused'):
                _REAL_SWITCH(prefix, 1, 1)

    def test_code_verification_uses_native_memory_reader_not_lua_runtime(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        read = Mock(return_value=b'\x90')
        owner = SimpleNamespace(prefix=SimpleNamespace(core=SimpleNamespace(_handle=0x1000),
            actions=SimpleNamespace(read=read), runtime=object()))
        with patch.object(perspective, '_read_proofs', return_value={}), \
             patch.object(perspective, '_live_instruction_set', return_value={0x180000123:b'\x90'}), \
             patch('civ6_host.runtime.native.native_world_configuration.verify_source'), \
             patch('civ6_host.runtime.native.native_diplomacy_configuration.verify_source'), \
             patch('civ6_host.runtime.provenance.verify_installation'):
            result = perspective.verify_source(owner)
        read.assert_called_once_with(0x1123, 1)
        self.assertEqual(result['live_instruction_count'], 1)

    def test_source_pins_expose_all_private_receipts(self):
        self.assertEqual(
            perspective.source_pins(),
            {
                'work/host-simultaneous/player-perspective-neutral-route.json': 'a6c99d4660fe48f9f90ee48f3bc51995b405e660b6b1250ef971f02e29bd4c3b',
                'evidence/native-local-player-perspective.json': '6d9924ed692afff7d6acd76e11619b05f95c08d613c14945461ff635495fcb52',
                'work/host-simultaneous/native-mode-getters.json': '65ba306c2d906affbe354bb828e7ba9cd9ba1de2717b0f7a7fe05b4bb18fc528',
                'work/host-simultaneous/perspective-routes.json': '210b3ee39a64dc2d36b1176762da61467b30027092b88c4a072f4c5f21511c5c',
                'evidence/native-world-configuration/62dd74236082b2da47fc5a34fd1b59276c1abc951ac7e717e053630a3660e31e.json': '62dd74236082b2da47fc5a34fd1b59276c1abc951ac7e717e053630a3660e31e',
                'evidence/native-diplomacy-configuration/84fce676a2438dd67001f44658e6ccaea00bd7dc7663bfcd8307f568214d83eb.json': '84fce676a2438dd67001f44658e6ccaea00bd7dc7663bfcd8307f568214d83eb',
            },
        )

    def test_base_four_view_switches_restores_and_returns_only_public_view(self):
        prefix = _Prefix()
        owner = _Owner(prefix)
        profile = type('Profile', (), {})()
        inputs = type('Inputs', (), {'profile': profile})()

        def validate(candidate, *, stage):
            self.assertIs(candidate, owner)
            self.assertEqual(stage, 'official-hotseat-decision-ready')
            return inputs

        observation = {'schema': 'public', 'player_id': 2, 'turn': 3}
        player_map = {'schema': 'map', 'player_id': 2, 'turn': 3}
        config = {'is_any_multiplayer': True, 'players': {pid: {'is_human': True} for pid in (0, 1, 2, 3)}}
        with (
            patch('civ6_host.runtime.native.native_official_load.HOTSEAT_FOUR_PROFILE', profile),
            patch('civ6_host.runtime.native.native_official_postload.validate_owner', validate),
            patch('civ6_host.runtime.native.native_world_configuration.read', return_value=config),
            patch.object(perspective, 'verify_source', return_value={'source_pins': perspective.source_pins(), 'live_instruction_count': 144}),
            patch('civ6_host.runtime.native.native_player_observation.observe_player', return_value=observation) as observe,
            patch('civ6_host.runtime.native.native_saved_player_map.observe', return_value=player_map) as observe_map,
        ):
            result = perspective.collect_player_view(owner, 2, player_ids=(0, 1, 2, 3))

        self.assertEqual(
            result,
            {
                'observation': observation,
                'player_map': player_map,
                'player_turn': {'active': False, 'turn_active_complete': False},
            },
        )
        observe.assert_called_once_with(prefix.runtime, prefix.ui_child, 2)
        observe_map.assert_called_once_with(prefix, observation)
        self.assertEqual((prefix.local, prefix.observer), (0, 0))
        self.assertEqual(prefix.deferred_events.drains, 2)
        self.assertEqual(prefix.view_publisher.publishes, 2)
        self.assertEqual(prefix.actions.updates, 0)
        self.assertFalse(owner.busy)
        self.assertFalse(owner.poisoned)
        diagnostic = [row for row in owner.events if row[0] == 'human_perspective_view_diagnostic']
        self.assertEqual(len(diagnostic), 1)
        self.assertEqual(diagnostic[0][1]['player_id'], 2)
        self.assertFalse(diagnostic[0][1]['native_perspective_neutrality_proven'])

    def test_non_taken_application_configuration_refuses_before_mutation(self):
        prefix = _Prefix()
        owner = _Owner(prefix)
        profile = type('Profile', (), {})()
        inputs = type('Inputs', (), {'profile': profile})()
        config = {'is_any_multiplayer': True, 'players': {pid: {'is_human': pid != 1} for pid in (0, 1, 2, 3)}}
        with (
            patch('civ6_host.runtime.native.native_official_load.HOTSEAT_FOUR_PROFILE', profile),
            patch('civ6_host.runtime.native.native_official_postload.validate_owner', return_value=inputs),
            patch('civ6_host.runtime.native.native_world_configuration.read', return_value=config),
            patch.object(perspective, 'verify_source', return_value={'source_pins': perspective.source_pins(), 'live_instruction_count': 144}),
        ):
            with self.assertRaisesRegex(RuntimeError, 'SS_TAKEN'):
                perspective.collect_player_view(owner, 1, player_ids=(0, 1, 2, 3))
        self.assertEqual((prefix.local, prefix.observer), (0, 0))
        self.assertFalse(owner.poisoned)

    def test_unknown_callback_refuses_and_poisons_without_action_or_update(self):
        prefix = _Prefix(fail_drain=True)
        owner = _Owner(prefix)
        profile = type('Profile', (), {})()
        inputs = type('Inputs', (), {'profile': profile})()
        config = {'is_any_multiplayer': True, 'players': {pid: {'is_human': True} for pid in (0, 1, 2, 3)}}
        with (
            patch('civ6_host.runtime.native.native_official_load.HOTSEAT_FOUR_PROFILE', profile),
            patch('civ6_host.runtime.native.native_official_postload.validate_owner', return_value=inputs),
            patch('civ6_host.runtime.native.native_world_configuration.read', return_value=config),
            patch.object(perspective, 'verify_source', return_value={'source_pins': perspective.source_pins(), 'live_instruction_count': 144}),
        ):
            with self.assertRaisesRegex(RuntimeError, 'unknown native callback'):
                perspective.collect_player_view(owner, 1, player_ids=(0, 1, 2, 3))
        self.assertTrue(owner.poisoned)
        self.assertEqual(owner.stage, 'poisoned')
        self.assertEqual((prefix.local, prefix.observer), (1, 1))
        self.assertEqual(prefix.actions.updates, 0)
        self.assertFalse(owner.busy)

    def test_bad_roster_refuses_before_source_check_or_native_mutation(self):
        prefix = _Prefix()
        owner = _Owner(prefix)
        with patch.object(perspective, 'verify_source') as verify:
            with self.assertRaisesRegex(ValueError, 'exact four-player roster'):
                perspective.collect_player_view(owner, 1, player_ids=(0, 1))
        verify.assert_not_called()
        self.assertEqual((prefix.local, prefix.observer), (0, 0))
        self.assertFalse(owner.poisoned)

    def test_nonhuman_slot_refuses_before_mutation(self):
        prefix = _Prefix(invalid_human=True)
        owner = _Owner(prefix)
        profile = type('Profile', (), {})()
        inputs = type('Inputs', (), {'profile': profile})()
        with (
            patch('civ6_host.runtime.native.native_official_load.HOTSEAT_FOUR_PROFILE', profile),
            patch('civ6_host.runtime.native.native_official_postload.validate_owner', return_value=inputs),
            patch.object(perspective, 'verify_source', return_value={'source_pins': perspective.source_pins(), 'live_instruction_count': 144}),
        ):
            with self.assertRaisesRegex(RuntimeError, 'not a live human'):
                perspective.collect_player_view(owner, 1, player_ids=(0, 1, 2, 3))
        self.assertEqual((prefix.local, prefix.observer), (0, 0))
        self.assertFalse(owner.poisoned)

    def test_unverified_static_sources_refuse_before_mutation(self):
        prefix = _Prefix()
        owner = _Owner(prefix)
        profile = type('Profile', (), {})()
        inputs = type('Inputs', (), {'profile': profile})()
        with (
            patch('civ6_host.runtime.native.native_official_load.HOTSEAT_FOUR_PROFILE', profile),
            patch('civ6_host.runtime.native.native_official_postload.validate_owner', return_value=inputs),
            patch.object(perspective, 'verify_source', side_effect=RuntimeError('perspective proof hash changed')),
        ):
            with self.assertRaisesRegex(RuntimeError, 'proof hash changed'):
                perspective.collect_player_view(owner, 1, player_ids=(0, 1, 2, 3))
        self.assertEqual((prefix.local, prefix.observer), (0, 0))
        self.assertFalse(owner.poisoned)


if __name__ == '__main__':
    unittest.main()

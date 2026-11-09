import unittest
from copy import deepcopy

from civ6_host.contracts import policy_unlock


def catalogue(**overrides):
    value = dict(player_id=0, turn=12, cost=100, currency='YIELD_GOLD',
                 reason='available', can_unlock=True)
    value.update(overrides)
    return value


class PolicyUnlockContractTests(unittest.TestCase):
    def test_available_gold_and_faith_catalogues_project_one_action(self):
        for currency in ('YIELD_GOLD', 'YIELD_FAITH'):
            value = catalogue(currency=currency)
            self.assertIs(policy_unlock.validate(value, 0, 12), value)
            self.assertEqual(policy_unlock.actions(value), [dict(
                kind='policy_unlock', cost=100, currency=currency)])

    def test_valid_refusals_have_no_action(self):
        cases = [
            catalogue(reason='already_changed', can_unlock=False),
            catalogue(cost=0, reason='no_cost', can_unlock=False),
            catalogue(reason='insufficient_funds', can_unlock=False),
            catalogue(reason='native_unavailable', can_unlock=False),
        ]
        for value in cases:
            with self.subTest(reason=value['reason']):
                policy_unlock.validate(value, 0, 12)
                self.assertEqual(policy_unlock.actions(value), [])
        self.assertEqual(policy_unlock.actions(None), [])

    def test_native_cost_and_identity_boundaries_are_strict(self):
        policy_unlock.validate(catalogue(cost=0x7fffffff), 0, 12)
        for bad in (True, -1, 0x80000000, 1.0):
            with self.subTest(cost=bad):
                with self.assertRaises(ValueError):
                    policy_unlock.validate(catalogue(cost=bad), 0, 12)
        for pid, turn in ((-1, 12), (64, 12), (True, 12), (0, -1), (0, 0x100000000)):
            with self.subTest(pid=pid, turn=turn):
                with self.assertRaises(ValueError):
                    policy_unlock.validate(catalogue(), pid, turn)
        with self.assertRaises(ValueError):
            policy_unlock.validate(catalogue(player_id=1), 0, 12)

    def test_currency_and_reason_relationships_are_closed(self):
        for bad in ('GOLD', None, 1):
            with self.subTest(currency=bad), self.assertRaises(ValueError):
                policy_unlock.validate(catalogue(currency=bad), 0, 12)
        cases = [catalogue(reason='available', cost=0),
                 catalogue(reason='no_cost', cost=1, can_unlock=False),
                 catalogue(reason='insufficient_funds', cost=0, can_unlock=False),
                 catalogue(reason='native_unavailable', can_unlock=True),
                 catalogue(reason='available', can_unlock=1),
                 catalogue(reason='unknown', can_unlock=False)]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy_unlock.validate(value, 0, 12)

    def test_foreign_duplicate_or_hidden_balance_fields_are_rejected(self):
        for key, value in (('balance', 200), ('hidden_precision', 3), ('player_id', 0)):
            bad = deepcopy(catalogue())
            bad['invented' if key == 'player_id' else key] = value
            if key == 'player_id':
                bad['player_id_copy'] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                policy_unlock.validate(bad, 0, 12)
        with self.assertRaises(ValueError):
            policy_unlock.validate(None, 0, 12)

    def test_action_validation_rejects_extra_fields_and_invalid_values(self):
        valid = dict(kind='policy_unlock', cost=20, currency='YIELD_FAITH')
        self.assertIs(policy_unlock.validate_action(valid), valid)
        bad_actions = [dict(valid, balance=100), dict(valid, kind='unlock'),
                       dict(valid, cost=True), dict(valid, cost=0),
                       dict(valid, currency='YIELD_GOLD_AND_FAITH')]
        for action in bad_actions:
            with self.subTest(action=action), self.assertRaises(ValueError):
                policy_unlock.validate_action(action)


if __name__ == '__main__':
    unittest.main()

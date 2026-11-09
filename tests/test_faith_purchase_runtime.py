"""Faith purchase adapter routing fixtures, not native-effect witnesses."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class FaithPurchaseAdapterTests(unittest.TestCase):
    def setUp(self):
        from civ6_host.runtime import xp2_plot_purchases
        self.adapter = xp2_plot_purchases
        self.saved = SimpleNamespace(prefix=object())
        self.observation = dict(player_id=0, turn=56, cities=[dict(id=65536)])
        base = dict(kind='purchase', city_id=65536, category='unit', index=20,
                    hash=1872107673, item_type='UNIT_SCOUT', price_token='60')
        self.gold = dict(base, currency='YIELD_GOLD')
        self.faith = dict(base, currency='YIELD_FAITH')
        self.catalogue = dict(player_id=0, turn=56, city_id=65536, offers=[
            dict(action=self.gold, command_legal=True, can_afford=True),
            dict(action=self.faith, command_legal=True, can_afford=False)])

    def read(self, **kwargs):
        with patch.object(self.adapter, '_bind'):
            with patch.object(self.adapter.plots, 'catalog', return_value=dict(offers=[])):
                with patch.object(self.adapter.purchases, 'catalog', return_value=deepcopy(self.catalogue)):
                    return self.adapter.catalogue(self.saved, self.observation, **kwargs)

    def test_legacy_default_keeps_gold_and_explicit_opt_in_preserves_every_native_quote(self):
        _, legacy = self.read()
        self.assertEqual(legacy[0]['offers'], self.catalogue['offers'][:1])
        _, current = self.read(allow_faith=True)
        self.assertEqual(current[0], self.catalogue)
        # Unaffordable quotes are preserved as public catalogue data; only
        # the native legality/affordability flags select command candidates.
        self.assertFalse(current[0]['offers'][1]['can_afford'])

    def test_faith_dispatch_keeps_the_exact_action_and_shared_native_provider(self):
        result = dict(only_a_dispatch_fixture=True)
        with patch.object(self.adapter, '_bind'):
            with patch.object(self.adapter.purchases, 'apply', return_value=result) as apply:
                self.assertIs(self.adapter.apply(self.saved, self.faith, self.observation,
                                                allow_faith=True), result)
                apply.assert_called_once_with(self.saved, self.saved.prefix, self.faith, 56,
                                              self.observation, player_id=0)

    def test_legacy_faith_dispatch_is_refused_before_the_native_provider(self):
        with patch.object(self.adapter, '_bind'):
            with patch.object(self.adapter.purchases, 'apply') as apply:
                with self.assertRaises(ValueError):
                    self.adapter.apply(self.saved, self.faith, self.observation)
                apply.assert_not_called()

    def test_faith_request_reuses_the_existing_requote_and_native_command_source(self):
        from civ6_host.runtime.native.native_saved_purchases import request_source
        code = request_source(self.faith, 0, 56)
        self.assertIn(b"local kind,currency='unit','YIELD_FAITH'", code)
        self.assertIn(b"local q=quote(kind,row,currency)", code)
        self.assertIn(b"q.price=='60'", code)
        self.assertIn(b"CityManager.RequestCommand(city,cc.PURCHASE,q.params)", code)


if __name__ == '__main__':
    unittest.main()

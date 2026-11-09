import inspect
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_trade


class XP2TradeAdapterTests(unittest.TestCase):
    def test_public_adapter_signatures_match_saved_continuation(self):
        self.assertEqual(tuple(inspect.signature(xp2_trade.catalogue).parameters),
                         ('saved', 'observation', 'include_origins'))
        selection = inspect.signature(xp2_trade.catalogue).parameters['include_origins']
        self.assertIs(selection.default, True)
        self.assertEqual(selection.kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(tuple(inspect.signature(xp2_trade.apply).parameters),
                         ('saved', 'action', 'before'))

    def test_unknown_execution_image_is_refused_before_resource_access(self):
        with patch('civ6_host.runtime.paths.resource_root',
                   side_effect=AssertionError('must reject before resolving resources')):
            with self.assertRaisesRegex(ValueError, 'current execution image'):
                xp2_trade.source_dependencies(execution_image=object())

    def test_current_accessors_pin_is_a_fixed_full_sha256(self):
        path, digest = xp2_trade._ACCESSORS
        self.assertEqual(path, 'work/trade-common-client/xp2-current-trade-accessors.json')
        self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_routes_survive_unavailable_origin_reader_without_empty_substitution(self):
        from civ6_host.runtime.execution_images import select, known_path
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        profile = 'xp2-gamecore-current-092abfbb'
        image = select(profile, core_path=known_path(profile))
        observation = dict(player_id=0, turn=61)
        routes = dict(native_route_witness=[{'unit_id': 19}])
        origins = dict(native_origin_witness=[{'unit_id': 23}])
        c = NS(observation=deepcopy(observation), sequence=5,
               transport=NS(require_empty_native_queue=lambda: None))
        b = NS(load_abi=NS(core_sha256=XP2_CORE_SHA256),
               core=NS(_civ6_host_execution_image=image), control=lambda **kw: None)
        p, identity, saved = object(), object(), object()
        with patch.object(xp2_trade, '_owner', return_value=(b,c,p,identity)), \
                patch.object(xp2_trade, 'source_dependencies'), \
                patch('civ6_host.runtime.native.native_saved_trade.catalog', return_value=routes) as route_read, \
                patch('civ6_host.runtime.native.native_saved_trade_origin.catalog', return_value=origins) as origin_read, \
                patch('civ6_host.runtime.native.native_saved_trade.compare_own') as route_check, \
                patch('civ6_host.runtime.native.native_saved_trade_origin.compare_own') as origin_check:
            result = xp2_trade.catalogue(saved, observation, include_origins=False)
            self.assertEqual(result['trade_routes'], routes)
            self.assertIsNone(result['trade_origins'])
            self.assertIsNone(c._xp2_trade_catalogue.origins)
            route_read.assert_called_once_with(p, 61, player_id=0)
            route_check.assert_called_once_with(routes, observation)
            origin_read.assert_not_called(); origin_check.assert_not_called()
            # A subsequent allowed query reads the origin afresh; it does not
            # keep the unavailable value or fabricate a zero-length catalogue.
            result = xp2_trade.catalogue(saved, observation)
            self.assertEqual(result['trade_origins'], origins)
            origin_read.assert_called_once_with(p, 61, player_id=0)
            origin_check.assert_called_once_with(origins, observation)

    def test_origin_reader_selection_is_exact_boolean(self):
        with self.assertRaisesRegex(ValueError, 'Boolean'):
            xp2_trade.catalogue(None, None, include_origins=0)


if __name__ == '__main__':
    unittest.main()

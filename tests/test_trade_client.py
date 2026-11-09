"""Trade decision and information boundaries without importing GameCore."""
import copy
import unittest

from civ6_host import HotseatClient, InformationUnavailable, SessionClient
from civ6_host.client import _digest
from civ6_host.contracts import information, trade
from test_client import Backend as HotseatBackend
from test_session_client import Backend as LanBackend


def add_trade(reply):
    obs, decisions = reply['observation'], reply['decisions']
    pid, turn = obs['player_id'], obs['turn']
    obs.update(width=3, height=2, units=[dict(id=9, owner=pid, x=0, y=0)],
               cities=[dict(id=11, owner=pid, x=0, y=0), dict(id=12, owner=pid, x=2, y=0)])
    boundary = dict(player_id=pid, turn=turn, width=3, height=2)
    quote = dict(values=[1, 2], majority_religion=-1, religion_pressure=0.0, path_bonus=False, tooltip='')
    destination = dict(owner=pid, city_id=12, x=2, y=0, name='Port', path=[0, 1, 2],
                       portal_entrances=[], portal_exits=[], repeat_route=False,
                       can_confirm=True, has_post=False, origin_yields=quote,
                       destination_yields=copy.deepcopy(quote))
    routes = dict(**boundary, active_routes=[], traders=[dict(unit_id=9, x=0, y=0,
                  origin_owner=pid, origin_city=11, destinations=[destination])])
    target = dict(city_id=12, x=2, y=0, plot_id=2, name='Port')
    origins = dict(**boundary, units=[dict(unit_id=9, origin_city=11, x=0, y=0,
                   available=True, targets=[target], map_targets=[2])])
    decisions.update(trade_routes=routes, trade_origins=origins)
    if not any(reply['outcome'][key] for key in ('terminated', 'truncated')):
        for action in trade.route_actions(routes) + trade.origin_actions(origins):
            decisions['candidates'].append(dict(candidate_id=_digest(action), action=action))
    decisions['decision_id'] = _digest({k:v for k,v in decisions.items() if k != 'decision_id'})
    return reply


class TradeHotseatBackend(HotseatBackend):
    def reply(self, operation, applied=None):
        return add_trade(super().reply(operation, applied))


class TradeLanBackend(LanBackend):
    def _reply(self, operation, sequence, **kwargs):
        return add_trade(super()._reply(operation, sequence, **kwargs))


class TradeClientTests(unittest.TestCase):
    def test_lan_read_preserves_native_path_quotes_and_choice_boundary(self):
        backend = TradeLanBackend()
        client = SessionClient(backend, allow_administrative=True)
        view = client.reset()
        result = client.information('trade')
        self.assertEqual((result['turn'], result['sequence']), (view['observation']['turn'], 0))
        self.assertEqual(result['native_decision_id'], view['decisions']['decision_id'])
        self.assertEqual(result['data']['routes'], view['decisions']['trade_routes'])
        self.assertEqual(result['data']['origins'], view['decisions']['trade_origins'])
        result['data']['origins']['units'].clear()
        self.assertEqual(len(client.information('trade')['data']['origins']['units']), 1)
        self.assertEqual(backend.calls, [])
        with self.assertRaises(InformationUnavailable):
            client.information('trade', channel='administrative')

    def test_hotseat_refuses_candidate_not_in_native_trade_catalogue(self):
        backend = TradeHotseatBackend()
        original_reset = backend.reset

        def substituted():
            reply = original_reset()
            decisions = reply['decisions']
            decisions['candidates'][-1]['action']['destination_city'] = 13
            decisions['decision_id'] = _digest({k:v for k,v in decisions.items() if k != 'decision_id'})
            return reply

        backend.reset = substituted
        with self.assertRaisesRegex(ValueError, 'Trade choices differ'):
            HotseatClient(backend).reset()
        self.assertEqual(len(backend.aborts), 1)

    def test_hotseat_refuses_trade_commands_without_their_catalogues(self):
        backend = TradeHotseatBackend()
        original_reset = backend.reset

        def without_trade_catalogues():
            reply = original_reset()
            decisions = reply['decisions']
            del decisions['trade_routes'], decisions['trade_origins']
            decisions['decision_id'] = _digest({k:v for k,v in decisions.items() if k != 'decision_id'})
            return reply

        backend.reset = without_trade_catalogues
        with self.assertRaisesRegex(ValueError, 'lacks its native catalogue'):
            HotseatClient(backend).reset()

    def test_terminal_hotseat_view_can_retain_trade_information_without_candidates(self):
        backend = TradeHotseatBackend()
        client = HotseatClient(backend)
        view = client.reset()
        trade_info = client.information('trade', player_id=0)
        self.assertEqual(trade_info['native_decision_id'], view['decisions']['decision_id'])
        self.assertEqual(trade_info['data']['routes'], view['decisions']['trade_routes'])
        self.assertEqual(backend.calls, [])
        with self.assertRaises(InformationUnavailable):
            client.information('trade', player_id=1)
        closed = client.close()
        self.assertEqual(closed['decisions']['candidates'], [])
        self.assertEqual(len(closed['decisions']['trade_origins']['units']), 1)
        with self.assertRaises(InformationUnavailable):
            client.information('trade')

    def test_foreign_trade_origin_and_injected_quotes_are_refused(self):
        reply = TradeHotseatBackend().reset()
        obs, decisions = reply['observation'], reply['decisions']
        foreign = copy.deepcopy(decisions)
        foreign['trade_origins']['units'][0]['targets'][0]['city_id'] = 999
        with self.assertRaisesRegex(ValueError, 'observed own city'):
            information.project('trade', obs, foreign)
        decisions['trade_routes']['traders'][0]['destinations'][0]['origin_yields']['values'] = [10**1000]
        with self.assertRaisesRegex(ValueError, 'Invalid trade number'):
            information.project('trade', obs, decisions)

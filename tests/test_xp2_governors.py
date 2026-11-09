"""Composed governor transport checks using non-native XP2 owner fixtures.

These fixtures exercise ordering and readback policy only. They do not qualify
the selected GameCore ABI or the official governor UI callbacks.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.contracts import governors as contract
from civ6_host.runtime import xp2_governors as adapter
from civ6_host.runtime import xp2_governors_source as governor_source
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import known_path, select


def _status(city=None):
    return dict(neutralized_turns=0, established=False, turns_to_establish=4,
        turns_on_site=0, assigned_city=city, govern_city_state=False,
        can_assign_to_major_civ=False)


def _catalogue(kind, *, phase='before', points=0):
    value = dict(player_id=0, current_game_turn=17, points_obtained=points,
        points_spent=0, can_appoint=False, titles_considered=True, governors=[])
    if kind == 'consider_governor_titles':
        value.update(titles_considered=(phase == 'after'))
    elif kind == 'appoint_governor':
        row = dict(index=4, hash=40, appointed=(phase == 'after'),
            can_ever_appoint=True, can_promote=False, assignment_open=False,
            turns_to_establish=4, status=None, promotions=[], assignment_targets=[])
        if phase == 'after':
            row['status'] = _status()
        value.update(can_appoint=True, governors=[row])
    elif kind == 'promote_governor':
        row = dict(index=4, hash=40, appointed=True, can_ever_appoint=False,
            can_promote=False, assignment_open=False, turns_to_establish=4,
            status=_status(), promotions=[dict(index=2, hash=20,
                owned=(phase == 'after'), can_earn=True, hidden=True,
                base_ability=False, level=1)], assignment_targets=[])
        value['governors'] = [row]
    elif kind == 'assign_governor':
        city = dict(owner=0, city_id=12) if phase == 'after' else dict(owner=0, city_id=11)
        row = dict(index=4, hash=40, appointed=True, can_ever_appoint=False,
            can_promote=False, assignment_open=True, turns_to_establish=4,
            status=_status(city), promotions=[], assignment_targets=[
                dict(owner=0, city_id=12, can_assign=True)])
        value['governors'] = [row]
    return value


def _wire(value):
    rows = ["H|{player_id}|{current_game_turn}|{points_obtained}|{points_spent}|{can_appoint}|{titles_considered}".format(
        **{**value, 'can_appoint': int(value['can_appoint']),
           'titles_considered': int(value['titles_considered'])})]
    for row in value['governors']:
        rows.append('G|{index}|{hash}|{appointed}|{can_ever_appoint}|{can_promote}|{assignment_open}|{turns_to_establish}'.format(
            **{**row, 'appointed': int(row['appointed']),
               'can_ever_appoint': int(row['can_ever_appoint']),
               'can_promote': int(row['can_promote']),
               'assignment_open': int(row['assignment_open'])}))
        status = row['status']
        if status is not None:
            city = status['assigned_city']
            owner, city_id = ('~', '~') if city is None else (city['owner'], city['city_id'])
            rows.append('S|{index}|{neutralized_turns}|{established}|{turns_to_establish}|{turns_on_site}|{owner}|{city_id}|{govern_city_state}|{can_assign_to_major_civ}'.format(
                index=row['index'], neutralized_turns=status['neutralized_turns'],
                established=int(status['established']), turns_to_establish=status['turns_to_establish'],
                turns_on_site=status['turns_on_site'], owner=owner, city_id=city_id,
                govern_city_state=int(status['govern_city_state']),
                can_assign_to_major_civ=int(status['can_assign_to_major_civ'])))
        for promotion in row['promotions']:
            rows.append('P|{index}|{pindex}|{phash}|{owned}|{can_earn}|{hidden}|{base_ability}|{level}'.format(
                index=row['index'], pindex=promotion['index'], phash=promotion['hash'],
                owned=int(promotion['owned']), can_earn=int(promotion['can_earn']),
                hidden=int(promotion['hidden']), base_ability=int(promotion['base_ability']),
                level=promotion['level']))
        for target in row['assignment_targets']:
            rows.append('T|{index}|{owner}|{city_id}|{can_assign}'.format(
                index=row['index'], owner=target['owner'], city_id=target['city_id'],
                can_assign=int(target['can_assign'])))
    rows.append('E|{count}|{line_count}'.format(count=len(value['governors']),
        line_count=len(rows)))
    return '\n'.join(rows).encode('ascii')


class FakeGovernorSession:
    def __init__(self, initial, catalogues, *, consideration=b'considered'):
        self.calls = []
        self.catalogues = list(catalogues)
        self.consideration = consideration
        pending = []
        deferred = []

        def evaluate(_child, _source, label, **_kwargs):
            if label == b'@xp2_governor_catalogue':
                if self.calls and self.calls[-3:] == ['deliver', 'drain', 'publish']:
                    self.calls.append('post_delivery_catalogue')
                return self.catalogues.pop(0)
            if label == b'@xp2_governor_title_consideration':
                return self.consideration
            raise AssertionError('unexpected fixture UI callback label: %r' % (label,))

        def deliver():
            self.calls.append('deliver')
            pending.pop(0)

        def drain():
            self.calls.append('drain')
            deferred.clear()

        def publish():
            self.calls.append('publish')

        self.prefix = SimpleNamespace(
            actions=SimpleNamespace(pending=pending, deliver_one=deliver),
            deferred_events=SimpleNamespace(pending=deferred, drain=drain),
            view_publisher=SimpleNamespace(publish=publish), ui_child=object(),
            runtime=SimpleNamespace(evaluate_text=evaluate))
        self.backend = SimpleNamespace(core=object(), context=object())
        self.continuation = SimpleNamespace(explicit_governors=deepcopy(initial), trade_feedback=None)
        self.emit = lambda *args, **kwargs: self.calls.append(('emit', args, kwargs))
        self.observation = dict(player_id=0, turn=17)


class Xp2GovernorCompositionTests(unittest.TestCase):
    def test_source_dependencies_translate_only_selected_current_image(self):
        profile = select('xp2-gamecore-current-092abfbb',
            core_path=known_path('xp2-gamecore-current-092abfbb'))
        pins = governor_source.source_dependencies(execution_image=profile)
        image_path = str(Path(profile.path).resolve())
        self.assertEqual(pins[image_path], profile.image_sha256)
        self.assertNotEqual(pins[image_path], profile.reference_core_sha256)
        self.assertEqual(adapter.source_dependencies(execution_image=profile), pins)

        # The legacy default remains pinned to the old installed-image hash.
        with self.assertRaisesRegex(ValueError, 'Governor source dependency changed'):
            governor_source.source_dependencies()

    def _apply(self, kind, *, fresh=None, after=None, request_result=None,
               archive=(3294486831).to_bytes(4, 'little') + b'fixture', unknown=False):
        offered = _catalogue(kind)
        fresh = deepcopy(fresh if fresh is not None else offered)
        after = deepcopy(after if after is not None else _catalogue(kind, phase='after'))
        session = FakeGovernorSession(offered, [_wire(fresh), _wire(after)])
        binder = __import__('civ6_host.runtime.xp2_governors_source', fromlist=['unused'])
        bind_calls = []

        def bind(owner, *, active):
            self.assertIs(owner, session)
            self.assertIs(active, True)
            bind_calls.append(active)

        def request(core, context, player_id, operation, parameters, *, core_sha256):
            self.assertIs(core, session.backend.core)
            self.assertIs(context, session.backend.context)
            self.assertEqual(player_id, 0)
            self.assertEqual(core_sha256, XP2_CORE_SHA256)
            self.assertIs(type(operation), int)
            self.assertIs(type(parameters), dict)
            session.calls.append('request')
            if unknown:
                session.prefix.actions.pending.append((1).to_bytes(4, 'little') + b'unknown')
            elif request_result is None or request_result.get('request_invoked'):
                session.prefix.actions.pending.append(archive)
            return request_result or dict(can_start=True, request_invoked=True)

        def observe(_runtime, _child, player_id):
            return dict(player_id=player_id, turn=17)

        patches = (
            patch.object(binder, 'bind_owner', side_effect=bind),
            patch.object(binder, 'support_source', return_value=b'-- fixture support --'),
            patch('civ6_host.runtime.native.native_player_operation_request.request_player_operation',
                  side_effect=request),
            patch('civ6_host.runtime.native.native_player_observation.observe_player',
                  side_effect=observe),
        )
        return session, bind_calls, patches

    def test_appointment_composes_real_catalogue_and_requeries_only_after_delivery(self):
        kind = 'appoint_governor'
        offered = _catalogue(kind)
        changed_points = _catalogue(kind, points=9)
        after = _catalogue(kind, phase='after', points=9)
        session, bind_calls, patches = self._apply(kind, fresh=changed_points, after=after)
        with patches[0], patches[1], patches[2], patches[3]:
            result = adapter.apply(session, contract.actions(offered)[0], dict(player_id=0, turn=17))
        self.assertEqual(result['effect']['kind'], kind)
        self.assertTrue(result['effect']['native_effect_observed'])
        self.assertEqual(result['effect']['points_obtained_before'], 9)
        emitted = [call for call in session.calls if isinstance(call, tuple) and call[0] == 'emit']
        self.assertTrue(emitted[-1][2]['catalogue_changed_since_offer'])
        self.assertTrue(any(call == 'post_delivery_catalogue' for call in session.calls))
        self.assertLess(session.calls.index('deliver'), session.calls.index('post_delivery_catalogue'))
        self.assertEqual(session.calls[:4], ['request', 'deliver', 'drain', 'publish'])
        self.assertTrue(bind_calls and all(value is True for value in bind_calls))

    def test_promotion_and_assignment_effects_use_selected_rows_not_cost_formulas(self):
        for kind in ('promote_governor', 'assign_governor'):
            with self.subTest(kind=kind):
                offered = _catalogue(kind)
                session, _, patches = self._apply(kind)
                with patches[0], patches[1], patches[2], patches[3]:
                    result = adapter.apply(session, contract.actions(offered)[0],
                                           dict(player_id=0, turn=17))
                self.assertTrue(result['effect']['native_effect_observed'])

    def test_consider_titles_uses_setter_and_transport_without_operation_archive(self):
        kind = 'consider_governor_titles'
        offered = _catalogue(kind)
        session, _, patches = self._apply(kind)
        with patches[0], patches[1], patches[2] as request, patches[3]:
            result = adapter.apply(session, contract.actions(offered)[0],
                                   dict(player_id=0, turn=17))
        request.assert_not_called()
        self.assertFalse(session.prefix.actions.pending)
        self.assertEqual(session.calls[:2], ['drain', 'publish'])
        self.assertTrue(result['effect']['native_effect_observed'])

    def test_stale_choice_native_refusal_and_unknown_pending_do_not_deliver(self):
        kind = 'appoint_governor'
        offered = _catalogue(kind)
        stale = deepcopy(offered)
        stale['governors'][0]['can_ever_appoint'] = False
        session, _, patches = self._apply(kind, fresh=stale)
        with patches[0], patches[1], patches[2] as request, patches[3]:
            with self.assertRaisesRegex(RuntimeError, 'no longer offered'):
                adapter.apply(session, contract.actions(offered)[0], dict(player_id=0, turn=17))
        request.assert_not_called()
        self.assertNotIn('deliver', session.calls)

        session, _, patches = self._apply(kind,
            request_result=dict(can_start=False, request_invoked=False))
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaisesRegex(RuntimeError, 'refused'):
                adapter.apply(session, contract.actions(offered)[0], dict(player_id=0, turn=17))
        self.assertNotIn('deliver', session.calls)
        self.assertNotIn('publish', session.calls)

        session, _, patches = self._apply(kind, unknown=True)
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaisesRegex(RuntimeError, 'single native operation archive'):
                adapter.apply(session, contract.actions(offered)[0], dict(player_id=0, turn=17))
        self.assertNotIn('deliver', session.calls)
        self.assertNotIn('publish', session.calls)

    def test_false_readback_is_rejected_after_the_real_fake_fifo_cycle(self):
        kind = 'appoint_governor'
        offered = _catalogue(kind)
        session, _, patches = self._apply(kind, after=offered)
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaisesRegex(RuntimeError, 'appointment was not observed'):
                adapter.apply(session, contract.actions(offered)[0], dict(player_id=0, turn=17))
        self.assertEqual(session.calls[:4], ['request', 'deliver', 'drain', 'publish'])
        self.assertTrue(any(call == 'post_delivery_catalogue' for call in session.calls))


if __name__ == '__main__':
    unittest.main()

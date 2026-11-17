"""Latest-boundary file delivery, identity, integrity and bounded retention."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from test_player_view import Backend, make_player_view
from civ6_host.client import InformationUnavailable, ProtocolError
from civ6_host.session_client import SessionClient
from civ6_host.runtime.player_views import (
    SessionViewsMixin, STAGE, publish_player_views, validate_lan_views, validate_players,
)


class Session(SessionViewsMixin):
    def _owner(self):
        pass


class ViewTransportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.session = Session(public_view_players=[1])
        self.session.run = Path(self.directory.name)
        self.reply = Backend().reset()
        self.session.nonce = self.reply['nonce']
        self.session.last = copy.deepcopy(self.reply)
        self.session.finished = False
        self.session.protocol = SimpleNamespace(sequence=0)
        self.session.protocol_class = SimpleNamespace(max_commands=1024)
        self.value = make_player_view(self.reply, 1)
        self.path = self.session.run / 'public-player-views/player-1.json'
        self.path.parent.mkdir()
        self.install()

    def install(self):
        raw = json.dumps(self.value, sort_keys=True).encode()
        self.path.write_bytes(raw)
        self.manifest = dict(stage=STAGE, nonce=self.reply['nonce'],
            episode_id=self.reply['episode_id'], game_generation=self.reply['game_generation'],
            sequence=self.reply['sequence'], turn=self.reply['observation']['turn'],
            files=[dict(player_id=1, file='public-player-views/player-1.json', bytes=len(raw),
                        sha256=hashlib.sha256(raw).hexdigest())])
        self.session._accept_view_manifest(self.manifest)

    def test_returned_view_detached_and_actor_boundary_unchanged(self):
        result = self.session.read_player_view(self.reply, 1)
        self.assertEqual(result, self.value)
        result['observation']['plots'].clear()
        self.assertEqual(self.session.read_player_view(self.reply, 1), self.value)
        self.assertEqual(self.session.last, self.reply)

    def test_diplomatic_wars_are_boolean_sorted_and_local(self):
        from civ6_host.player_view import WAR_STATUS_SCHEMA

        def publish(rows):
            self.reply['sequence'] += 1
            self.session.last = copy.deepcopy(self.reply)
            self.session.protocol.sequence = self.reply['sequence']
            self.value = dict(make_player_view(self.reply, 1), schema=WAR_STATUS_SCHEMA, diplomatic_wars=rows)
            self.install()

        publish([dict(player_id=0, at_war=True)])
        result = self.session.read_player_view(self.reply, 1)
        self.assertEqual(result['diplomatic_wars'], [dict(player_id=0, at_war=True)])
        result['diplomatic_wars'].clear()
        self.assertEqual(self.session.read_player_view(self.reply, 1), self.value)
        for rows in ([dict(player_id=1, at_war=True)], [dict(player_id=0, at_war=1)],
                     [dict(player_id=0, at_war=True)] * 2,
                     [dict(player_id=2, at_war=False, grievance=100)]):
            with self.subTest(rows=rows):
                publish(rows)
                with self.assertRaisesRegex(ValueError, 'diplomatic war'):
                    self.session.read_player_view(self.reply, 1)

    def test_rejects_unconfigured_player_and_stale_boundary(self):
        with self.assertRaisesRegex(ValueError, 'authorized'):
            self.session.read_player_view(self.reply, 0)
        stale = copy.deepcopy(self.reply)
        stale['sequence'] += 1
        with self.assertRaisesRegex(ValueError, 'latest live'):
            self.session.read_player_view(stale, 1)

    def test_rejects_file_replaced_after_manifest(self):
        self.path.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'size or hash'):
            self.session.read_player_view(self.reply, 1)

    def test_rejects_redirected_and_duplicate_manifest(self):
        bad = copy.deepcopy(self.manifest)
        bad['sequence'] = 1
        bad['files'][0]['file'] = '../private.json'
        with self.assertRaisesRegex(ValueError, 'path differs'):
            self.session._accept_view_manifest(bad)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.session._accept_view_manifest(self.manifest)

    def test_new_boundary_replaces_single_file_and_invalidates_previous(self):
        previous = copy.deepcopy(self.reply)
        self.reply['sequence'] = 1
        self.session.last = copy.deepcopy(self.reply)
        self.session.protocol.sequence = 1
        self.value = make_player_view(self.reply, 1)
        self.install()
        self.assertEqual(self.session.read_player_view(self.reply, 1)['sequence'], 1)
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)
        with self.assertRaises(ValueError):
            self.session.read_player_view(previous, 1)

    def test_closed_boundary_and_invalid_optin_refused(self):
        self.session.finished = True
        with self.assertRaisesRegex(ValueError, 'live'):
            self.session.read_player_view(self.reply, 1)
        self.assertEqual(validate_players(None), ())
        for invalid in ([], [True], [0, 0], [64], '1'):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                validate_players(invalid)


class LanViewTransportTests(unittest.TestCase):
    def setup_session(self):
        from civ6_host.runtime.backend import NetworkBackend
        from civ6_host.runtime.execution_images import _PROFILE, identity
        from civ6_host.runtime.native.network_session import NativeNetworkSession
        from test_session_client import Backend as LanReplyFixture
        from test_xp2_human_perspective import PerspectiveFixture

        fixture = PerspectiveFixture()
        self.addCleanup(fixture.close)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        native = NativeNetworkSession.__new__(NativeNetworkSession)
        native.owner_thread = threading.get_ident()
        native.public_view_players = (0, 1)
        native.input_profile = 'xp2-lan'
        native.run = Path(directory.name)
        native.finished = False
        wire_fixture = LanReplyFixture()
        wire_fixture.reset()
        wire_fixture.turn = fixture.token.observation['turn']
        reply = wire_fixture._reply('reset', 0, pid=0)
        reply['observation'] = copy.deepcopy(fixture.token.observation)
        native.last = copy.deepcopy(reply)
        native.nonce = reply['nonce']
        native.protocol = SimpleNamespace(sequence=0, ended=False, closed=False,
            nonce=reply['nonce'], session=copy.deepcopy(reply['session']),
            identity=SimpleNamespace(episode_id=reply['episode_id'],
                                     game_generation=reply['game_generation']))
        native.reset = Mock(return_value=copy.deepcopy(reply))
        native.request = Mock(side_effect=AssertionError('View lookup must not issue a command'))
        closure = dict(input_profile='xp2-lan', execution_image=identity(_PROFILE), pins={})
        native._configure_public_views(closure)
        closure_path = native.run / 'closure.json'
        closure_path.write_text(json.dumps(closure), encoding='utf-8')
        players = validate_lan_views(closure)

        def publish():
            def emit(stage, **fields):
                native._accept_view_manifest(dict(stage=stage, **fields))
            publish_player_views(emit, fixture.saved, native.protocol, reply['observation'],
                                 closure, closure_path, lan_players=players)

        backend = NetworkBackend.__new__(NetworkBackend)
        backend._session = native
        backend._information_store = None
        backend._display_projection_enabled = False
        client = SessionClient(backend)
        client.reset()
        return fixture, native, client, publish, closure

    def test_owned_secondary_view_round_trips_through_lan_client_without_an_order(self):
        fixture, native, client, publish, _ = self.setup_session()
        publish()
        view = client.player_view(1)
        self.assertEqual(view['player_id'], 1)
        self.assertEqual(view['observation']['units'][0]['id'], 28)
        self.assertEqual([p['index'] for p in view['player_map']['plots']], [3])
        self.assertNotIn('decisions', view)
        view['observation']['units'].clear()
        self.assertEqual(client.player_view(1)['observation']['units'][0]['id'], 28)
        self.assertEqual(client.view(0)['sequence'], 0)
        self.assertEqual(client.controllable_player_ids, (0,))
        with self.assertRaisesRegex(ProtocolError, 'cannot route'):
            client.observe(1)
        fixture.defeated_secondary = True
        native.protocol.sequence = 1
        native.last['sequence'] = 1
        publish()
        self.assertFalse((native.run / 'public-player-views/player-1.json').exists())
        with self.assertRaisesRegex(InformationUnavailable, 'living'):
            native.read_player_view(native.last, 1)
        self.assertEqual(native.read_player_view(native.last, 0)['player_id'], 0)
        native.request.assert_not_called()

    def test_lan_client_can_read_defenders_public_war_at_latest_boundary(self):
        from civ6_host.player_view import WAR_STATUS_SCHEMA
        from civ6_host.runtime import xp2_diplomatic_relationships

        fixture, native, client, publish, closure = self.setup_session()
        closure['diplomacy_overview_diagnostic'] = True
        fixture.saved.diplomacy_overview_diagnostic = True

        def read(prefix, player_id, turn):
            self.assertEqual((prefix, fixture.player, turn), (fixture.saved.prefix, player_id, 8))
            return [dict(player_id=1 - player_id, at_war=True)]

        with patch.object(xp2_diplomatic_relationships, 'read_wars', side_effect=read):
            publish()
        defender = client.player_view(1)
        self.assertEqual(defender['schema'], WAR_STATUS_SCHEMA)
        self.assertEqual(defender['diplomatic_wars'], [dict(player_id=0, at_war=True)])
        self.assertEqual((defender['turn'], defender['sequence']), (8, 0))
        self.assertEqual(client.view(0)['sequence'], 0)
        native.request.assert_not_called()

    def test_refuses_tampered_sources_and_unadmitted_lan_profiles(self):
        from civ6_host.runtime.native.network_session import NativeNetworkSession

        _, _, _, _, closure = self.setup_session()
        pin = next(iter(closure['public_view_sources']))
        closure['pins'][pin] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source closure'):
            validate_lan_views(closure)
        for profile in ('lan', 'xp1-lan', 'xp2-lan'):
            with self.subTest(profile=profile), self.assertRaisesRegex(
                    ValueError, 'installed Gathering Storm'):
                NativeNetworkSession(input_profile=profile, public_view_players=[0, 1])


if __name__ == '__main__':
    unittest.main()

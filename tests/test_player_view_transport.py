"""Latest-boundary file delivery, identity, integrity and bounded retention."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from test_player_view import Backend, make_player_view
from civ6_host.runtime.player_views import SessionViewsMixin, STAGE, validate_players


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


if __name__ == '__main__':
    unittest.main()

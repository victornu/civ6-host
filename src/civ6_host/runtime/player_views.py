"""Opt-in public perspectives on the existing native session transport.

Files hold only the latest accepted boundary, never a growing replay or a
privileged critic channel. Reading a view does not submit a game command.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

from civ6_host.player_view import SCHEMA, validate_player_view

STAGE = 'host_public_player_views'
MAX_VIEW_BYTES = 8 * 1024 * 1024
DIRECTORY = 'public-player-views'


def validate_players(value):
    if value is None:
        return ()
    if type(value) not in (list, tuple) or not 1 <= len(value) <= 64:
        raise ValueError('Public view players require an explicit nonempty list')
    if any(type(p) is not int or not 0 <= p < 64 for p in value) or len(set(value)) != len(value):
        raise ValueError('Public view players must be distinct native player IDs')
    return tuple(sorted(value))


def _relative(pid):
    return f'{DIRECTORY}/player-{pid}.json'


def _path(run, pid):
    run = Path(run).resolve(strict=True)
    path = run / _relative(pid)
    if path.is_symlink() or path.parent.is_symlink() or path.resolve() != path:
        raise ValueError('Public player view path is redirected')
    return path


def _read_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate public view key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite public view value: ' + value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def publish_player_views(emit, owner, protocol, observation, closure, closure_path):
    """Worker hook: preserve legacy reply/action semantics and original actor."""
    players = validate_players(closure.get('public_view_players'))
    if not players or protocol.ended or protocol.closed or observation is None:
        return
    from .human_perspective import collect_player_view, source_pins
    pins = source_pins()
    if closure.get('public_view_sources') != pins or any(closure['pins'].get(k) != v for k, v in pins.items()):
        raise ValueError('Public perspective source closure differs')
    from .native.native_official_hotseat import PLAYERS
    from .native.native_player_observation import observe_player
    current = observation['player_id']
    # Read the initial actor last so the existing reply can be compared at the
    # same retained boundary after all requested human perspective changes.
    ordered = [p for p in players if p != current] + ([current] if current in players else [])
    payloads = {}
    for pid in ordered:
        view = collect_player_view(owner, pid, player_ids=PLAYERS)
        value = dict(schema=SCHEMA, episode_id=protocol.identity.episode_id,
            game_generation=protocol.identity.game_generation, sequence=protocol.sequence,
            player_id=pid, turn=observation['turn'], **view)
        payloads[pid] = validate_player_view(value, episode_id=value['episode_id'],
            game_generation=value['game_generation'], sequence=protocol.sequence,
            player_id=pid, turn=observation['turn'])
    retained = (payloads[current]['observation'] if current in payloads else
                observe_player(owner.prefix.runtime, owner.prefix.ui_child, current))
    if retained != observation:
        raise ValueError('Public perspective collection changed the retained actor observation')
    run = Path(closure_path).resolve(strict=True).parent
    rows = []
    for pid in players:
        path = _path(run, pid)
        path.parent.mkdir(exist_ok=True)
        raw = json.dumps(payloads[pid], sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
        if len(raw) > MAX_VIEW_BYTES:
            raise ValueError('Public player view exceeds file bound')
        temporary = path.with_suffix('.pending')
        with temporary.open('xb') as stream:
            stream.write(raw)
        os.replace(temporary, path)
        rows.append(dict(player_id=pid, file=_relative(pid), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    emit(STAGE, nonce=protocol.nonce, episode_id=protocol.identity.episode_id,
        game_generation=protocol.identity.game_generation, sequence=protocol.sequence,
        turn=observation['turn'], files=rows)


class SessionViewsMixin:
    """Add views without creating a second native worker/session pipeline."""
    def __init__(self, *args, public_view_players=None, **kwargs):
        self.public_view_players = validate_players(public_view_players)
        self._view_manifest = None
        super().__init__(*args, **kwargs)

    def _configure_closure(self, closure):
        super()._configure_closure(closure)
        self._view_manifest = None
        if self.public_view_players:
            from .human_perspective import source_pins, verify_source
            verify_source()
            pins = source_pins()
            closure['public_view_players'] = list(self.public_view_players)
            closure['public_view_sources'] = pins
            closure['pins'].update(pins)

    def _read_stream(self, pipe, name, limit, events):
        if not events or not self.public_view_players:
            return super()._read_stream(pipe, name, limit, events)
        session = self
        class ManifestPipe:
            def readline(self, maximum):
                line = pipe.readline(maximum)
                if len(line) <= maximum:
                    try:
                        value = json.loads(line)
                    except (ValueError, UnicodeError):
                        value = None
                    if type(value) is dict and value.get('stage') == STAGE:
                        session._accept_view_manifest(value)
                return line
        return super()._read_stream(ManifestPipe(), name, limit, events)

    def _accept_view_manifest(self, value):
        from .native.native_episode_identity import DiagnosticEpisodeIdentity
        fields = {'stage', 'nonce', 'episode_id', 'game_generation', 'sequence', 'turn', 'files'}
        if type(value) is not dict or set(value) != fields or value['stage'] != STAGE or value['nonce'] != self.nonce:
            raise ValueError('Public view manifest identity differs')
        DiagnosticEpisodeIdentity(value['episode_id'], value['game_generation'])
        if type(value['sequence']) is not int or not 0 <= value['sequence'] <= self.protocol_class.max_commands:
            raise ValueError('Public view manifest sequence differs')
        if type(value['turn']) is not int or value['turn'] < 0:
            raise ValueError('Public view manifest turn differs')
        if self._view_manifest is not None and value['sequence'] <= self._view_manifest['sequence']:
            raise ValueError('Duplicate or reversed public view manifest')
        files = value['files']
        if type(files) is not list or len(files) != len(self.public_view_players):
            raise ValueError('Public view manifest roster differs')
        for row, pid in zip(files, self.public_view_players):
            if type(row) is not dict or set(row) != {'player_id', 'file', 'bytes', 'sha256'}:
                raise ValueError('Public view file manifest fields differ')
            if type(row['player_id']) is not int or row['player_id'] != pid or row['file'] != _relative(pid):
                raise ValueError('Public view file player or path differs')
            pin = row['sha256']
            if type(pin) is not str or len(pin) != 64 or any(c not in '0123456789abcdef' for c in pin):
                raise ValueError('Public view manifest hash differs')
            if type(row['bytes']) is not int or not 0 < row['bytes'] <= MAX_VIEW_BYTES:
                raise ValueError('Public view manifest size differs')
        self._view_manifest = copy.deepcopy(value)

    def read_player_view(self, response, player_id):
        self._owner()
        if type(player_id) is not int or player_id not in self.public_view_players:
            raise ValueError('Player not authorized by public_view_players')
        if self.finished or self.protocol is None or response != self.last or response['sequence'] != self.protocol.sequence:
            raise ValueError('Public view requires the latest live accepted response')
        if any(response['outcome'][k] for k in ('terminated', 'truncated')):
            raise ValueError('Public view requires a live episode')
        manifest = self._view_manifest
        if manifest is None or any(manifest[k] != response[k] for k in ('nonce','episode_id','game_generation','sequence')):
            raise ValueError('Public view manifest belongs to another boundary')
        turn = response['observation']['turn']
        if manifest['turn'] != turn:
            raise ValueError('Public view manifest turn differs from accepted response')
        row = next(r for r in manifest['files'] if r['player_id'] == player_id)
        with _path(self.run, player_id).open('rb') as stream:
            raw = stream.read(MAX_VIEW_BYTES + 1)
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Public view file size or hash differs')
        return validate_player_view(_read_json(raw), episode_id=response['episode_id'],
            game_generation=response['game_generation'], sequence=response['sequence'],
            player_id=player_id, turn=turn)

"""Bounded, response-bound store for already captured administrative evidence.

The store runs on the host side of the event pipe.  It never calls GameCore;
it only associates native readback events with the exact public response that
was produced from the same player, sequence, turn, and native episode.
"""
from __future__ import annotations

import copy
import json
import re
import threading
from uuid import UUID


_STAGE_GROUP = {
    'native_player_display_readback': 'display',
    'native_production_administrative_readback': 'production',
    'native_city_growth_administrative_readback': 'growth',
    'native_combat_administrative_readback': 'combat',
    'xp2_saved_end_turn_observed': 'turn_horizon',
}
_BASE_FIELDS = {
    'stage', 'episode_id', 'game_generation', 'player_id', 'sequence', 'turn',
    'source_sha256', 'actor_channel',
}
_EXTRA_FIELDS = {
    'display': {'locale','provider_id','provider_sha256','raw_observation_sha256',
                'response_binding_sha256','formatter_input_f64le','top_panel_text'},
    'production': {'production', 'production_info', 'public_production'},
    'growth': {'cities'},
    'combat': {'cities'},
    'turn_horizon': {'end_turn'},
}
_PIN = re.compile(r'^[0-9a-f]{64}$')
_MAX_PLAYER = 63
_MAX_TURN = 2**31 - 1


def _wire_size(value, limit):
    """Return compact UTF-8 JSON size, failing as soon as it exceeds limit."""
    # JSON byte size alone does not bound Python object overhead: a list with
    # millions of tiny scalar values can occupy far more memory than its wire
    # representation. Bound the retained JSON tree as well as its bytes.
    node_limit = max(32, min(250_000, limit // 8))
    stack = [iter((value,))]
    nodes = 0
    while stack:
        try:
            node = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        nodes += 1
        if nodes > node_limit:
            raise ValueError('Administrative evidence exceeds store structure bound')
        if type(node) is dict:
            if node:
                stack.append(iter(node.keys()))
                stack.append(iter(node.values()))
        elif type(node) is list:
            if node:
                stack.append(iter(node))
        elif type(node) not in (str, int, float, bool, type(None)):
            raise ValueError('Administrative evidence is not JSON data')
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False,
                               separators=(',', ':'), check_circular=True)
    size = 0
    try:
        for chunk in encoder.iterencode(value):
            size += len(chunk.encode('utf-8'))
            if size > limit:
                return size
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError('Administrative evidence is not bounded JSON data') from exc
    return size


def _identity(value, *, response=False):
    if type(value) is not dict:
        return None
    try:
        episode = value.get('episode_id')
        generation = value.get('game_generation')
        if type(episode) is not str or str(UUID(episode)) != episode:
            return None
        if generation != 'native-' + episode:
            return None
        if response:
            observation = value.get('observation')
            if type(observation) is not dict:
                return None
            pid = observation.get('player_id')
            turn = observation.get('turn')
        else:
            pid = value.get('player_id')
            turn = value.get('turn')
        sequence = value.get('sequence')
        if type(pid) is not int or not 0 <= pid <= _MAX_PLAYER:
            return None
        if type(sequence) is not int or sequence < 0:
            return None
        if type(turn) is not int or not 0 <= turn <= _MAX_TURN:
            return None
        return episode, generation, pid, sequence, turn
    except (ValueError, TypeError, AttributeError):
        return None


class InformationStore:
    """Keep only latest pending/sealed administrative readbacks per player.

    ``source_pins`` uses the public group names ``production``, ``growth`` and ``combat``.
    The limit covers every retained pending and sealed JSON snapshot together.
    Readers may run on a different thread from the event-pipe writer.
    """

    def __init__(self, source_pins: dict[str, str], max_bytes: int = 32 * 1024**2):
        if type(source_pins) is not dict:
            raise TypeError('source_pins must be a dictionary')
        pins = {}
        for group, pin in source_pins.items():
            if group not in _EXTRA_FIELDS or type(pin) is not str or not _PIN.fullmatch(pin):
                raise ValueError('Invalid administrative source pin')
            pins[group] = pin
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError('max_bytes must be a positive integer')
        self._pins = pins
        self._max_bytes = max_bytes
        self._lock = threading.RLock()
        self._episode = None
        self._pending = {}  # (group, pid) -> (identity, detached event, size)
        self._sealed = {}   # (group, pid) -> (identity, detached event, size)
        self._bytes = 0

    def clear(self):
        """Discard all pending and sealed evidence, including episode identity."""
        with self._lock:
            self._pending.clear()
            self._sealed.clear()
            self._bytes = 0
            self._episode = None

    def _set_episode(self, identity):
        episode = identity[:2]
        if self._episode is None:
            self._episode = episode
        elif self._episode != episode:
            self._pending.clear()
            self._sealed.clear()
            self._bytes = 0
            self._episode = episode

    def ingest(self, event):
        """Ingest a readback or response event; unrelated events are ignored.

        A display subscription ignores unselected groups. Malformed selected
        readbacks raise ``ValueError``. A response only seals evidence when the
        matching readback passes the strict semantic
        contract validator and agrees with the public response fields.
        """
        if type(event) is not dict:
            return
        stage = event.get('stage')
        group = _STAGE_GROUP.get(stage)
        if group is not None:
            # Display subscribes to a shared stream that also emits administrative events.
            if ('display' in self._pins or group == 'turn_horizon') and group not in self._pins:
                return
            self._ingest_readback(group, event)
        elif stage == 'official_session_response':
            self._ingest_response(event)

    def _ingest_readback(self, group, event):
        identity = _identity(event)
        expected_fields = _BASE_FIELDS | _EXTRA_FIELDS[group]
        if identity is None or set(event) != expected_fields or event.get('actor_channel') is not False:
            raise ValueError('Malformed administrative readback identity or fields')
        if group not in self._pins or event.get('source_sha256') != self._pins[group]:
            raise ValueError('Administrative readback source pin differs')
        size = _wire_size(event, self._max_bytes)
        if size > self._max_bytes:
            raise ValueError('Administrative readback exceeds store capacity')
        detached = copy.deepcopy(event)
        key = (group, identity[2])
        with self._lock:
            self._set_episode(identity)
            old = self._pending.get(key)
            prospective = self._bytes - (old[2] if old else 0) + size
            if prospective > self._max_bytes:
                raise ValueError('Administrative information store is full')
            self._pending[key] = (identity, detached, size)
            self._bytes = prospective

    def _ingest_response(self, response):
        # Responses carry player/turn in their observation. Sequence and native
        # episode identity live at the envelope. Reset/terminal responses with
        # no observation still change the episode and clear old evidence.
        episode = response.get('episode_id')
        generation = response.get('game_generation')
        try:
            valid_episode = type(episode) is str and str(UUID(episode)) == episode
        except (ValueError, TypeError, AttributeError):
            valid_episode = False
        if not valid_episode or generation != 'native-' + episode:
            return
        with self._lock:
            episode_identity = (episode, generation)
            if self._episode is not None and self._episode != episode_identity:
                self._pending.clear()
                self._sealed.clear()
                self._bytes = 0
            self._episode = episode_identity
        identity = _identity(response, response=True)
        if identity is None:
            outcome = response.get('outcome')
            if (response.get('operation') == 'close'
                    or (type(outcome) is dict and (outcome.get('terminated') is True
                                                   or outcome.get('truncated') is True))):
                with self._lock:
                    self._pending.clear()
                    self._sealed.clear()
                    self._bytes = 0
            return
        with self._lock:
            observation = response.get('observation')
            if type(observation) is not dict:
                return
            pid, turn = observation.get('player_id'), observation.get('turn')
            if type(pid) is not int or type(turn) is not int:
                return
            if pid != identity[2] or turn != identity[4]:
                return
            outcome = response.get('outcome')
            ended = (response.get('operation') == 'close'
                     or (type(outcome) is dict and (outcome.get('terminated') is True
                                                    or outcome.get('truncated') is True)))
            if ended:
                # Preserve at most the exact pending display for the final frame.
                final_display = ('display', pid)
                for key in list(self._pending):
                    if key != final_display:
                        self._discard_pending(key)
                for _, _, size in self._sealed.values():
                    self._bytes -= size
                self._sealed.clear()
            for group in _EXTRA_FIELDS:
                key = (group, pid)
                pending = self._pending.get(key)
                if ended and group != 'display':
                    self._discard_pending(key)
                    sealed = self._sealed.pop(key, None)
                    if sealed is not None:
                        self._bytes -= sealed[2]
                    continue
                if pending is None or pending[0] != identity:
                    # A new accepted boundary without a same-boundary event
                    # cannot reuse the previous turn's administrative view.
                    sealed = self._sealed.pop(key, None)
                    if sealed is not None:
                        self._bytes -= sealed[2]
                    continue
                try:
                    if group == 'display':
                        from .player_display_toppanel import validate_readback
                        validate_readback(pending[1], response, source_sha256=self._pins[group])
                    else:
                        from civ6_host.contracts.information import validate_administrative
                        validate_administrative(group, pending[1], response,
                                                 source_sha256=self._pins[group])
                except (ImportError, TypeError, ValueError, KeyError, OverflowError):
                    # A same-turn pre-action readback can be present in the
                    # event stream. Failed exact-boundary projection never
                    # becomes a final administrative snapshot.
                    self._discard_pending(key)
                    sealed = self._sealed.pop(key, None)
                    if sealed is not None:
                        self._bytes -= sealed[2]
                    continue
                old = self._sealed.get(key)
                self._sealed[key] = pending
                if old is not None:
                    self._bytes -= old[2]
                self._pending.pop(key, None)

    def _discard_pending(self, key):
        pending = self._pending.pop(key, None)
        if pending is not None:
            self._bytes -= pending[2]

    def read(self, group, response):
        """Return a detached snapshot only for its exact accepted response."""
        if group not in _EXTRA_FIELDS:
            raise ValueError('Unknown administrative information group')
        if type(response) is not dict or response.get('stage') != 'official_session_response':
            return None
        identity = _identity(response, response=True)
        observation = response.get('observation')
        if identity is None or type(observation) is not dict:
            return None
        if (observation.get('player_id') != identity[2]
                or observation.get('turn') != identity[4]):
            return None
        outcome = response.get('outcome')
        if group != 'display' and (response.get('operation') == 'close'
                or (type(outcome) is dict and (outcome.get('terminated') is True
                                               or outcome.get('truncated') is True))):
            return None
        with self._lock:
            if self._episode != identity[:2]:
                return None
            item = self._sealed.get((group, identity[2]))
            if item is None or item[0] != identity:
                return None
            try:
                if group == 'display':
                    from .player_display_toppanel import validate_readback
                    validate_readback(item[1], response, source_sha256=self._pins[group])
                else:
                    from civ6_host.contracts.information import validate_administrative
                    validate_administrative(group, item[1], response,
                                             source_sha256=self._pins[group])
            except (ImportError, TypeError, ValueError, KeyError, OverflowError):
                return None
            return copy.deepcopy(item[1])


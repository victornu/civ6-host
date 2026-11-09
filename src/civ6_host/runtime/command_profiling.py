"""Bounded opt-in Python profiling for one native command and response."""
from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from time import perf_counter
import math
import re
import sys


_PHASES = frozenset(('command', 'response'))
_OPERATIONS = frozenset(('act', 'poll'))
_MAX_ROWS = 80
_MAX_FILENAME = 256
_MAX_FUNCTION = 160
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')


def _identity_fields(identity):
    if type(identity) is dict:
        episode_id = identity.get('episode_id')
        game_generation = identity.get('game_generation')
    else:
        episode_id = getattr(identity, 'episode_id', None)
        game_generation = getattr(identity, 'game_generation', None)
    for name, value in (('episode_id', episode_id), ('game_generation', game_generation)):
        if (type(value) is not str or not value or len(value) > 128
                or any(ord(char) < 32 for char in value)):
            raise ValueError('Invalid command profiler identity field: ' + name)
    return episode_id, game_generation


def _bounded(value, limit):
    if len(value) <= limit:
        return value, False
    return value[:limit], True


class CommandProfiler:
    """Profile at most command+response for the first eligible act/poll.

    This profiler records Python call costs only. It does not inspect command
    arguments or game state and is disabled unless explicitly requested.
    """

    def __init__(self, enabled, emit, identity):
        if type(enabled) is not bool:
            raise TypeError('Command profiler enabled must be a bool')
        if not callable(emit):
            raise TypeError('Command profiler emit callback must be callable')
        self.enabled = enabled
        self.emit = emit
        self.episode_id, self.game_generation = _identity_fields(identity)
        self._lock = Lock()
        self._selected = None
        self._used_phases = set()

    @contextmanager
    def measure(self, phase, operation, sequence, player_id):
        if type(phase) is not str or phase not in _PHASES:
            raise ValueError('Unknown command profiling phase')
        if type(operation) is not str or not operation or len(operation) > 64:
            raise ValueError('Invalid command profiling operation')
        if type(sequence) is not int or sequence < 0:
            raise ValueError('Invalid command profiling sequence')
        if type(player_id) is not int or player_id < 0:
            raise ValueError('Invalid command profiling player ID')

        key = (operation, sequence, player_id)
        selected = False
        if self.enabled and operation in _OPERATIONS:
            with self._lock:
                if self._selected is None:
                    self._selected = key
                if self._selected == key and phase not in self._used_phases:
                    self._used_phases.add(phase)
                    selected = True
        if not selected:
            yield
            return

        # Check before entering the target block. cProfile owns sys.setprofile;
        # replacing another profiler would silently corrupt its measurements.
        if sys.getprofile() is not None:
            raise RuntimeError('Cannot profile command while another profiler is active')
        import cProfile

        profiler = cProfile.Profile()
        started = perf_counter()
        callback_failed = False
        profiler.enable()
        try:
            yield
        except BaseException:
            callback_failed = True
            raise
        finally:
            wall_seconds = perf_counter() - started
            try:
                profiler.disable()
                record = self._record(profiler, wall_seconds, phase, operation,
                                      sequence, player_id, callback_failed)
                self.emit('native_command_python_profile', **record)
            except BaseException:
                if not callback_failed:
                    raise

    def _record(self, profiler, wall_seconds, phase, operation, sequence,
                player_id, callback_failed):
        import pstats

        stats = pstats.Stats(profiler)
        rows = []
        ordered = sorted(stats.stats.items(), key=lambda item: (-item[1][3],
                          item[0][0], item[0][1], item[0][2]))
        for (filename, line, function), (primitive_calls, calls,
                                         self_seconds, cumulative_seconds, _callers) in ordered[:_MAX_ROWS]:
            filename, filename_truncated = _bounded(str(filename), _MAX_FILENAME)
            function, function_truncated = _bounded(str(function), _MAX_FUNCTION)
            rows.append(dict(filename=filename, line=int(line), function=function,
                calls=int(calls), primitive_calls=int(primitive_calls),
                recursive_calls=max(0, int(calls) - int(primitive_calls)),
                cumulative_seconds=float(cumulative_seconds),
                self_seconds=float(self_seconds),
                filename_truncated=filename_truncated,
                function_truncated=function_truncated))
        return dict(episode_id=self.episode_id,
            game_generation=self.game_generation, player_id=player_id,
            sequence=sequence, operation=operation, phase=phase,
            actor_channel=False, wall_seconds=float(wall_seconds),
            outcome='error' if callback_failed else 'ok',
            total_function_count=len(ordered),
            reported_function_count=len(rows), truncated=len(ordered) > len(rows),
            functions=rows)

    def emit_captured(self, profiler, *, phase, operation, sequence, player_id,
                      wall_seconds, core_identity, callback_failed=False):
        """Emit one worker-thread native Load profile after its identity exists."""
        if not self.enabled:
            return
        if (phase != 'load' or operation != 'reset' or type(sequence) is not int
                or sequence != 0 or type(player_id) is not int or player_id < 0
                or type(wall_seconds) not in (int, float) or not math.isfinite(wall_seconds)
                or wall_seconds < 0 or type(callback_failed) is not bool):
            raise ValueError('Invalid captured Load profiling metadata')
        fields = {'actual_core_sha256', 'reference_core_sha256',
                  'execution_profile_id', 'execution_image_sha256'}
        if (type(core_identity) is not dict or set(core_identity) != fields
                or type(core_identity['execution_profile_id']) is not str
                or not core_identity['execution_profile_id']
                or len(core_identity['execution_profile_id']) > 128
                or any(type(core_identity[key]) is not str for key in
                       ('actual_core_sha256', 'reference_core_sha256', 'execution_image_sha256'))
                or any(_SHA256_RE.fullmatch(core_identity[key]) is None for key in
                       ('actual_core_sha256', 'reference_core_sha256', 'execution_image_sha256'))
                or core_identity['actual_core_sha256'] != core_identity['execution_image_sha256']
                or core_identity['actual_core_sha256'] == core_identity['reference_core_sha256']):
            raise ValueError('Captured Load core identity is not an exact current/reference pair')
        record = self._record(profiler, float(wall_seconds), phase, operation,
                              sequence, player_id, callback_failed)
        record['core_identity'] = dict(core_identity)
        self.emit('native_load_python_profile', **record)

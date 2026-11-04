"""Shared bounded process launch after engine-specific input preparation.

The existing session owns readers, resource monitoring, request validation and
reaping. Engine adapters may explicitly select the initial protocol's source
profile; they do not replace the bounded transport or reply validation.
"""
import copy
import queue
import subprocess
import threading
import time
from .resource_resolution import resolve_path as _resolve_resource_path
from .native.native_episode_identity import DiagnosticEpisodeIdentity


def launch(self, HOST, worker, closure, env, captured, reset_started):
    from .native.native_saved_session import MEMORY_LIMIT, MAX_STDERR, ROOT
    from .native.native_official_bundle import LOCALIZATION_HANDOFF_ENV
    self.process = None
    self.job = None
    self.protocol = None
    self.last = None
    self.error = None
    self.stop_reason = None
    self.peak = {}
    self.samples = 0
    self.close_context = None
    self.stdout_native_records = []
    self.responses = queue.Queue(maxsize=2)
    self.done = threading.Event()
    self.error_lock = threading.Lock()
    self.threads = []
    self.started = time.perf_counter()
    self.finished = False
    self.command_log = _resolve_resource_path(self.run / 'commands.jsonl').open('wb')
    try:
        phase_started = time.perf_counter()
        self.process = subprocess.Popen([str(HOST), '-B', str(worker), str(self.run / 'closure.json')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, env=env, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        env.pop(LOCALIZATION_HANDOFF_ENV, None)
        handoff_key = None
        self.job = self.win.job(self.process, MEMORY_LIMIT)
        for target, args in ((self._read_stream, (self.process.stdout, 'events.jsonl', self.stdout_limit_bytes, True)), (self._read_stream, (self.process.stderr, 'stderr.txt', MAX_STDERR, False)), (self._watch, ())):
            thread = threading.Thread(target=target, args=args, daemon=True)
            self.threads.append(thread)
            thread.start()
        self._send(b'go\n')
        response = self._receive()
        self.reset_timings_seconds['child_spawn_to_initial_response_seconds'] = time.perf_counter() - phase_started
        phase_started = time.perf_counter()
        identity = DiagnosticEpisodeIdentity(response['episode_id'], response['game_generation'])
        initialize = getattr(self, '_initial_protocol', None)
        self.protocol = (initialize(identity, closure) if initialize is not None
                         else self.protocol_class(identity, self.nonce, round_limit=closure['rounds']))
        if captured is not None:
            self.protocol.initial_turn = closure['initial_turn']
        self.response_validator(response, self.protocol, 'reset')
        self.protocol.ended = response['outcome']['terminated']
        self._accepted_response(response)
        self.last = copy.deepcopy(response)
        self.reset_timings_seconds['initial_response_validation_seconds'] = time.perf_counter() - phase_started
        self.reset_timings_seconds['reset_total_seconds'] = time.perf_counter() - reset_started
        return copy.deepcopy(response)
    except BaseException as exc:
        self._fail('reset_failed', repr(exc))
        self._finish()
        raise

"""Bounded Python pipe session for the saved Base diagnostic, not a Gym env.

Every reset reaps the old process and creates private databases and a new
native episode identity. Native Destroy/reload in one process is not assumed.
The development-turn operation makes automatic diagnostic decisions; it is
not an agent action space and is never admitted for strategic training.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from datetime import datetime
from datetime import timezone
import copy, hashlib, json, os, queue, subprocess, sys, threading, time, uuid
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.native.native_saved_session_protocol import SCHEMA
from civ6_host.runtime.native.native_saved_session_protocol import SessionProtocol
from civ6_host.runtime.native.native_saved_session_protocol import validate_response
from civ6_host.runtime.native.legacy_budget import MAX_EPISODE_SECONDS
from civ6_host.runtime.native.legacy_budget import validate_collection
from civ6_host.runtime.native.legacy_budget import is_extended
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_session.py')))).resolve().parents[1]
MEMORY_LIMIT = 512 * 1024 * 1024
LIFETIME = 45
MAX_LINE = 1024 * 1024
MAX_STDOUT = 64 * 1024 * 1024
MAX_STDERR = 1024 * 1024
MAX_EXTENDED_STDOUT = 512 * 1024 * 1024
MAX_STANDARD_STDOUT = 256 * 1024 * 1024

def stdout_limit_ceiling(episode_budget):
    """Choose the bounded native event log cap for a validated episode budget."""
    if episode_budget is not None and is_extended(episode_budget) and (episode_budget['max_decisions'] > 128):
        return MAX_EXTENDED_STDOUT
    return MAX_STANDARD_STDOUT

def sha(path):
    return hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(path))).read_bytes()).hexdigest()

def write_json(path, value):
    _resolve_resource_path(Path(path)).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

def validate_episode_budget_closure(closure):
    """Validate the opt-in native lifetime/round binding in a worker closure.

    Historical closures omit ``episode_budget`` and retain their 180-second
    ceiling. A present field must carry the exact extended learning budget;
    the closure cannot independently raise either native bound.
    """
    if type(closure) is not dict:
        raise ValueError('Native worker closure must be an object')
    if 'episode_budget' not in closure:
        if type(closure.get('lifetime_seconds')) is not int or not 1 <= closure['lifetime_seconds'] <= __import__('civ6_host.runtime.session_limits', fromlist=['standard_lifetime_limit']).standard_lifetime_limit(closure.get('input_profile')):
            raise ValueError('Native closure exceeds its standard profile lifetime ceiling')
        stdout_limit = closure.get('stdout_limit_bytes')
        if stdout_limit is not None and (type(stdout_limit) is not int or not 1024 * 1024 <= stdout_limit <= MAX_STANDARD_STDOUT):
            raise ValueError('Legacy native closure exceeds its stdout log ceiling')
        return None
    budget = validate_collection(closure['episode_budget'])
    if not is_extended(budget):
        raise ValueError('Native closure requires the explicit extended episode budget')
    if type(closure.get('rounds')) is not int or closure['rounds'] != budget['max_rounds'] or type(closure.get('lifetime_seconds')) is not int or (closure['lifetime_seconds'] != budget['wall_seconds']):
        raise ValueError('Native closure bounds differ from the extended episode budget')
    stdout_limit = closure.get('stdout_limit_bytes')
    if stdout_limit is not None and (type(stdout_limit) is not int or not 1024 * 1024 <= stdout_limit <= stdout_limit_ceiling(budget)):
        raise ValueError('Native closure stdout limit exceeds its episode budget ceiling')
    return budget

class NativeSavedSession:
    event_line_limit_bytes = MAX_LINE
    input_profile = 'single'
    worker_name = 'official_session_worker913.py'
    closure_schema = 'civ6rl.saved_session913.closure.v1'
    protocol_class = SessionProtocol
    response_validator = staticmethod(validate_response)
    command_schema = SCHEMA

    def __init__(self, run_root=None, *, round_limit=8, lifetime_seconds=LIFETIME, stdout_limit_mib=64, official_bundle=None, episode_budget=None, _admitted_bundle=None):
        if type(round_limit) is not int or not 1 <= round_limit <= self.protocol_class.max_round_limit:
            raise ValueError('Invalid configured diagnostic round limit')
        if self.protocol_class is SessionProtocol and round_limit != 8:
            raise ValueError('Legacy automatic worker retains its eight-round profile')
        budget = None
        if episode_budget is not None:
            budget = validate_collection(episode_budget)
            if not is_extended(budget):
                raise ValueError('Native episode budget requires the explicit extended contract')
            from civ6_host.runtime.native.native_action_session import ActionProtocol
            if not issubclass(self.protocol_class, ActionProtocol):
                raise ValueError('Extended episode budgets require the explicit action protocol')
            if round_limit != budget['max_rounds'] or lifetime_seconds != budget['wall_seconds']:
                raise ValueError('Native session bounds must match the declared episode budget')
        max_lifetime = MAX_EPISODE_SECONDS if budget is not None else __import__('civ6_host.runtime.session_limits', fromlist=['standard_lifetime_limit']).standard_lifetime_limit(self.input_profile)
        stdout_limit_ceiling_bytes = stdout_limit_ceiling(budget)
        if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= max_lifetime or type(stdout_limit_mib) is not int or (not 1 <= stdout_limit_mib <= stdout_limit_ceiling_bytes // (1024 * 1024)):
            raise ValueError('Invalid bounded session lifetime or log budget')
        if self.protocol_class is SessionProtocol and (lifetime_seconds != LIFETIME or stdout_limit_mib != 64):
            raise ValueError('Legacy automatic worker retains its resource bounds')
        self.episode_budget = budget
        self.lifetime_seconds = lifetime_seconds
        self.stdout_limit_bytes = stdout_limit_mib * 1024 * 1024
        self.round_limit = round_limit
        self.run_root = _resolve_resource_path(_resolve_resource_path(Path(run_root or ROOT / 'work/saved-session913/runs'))).resolve()
        if not self.run_root.is_relative_to(ROOT / 'work'):
            raise ValueError('Session evidence must stay in work')
        self.owner_thread = threading.get_ident()
        self.official_bundle = None
        if _admitted_bundle is not None and official_bundle is None:
            raise ValueError('An admitted bundle requires its exact official reference')
        self._admitted_bundle = _admitted_bundle
        if official_bundle is not None:
            if self.protocol_class is SessionProtocol:
                raise ValueError('Official bundle requires an explicit action session, not the automatic historical worker')
            from civ6_host.runtime.native.native_official_bundle import normalize_reference
            self.official_bundle = normalize_reference(official_bundle)
        self.process = None
        self.job = None
        self.protocol = None
        self.last = None
        self.runs = []
        self.finished = True
        self.reset_timings_seconds = {}
        self.reset_resource_samples = []

    def _owner(self):
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError('Use the session from one parent thread')

    def _check_reset_resources(self, phase):
        """Refuse before costly work, and recheck after it; never lower the reserve."""
        available = self.win.available()
        required = MEMORY_LIMIT + 2 * 1024 ** 3
        admitted = min(available['physical_available_bytes'], available['commit_available_bytes']) >= required
        self.reset_resource_samples.append(dict(phase=phase, elapsed_seconds=time.perf_counter() - self.reset_started, available=dict(available), parent_memory=self.win.memory(), required_available_bytes=required, admitted=admitted))
        if not admitted:
            self.reset_timings_seconds['reset_total_seconds'] = time.perf_counter() - self.reset_started
            raise RuntimeError('Need 512 MiB child budget plus 2 GiB reserve (' + phase + ')')

    def reset(self):
        reset_started = time.perf_counter()
        self._owner()
        previous = getattr(self, 'run', None)
        if not self.finished:
            self.close_context = 'reset'
            self.close()
        self.reset_timings_seconds = {}
        self.reset_resource_samples = []
        self.reset_started = reset_started
        replaces = None
        if previous is not None:
            if not self.report['reaped']:
                raise RuntimeError('Previous native process was not reaped')
            replaces = dict(run=previous.relative_to(ROOT).as_posix(), supervisor_sha256=sha(previous / 'supervisor.json'), episode_id=self.report['episode_id'], previous_pid=self.report['pid'], previous_reaped=True)
        from civ6_host.runtime.native.native_probe import Windows
        from civ6_host.runtime.native.native_probe import prepare_init_fixture_copies
        self.win = Windows()
        self._check_reset_resources('before_preflight')
        from civ6_host.runtime.native.native_official_load import SINGLE_PROFILE
        from civ6_host.runtime.native.native_official_load import HOTSEAT_FOUR_PROFILE
        from civ6_host.runtime.native.native_official_load import WITNESS_PATH
        if self.input_profile not in ('single', 'hotseat-four', 'lan'):
            raise ValueError('Unknown saved session profile')
        from civ6_host.runtime.capture_profiles import LAN_PROFILE
        selected = {'single': SINGLE_PROFILE, 'hotseat-four': HOTSEAT_FOUR_PROFILE, 'lan': LAN_PROFILE}[self.input_profile]
        if self.input_profile == 'lan' and self.official_bundle is None:
            raise ValueError('LAN session requires its exact official bundle')
        if str(ROOT / 'tools') not in sys.path:
            pass
        from civ6_host.runtime.workers.run_official_postload909 import HOST
        from civ6_host.runtime.workers.run_official_postload909 import HOST_SHA
        from civ6_host.runtime.workers.run_official_postload909 import CACHE_MANIFEST
        from civ6_host.runtime.workers.run_official_postload909 import CACHE_MANIFEST_SHA
        phase_started = time.perf_counter()
        try:
            if sha(HOST) != HOST_SHA:
                raise ValueError('Pinned host changed')
            captured = None
            source_fixture = CACHE_MANIFEST
            if self.official_bundle is not None:
                from civ6_host.runtime.native.native_official_bundle import prepare_official_bundle
                captured, source_fixture = prepare_official_bundle(dict(path=self.official_bundle[0], sha256=self.official_bundle[1]), input_profile=self.input_profile, output_directory=self.run_root / ('inputs-' + uuid.uuid4().hex), **{'_admitted_bundle': self._admitted_bundle} if self._admitted_bundle is not None else {})
                self._set_bundle_initial_turn(captured.initial_turn)
            elif sha(CACHE_MANIFEST) != CACHE_MANIFEST_SHA:
                raise ValueError('Pinned official-cache fixture changed')
            from civ6_host.runtime.native.native_checkpoint_load import verify_source
            from civ6_host.runtime.native import native_stdout_transport as transport
            core_path = _resolve_resource_path(Path(verify_source()['provider']['images']['core']['path']))
            self.stdout_identity = dict(core_sha256=sha(core_path), host_sha256=sha(HOST))
            if self.stdout_identity != dict(core_sha256=transport.CORE_SHA256, host_sha256=transport.HOST_SHA256):
                raise ValueError('Saved-session stdout transport requires the exact Base Core and Host41')
            transport.verify_source()
            self._check_reset_resources('after_preflight')
        finally:
            self.reset_timings_seconds['parent_preflight_seconds'] = time.perf_counter() - phase_started
        phase_started = time.perf_counter()
        isolation = prepare_init_fixture_copies(source_fixture, 1)
        self.reset_timings_seconds['fixture_prepare_total_seconds'] = time.perf_counter() - phase_started
        self.reset_timings_seconds['fixture_prepare_subphases_seconds'] = isolation.get('timings_seconds', {})
        phase_started = time.perf_counter()
        fixture = _resolve_resource_path(Path(isolation['workers'][0]['manifest_path']))
        worker = _worker_path(self.worker_name)
        self.run = self.run_root / ('run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
        self.run.mkdir(parents=True)
        self.runs.append(self.run)
        files = list((ROOT / 'civ6rl').glob('*.py'))
        files.append(ROOT / 'civ6rl/learning/diagnostic_budget998.py')
        if captured is None:
            files += list(selected.folder.rglob('*'))
        files += [worker, ROOT / 'tools/run_official_postload909.py', HOST, source_fixture, fixture, WITNESS_PATH, ROOT / 'work/official-save909/singleplayer-capability-branch-proof.json', ROOT / 'work/native-controller911/source-r2.json']
        if captured is None:
            files += [ROOT / 'work/official-cache912/database-comparison.json', ROOT / 'work/phase23-native-fixture02/icudt56l.dat']
        else:
            files += [ROOT / 'tools/capture_phase1_bundle994.py', ROOT / 'tools/capture_phase1_bundle974.py']
        if self.input_profile == 'hotseat-four' and captured is None:
            files += [ROOT / 'tools/official_hotseat_worker923.py', ROOT / 'work/official-hotseat921/configuration-opaque-evidence921.json', ROOT / 'work/official-hotseat921/player-human-source.json', ROOT / 'evidence/native-official-hotseat922.json', ROOT / 'evidence/phase2-hotseat-save-admin/before.json', ROOT / 'evidence/phase2-hotseat-save-admin/result.json']
        for row in isolation['workers'][0]['databases'].values():
            files += [_resolve_resource_path(Path(row['source_path'])), _resolve_resource_path(Path(row['copy_path']))]
        self.pins = {_pin_key(p): sha(p) for p in files if _resolve_resource_path(p).is_file()}
        self.pins.update(_installed_source_pins())
        if captured is not None:
            self.pins.update(captured.dependencies)
        self.nonce = uuid.uuid4().hex
        closure = dict(schema=self.closure_schema, pins=self.pins, nonce=self.nonce, fixture=str(fixture), fixture_isolation=isolation, input_profile=self.input_profile, rounds=self.round_limit, native_controller=True, experimental_fresh_controller=False, database_profile='official-cache-phase23-diagnostic', replaces=replaces, stdout_transport=dict(schema=transport.SCHEMA, source_sha256=transport.SOURCE_SHA256, **self.stdout_identity), lifetime_seconds=self.lifetime_seconds, stdout_limit_bytes=self.stdout_limit_bytes)
        if self.episode_budget is not None:
            closure['episode_budget'] = copy.deepcopy(self.episode_budget)
        if captured is not None:
            from civ6_host.runtime.native.native_official_bundle import DATABASE_PROFILE
            closure.update(database_profile=DATABASE_PROFILE, official_bundle=dict(path=captured.reference[0], sha256=captured.reference[1]), initial_turn=captured.initial_turn)
        handoff_key = self._write_private_closure(closure, captured=captured)
        self.reset_timings_seconds['closure_pin_and_write_seconds'] = time.perf_counter() - phase_started
        from civ6_host.runtime.native.native_official_bundle import LOCALIZATION_HANDOFF_ENV
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        env.pop(LOCALIZATION_HANDOFF_ENV, None)
        if handoff_key is not None:
            env[LOCALIZATION_HANDOFF_ENV] = handoff_key
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', CIV6RL_PYTHON_HOME=sys.base_prefix)
        env['PATH'] = sys.base_prefix + os.pathsep + env.get('PATH', '')
        from civ6_host.runtime.session_launch import launch
        return launch(self, HOST, worker, closure, env, captured, reset_started)

    def _fail(self, reason, error=None):
        with self.error_lock:
            if self.stop_reason is None:
                self.stop_reason = reason
                self.error = error
            if self.process is not None and self.process.poll() is None:
                if self.job:
                    self.win.kernel.TerminateJobObject(self.job, 124 if reason == 'lifetime_limit' else 125)
                else:
                    self.process.kill()

    def _watch(self):
        while not self.done.wait(0.1):
            if self.process.poll() is not None:
                return
            if time.perf_counter() - self.started >= self.lifetime_seconds:
                self._fail('lifetime_limit', 'Session lifetime exceeded')
                return
            try:
                memory = self.win.memory(int(self.process._handle))
                self.samples += 1
                for key, value in memory.items():
                    self.peak[key] = max(value, self.peak.get(key, 0))
            except OSError as exc:
                if self.process.poll() is None:
                    self._fail('memory_monitor_failed', repr(exc))
                return

    def _read_stream(self, pipe, name, limit, events):
        line_limit = self.event_line_limit_bytes if events else MAX_LINE
        total = 0
        line_number = 0
        try:
            from civ6_host.runtime.stdout_transport_profiles import decode_record as _decode_stdout_record, selected_profile as _stdout_profile
            stdout_profile = _stdout_profile(**self.stdout_identity) if events else None
            with _resolve_resource_path(self.run / name).open('wb') as log:
                while True:
                    line = pipe.readline(line_limit + 1)
                    if not line:
                        return
                    line_number += 1
                    total += len(line)
                    if total > limit or len(line) > line_limit:
                        raise ValueError('Bounded native log exceeded')
                    log.write(line)
                    if events:
                        if not line.endswith(b'\n'):
                            raise ValueError('Incomplete native event line')
                        event, native_record = _decode_stdout_record(line, stdout_profile, line_number=line_number, line_limit=line_limit)
                        if native_record is not None:
                            if len(self.stdout_native_records) >= 4096:
                                raise ValueError('Native diagnostic record budget exceeded')
                            self.stdout_native_records.append(native_record)
                        if isinstance(event, dict) and event.get('stage') == 'native_city_specialist_preparation_readback':
                            log.flush()
                        if type(event) is not dict or type(event.get('stage')) is not str:
                            raise ValueError('Malformed native event object')
                        information_store = getattr(self, '_information_store', None)
                        if information_store is not None:
                            information_store.ingest(event)
                        if event.get('stage') in ('official_session_response', 'official_session_refused'):
                            self.responses.put_nowait(event)
        except BaseException as exc:
            self._fail('pipe_reader_failed', repr(exc))

    def _send(self, payload):
        if self.process.poll() is not None:
            raise RuntimeError('Native child already exited')
        self.command_log.write(payload)
        self.command_log.flush()
        self.process.stdin.write(payload)
        self.process.stdin.flush()

    def _receive(self):
        while True:
            try:
                response = self.responses.get(timeout=0.1)
                if response['stage'] == 'official_session_refused':
                    raise RuntimeError(response['error'])
                return response
            except queue.Empty:
                if self.error is not None:
                    raise RuntimeError(self.error)
                if self.process.poll() is not None:
                    self.threads[0].join(timeout=1)
                    try:
                        response = self.responses.get_nowait()
                    except queue.Empty:
                        raise RuntimeError('Native child exited without response: ' + str(self.process.returncode))
                    if response['stage'] == 'official_session_refused':
                        raise RuntimeError(response['error'])
                    return response

    def command(self, operation):
        self._owner()
        if self.protocol is None:
            raise RuntimeError('Reset first')
        return self.request(dict(schema=self.command_schema, nonce=self.nonce, episode_id=self.protocol.identity.episode_id, game_generation=self.protocol.identity.game_generation, sequence=self.protocol.sequence + 1, operation=operation))

    def request(self, request):
        self._owner()
        if self.finished or self.protocol is None:
            raise RuntimeError('No live native session')
        operation = self.protocol.validate(request)
        try:
            self._send(json.dumps(request, separators=(',', ':')).encode('utf-8') + b'\n')
            response = self._receive()
            self.response_validator(response, self.protocol, operation, request=request)
            self._commit_response(request, response)
            self._accepted_response(response)
            self.last = copy.deepcopy(response)
            if operation == 'close':
                self._finish()
                if self.report['exit_code'] != 90 or self.report['error'] is not None or (not all(self.report['source_unchanged'].values())):
                    raise RuntimeError('Native session did not close with unchanged inputs and controlled exit')
            return copy.deepcopy(response)
        except BaseException as exc:
            self._fail('command_failed', repr(exc))
            self._finish()
            raise

    def _write_private_closure(self, closure, *, captured):
        """Finish shared inputs before subclasses freeze reward/critic identity."""
        from civ6_host.runtime.native.native_official_bundle import create_parent_localization_handoff
        from civ6_host.runtime.native.native_official_bundle import LOCALIZATION_HANDOFF_FIELD
        handoff_key = None
        from civ6_host.runtime.capture_admission import configure_prepared_closure
        compact = configure_prepared_closure(closure, captured)
        if captured is not None and (not compact):
            envelope, handoff_key = create_parent_localization_handoff(closure)
            handoff_path = self.run / 'localization-parent-validation.json'
            raw = json.dumps(envelope, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
            with _resolve_resource_path(handoff_path).open('xb') as stream:
                stream.write(raw)
            digest = hashlib.sha256(raw).hexdigest()
            self.pins[str(handoff_path.relative_to(ROOT))] = digest
            closure[LOCALIZATION_HANDOFF_FIELD] = dict(path=str(handoff_path), bytes=len(raw), sha256=digest)
        from civ6_host.runtime.resource_resolution import configure_closure as configure_resources
        configure_resources(closure)
        self._configure_closure(closure)
        write_json(self.run / 'closure.json', closure)
        return handoff_key

    def _configure_closure(self, closure):
        """Parent-side opt-in administrative extensions before the child exists."""

    def _commit_response(self, request, response):
        self.protocol.commit(request, native_terminated=response['outcome']['terminated'])

    def _accepted_response(self, response):
        """Extension point for a separately validated action catalogue."""

    def close(self):
        self._owner()
        if self.finished:
            return
        if self.close_context is None:
            self.close_context = 'requested_close'
        if self.protocol is not None and self.process.poll() is None and (self.error is None):
            return self.command('close')
        self._finish()

    def abort(self, reason='parent_abort'):
        self._owner()
        if not self.finished:
            self._fail(reason)
            self._finish()

    def _finish(self):
        if self.finished:
            return
        process = self.process
        if process is not None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._fail('reap_timeout', 'Child did not stop')
                process.kill()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.done.set()
                    self.report = dict(schema='civ6rl.saved_session913.supervisor.v1', pid=process.pid, exit_code=process.poll(), reaped=False, error='Child survived bounded termination waits', stop_reason='reap_failed', reset_timings_seconds=dict(self.reset_timings_seconds), reset_timing_scopes={'reset_total_seconds': 'parent reset inclusive total', 'child_spawn_to_initial_response_seconds': 'inclusive; child startup through first response'}, strategic_training_ready=False)
                    write_json(self.run / 'supervisor.json', self.report)
                    raise RuntimeError('Native child could not be reaped; replacement refused')
        self.done.set()
        for thread in self.threads:
            thread.join(timeout=2)
        if any((t.is_alive() for t in self.threads)):
            raise RuntimeError('Native supervisor thread failed to join')
        job_assigned = self.job is not None
        if self.job:
            self.win.kernel.CloseHandle(self.job)
            self.job = None
        pipe_cleanup_errors = []
        if process is not None:
            from civ6_host.runtime.supervisor_cleanup import close_reaped_process_pipes
            pipe_cleanup_errors = close_reaped_process_pipes(process)
            if pipe_cleanup_errors and self.error is None:
                self.error = 'Native pipe cleanup failed: ' + repr(pipe_cleanup_errors)
                self.stop_reason = self.stop_reason or 'pipe_cleanup_failed'
        self.command_log.close()
        unchanged = {name: sha(ROOT / name) == digest for name, digest in self.pins.items()}
        self.report = dict(schema='civ6rl.saved_session913.supervisor.v1', pid=process.pid if process else None, exit_code=process.returncode if process else None, reaped=process is not None and process.poll() is not None, job_assigned=job_assigned, elapsed_seconds=time.perf_counter() - self.started, timeout_seconds=self.lifetime_seconds, memory_limit_bytes=MEMORY_LIMIT, stdout_limit_bytes=self.stdout_limit_bytes, stop_reason=self.stop_reason, error=self.error, timed_out=self.stop_reason == 'lifetime_limit', close_context=self.close_context, memory_samples=self.samples, sampled_memory_peaks=self.peak, source_unchanged=unchanged, stdout_native_records=self.stdout_native_records, reset_timings_seconds=dict(self.reset_timings_seconds), reset_resource_samples=copy.deepcopy(self.reset_resource_samples), reset_timing_scopes={'reset_total_seconds': 'parent reset inclusive total', 'parent_preflight_seconds': 'non-overlapping parent validation and resource check', 'fixture_prepare_total_seconds': 'inclusive; contains fixture_prepare_subphases_seconds', 'closure_pin_and_write_seconds': 'non-overlapping parent closure pinning and write', 'child_spawn_to_initial_response_seconds': 'inclusive; child startup through first response', 'initial_response_validation_seconds': 'non-overlapping parent identity/protocol validation'}, episode_id=self.protocol.identity.episode_id if self.protocol else None, last_sequence=self.protocol.sequence if self.protocol else None, game_executable_launched=False, normal_destroy_called=False, termination_inferred_from_process_exit=False, strategic_training_ready=False)
        self.report['pipe_cleanup_errors'] = pipe_cleanup_errors
        write_json(self.run / 'supervisor.json', self.report)
        self.finished = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.abort('parent_exception')
        else:
            self.close()

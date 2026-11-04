"""Experimental mounted-Lua inbox / framed Lua.log transport; no sockets.

The game must have emitted CIV6RL_FILE_READY before connecting. Commands are
published once, atomically, and never replayed after an uncertain outcome.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import uuid
from civ6_host.runtime.native.log_frames import FrameError
from civ6_host.runtime.native.log_frames import LogFrameCollector
from civ6_host.runtime.native.log_tail import LogTail
from civ6_host.runtime.native.log_tail import LogTailError
from civ6_host.runtime.native.protocol import validate_action

class FileTransportError(RuntimeError):
    pass

class FileTimeout(FileTransportError):
    """An already published command may have executed; never blindly retry."""

def _duration(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (not math.isfinite(value)) or (value <= 0):
        raise ValueError('timeout must be positive and finite')
    return float(value)

def _lua(value):
    """Serialize our closed ASCII command vocabulary, not arbitrary Lua."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and re.fullmatch('[A-Za-z0-9_.:-]{1,128}', value):
        return '"' + value + '"'
    if isinstance(value, list):
        return '{' + ','.join((_lua(item) for item in value)) + '}'
    if isinstance(value, dict) and all((isinstance(key, str) and re.fullmatch('[a-z_]+', key) for key in value)):
        return '{' + ','.join((key + '=' + _lua(item) for key, item in sorted(value.items()))) + '}'
    raise ValueError('unsupported value in the file transport command')

def publish_command(inbox, command):
    """Publish once; briefly tolerate Windows denying the unpublished rename.

    Civ6 periodically opens the mounted inbox without delete sharing. A failed
    rename may be retried only while both the staging file and old inbox still
    have their original bytes. Never retry an acknowledged/uncertain command.
    """
    path = _resolve_resource_path(Path(inbox))
    if path.name != 'Civ6RLInbox.lua' or not _resolve_resource_path(path).is_file():
        raise ValueError('inbox must be an existing Civ6RLInbox.lua')
    data = ('-- Generated local command. Do not execute outside the Civ6RL mod.\nCiv6RL_Inbox=' + _lua(command) + '\n').encode('ascii')
    temporary = None
    previous = _resolve_resource_path(path).read_bytes()
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.civ6rl-', suffix='.tmp', delete=False) as stream:
            temporary = _resolve_resource_path(Path(stream.name))
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        deadline = time.monotonic() + 1.0
        while True:
            try:
                os.replace(temporary, path)
                break
            except PermissionError as exc:
                if getattr(exc, 'winerror', None) not in (5, 32, 33) or time.monotonic() >= deadline or (not _resolve_resource_path(temporary).is_file()) or (_resolve_resource_path(temporary).read_bytes() != data) or (_resolve_resource_path(path).read_bytes() != previous):
                    raise
                time.sleep(min(0.025, max(0.0, deadline - time.monotonic())))
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

class FileClient:
    """One writer, one game context, with the observe/step LiveEnv interface.

    File availability, mounted-script rereading and log flushing must first be
    proven in the target game mode. This does not load saves or execute Lua.
    """

    def __init__(self, inbox, log, *, timeout=150, resume_hotseat=False):
        self.inbox, self.log = (_resolve_resource_path(Path(inbox)), _resolve_resource_path(Path(log)))
        self.timeout = _duration(timeout)
        if not isinstance(resume_hotseat, bool):
            raise ValueError('resume_hotseat must be boolean')
        self.resume_hotseat = resume_hotseat
        self.session = uuid.uuid4().hex
        self._tail = None
        self._collector = LogFrameCollector(expected_session=self.session)
        self._lock_path = self.inbox.with_suffix('.lua.lock')
        self._owns_lock = False
        self._connected = False
        self._failed = False
        self._used = set()
        self._lock = threading.RLock()

    def _publish(self, op, command_id, **fields):
        try:
            publish_command(self.inbox, dict(transport_version=1, op=op, session_id=self.session, command_id=command_id, **fields))
        except (OSError, ValueError):
            self._failed = True
            raise

    def _check(self, context):
        if context not in ('InGame', 'Civ6RL'):
            raise ValueError('file transport exposes only the Civ6RL UI bridge')
        if not self._connected or self._failed:
            raise FileTransportError('file client is not connected or has failed')

    def _wait(self, command_id, accept, duration):
        deadline = time.monotonic() + duration
        try:
            while True:
                complete = None
                for line in self._tail.read_lines():
                    record = self._collector.feed_line(line)
                    if record is not None and record.get('request_id') == command_id:
                        candidate = accept(record)
                        if candidate is not None:
                            complete = candidate
                if complete is not None:
                    return complete
                if time.monotonic() >= deadline:
                    raise FileTimeout(f'command {command_id} deadline expired; outcome may be unknown; not replayed')
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        except (OSError, FrameError, FileTransportError, ValueError):
            self._failed = True
            raise

    def connect(self):
        with self._lock:
            if self._connected:
                self._check('Civ6RL')
                return self
            if self._failed:
                raise FileTransportError('failed clients cannot reconnect or replay')
            if self.inbox.name != 'Civ6RLInbox.lua' or not _resolve_resource_path(self.inbox).is_file():
                raise ValueError('inbox must be an existing Civ6RLInbox.lua')
            try:
                descriptor = _resolve_resource_path(os).open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                raise FileTransportError('inbox writer lock exists; do not run concurrent clients') from exc
            self._owns_lock = True
            try:
                with os.fdopen(descriptor, 'w', encoding='ascii') as lock_file:
                    lock_file.write(f'{os.getpid()} {self.session}\n')
                self._tail = LogTail(self.log)
                command_id = uuid.uuid4().hex
                self._publish('hello', command_id, resume_hotseat=self.resume_hotseat)

                def accept(record):
                    if record['type'] != 'transport_status':
                        return None
                    if record['status'] != 'ok' or record['reason'] != 'file_transport_ready':
                        raise FileTransportError('bridge rejected the file handshake')
                    return record
                self._wait(command_id, accept, self.timeout)
                self._connected = True
                return self
            except BaseException:
                self.close()
                raise

    def refresh_states(self):
        self._check('Civ6RL')
        return {0: 'Civ6RL'}

    def observe(self, *, context='InGame'):
        with self._lock:
            self._check(context)
            command_id = uuid.uuid4().hex
            self._publish('observe', command_id)

            def accept(record):
                if record['type'] == 'bridge_error':
                    raise FileTransportError(record['reason'])
                return record if record['type'] == 'observation' else None
            return self._wait(command_id, accept, self.timeout)

    def diagnostics(self):
        with self._lock:
            self._check('Civ6RL')
            command_id = uuid.uuid4().hex
            self._publish('diagnostics', command_id)
            return self._wait(command_id, lambda record: record if record['type'] == 'transport_status' else None, self.timeout)
    _CITY_ATTACK_CASES = frozenset(('wall_ranged', 'wall_melee', 'no_wall_ranged', 'no_wall_melee'))

    def _city_attack_diagnostic(self, operation, case_name, expected_player_id, expected_turn):
        if case_name not in self._CITY_ATTACK_CASES:
            raise ValueError('case_name is not in the fixed city-attack diagnostic allowlist')
        for name, value in (('expected_player_id', expected_player_id), ('expected_turn', expected_turn)):
            if type(value) is not int or value < 0:
                raise ValueError(f'{name} must be a nonnegative integer')
        with self._lock:
            self._check('Civ6RL')
            command_id = uuid.uuid4().hex
            self._publish(operation, command_id, case_name=case_name, expected_player_id=expected_player_id, expected_turn=expected_turn)
            expected_reason = 'city_attack_read' if operation == 'city_attack_read' else 'city_attack_request_submitted'

            def accept(record):
                if record['type'] != 'transport_status':
                    return None
                if record['status'] != 'ok' or record['reason'] != expected_reason:
                    raise FileTransportError(record.get('reason', 'city-attack diagnostic rejected'))
                if record.get('player_id') != expected_player_id or record.get('turn') != expected_turn:
                    raise FileTransportError('city-attack diagnostic has unexpected actor/turn')
                if operation == 'city_attack_read':
                    snapshot = (record.get('diagnostics') or {}).get('case_snapshot')
                    if not isinstance(snapshot, dict) or snapshot.get('case') != case_name:
                        raise FileTransportError('city-attack readback identity mismatch')
                    diagnostic = record['diagnostics']
                    if diagnostic.get('native_game_core_busy') is not False or diagnostic.get('completion') != 'state_readback_only':
                        raise FileTransportError('city-attack readback did not prove an idle state sample')
                    publish_serial = diagnostic.get('publish_serial')
                    if type(record.get('sequence')) is not int or type(publish_serial) is not int or publish_serial < 0:
                        raise FileTransportError('city-attack readback source frame is missing')
                    record['source_frame'] = {'sequence': record['sequence'], 'publish_serial': publish_serial}
                    return record
                diagnostic = record.get('diagnostics') or {}
                if diagnostic.get('native_request_id') != command_id or diagnostic.get('completion') != 'not_confirmed_by_submission_ack' or diagnostic.get('native_game_core_busy_before') is not False:
                    raise FileTransportError('city-attack request acknowledgement is incomplete or mismatched')
                return record
            return self._wait(command_id, accept, self.timeout)

    def read_city_attack(self, case_name, *, expected_player_id, expected_turn):
        """Read one allowlisted Phase14 case; returns correlated status and sample."""
        return self._city_attack_diagnostic('city_attack_read', case_name, expected_player_id, expected_turn)

    def request_city_attack(self, case_name, *, expected_player_id, expected_turn):
        """Submit one allowlisted native operation; acknowledgement is not combat completion."""
        return self._city_attack_diagnostic('city_attack_request', case_name, expected_player_id, expected_turn)
    _CITY_CAPTURE_CASES = frozenset(('secondary_capture',))

    def _city_capture_diagnostic(self, operation, case_name, expected_player_id, expected_turn):
        if case_name not in self._CITY_CAPTURE_CASES:
            raise ValueError('case_name is not in the fixed city-capture diagnostic allowlist')
        for name, value in (('expected_player_id', expected_player_id), ('expected_turn', expected_turn)):
            if type(value) is not int or value < 0:
                raise ValueError(f'{name} must be a nonnegative integer')
        with self._lock:
            self._check('Civ6RL')
            command_id = uuid.uuid4().hex
            self._publish(operation, command_id, case_name=case_name, expected_player_id=expected_player_id, expected_turn=expected_turn)
            expected_reason = {'city_capture_read': 'city_capture_read', 'city_capture_arm': 'city_capture_target_armed', 'city_capture_request': 'city_capture_request_submitted'}[operation]

            def accept(record):
                if record['type'] != 'transport_status':
                    return None
                if record['status'] != 'ok' or record['reason'] != expected_reason:
                    raise FileTransportError(record.get('reason', 'city-capture diagnostic rejected'))
                if record.get('player_id') != expected_player_id or record.get('turn') != expected_turn:
                    raise FileTransportError('city-capture diagnostic has unexpected actor/turn')
                if operation == 'city_capture_read':
                    snapshot = (record.get('diagnostics') or {}).get('case_snapshot')
                    if not isinstance(snapshot, dict) or snapshot.get('case') != case_name:
                        raise FileTransportError('city-capture readback identity mismatch')
                    diagnostic = record['diagnostics']
                    if diagnostic.get('native_game_core_busy') is not False or diagnostic.get('completion') != 'state_readback_only':
                        raise FileTransportError('city-capture readback did not prove an idle state sample')
                    publish_serial = diagnostic.get('publish_serial')
                    if type(record.get('sequence')) is not int or type(publish_serial) is not int or publish_serial < 0:
                        raise FileTransportError('city-capture readback source frame is missing')
                    record['source_frame'] = {'sequence': record['sequence'], 'publish_serial': publish_serial}
                    return record
                diagnostic = record.get('diagnostics') or {}
                if operation == 'city_capture_arm':
                    if diagnostic.get('native_arm_id') != command_id or diagnostic.get('completion') != 'fixture_damage_setup_only_no_capture':
                        raise FileTransportError('city-capture arming acknowledgement is incomplete or mismatched')
                    return record
                if diagnostic.get('native_request_id') != command_id or diagnostic.get('completion') != 'not_confirmed_by_submission_ack' or diagnostic.get('native_game_core_busy_before') is not False:
                    raise FileTransportError('city-capture request acknowledgement is incomplete or mismatched')
                return record
            return self._wait(command_id, accept, self.timeout)

    def read_city_capture(self, case_name='secondary_capture', *, expected_player_id, expected_turn):
        """Read the fixed Phase15 capture fixture; includes its source publication frame."""
        return self._city_capture_diagnostic('city_capture_read', case_name, expected_player_id, expected_turn)

    def request_city_capture(self, case_name='secondary_capture', *, expected_player_id, expected_turn):
        """Submit the fixture's one ordinary capture operation; the ACK is submission only."""
        return self._city_capture_diagnostic('city_capture_request', case_name, expected_player_id, expected_turn)

    def arm_city_capture(self, case_name='secondary_capture', *, expected_player_id, expected_turn):
        """Apply fixture-only city damage after food/production are observed; does not attack."""
        return self._city_capture_diagnostic('city_capture_arm', case_name, expected_player_id, expected_turn)

    def _administrative(self, operation, expected_player_id, expected_turn, **fields):
        """Acknowledge a bounded operation; an acknowledgement is not completion."""
        for name, value in (('expected_player_id', expected_player_id), ('expected_turn', expected_turn)):
            if type(value) is not int or value < 0:
                raise ValueError(f'{name} must be a nonnegative integer')
        with self._lock:
            self._check('Civ6RL')
            command_id = uuid.uuid4().hex
            self._publish(operation, command_id, expected_player_id=expected_player_id, expected_turn=expected_turn, **fields)

            def accept(record):
                if record['type'] != 'transport_status':
                    return None
                if record['status'] != 'ok' or record['reason'] != operation + '_requested':
                    raise FileTransportError(record.get('reason', 'administrative operation rejected'))
                if record['player_id'] != expected_player_id or record['turn'] != expected_turn:
                    raise FileTransportError('administrative acknowledgement has unexpected actor/turn')
                return record
            return self._wait(command_id, accept, self.timeout)

    def save_snapshot(self, name, *, save_directory, expected_player_id, expected_turn, timeout=None):
        """Save a NEW laboratory snapshot and wait for stable nonempty local bytes.

        save_directory must be the native folder for this mode (Hotseat/Single).
        File existence/stability is transport evidence, not proof it can be loaded;
        a separate load and state comparison is required before training resets.
        """
        if not isinstance(name, str) or not re.fullmatch('Civ6RLLab_[A-Za-z0-9_-]{1,90}', name):
            raise ValueError('snapshot must have a simple Civ6RLLab_ name')
        directory = _resolve_resource_path(_resolve_resource_path(Path(save_directory))).resolve(strict=True)
        if not _resolve_resource_path(directory).is_dir():
            raise ValueError('save_directory must be an existing native save folder')
        target = directory / (name + '.Civ6Save')
        if _resolve_resource_path(target).exists():
            raise FileExistsError('snapshot already exists; it will not be overwritten')
        duration = self.timeout if timeout is None else _duration(timeout)
        with self._lock:
            acknowledgement = self._administrative('save_snapshot', expected_player_id, expected_turn, name=name)
            deadline, previous, stable_since = (time.monotonic() + duration, None, None)
            try:
                while True:
                    now = time.monotonic()
                    try:
                        stat = _resolve_resource_path(target).stat()
                        signature = (stat.st_size, stat.st_mtime_ns)
                    except FileNotFoundError:
                        signature = None
                    if signature is not None and signature[0] > 0:
                        if signature == previous and stable_since is not None and (now - stable_since >= 0.5):
                            data = _resolve_resource_path(target).read_bytes()
                            if len(data) == signature[0] and _resolve_resource_path(target).stat().st_mtime_ns == signature[1]:
                                return {'acknowledgement': acknowledgement, 'path': str(target), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'validation': 'stable local file; load verification still required'}
                        if signature != previous:
                            stable_since = now
                    else:
                        stable_since = None
                    previous = signature
                    if now >= deadline:
                        raise FileTimeout('save requested but no stable file confirmed; not replayed')
                    time.sleep(min(0.1, deadline - now))
            except (OSError, FileTransportError):
                self._failed = True
                raise

    def read_active_database(self, request, *, timeout=None):
        """Read one bounded diagnostic page, never an actor observation/action.

        Does not attest an atomic database snapshot, active gameplay scripts,
        PID identity or correspondence with a save. Callers must join those.
        Timeout bounds protocol waiting only; it cannot cancel engine SQL.
        """
        from civ6_host.runtime.native.database_capture992 import validate_request
        from civ6_host.runtime.native.database_capture992 import validate_response
        request = validate_request(request)
        duration = self.timeout if timeout is None else _duration(timeout)
        with self._lock:
            self._check('Civ6RL')
            command_id = uuid.uuid4().hex
            self._publish('database_capture', command_id, capture=request)

            def accept(record):
                if record['type'] != 'transport_status':
                    return None
                if record['status'] != 'ok' or record['reason'] != 'database_capture_read':
                    raise FileTransportError(record.get('reason', 'database capture rejected'))
                if type(record.get('player_id')) is not int or record['player_id'] != request['expected_player_id'] or type(record.get('turn')) is not int or (record['turn'] != request['expected_turn']):
                    raise FileTransportError('database capture has unexpected actor/turn')
                data = record.get('diagnostics')
                if type(data) is not dict or set(data) != {'database_capture', 'request_id', 'completion', 'native_game_core_busy'} or data['request_id'] != command_id or (data['completion'] != 'read_only_active_connection') or (data['native_game_core_busy'] is not False):
                    raise FileTransportError('database capture request/idle readback differs')
                validate_response(data['database_capture'], request)
                return record
            return self._wait(command_id, accept, duration)

    def read_ui_availability(self, *, expected_player_id, expected_turn, timeout=None):
        """Read actual current UI controls; no selection/action or headless admission."""
        from civ6_host.runtime.native.native_ui_availability import validate_request
        from civ6_host.runtime.native.native_ui_availability import validate_response
        request = validate_request(dict(expected_player_id=expected_player_id, expected_turn=expected_turn))
        duration = self.timeout if timeout is None else _duration(timeout)
        with self._lock:
            self._check('Civ6RL')
            command_id = uuid.uuid4().hex
            self._publish('ui_availability', command_id, capture=request)

            def accept(record):
                if record['type'] != 'transport_status':
                    return None
                if record['status'] != 'ok' or record['reason'] != 'ui_availability_read':
                    raise FileTransportError(record.get('reason', 'UI availability capture rejected'))
                if type(record.get('player_id')) is not int or record['player_id'] != expected_player_id or type(record.get('turn')) is not int or (record['turn'] != expected_turn):
                    raise FileTransportError('UI availability actor/turn differs')
                data = record.get('diagnostics')
                if type(data) is not dict or set(data) != {'ui_availability', 'request_id', 'completion', 'native_game_core_busy'} or data['request_id'] != command_id or (data['completion'] != 'read_only_current_ui') or (data['native_game_core_busy'] is not False):
                    raise FileTransportError('UI availability request/idle readback differs')
                validate_response(data['ui_availability'], request)
                return record
            return self._wait(command_id, accept, duration)

    def exit_to_menu(self, *, expected_player_id, expected_turn):
        """Request normal game exit; caller must verify arrival at the main menu."""
        acknowledgement = self._administrative('exit_to_menu', expected_player_id, expected_turn)
        self.close()
        return acknowledgement

    def step(self, action, *, context='InGame', timeout=None):
        action = dict(validate_action(action))
        duration = self.timeout if timeout is None else _duration(timeout)
        with self._lock:
            self._check(context)
            request_id = action['request_id']
            if request_id in self._used:
                raise FileTransportError('request_id already used; step will not replay it')
            self._used.add(request_id)
            collected = dict(before=None, after=None, result=None, transition=None)
            handoff = action['kind'] == 'end_player_turn'

            def accept(record):
                key = {'action_result': 'result', 'action_transition': 'transition'}.get(record['type'])
                if record['type'] == 'observation':
                    key = {'before_action': 'before', 'after_action': 'after'}.get(record['event'])
                if record['type'] in ('bridge_error', 'transport_status'):
                    raise FileTransportError(record.get('reason', 'bridge rejected action'))
                if key is None:
                    return None
                if collected[key] is not None and collected[key] != record:
                    raise FileTransportError(f'conflicting {key} records for {request_id}')
                collected[key] = record
                before, after, result, transition = (collected[k] for k in ('before', 'after', 'result', 'transition'))
                if result is None:
                    return None
                if result['status'] != 'requested':
                    if transition is not None or after is not None:
                        raise FileTransportError('non-requested action unexpectedly produced a transition')
                    return collected
                if 'player_id' in action and result['player_id'] != action['player_id']:
                    raise FileTransportError('acknowledged player does not match requested actor')
                for item in (before, transition) if handoff else (before, after, transition):
                    if item is not None and item['player_id'] != result['player_id']:
                        raise FileTransportError('transition player does not match action acknowledgement')
                if before is not None and before['turn'] != action['turn']:
                    raise FileTransportError('before-state turn does not match requested action')
                if transition is None:
                    return None
                if transition['kind'] != action['kind']:
                    raise FileTransportError('transition kind does not match requested action')
                if handoff and (transition['actor_player_id'] != result['player_id'] or transition['before_turn'] != action['turn'] or (after is not None and (transition['next_player_id'] != after['player_id'] or transition['after_turn'] != after['turn']))):
                    raise FileTransportError('hotseat transition does not match actors or turns')
                for item, field in ((before, 'before_sequence'), (after, 'after_sequence')):
                    if item is not None and item['sequence'] != transition[field]:
                        raise FileTransportError(f'transition {field} does not match observation')
                return collected if before is not None and (transition['after_sequence'] == 0 or after is not None) else None
            self._publish('action', request_id, action=action)
            return self._wait(request_id, accept, duration)

    def close(self):
        with self._lock:
            if self._owns_lock:
                try:
                    self._publish('close', uuid.uuid4().hex)
                except (OSError, ValueError):
                    pass
            if self._tail is not None:
                self._tail.close()
                self._tail = None
            self._connected = False
            if self._owns_lock:
                try:
                    if _resolve_resource_path(self._lock_path).read_text(encoding='ascii') == f'{os.getpid()} {self.session}\n':
                        self._lock_path.unlink()
                except FileNotFoundError:
                    pass
                finally:
                    self._owns_lock = False

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.close()

    def read_database_rows(self, request, output_path, *, provider_nonce, timeout=None, envelope_sink=None):
        from civ6_host.runtime.localization_stream_bridge import read_rows
        return read_rows(self, request, output_path, provider_nonce=provider_nonce, timeout=timeout, envelope_sink=envelope_sink)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inbox', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=150)
    parser.add_argument('--resume-hotseat', action='store_true')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--action', type=Path)
    modes.add_argument('--diagnostics', action='store_true')
    args = parser.parse_args()
    with FileClient(args.inbox, args.log, timeout=args.timeout, resume_hotseat=args.resume_hotseat) as client:
        result = client.step(json.loads(_resolve_resource_path(args.action).read_text(encoding='utf-8'))) if args.action else client.diagnostics() if args.diagnostics else client.observe()
        print(json.dumps(result, ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()

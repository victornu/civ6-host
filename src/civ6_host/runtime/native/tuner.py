"""Local FireTuner transport, measured against Civ VI DX12 on 2026-10-10.

Wire protocol reference: lmwilki/civ6-mcp, tuner_client.py (MIT), commit
dd2019056371b92ea4854e879ddf05a8cad95e8a. See docs/tuner-transport.md.
Commands are never replayed after failure: their outcome can be unknown.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import argparse
from collections import deque
import ipaddress
import json
import math
from pathlib import Path
import socket
import struct
import threading
import time
import uuid
from civ6_host.runtime.native.protocol import decode_record
from civ6_host.runtime.native.protocol import lua_command
HEADER = struct.Struct('<Ii')
MAX_FRAME_BYTES = 8 * 1024 * 1024
MAX_PENDING_EVENTS = 4096

class TunerError(RuntimeError):
    pass

class TunerTimeout(TunerError):
    """No completion received. An already submitted command may have executed."""

class LuaError(TunerError):
    pass

def _timeout(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (not math.isfinite(value)) or (value <= 0):
        raise ValueError('timeout must be positive and finite')
    return float(value)

def encode_frame(tag: int, payload: str) -> bytes:
    if not isinstance(payload, str) or '\x00' in payload:
        raise ValueError('outgoing payload must be text without NUL')
    data = payload.encode('utf-8') + b'\x00'
    if len(data) > MAX_FRAME_BYTES:
        raise ValueError('frame too large')
    return HEADER.pack(len(data), tag) + data

class FramedSocket:
    """Buffered reads retain a partial header/body if a receive times out."""

    def __init__(self, sock):
        self.sock = sock
        self.buffer = bytearray()

    def receive(self, deadline: float) -> tuple[int, str]:
        while True:
            if len(self.buffer) >= HEADER.size:
                length, tag = HEADER.unpack_from(self.buffer)
                if not 1 <= length <= MAX_FRAME_BYTES:
                    raise TunerError(f'invalid frame length: {length}')
                size = HEADER.size + length
                if len(self.buffer) >= size:
                    data = bytes(self.buffer[HEADER.size:size])
                    del self.buffer[:size]
                    if not data.endswith(b'\x00'):
                        raise TunerError('received frame has no terminal NUL')
                    try:
                        return (tag, data[:-1].decode('utf-8'))
                    except UnicodeDecodeError as exc:
                        raise TunerError('received invalid UTF-8') from exc
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TunerTimeout('Tuner response deadline expired; command outcome may be unknown')
            self.sock.settimeout(remaining)
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout as exc:
                raise TunerTimeout('Tuner response deadline expired; command outcome may be unknown') from exc
            if not chunk:
                raise TunerError('Tuner connection closed; command outcome may be unknown')
            self.buffer.extend(chunk)

def parse_states(payload: str) -> dict[int, str]:
    parts = payload.rstrip('\x00').split('\x00')
    if len(parts) == 1:
        parts = payload.splitlines()
    if parts and parts[0] == 'LSQ:':
        parts = parts[1:]
    if not parts or parts == ['']:
        return {}
    if len(parts) % 2:
        raise TunerError('malformed Lua-state list')
    states = {}
    for number, name in zip(parts[::2], parts[1::2]):
        if not number.isascii() or not number.isdigit() or (not name):
            raise TunerError('invalid Lua-state entry')
        index = int(number)
        if index in states:
            raise TunerError('duplicate Lua-state index')
        states[index] = name
    return states

def output_text(payload: str) -> str | None:
    if not payload.startswith('O\x00'):
        return None
    _, separator, text = payload[2:].partition(': ')
    return text if separator else payload[2:]

class TunerClient:

    def __init__(self, host='127.0.0.1', port=4318, *, timeout=10.0, transcript=None):
        if host == 'localhost':
            host = '127.0.0.1'
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = False
        if not local:
            raise ValueError('Tuner host must be a loopback IP address')
        if isinstance(port, bool) or not isinstance(port, int) or (not 1 <= port <= 65535):
            raise ValueError('invalid TCP port')
        self.host, self.port, self.timeout = (host, port, _timeout(timeout))
        self.transcript = _resolve_resource_path(Path(transcript)) if transcript else None
        self.identity = ''
        self.states: dict[int, str] = {}
        self._sock = None
        self._frames = None
        self._lock = threading.RLock()
        self._events = deque()
        self._step_requests = set()

    def _record(self, direction, tag, payload):
        if self.transcript:
            self.transcript.parent.mkdir(parents=True, exist_ok=True)
            with _resolve_resource_path(self.transcript).open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'time': time.time(), 'direction': direction, 'tag': tag, 'payload': payload}, ensure_ascii=True) + '\n')

    def _send(self, tag, payload, *, timeout=None):
        if self._sock is None:
            raise TunerError('not connected')
        frame = encode_frame(tag, payload)
        self._sock.settimeout(self.timeout if timeout is None else timeout)
        self._sock.sendall(frame)
        self._record('sent', tag, payload)

    def _receive(self, deadline):
        if self._frames is None:
            raise TunerError('not connected')
        if time.monotonic() >= deadline:
            raise TunerTimeout('Tuner response deadline expired; command outcome may be unknown')
        tag, payload = self._frames.receive(deadline)
        self._record('received', tag, payload)
        if payload.startswith('ERR:') or payload.startswith('E\x00'):
            raise LuaError(payload)
        text = output_text(payload)
        if text is not None:
            try:
                record = decode_record(text)
            except ValueError as exc:
                raise TunerError('malformed asynchronous bridge record') from exc
            if record is not None:
                if len(self._events) >= MAX_PENDING_EVENTS:
                    raise TunerError('bridge event queue full; drain receive_events() regularly')
                self._events.append(record)
        return (tag, payload)

    def _take_events(self, request_id=None):
        selected, remaining = ([], deque())
        while self._events:
            record = self._events.popleft()
            if request_id is None or record.get('request_id') == request_id:
                selected.append(record)
            else:
                remaining.append(record)
        self._events = remaining
        return selected

    def receive_events(self, *, timeout=None):
        """Drain queued bridge records, or wait for the next one without sending Lua.

        Records are captured even outside execute()'s markers. An idle receive
        returns [] and preserves the connection and any partial TCP frame. Other
        transport/protocol errors close the connection. This method sends nothing.
        """
        duration = self.timeout if timeout is None else _timeout(timeout)
        with self._lock:
            if self._frames is None:
                raise TunerError('not connected')
            records = self._take_events()
            if records:
                return records
            deadline = time.monotonic() + duration
            try:
                while True:
                    self._receive(deadline)
                    records = self._take_events()
                    if records:
                        return records
            except TunerTimeout:
                return []
            except (OSError, TunerError):
                self.close()
                raise

    def _control(self, text):
        self._send(4, text)
        deadline = time.monotonic() + self.timeout
        while True:
            tag, payload = self._receive(deadline)
            if tag == 4:
                return payload

    def connect(self):
        with self._lock:
            self.close()
            try:
                self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
                self._frames = FramedSocket(self._sock)
                self.identity = self._control('APP:')
                if self.identity.split('\x00', 1)[0] != 'Civ6':
                    raise TunerError('endpoint did not identify itself as Civ6')
                self.states = parse_states(self._control('LSQ:'))
                return self
            except Exception:
                self.close()
                raise

    def refresh_states(self):
        with self._lock:
            try:
                self.states = parse_states(self._control('LSQ:'))
                return dict(self.states)
            except Exception:
                self.close()
                raise

    def state_index(self, context):
        if isinstance(context, int) and (not isinstance(context, bool)):
            if context in self.states:
                return context
        elif isinstance(context, str):
            matches = [index for index, name in self.states.items() if name == context]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise TunerError(f'ambiguous context {context!r}; select its numeric index')
        raise TunerError(f'context {context!r} not found; refresh states after loading a game')

    def execute(self, code: str, *, context='InGame', timeout=None):
        """Run explicit trusted Lua once; return printed lines until a unique marker.

        Completion of Lua does not imply completion of an asynchronous game action.
        On timeout/disconnect the connection is closed and the command is NOT retried.
        """
        duration = self.timeout if timeout is None else _timeout(timeout)
        if not isinstance(code, str) or '\x00' in code:
            raise ValueError('Lua must be text without NUL')
        with self._lock:
            index = self.state_index(context)
            token = uuid.uuid4().hex
            begin, done, error = (f'__CIV6RL_{kind}_{token}__' for kind in ('BEGIN', 'DONE', 'ERROR'))
            wrapped = f'print("{begin}"); local ok,err=pcall(function()\n{code}\nend); if not ok then print("{error}"..tostring(err)) end; print("{done}")'
            lines, started, error_text = ([], False, None)
            try:
                deadline = time.monotonic() + duration
                self._send(3, f'CMD:{index}:{wrapped}', timeout=duration)
                total = 0
                while True:
                    _, payload = self._receive(deadline)
                    text = output_text(payload)
                    if text is None:
                        continue
                    if text == begin:
                        started = True
                    elif started and text == done:
                        if error_text is not None:
                            raise LuaError(error_text)
                        return lines
                    elif started and text.startswith(error):
                        error_text = text[len(error):]
                    elif started:
                        total += len(text)
                        if total > MAX_FRAME_BYTES:
                            raise TunerError('command output exceeded the collection limit')
                        lines.append(text)
            except socket.timeout as exc:
                self.close()
                raise TunerTimeout('Tuner send deadline expired; command outcome may be unknown') from exc
            except (OSError, TunerError):
                self.close()
                raise

    def observe(self, *, context='InGame'):
        lines = self.execute('assert(ExposedMembers and ExposedMembers.Civ6RL, "Civ6RL mod unavailable"); ExposedMembers.Civ6RL.EmitObservation("tuner_poll")', context=context)
        records = [record for line in lines if (record := decode_record(line)) is not None]
        observations = [record for record in records if record['type'] == 'observation']
        if not observations:
            raise TunerError(f'bridge did not produce an observation: {lines!r}')
        return observations[-1]

    def dispatch(self, action, *, context='InGame', timeout=None):
        command = lua_command(action)
        lines = self.execute(command, context=context, timeout=timeout)
        records = [record for line in lines if (record := decode_record(line)) is not None]
        matching = [record for record in records if record['type'] == 'action_result' and record['request_id'] == action['request_id']]
        if len(matching) != 1:
            raise TunerError('missing or ambiguous action acknowledgement; do not blindly retry')
        return {'result': matching[0], 'records': records}

    def step(self, action, *, context='InGame', timeout=None):
        """Dispatch once and assemble its correlated engine transition.

        Returns complete before/after observation records, action_result and
        action_transition. Rejected/error acknowledgements have no transition.
        Requested actions require a terminal transition and its referenced states,
        even if these arrive after the command's DONE marker. The same connection
        stays open throughout. An outer deadline closes it without replay; the
        outcome is then unknown. A mod timeout/failed status is returned as-is.
        """
        lua_command(action)
        duration = self.timeout if timeout is None else _timeout(timeout)
        request_id = action['request_id']
        with self._lock:
            self.state_index(context)
            handoff = action['kind'] == 'end_player_turn'
            if handoff:
                self.state_index('PlayerChange')
            if request_id in self._step_requests or any((record.get('request_id') == request_id for record in self._events)):
                raise TunerError('request_id already used or queued; step will not replay it')
            self._step_requests.add(request_id)
            deadline = time.monotonic() + duration
            collected = {'before': None, 'after': None, 'result': None, 'transition': None}

            def accept(record):
                kind = record['type']
                key = {'action_result': 'result', 'action_transition': 'transition'}.get(kind)
                if kind == 'observation':
                    key = {'before_action': 'before', 'after_action': 'after'}.get(record['event'])
                if key is None:
                    return
                previous = collected[key]
                if previous is not None and previous != record:
                    raise TunerError(f'conflicting {key} records for {request_id}')
                collected[key] = record

            def completed():
                before, after = (collected['before'], collected['after'])
                result, transition = (collected['result'], collected['transition'])
                if result['status'] != 'requested':
                    if transition is not None or after is not None:
                        raise TunerError('non-requested action unexpectedly produced a transition')
                    return True
                if 'player_id' in action and result['player_id'] != action['player_id']:
                    raise TunerError('acknowledged player does not match the requested actor')
                for record in (before, transition) if handoff else (before, after, transition):
                    if record is not None and record['player_id'] != result['player_id']:
                        raise TunerError('transition player does not match the action acknowledgement')
                if before is not None and before['turn'] != action['turn']:
                    raise TunerError('before-state turn does not match the requested action')
                if transition is None:
                    return False
                if transition['kind'] != action['kind']:
                    raise TunerError('transition kind does not match the requested action')
                if handoff:
                    if transition['actor_player_id'] != result['player_id'] or transition['before_turn'] != action['turn'] or (after is not None and (transition['next_player_id'] != after['player_id'] or transition['after_turn'] != after['turn'])):
                        raise TunerError('hotseat transition does not match its actors or turns')
                for record, field in ((before, 'before_sequence'), (after, 'after_sequence')):
                    if record is not None and record['sequence'] != transition[field]:
                        raise TunerError(f'transition {field} does not match its observation')
                return before is not None and (transition['after_sequence'] == 0 or after is not None)
            try:
                reply = self.dispatch(action, context=context, timeout=duration)
                accept(reply['result'])
                while True:
                    if time.monotonic() >= deadline:
                        raise TunerTimeout(f'action {request_id} deadline expired; outcome may be unknown')
                    for record in self._take_events(request_id):
                        accept(record)
                    if completed():
                        return collected
                    if handoff:
                        self.execute('OnKeyUp_Return()', context='PlayerChange', timeout=max(0.001, deadline - time.monotonic()))
                        self.execute('ExposedMembers.Civ6RL.Poll()', context=context, timeout=max(0.001, deadline - time.monotonic()))
                        time.sleep(min(0.1, max(0, deadline - time.monotonic())))
                    else:
                        self._receive(deadline)
            except TunerTimeout as exc:
                self.close()
                raise TunerTimeout(f'action {request_id} deadline expired; outcome may be unknown; not replayed') from exc
            except (OSError, TunerError):
                self.close()
                raise

    def close(self):
        self._events.clear()
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = self._frames = None
                self.states = {}

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=4318)
    parser.add_argument('--context', default='InGame', help='exact context name, or numeric index')
    parser.add_argument('--timeout', type=float, default=10.0)
    parser.add_argument('--transcript', type=Path)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--probe', action='store_true', help='handshake and state list only (default)')
    actions.add_argument('--lua', help='explicit trusted Lua command; no automatic replay')
    actions.add_argument('--file', type=Path, help='UTF-8 file containing explicit trusted Lua')
    actions.add_argument('--observe', action='store_true', help='ask the installed mod for an observation')
    actions.add_argument('--action', type=Path, help='validated bridge action JSON file')
    actions.add_argument('--step', type=Path, help='dispatch action JSON once and await its engine transition')
    args = parser.parse_args()
    context = int(args.context) if args.context.isascii() and args.context.isdigit() else args.context
    with TunerClient(args.host, args.port, timeout=args.timeout, transcript=args.transcript) as client:
        result = {'identity': client.identity.split('\x00'), 'states': client.states}
        if args.file:
            result['lines'] = client.execute(_resolve_resource_path(args.file).read_text(encoding='utf-8-sig'), context=context)
        elif args.lua is not None:
            result['lines'] = client.execute(args.lua, context=context)
        elif args.observe:
            result['observation'] = client.observe(context=context)
        elif args.action:
            action = json.loads(_resolve_resource_path(args.action).read_text(encoding='utf-8-sig'))
            result['dispatch'] = client.dispatch(action, context=context)
        elif args.step:
            action = json.loads(_resolve_resource_path(args.step).read_text(encoding='utf-8-sig'))
            result['step'] = client.step(action, context=context)
        print(json.dumps(result, ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()

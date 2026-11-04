"""Explicit private-response transport for stationary official captures only.

The native writer must already have an exact retained installation proof. This
client never installs it, starts Civ6, or falls back to framed log payloads.
Game actions/turns use other existing transports and are not admitted here.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy
import json
import re
from civ6_host.runtime.native.file_client import FileClient
from civ6_host.runtime.native.file_client import FileTransportError
from civ6_host.runtime.native.protocol import PREFIX
from civ6_host.runtime.native.protocol import decode_record
from civ6_host.runtime.native import native_response_file_writer as writer
MODE = 'response_file_v1'
ALLOWED_OPERATIONS = frozenset(('hello', 'observe', 'diagnostics', 'database_capture', 'ui_availability', 'save_snapshot', 'close', 'database_row_stream'))

def _installation(reference):
    if type(reference) is not dict or set(reference) != {'path', 'bytes', 'sha256'}:
        raise ValueError('Explicit pinned writer installation required')
    if writer.reference(reference['path']) != reference:
        raise ValueError('Writer installation file changed')
    from pathlib import Path
    report = writer._json(_resolve_resource_path(_resolve_resource_path(Path(reference['path']))).read_bytes())
    result = writer.validate_installation(report)
    if result.get('status') != 'ui_writer_installed':
        raise ValueError('Writer installation was not validated')
    return result

class _ReceiptCollector:

    def __init__(self, prepared):
        self.reader = writer.ResponseFileReader(prepared)
        self.session = prepared['session_id']
        self.nonce = prepared['writer_nonce']
        self.hello = None

    def feed_line(self, line):
        if not isinstance(line, str):
            raise ValueError('Expected a complete response log line')
        if 'CIV6RL_IO_ERROR ' in line:
            raise FileTransportError('Direct response transport reported an IO error')
        if 'CIV6RL_FRAME ' + self.session + ' ' in line:
            raise FileTransportError('Framed response fallback is forbidden in direct mode')
        record = self.reader.feed_line(line)
        if record is None:
            return None
        record = decode_record(PREFIX + json.dumps(record, ensure_ascii=False, allow_nan=False))
        if record.get('request_id') == self.hello:
            expected = dict(response_mode=MODE, writer_nonce=self.nonce)
            if record.get('diagnostics') != expected:
                raise FileTransportError('Direct response handshake did not confirm the exact writer')
        return record

class ResponseFileClient(FileClient):
    """Reuse FileClient operations, one-writer lock and timeout/replay behavior."""

    def __init__(self, inbox, log, *, installation, timeout=150, resume_hotseat=False):
        if resume_hotseat is not False:
            raise ValueError('Direct capture transport cannot resume or change turns')
        checked = _installation(installation)
        prepared = copy.deepcopy(checked['prepared'])
        writer.validate_directory(prepared, empty=True)
        super().__init__(inbox, log, timeout=timeout, resume_hotseat=False)
        self.writer_installation = copy.deepcopy(installation)
        self.prepared = prepared
        self.session = prepared['session_id']
        self._collector = _ReceiptCollector(prepared)

    def connect(self):
        with self._lock:
            if not self._connected and (not self._failed):
                try:
                    checked = _installation(self.writer_installation)
                    if checked['prepared'] != self.prepared:
                        raise ValueError('Writer preparation changed before connection')
                    writer.validate_directory(self.prepared, empty=True)
                except (OSError, ValueError):
                    self._failed = True
                    raise
            return super().connect()

    def _publish(self, op, command_id, **fields):
        if op not in ALLOWED_OPERATIONS:
            raise FileTransportError('Direct capture transport forbids operation: ' + str(op))
        if type(command_id) is not str or re.fullmatch('[0-9a-f]{32}', command_id) is None:
            raise ValueError('Direct response request IDs must be exactly 32 lowercase hex characters')
        if op == 'hello':
            if fields != {'resume_hotseat': False}:
                raise ValueError('Direct response hello must retain the stationary capture scope')
            fields.update(response_mode=MODE, writer_nonce=self.prepared['writer_nonce'])
            self._collector.hello = command_id
        return super()._publish(op, command_id, **fields)

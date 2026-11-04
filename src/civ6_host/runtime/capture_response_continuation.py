"""Explicit continuation of a closed stationary capture response writer.

No installation, native call, action, turn advance or command replay occurs on
import or predecessor preparation. Existing native files remain immutable.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import stat

from .native import native_response_file_writer as writer
from .native.file_client import FileClient, FileTransportError
from .native.response_file_client import (
    ALLOWED_OPERATIONS, MODE, ResponseFileClient, _ReceiptCollector, _installation,
)
from .native.log_tail import MAX_FRAGMENT_BYTES
from .resource_resolution import historical_reference, resolve_path

SCHEMA = 'civ6-host.capture-response-predecessor.v1'
_RECEIPT = 'CIV6RL_FILE_RECEIPT '
_MAX_LOG_BYTES = 64 * 1024 * 1024
_MAX_REPORT_BYTES = 64 * 1024 * 1024
_REASONS = {
    ('ok', 'file_transport_ready'): 'hello',
    ('ok', 'file_transport_closed'): 'close',
    ('ok', 'diagnostics'): 'diagnostics',
    ('ok', 'database_capture_read'): 'database_capture',
    ('error', 'database_capture_read_failed'): 'database_capture',
    ('ok', 'database_row_stream_read'): 'database_row_stream',
    ('error', 'row_stream_native_failed'): 'database_row_stream',
    ('ok', 'ui_availability_read'): 'ui_availability',
    ('error', 'ui_availability_read_failed'): 'ui_availability',
    ('ok', 'save_snapshot_requested'): 'save_snapshot',
    ('error', 'save_snapshot_failed'): 'save_snapshot',
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _context(installation):
    checked = _installation(installation)
    original = writer._json(resolve_path(Path(installation['path'])).read_bytes())
    boundary = dict(player_id=writer._integer(original.get('player_id'), 0, 63),
                    turn=writer._integer(original.get('turn'), 0, 2**31-1))
    writer._process(checked.get('process'))
    return checked, boundary


class _StationaryCollector(_ReceiptCollector):
    """Existing receipt/protocol decoder with the stationary capture boundary."""

    def __init__(self, prepared, boundary):
        super().__init__(prepared)
        self.boundary = boundary
        self.request_ids = set()
        self.active = False
        self.connections = 0
        self.expected_request = self.expected_operation = None
        self.last = None

    def feed_line(self, line):
        record = super().feed_line(line)
        if record is None:
            return None
        request = record.get('request_id')
        _require(request not in self.request_ids, 'Duplicate native capture request ID')
        _require(all(type(record.get(k)) is int and record[k] == v
                     for k, v in self.boundary.items()), 'Native capture player/turn changed')
        operation = ('observe' if record['type'] == 'observation' and record.get('event') == 'file_poll'
                     else _REASONS.get((record.get('status'), record.get('reason')))
                     if record['type'] == 'transport_status' else None)
        _require(operation in ALLOWED_OPERATIONS, 'Non-capture or uncertain native response')
        if self.expected_request is not None:
            _require(request == self.expected_request and operation == self.expected_operation,
                     'Unexpected native capture command response')
        if not self.active:
            _require(operation == 'hello', 'Native capture prefix lacks its direct handshake')
        else:
            _require(operation != 'hello', 'Native capture reconnect precedes an acknowledged close')
        if operation == 'hello':
            _require(record.get('diagnostics') == dict(response_mode=MODE, writer_nonce=self.nonce),
                     'Native capture handshake identity differs')
            self.connections += 1
            self.active = True
        elif operation == 'close':
            self.active = False
        self.request_ids.add(request)
        self.last = record
        return record


def _scan(log, checked, boundary, *, prefix=None, exact_directory, retained_snapshot=None):
    """Replay through the original collector/reader, never seed claimed counters."""
    path = resolve_path(Path(log)).resolve(strict=True)
    collector = _StationaryCollector(checked['prepared'], boundary)
    rows = []
    digest = hashlib.sha256()
    terminal_prefix = None
    scope = False
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode), 'Capture log is not a regular file')
        identity = dict(device=before.st_dev, inode=before.st_ino)
        if prefix is not None:
            _require(identity == {k: prefix[k] for k in identity}, 'Capture log was replaced')
        limit = before.st_size if prefix is None or exact_directory else prefix['prefix_bytes']
        if retained_snapshot is not None:
            _require(before.st_size == retained_snapshot['bytes'], 'Retained capture prefix size changed')
        _require(type(limit) is int and 0 < limit <= min(before.st_size, _MAX_LOG_BYTES),
                 'Incomplete or oversized capture log prefix')
        offset = number = 0
        while offset < limit:
            raw = stream.readline(min(MAX_FRAGMENT_BYTES + 1, limit-offset))
            _require(raw.endswith(b'\n') and len(raw) <= MAX_FRAGMENT_BYTES,
                     'Incomplete or oversized capture log line')
            first = offset
            offset += len(raw)
            number += 1
            digest.update(raw)
            line = raw.decode('utf-8', errors='strict')
            if 'CIV6RL_RESPONSE_INSTALLED:' + checked['prepared']['writer_nonce'] + ':' in line:
                scope = True
            if _RECEIPT not in line:
                if scope or 'CIV6RL_FRAME ' + collector.session + ' ' in line:
                    collector.feed_line(line)  # Existing IO-error/fallback refusals.
                continue
            _require(line.count(_RECEIPT) == 1, 'Ambiguous native capture receipt')
            receipt = writer._json(line.split(_RECEIPT, 1)[1].strip())
            _require(type(receipt) is dict, 'Malformed native capture receipt')
            matches = (receipt.get('writer_nonce') == collector.nonce,
                       receipt.get('session_id') == collector.session)
            if not any(matches):
                continue
            _require(all(matches), 'Partial native writer/session identity match')
            scope = True
            if not collector.active:
                collector.hello = receipt.get('request_id')
            record = collector.feed_line(line)
            rows.append(dict(line_number=number, byte_offset=first, line=line,
                response=historical_reference(dict(path=str(collector.reader.directory / receipt['filename']),
                              bytes=receipt['bytes'], sha256=receipt['sha256']))))
            if not collector.active:
                terminal_prefix = dict(path=str(path), **identity, prefix_bytes=offset,
                                       prefix_sha256=digest.hexdigest())
        after = os.fstat(stream.fileno())
        current = path.stat()
        _require((before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
                 == (current.st_dev, current.st_ino) and min(after.st_size, current.st_size) >= limit,
                 'Capture log changed during predecessor read')
        if retained_snapshot is not None:
            signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            _require(signature(before) == signature(after) == signature(current)
                     and digest.hexdigest() == retained_snapshot['sha256'],
                     'Retained capture prefix changed during read or differs from its pin')
    _require(rows and not collector.active and collector.last.get('type') == 'transport_status'
             and collector.last.get('status') == 'ok'
             and collector.last.get('reason') == 'file_transport_closed',
             'Native capture predecessor does not end at an acknowledged close')
    if prefix is not None:
        _require(terminal_prefix == prefix, 'Native capture log prefix changed or has later receipts')
    if exact_directory:
        expected = {Path(row['response']['path']).name for row in rows}
        actual = {p.name for p in collector.reader.directory.iterdir()}
        _require(actual == expected and len(expected) == len(rows),
                 'Native capture directory has missing, duplicate or extra files')
    return dict(schema=SCHEMA, status='closed_native_capture_chain_authenticated',
        process=copy.deepcopy(checked['process']), prepared=copy.deepcopy(checked['prepared']),
        boundary=boundary, log=terminal_prefix, receipts=rows,
        reader_state=dict(sequence=collector.reader.sequence, count=collector.reader.count,
                          total_bytes=collector.reader.total),
        connection_count=collector.connections, terminal=collector.last,
        game_actions_issued=0, turns_advanced=0, atomic_snapshot_claimed=False), collector


def _retain_prefix(origin, target):
    """Copy exactly the proved closed prefix into a fresh immutable artifact."""
    _require(0 < origin['prefix_bytes'] <= _MAX_LOG_BYTES, 'Retained capture prefix exceeds 64 MiB')
    digest = hashlib.sha256()
    path = Path(origin['path'])
    with path.open('rb') as source:
        before = os.fstat(source.fileno())
        _require((before.st_dev, before.st_ino) == (origin['device'], origin['inode'])
                 and before.st_size >= origin['prefix_bytes'], 'Origin capture log changed before retention')
        with target.open('xb') as destination:
            remaining = origin['prefix_bytes']
            while remaining:
                raw = source.read(min(65536, remaining))
                _require(bool(raw), 'Origin capture prefix ended during retention')
                destination.write(raw)
                digest.update(raw)
                remaining -= len(raw)
            after = os.fstat(source.fileno())
            current = path.stat()
            _require((before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
                     == (current.st_dev, current.st_ino)
                     and min(after.st_size, current.st_size) >= origin['prefix_bytes']
                     and digest.hexdigest() == origin['prefix_sha256'],
                     'Origin capture prefix changed during retention')
    return writer.reference(target)


def prepare_predecessor(installation, log, output_path):
    """Write one new private receipt; no commands, native writes or file cleanup."""
    checked, boundary = _context(installation)
    target = writer._plain_path(output_path, exists=False)
    _require(not target.exists() and target.parent.is_dir()
             and not target.is_relative_to(Path(checked['prepared']['directory'])),
             'Predecessor report needs a fresh path outside the native response directory')
    report, _ = _scan(log, checked, boundary, exact_directory=True)
    snapshot = writer._plain_path(target.with_name(target.name + '.prefix.log'), exists=False)
    report['prefix_snapshot'] = _retain_prefix(report['log'], snapshot)
    report['installation'] = copy.deepcopy(installation)
    encoded = (json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')
    _require(len(encoded) <= _MAX_REPORT_BYTES, 'Capture predecessor report exceeds its bound')
    with target.open('xb') as stream:
        stream.write(encoded)
    return writer.reference(target)


def _validated_predecessor(reference, installation, *, exact_directory):
    _require(type(exact_directory) is bool, 'Exact-directory selection must be boolean')
    _require(type(reference) is dict and set(reference) == {'path', 'bytes', 'sha256'},
             'Explicit pinned capture predecessor required')
    writer._integer(reference['bytes'], 1, _MAX_REPORT_BYTES)
    path = writer._plain_path(reference['path'])
    _require(path.stat().st_size == reference['bytes'] and writer.reference(path) == reference,
             'Capture predecessor report pin changed')
    saved = writer._json(path.read_bytes())
    fields = {'schema','status','process','prepared','boundary','log','receipts',
              'reader_state','connection_count','terminal','game_actions_issued',
              'turns_advanced','atomic_snapshot_claimed','installation','prefix_snapshot'}
    _require(type(saved) is dict and set(saved) == fields and saved.get('schema') == SCHEMA
             and saved.get('installation') == installation, 'Capture predecessor installation differs')
    _require(type(saved['log']) is dict and set(saved['log']) == {
        'path','device','inode','prefix_bytes','prefix_sha256'}, 'Malformed capture predecessor log identity')
    snapshot = saved['prefix_snapshot']
    _require(type(snapshot) is dict and set(snapshot) == {'path','bytes','sha256'}
             and snapshot['bytes'] == saved['log']['prefix_bytes']
             and snapshot['sha256'] == saved['log']['prefix_sha256'],
             'Retained capture prefix pin differs from the original closed prefix')
    writer._integer(snapshot['bytes'], 1, _MAX_LOG_BYTES)
    snapshot_path = writer._plain_path(snapshot['path'])
    checked, boundary = _context(installation)
    actual, collector = _scan(snapshot_path, checked, boundary, exact_directory=False,
                              retained_snapshot=snapshot)
    _require(actual['log']['prefix_bytes'] == snapshot['bytes']
             and actual['log']['prefix_sha256'] == snapshot['sha256'],
             'Retained capture snapshot is not exactly its closed native prefix')
    # These FileIDs describe preparation-time origin provenance. A later bundle
    # consumer observes the immutable snapshot, never claims to observe the old
    # AppData log after Civ6 has rotated or replaced it.
    actual['log'] = copy.deepcopy(saved['log'])
    if exact_directory:
        live, live_collector = _scan(saved['log']['path'], checked, boundary,
                                     prefix=saved['log'], exact_directory=True)
        _require(live == actual, 'Live capture prefix differs from its retained snapshot')
        collector = live_collector
    actual['prefix_snapshot'] = copy.deepcopy(snapshot)
    actual['installation'] = copy.deepcopy(installation)
    _require(actual == saved, 'Capture predecessor receipt chain or identities differ')
    return actual, collector


def validate_predecessor(reference, installation, *, exact_directory=False):
    """Revalidate snapshot/payloads; exact mode also observes the live origin.

    The default remains reusable after the original AppData log disappears.
    Snapshot FileIDs are checked only within each read, allowing resource copies.
    """
    return _validated_predecessor(reference, installation, exact_directory=exact_directory)[0]


class ContinuedResponseFileClient(ResponseFileClient):
    """A new capture handshake over one explicitly proved closed native prefix."""

    def __init__(self, inbox, log, *, installation, predecessor, timeout=150, resume_hotseat=False):
        if resume_hotseat is not False:
            raise ValueError('Direct capture continuation cannot resume or change turns')
        report, collector = _validated_predecessor(predecessor, installation, exact_directory=True)
        _require(resolve_path(Path(log)).resolve(strict=True) == Path(report['log']['path']),
                 'Capture continuation log differs from its predecessor')
        # Deliberately use the inspected FileClient constructor. The ordinary
        # ResponseFileClient constructor keeps its empty-directory guard intact.
        FileClient.__init__(self, inbox, log, timeout=timeout, resume_hotseat=False)
        self.writer_installation = copy.deepcopy(installation)
        self.predecessor = copy.deepcopy(predecessor)
        self.predecessor_report = report
        self.prepared = copy.deepcopy(report['prepared'])
        self.session = self.prepared['session_id']
        self._collector = collector
        self._used.update(collector.request_ids)
        self._hello_published = False

    def connect(self):
        return FileClient.connect(self)

    def _publish(self, op, command_id, **fields):
        if op not in ALLOWED_OPERATIONS:
            raise FileTransportError('Direct capture transport forbids operation: ' + str(op))
        if op == 'close' and not self._hello_published:
            raise ValueError('No capture close is published before its new hello')
        try:
            writer._nonce(command_id)
            _require(command_id not in self._used, 'Capture request ID was already used; never replay')
            if op == 'hello':
                _require(self._owns_lock and not self._hello_published,
                         'Capture continuation hello requires its exclusive writer lock')
                report, collector = _validated_predecessor(self.predecessor, self.writer_installation,
                                                          exact_directory=True)
                _require(report == self.predecessor_report, 'Capture predecessor changed before hello')
                _require(self._lock_path.read_text(encoding='ascii') == f'{os.getpid()} {self.session}\n',
                         'Capture continuation no longer owns the existing writer lock')
                self._collector = collector
            else:
                _require(self._hello_published, 'Capture continuation has not published its hello')
            self._used.add(command_id)
            self._collector.expected_request = command_id
            self._collector.expected_operation = op
            result = ResponseFileClient._publish(self, op, command_id, **fields)
            if op == 'hello':
                self._hello_published = True
            return result
        except (OSError, ValueError, FileTransportError):
            self._failed = True
            raise

"""Prepared private response files; no game access or registration on import.

Command generators reuse the proven root LuaEvents -> UI handoff. The caller
must explicitly qualify those commands in the game before selecting this route.
Existing RecordSink/FileClient sources are intentionally not modified here.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from civ6_host.runtime.native.native_resolved_content import ROOT
from civ6_host.runtime.native.native_localization_export import _lua_string
from civ6_host.runtime.native.native_localization_export import _process
MAX_RECORD_BYTES = 1048576
MAX_RECORDS = 50000
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
RECEIPT_SCHEMA = 'civ6rl.response_file_receipt.v1'

def _require(ok, message):
    if not ok:
        raise ValueError(message)

def _nonce(value):
    _require(isinstance(value, str) and re.fullmatch('[a-f0-9]{32}', value), 'Invalid 32-hex identity')
    return value

def _integer(value, low, high):
    _require(type(value) is int and low <= value <= high, 'Integer outside response bound')
    return value

def _plain_path(value, *, exists=True):
    path = _resolve_resource_path(Path(value)).absolute()
    _require(str(path).isascii() and _resolve_resource_path(path).resolve(strict=exists) == path, 'Noncanonical response path')
    _require(path.is_relative_to(ROOT / 'work') and path != ROOT / 'work', 'Private project path required')
    for part in path.parts[1:]:
        _require(part not in ('.', '..') and (not part.endswith(('.', ' '))) and (':' not in part), 'Unsafe response path component')
    for candidate in [*reversed(path.parents), path]:
        if not _resolve_resource_path(candidate).exists() and (not candidate.is_symlink()):
            continue
        info = candidate.lstat()
        _require(not stat.S_ISLNK(info.st_mode) and (not getattr(info, 'st_file_attributes', 0) & 1024), 'Reparse points are not admitted')
    return path

def reference(path):
    from civ6_host.runtime.resource_resolution import historical_reference
    path = _resolve_resource_path(Path(path)).absolute()
    _require(_resolve_resource_path(path).resolve(strict=True) == path and path.is_relative_to(ROOT), 'Project source artifact required')
    data = _resolve_resource_path(path).read_bytes()
    return historical_reference(dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))

def prepare_directory(folder, *, session_id=None, writer_nonce=None, max_records=MAX_RECORDS, max_total_bytes=MAX_TOTAL_BYTES):
    """Create only a fresh, empty local folder, plus an external preparation file."""
    path = _plain_path(folder, exists=False)
    _require(not _resolve_resource_path(path).exists() and _resolve_resource_path(path.parent).is_dir(), 'Fresh response folder with existing parent required')
    session = _nonce(session_id or uuid.uuid4().hex)
    nonce = _nonce(writer_nonce or uuid.uuid4().hex)
    _integer(max_records, 1, MAX_RECORDS)
    _integer(max_total_bytes, 1, MAX_TOTAL_BYTES)
    free = shutil.disk_usage(path.parent).free
    _require(free >= max_total_bytes + 16 * 1024 * 1024, 'Insufficient free space for response budget')
    marker = path.with_name(path.name + '.preparation.json')
    _require(not _resolve_resource_path(marker).exists(), 'Preparation receipt already exists')
    path.mkdir()
    report = dict(schema='civ6rl.response_file_directory.v1', directory=str(path), writer_nonce=nonce, session_id=session, max_records=max_records, max_total_bytes=max_total_bytes, max_record_bytes=MAX_RECORD_BYTES, free_bytes_at_preparation=free, status='directory_prepared', native_ui_qualified=False)
    with _resolve_resource_path(marker).open('x', encoding='utf8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report

def validate_directory(report, *, empty=False):
    _require(report.get('schema') == 'civ6rl.response_file_directory.v1' and report.get('status') == 'directory_prepared', 'Response directory not prepared')
    path = _plain_path(report['directory'])
    _require(_resolve_resource_path(path).is_dir(), 'Response directory missing')
    _nonce(report['writer_nonce'])
    _nonce(report['session_id'])
    _integer(report['max_records'], 1, MAX_RECORDS)
    _integer(report['max_total_bytes'], 1, MAX_TOTAL_BYTES)
    _require(report['max_record_bytes'] == MAX_RECORD_BYTES, 'Record bound differs')
    if empty:
        _require(not any(path.iterdir()), 'Prepared response directory is not empty')
    return path

def verify_build(path):
    path = _plain_path(path)
    report = json.loads(_resolve_resource_path(path).read_text(encoding='utf8'))
    _require(report.get('schema') == 'civ6rl.response_file_writer_build.v1' and report.get('returncode') == 0 and (report.get('test_only') is False), 'Successful production writer build required')
    _require(report.get('native_ui_qualified') is False, 'Build cannot attest live UI qualification')
    _require(not any(('RFW_TESTING' in value for value in report['command'])), 'Test compiler define refused')
    for item in report['sources'] + report['snapshots'] + [report['dll']]:
        _require(type(item) is dict and reference(item['path']) == item, 'Build source/binary pin differs')
    expected = ROOT / 'native/response_file_writer.c'
    _require(report['sources'][0] == reference(expected) and report['snapshots'][0]['sha256'] == report['sources'][0]['sha256'], 'Writer source differs')
    _require(_resolve_resource_path(Path(report['dll']['path'])).name == 'civ6rl-response-file-writer.dll', 'Unexpected writer DLL')
    return report

def registration_command(build, process, prepared):
    """Pure generator: execute later in Main State at the menu, once only."""
    _process(process)
    validate_directory(prepared, empty=True)
    _require(build.get('test_only') is False and build.get('returncode') == 0, 'Production build required')
    return _registration_body(build, process, prepared)

def _registration_body(build, process, prepared):
    _process(process)
    validate_directory(prepared)
    q = _lua_string
    nonce = prepared['writer_nonce']
    session = prepared['session_id']
    event = 'Civ6RLResponseFileHandoff_' + nonce
    key = 'Civ6RLResponseFileWriter_' + build['dll']['sha256']
    args = [prepared['directory'], nonce, session, process['pid'], process['creation_filetime'], prepared['max_records'], prepared['max_total_bytes']]
    command = f"""local env=getfenv(1); assert(rawget(env,{q(key)})==nil,"writer already registered"); local callback,err=package.loadlib({q(build['dll']['path'])},"civ6rl_response_file_write"); assert(type(callback)=="function",tostring(err)); local prepare,err=package.loadlib({q(build['dll']['path'])},"civ6rl_response_file_prepare"); assert(type(prepare)=="function",tostring(err)); local receipt=prepare({','.join((q(x) for x in args))}); assert(type(receipt)=="string","writer preparation receipt missing"); local event=LuaEvents[{q(event)}]; local nonce={q(nonce)}; local type,assert=type,assert; local listener=function(box) assert(type(box)=="table" and box.nonce==nonce and box.callback==nil,"handoff identity"); box.callback=callback; box.received=nonce end; rawset(env,{q(key)},{{callback=callback,listener=listener,event=event,receipt=receipt}}); event.Add(listener); print({q('CIV6RL_RESPONSE_PREPARED:' + nonce + ':')}..receipt)"""
    return (event, command)

def validate_preparation_receipt(receipt, prepared):
    expected = dict(schema='civ6rl.response_file_preparation.v1', status='prepared', writer_nonce=prepared['writer_nonce'], session_id=prepared['session_id'], module_file_pins_retained=True, database_function_called=False)
    _require(receipt == expected, 'Native writer preparation refused or mismatched')

def install_command(prepared, process, event, *, player_id, turn):
    """Pure UI handoff; install one optional callback, without changing RecordSink.

    Caller passes callback(encoded, session_id, request_id, sequence) and prints
    the returned short receipt. Invalid receipt is an error; no fallback replay.
    """
    _process(process)
    validate_directory(prepared)
    _integer(player_id, 0, 63)
    _integer(turn, 0, 2 ** 31 - 1)
    nonce = prepared['writer_nonce']
    session = prepared['session_id']
    q = _lua_string
    _require(event == 'Civ6RLResponseFileHandoff_' + nonce, 'Writer event differs')
    return f"""assert(Game.GetLocalPlayer()=={player_id} and Game.GetCurrentGameTurn()=={turn},"UI drift"); assert(UI.IsGameCoreBusy()==false,"GameCore busy"); assert(Civ6RL_ResponseFileWriter==nil,"writer already installed"); local box={{nonce={q(nonce)}}}; LuaEvents[{q(event)}].Call(box); assert(box.received==box.nonce and type(box.callback)=="function","writer handoff failed"); local callback,lookup=box.callback,Locale.Lookup; local nonce,session,pid,created={q(nonce)},{q(session)},{q(process['pid'])},{q(process['creation_filetime'])}; Civ6RL_ResponseFileWriter=function(encoded,session_id,request_id,sequence) assert(session_id==session and type(sequence)=="number" and sequence>0 and sequence%1==0 and sequence<=9007199254740991,"writer session/sequence"); return callback(encoded,nonce,session,request_id,string.format("%.0f",sequence),pid,created,lookup) end; Civ6RL_ResponseFileWriterIdentity={q(nonce)}; Civ6RL_ResponseFileWriterSession={q(session)}; print({q('CIV6RL_RESPONSE_INSTALLED:' + nonce + ':')}..{q(json.dumps(dict(schema='civ6rl.response_file_installation_receipt.v1', status='installed', writer_nonce=nonce, session_id=session, player_id=player_id, turn=turn), separators=(',', ':')))})"""

def _pinned(item):
    _require(type(item) is dict and reference(item['path']) == item, 'Artifact pin differs')
    return _resolve_resource_path(Path(item['path']))

def validate_registration(report):
    """Validate a retained menu receipt; caller records the actual returned lines.

    Required fields: schema/status/build/prepared/process/event/command/lines.
    This is a receipt/source join, not a live module-memory attestation.
    """
    _require(report.get('schema') == 'civ6rl.response_file_registration.v1' and report.get('status') == 'registered_at_menu', 'Writer registration incomplete')
    build = verify_build(_pinned(report['build']))
    prepared = report['prepared']
    validate_directory(prepared)
    q = dict(prepared)
    event = 'Civ6RLResponseFileHandoff_' + q['writer_nonce']
    _require(report.get('event') == event, 'Registration event differs')
    expected = _registration_without_empty_check(build, report['process'], q)
    _require(report['command'] == expected, 'Registration command differs')
    prefix = 'CIV6RL_RESPONSE_PREPARED:' + q['writer_nonce'] + ':'
    lines = report['lines']
    _require(type(lines) is list and len(lines) == 1 and isinstance(lines[0], str) and lines[0].startswith(prefix), 'Registration acknowledgement missing or ambiguous')
    validate_preparation_receipt(_json(lines[0][len(prefix):]), prepared)
    return report

def _registration_without_empty_check(build, process, prepared):
    return _registration_body(build, process, prepared)[1]

def validate_installation(report):
    """Validate the UI handoff command/receipt, without claiming a native write."""
    _require(report.get('schema') == 'civ6rl.response_file_installation.v1' and report.get('status') == 'ui_writer_installed', 'Writer installation incomplete')
    registration = _json(_resolve_resource_path(_pinned(report['registration'])).read_bytes())
    validate_registration(registration)
    prepared = registration['prepared']
    expected = install_command(prepared, registration['process'], registration['event'], player_id=report['player_id'], turn=report['turn'])
    _require(report['command'] == expected and report['process'] == registration['process'], 'Installation join differs')
    expected_receipt = dict(schema='civ6rl.response_file_installation_receipt.v1', status='installed', writer_nonce=prepared['writer_nonce'], session_id=prepared['session_id'], player_id=report['player_id'], turn=report['turn'])
    prefix = 'CIV6RL_RESPONSE_INSTALLED:' + prepared['writer_nonce'] + ':'
    lines = report['lines']
    _require(type(lines) is list and len(lines) == 1 and isinstance(lines[0], str) and lines[0].startswith(prefix) and (_json(lines[0][len(prefix):]) == expected_receipt), 'Installation acknowledgement missing or mismatched')
    return dict(prepared=prepared, process=report['process'], registration=report['registration'], status='ui_writer_installed', native_write_demonstrated=False)

def _object(pairs):
    obj = {}
    for key, value in pairs:
        _require(key not in obj, 'Duplicate JSON key')
        obj[key] = value
    return obj

def _json(data):

    def bad(value):
        raise ValueError('Non-finite JSON constant: ' + value)
    return json.loads(data, object_pairs_hook=_object, parse_constant=bad)

class ResponseFileReader:
    """Consume each exact receipt/file pair once; preserve files, never replay."""

    def __init__(self, prepared):
        self.directory = validate_directory(prepared)
        self.prepared = dict(prepared)
        self.sequence = self.count = self.total = 0

    def accept(self, receipt, *, request_id=None):
        if isinstance(receipt, (str, bytes)):
            _require(len(receipt) <= 2048, 'Oversized writer receipt')
            receipt = _json(receipt)
        fields = {'schema', 'status', 'writer_nonce', 'session_id', 'request_id', 'sequence', 'filename', 'bytes', 'sha256', 'count', 'total_bytes', 'durable_flush'}
        _require(type(receipt) is dict and set(receipt) == fields and (receipt['schema'] == RECEIPT_SCHEMA) and (receipt['status'] == 'written') and (receipt['durable_flush'] is False), 'Writer did not report a complete write')
        _require(receipt['writer_nonce'] == self.prepared['writer_nonce'] and receipt['session_id'] == self.prepared['session_id'], 'Writer/session join differs')
        _nonce(receipt['request_id'])
        if request_id is not None:
            _require(receipt['request_id'] == _nonce(request_id), 'Request join differs')
        seq = _integer(receipt['sequence'], self.sequence + 1, 2 ** 53 - 1)
        size = _integer(receipt['bytes'], 1, MAX_RECORD_BYTES)
        _require(receipt['count'] == self.count + 1 and type(receipt['count']) is int and (receipt['count'] <= self.prepared['max_records']), 'Writer count differs')
        _require(receipt['total_bytes'] == self.total + size and type(receipt['total_bytes']) is int and (receipt['total_bytes'] <= self.prepared['max_total_bytes']), 'Writer byte total differs')
        name = f"{seq}-{receipt['request_id']}.json"
        _require(receipt['filename'] == name, 'Writer filename differs')
        path = _plain_path(self.directory / name)
        info = path.lstat()
        _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and (info.st_size == size), 'Unsafe response file')
        with _resolve_resource_path(path).open('rb') as stream:
            before = os.fstat(stream.fileno())
            data = stream.read(MAX_RECORD_BYTES + 1)
            after = os.fstat(stream.fileno())
        _require((info.st_dev, info.st_ino, info.st_size) == (before.st_dev, before.st_ino, before.st_size) and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Response file changed during read')
        _require(len(data) == size and hashlib.sha256(data).hexdigest() == receipt['sha256'], 'Response bytes/SHA differ')
        record = _json(data.decode('utf8', errors='strict'))
        _require(type(record) is dict and record.get('request_id') == receipt['request_id'] and (type(record.get('sequence')) is int) and (record['sequence'] == seq), 'Payload does not match native receipt')
        self.sequence, self.count, self.total = (seq, receipt['count'], receipt['total_bytes'])
        return record

    def feed_line(self, line):
        prefix = 'CIV6RL_FILE_RECEIPT '
        _require(isinstance(line, str), 'Expected log line text')
        if prefix not in line:
            return None
        _require(line.count(prefix) == 1, 'Ambiguous receipt line')
        return self.accept(line.split(prefix, 1)[1].strip())

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
LEGACY_BUILDER_SHA = 'ce9592de130f313d1c624e3144e63ed9e421a2a9bcc2a53f4ce7a068fe1a8c3e'
LEGACY_BUILDER_BYTES = 2980
LEGACY_BUILDER_ARCHIVE = ROOT / 'work/official-capture/current-image-adapter/before/tools/build_response_file_writer.py'

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

def current_source_overlay(source_bytes, profile=None):
    """Reconstruct the reviewed current-image writer snapshot without loading it."""
    from civ6_host.runtime.native.native_resolved_content import EXE_SHA
    from civ6_host.runtime.native.native_resolved_content import CURRENT_EXE_SHA
    from civ6_host.runtime.native.native_localization_query import current_image_profile
    profile = current_image_profile() if profile is None else profile
    _require(profile.get('schema') == 'civ6rl.localization_query_execution_profile.v1' and profile.get('executable_sha256') == CURRENT_EXE_SHA and (profile.get('lookup_rva') == '0x4c9c30') and (profile.get('root_manager_rva') == '0x2d09f88') and (profile.get('lua_cs_rva') == '0x3553fa0'), 'Current writer EXE profile differs')
    images = profile.get('images', {})
    havok_name = 'HavokScript_FinalRelease.dll'
    havok = images.get(havok_name)
    _require(type(havok) is dict and havok.get('historical_sha256') and havok.get('current_sha256'), 'Current writer Havok identity is incomplete')
    hashes = {EXE_SHA: CURRENT_EXE_SHA, havok['historical_sha256']: havok['current_sha256']}
    exports = {row.get('export_name'): row for row in profile.get('havok_exports', ()) if type(row) is dict}
    old_addresses = {5023184: profile['lookup_rva'], 47222664: profile['root_manager_rva'], 55914400: profile['lua_cs_rva']}
    text = source_bytes.decode('utf-8')
    api_rows = re.findall('API\\(\\s*\\w+\\s*,\\s*"([^"]+)"\\s*,\\s*(0x[0-9a-fA-F]+)\\s*\\)', text)
    _require(len(api_rows) == 5 and len({name for name, _ in api_rows}) == 5, 'Response writer Havok API surface changed')
    for export_name, old_text in api_rows:
        matches = [row for row in exports.values() if row.get('export_name') == export_name and row.get('old_rva', '').lower() == old_text.lower() and (row.get('old_havok_sha256') == havok['historical_sha256']) and (row.get('current_havok_sha256') == havok['current_sha256'])]
        _require(len(matches) == 1 and matches[0].get('current_rva'), 'Response writer Havok export lacks an exact current name/RVA join')
        old = int(old_text, 16)
        _require(old not in old_addresses, 'Duplicate response writer relocation')
        old_addresses[old] = matches[0]['current_rva']
    _require(len(old_addresses) == 8, 'Incomplete current writer relocation set')
    replacements = []
    for old, new in hashes.items():
        count = text.count(old)
        _require(count > 0, 'Current writer source does not consume a pinned image hash')
        text = text.replace(old, new)
        replacements.append(dict(kind='image_hash', old=old, new=new, count=count))
    seen = set()

    def relocate(match):
        value = int(match.group(), 16)
        if value not in old_addresses:
            return match.group()
        seen.add(value)
        return old_addresses[value]
    text = re.sub('\\b0x[0-9a-fA-F]+\\b', relocate, text)
    _require(seen == set(old_addresses), 'Current writer source overlay did not consume the exact reviewed RVA set')
    for old, new in old_addresses.items():
        replacements.append(dict(kind='rva', old='0x' + format(old, 'x'), new=new, count=len(re.findall('\\b' + re.escape('0x' + format(old, 'x')) + '\\b', source_bytes.decode('utf-8'), re.I))))
    return (text.encode('utf-8'), dict(profile=profile, replacements=replacements))

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
    expected = ROOT / 'native/response_file_writer.c'
    from civ6_host.runtime.native.native_resolved_content import EXE_SHA
    from civ6_host.runtime.native.native_resolved_content import CURRENT_EXE_SHA
    sources, snapshots, dll = (report.get('sources'), report.get('snapshots'), report.get('dll'))
    _require(type(sources) is list and len(sources) >= 3 and (type(snapshots) is list) and (len(snapshots) == 1) and (type(dll) is dict), 'Incomplete writer build references')
    for item in snapshots + [dll]:
        _require(type(item) is dict and reference(item['path']) == item, 'Build snapshot/binary pin differs')
    archived_builder = None
    archived_builder_index = None
    for index, item in enumerate(sources):
        _require(type(item) is dict, 'Invalid writer source pin')
        if item.get('path') == str(_resolve_resource_path(ROOT / 'tools/build_response_file_writer.py').resolve()) and item.get('sha256') == LEGACY_BUILDER_SHA and (item.get('bytes') == LEGACY_BUILDER_BYTES):
            archived = reference(LEGACY_BUILDER_ARCHIVE)
            _require(archived['sha256'] == LEGACY_BUILDER_SHA and archived['bytes'] == LEGACY_BUILDER_BYTES and ({**item, 'path': archived['path']} == archived), 'Archived legacy response writer builder differs')
            archived_builder, archived_builder_index = (archived, index)
        else:
            _require(reference(item['path']) == item, 'Build source pin differs')
    _require(sources[0] == reference(expected) and _resolve_resource_path(Path(dll['path'])).name == 'civ6rl-response-file-writer.dll', 'Writer source or DLL differs')
    profile = report.get('execution_profile')
    if profile is None:
        _require(set(report).isdisjoint({'source_overlay'}) and len(sources) == 3 and (sources[1].get('sha256') == LEGACY_BUILDER_SHA) and (sources[1].get('bytes') == LEGACY_BUILDER_BYTES) and (sources[2] == reference(ROOT / 'work/official-capture/localization-query/abi-audit.json')) and (snapshots[0]['sha256'] == sources[0]['sha256']) and (_resolve_resource_path(_resolve_resource_path(Path(snapshots[0]['path']))).read_bytes() == _resolve_resource_path(expected).read_bytes()), 'Legacy writer build/source archive differs')
    else:
        _require(profile.get('executable_sha256') == CURRENT_EXE_SHA, 'Writer execution profile executable differs')
        from civ6_host.runtime.native.native_localization_query import current_image_profile
        expected_profile = current_image_profile()
        _require(profile == expected_profile, 'Current writer execution profile/evidence differs')
        _require(len(sources) == 3 + len(profile['evidence']) and sources[1] == reference(ROOT / 'tools/build_response_file_writer.py') and (sources[2] == reference(ROOT / 'work/official-capture/localization-query/abi-audit.json')) and (sources[3:] == profile['evidence']), 'Current writer source/evidence pins differ')
        snapshot_path = _plain_path(snapshots[0]['path'])
        _require(snapshot_path.parent == path.parent and snapshot_path.name == expected.name, 'Current writer snapshot location differs')
        source_overlay = report.get('source_overlay')
        _require(type(source_overlay) is list and len(source_overlay) == 1, 'Current writer source-overlay proof missing')
        reconstructed, proof = current_source_overlay(_resolve_resource_path(expected).read_bytes(), profile)
        expected_overlay = [dict(source=reference(expected), snapshot=reference(snapshot_path), replacements=proof['replacements'])]
        _require(_resolve_resource_path(snapshot_path).read_bytes() == reconstructed and source_overlay == expected_overlay, 'Current writer snapshot is not the exact reviewed one-pass overlay')
    _require(report.get('command') and str(snapshots[0]['path']) in report['command'], 'Compiler command does not compile the pinned snapshot')
    _require(report.get('execution_profile') is None or report['execution_profile']['executable_sha256'] == CURRENT_EXE_SHA, 'Unsupported writer execution profile')
    if archived_builder is not None:
        report['sources'] = list(sources)
        report['sources'][archived_builder_index] = archived_builder
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

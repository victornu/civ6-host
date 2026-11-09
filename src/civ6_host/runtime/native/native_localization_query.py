"""Explicit Localization read provider using the verified menu-to-UI handoff.

No operation occurs on import. The source is borrowed in the official UI scope.
Primary Tuner must be live at the menu; port4319 must never be used in Hotseat.
The resulting provider is only for database capture, never policy observation.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import json
import struct
import os
import tempfile
import time
import uuid
import subprocess
import hashlib
from civ6_host.runtime.native.native_localization_export import reference
from civ6_host.runtime.native.native_localization_export import _file
from civ6_host.runtime.native.native_localization_export import _lua_string
from civ6_host.runtime.native.native_localization_export import _helper_module
from civ6_host.runtime.native.native_localization_export import _process
from civ6_host.runtime.native.native_resolved_content import ROOT
from civ6_host.runtime.native.native_resolved_content import EXE_SHA
from civ6_host.runtime.native.native_resolved_content import CURRENT_EXE_SHA
CURRENT_EXE_BINDINGS_SHA = '0eb18f55c96926680baa336bb3a9ff36c0f7cc489a2836df018dd905cb507c38'
CURRENT_GETTERS_SHA = '96da73c244a9b4421e4da8ffaec14bfe1ecb3dc9e51070e717cfbcf31fd09a20'
LEGACY_BUILDER_SHA = '53baf5629ee0c625d028ffa289b30bb0fd7054e40303820fcfd4f51609df9fa8'

def current_image_profile():
    """Exact static bindings for the current helper; not a live-export claim."""
    from civ6_host.runtime.native.native_localization_capture import CURRENT_SHARED_SHA
    rows = []
    for name, digest in (('current-localization-shared-bindings.json', CURRENT_SHARED_SHA), ('current-exe-localization-bindings.json', CURRENT_EXE_BINDINGS_SHA), ('current-localization-query-getters.json', CURRENT_GETTERS_SHA)):
        path = ROOT / 'work/official-capture' / name
        raw = _resolve_resource_path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Current Localization helper source correspondence changed')
        rows.append((reference(path), json.loads(raw)))
    shared, exe, getters = (row[1] for row in rows)
    if exe['current_exe']['sha256'] != CURRENT_EXE_SHA or getters['current_database_image']['sha256'] != shared['source_images']['DatabaseDLL_FinalRelease.dll']['current_sha256']:
        raise ValueError('Current helper image correspondence differs')
    bindings = exe['current_exe_bindings']
    profile = dict(schema='civ6rl.localization_query_execution_profile.v1', executable_sha256=CURRENT_EXE_SHA, evidence=[row[0] for row in rows], images={'exe': exe['current_exe'], **shared['source_images']}, lookup_rva=bindings[0]['current_candidate_rva'], root_manager_rva=bindings[1]['current_rva'], lua_cs_rva=bindings[2]['current_rva'], havok_exports=shared['havok_qapi_exports']['exports'], native_export_qualified=False)
    if len(profile['havok_exports']) != 20:
        raise ValueError('Incomplete current Havok callback API')
    return profile

def _primary_tuner_owner(pid):
    """Attribute the local server endpoint; native callbacks also verify PID/Lua.

    Do not infer reachability from the reported TCP state: this installation
    reports state 6 for the RemotePort=0 endpoint that answers LSQ. The actual
    protocol handshake and guarded native acknowledgement remain mandatory.
    """
    if type(pid) is not int or not 0 < pid < 2**32 or os.name != 'nt':
        raise ValueError('Invalid Windows Tuner owner request')
    script = ("$ErrorActionPreference='Stop'; ConvertTo-Json -Compress -InputObject "
              "@(Get-NetTCPConnection -LocalPort 4318 | "
              "Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,OwningProcess,State)")
    powershell = _resolve_resource_path(Path(os.environ['SystemRoot'])) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    result = subprocess.run([str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script],
        capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError('Windows could not establish the primary Tuner socket owner')
    rows = json.loads(result.stdout.decode('utf-8-sig'))
    if (type(rows) is not list or not rows or len(rows) > 32
            or any(type(row) is not dict or row.get('LocalPort') != 4318 for row in rows)):
        raise ValueError('Primary Tuner endpoint inventory is absent or invalid')
    servers = [row for row in rows if type(row.get('RemotePort')) is int and row['RemotePort'] == 0
               and row.get('RemoteAddress') in ('0.0.0.0', '::')]
    if (not servers or any(type(row.get('OwningProcess')) is not int or row['OwningProcess'] != pid
                           or row.get('LocalAddress') not in ('127.0.0.1', '0.0.0.0', '::', '::1')
                           for row in servers)):
        raise ValueError('Primary Tuner server endpoint is absent, ambiguous or belongs to another process')
    identity_fields = ('LocalAddress', 'LocalPort', 'RemoteAddress', 'RemotePort', 'OwningProcess')
    return dict(source='Windows.Get-NetTCPConnection', pid=pid, port=4318,
                server_endpoints=sorted(({key: row[key] for key in identity_fields} for row in servers),
                                        key=lambda row: row['LocalAddress']),
                tcp_state_interpreted=False)

def verify_build(path):
    path = _resolve_resource_path(_resolve_resource_path(Path(path))).resolve(strict=True)
    if not path.is_relative_to(ROOT / 'work'):
        raise ValueError('Helper build must be a project artifact')
    build = json.loads(_resolve_resource_path(path).read_text(encoding='utf8'))
    if build.get('schema') != 'civ6rl.localization_query_build.v1' or build.get('returncode') != 0:
        raise ValueError('Localization query build is not successful')
    for item in build['sources'] + build['snapshots'] + [build['dll']]:
        if item['sha256'] == LEGACY_BUILDER_SHA and _resolve_resource_path(_resolve_resource_path(Path(item['path']))).resolve() == _resolve_resource_path(ROOT / 'tools/build_localization_query.py').resolve():
            item = {**item, 'path': str(ROOT / 'work/official-capture/current-image-adapter/before/tools/build_localization_query.py')}
        _file(item, limit=4 * 1024 * 1024)
    from civ6_host.runtime.localization_stream_bridge import verify_stream_build
    return verify_stream_build(build, path)

def registration_command(build, process, nonce):
    _process(process)
    if len(nonce) != 32 or any((c not in '0123456789abcdef' for c in nonce)):
        raise ValueError('Invalid registration nonce')
    quote = _lua_string
    path = quote(build['dll']['path'])
    key = quote('Civ6RLLocalizationQuery_' + build['dll']['sha256'])
    event = 'Civ6RLLocalizationQueryHandoff_' + nonce
    command = f"""local env=getfenv(1); assert(rawget(env,{key})==nil,"provider already registered"); local callback,err=package.loadlib({path},"civ6rl_localization_query"); assert(type(callback)=="function",tostring(err)); local prepare,err=package.loadlib({path},"civ6rl_localization_query_prepare"); assert(type(prepare)=="function",tostring(err)); local receipt=prepare({quote(nonce)},{quote(process['pid'])},{quote(process['creation_filetime'])}); assert(type(receipt)=="string","preparation receipt missing"); local event=LuaEvents[{quote(event)}]; local nonce={quote(nonce)}; local type,assert=type,assert; local listener=function(box) assert(type(box)=="table" and box.nonce==nonce and box.callback==nil,"handoff nonce"); box.callback=callback; box.received=nonce end; rawset(env,{key},{{callback=callback,listener=listener,event=event,receipt=receipt}}); event.Add(listener); print({quote('CIV6RL_LOC_QUERY_PREPARED:' + nonce + ':')}..receipt)"""
    from civ6_host.runtime.localization_stream_bridge import registration_command as stream_command
    return (event, stream_command(command, build, process, nonce))

def prepare(pid, build_path, folder, *, executable_sha256=EXE_SHA):
    """Once at the official menu, before the later save Load. No game action."""
    from civ6_host.runtime.workers.capture_official_content929 import ReadOnlyProcess
    from civ6_host.runtime.native.tuner import TunerClient
    folder = _resolve_resource_path(_resolve_resource_path(Path(folder))).resolve()
    if _resolve_resource_path(folder).exists() or not folder.is_relative_to(ROOT / 'work'):
        raise ValueError('Fresh project output required; uncertain registration must not be replayed')
    build = verify_build(build_path)
    folder.mkdir(parents=True)
    if executable_sha256 not in (EXE_SHA, CURRENT_EXE_SHA):
        raise ValueError('Unsupported Localization query executable')
    if executable_sha256 == CURRENT_EXE_SHA and build.get('execution_profile') != current_image_profile():
        raise ValueError('Current Localization query build/profile differs')
    nonce = uuid.uuid4().hex
    report = dict(schema='civ6rl.localization_query_registration.v1', nonce=nonce, build=reference(build_path), training_eligible=False)
    try:
        with ReadOnlyProcess(pid) as process:
            identity = process.identity()
            _process(identity)
            exe = reference(identity['image_path'])
            if exe['sha256'] != executable_sha256:
                raise ValueError('Official EXE differs')
            modules = process.modules()
            match = [m for m in modules if _resolve_resource_path(_resolve_resource_path(Path(m['path']))).resolve() == _resolve_resource_path(_resolve_resource_path(Path(identity['image_path']))).resolve()]
            if len(match) != 1:
                raise ValueError('EXE module missing or ambiguous')
            if executable_sha256 == CURRENT_EXE_SHA:
                listener = _primary_tuner_owner(pid)
            else:
                listener = struct.unpack('<Q', process.read(match[0]['base'] + 19675280 + 48, 8))[0]
                if listener < 65536:
                    raise ValueError('Primary Tuner listener absent; never use Hotseat secondary port')
            event, command = registration_command(build, identity, nonce)
            report.update(process=identity, event=event, command=command, primary_listener=listener if type(listener) is dict else hex(listener))
            if executable_sha256 == CURRENT_EXE_SHA:
                report['executable_sha256'] = executable_sha256
            with TunerClient(port=4318, timeout=20, transcript=folder / 'tuner.jsonl') as tuner:
                lines = tuner.execute(command, context='Main State', timeout=20)
            report['lines'] = lines
            prefix = 'CIV6RL_LOC_QUERY_PREPARED:' + nonce + ':'
            if len(lines) != 1 or not lines[0].startswith(prefix):
                raise ValueError('Unexpected preparation acknowledgement')
            receipt = json.loads(lines[0][len(prefix):])
            report['native_receipt'] = receipt
            if receipt != dict(schema='civ6rl.localization_query_preparation.v1', status='ok', nonce=nonce, database_function_called=False, module_file_pins_retained=True):
                raise ValueError('Native preparation refused')
            report['helper_module'] = _helper_module(process, build)
            if executable_sha256 == CURRENT_EXE_SHA and _primary_tuner_owner(pid) != listener:
                raise ValueError('Primary Tuner socket owner changed during registration')
            if identity != process.identity():
                raise ValueError('Process changed')
            report['status'] = 'registered_at_menu'
    except Exception as exc:
        report.update(status='refused', error=type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        (folder / 'registration.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    return report

def install_command(registration, *, player_id, turn):
    """Passed through the mounted mod inbox, with the FileClient single writer lock.

    Installation sets one explicit provider. It never rebinds DB.Query and never
    changes source transactions. A query error propagates to the capture reader.
    """
    if registration.get('status') != 'registered_at_menu':
        raise ValueError('Provider not registered')
    if type(player_id) is not int or not 0 <= player_id < 64 or type(turn) is not int or (turn < 0):
        raise ValueError('Invalid expected UI identity')
    quote = _lua_string
    process = registration['process']
    nonce = registration['nonce']
    from civ6_host.runtime.localization_stream_bridge import install_command as stream_install
    return stream_install(f"""assert(Game.GetLocalPlayer()=={player_id} and Game.GetCurrentGameTurn()=={turn},"UI drift"); assert(UI.IsGameCoreBusy()==false,"GameCore busy"); assert(Civ6RL_LocalizationQuery==nil,"provider already installed"); local box={{nonce={quote(nonce)}}}; LuaEvents[{quote(registration['event'])}].Call(box); assert(box.received==box.nonce and type(box.callback)=="function","provider handoff failed"); local callback,lookup=box.callback,Locale.Lookup; local pid,created={quote(process['pid'])},{quote(process['creation_filetime'])}; Civ6RL_LocalizationQuery=function(sql) return callback(sql,pid,created,lookup) end; Civ6RL_LocalizationQueryIdentity={quote(nonce)}; local rows=Civ6RL_LocalizationQuery("SELECT sqlite_version() AS version"); assert(type(rows)=="table" and #rows==1 and type(rows[1].version)=="string","provider probe failed"); print({quote('CIV6RL_LOC_QUERY_READY:' + nonce + ':')}..rows[1].version)""", registration, player_id, turn)

def install(registration_path, folder, *, inbox, log, player_id, turn):
    """Single-use UI installation. Preserve inbox bytes and all failure receipts."""
    from civ6_host.runtime.workers.capture_official_content929 import ReadOnlyProcess
    from civ6_host.runtime.native.native_localization_export import runtime
    from civ6_host.runtime.native.native_localization_export import runtime_identity
    registration_path = _resolve_resource_path(_resolve_resource_path(Path(registration_path))).resolve(strict=True)
    registered = json.loads(_resolve_resource_path(registration_path).read_text(encoding='utf8'))
    executable_sha256 = registered.get('executable_sha256', EXE_SHA)
    if executable_sha256 not in (EXE_SHA, CURRENT_EXE_SHA):
        raise ValueError('Unsupported registered Localization executable')
    folder = _resolve_resource_path(_resolve_resource_path(Path(folder))).resolve()
    if _resolve_resource_path(folder).exists() or not folder.is_relative_to(ROOT / 'work'):
        raise ValueError('Fresh project folder required; no uncertain install retry')
    build_ref = registered['build']
    _file(build_ref)
    build = verify_build(build_ref['path'])
    inbox, log = (_resolve_resource_path(Path(inbox)), _resolve_resource_path(Path(log)))
    if inbox.name != 'Civ6RLInbox.lua' or not _resolve_resource_path(inbox).is_file():
        raise ValueError('Existing mounted mod inbox required')
    folder.mkdir(parents=True)
    nonce = uuid.uuid4().hex
    marker = 'CIV6RL_QUERY_INSTALL_' + nonce
    body = install_command(registered, player_id=player_id, turn=turn)
    code = f"""Civ6RL_Inbox={{transport_version=1,op="idle"}}\nif Civ6RL_LocalizationQueryInstallNonce~={_lua_string(nonce)} then Civ6RL_LocalizationQueryInstallNonce={_lua_string(nonce)}; local ok,result=pcall(function() {body}; return "installed" end); print({_lua_string(marker + ' RESULT ')}..tostring(ok).." "..tostring(result)) end\n""".encode('ascii')
    (folder / 'command.lua').write_bytes(code)
    report = dict(schema='civ6rl.localization_query_installation.v1', nonce=nonce, registration=reference(registration_path), command=reference(folder / 'command.lua'), atomic_snapshot_proven=False, training_eligible=False, game_actions_issued=0)

    def atomic(data, expected):
        with tempfile.NamedTemporaryFile(dir=inbox.parent, prefix='.civ6rl-query-', suffix='.tmp', delete=False) as stream:
            name = _resolve_resource_path(Path(stream.name))
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        deadline = time.monotonic() + 1
        try:
            while True:
                if _resolve_resource_path(inbox).read_bytes() != expected:
                    raise ValueError('Another writer changed the inbox')
                try:
                    os.replace(name, inbox)
                    return
                except OSError as exc:
                    if getattr(exc, 'winerror', None) not in (5, 32, 33) or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.02)
        finally:
            name.unlink(missing_ok=True)
    lock = inbox.with_suffix('.lua.lock')
    owns = False
    previous = None
    try:
        fd = _resolve_resource_path(os).open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        owns = True
        previous = _resolve_resource_path(inbox).read_bytes()
        with ReadOnlyProcess(registered['process']['pid']) as process:
            if process.identity() != registered['process']:
                raise ValueError('Process changed since menu preparation')
            report['helper_module'] = _helper_module(process, build)
            before = runtime.capture_process(process, folder / 'runtime-before', nonce=nonce, timeout_seconds=15, executable_sha256=executable_sha256)
            report['runtime_before'] = reference(folder / 'runtime-before/localization-manifest.json')
            identity = runtime_identity(before)
            offset = _resolve_resource_path(log).stat().st_size
            atomic(code, previous)
            deadline = time.monotonic() + 25
            found = None
            while time.monotonic() < deadline:
                with _resolve_resource_path(log).open('rb') as stream:
                    stream.seek(offset)
                    raw = stream.read(1024 * 1024)
                lines = [s for s in raw.decode('utf8', errors='replace').splitlines() if marker in s]
                results = [s.split(marker + ' RESULT ', 1)[1] for s in lines if marker + ' RESULT ' in s]
                if results:
                    if len(results) != 1:
                        raise ValueError('Duplicate install receipt')
                    found = results[0]
                    report['lines'] = lines
                    break
                time.sleep(0.1)
            if found != 'true installed':
                raise ValueError(found or 'Install outcome unknown; do not replay')
            after = runtime.capture_process(process, folder / 'runtime-after', nonce=nonce, timeout_seconds=15, executable_sha256=executable_sha256)
            report['runtime_after'] = reference(folder / 'runtime-after/localization-manifest.json')
            if runtime_identity(after) != identity or after['modules'] != before['modules']:
                raise ValueError('Localization identity changed during install/query')
            if process.identity() != registered['process']:
                raise ValueError('Process changed during install')
            report.update(status='ui_provider_installed_and_first_query_verified', process=registered['process'], runtime_identity=identity, player_id=player_id, turn=turn)
    except Exception as exc:
        report.update(status='refused', error=type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        try:
            if owns and previous is not None:
                if _resolve_resource_path(inbox).read_bytes() == code:
                    atomic(previous, code)
                report['inbox_restored'] = _resolve_resource_path(inbox).read_bytes() == previous
        finally:
            if owns:
                lock.unlink()
            (folder / 'installation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    return report

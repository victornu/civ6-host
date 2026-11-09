"""Opt-in row-file channel on the existing capture client and UI handoff.

Importing this module installs nothing. The selected helper build and ordinary
query API are reused; the official UI producer still needs live qualification.
"""
from pathlib import Path
import hashlib
import json
import re

from .database_bulk_capture import _context
from .database_row_stream import row_query, validate_native_row_stream

BUILD_SHA256='0e39bf50b9073687337f93526eada44ce9ed7910b1f011c37d2b4470ede8d492'
DLL_SHA256='f9485b49eb23b48f42ae3d37012eed130dceb059c5c4a1076442079db2c1dba6'
# Keep retained build03 artifacts readable; never reinterpret them as build04.
STREAM_BUILDS={
    '4fb65eb9cb1fb4fcc445927276a4c0d9c0e1cd1991ef0b30cfa16b0559e4ff8b':
        '3bff1ceb00c38e8619b7330ce2cf3c4ca5d68510e3d9b58e83b0f40876cc3c8d',
    DLL_SHA256:BUILD_SHA256,
    # Current EXE/Havok binding overlay; native qualification is recorded
    # separately. Recognition permits the bounded explicit capture probe.
    'a93a6d1655bf36f9e839b3c990fabc43126a855f662cc8a8877caafb75250445':
        'd9ea818a9911274d2939d13abe02083229c0bf249c70763d2467e859c2b40a85',
}


def _require(ok,message):
    if not ok:raise ValueError(message)


def stream_build(build):
    """Recognize an exact reviewed build; never infer features from filenames."""
    return type(build) is dict and type(build.get('dll')) is dict and build['dll'].get('sha256') in STREAM_BUILDS


def verify_stream_build(build,path):
    if not stream_build(build):return build
    _require(hashlib.sha256(Path(path).read_bytes()).hexdigest()==STREAM_BUILDS[build['dll']['sha256']],'Unknown row-stream build composition')
    # Existing verify_build authenticates all sources/snapshots/DLL bytes first.
    return build


def _replace(text,old,new):
    _require(text.count(old)==1,'Row-stream handoff source boundary changed')
    return text.replace(old,new)


def registration_command(command,build,process,nonce):
    if not stream_build(build):return command
    from .native.native_localization_export import _lua_string as quote
    command=_replace(command,'local prepare,err=package.loadlib(',
        'local stream,err=package.loadlib('+quote(build['dll']['path'])+',"civ6rl_localization_row_stream"); assert(type(stream)=="function",tostring(err)); local prepare,err=package.loadlib(')
    command=_replace(command,'box.callback=callback; box.received=nonce',
        'assert(box.stream==nil,"stream already supplied"); box.callback=callback; box.stream=stream; box.received=nonce')
    return command


def install_command(command,registration,player_id,turn):
    if registration.get('helper_module',{}).get('sha256') not in STREAM_BUILDS:return command
    from .native import native_localization_query as provider
    from .native.native_localization_export import _lua_string as quote
    build=provider.verify_build(registration['build']['path'])
    if not stream_build(build):return command
    extra='''assert(Civ6RL_LocalizationRowStream==nil,"stream already installed"); assert(type(box.stream)=="function","stream handoff absent"); local stream=box.stream; Civ6RL_LocalizationRowStream=function(sql,path,nonce) return stream(sql,path,nonce,pid,created,lookup) end; Civ6RL_LocalizationRowStreamIdentity='''+quote(registration['nonce'])+'; '
    return _replace(command,'local rows=Civ6RL_LocalizationQuery(',extra+'local rows=Civ6RL_LocalizationQuery(')


def _chunks(value,maximum):
    _require(type(value)is str and '\0' not in value,'Invalid stream command string')
    encoded=value.encode('ascii')
    _require(0<len(encoded)<=maximum,'Stream command string bound')
    text=encoded.hex()
    return [text[i:i+128] for i in range(0,len(text),128)]


def _json(raw):
    def unique(pairs):
        result={}
        for k,v in pairs:
            _require(k not in result,'Duplicate native row receipt key');result[k]=v
        return result
    return json.loads(raw,object_pairs_hook=unique,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite native receipt')))


def read_rows(client,request,output_path,*,provider_nonce,timeout=None,envelope_sink=None):
    """Publish one stationary diagnostic; retain existing one-writer/timeout rules."""
    from .native.file_client import FileTransportError,_duration
    _require(envelope_sink is None or callable(envelope_sink),'Invalid row envelope sink')
    _require(type(request)is dict and set(request)=={'schema','request','projection','query','process','runtime_identity','nonce','output'}
        and request['schema']=='civ6-host.database_bulk_row_request.v1','Invalid bulk request packet')
    _context(request['process'],request['runtime_identity'])
    nonce=request['nonce'];_require(type(nonce)is str and re.fullmatch('[0-9a-f]{32}',nonce),'Invalid native row nonce')
    _require(type(provider_nonce)is str and re.fullmatch('[0-9a-f]{32}',provider_nonce),'Explicit installed stream identity required')
    projection=request['projection'];_require(type(projection)is dict,'Missing projection')
    _require(request['query']==row_query(**projection),'Noncanonical row SQL')
    native=request['request'];_require(type(native)is dict and set(native)=={'connection','operation','expected_player_id','expected_turn','table_name','offset','limit','after_rowid'}
        and native['connection']=='localization' and native['operation']=='rows'
        and native['table_name']==projection['table_name'] and native['limit']==projection['limit']
        and native['after_rowid']==projection['after_rowid'],'Row request scope differs')
    for key,maximum in [('expected_player_id',63),('expected_turn',1000000),('offset',10000000)]:
        _require(type(native[key])is int and 0<=native[key]<=maximum,'Invalid row '+key)
    path=Path(output_path).absolute()
    _require(path.name==request['output'] and re.fullmatch(r'[0-9]{6}\.rows\.bin',path.name)
        and not path.exists() and path.parent.is_dir() and not path.is_symlink(),'Fresh row-file output required')
    # Hex chunks fit the existing closed ASCII command serializer. No expansion
    # of its general string vocabulary and no arbitrary executable Lua input.
    payload=dict(nonce=nonce,provider_nonce=provider_nonce,sql_hex=_chunks(request['query'],65536),
        path_hex=_chunks(str(path),2047),expected_player_id=native['expected_player_id'],expected_turn=native['expected_turn'])
    duration=_duration(client.timeout if timeout is None else timeout)
    with client._lock:
        client._check('Civ6RL')
        # ContinuedResponseFileClient reserves its general transport nonce in
        # _publish. Keep the row API's reservation separate so that a first
        # submission reaches that guard, while uncertain row calls stay latched
        # even on the ordinary FileClient (whose _publish does not reserve).
        row_used=getattr(client,'_row_stream_used',None)
        if row_used is None:row_used=set();client._row_stream_used=row_used
        if nonce in client._used or nonce in row_used:raise FileTransportError('Row request was already submitted; no replay')
        row_used.add(nonce)
        client._publish('database_row_stream',nonce,bulk=payload)
        def accept(record):
            if record.get('type')!='transport_status':return None
            if record.get('status')!='ok' or record.get('reason')!='database_row_stream_read':
                raise FileTransportError(record.get('reason','Row stream refused'))
            data=record.get('diagnostics')
            if (type(data)is not dict or set(data)!={'native_receipt','provider_nonce','request_id','completion','native_game_core_busy'}
                or data['provider_nonce']!=provider_nonce or data['request_id']!=nonce
                or data['completion']!='read_only_active_connection' or data['native_game_core_busy'] is not False):
                raise FileTransportError('Row stream envelope/source identity differs')
            if (type(record.get('player_id'))is not int or record['player_id']!=native['expected_player_id']
                or type(record.get('turn'))is not int or record['turn']!=native['expected_turn']):
                raise FileTransportError('Row stream player/turn changed')
            raw=data['native_receipt'];_require(type(raw)is str and 0<len(raw)<=8192,'Invalid native row receipt')
            receipt=_json(raw)
            validate_native_row_stream(receipt,process=request['process'],nonce=nonce,runtime_identity=request['runtime_identity'],
                query=request['query'],path=path,**projection)
            if envelope_sink is not None:envelope_sink(record)
            return receipt
        return client._wait(nonce,accept,duration)

"""Repeated active Localization reads with explicit native row-file evidence.

Metadata keeps its real bridge envelopes. Row files have their own native
receipts; this module never manufactures legacy per-page responses. Closed
protocol consistency does not authenticate an installed official producer.
"""
from dataclasses import asdict, dataclass
from pathlib import Path, PureWindowsPath
from types import MappingProxyType
from weakref import WeakSet
import hashlib
import json
import math
import re
import time
import uuid

from .native import database_capture_bundle993 as tables
from .native.database_capture992 import SERIALIZATION, require, validate_request
from .database_row_stream import row_query, validate_native_row_stream, MAX_FILE_BYTES, _source_identity

SCHEMA = 'civ6-host.database_bulk_capture.v1'
_TOKEN = object()
_VERIFIED = WeakSet()
_NAME = re.compile(r'[0-9]{6}\.(request\.json|response\.json|rows\.bin)\Z')
_HASH = re.compile(r'[0-9a-f]{64}\Z')


@dataclass(frozen=True)
class Limits(tables.Limits):
    localization_row_pagination: str = 'rowid_seek_v1'
    row_page_size: int = 8192

    def validate(self):
        super().validate()
        require(type(self.row_page_size) is int and 1 <= self.row_page_size <= 8192, 'Invalid bulk row page size')
        require(self.localization_row_pagination == 'rowid_seek_v1', 'Bulk rows require exact keyset seek')
        require(self.max_bytes <= 512*1024*1024 and self.max_requests <= 20000
                and self.max_tables <= 2048 and self.max_schema_objects <= 10000
                and self.max_rows_total <= 2000000 and self.max_rows_per_table <= 1000000
                and self.timeout_seconds <= 3600 and self.request_timeout_seconds <= 30,
                'Bulk capture exceeds supported bounds')
        return self


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def _load(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            require(k not in result, 'Duplicate capture JSON key')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite capture JSON')))


def _pin(path):
    require(path.is_file() and not path.is_symlink(), 'Missing or linked capture file')
    size = path.stat().st_size
    require(0 < size <= MAX_FILE_BYTES, 'Capture file exceeds byte bound')
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024*1024), b''):
            digest.update(chunk)
    require(path.stat().st_size == size, 'Capture file changed while hashing')
    return dict(path=path.name, bytes=size, sha256=digest.hexdigest())


def _path(directory):
    path = Path(directory).absolute()
    require('..' not in path.parts, 'Capture path contains parent traversal')
    for part in (path, *path.parents):
        require(not part.is_symlink() and not getattr(part, 'is_junction', lambda: False)(), 'Capture path is linked')
    return path


def _file(directory, pin):
    require(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}
            and type(pin['path']) is str and _NAME.fullmatch(pin['path'])
            and type(pin['bytes']) is int and 0 < pin['bytes'] <= MAX_FILE_BYTES
            and type(pin['sha256']) is str and _HASH.fullmatch(pin['sha256']), 'Invalid bulk file reference')
    if not pin['path'].endswith('rows.bin'):
        require(pin['bytes'] <= 2*1024*1024, 'Metadata journal exceeds byte bound')
    path = directory / pin['path']
    require(_pin(path) == pin, 'Bulk capture file changed')
    return path


def _json_file(directory, pin):
    path=_file(directory,pin)
    require(pin['bytes']<=2*1024*1024,'JSON artifact byte bound')
    raw=path.read_bytes()
    require(len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],
            'Parsed bulk JSON bytes changed')
    return _load(raw)


def _row_request(request, columns, process, identity, nonce, filename):
    require(request['connection'] == 'localization' and request['operation'] == 'rows', 'Unknown bulk connection')
    names = [c['name'] for c in columns['columns']]
    projection = dict(table_name=request['table_name'], columns=names,
                      rowid_alias=columns['rowid_alias'], after_rowid=request['after_rowid'],
                      limit=request['limit'])
    query = row_query(**projection)
    return dict(schema='civ6-host.database_bulk_row_request.v1', request=request,
                projection=projection, query=query, process=process, runtime_identity=identity,
                nonce=nonce, output=filename)


def _rows(directory, request, receipt, pin):
    path = _file(directory, pin)
    result = validate_native_row_stream(receipt, process=request['process'], nonce=request['nonce'],
        runtime_identity=request['runtime_identity'], query=request['query'], path=path, **request['projection'])
    require(result['artifact']['sha256'] == pin['sha256'] and result['artifact']['bytes'] == pin['bytes'], 'Native row file association differs')
    return dict(rowid_alias=request['projection']['rowid_alias'], columns=request['projection']['columns'], rows=result['rows'])


def _context(process, identity):
    require(type(process) is dict and set(process)=={'pid','creation_filetime','image_path'}
            and type(process['pid']) is int and 0<process['pid']<2**32
            and type(process['creation_filetime']) is int and 0<process['creation_filetime']<2**64
            and type(process['image_path']) is str and 1<=len(process['image_path'])<=32767 and '\0' not in process['image_path']
            and (PureWindowsPath(process['image_path']).is_absolute() or Path(process['image_path']).is_absolute()),
            'Invalid bulk process identity')
    _source_identity(identity,sqlite=False)


def _main_metadata(result):
    rows=result['databases']
    require(len(rows)==1 and rows[0]['seq']==0 and rows[0]['name']=='main',
            'Attached Localization content cannot be silently omitted')


def _walk(metadata, rows, manifest, limits):
    counter = [0]
    passes = []
    for repeat in range(2):
        result = tables._pass(metadata, 'localization', manifest['expected_player_id'], manifest['expected_turn'],
                             limits, counter, row_exchange=rows, row_page_size=limits.row_page_size)
        require(result['metadata']['databases'] == [dict(seq=0, name='main', file=result['metadata']['databases'][0]['file'])],
                'Attached Localization content cannot be silently omitted')
        passes.append([result])
        if repeat:
            require(tables._semantic(result) == tables._semantic(passes[0][0]), 'Database content changed between complete bulk reads')
    return passes, counter[0]


def capture_bundle(metadata_reader, row_reader, directory, *, process, runtime_identity,
                   expected_player_id, expected_turn, limits=Limits(), clock=time.monotonic):
    """Collect twice; retain submitted requests on error, never retry them.

    row_reader(request, output_path, timeout=...) receives a generated projection,
    exact process/runtime identity and nonce, and returns its native receipt.
    The installed helper and source witness are authenticated by its outer caller.
    """
    limits.validate()
    validate_request(dict(connection='localization', operation='metadata', expected_player_id=expected_player_id, expected_turn=expected_turn))
    # Shape/source identity is checked by the receipt decoder before any result
    # is accepted. Copies here prevent the producer changing the next request.
    process, runtime_identity = _load(_json(process)), _load(_json(runtime_identity))
    _context(process,runtime_identity)
    directory = _path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    manifest = dict(schema=SCHEMA, serialization=SERIALIZATION, status='incomplete',
        atomic_snapshot=False, save_process_scripts_associated=False, native_producer_verified=False,
        connections=['localization'], expected_player_id=expected_player_id, expected_turn=expected_turn,
        process=process, runtime_identity=runtime_identity, limits=asdict(limits), journal=[], passes=[], files=[],
        requests=0, rows_read=0, journal_bytes=0)
    started = clock(); nonces = set(); sequence = [-1]
    def checkpoint():
        raw=_json(manifest)
        require(len(raw)<=16*1024*1024,'Bulk manifest byte bound')
        (directory/'manifest.json').write_bytes(raw)
    def remaining():
        value = limits.timeout_seconds-(clock()-started)
        require(value > 0, 'Bulk capture deadline expired; no request replay')
        return min(value, limits.request_timeout_seconds)
    def add(path):
        pin = _pin(path)
        manifest['journal_bytes'] += pin['bytes']
        require(manifest['journal_bytes'] <= limits.max_bytes, 'Bulk capture total byte bound')
        manifest['files'].append(pin)
        return pin
    def write(name, value):
        with (directory/name).open('xb') as stream:
            stream.write(_json(value))
        return add(directory/name)
    def begin(kind, request):
        remaining(); index=len(manifest['journal'])
        require(index < limits.max_requests, 'Bulk request count bound')
        entry=dict(kind=kind,request=write(f'{index:06d}.request.json',request),response=None)
        if kind=='rows':entry['rows']=None
        manifest['journal'].append(entry);manifest['requests']=len(manifest['journal']);checkpoint()
        return index,entry
    def metadata(request):
        request=validate_request(request);index,entry=begin('metadata',request)
        record=metadata_reader(request,timeout=remaining())
        entry['response']=write(f'{index:06d}.response.json',record)
        result,sequence[0]=tables._envelope(record,request,nonces,sequence[0])
        if request['operation']=='metadata':_main_metadata(result)
        remaining();return result,index
    def rows(request, columns):
        index=len(manifest['journal']);nonce=uuid.uuid4().hex
        packet=_row_request(request,columns,process,runtime_identity,nonce,f'{index:06d}.rows.bin')
        _,entry=begin('rows',packet)
        receipt=row_reader(_load(_json(packet)), directory/packet['output'],timeout=remaining())
        entry['response']=write(f'{index:06d}.response.json',receipt)
        entry['rows']=add(directory/packet['output'])
        require(nonce not in nonces,'Repeated capture nonce');nonces.add(nonce)
        result=_rows(directory,packet,receipt,entry['rows']);remaining();return result,index
    try:
        manifest['passes'],manifest['rows_read']=_walk(metadata,rows,manifest,limits)
        manifest['status']='repeated_reads_agree'
        return manifest
    except BaseException as exc:
        manifest.update(status='failed',error=type(exc).__name__+': '+str(exc)[:1024])
        raise
    finally:
        manifest['elapsed_seconds']=clock()-started;checkpoint()


class _VerifiedBulk:
    __slots__=('directory','_raw','_pin','_files','__weakref__')
    def __init__(self, token, directory, manifest, files):
        require(token is _TOKEN,'Bulk evidence must be verified')
        self.directory=directory;self._raw=_json(manifest);self._pin=tables._pin(directory/'manifest.json')
        self._files=MappingProxyType(dict(files));_VERIFIED.add(self)
    @property
    def manifest(self):return _load(self._raw)
    def dependency_pins(self):
        return tuple((str(self.directory/p['path']),p['sha256'],p['bytes']) for p in [self._pin,*self._files.values()])
    def iter_rows(self, table):
        require(is_verified(self) and tables._pin(self.directory/'manifest.json')==self._pin,'Bulk evidence changed')
        manifest=self.manifest
        require(table in manifest['passes'][0][0]['tables'],'Table is not in verified first pass')
        for index in table['row_pages']:
            entry=manifest['journal'][index]
            require(entry['kind']=='rows','Table points to a metadata event')
            for p in (entry['request'],entry['response'],entry['rows']):
                require(self._files.get(p['path'])==p,'Row dependency is outside verified evidence')
            packet=_json_file(self.directory,entry['request'])
            receipt=_json_file(self.directory,entry['response'])
            yield from _rows(self.directory,packet,receipt,entry['rows'])['rows']
        require(tables._pin(self.directory/'manifest.json')==self._pin,'Bulk manifest changed during row read')


def is_verified(value):return type(value) is _VerifiedBulk and value in _VERIFIED


def _verify_bundle(directory):
    directory=_path(directory).resolve(strict=True);path=directory/'manifest.json'
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 16*1024*1024,'Bulk manifest byte bound')
    before=tables._pin(path);manifest=_load(path.read_bytes())
    expected={'schema','serialization','status','atomic_snapshot','save_process_scripts_associated','native_producer_verified',
        'connections','expected_player_id','expected_turn','process','runtime_identity','limits','journal','passes','files',
        'requests','rows_read','journal_bytes','elapsed_seconds'}
    require(type(manifest) is dict and set(manifest)==expected and manifest['schema']==SCHEMA
            and manifest['serialization']==SERIALIZATION and manifest['status']=='repeated_reads_agree'
            and manifest['connections']==['localization'] and all(manifest[k] is False for k in
                ('atomic_snapshot','save_process_scripts_associated','native_producer_verified')), 'Bulk capture incomplete or overclaims provenance')
    limits=Limits(**manifest['limits']).validate()
    _context(manifest['process'],manifest['runtime_identity'])
    validate_request(dict(connection='localization',operation='metadata',expected_player_id=manifest['expected_player_id'],expected_turn=manifest['expected_turn']))
    require(type(manifest['journal']) is list and 0 < len(manifest['journal']) <= limits.max_requests
            and type(manifest['files']) is list and len(manifest['files'])<=3*limits.max_requests,'Bulk journal bound')
    files={};total=0
    for p in manifest['files']:
        _file(directory,p);require(p['path'] not in files,'Duplicate bulk file');files[p['path']]=p;total+=p['bytes']
        require(total<=limits.max_bytes,'Bulk byte bound')
    require(type(manifest['journal_bytes']) is int and manifest['journal_bytes']==total,'Bulk byte counter differs')
    position=[0];sequence=[-1];nonces=set();consumed=set()
    def entry(kind):
        i=position[0];require(i<len(manifest['journal']),'Bulk journal ended')
        e=manifest['journal'][i];position[0]+=1
        require(type(e) is dict and set(e)==({'kind','request','response','rows'} if kind=='rows' else {'kind','request','response'})
                and e['kind']==kind,'Bulk event kind/order differs')
        values=[]
        for field,suffix in [('request','request.json'),('response','response.json')]+([('rows','rows.bin')] if kind=='rows' else []):
            p=e[field];require(type(p) is dict and p.get('path')==f'{i:06d}.{suffix}'
                and files.get(p['path'])==p and p['path'] not in consumed,'Bulk event association differs')
            consumed.add(p['path']);values.append(_file(directory,p))
        return i,e,values
    def metadata(request):
        i,e,paths=entry('metadata');saved=_json_file(directory,e['request'])
        require(saved==validate_request(request),'Bulk metadata request/order differs')
        record=_json_file(directory,e['response']);result,sequence[0]=tables._envelope(record,request,nonces,sequence[0])
        if request['operation']=='metadata':_main_metadata(result)
        return result,i
    def rows(request,columns):
        i,e,paths=entry('rows');packet=_json_file(directory,e['request'])
        require(type(packet) is dict and type(packet.get('nonce')) is str and re.fullmatch('[0-9a-f]{32}',packet['nonce'])
                and packet['nonce'] not in nonces,'Invalid/repeated bulk nonce')
        expected=_row_request(request,columns,manifest['process'],manifest['runtime_identity'],packet['nonce'],f'{i:06d}.rows.bin')
        require(packet==expected,'Bulk row query/process/runtime/scope differs');nonces.add(packet['nonce'])
        return _rows(directory,packet,_json_file(directory,e['response']),e['rows']),i
    passes,count=_walk(metadata,rows,manifest,limits)
    require(passes==manifest['passes'] and type(manifest['rows_read']) is int and count==manifest['rows_read']
            and type(manifest['requests']) is int and position[0]==len(manifest['journal'])==manifest['requests']
            and consumed==set(files),'Bulk summaries/counters/unconsumed evidence differ')
    require(type(manifest['elapsed_seconds']) in (int,float) and math.isfinite(manifest['elapsed_seconds'])
            and 0<=manifest['elapsed_seconds']<=limits.timeout_seconds,'Bulk elapsed time differs')
    require(tables._pin(path)==before,'Bulk manifest changed during verification')
    return _VerifiedBulk(_TOKEN,directory,manifest,files)


def verify_bundle(directory):return _verify_bundle(directory).manifest

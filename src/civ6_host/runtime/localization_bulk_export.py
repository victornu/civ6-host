"""Explicit bulk-row branch in the existing official Localization export.

The ordinary producer remains the default. A new helper requires the exact
reviewed build, installed transport and source closure; none are substituted.
"""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json

from . import database_bulk_capture as bulk
from . import localization_stream_bridge as stream

TRANSPORT_SHA256='0eaf8eb75ac1665d229282cc4cf0b50482b199f54f361ae1e0a2d8c832d06267'
PROFILE='civ6-host.localization_bulk_export_sources.v1'


def _logical():
    from .native import native_localization_logical_export
    return native_localization_logical_export


def selected_build(reference):
    """Return only the explicitly reviewed stream build, otherwise legacy path."""
    if type(reference) is not dict or reference.get('sha256') not in stream.STREAM_BUILDS.values():return None
    logical=_logical();logical._file(reference)
    logical._require(reference==logical.reference(reference['path']),'Stream build reference differs')
    build=logical.provider.verify_build(reference['path'])
    logical._require(stream.stream_build(build),'Unknown selected row-file build')
    return build


def bridge_source(relative,original,installed):
    """Select a reviewed derivative explicitly by its installed byte identity."""
    if relative!='UI/Civ6RLFileTransport.lua':return original
    if hashlib.sha256(Path(installed).read_bytes()).hexdigest()!=TRANSPORT_SHA256:return original
    candidate=Path(__file__).resolve().parents[3]/'work/localization-stream-bridge/staged01/Civ6RLFileTransport.lua'
    _logical()._require(candidate.is_file() and hashlib.sha256(candidate.read_bytes()).hexdigest()==TRANSPORT_SHA256,
                       'Prepared bulk transport source missing or changed')
    return candidate


def _sources(transport):
    logical=_logical();transport=Path(transport).resolve(strict=True)
    logical._require(transport.name=='Civ6RLFileTransport.lua' and logical.reference(transport)['sha256']==TRANSPORT_SHA256,
                     'Installed row-file transport differs from the qualified candidate')
    from . import database_row_stream
    from .native import file_client,native_localization_query,response_file_client
    sources=[logical.reference(Path(m.__file__)) for m in
        (bulk,stream,database_row_stream,file_client,response_file_client,native_localization_query,logical)]
    sources.append(logical.reference(Path(__file__)))
    sources.append(logical.reference(Path(__file__).resolve().parents[3]/'lua/capture_row_stream.lua'))
    return dict(schema=PROFILE,transport=logical.reference(transport),sources=sources)


def declare_sources(client,build,report):
    if stream.stream_build(build):report['row_files']=_sources(Path(client.inbox).parent/'Civ6RLFileTransport.lua')


def capture_tables(reader,directory,*,client,process,build,registered,identity,remaining,**kwargs):
    logical=_logical()
    if not stream.stream_build(build):return logical.tables.capture_bundle(reader,directory,**kwargs)
    logical._require(callable(getattr(client,'read_database_rows',None)),'Bulk row channel missing; no legacy fallback')
    logical._require(kwargs['connections']==('localization',),'Bulk capture connection differs')
    old=kwargs['limits']
    limits=bulk.Limits(page_size=old.page_size,max_requests=old.max_requests,max_tables=old.max_tables,
        max_rows_per_table=old.max_rows_per_table,max_rows_total=old.max_rows_total,max_schema_objects=old.max_schema_objects,
        max_bytes=old.max_bytes,timeout_seconds=old.timeout_seconds,request_timeout_seconds=old.request_timeout_seconds)
    expected=process.identity()
    def rows(request,path,*,timeout):
        logical._require(process.identity()==expected,'Process changed before native row-file request')
        result=client.read_database_rows(request,path,provider_nonce=registered['nonce'],timeout=min(timeout,remaining(15)))
        logical._require(process.identity()==expected,'Process changed during native row-file request')
        return result
    return bulk.capture_bundle(reader,rows,directory,process=expected,runtime_identity=identity,
        expected_player_id=kwargs['expected_player_id'],expected_turn=kwargs['expected_turn'],limits=limits)


def tables_manifest(manifest,reference,folder,player,turn,*,with_evidence=False):
    """None means this is the unchanged legacy table protocol."""
    logical=_logical()
    if manifest.get('schema')!=bulk.SCHEMA:return None
    directory=Path(reference['path']).resolve().parent
    logical._require(directory==folder/'tables' and Path(reference['path']).name=='manifest.json','Bulk tables location differs')
    verified=bulk._verify_bundle(directory);value=verified.manifest
    logical._require(value==manifest and value['expected_player_id']==player and value['expected_turn']==turn,
                     'Bulk tables player/turn/journal join differs')
    return (directory,verified) if with_evidence else directory


def retained_dependencies(profile,reference):
    """Read explicit immutable producer bytes, never the restored live mod.

    This is artifact consumption only. Live capture still requires the current
    installed sources, and the retained producer identity is never rewritten.
    """
    logical=_logical()
    root=Path(logical.ROOT).resolve()/ 'work'
    manifest_path=logical._file(reference,limit=1024*1024).resolve()
    logical._require(manifest_path.is_relative_to(root),'Retained producer manifest escaped private work')
    report=logical._json(reference,limit=1024*1024)
    logical._require(type(report)is dict and report.get('schema')=='civ6-host.localization-retained-producer-sources.v1'
        and report.get('profile')==profile and type(profile)is dict
        and set(profile)=={'schema','transport','sources'} and profile['schema']==PROFILE,
        'Retained producer profile differs')
    logical._require(type(profile['sources'])is list and 0<len(profile['sources'])<=64,
        'Retained producer source count differs')
    logical._require(type(profile['transport'])is dict
        and profile['transport'].get('sha256')==TRANSPORT_SHA256
        and Path(profile['transport'].get('path','')).name=='Civ6RLFileTransport.lua',
        'Retained producer transport is not the qualified row-file candidate')
    origins=[profile['transport'],*profile['sources']]
    rows=report.get('files')
    logical._require(type(rows)is list and len(rows)==len(origins),'Retained producer file closure differs')
    archive=logical._file(report['producer_archive'],limit=32*1024*1024).resolve()
    pins_path=logical._file(report['producer_pins'],limit=4*1024*1024).resolve()
    logical._require(archive.is_relative_to(root) and pins_path.is_relative_to(root),
        'Retained producer provenance escaped private work')
    pins=logical._json(report['producer_pins'],limit=4*1024*1024)
    dependencies=[reference,report['producer_archive'],report['producer_pins']]
    import zipfile
    with zipfile.ZipFile(archive) as saved:
        for origin,row in zip(origins,rows):
            logical._require(type(row)is dict and set(row)=={'origin','copy','provenance'} and row['origin']==origin,
                'Retained producer origin/order differs')
            copy=row['copy']
            logical._require(type(copy)is dict and all(copy.get(k)==origin.get(k) for k in ('bytes','sha256')),
                'Retained producer copy pin differs')
            path=logical._file(copy,parent=manifest_path.parent/'sources',limit=4*1024*1024)
            logical._require(path.name==origin['sha256']+Path(origin['path']).suffix,
                'Retained producer copy name differs')
            provenance=row['provenance']
            logical._require(type(provenance)is dict,'Retained producer provenance missing')
            kind=provenance.get('kind')
            if kind=='installed_source_archive_member':
                member=provenance.get('member')
                logical._require(type(member)is str and not Path(member).is_absolute()
                    and '..' not in Path(member).parts and saved.namelist().count(member)==1,
                    'Retained producer archive member differs')
                info=saved.getinfo(member)
                logical._require(info.file_size==origin['bytes'] and info.file_size<=4*1024*1024
                    and pins.get(origin['path'])==origin['sha256'],
                    'Retained installed producer pins differ')
                logical._require(hashlib.sha256(saved.read(member)).hexdigest()==origin['sha256'],
                    'Retained producer archive bytes differ')
            elif kind=='retained_installed_transport_after_capture':
                source=provenance.get('source')
                logical._require(origin is origins[0] and origin['sha256']==TRANSPORT_SHA256
                    and type(source)is dict and all(source.get(k)==origin.get(k) for k in ('bytes','sha256')),
                    'Retained installed transport differs')
                backup=logical._file(source,limit=4*1024*1024).resolve()
                logical._require(backup.is_relative_to(root),'Retained transport escaped private work')
                dependencies.append(source)
            else:
                logical._require(kind=='current_file_with_exact_retained_producer_hash'
                    and set(provenance)=={'kind'},'Unknown retained producer provenance')
            dependencies.append(copy)
    return dependencies


def validate_sources(report,verified,build,*,retained_sources=None):
    logical=_logical();manifest=verified.manifest
    if not bulk.is_verified(verified):
        logical._require(retained_sources is None and 'row_files' not in report and not stream.stream_build(build),'Bulk producer cannot use legacy page evidence')
        return
    logical._require(stream.stream_build(build) and report['build']['sha256']==stream.STREAM_BUILDS.get(build['dll']['sha256']),
                     'Bulk table evidence lacks the exact stream build')
    profile=report.get('row_files');logical._require(type(profile)is dict and set(profile)=={'schema','transport','sources'},'Bulk source profile missing')
    transport=Path(profile['transport']['path'])
    logical._require(transport.parent==Path(report['installed_collector']['path']).parent,'Bulk transport belongs to another installed mod')
    if retained_sources is None:
        logical._require(profile==_sources(transport),'Bulk producer sources changed')
    else:
        retained_dependencies(profile,retained_sources)
    logical._require(manifest['process']==report['process'] and manifest['runtime_identity']==report['runtime_identity'],
                     'Bulk table source belongs to another process/runtime')
    for item in (report['comparison'],report.get('materialization',{})):
        logical._require(item.get('capture_schema')==bulk.SCHEMA,'Bulk materialization/comparison kind differs')


def check_live_sources(client,build,report):
    if stream.stream_build(build):
        _logical()._require(report.get('row_files')==_sources(Path(client.inbox).parent/'Civ6RLFileTransport.lua'),
                            'Bulk producer/transport changed across collection')


def extra_dependencies(report,*,retained_sources=None):
    profile=report.get('row_files')
    if retained_sources is not None:
        return retained_dependencies(profile,retained_sources)
    return [] if profile is None else [profile['transport'],*profile['sources']]


def same_profile(first,last):
    if 'row_files' not in first and 'row_files' not in last:return
    logical=_logical()
    logical._require(type(first.get('row_files'))is dict and first['row_files']==last.get('row_files')
        and all(first.get(k)==last.get(k) for k in ('build','helper_module','provider_nonce')),
        'Localization bulk producer/transport changed across the official save')


def capture_proxy(client,inbox,metadata_reader,record,remaining):
    """Keep all metadata and row envelopes in capture994's global order."""
    proxy=SimpleNamespace(inbox=inbox,read_active_database=metadata_reader)
    if hasattr(client,'_lock'):proxy._lock=client._lock
    if callable(getattr(client,'read_database_rows',None)):
        def rows(request,path,*,provider_nonce,timeout):
            return client.read_database_rows(request,path,provider_nonce=provider_nonce,timeout=min(timeout,remaining()),
                envelope_sink=lambda envelope:record('database_row_stream',envelope))
        proxy.read_database_rows=rows
    return proxy

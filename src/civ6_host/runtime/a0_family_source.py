"""Pinned reuse boundary for the shared EXE event codecs, not XP1 gameplay coverage."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from types import MappingProxyType
from .configuration_profiles import _source
from .paths import resource_root
from .resource_resolution import resolve_path
from .source_verification import file_sha256

SOURCE=('work/host-extensions/a0-family-reuse-static/a0-family-reuse-v1.json',
        '0a1d3e3dabb677d7cb14cce1926dabb8360568c69fe97c5d2d61293c0c114e43')


@dataclass(frozen=True)
class A0FamilyProfile:
    record_types_by_kind: object
    record_sizes: object
    source_sha256: str


def source():
    p=_source(SOURCE)
    expected=dict(source_hashes_verified=True,native_execution=False,host_objects_constructed=False,
        static_python_metadata_only=True,branch_count=133,function_node_count=1157,
        admitted_kind_count=156,admitted_branch_count=76,record_type_count=143,
        source_module_count=103,proof_file_hash_count=136)
    if (p['schema']!='civ6_host.a0_family_reuse.static.v1'
            or dict(p['validation'])!=expected):
        raise ValueError('A0 family reuse source boundary differs')
    g=p['initial_group'];kinds=set(g['kind_values'])
    if (len(kinds)!=156 or kinds!={int(k) for k in g['kind_to_record_types']}
            or len(g['branch_ids'])!=76 or len(g['record_type_to_size'])!=143
            or set(g['required_shared_methods'])!={'_dispatch_fields','_enqueue',
                '_enqueue_city_command_started','_enqueue_unit_embarked_state_changed',
                '_finish_counter_neutral_event','_require_no_f391_reentry'}):
        raise ValueError('A0 family codec membership differs')
    for ref in p['references'].values():_source((ref['path'],ref['sha256']))
    return p


def _path(relative):
    path=Path(relative.replace('\\','/'))
    if path.is_absolute() or '..' in path.parts:raise ValueError('A0 source path escaped resources')
    return resolve_path(resource_root()/path)


def source_pins():
    p=source()
    refs=[{'path':SOURCE[0],'sha256':SOURCE[1]},p['source'],
          *p['references'].values(),*p['source_pins'].values()]
    refs.extend({'path':path,'sha256':sha} for sha,paths in p['proof_files'].items() for path in paths)
    pins={}
    for ref in refs:
        path=str(_path(ref['path']))
        if path in pins and pins[path]!=ref['sha256']:raise ValueError('Conflicting A0 source pins')
        pins[path]=ref['sha256']
    return pins


def verify_pinned_files(pins):
    """Stream source identities once per owner, not once per native event."""
    for name,sha in pins.items():
        if file_sha256(Path(name)) != sha:
            raise ValueError('A0 source closure changed: '+name)


def verify_extracted_sources(references):
    from .provenance import _mapping
    rows={r['source'].replace('\\','/'):r for r in _mapping()['sources']}
    package=Path(__file__).resolve().parents[2]
    for ref in references:
        row=rows.get(ref['path'].replace('\\','/'))
        if row is None or row['source_sha256']!=ref['sha256']:
            raise ValueError('A0 extracted source closure differs')
        destination=package/Path(row['destination']).relative_to('src')
        if not destination.resolve().is_relative_to(package):raise ValueError('A0 destination escaped package')
        with destination.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=row['destination_sha256']:
                raise ValueError('A0 installed codec changed: '+str(destination))


def family_profile():
    p=source()
    # Do not parse large disassembly files just to check their identity;
    # codecs retain their existing semantic checks.
    verify_pinned_files(source_pins())
    verify_extracted_sources((p['source'],*p['source_pins'].values()))
    from .native.native_deferred_empty_profile import _ROWS
    g=p['initial_group'];sizes={int(k):v for k,v in g['record_type_to_size'].items()}
    for kind,size in sizes.items():
        expected=g['receiver_rows'][str(kind)];row=_ROWS.get(kind)
        if (row is None or set(row['record_sizes'])!={size}
                or tuple(g['record_type_to_sizes'][str(kind)])!=(size,)
                or any(row[k]!=expected[k] for k in ('event_name','handler_va','handler_body_sha256'))):
            raise ValueError('A0 shared receiver source differs')
    mapping={int(k):frozenset(v) for k,v in g['kind_to_record_types'].items()}
    if set().union(*mapping.values())!=set(sizes):raise ValueError('A0 record membership differs')
    return A0FamilyProfile(MappingProxyType(mapping),MappingProxyType(sizes),SOURCE[1])

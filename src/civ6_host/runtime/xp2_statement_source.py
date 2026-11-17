"""Actual-image statement transport with a headless presentation contract.

The shared EXE record codec is reused; its Base Core query RVAs are not. The
UI dirty-hint query is explicitly excluded, never answered with a fake value.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from types import MappingProxyType

from .execution_images import identity
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE=('work/bbg751-turn-source-scope/war-confirmation/request-session-closure-v3.json',
        '5c76284af04f07fc754dcceffdd499b3769c12f49b198ff628671a721932d566')
PRESENTATION=('work/bbg751-turn-source-scope/war-confirmation/statement-headless-presentation-scope-v1.json',
              'eca8c2da5d761f0cf0b4934c9387d62a37cde64152255a073491da0bdf41cbaa')
CONTACT_SCOPE_COMPATIBILITY = ('evidence/host-xp2-statement-contact-scope-compatibility.json',
                               'fa10cac81476fcd58b23722ca3d77aea83ad154ffd6d1b1e286c70b5b7a26bed')
_CONTACT_SCOPE_HOST = 'src/civ6_host/runtime/native/native_host_events.py'
_CONTACT_SCOPE_HASH = '258173e1ef2e3addf38878064bbd5b2e383989661696e0b0fe2d83fdfee9036c'
KIND=0xfc731e25


@dataclass(frozen=True)
class StatementProfile:
    source_sha256:str=SOURCE[1]
    presentation_sha256:str=PRESENTATION[1]
    record_types_by_kind:object=None
    record_sizes:object=None


PROFILE=StatementProfile(record_types_by_kind=MappingProxyType({KIND:132}),
                         record_sizes=MappingProxyType({132:112}))


def source(*,execution_image):
    identity(execution_image)
    if execution_image.id!='xp2-gamecore-current-092abfbb':
        raise ValueError('Statement runtime is not admitted')
    p=load_pinned_json(resolve_path(resource_root()/SOURCE[0]),SOURCE[1])
    if (p['actual_image']['sha256']!=execution_image.image_sha256
            or p['shared_abi_reference_core_sha256']!=execution_image.reference_core_sha256
            or p['functions']['request_start']['bytes']!=579
            or p['functions']['request_start']['fragment_count']!=3
            or p['message_slots']['0x18']!='0x35c60'):
        raise ValueError('Statement source/runtime correspondence differs')
    from .native.native_diplomacy_statement import NAMES,OPAQUE_KEY
    if {int(row['key'],16) for row in p['common_statement_fields']}!=set(NAMES.values())|{OPAQUE_KEY}:
        raise ValueError('Statement common field set differs from the record codec')
    return p


def source_dependencies(*,execution_image):
    p=source(execution_image=execution_image)
    root=resource_root()
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),dict(path=PRESENTATION[0],sha256=PRESENTATION[1]),
          p['previous_sparse_capture'],p['extractor'],p['shared_host_receiver'],*p['capture_helpers']]
    presentation=load_pinned_json(resolve_path(root/PRESENTATION[0]),PRESENTATION[1])
    host=Path(__file__).resolve().parents[3]
    for row in presentation['consulted_host_source_files']:
        path=host/row['path']
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual == row['sha256']:
            continue
        if (row['path'], actual) != (_CONTACT_SCOPE_HOST, _CONTACT_SCOPE_HASH):
            raise ValueError('Statement presentation scope changed: '+row['path'])
        compatibility = load_pinned_json(resolve_path(root / CONTACT_SCOPE_COMPATIBILITY[0]),
                                         CONTACT_SCOPE_COMPATIBILITY[1])
        if (compatibility['schema'] != 'civ6-host.xp2-statement-contact-scope-compatibility.v1'
                or (compatibility['parent']['path'], compatibility['parent']['sha256']) != PRESENTATION
                or compatibility['source_path'] != row['path']
                or compatibility['previous_sha256'] != row['sha256']
                or compatibility['current_sha256'] != actual
                or compatibility['statement_semantics_changed'] is not False
                or compatibility['checked_other_consulted_sources'] is not True):
            raise ValueError('Statement contact scope compatibility changed')
        refs.append(dict(path=CONTACT_SCOPE_COMPATIBILITY[0], sha256=CONTACT_SCOPE_COMPATIBILITY[1]))
        refs.append(compatibility['contact_source'])
    pins={}
    for row in refs:
        path=resolve_path(root/row['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Statement source dependency changed')
        pins[str(path)]=row['sha256']
    from .xp2_statement_factory import source_dependencies as factory_dependencies
    pins.update(factory_dependencies(execution_image=execution_image))
    return pins


def verify_live(base,read,*,execution_image):
    p=source(execution_image=execution_image)
    for name,body in p['functions'].items():
        for fragment in body['fragments']:
            raw=bytes.fromhex(fragment['raw_hex'])
            if hashlib.sha256(raw).hexdigest()!=fragment['sha256']:
                raise ValueError('Statement body capture is inconsistent')
            if read(base+int(fragment['start_rva'],16),len(raw))!=raw:
                raise ValueError('Statement native instructions changed: '+name)
    for offset,target in p['message_slots'].items():
        address=base+int(p['message_vtable_rva'],16)+int(offset,16)
        if read(address,8)!=(base+int(target,16)).to_bytes(8,'little'):
            raise ValueError('Statement message interface changed')
    return PROFILE

"""The installed PostTourismBomb callback under the owned empty UI receiver."""

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import struct
from types import MappingProxyType

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source
from .execution_images import _PROFILE
from .resource_resolution import resolve_path
from .native.native_host_events import copy_eight_byte_variant
from .xp2_congress_presentation import _empty
from .xp2_feature_reveal_source import _uint32_variant

SOURCE = ('evidence/host-xp2-rock-bands-source-v2.json',
          '1987b122d57f597c89c2d6c70d5eaa2cb632ef0e5cdabd1483ed4ea74591531e')
POLICY = 'source-qualified-empty-presentation-zero-records'
KIND = 0x90cac3df
KINDS = frozenset((KIND,))
CALLBACKS = MappingProxyType({KIND: 0x14c710})
SELECTOR, UNIT, POSITION, RESULT, TOURISM = 0xa1e5a149, 0xf0548bb7, 0x8c468e3c, 0xd6fcf3e4, 0xa1fbc372


@lru_cache(maxsize=1)
def source():
    proof = _source(SOURCE)
    event = proof['event']
    if (proof['schema'] != 'civ6-host.xp2-rock-bands.source.v2'
            or proof['images']['core']['sha256'] != _PROFILE.image_sha256
            or proof['images']['exe']['sha256'] !=
               'd1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe'
            or proof['operation_hash'] != 0x852ce4df or proof['native_execution'] is not False
            or (event['kind'],event['retained_callback_rva'],event['current_callback_rva']) !=
               (KIND,CALLBACKS[KIND],0x14be00)
            or tuple(event['records']) != (0x3f,0x40) or event['record_size'] != 112
            or event['internal_dispatch_before_host'] is not True
            or event['public_movie_disabled_in_lan'] is not True
            or event['public_result_popup_enabled_in_lan'] is not True
            or event['metadata_queries_omitted_only_with_empty_receivers'] is not True
            or event['fields'] != {hex(SELECTOR):3,hex(UNIT):1024,hex(POSITION):0,
                                    hex(RESULT):2,hex(TOURISM):2}):
        raise ValueError('Rock concert source contract differs')
    return proof


def source_dependencies():
    proof = source()
    references = [dict(path=SOURCE[0],sha256=SOURCE[1]), *proof['images'].values(),
                  *proof['ui'],proof['shared_dispatch_source'],
                  proof['listeners']['bbg_modinfo'],*proof['listeners']['bbg_lua']]
    pins = {str(source_path(row['path']).resolve()):row['sha256'] for row in references}
    module = Path(__file__).resolve()
    pins[str(module)] = sha256(module.read_bytes()).hexdigest()
    verify_pinned_files(pins)
    return pins


def source_path(name):
    path = Path(name)
    return resolve_path(path if path.is_absolute() else _path(name))


def core_spans():
    proof = source()
    for name in ('0x74eac0','0x5fb580'):
        yield from proof['operation_bodies'][name]


def verify_live(core, read):
    if getattr(core,'_civ6_host_execution_image',None) is not _PROFILE:
        raise ValueError('Rock concert requires the installed Gathering Storm image')
    for row in core_spans():
        raw = read(core._handle+row['rva'],row['bytes'])
        if type(raw) is not bytes or len(raw)!=row['bytes'] or sha256(raw).hexdigest()!=row['sha256']:
            raise ValueError('Rock concert live producer differs')


def bind_owner(backend, core, read):
    backend.check_thread()
    if (backend.core is not core or backend.stage!='prepared' or backend.poisoned or backend.destroyed
            or backend.load_abi.core_sha256!=XP2_CORE_SHA256):
        raise ValueError('Rock concert requires its prepared XP2 owner')
    source_dependencies()
    verify_live(core,read)
    backend._xp2_rock_concert_source_identity=(id(core),core._handle,id(_PROFILE),SOURCE[1])


def validate_empty_owner(owner):
    from .a0_family_service import A0FamilyService
    from .a0_foundation_events import require_borrow
    if type(owner) is not A0FamilyService:
        raise ValueError('Rock concert requires the composed A0 owner')
    owner._check()
    backend=require_borrow(owner).owner
    if (owner.active_kind!=KIND or owner._foundation_backend is not backend
            or backend.load_abi.core_sha256!=XP2_CORE_SHA256
            or owner.arguments.reader.core_sha256!=XP2_CORE_SHA256
            or owner.deferred.cache_core_sha256!=XP2_CORE_SHA256
            or backend.core is not owner.deferred.core or backend.host is not owner.arguments.host
            or not _empty(owner.empty_receiver_state) or not _empty(owner._receiver_profile)
            or type(owner.entity_listener_count) is not int or owner.entity_listener_count!=0
            or owner.dynamic_event_registration_present is not False
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or owner.host_notification_counter or owner.host_metadata_counter
            or getattr(backend,'_xp2_rock_concert_source_identity',None) !=
               (id(backend.core),backend.core._handle,id(_PROFILE),SOURCE[1])):
        raise ValueError('Rock concert receiver, hooks, source or notification scope differs')
    return POLICY


@dataclass(frozen=True)
class Concert:
    player_id: int
    unit_id: int
    x: int
    y: int
    result: int
    tourism: int

    def to_admin(self):
        return dict(event_name='PostTourismBomb',player_id=self.player_id,unit_id=self.unit_id,
                    x=self.x,y=self.y,result=self.result,tourism=self.tourism,
                    borrowed_pointers_retained=False,public_visibility_qualified=False)


def decode_fields(kind, fields, read):
    source()
    if type(kind) is not int or kind!=KIND or type(fields) is not dict or set(fields)!={SELECTOR,UNIT,POSITION,RESULT,TOURISM}:
        raise ValueError('Rock concert argument shape differs')
    if _uint32_variant(fields[SELECTOR],3,'concert selector')!=0:
        raise ValueError('Rock concert selector differs')
    unit=copy_eight_byte_variant(fields[UNIT],read,expected_tag=1024)
    position=copy_eight_byte_variant(fields[POSITION],read,expected_tag=0)
    owner,entity_type,identifier=struct.unpack('<HHI',unit)
    if entity_type!=1 or owner>=64 or identifier==0xffffffff:
        raise ValueError('Rock concert unit descriptor differs')
    values=[_uint32_variant(fields[key],2,'concert result') for key in (RESULT,TOURISM)]
    values=[value if value<2**31 else value-2**32 for value in values]
    return Concert(owner,identifier,*struct.unpack('<ii',position),*values)


def record_callback(owner, fields):
    """Attach an actual callback to an already executing public concert."""
    validate_empty_owner(owner)
    pending=getattr(owner,'_xp2_requested_rock_concert',None)
    if pending is None:
        return
    if (fields.player_id,fields.unit_id,fields.x,fields.y)!=pending['identity']:
        raise RuntimeError('Native concert belongs to another unit or position')
    if pending['event'] is not None:
        raise RuntimeError('Native concert result repeated within one command')
    pending['event']=fields


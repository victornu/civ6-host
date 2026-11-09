"""Two sourced Congress notices on the shared owned empty A0 receiver.

The Core producer remains unchanged. Neither notice is a Stage/Finished event,
ballot acknowledgement or public observation. No native record is synthesized.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from .configuration_profiles import XP2_CORE_SHA256, _source
from .a0_family_source import _path, verify_pinned_files
from .a0_policy_unlock_current import _require_image
from .xp2_feature_reveal_source import _uint32_variant, _read_exact
from .xp2_wmd_fallout_source import _fragments
from .xp2_congress_presentation import _empty

SOURCE = ('work/trade-common-client/congress-unary-source-staging/source.json',
          '597d4c8fd2fe871ab513623c2cb9c34e5a84c904f8881beecb31cc56e705dd49')
POLICY = 'source-qualified-empty-presentation-zero-records'
EMERGENCY_READY, SPECIAL_SESSION = 0x54e4377b, 0xfdc05d8b
KINDS = frozenset((EMERGENCY_READY,SPECIAL_SESSION))
EXCLUDED = frozenset((0x697de853,0x30810688))
SELECTOR_KEY, VALUE_KEY = 0xa1e5a149,0xd6fcf3e4
# Historical shared registry identity stays distinct from current EXE targets.
CALLBACKS = MappingProxyType({EMERGENCY_READY:0x159b40,SPECIAL_SESSION:0x159f00})
CURRENT_CALLBACKS = MappingProxyType({EMERGENCY_READY:0x159230,SPECIAL_SESSION:0x1595f0})
EVENT_NAMES = MappingProxyType({EMERGENCY_READY:'WorldCongressEmergencyReady',
                               SPECIAL_SESSION:'WorldCongressSpecialSessionBeingCalled'})
_CORE_SHA = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
_EXE_SHA = 'd1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe'
_NORMALIZER_SHA = '29349dfc3a1465253454f320a4d751d0c169ca35ec1f97a6410b8f38edd3aa6d'
_CORE_ROOTS = ('0x3bfb40','0x5fc4f0','0x99fee0','0x9a0000')
_EXE_ROOTS = ('0x159230','0x1595f0','0xc7a60','0xd5690','0x123dc0',
              '0xc7b20','0xd56f0','0x123fb0')
_NORMALIZER_ROOTS = ('0x1c90e0','0x143ce0','0xdb810','0xc4930')
_ROUTES = MappingProxyType({EMERGENCY_READY:(307,'0x123dc0','0xc7a60','0xd5690','0x150d77'),
                           SPECIAL_SESSION:(308,'0x123fb0','0xc7b20','0xd56f0','0x150d98')})


def _selected_fragments(proof,image,roots):
    selected = dict(bodies={image:{key:proof['bodies'][image][key] for key in roots}})
    yield from _fragments(selected,image)


def _verify(p):
    c = p['shared_contract']
    if (p['schema'] != 'civ6-host.xp2-congress-unary-presentation-matrix.static.v1'
            or p['scope'] != dict(static_only=True,native_execution=False,process_memory_read=False,
                runtime_modified=False,runtime_admission_performed=False)
            or p['images']['core']['sha256'] != _CORE_SHA or p['images']['exe']['sha256'] != _EXE_SHA
            or set(p['qualified_source_kinds']) != {hex(k) for k in KINDS}
            or set(p['not_admitted_kinds']) != {hex(k) for k in EXCLUDED}
            or p['parents']['current_normalizer_empty_dispatch']['sha256'] != _NORMALIZER_SHA
            or c['policy'] != POLICY or c['source_qualified_builder_rva'] != '0x5fc4f0'
            or set(c['fields']) != {hex(SELECTOR_KEY),hex(VALUE_KEY)}
            or c['fields'][hex(SELECTOR_KEY)] != dict(tag=3,selector=0)
            or c['fields'][hex(VALUE_KEY)]['tag'] != 2
            or tuple(c['fields'][hex(VALUE_KEY)]['domain']) != (0,0xffffffff)
            or (c['normalizer_rva'],c['callback_dispatch_rva'],c['receiver_dispatch_rva']) !=
               ('0x1c90e0','0x143ce0','0xdb810')
            or c['explicit_normalizer_return'] != 0 or c['native_queries'] != 0 or c['records_enqueued'] != 0
            or c['Core_internal_dispatch_preserved'] is not True
            or c['notification_scope_and_FIFO_preserved'] is not True
            or c['receiver_guards'] != dict(nonnull_state=True,subscriber_count=0,active=False,dirty=False,
                pre_hook=None,post_hook=None,producer_hook=None,normalizer_transform_present=False,
                writer_metadata_callback_present=False)):
        raise ValueError('Congress notice source header differs')
    for kind,(typ,writer,setup,handler,registration) in _ROUTES.items():
        row = p['routes'][hex(kind)]
        incoming = row['input']
        if (row['kind'] != hex(kind) or row['name'] != 'GameCoreEvent::'+EVENT_NAMES[kind]
                or row['callback_rva'] != hex(CURRENT_CALLBACKS[kind])
                or (row['record_type'],row['record_size'],row['writer_rva'],row['setup_rva'],row['handler_rva']) !=
                   (typ,96,writer,setup,handler)
                or row['registry']['start_rva'] != registration
                or row['registry']['callback_rva'] != row['callback_rva']
                or row['row_rva'] != hex(0x12c78b0+typ*48) or row['metadata_flag'] != 6
                or (row['callback_bytes'],row['writer_bytes']) != (249,495)
                or tuple(row['handler_calls']) != ('call 0x14098abe0','call 0x1400db810','call 0x14098ac10')
                or row['empty_receiver_eligible_given_producer'] is not True
                or row['producer_status'] != 'source-qualified-current-generic-builder'
                or p['current_producer_matrix'][hex(kind)]['body'] != '0x3bfb40'
                or incoming['normalized_marker'] != '0x6447c33d'
                or (incoming['D6_offset'],incoming['payload_size'],incoming['payload_value_offset']) != (80,8,84)
                or tuple(incoming['value_domain']) != (0,0xffffffff) or incoming['extra_getters'] is not False):
            raise ValueError('Congress notice producer/callback route differs')
    for kind in EXCLUDED:
        if p['routes'][hex(kind)]['producer_status'] != 'unresolved-native-A0-producer':
            raise ValueError('Congress notice unresolved producer scope differs')
    tuple(_selected_fragments(p,'core',_CORE_ROOTS))
    tuple(_selected_fragments(p,'exe',_EXE_ROOTS))
    return p


@lru_cache(maxsize=1)
def source():
    p = _verify(_source(SOURCE))
    parent = p['parents']['current_normalizer_empty_dispatch']
    normalizer = _source((parent['path'],parent['sha256']))
    if any(normalizer['images'][key]['sha256'] != p['images'][key]['sha256'] for key in ('core','exe')):
        raise ValueError('Congress notice normalizer image differs')
    verify_pinned_files({row['path']:row['sha256'] for row in p['images'].values()})
    for image,fragments in (('core',_selected_fragments(p,'core',_CORE_ROOTS)),
                            ('exe',_selected_fragments(p,'exe',_EXE_ROOTS)),
                            ('exe',_selected_fragments(normalizer,'exe',_NORMALIZER_ROOTS))):
        with Path(p['images'][image]['path']).open('rb') as stream:
            for _,offset,raw in fragments:
                stream.seek(offset)
                if stream.read(len(raw)) != raw:
                    raise ValueError('Congress notice installed source bytes differ')
    for row in p['spans']:
        if not any(row['label'].startswith(hex(k)+' ') for k in KINDS):continue
        raw = bytes.fromhex(row['raw_hex'])
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Congress notice registration source differs')
        with Path(p['images'][row['image']]['path']).open('rb') as stream:
            stream.seek(int(row['file_offset'],16))
            if stream.read(len(raw)) != raw:
                raise ValueError('Congress notice installed registration differs')
    return p


def source_dependencies():
    p = source()
    refs = [dict(path=str(_path(SOURCE[0]).resolve()),sha256=SOURCE[1]),
            *p['images'].values(),*p['parents'].values(),p['listeners']['bbg_modinfo'],
            *p['listeners']['bbg_lua_files'],p['listeners']['official_ui']['source']]
    pins = {str(Path(row['path']).resolve()):row['sha256'] for row in refs}
    verify_pinned_files(pins)
    return pins


def core_fragments():
    for rva,_,raw in _selected_fragments(source(),'core',_CORE_ROOTS):yield rva,raw


def _execution(core):
    image = getattr(core,'_civ6_host_execution_image',None)
    _require_image(image)
    if Path(image.path).resolve() != Path(source()['images']['core']['path']).resolve():
        raise ValueError('Congress notice current image path differs')
    return image


def bind_owner(backend,core,read):
    backend.check_thread()
    if (backend.core is not core or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or backend.stage != 'prepared' or backend.poisoned or backend.destroyed
            or type(core._handle) is not int or core._handle <= 0):
        raise ValueError('Congress notice requires its exact prepared XP2 owner')
    image = _execution(core)
    source_dependencies()
    for rva,raw in core_fragments():
        if _read_exact(read,core._handle+rva,len(raw)) != raw:
            raise ValueError('Congress notice live Core source differs')
    backend._xp2_congress_notice_source_identity = (
        id(core),core._handle,XP2_CORE_SHA256,id(image),_CORE_SHA,SOURCE[1])
    return SOURCE[1]


def validate_empty_owner(owner):
    from .a0_family_service import A0FamilyService
    from .a0_foundation_events import require_borrow
    if type(owner) is not A0FamilyService:
        raise ValueError('Congress notice requires the real shared A0 owner')
    owner._check()
    backend = require_borrow(owner).owner
    image = _execution(backend.core)
    if (type(owner.active_kind) is not int or owner.active_kind not in KINDS
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or owner.arguments.reader.core_sha256 != XP2_CORE_SHA256
            or owner.deferred.cache_core_sha256 != XP2_CORE_SHA256
            or owner._foundation_backend is not backend or backend.core is not owner.deferred.core
            or backend.host is not owner.arguments.host
            or not _empty(owner.empty_receiver_state) or not _empty(owner._receiver_profile)
            or type(owner.entity_listener_count) is not int or owner.entity_listener_count != 0
            or owner.dynamic_event_registration_present is not False
            or owner.normalizer_transform_present is not False or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or getattr(backend,'_xp2_congress_notice_source_identity',None) !=
               (id(backend.core),backend.core._handle,XP2_CORE_SHA256,id(image),_CORE_SHA,SOURCE[1])):
        raise ValueError('Congress notice empty receiver or owner source changed')
    return POLICY


@dataclass(frozen=True)
class NoticeFields:
    kind: int
    value: int

    def to_admin(self):
        return dict(event_name=EVENT_NAMES[self.kind],selector=0,source_d6_value=self.value,
                    gameplay_getters_required=False,congress_stage_or_finished=False,ballot_acknowledgement=False)


def decode_fields(kind,fields,read):
    source()
    if (type(kind) is not int or kind not in KINDS or type(fields) is not dict
            or any(type(key) is not int for key in fields) or set(fields) != {SELECTOR_KEY,VALUE_KEY}):
        raise ValueError('Congress notice argument shape differs')
    selector = _uint32_variant(fields[SELECTOR_KEY],3,'selector')
    value = _uint32_variant(fields[VALUE_KEY],2,'value')
    if selector != 0:raise ValueError('Congress notice selector differs from its producer')
    return NoticeFields(kind,value)

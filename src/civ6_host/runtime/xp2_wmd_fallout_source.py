"""WMDFalloutChanged on the exact current XP2 owned empty receiver.

The native producer and its internal dispatch run unchanged. The host copies
the borrowed coordinate pair synchronously, then omits only the source-proven
empty EXE presentation route. No record, undefined padding or public fallout
observation is synthesized.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from .configuration_profiles import XP2_CORE_SHA256, _source
from .a0_family_source import _path, verify_pinned_files
from .a0_policy_unlock_current import _require_image
from .xp2_feature_reveal_source import _uint32_variant, _read_exact
from .native.native_host_events import copy_eight_byte_variant

SOURCE = ('work/trade-common-client/post-congress-a0-8e5e1e95-staging/source.json',
          '29349dfc3a1465253454f320a4d751d0c169ca35ec1f97a6410b8f38edd3aa6d')
SCALAR_SOURCE = ('work/trade-common-client/post-congress-a0-8e5e1e95-staging/scalar-domain-supplement.json',
                 'd9fe174b7ae20f57874d255bfc05f4bae8cd43ae0df7d46c93072d98345c32f1')
POLICY = 'source-qualified-empty-presentation-zero-records'
KIND = 0x8e5e1e95
KINDS = frozenset((KIND,))
# Registry identity is historical; the current EXE registration is separately
# pinned at14ff23 ->159050. Do not overwrite the historical registry wholesale.
CALLBACKS = MappingProxyType({KIND: 0x159960})
SELECTOR_KEY, POSITION_KEY, VALUE_KEY, STATE_KEY = 0xa1e5a149, 0x8c468e3c, 0xd6fcf3e4, 0xa1fbc372
_CORE_SHA = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
_EXE_SHA = 'd1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe'
_EMPTY_STATE = MappingProxyType(dict(observer_registered=False,
    state_pointer_nonnull=True, pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0))
_ROOTS = dict(core=frozenset(('0x5fac20','0x1ee360','0x11f610','0x99fee0','0x9a0000','0x5fb580','0x5fcde0')),
             exe=frozenset(('0x159050','0x138cf0','0xd1120','0xda1f0','0xdb810','0xc4930','0x1c90e0','0x143ce0')))


def _fragments(proof, image):
    for body in proof['bodies'][image].values():
        for fragment in body['fragments']:
            raw = bytes.fromhex(fragment['raw_hex'])
            if (fragment['dir64_relocations'] or len(raw) != fragment['length']
                    or hashlib.sha256(raw).hexdigest() != fragment['sha256']
                    or int(fragment['end_rva_exclusive'],16)-int(fragment['start_rva'],16) != len(raw)):
                raise ValueError('WMDFalloutChanged source span or relocation differs')
            yield int(fragment['start_rva'],16), int(fragment['file_offset'],16), raw


def _verify(proof):
    route, contract = proof['route'], proof['contract']
    if (proof['schema'] != 'civ6-host.xp2-wmd-fallout-changed.source.v1'
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or proof['runtime_modified'] is not False
            or proof['images']['core']['sha256'] != _CORE_SHA
            or proof['images']['exe']['sha256'] != _EXE_SHA
            or {key:frozenset(value) for key,value in proof['bodies'].items()} != _ROOTS
            or (route['kind'],route['name'],route['historical_registry_callback_rva'],
                route['current_callback_rva'],route['writer_rva'],route['record_type'],route['record_size'],
                route['row_static_rva'],route['setup_rva'],route['handler_rva'],route['dispatch_rva']) !=
               ('0x8e5e1e95','GameCoreEvent::WMDFalloutChanged','0x159960','0x159050',
                '0x138cf0',200,96,'0x12c9e30','0xd1120','0xda1f0','0xdb810')
            or route['callback_gameplay_queries'] != 0 or route['metadata_flag'] != 0
            or route['normalizer']['callback_uses_A1'] is not False
            or route['normalizer']['normalized_offsets'] != dict(position=72,D6=80,A1=84)
            or contract['policy'] != POLICY or contract['kind'] != KIND
            or (contract['producer_rva'],contract['builder_rva']) != ('0x1ee360','0x5fac20')
            or (contract['selector'],contract['D6'],tuple(contract['A1_domain'])) != (0,0,(0,255))
            or contract['field_tags'] != {hex(SELECTOR_KEY):3,hex(POSITION_KEY):0,
                                         hex(VALUE_KEY):2,hex(STATE_KEY):2}
            or contract['normalizer_return'] != 0 or contract['internal_dispatch_before_host'] is not True
            or contract['native_queries_required'] != 0 or contract['records_enqueued'] != 0
            or contract['administrative_only'] is not True or contract['public_visibility_qualified'] is not False
            or contract['empty_receiver'] != dict(state_pointer_nonnull=True,subscriber_count=0,
                active_flag=False,dirty_flag=False,pre_hook=None,post_hook=None,producer_hook=None,
                normalizer_transform_present=False,writer_metadata_callback_present=False)):
        raise ValueError('WMDFalloutChanged source header differs')
    for image in _ROOTS:
        tuple(_fragments(proof,image))
    return proof


def _verify_scalar_source(proof, supplement):
    change = supplement['admission_change']
    domains = change['fields']
    expected_domain = dict(type='exact uint32 bit pattern',minimum=0,maximum=0xffffffff)
    if (supplement['schema'] != 'civ6-host.xp2-wmd-fallout-changed.scalar-domain-supplement.v1'
            or supplement['native_execution'] is not False or supplement['process_memory_read'] is not False
            or supplement['runtime_modified'] is not False
            or supplement['parent']['sha256'] != SOURCE[1]
            or Path(supplement['parent']['path']).resolve() != _path(SOURCE[0]).resolve()
            or supplement['images'] != proof['images'] or supplement['kind'] != KIND
            or supplement['policy'] != POLICY or tuple(change['only_changed_fields']) != ('D6','A1')
            or change['selector_remains'] != 0 or change['position_blob_and_flags_unchanged'] is not True
            or change['all_other_field_and_owner_guards_unchanged'] is not True
            or set(domains) != {hex(VALUE_KEY),hex(STATE_KEY)}
            or any(row['variant_tag'] != 2 or row['new_domain'] != expected_domain for row in domains.values())
            or domains[hex(VALUE_KEY)]['callback_conversion'] != 'D6 != 0'
            or domains[hex(STATE_KEY)]['callback_consumption'] != 'not read by callback159050'):
        raise ValueError('WMDFalloutChanged scalar ABI source differs')
    # The supplement selects instructions within the same already-pinned full
    # bodies; it does not admit another producer, image, getter or owner path.
    for group in supplement['instructions']:
        body = proof['bodies'][group['image']][group['body_rva']]
        if (group['complete_body_bytes'],group['complete_body_sha256']) != (body['length'],body['sha256']):
            raise ValueError('WMDFalloutChanged scalar ABI body differs')
        fragments = tuple(_fragments(dict(bodies={group['image']:{group['body_rva']:body}}),group['image']))
        for instruction in group['instructions']:
            raw = bytes.fromhex(instruction['raw_hex'])
            rva, offset = int(instruction['rva'],16),int(instruction['file_offset'],16)
            if (len(raw) != instruction['bytes'] or hashlib.sha256(raw).hexdigest() != instruction['sha256']
                    or not any(start <= rva and rva+len(raw) <= start+len(code)
                        and offset == file_offset+rva-start and code[rva-start:rva-start+len(raw)] == raw
                        for start,file_offset,code in fragments)):
                raise ValueError('WMDFalloutChanged scalar ABI instruction differs')
    return supplement


@lru_cache(maxsize=1)
def source():
    proof = _verify(_source(SOURCE))
    _verify_scalar_source(proof,_source(SCALAR_SOURCE))
    verify_pinned_files({r['path']:r['sha256'] for r in proof['images'].values()})
    for image in _ROOTS:
        with Path(proof['images'][image]['path']).open('rb') as stream:
            for _, offset, raw in _fragments(proof,image):
                stream.seek(offset)
                if stream.read(len(raw)) != raw:
                    raise ValueError('WMDFalloutChanged installed source bytes differ')
    for span in proof['spans']:
        raw = bytes.fromhex(span['raw_hex'])
        if len(raw) != span['bytes'] or hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('WMDFalloutChanged registration span differs')
        with Path(proof['images'][span['image']]['path']).open('rb') as stream:
            stream.seek(int(span['file_offset'],16))
            if stream.read(len(raw)) != raw:
                raise ValueError('WMDFalloutChanged installed registration differs')
    return proof


def source_dependencies():
    proof = source()
    refs = [dict(path=str(_path(SOURCE[0]).resolve()),sha256=SOURCE[1]),
            dict(path=str(_path(SCALAR_SOURCE[0]).resolve()),sha256=SCALAR_SOURCE[1]),
            *proof['images'].values(),*proof['parents'].values(),
            proof['listeners']['bbg_modinfo'],*proof['listeners']['bbg_lua']]
    pins = {str(Path(r['path']).resolve()):r['sha256'] for r in refs}
    verify_pinned_files(pins)
    return pins


def core_fragments():
    for rva, _, raw in _fragments(source(),'core'):
        yield rva, raw


def _execution(core):
    image = getattr(core,'_civ6_host_execution_image',None)
    _require_image(image)
    if Path(image.path).resolve() != Path(source()['images']['core']['path']).resolve():
        raise ValueError('WMDFalloutChanged current image path differs')
    return image


def bind_owner(backend, core, read):
    backend.check_thread()
    if (backend.core is not core or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or backend.stage != 'prepared' or backend.poisoned or backend.destroyed
            or type(core._handle) is not int or core._handle <= 0):
        raise ValueError('WMDFalloutChanged requires its exact prepared XP2 owner')
    image = _execution(core)
    source_dependencies()
    for rva, raw in core_fragments():
        for offset in range(0,len(raw),4096):
            chunk = raw[offset:offset+4096]
            if _read_exact(read,core._handle+rva+offset,len(chunk)) != chunk:
                raise ValueError('WMDFalloutChanged live Core source differs')
    backend._xp2_wmd_fallout_source_identity = (
        id(core),core._handle,XP2_CORE_SHA256,id(image),_CORE_SHA,SOURCE[1],SCALAR_SOURCE[1])
    return SOURCE[1]


def validate_empty_owner(owner):
    from .a0_family_service import A0FamilyService
    from .a0_foundation_events import require_borrow
    if type(owner) is not A0FamilyService:
        raise ValueError('WMDFalloutChanged requires the real shared A0 owner')
    owner._check()
    backend = require_borrow(owner).owner
    image = _execution(backend.core)
    if (type(owner.active_kind) is not int or owner.active_kind not in KINDS
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or owner.arguments.reader.core_sha256 != XP2_CORE_SHA256
            or owner.deferred.cache_core_sha256 != XP2_CORE_SHA256
            or owner._foundation_backend is not backend or backend.core is not owner.deferred.core
            or backend.host is not owner.arguments.host
            or owner.empty_receiver_state != dict(_EMPTY_STATE)
            or owner._receiver_profile != dict(_EMPTY_STATE)
            or any(type(owner.empty_receiver_state[k]) is not type(v) for k,v in _EMPTY_STATE.items())
            or type(owner.entity_listener_count) is not int or owner.entity_listener_count != 0
            or owner.dynamic_event_registration_present is not False
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or getattr(backend,'_xp2_wmd_fallout_source_identity',None) !=
               (id(backend.core),backend.core._handle,XP2_CORE_SHA256,id(image),_CORE_SHA,SOURCE[1],SCALAR_SOURCE[1])):
        raise ValueError('WMDFalloutChanged empty receiver or owner source changed')
    return POLICY


@dataclass(frozen=True)
class FalloutFields:
    position: tuple
    value: int
    state: int

    def to_admin(self):
        return dict(event_name='GameCoreEvent::WMDFalloutChanged',coordinate=list(self.position),
            source_d6_value=self.value,exe_boolean=bool(self.value),source_a1_state=self.state,
            a1_consumed_by_exe_callback=False,borrowed_position_payload_copied=True,
            borrowed_pointer_retained=False,undefined_record_padding_synthesized=False)


def decode_fields(kind, fields, read):
    source()
    if (type(kind) is not int or kind != KIND or type(fields) is not dict
            or any(type(k) is not int for k in fields)
            or set(fields) != {SELECTOR_KEY,POSITION_KEY,VALUE_KEY,STATE_KEY}):
        raise ValueError('WMDFalloutChanged argument shape differs')
    selector = _uint32_variant(fields[SELECTOR_KEY],3,'selector')
    # Both scalars preserve the full tag-2 DWORD. The observed caller's zero
    # D6 and byte A1 are witness values, not limits of this shared native ABI.
    value = _uint32_variant(fields[VALUE_KEY],2,'value')
    state = _uint32_variant(fields[STATE_KEY],2,'state')
    if selector != 0:
        raise ValueError('WMDFalloutChanged arguments differ from the admitted native producer')
    raw = fields[POSITION_KEY]
    if (type(raw) is not bytes or len(raw) != 24 or struct.unpack_from('<H',raw)[0] != 0
            or struct.unpack_from('<II',raw,16) != (8,0x21000001)):
        raise ValueError('WMDFalloutChanged borrowed coordinate header differs')
    pair = copy_eight_byte_variant(raw,lambda address,size:_read_exact(read,address,size),expected_tag=0)
    return FalloutFields(struct.unpack('<ii',pair),value,state)

"""Congress stage/finished presentation on the shared owned A0 continuation.

Core performs its internal dispatch and Congress work before this boundary.
Only the exact empty subscriber path is omitted; any observer or hook refuses.
No getter, native record, notification or public voting action is synthesized.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import struct
from types import MappingProxyType

from .configuration_profiles import XP2_CORE_SHA256, _source
from .a0_family_source import _path, verify_pinned_files

SOURCE = ('work/trade-common-client/congress-presentation-source.json',
          'a440f46414b1887f3d2d669853a4cc594f56881dca54d1c8551c161acb527e4c')
PREVIOUS_SOURCE = ('work/trade-common-client/congress-followup-source.json',
                   '4198495bbd2b0150a3a06f0ed21cb1c4c22ea8cb59d4a04de677f1b081378b30')
POLICY = 'source-qualified-empty-presentation-zero-records'
STAGE1, STAGE2, STAGE3, FINISHED = 0xDABC2341, 0x43B572FB, 0x34B2426D, 0x6ED99EE8
KINDS = frozenset((STAGE1, STAGE2, STAGE3, FINISHED))
SELECTOR_KEY, VALUE_KEY = 0xA1E5A149, 0xD6FCF3E4
# Shared A0 dispatch uses the retained registry identity. Installed EXE targets
# are independently pinned and are not claimed to have the same RVA.
CALLBACKS = MappingProxyType({STAGE1: 0x15A000, STAGE2: 0x15A100,
                              STAGE3: 0x15A200, FINISHED: 0x159C40})
CURRENT_CALLBACKS = MappingProxyType({STAGE1: 0x1596F0, STAGE2: 0x1597F0,
                                      STAGE3: 0x1598F0, FINISHED: 0x159330})
# kind: record type, callback registration, writer, name setup, row setup, handler
_ROUTES = MappingProxyType({
    STAGE1: (300, 0x150CB1, 0x123020, 0xDD506, 0xC7460, 0xD5390),
    STAGE2: (301, 0x150CD2, 0x123210, 0xDD51C, 0xC7520, 0xD53F0),
    STAGE3: (302, 0x150CF3, 0x123400, 0xDD532, 0xC75E0, 0xD5450),
    FINISHED: (304, 0x150D14, 0x1239E0, 0xDD55E, 0xC7820, 0xD5570)})
EVENT_NAMES = MappingProxyType({STAGE1: 'WorldCongressStage1',
    STAGE2: 'WorldCongressStage2', STAGE3: 'WorldCongressStage3',
    FINISHED: 'WorldCongressFinished'})
_CORE_SHA = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
_EXE_SHA = 'd1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe'
_EMPTY_STATE = MappingProxyType(dict(observer_registered=False,
    state_pointer_nonnull=True, pre_hook=None, post_hook=None,
    subscriber_count=0, state_flags=0))
_CORE_SPANS = (
    (0x3bfb40, 776, '98d038321d8026c37201a56d223e4f0b3a80db2c01fed81900d1c2e7d454806c'),
    (0x5fc4f0, 168, 'a33b80045aca48549688e41b42b61ff81f533dcf71a4ed390f46e5f6ab7c9720'),
    (0x3bf7c2, 134, 'a71abe5d224d09d6286d54b1da9221a5888c4cc0b14e7ceb59111fd8c2f3253b'),
    (0x5fa9b0, 154, '58784af927c5ebea91f03fa29f6997cbf13ce7351e42fc5679c68a193b5548e1'),
    (0x99fee0, 277, '30f6aba003bb9b0e9d943ec1d5cd3b620fedd100e2a5144bcef498cad87c1150'),
    (0x9a0000, 277, '6867223b6a769cb179758c0bd732745f1485cb674b7d00eed439a06f8a501940'),
)
_DISPATCH_RVAS = frozenset((0xC4930, 0xDB810, 0xDB81C, 0xDB852,
                           0xDB8AE, 0xDB8C2, 0xDB8DE))


def _verify(p):
    if (p['schema'] != 'civ6-host.xp2-congress-presentation-source.static.v1'
            or p['scope']['static_only'] is not True
            or p['scope']['native_execution'] is not False
            or p['scope']['process_memory_read'] is not False
            or p['images']['core']['sha256'] != _CORE_SHA
            or p['runtime_identity']['reference_core_sha256'] != XP2_CORE_SHA256
            or p['runtime_identity']['actual_core_sha256'] != _CORE_SHA
            or p['images']['exe']['sha256'] != _EXE_SHA
            or p['parents']['previous_finished_inventory']['sha256'] != PREVIOUS_SOURCE[1]
            or set(p['routes']) != {hex(k) for k in KINDS}
            or p['dispatch']['root_rva'] != '0xdb810'
            or p['dispatch']['complete_chained_sha256'] !=
               '971f1af6bacfde1ecaefe257e322c95c9157b4fec318adef3918df605891ae92'
            or p['dispatch']['payload_read_on_empty_path'] is not False
            or p['dispatch']['native_gameplay_call_on_empty_path'] is not False
            or p['empty_receiver'] != dict(row_pre_hook=None, row_post_hook=None,
                row_producer_hook=None, subscriber_state_required_nonnull=True,
                subscriber_count=0, active_flag=False, dirty_flag=False)
            or p['stage_producer']['internal_dispatch_before_host'] is not True
            or p['stage_producer']['host_return_discarded_by_caller'] is not True):
        raise ValueError('Congress presentation source contract changed')
    required = set(_DISPATCH_RVAS)
    for kind, (typ, registration, writer, name_setup, setup, handler) in _ROUTES.items():
        row = p['routes'][hex(kind)]
        if (row['name'] != 'GameCoreEvent::' + EVENT_NAMES[kind]
                or row['registration_rva'] != hex(registration)
                or row['callback_rva'] != hex(CURRENT_CALLBACKS[kind])
                or row['retained_registry_callback_rva'] != hex(CALLBACKS[kind])
                or row['writer_rva'] != hex(writer) or row['record_type'] != typ
                or row['record_size'] != 96 or row['writer_bytes'] != 495
                or row['name_registration_rva'] != hex(name_setup)
                or row['setup_rva'] != hex(setup)
                or row['row_static_rva'] != hex(0x12C78B0 + typ * 48)
                or row['handler_rva'] != hex(handler)
                or row['callback_getter_calls'] is not False
                or tuple(row['handler_calls']) != ('0x98abe0', '0xdb810', '0x98ac10')):
            raise ValueError('Congress callback/reader route changed')
        required.update((registration, CURRENT_CALLBACKS[kind], writer,
                         name_setup, setup, handler))
    expected = set(_CORE_SPANS)
    actual = {(int(s['rva'], 16), s['bytes'], s['sha256'])
              for s in p['spans'] if s['image'] == 'core'}
    if not expected <= actual or not required <= {
            int(s['rva'], 16) for s in p['spans'] if s['image'] == 'exe'}:
        raise ValueError('Congress presentation source spans changed')
    return p


@lru_cache(maxsize=1)
def source():
    p = _verify(_source(SOURCE))
    _source(PREVIOUS_SOURCE)
    verify_pinned_files({row['path']: row['sha256'] for row in p['images'].values()})
    for row in p['spans']:
        with Path(p['images'][row['image']]['path']).open('rb') as stream:
            stream.seek(int(row['file_offset'], 16))
            raw = stream.read(row['bytes'])
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Congress presentation installed image span differs')
    return p


def source_dependencies():
    p = source()
    refs = {str(_path(path).resolve()): digest for path, digest in (SOURCE, PREVIOUS_SOURCE)}
    refs.update({str(Path(row['path']).resolve()): row['sha256']
                 for row in p['images'].values()})
    return refs


def core_fragments():
    """Bounded installed source bytes used by the prepared-owner live guard."""
    p = source()
    wanted = {rva for rva, _, _ in _CORE_SPANS}
    for row in p['spans']:
        if row['image'] == 'core' and int(row['rva'], 16) in wanted:
            with Path(p['images']['core']['path']).open('rb') as stream:
                stream.seek(int(row['file_offset'], 16))
                raw = stream.read(row['bytes'])
            if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('Congress presentation source bytes changed')
            yield int(row['rva'], 16), raw


def _execution(core):
    from .execution_images import identity
    profile = getattr(core, '_civ6_host_execution_image', None)
    selected = identity(profile)
    if (selected['profile_id'] != 'xp2-gamecore-current-092abfbb'
            or selected['image_sha256'] != _CORE_SHA
            or selected['reference_core_sha256'] != XP2_CORE_SHA256
            or Path(selected['path']).resolve() != Path(source()['images']['core']['path']).resolve()):
        raise ValueError('Congress presentation requires its exact current execution image')
    return profile


def bind_owner(backend, core, read):
    backend.check_thread()
    if (backend.core is not core or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or backend.stage != 'prepared' or backend.poisoned or backend.destroyed
            or type(core._handle) is not int or core._handle <= 0 or not callable(read)):
        raise ValueError('Congress presentation requires its exact prepared XP2 owner')
    execution = _execution(core)
    source_dependencies()
    for rva, raw in core_fragments():
        actual = read(core._handle + rva, len(raw))
        if type(actual) is not bytes or actual != raw:
            raise ValueError('Congress presentation live producer source differs')
    backend._xp2_congress_presentation_source_identity = (
        id(core), core._handle, XP2_CORE_SHA256, id(execution), _CORE_SHA, SOURCE[1])
    return SOURCE[1]


def _empty(state):
    return (type(state) is dict and set(state) == set(_EMPTY_STATE)
            and all(type(state[k]) is type(v) and state[k] == v
                    for k, v in _EMPTY_STATE.items()))


def validate_empty_owner(owner):
    from .a0_family_service import A0FamilyService
    from .a0_foundation_events import require_borrow
    if type(owner) is not A0FamilyService:
        raise ValueError('Congress presentation requires the real shared A0 owner')
    owner._check()
    backend = require_borrow(owner).owner
    execution = _execution(backend.core)
    if (type(owner.active_kind) is not int or owner.active_kind not in KINDS
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or owner.arguments.reader.core_sha256 != XP2_CORE_SHA256
            or owner.deferred.cache_core_sha256 != XP2_CORE_SHA256
            or owner._foundation_backend is not backend
            or backend.core is not owner.deferred.core
            or backend.host is not owner.arguments.host
            or not _empty(owner.empty_receiver_state)
            or not _empty(owner._receiver_profile)
            or type(owner.entity_listener_count) is not int or owner.entity_listener_count != 0
            or owner.dynamic_event_registration_present is not False
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or getattr(backend, '_xp2_congress_presentation_source_identity', None) !=
               (id(backend.core), backend.core._handle, XP2_CORE_SHA256,
                id(execution), _CORE_SHA, SOURCE[1])):
        raise ValueError('Congress presentation receiver, hooks or owner source changed')
    return POLICY


@dataclass(frozen=True)
class CongressFields:
    kind: int
    selector: int
    value: int | None

    def to_admin(self):
        tags = {hex(SELECTOR_KEY): 3}
        if self.kind != FINISHED:
            tags[hex(VALUE_KEY)] = 2
        return dict(event_name=EVENT_NAMES[self.kind], selector=self.selector,
                    source_d6_value=self.value, field_tags=tags,
                    gameplay_getters_required=False)


def _uint32_variant(raw, tag):
    if (type(raw) is not bytes or len(raw) != 24
            or struct.unpack_from('<H', raw)[0] != tag or raw[16:24] != b'\0' * 8):
        raise ValueError('Congress presentation scalar variant differs')
    # Padding is deliberately ignored, including the nonzero bytes in the
    # copied native Stage1 failure header. Value and flags remain exact.
    return struct.unpack_from('<I', raw, 8)[0]


def decode_fields(kind, fields, read):
    source()
    if (type(kind) is not int or kind not in KINDS or type(fields) is not dict
            or any(type(key) is not int for key in fields)
            or set(fields) != ({SELECTOR_KEY} if kind == FINISHED
                                else {SELECTOR_KEY, VALUE_KEY})):
        raise ValueError('Congress presentation argument shape differs')
    selector = _uint32_variant(fields[SELECTOR_KEY], 3)
    if selector != 0:
        raise ValueError('Congress presentation selector differs from its producer')
    value = None if kind == FINISHED else _uint32_variant(fields[VALUE_KEY], 2)
    return CongressFields(kind, selector, value)


def record_callback(owner, fields):
    """Record only the actual validated callback, without an EXE subscriber."""
    from .xp2_congress_cycle import record_callback as record
    validate_empty_owner(owner)
    record(owner, fields)

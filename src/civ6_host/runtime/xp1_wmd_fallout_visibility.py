"""Installed Rise and Fall fallout visibility forms on the shared deferred FIFO."""

from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from . import xp2_wmd_fallout_visibility as shared
from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE, identity
from .xp1_saved_load import REFERENCE


SOURCE = ('evidence/host-xp1-installed-wmd-fallout-visibility-source.json',
          'e0e02a15e0a539ff31a579f8f91df1e70e3387c2a9298d97c3d941388361c966')
KIND, RECORD_TYPE, RECORD_SIZE = shared.KIND, shared.RECORD_TYPE, shared.RECORD_SIZE
SELECTOR, VALUE, POSITION, PLAYER = shared.SELECTOR, shared.VALUE, shared.POSITION, shared.PLAYER
_DIRECT = frozenset((SELECTOR, VALUE, POSITION))
_PLAYER = _DIRECT | {PLAYER}
_EXE_SHA = 'd1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe'


@lru_cache(maxsize=1)
def _installed_source():
    proof = _source(SOURCE)
    contract, capture, reference = (proof[name] for name in ('contract', 'capture', 'reference'))
    direct, player = (contract['forms'][name] for name in ('direct', 'player'))
    direct_tags = {hex(SELECTOR): 3, hex(VALUE): 2, hex(POSITION): 0}
    player_tags = {**direct_tags, hex(POSITION): 13, hex(PLAYER): 2}
    if (proof['schema'] != 'civ6-host.xp1-installed-wmd-fallout-visibility.static.v1'
            or proof['image'] != identity(_XP1_PROFILE)
            or proof['executable']['sha256'] != _EXE_SHA
            or (capture['official']['path'], capture['official']['sha256']) != REFERENCE
            or (reference['path'], reference['sha256']) != shared.SOURCE
            or (contract['kind'], contract['selector'], contract['scalar_flags']) != (KIND, 0, 0)
            or direct['key_tags'] != direct_tags or player['key_tags'] != player_tags
            or direct['D6_domains_by_site'] != ((2,), (2,), (0, 2))
            or player['D6_domains_by_site'] != ((0, 2),) or player['EXE_reads_player'] is not False
            or (contract['position_bytes'], contract['position_flags']) != (8, 0x21000001)
            or contract['core_internal_dispatch_before_host'] is not True
            or (contract['record'], contract['record_bytes']) != (RECORD_TYPE, RECORD_SIZE)
            or (contract['metadata_offset'], contract['sequence_offset'], contract['position_offset'],
                contract['D6_offset'], contract['reserved_zero_allocation']) != (72, 80, 84, 92, (76, 80))
            or contract['metadata_counters'] != dict(notification_rva=0x22d8c6c, metadata_rva=0x22d8c68,
                N_eq_0=(0, 'M'), N_nonzero_M_lt_N=(32, 'M+1'), N_nonzero_M_ge_N=(64, 'M'))
            or contract['receiver_guard'] != dict(observer_registered=False, state_pointer_nonnull=True,
                pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0)
            or contract['handler'] != proof['exe']['receiver_handler']['rva']
            or contract['use_existing_owned_fifo'] is not True
            or contract['zero_record_omission_admitted'] is not False):
        raise ValueError('Installed Rise and Fall fallout visibility source differs')
    return proof


def source(execution_image):
    if execution_image is not _XP1_PROFILE:
        raise ValueError('Fallout visibility requires the installed Rise and Fall image')
    return _installed_source()


def source_dependencies(execution_image):
    proof = source(execution_image)
    capture = proof['capture']
    exe = proof['executable']
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1],
            str(Path(execution_image.path).resolve()): execution_image.image_sha256,
            str(Path(exe['path']).resolve()): exe['sha256']}
    for ref in (capture['official'], capture['prepared'], proof['reference']):
        pins[str(_path(ref['path']).resolve())] = ref['sha256']
    verify_pinned_files(pins)
    return pins


def verify_live(core, read):
    proof = source(getattr(core, '_civ6_host_execution_image', None))
    for name, span in proof['core'].items():
        raw = read(core._handle + span['rva'], span['bytes'])
        if (type(raw) is not bytes or len(raw) != span['bytes']
                or sha256(raw).hexdigest() != span['sha256']):
            raise ValueError('Live Rise and Fall fallout visibility source differs: ' + name)


def receiver_row():
    span = _installed_source()['exe']['receiver_handler']
    return dict(event_name='GameCoreEvent::WMDFalloutVisibilityChanged',
                handler_va=hex(0x140000000 + span['rva']),
                handler_body_sha256=span['sha256'], record_sizes={RECORD_SIZE})


def decode_fields(fields, read):
    from .native.native_application_mirror import decode_scalar
    from .native.native_event_827289e6 import _copy_blob

    if type(fields) is not dict or set(fields) not in (_DIRECT, _PLAYER):
        raise ValueError('Rise and Fall fallout visibility has unqualified field keys')
    selector = decode_scalar(fields[SELECTOR], 3)
    value = decode_scalar(fields[VALUE], 2)
    if selector != 0 or value not in (0, 2):
        raise ValueError('Rise and Fall fallout visibility selector or value differs')
    tag = 0
    if PLAYER in fields:
        decode_scalar(fields[PLAYER], 2)
        tag = 13
    return _copy_blob(fields[POSITION], read, tag, 'WMD visibility position'), value


def dispatch(owner, fields):
    from .a0_foundation_events import require_borrow

    backend = require_borrow(owner).owner
    image = getattr(backend.core, '_civ6_host_execution_image', None)
    proof = source(image)
    owner._require_no_f391_reentry()
    if (backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or owner.foundation_core_sha256 != XP1_CORE_SHA256 or owner.active_kind != KIND
            or backend.captured_bundle.reference != REFERENCE
            or backend.captured_bundle.content_profile['gameplay_scripts'] != proof['capture']['gameplay_scripts']
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False):
        raise ValueError('Fallout visibility requires the exact Rise and Fall callback owner')
    position, value = decode_fields(fields, owner.read)
    return shared.enqueue(owner, position, value, source_sha256=SOURCE[1])

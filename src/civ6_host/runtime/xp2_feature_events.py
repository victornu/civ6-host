"""Current XP2 feature events on the shared A0 owner and FIFO."""

from contextlib import contextmanager
import ctypes as C
from hashlib import sha256
from pathlib import Path
import struct

from .a0_family_source import _path, verify_pinned_files
from .a0_policy_unlock_current import CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image
from .configuration_profiles import XP2_CORE_SHA256, _source
from .foundation_facade_profiles import query_abi
from .paths import resource_root
from .resource_resolution import resolve_path


_DIRECTORY = 'work/official-capture/bbg751-world-A-trade-ui-association/'
SOURCE = (_DIRECTORY + 'trade-amani-feature-facades.json',
          '69f712b3e9567055d1a744eadc910744c0f44157d4c127b9aceb1cc88cdef406')
RECEIVERS = (_DIRECTORY + 'trade-amani-feature-family-receivers.json',
             'ecef5a87f78f49a71a96eca860afbf1b48868fe67c05d914579dff21a5cb7e5c')
ADDED, CHANGED, VISIBILITY = 0xb39c906a, 0xf7807ff9, 0x878cd252
RECORD_TYPE, RECORD_SIZE = 116, 112
_PLOT_CHILD = (0xa12490, 0x40, 0x5a11b0)
_CHILD_RELEASE = (0xa117e8, 0x08, 0x59b950)
_CHILD_VALUE = (0xa117e8, 0x18, 0x59b970)
_LOCAL_GAME_MODE = 0xe9685ee7


def source_dependencies(*, execution_image):
    _require_image(execution_image)
    proof = _source(SOURCE)
    images = proof['images']
    if (proof['schema'] != 'civ6-host.xp2-feature-callback-facades.static.v1'
            or images['core']['sha256'] != CURRENT_CORE_SHA256
            or images['exe']['sha256'] != CURRENT_EXE_SHA256
            or resolve_path(Path(images['core']['path'])).resolve() != Path(execution_image.path).resolve()
            or proof['contract']['normalizer_return'] != 0
            or proof['contract']['core_internal_dispatch_before_host'] is not True
            or proof['contract']['game_mode_equality'] != _LOCAL_GAME_MODE
            or not {_PLOT_CHILD, _CHILD_RELEASE, _CHILD_VALUE} <= {
                (row['table'], row['slot'], row['target']) for row in proof['virtual_slots']}):
        raise ValueError('Current XP2 feature event source differs')
    refs = [(SOURCE[0], SOURCE[1]), (RECEIVERS[0], RECEIVERS[1])]
    pins = {str(_path(path).resolve()): digest for path, digest in refs}
    for row in proof['parents']:
        path = str(_path(row['path']).resolve())
        if pins.setdefault(path, row['sha256']) != row['sha256']:
            raise ValueError('Conflicting feature source dependencies')
    pins.update((str(resolve_path(Path(row['path'])).resolve()), row['sha256'])
                for row in images.values())
    verify_pinned_files(pins)
    return pins


def receiver_row():
    proof = _source(RECEIVERS)
    if (proof['schema'] != 'civ6-host.xp2-current-feature-family-receivers.static.v1'
            or proof['exe_sha256'] != CURRENT_EXE_SHA256
            or tuple(row['record_type'] for row in proof['receivers']) != (116, 117, 118)):
        raise ValueError('Current XP2 feature receiver source differs')
    row = proof['receivers'][0]
    handler = row['handler']
    if (row['name'] != 'GameCoreEvent::FeatureAddedToMap' or handler['rva'] != '0xd81b0'
            or handler['instructions']['0xd81f4'] != 'call 0x1400db810'):
        raise ValueError('FeatureAddedToMap receiver differs')
    return dict(event_name=row['name'], handler_va='0x1400d81b0',
                handler_body_sha256=handler['sha256'], record_sizes={RECORD_SIZE})


def core_fragments():
    proof = _source(SOURCE)
    path = resolve_path(Path(proof['images']['core']['path']))
    with path.open('rb') as stream:
        for row in proof['core'].values():
            stream.seek(int(row['file_offset'], 16))
            raw = stream.read(row['bytes'])
            if len(raw) != row['bytes'] or sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('Installed XP2 feature source changed at ' + row['rva'])
            yield int(row['rva'], 16), raw


def verify_live(core, read):
    _require_image(getattr(core, '_civ6_host_execution_image', None))
    base = core._handle
    for rva, raw in core_fragments():
        if read(base + rva, len(raw)) != raw:
            raise ValueError('Live XP2 feature source changed at ' + hex(rva))
    for row in _source(SOURCE)['virtual_slots']:
        if read(base + row['table'] + row['slot'], 8) != struct.pack('<Q', base + row['target']):
            raise ValueError('Live XP2 feature vtable changed at ' + hex(row['table'] + row['slot']))


def _slot(abi, name):
    return abi.table(abi.operations[name]['table']), abi.slot(name), abi.rva(name)


@contextmanager
def _query_added_feature(owner, x, y):
    """Release the map and child before enqueue, and the plot after enqueue."""
    base, read = owner.base, owner.read
    abi = query_abi(XP2_CORE_SHA256, resource_root())

    def invoke(obj, route, result, *args, types=()):
        table, offset, target = route
        if (read(obj, 8) != struct.pack('<Q', base + table)
                or read(base + table + offset, 8) != struct.pack('<Q', base + target)):
            raise ValueError('FeatureAddedToMap facade or method differs')
        return C.WINFUNCTYPE(result, C.c_void_p, *types)(base + target)(obj, *args)

    map_object = invoke(owner.context, _slot(abi, 'outer_map'), C.c_void_p)
    if not map_object:
        yield -1
        return
    try:
        plot = invoke(map_object, _slot(abi, 'get_plot'), C.c_void_p,
                      x, y, types=(C.c_int32, C.c_int32))
    finally:
        invoke(map_object, _slot(abi, 'release_map'), None)
    if not plot:
        yield -1
        return
    try:
        child = invoke(plot, _PLOT_CHILD, C.c_void_p)
        # The EXE calls the child getter without a null check after a
        # successful plot lookup. A failed allocation has no valid value.
        if not child:
            raise RuntimeError('FeatureAddedToMap native plot child is absent')
        try:
            value = invoke(child, _CHILD_VALUE, C.c_int32)
        finally:
            invoke(child, _CHILD_RELEASE, None)
        yield value
    finally:
        invoke(plot, _slot(abi, 'release_plot'), None)


def dispatch_added(owner, raw_fields):
    from .a0_foundation_events import require_borrow
    from .native.native_deferred_empty_profile import validate_empty_profile_record
    from .native.native_player_event_domains import validate_sequence
    from .native.native_position_value_event_family import decode_fields
    from .native.native_unary_event_family import _METADATA
    from .turn_unit_event_profile import read_application_mode

    backend = require_borrow(owner).owner
    owner._require_no_f391_reentry()
    if (owner.active_kind != ADDED or owner.foundation_core_sha256 != XP2_CORE_SHA256
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or type(owner.entity_listener_count) is not int or owner.entity_listener_count != 0
            or len(owner.pending) >= owner.limit):
        raise ValueError('FeatureAddedToMap requires its owned empty A0 receiver')
    sequence = validate_sequence(owner._sequence + 1)
    fields = decode_fields(raw_fields, owner.read)
    if fields.selector != 0:
        raise ValueError('FeatureAddedToMap selector differs')

    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII', record, 0, RECORD_SIZE, RECORD_TYPE, sequence, 0)
    validate_empty_profile_record(record, **owner.empty_receiver_state)
    record[16:80] = _METADATA
    mode = read_application_mode(backend.owner, XP2_CORE_SHA256, candidate_backend=backend)
    with _query_added_feature(owner, fields.x, fields.y) as value:
        struct.pack_into('<I8sIiB', record, 80, sequence, fields.position_bytes,
                         fields.value, value, int(mode == _LOCAL_GAME_MODE))
        owner._enqueue(bytes(record))
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(ADDED),
               queue_type=hex(RECORD_TYPE), sequence=sequence, record_hex=record.hex(),
               source_proof_sha256=SOURCE[1], native_feature_value_queried=True,
               payload_exposed_to_learner=False, eligible_for_training=False)
    return 0

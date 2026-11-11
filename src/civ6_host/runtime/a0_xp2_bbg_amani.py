"""Source-bound BBG property notifications on the existing A0 owner."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import struct

from .a0_policy_unlock_current import CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image
from .configuration_profiles import _source
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp2_feature_reveal_source import _copy_pair, _uint32_variant

PREPARATION = ('evidence/host-xp2-bbg-amani-preparation.json',
               '76c113a5126c01c53930fd822c52566096d64d708776ece9e3590e4efbaf6f71')
SOURCE = ('evidence/host-xp2-bbg-amani-property-profile.json',
          '1090cb3fd5c49747157769552d942d628ff51f710080bd808035683eab47974e')
PLOT_SOURCE = ('evidence/host-xp2-bbg-liberation-plot-property-gap.json',
               '110b2deceadc60a693877074465c522613086969da9dabea4675393afad3b124')
GOVERNOR_ASSIGNED, GOVERNOR_CHANGED = 0xcf9c73f1, 0xcb6c9e05
PLAYER_PROPERTY, PLOT_PROPERTY = 0x153e72c2, 0x6195d70f
ASSIGNED_RECORD, CHANGED_RECORD, PLOT_RECORD = 223, 224, 184
_SELECTOR, _VALUE, _POSITION, _PLAYER = 0xa1e5a149, 0xd6fcf3e4, 0x8c468e3c, 0xf06a2af2
_AMANI_HASH = 0x259285b3
_PLOT_HASHES = {0x4c608a17, 0xfa20f799}


def _proof(image):
    _require_image(image)
    preparation, proof = _source(PREPARATION), _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-bbg-amani-property-profile.static.v1'
            or proof['images'] != {'exe': CURRENT_EXE_SHA256, 'core': CURRENT_CORE_SHA256}
            or proof['parent'] != {'path': PREPARATION[0], 'sha256': PREPARATION[1]}
            or preparation['current_static_lua_order_verified'] is not True
            or preparation['property_sources']['main_host_dispatch']['fixed_lookup_miss_returns_zero'] is not True
            or proof['player']['fixed_callback_absent'] is not True
            or proof['plot']['exact_selected_bbg_files_subscribe_to_property_notification'] is not False):
        raise ValueError('BBG Amani sources differ from the admitted notification route')
    return preparation, proof


def _plot_source(image):
    _require_image(image)
    proof = _source(PLOT_SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-bbg-plot-property-continuation.v1'
            or proof['installed_executable']['sha256'] != CURRENT_EXE_SHA256
            or proof['installed_core']['sha256'] != CURRENT_CORE_SHA256
            or proof['registry']['kind'] != PLOT_PROPERTY
            or proof['inputs']['amani_profile']['sha256'] != SOURCE[1]
            or proof['native_record'] != dict(
                type=PLOT_RECORD, size=96, position_offset=84, position_size=8,
                native_property_hash_consumed_by_presentation=False,
                game_effect_processed_by_core_before_dispatch=True, handler_rva=0xd9b90,
                event_name='GameCoreEvent::PlotPropertyChanged', selected_bbg_subscribes=False)):
        raise ValueError('Current BBG plot property receiver source differs')
    return proof


def source_dependencies(*, execution_image):
    _proof(execution_image)
    executable = _plot_source(execution_image)['installed_executable']
    pins = {resource_root() / path: sha for path, sha in (PREPARATION, SOURCE, PLOT_SOURCE)}
    pins[resolve_path(Path(executable['path'])).resolve()] = executable['sha256']
    return pins


def verify_live(owner, backend, image):
    preparation, proof = _proof(image)
    _plot_source(image)
    properties = preparation['property_sources']
    spans = [*(row['core_producer'] for row in preparation['governor_routes']),
             properties['plot']['setter'], properties['plot']['core_emitter'],
             properties['player']['setter'], properties['player']['core_emitter'],
             *(row['constructor'] for row in properties['player']['core_variant_inputs']
               if 'constructor' in row), proof['plot']['native_recalculation']]
    for row in spans:
        data = owner.read(backend.core._handle + int(row['rva'], 16), row['bytes'])
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Live BBG Amani notification source differs at ' + row['rva'])


@contextmanager
def expect_properties(owner, *, player, plots, allow_player):
    if (getattr(owner, '_bbg_amani_receiver', None) is None or owner._bbg_amani_property_scope is not None
            or owner.active_kind is not None or owner.pending or owner.deferred._draining_empty_receivers
            or type(player) is not int or not 0 <= player < 64 or type(allow_player) is not bool):
        raise ValueError('BBG Amani properties require one idle feedback owner')
    owner._bbg_amani_property_scope = (player, frozenset(plots), allow_player)
    try:
        yield
    finally:
        owner._bbg_amani_property_scope = None


def dispatch_property(owner, kind, fields):
    scope = owner._bbg_amani_property_scope
    extra = _PLAYER if kind == PLAYER_PROPERTY else _POSITION
    if (kind not in (PLAYER_PROPERTY, PLOT_PROPERTY) or owner.active_kind != kind
            or owner.dynamic_event_registration_present is not False
            or owner.normalizer_transform_present is not False
            or set(fields) != {_SELECTOR, _VALUE, extra}
            or _uint32_variant(fields[_SELECTOR], 3, 'BBG property selector') != 0):
        raise ValueError('BBG property notification differs from its native envelope')
    if kind == PLAYER_PROPERTY:
        if scope is None:
            raise ValueError('BBG Amani player property is outside the exact operation')
        player, _, allow_player = scope
        prop = _uint32_variant(fields[_VALUE], 3, 'Amani player property')
        if (not allow_player or prop != _AMANI_HASH
                or _uint32_variant(fields[_PLAYER], 2, 'Amani property player') != player):
            raise ValueError('BBG Amani player property crossed its operation scope')
        # GameCore already wrote the value and ran its internal dispatch. This
        # exact event has no fixed EXE callback, and this owner has no dynamic hooks.
        owner.emit('xp2_bbg_amani_player_property_notification', player_id=player,
                   property_hash=hex(prop), core_internal_dispatch_preserved=True)
        return 0
    prop = _uint32_variant(fields[_VALUE], 2, 'BBG plot property')
    raw = fields[_POSITION]
    if (type(raw) is not bytes or len(raw) != 24 or struct.unpack_from('<H', raw)[0] != 0
            or struct.unpack_from('<II', raw, 16) != (8, 0x21000001)):
        raise ValueError('Unqualified BBG plot property coordinates')
    position = _copy_pair(owner.read, struct.unpack_from('<Q', raw, 8)[0])
    amani_write = scope is not None and prop in _PLOT_HASHES
    if amani_write and position not in scope[1]:
        raise ValueError('BBG Amani plot property is outside the owned city locations')

    # The installed presentation writer copies the position alone for every
    # plot property. GameCore has already performed its gameplay dispatch.
    sequence = owner._sequence + 1
    from .native.native_scalar_event_encoder import _encode_profile_record
    row = {'writer_record_type': hex(PLOT_RECORD), 'payload_value_count': 2}
    owner._enqueue(_encode_profile_record(row, sequence, tuple(value & 0xffffffff for value in position)))
    if amani_write:
        owner.emit('xp2_bbg_amani_plot_property_notification', player_id=scope[0],
                   position=list(position), property_hash=hex(prop), sequence=sequence)
    else:
        owner.emit('xp2_bbg_plot_property_notification', position=list(position),
                   property_hash=hex(prop), sequence=sequence, payload_exposed_to_learner=False)
    return 0


def validate_plot_record(owner, record, sequence):
    if (len(record) != 96 or struct.unpack_from('<IIII', record) != (96, PLOT_RECORD, sequence, 0)
            or struct.unpack_from('<I', record, 80)[0] != sequence
            or owner.empty_receiver_state != dict(observer_registered=False, state_pointer_nonnull=True,
                pre_hook=None, post_hook=None, subscriber_count=0, state_flags=0)):
        raise ValueError('BBG plot property record lacks its exact source-qualified receiver')
    return struct.unpack_from('<ii', record, 84)

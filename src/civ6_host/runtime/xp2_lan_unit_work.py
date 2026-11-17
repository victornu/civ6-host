"""UnitPanel work for an authenticated Gathering Storm LAN seat."""

from functools import partial
from hashlib import sha256
from struct import pack
from types import SimpleNamespace

from civ6_host.contracts import network_turn, unit_work
from . import unit_work_info, unit_work_state


KINDS = unit_work.ADJACENT_NETWORK_ACTION_FIELDS
ADJACENT = unit_work.ADJACENT_KIND

# Current XP2: operation registration and parameter reader/writer, then the
# shared encoder for the improvement identity and the two coordinates.
_ADJACENT_LAYOUT = (
    (0x74a600, 0x7a, 'bdbc29db8f08e1686b01f9c4bfd5e787657773339256873481eb705563519366'),
    (0x74a310, 0xce, 'eb83117b673914bf99d50ad6bd0b821aea94fb612d6f6501d773a459f7dbb073'),
    (0x74a5a0, 0x5b, 'ac29a62c6086451e081f83ea3df855cef2528eef3a3d469c9cde8f2885f727b3'),
    (0x6024b0, 0x6d, 'e4d3827ac41f802747c8c194ab0e5b0dc515d2f2f6c6616017ff6747474a7e09'),
    (0x602480, 0x15, '6a7a503f1307bdd51a302fc93b4f80c2c1f96ff7cab74b1443ee8b20e898197f'),
    (0x74ab10, 0x5e, '2b7e8539983a9423762642128cc9f5e1396f27ea5a629493cddd07ba2f0be7b1'),
    (0x600b80, 0x77, '1119d61541513dcf6caf822f7088d04bb1f5aea33cd8398947254daf77d4388b'),
    (0x68d10, 0x3d, 'ec5b68532098dd45a77b8c18f8a6915880d665c4e6e6fa77c8a5a49060273042'),
    (0xa438c4, 4, '67abdd721024f0ff4e0b3f4c2fc13bc5bad42d0b7851d456d88d203d15aaa450'),
    (0x3a800, 0x75, '6d2cd098490a1ddcb741b529764ef5e65fa82ec258c061db6e5583888678ab12'),
    (0x3abd0, 0x4e, '87c180b8228310c385f55a0f3f0ca8d5fb7a19f8448a1e40b6419aa54849bacf'),
    (0x6c1e40, 0x176, 'd3313d014bde091c9685f1efdaa6a42353560b46b9f6641dc62c50a4835b1fe1'),
)
_ADJACENT_SLOTS = ((0xa438f8 + 0x78, 0x74a310),
                   (0xa438c8 + 0x08, 0x74a5a0), (0xa438c8 + 0x20, 0x74ab10))


def enabled(saved):
    return getattr(saved, '_xp2_lan_unit_work_enabled', False) is True


def adjacent_enabled(saved):
    return (enabled(saved) and primary_adjacent_enabled(saved)
            and getattr(saved, '_xp2_lan_adjacent_work_enabled', False) is True)


def primary_adjacent_enabled(saved):
    core = getattr(saved, '_xp2_adjacent_work_core', None)
    return core is not None and core is saved.backend.core


def bind_adjacent(saved):
    from .xp2_unit_attack_source import current_lifecycle_image

    core = saved.backend.core
    if not current_lifecycle_image(getattr(core, '_civ6_host_execution_image', None)):
        return
    verify_adjacent_layout(core._handle, saved.backend.runtime.read)
    saved._xp2_adjacent_work_core = core
    saved._xp2_lan_adjacent_work_enabled = enabled(saved)


def verify_adjacent_layout(base, read):
    if type(base) is not int or not 0 < base < (1 << 47) - 0x1000000:
        raise ValueError('Invalid module for XP2 adjacent work')
    for rva, size, expected in _ADJACENT_LAYOUT:
        raw = read(base + rva, size)
        if type(raw) is not bytes or len(raw) != size or sha256(raw).hexdigest() != expected:
            raise ValueError(f'XP2 adjacent work layout differs at 0x{rva:x}')
    for slot, target in _ADJACENT_SLOTS:
        if read(base + slot, 8) != pack('<Q', base + target):
            raise ValueError(f'XP2 adjacent work vtable differs at 0x{slot:x}')


def require_archive(payload, player_id, action, *, operation_index):
    unit_work.validate_action(action)
    if (type(player_id) is not int or not 0 <= player_id < 64 or action['kind'] not in KINDS
            or type(operation_index) is not int or not 0 <= operation_index <= 2047):
        raise ValueError('Borrowed work requires a native actor and operation index')
    head = pack('<IHH4I', 0x8c0f3f36, player_id, 1, action['unit_id'], operation_index, 0xffffffff, 0)
    if action['kind'] == 'build_improvement':
        expected = head + pack('<4I', 1, 0, action['hash'], 0)
    elif action['kind'] == ADJACENT:
        expected = head + pack('<6I', 1, 0, action['hash'], action['x'], action['y'], 0)
    else:
        expected = head + pack('<I', 0)
    if type(payload) is not bytes or payload != expected:
        raise ValueError('Borrowed work archive differs from its actor, unit or operation')


def _operation_index(prefix, observation, action):
    pid, turn = observation['player_id'], observation['turn']
    terrain = action['kind'] == 'terrain_operation'
    if terrain:
        name = action['operation']
        # Generic UnitPanel operations use the DB row, including REPAIR_ROUTE,
        # whose name is absent from the installed UnitOperationTypes.
        expected_hash = str(action['hash'])
    elif action['kind'] == ADJACENT:
        name, expected_hash = 'BUILD_IMPROVEMENT_ADJACENT', '945035974'
    else:
        name, expected_hash = 'BUILD_IMPROVEMENT', '492889976'
    source = f"""
assert(Game.GetLocalPlayer()=={pid} and Game.GetLocalObserver()=={pid}
    and Game.GetCurrentGameTurn()=={turn},'borrowed work perspective changed')
local op=GameInfo.UnitOperations['UNITOPERATION_{name}']
assert(op and type(op.Hash)=='number' and op.Hash%4294967296=={expected_hash}
    and type(op.Index)=='number'
    and op.Index%1==0 and op.Index>=0 and op.Index<=2047,'invalid native work operation index')
return string.format('%.0f',op.Index)
""".encode('ascii')
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source, b'@xp2_borrowed_unit_work_index', capacity=16)
    if type(raw) is not bytes or not 1 <= len(raw) <= 4 or not raw.isdigit():
        raise ValueError('Invalid borrowed native work operation index')
    index = int(raw)
    if not 0 <= index <= 2047 or str(index).encode('ascii') != raw:
        raise ValueError('Noncanonical borrowed native work operation index')
    return index


def archive_scope(transport, prefix, observation, action):
    index = _operation_index(prefix, observation, action)
    return transport.require_xp2_single_archive(partial(
        require_archive, player_id=observation['player_id'], action=action, operation_index=index))


def read(saved, observation, activity):
    if not enabled(saved):
        return None
    pid, turn = observation['player_id'], observation['turn']
    row = next(row for row in activity['rows'] if row['player_id'] == pid)
    if network_turn.is_waiting(row):
        return None
    from .xp1_session_view import _borrowed_xp2_reference

    _borrowed_xp2_reference(saved, pid)
    transport = saved.continuation.transport
    transport.require_empty_native_queue()
    catalog, info = unit_work_info.read_catalog(saved.prefix, turn, player_id=pid, processing=True,
                                               adjacent=adjacent_enabled(saved))
    state = unit_work_state.observe(saved, observation, catalog, include_plot=True)
    transport.require_empty_native_queue()
    return catalog, state, info


def apply(saved, action, observation, work):
    from .native import native_saved_unit_work as native

    if (work is None or (action['kind'] == ADJACENT and not adjacent_enabled(saved))
            or action not in unit_work.actions(work[0])):
        return dict(status='refused', reason='native_unit_work_choice_unavailable', requested_action=action), None
    pid, turn = observation['player_id'], observation['turn']
    prefix, token = saved.prefix, saved.continuation
    receipts = []

    def emit(stage, **row):
        if stage != 'official_explicit_unit_work_effect' or receipts:
            raise RuntimeError('Unexpected borrowed unit-work receipt')
        receipts.append(row)
        saved.emit(stage, **row)

    count = token.publication_count
    owner = SimpleNamespace(emit=emit)
    with archive_scope(token.transport, prefix, observation, action):
        after = native.apply(owner, prefix, action, turn, observation, player_id=pid)
    if len(receipts) != 1 or token.publication_count != count + 1:
        raise RuntimeError('Borrowed worker action did not publish one native effect')
    receipt = receipts[0]
    if (receipt['action'] != action or receipt['observation_before'] != observation
            or receipt['observation_after'] != after or receipt['automatic_choices_applied'] is not False
            or receipt['plot_before'].get('charges') != action['charges']):
        raise RuntimeError('Borrowed work effect differs from the submitted action')
    feedback = token.trade_feedback
    if feedback is not None and feedback.events:
        delivered = token.flush_trade_feedback()
        if delivered:
            saved.emit('xp2_bbg_trade_gameplay_delivered', feedback=delivered)
        from .native.native_player_observation import observe_player

        after = observe_player(prefix.runtime, prefix.ui_child, pid)
    token.transport.require_empty_native_queue()
    return dict(status='completed', reason=None, requested_action=action), after

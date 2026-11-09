"""Run the captured BBG trade listener through the retained native command owner."""
from collections import deque
import hashlib
from pathlib import Path

from .configuration_profiles import _source
from .resource_resolution import resolve_path

UI_SOURCE = ('work/trade-common-client/xp2-current-trade-registration.json',
             'cdd63fa9e758eb02170ebc7d35a48c9ef7b2fa4e49ae330d64ff2061d79b6f43')
_UI_SHA256 = '65aded4dfc11b8c088b62d7be4c998970b59d6fbf6a73e75c48d45b6d1052ef3'
_CAPACITY = 1024

_BEFORE = b"""
assert(Civ6HostBBGTradeFeedback == nil, 'Existing BBG trade feedback owner')
local OnTradeRouteActivityChanged, OnLocalPlayerTurnBegin
local requests = {}
local PlayerOperations = {EXECUTE_SCRIPT = 0xc665ad08}
local UI = {}
function UI.RequestPlayerOperation(player, operation, p)
    assert(operation == PlayerOperations.EXECUTE_SCRIPT and p.OnStart == 'GameplaySetCSTrader'
        and player == p.iOriginPlayerID and #requests < 1024, 'Unexpected BBG trade request')
    for k in pairs(p) do
        assert(k == 'OnStart' or k == 'iOriginPlayerID' or k == 'iOriginCityID'
            or k == 'iTargetPlayerID', 'Unexpected BBG trade parameter')
    end
    for _, value in ipairs({player, p.iOriginCityID, p.iTargetPlayerID}) do
        assert(type(value) == 'number' and value % 1 == 0, 'Invalid BBG trade request integer')
    end
    requests[#requests + 1] = string.format('%d,%d,%d', player, p.iOriginCityID, p.iTargetPlayerID)
end
"""
_AFTER = b"""
local function dispatch(listener, ...)
    assert(#requests == 0, 'Pending BBG trade request')
    listener(...)
    assert(#tBufferedParams.CSBufferedParams <= 1024, 'BBG trade buffer exhausted')
    local result = table.concat(requests, ';')
    requests = {}
    return result
end
Civ6HostBBGTradeFeedback = {
    activity = function(...) return dispatch(OnTradeRouteActivityChanged, ...) end,
    turn_begin = function() return dispatch(OnLocalPlayerTurnBegin) end,
    buffered = function() return tostring(#tBufferedParams.CSBufferedParams) end,
}
"""


def _ui_source():
    ref = _source(UI_SOURCE)['bbg_ui_route']['installed_sources']['scripts/bbg_uitogameplay.lua']
    path = resolve_path(Path(ref['path'])).resolve()
    data = path.read_bytes()
    if (ref['sha256'] != _UI_SHA256 or len(data) != ref['bytes']
            or hashlib.sha256(data).hexdigest() != _UI_SHA256):
        raise ValueError('Installed BBG trade UI script changed')
    return path, data


def source_dependencies(*, execution_image):
    from .a0_xp2_bbg_trade import source_dependencies as events
    from .paths import resource_root
    from .xp2_trade_table_variant import source_dependencies as table_reader
    from .xp2_script_operation import listener_source_dependencies
    path, _ = _ui_source()
    return {**events(execution_image=execution_image),
            **table_reader(execution_image=execution_image),
            **listener_source_dependencies(execution_image=execution_image),
            resource_root() / UI_SOURCE[0]: UI_SOURCE[1], path: _UI_SHA256}


def _between(raw, start, end):
    if raw.count(start) != 1 or raw.count(end) != 1:
        raise ValueError('Ambiguous BBG trade source anchors')
    first, last = raw.index(start), raw.index(end)
    if first >= last:
        raise ValueError('BBG trade source anchors are out of order')
    return raw[first:last]


def lua_bridge(raw):
    """Use the exact BBG callbacks, including the order of buffered removals."""
    return (_BEFORE + _between(raw, b'local tBufferedParams = {}', b'UIEvents = ExposedMembers.LuaEvents')
            + _between(raw, b'function OnTradeRouteActivityChanged(', b'function OnGovernorChanged(')
            + _AFTER)


def _requests(raw, origin=None):
    """Retain each Lua request owner, including owners saved in the official buffer."""
    if type(raw) is not bytes or len(raw) >= 32768:
        raise ValueError('Invalid BBG trade Lua output')
    if not raw:
        return []
    rows = raw.split(b';')
    if len(rows) > _CAPACITY:
        raise ValueError('BBG trade Lua output exceeds its bound')
    result = []
    for row in rows:
        owner, city, target = map(int, row.split(b','))
        if (row != f'{owner},{city},{target}'.encode('ascii') or not 0 <= owner < 64
                or (origin is not None and (type(origin) is not int or owner != origin))
                or not 0 <= city <= 0x7fffffff or not -0x7fff <= target <= 0x7fff):
            raise ValueError('BBG trade request differs from its native event owner or bounds')
        result.append((owner, city, target))
    return result


class TradeFeedback:
    def __init__(self, continuation, gameplay_child, table_reader):
        self.continuation = continuation
        self.gameplay_child = gameplay_child
        self.table_reader = table_reader
        self.events = deque()
        self.last_sequence = 0
        self.spy_completions = None

    def _enqueue(self, sequence, kind, values):
        if (type(sequence) is not int or sequence <= self.last_sequence
                or len(self.events) >= _CAPACITY):
            raise ValueError('BBG trade feedback sequence is invalid or full')
        self.events.append((sequence, kind, values))
        self.last_sequence = sequence

    def activity(self, sequence, player, origin, city, target, destination):
        self._enqueue(sequence, 'activity', (player, origin, city, target, destination))

    def turn_begin(self, sequence):
        self._enqueue(sequence, 'turn_begin', ())

    def governor(self, sequence, event_player, source):
        self._enqueue(sequence, 'governor', (event_player, source))

    def promotion(self, sequence, event_player, event_unit, source):
        self._enqueue(sequence, 'promotion', (event_player, event_unit, source))

    def spy(self, sequence, player, mission):
        self._enqueue(sequence, 'spy', (player, mission))

    def _evaluate(self, source, name, *, child=None, capacity=32768):
        continuation = self.continuation
        return continuation.runtime.evaluate_text(
            continuation.ui_child if child is None else child, source, name, capacity=capacity)

    def _property(self, player, city):
        return self._evaluate(f"""
local city = CityManager.GetCity({player}, {city})
assert(city ~= nil, 'Missing BBG trade origin city')
local traders = city:GetProperty('CS_TRADERS')
if traders == nil then return 'absent' end
assert(type(traders) == 'table' and #traders <= 1024, 'Invalid BBG trader property')
local values = {{}}
for i, value in ipairs(traders) do
    assert(type(value) == 'number' and value % 1 == 0, 'Invalid BBG trader property entry')
    values[i] = string.format('%d', value)
end
return table.concat(values, ',')
""".encode('ascii'), b'@bbg751_trade_property_readback', child=self.gameplay_child)

    def _deliver(self, sequence, player, city, target):
        from .a0_xp2_bbg_amani import expect_properties
        from .a0_xp2_bbg_trade import expect_city_property
        from .xp2_script_operation import deliver_listener_script_operation

        owner = self.continuation.prefix.event_arguments.consumer
        with self.table_reader.active():
            before = self._property(player, city)
            amani_before, flags_before, positions = self._amani_properties(player)
            with (expect_city_property(owner, player, city),
                  expect_properties(owner, player=player, plots=(positions[city],), allow_player=False)):
                receipt = deliver_listener_script_operation(self.continuation, player, {
                    b'OnStart': b'GameplaySetCSTrader', b'iOriginPlayerID': player,
                    b'iOriginCityID': city, b'iTargetPlayerID': target,
                })
            after = self._property(player, city)
            amani_after, flags_after, after_positions = self._amani_properties(player)
        if receipt.get('native_request_filtered') is True:
            if (receipt['native_archive_delivered'] is not False or after != before
                    or (amani_after, flags_after, after_positions) != (amani_before, flags_before, positions)):
                raise RuntimeError('Filtered BBG trade request changed native properties')
            self.continuation.owner.emit('xp2_bbg_trade_request_filtered', event_sequence=sequence,
                player_id=player, local_player_id=self.continuation.observation['player_id'],
                origin_city_id=city, target_player_id=target,
                native_archive_delivered=False, native_effect_observed=False)
            return None
        if after == b'absent' or receipt['native_archive_delivered'] is not True:
            raise RuntimeError('BBG trade gameplay callback has no native property readback')
        expected = [] if before in (b'absent', b'') else list(map(int, before.split(b',')))
        if target > 0:
            expected.append(target)
        elif target < 0 and -target in expected:
            expected.remove(-target)
        actual = list(map(int, after.split(b','))) if after else []
        if actual != expected:
            raise RuntimeError('BBG trade gameplay property differs after native delivery')
        return dict(event_sequence=sequence, origin_player_id=player, origin_city_id=city,
                    target_player_id=target, native_archive_delivered=True,
                    trader_property_before=before.decode('ascii'),
                    trader_property_after=after.decode('ascii'))

    def _amani_properties(self, player):
        from .xp2_bbg_amani import parse_property, property_source

        raw = self._evaluate(property_source(player), b'@bbg751_amani_property_readback',
                             child=self.gameplay_child, capacity=65537)
        return parse_property(raw, player)

    def _deliver_governor(self, sequence, player, source):
        from .a0_xp2_bbg_amani import expect_properties
        from .xp2_bbg_amani import parse_request
        from .xp2_script_operation import deliver_listener_script_operation

        owner = self.continuation.prefix.event_arguments.consumer
        with self.table_reader.active():
            raw = self._evaluate(source, b'@bbg751_amani_ui_event', capacity=33)
            if not raw:
                return
            request = parse_request(raw, player)
            before, flags_before, positions = self._amani_properties(player)
            with expect_properties(owner, player=player, plots=positions.values(), allow_player=True):
                receipt = deliver_listener_script_operation(self.continuation, player, request.parameters())
            after, flags_after, after_positions = self._amani_properties(player)
        if receipt.get('native_request_filtered') is True:
            if (receipt['native_archive_delivered'] is not False
                    or (after, flags_after, after_positions) != (before, flags_before, positions)):
                raise RuntimeError('Filtered BBG governor request changed native properties')
            self.continuation.owner.emit('xp2_bbg_amani_request_filtered', event_sequence=sequence,
                player_id=player, local_player_id=self.continuation.observation['player_id'],
                native_archive_delivered=False, native_effect_observed=False)
            return
        if after != request or after_positions != positions or receipt['native_archive_delivered'] is not True:
            raise RuntimeError('BBG Amani gameplay callback has no exact native property readback')
        self.continuation.owner.emit('xp2_bbg_amani_gameplay_delivered', event_sequence=sequence,
            player_id=player, city_owner=after.city_owner, city_id=after.city, status=after.status,
            previous_status=None if before is None else before.status,
            plot_flags_before=flags_before, plot_flags_after=flags_after, native_archive_delivered=True)

    def _deliver_promotion(self, sequence, player, event_unit, source):
        from .xp2_bbg_promotion import experience_source, parse_experience, parse_request
        from .xp2_script_operation import deliver_listener_script_operation

        parameters = parse_request(self._evaluate(source, b'@bbg751_promotion_ui_event', capacity=16),
                                   player, event_unit=event_unit)
        unit = parameters[b'iUnitID']
        readback = experience_source(player, unit)
        before = parse_experience(self._evaluate(readback, b'@bbg751_promotion_xp', child=self.gameplay_child,
                                                 capacity=16))
        receipt = deliver_listener_script_operation(self.continuation, player, parameters)
        after = parse_experience(self._evaluate(readback, b'@bbg751_promotion_xp', child=self.gameplay_child,
                                                capacity=16))
        if receipt.get('native_request_filtered') is True:
            if receipt['native_archive_delivered'] is not False or after != before:
                raise RuntimeError('Filtered BBG promotion request changed native experience')
            self.continuation.owner.emit('xp2_bbg_promotion_request_filtered', event_sequence=sequence,
                player_id=player, local_player_id=self.continuation.observation['player_id'],
                unit_id=unit, xp_before=before, xp_after=after,
                native_archive_delivered=False, native_effect_observed=False)
            return
        if (receipt['native_archive_delivered'] is not True or (before is None) != (after is None)
                or (before is not None and after < before)):
            raise RuntimeError('BBG promotion gameplay callback changed its target or decreased experience')
        self.continuation.owner.emit('xp2_bbg_promotion_gameplay_delivered', event_sequence=sequence,
            player_id=player, unit_id=unit, xp_before=before, xp_after=after,
            xp_effect_observed=before != after, native_archive_delivered=True)

    def _deliver_spy(self, sequence, player, event_player, mission):
        from .xp2_bbg_spy import capacity_source, parse_capacity, parse_request
        from .xp2_script_operation import deliver_script_operation

        source = f'return Civ6HostBBGSpy({event_player},{mission})'.encode('ascii')
        parameters = parse_request(self._evaluate(source, b'@bbg751_spy_ui_event', capacity=16),
                                   local_player=player, event_player=event_player, mission=mission)
        if parameters is None:
            return
        readback = capacity_source(player)
        before = parse_capacity(self._evaluate(readback, b'@bbg751_spy_capacity', capacity=16))
        receipt = deliver_script_operation(self.continuation, player, parameters)
        after = parse_capacity(self._evaluate(readback, b'@bbg751_spy_capacity', capacity=16))
        if receipt['native_archive_delivered'] is not True:
            raise RuntimeError('BBG spy gameplay callback has no native delivery')
        self.continuation.owner.emit('xp2_bbg_spy_gameplay_delivered', event_sequence=sequence,
            player_id=player, mission_id=mission, state=parameters[b'State'], capacity_before=before,
            capacity_after=after, capacity_effect_observed=before != after, native_archive_delivered=True)

    def flush(self):
        continuation = self.continuation
        continuation.check(active=True)
        deferred = continuation.prefix.deferred_events
        if continuation.publishing or deferred.pending or deferred._draining_empty_receivers:
            raise ValueError('BBG feedback requires a quiescent native FIFO')
        player = continuation.observation['player_id']
        delivered = []
        requests_processed = 0
        for _ in range(_CAPACITY):
            if not self.events:
                return delivered
            sequence, kind, values = self.events.popleft()
            if kind == 'governor':
                self._deliver_governor(sequence, *values)
                continue
            if kind == 'promotion':
                self._deliver_promotion(sequence, *values)
                continue
            if kind == 'spy':
                self._deliver_spy(sequence, player, *values)
                if self.spy_completions is not None:
                    self.spy_completions.receive(sequence, *values)
                continue
            args = ','.join(str(value) for value in values)
            source = f'return Civ6HostBBGTradeFeedback.{kind}({args})'.encode('ascii')
            raw = self._evaluate(source, b'@bbg751_trade_ui_event')
            origin = values[1] if kind == 'activity' else None
            for request_player, city, target in _requests(raw, origin):
                if kind == 'activity' and (city != values[2] or target not in (values[3], -values[3])):
                    raise ValueError('BBG trade request differs from its native event identity')
                if requests_processed >= _CAPACITY:
                    raise RuntimeError('BBG trade feedback exceeded its delivery bound')
                requests_processed += 1
                receipt = self._deliver(sequence, request_player, city, target)
                if receipt is not None:
                    delivered.append(receipt)
        if self.events:
            raise RuntimeError('BBG trade feedback exceeded its event bound')
        return delivered

    def check_checkpoint(self):
        if self.spy_completions is not None:
            self.spy_completions.check_checkpoint()
        if self.events or self._evaluate(b'return Civ6HostBBGTradeFeedback.buffered()',
                b'@bbg751_trade_buffer_count', capacity=16) != b'0':
            raise ValueError('Cannot checkpoint pending BBG UI trade feedback')


def bind(saved):
    from .a0_xp2_bbg_trade import enable
    from .captured_session_profile import require_bbg_capture
    from .xp2_trade_table_variant import TradeTableVariantReader
    from .xp2_bbg_amani import listener_source
    from .xp2_bbg_promotion import listener_source as promotion_listener_source
    from .xp2_bbg_spy import listener_source as spy_listener_source

    continuation = saved.continuation
    continuation.check(active=False)
    backend, prefix = saved.backend, saved.prefix
    image = backend.core._civ6_host_execution_image
    if getattr(saved, 'trade_diagnostic', False) is not True or continuation.trade_feedback is not None:
        raise ValueError('BBG trade feedback requires one source-qualified capture')
    require_bbg_capture(saved.inputs.official_bundle, execution_image=image)
    contexts = prefix.contexts
    scripts = [pointer for pointer, name in contexts.names.items() if name == b'bbg_script']
    if len(scripts) != 1 or scripts[0] not in contexts.loaded:
        raise ValueError('BBG trade has no live loaded gameplay script')
    gameplay_child = contexts.lifetime._contexts[scripts[0]]
    continuation.runtime.registry.validate(gameplay_child)
    feedback = TradeFeedback(continuation, gameplay_child, TradeTableVariantReader(continuation))
    if getattr(saved, 'espionage_diagnostic', False):
        from .xp2_spy_completion import CompletionQueue
        feedback.spy_completions = CompletionQueue(continuation)
    _, raw = _ui_source()
    continuation.runtime.execute(continuation.ui_child, lua_bridge(raw), b'@bbg751_trade_ui_listener')
    continuation.runtime.execute(continuation.ui_child, listener_source(raw), b'@bbg751_amani_ui_listener')
    continuation.runtime.execute(continuation.ui_child, promotion_listener_source(raw), b'@bbg751_promotion_ui_listener')
    continuation.runtime.execute(continuation.ui_child, spy_listener_source(raw), b'@bbg751_spy_ui_listener')
    enable(prefix.event_arguments.consumer, backend, feedback.activity,
           on_local_turn_begin=feedback.turn_begin, on_governor=feedback.governor,
           on_promotion=feedback.promotion, on_spy=feedback.spy)
    continuation.trade_feedback = feedback

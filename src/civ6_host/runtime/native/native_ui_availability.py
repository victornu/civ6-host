"""Current official UI witnesses, never a certificate for headless menus.

The producer reads actual controls and APIs in the existing UI bridge. This
module validates that closed protocol and pins the installed source contract.
Temporary selection/mode and panel visibility do not prune headless actions.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
import json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_ui_availability.py')))).resolve().parents[1]
SCHEMA = 'civ6rl.ui_availability.v2'
SOURCE_SHA256 = '2a8c39b4e2e8ec2d80f607a721041ae29d444e6b4d9abdcb13ae5f0f2890589a'
LEGACY_SCHEMA = 'civ6rl.ui_availability.v1'
LEGACY_SOURCE_SHA256 = 'd47554d28ef2d584d2eb5d9a5107f669dd925e779fe709960cba8a1af67b068b'
MAX_BYTES = 262144
MAX_CONTROLS = 256
MAX_EVENTS = 1000000
CONTROL_PATHS = {'city_yields': '/InGame/CityPanel/YieldsArea', 'city_citizens': '/InGame/CityPanel/ManageCitizensCheck', 'city_production': '/InGame/CityPanel/ChangeProductionCheck', 'production_queue_tab': '/InGame/ProductionPanel/QueueTab', 'production_queue_container': '/InGame/ProductionPanel/QueueContainer', 'production_mini_tab': '/InGame/ProductionPanel/MiniProductionTab'}
TURN_INTS = {'first_blocker', 'no_blocker', 'stacked_units_blocker', 'needs_orders_blocker', 'units_blocker'}
TURN_BOOLS = {'alive', 'active', 'active_complete', 'can_unready', 'timer_elapsed', 'processing_messages', 'gamecore_busy', 'can_end_turn', 'allow_tactical', 'allow_strategic', 'auto_end_turn', 'city_attack_turn_blocking', 'ready_unit_present', 'city_attack_present', 'city_attack_dismissed', 'blocking_notification_present'}
UNKNOWN_REASONS = {'missing_api', 'read_failed', 'invalid_value', 'missing_enum', 'dependency_unavailable', 'absent', 'missing_control', 'local_state_not_exported'}
TUTORIAL_BOOLS = {'manager_active', 'overlay_enabled', 'any_multiplayer', 'benchmark_enabled'}
SELECTION_INTS = {'manage_citizen_parameter_key', 'manage_citizen_parameter_value'}

def _require(condition, message):
    if not condition:
        raise ValueError('UI availability: ' + message)

def _fields(value, expected):
    _require(type(value) is dict and set(value) == set(expected), 'unexpected fields')

def validate_request(value):
    _fields(value, {'expected_player_id', 'expected_turn'})
    for name, maximum in (('expected_player_id', 63), ('expected_turn', 2147483647)):
        _require(type(value[name]) is int and 0 <= value[name] <= maximum, 'invalid ' + name)
    return dict(value)

def _state(value, kind):
    _require(type(value) is dict, 'state is not an object')
    if value.get('status') == 'unknown':
        _fields(value, {'status', 'reason'})
        _require(value['reason'] in UNKNOWN_REASONS, 'unknown reason')
    else:
        _fields(value, {'status', 'value'})
        _require(value['status'] == 'observed' and type(value['value']) is kind, 'invalid observed type')
        if kind is int:
            _require(-2147483648 <= value['value'] <= 2147483647, 'integer outside native bounds')

def verify_source():
    path = ROOT / 'work/ui-availability/source-v2.json'
    raw = _resolve_resource_path(path).read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256, 'source proof changed')
    value = json.loads(raw)
    _require(value['schema'] == 'civ6rl.ui_availability.source.v2', 'unexpected source contract')
    for row in value['sources'] + value['additions']:
        data = _resolve_resource_path(_resolve_resource_path(Path(row['path']))).read_bytes()
        _require(len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'], 'installed official UI changed: ' + row['relative'])
    return value

def _context_locks(value):
    """Validate observed event arguments, never infer an initial empty list."""
    _fields(value, {'registration', 'events_seen', 'city_panel'})
    registration = value['registration']
    _require(type(registration) is dict, 'invalid observer registration')
    if registration.get('status') == 'unknown':
        _fields(registration, {'status', 'reason'})
        _require(registration['reason'] in {'missing_api', 'read_failed', 'observer_stopped'}, 'invalid observer registration reason')
    else:
        _state(registration, bool)
        _require(registration['value'] is True, 'observer registration cannot be false')
    seen = value['events_seen']
    _require(type(seen) is int and 0 <= seen <= MAX_EVENTS, 'invalid observed event count')
    panel = value['city_panel']
    _require(type(panel) is dict, 'invalid context lock state')
    if panel.get('status') == 'unknown':
        _fields(panel, {'status', 'reason'})
        reason = panel['reason']
        _require(reason in {'no_observed_event', 'event_limit', 'invalid_event', 'observer_stopped'}, 'invalid context lock reason')
        if reason == 'no_observed_event':
            _require(seen == 0, 'initial unknown state has observed events')
        elif reason == 'event_limit':
            _require(seen == MAX_EVENTS, 'event limit not reached')
        elif reason == 'invalid_event':
            _require(seen > 0, 'invalid event was not observed')
    else:
        _fields(panel, {'status', 'event_index', 'controls', 'parameter_was_nil'})
        _require(panel['status'] == 'observed' and type(panel['event_index']) is int and (panel['event_index'] == seen) and (seen > 0), 'invalid lock event index')
        _require(type(panel['parameter_was_nil']) is bool, 'invalid nil argument flag')
        controls = panel['controls']
        _require(type(controls) is list and len(controls) <= MAX_CONTROLS, 'invalid ordered controls')
        for name in controls:
            _require(type(name) is str and '\x00' not in name and (1 <= len(name.encode('utf-8')) <= 128), 'invalid control name')
        _require(not panel['parameter_was_nil'] or not controls, 'nil parameter has controls')
    stopped = registration == {'status': 'unknown', 'reason': 'observer_stopped'}
    _require((panel == {'status': 'unknown', 'reason': 'observer_stopped'}) == stopped, 'stopped observer state differs')
    if not stopped and seen > 0:
        _require(registration == {'status': 'observed', 'value': True}, 'events reported without registered observer')

def validate_response(value, request):
    request = validate_request(request)
    _fields(value, {'schema', 'source_sha256', 'player_id', 'turn', 'tutorial', 'selection', 'controls', 'turn_state', 'read_only', 'atomic_snapshot', 'runtime_context_sources_verified', 'headless_qualified', 'observed_unchanged'})
    legacy = value['schema'] == LEGACY_SCHEMA
    _require(type(value['schema']) is str and type(value['source_sha256']) is str, 'invalid source/schema type')
    _require((value['schema'], value['source_sha256']) in {(SCHEMA, SOURCE_SHA256), (LEGACY_SCHEMA, LEGACY_SOURCE_SHA256)}, 'source/schema differs')
    for key in ('player_id', 'turn'):
        _require(type(value[key]) is int and value[key] == request['expected_' + key], 'stale player/turn')
    for key in ('read_only', 'observed_unchanged'):
        _require(value[key] is True, 'missing stable read: ' + key)
    for key in ('atomic_snapshot', 'runtime_context_sources_verified', 'headless_qualified'):
        _require(value[key] is False, 'overclaim: ' + key)
    tutorial_fields = {'active', 'production_cached_active', 'production_test_mode'}
    if not legacy:
        tutorial_fields |= TUTORIAL_BOOLS | {'user_level', 'context_locks'}
    _fields(value['tutorial'], tutorial_fields)
    _state(value['tutorial']['active'], bool)
    for name in ('production_cached_active', 'production_test_mode'):
        _require(value['tutorial'][name] == {'status': 'unknown', 'reason': 'local_state_not_exported'}, 'unexported production state claimed known')
    if not legacy:
        for name in TUTORIAL_BOOLS:
            _state(value['tutorial'][name], bool)
        _state(value['tutorial']['user_level'], int)
        _context_locks(value['tutorial']['context_locks'])
    selection_fields = {'mode', 'selection_mode', 'city_management_mode', 'city_present', 'city_id', 'city_owner'}
    _fields(value['selection'], selection_fields | (set() if legacy else SELECTION_INTS))
    for key, state in value['selection'].items():
        _state(state, bool if key == 'city_present' else int)
    _fields(value['controls'], CONTROL_PATHS)
    for name, path in CONTROL_PATHS.items():
        row = value['controls'][name]
        _fields(row, {'path', 'disabled', 'hidden'})
        _require(row['path'] == path, 'control path mismatch')
        _state(row['disabled'], bool)
        _state(row['hidden'], bool)
    _fields(value['turn_state'], TURN_BOOLS | TURN_INTS)
    for key, state in value['turn_state'].items():
        _state(state, int if key in TURN_INTS else bool)
    _require(len(json.dumps(value, allow_nan=False).encode('utf-8')) <= (32768 if legacy else MAX_BYTES), 'response exceeds bound')
    return value

def capture_limits(value):
    """Explain the remaining evidence without converting raw fields to masks."""
    validate_response(value, {'expected_player_id': value['player_id'], 'expected_turn': value['turn']})
    unknown = []

    def visit(current, path):
        if type(current) is dict:
            if current.get('status') == 'unknown':
                unknown.append(path)
            else:
                for key, child in current.items():
                    visit(child, path + '.' + key if path else key)
    visit(value, '')
    return {'unknown_fields': sorted(unknown), 'headless_actions_qualified': False, 'current_selection_only': True, 'free_city_selection_must_not_be_pruned': True, 'resolved_ui_profile_required': True, 'passive_event_scope': 'Only replacement arguments received since this observer registered; initial locks remain unknown.', 'scope': 'Current UI witness and observed lock events. Neither certifies imported UI sources or future action availability.'}

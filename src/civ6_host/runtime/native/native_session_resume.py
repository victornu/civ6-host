"""Load a hash-bound native session Save pair through the existing official path.

Scope remains Base Single diagnostic; source DB/script equivalence is unresolved.
Never edits the saved configuration or synthesizes a native turn notification.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from collections.abc import Mapping
from pathlib import Path
import copy, hashlib, json
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_session_resume.py')))).resolve().parents[1]
SCHEMA = 'civ6rl.session_checkpoint939.v1'
CHAIN_SCHEMA = 'civ6rl.session_checkpoint944.v1'
MAX_CHAIN_DEPTH = 64

def plain(value):
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def normalize_reference(value):
    if type(value) is not dict or set(value) not in ({'path', 'sha256'}, {'path', 'sha256', 'bytes'}):
        raise ValueError('Checkpoint requires its explicit path and SHA256')
    path = _resolve_resource_path(Path(value['path']))
    path = _resolve_resource_path(ROOT / path).resolve()
    if not path.is_relative_to(ROOT / 'work') or not _resolve_resource_path(path).is_file():
        raise ValueError('Checkpoint must be an existing private work artifact')
    pin = value['sha256']
    if type(pin) is not str or len(pin) != 64 or any((c not in '0123456789abcdef' for c in pin)):
        raise ValueError('Malformed checkpoint hash')
    if 'bytes' in value and (type(value['bytes']) is not int or _resolve_resource_path(path).stat().st_size != value['bytes']):
        raise ValueError('Checkpoint size differs')
    if not 1 <= _resolve_resource_path(path).stat().st_size <= 4 * 1024 ** 2:
        raise ValueError('Unbounded checkpoint manifest')
    return (path.relative_to(ROOT).as_posix(), pin)

def _manifest_node(reference):
    from civ6_host.runtime.native.native_official_load import SINGLE_PROFILE
    from civ6_host.runtime.native.native_checkpoint_provider import CORE_SHA256
    if type(reference) is not tuple or len(reference) != 2 or any((type(x) is not str for x in reference)) or (normalize_reference(dict(path=reference[0], sha256=reference[1])) != reference):
        raise ValueError('Checkpoint reference must be canonical and immutable')
    m = load_pinned_json(ROOT / reference[0], reference[1])
    if m.get('schema') not in (SCHEMA, CHAIN_SCHEMA) or m.get('input_profile') != SINGLE_PROFILE.name or m.get('origin_official_save_sha256') != SINGLE_PROFILE.save_sha or (m.get('core_sha256') != CORE_SHA256) or (type(m.get('native_save_status')) is not int) or (m['native_save_status'] != 0) or (m.get('stream_closed') is not True) or (m.get('game_version_prefix') != '05000000') or (m.get('jobs_quiescent_unchanged') is not True) or (m.get('full_civ6save_container') is not False) or (m.get('eligible_for_training') is not False) or (type(m.get('observed_game_turn')) is not int) or (not 1 <= m['observed_game_turn'] <= 100000) or (type(m.get('player_id')) is not int) or (m['player_id'] != 0) or (m.get('database_profile') != 'official-cache-phase23-diagnostic') or (m.get('exact_save_database_content_scripts_proven') is not False) or (m.get('dlc_mod_compatibility_proven') is not False):
        raise ValueError('Unsupported native Save pair provenance or scope')
    if set(m['components']) != {'gamecore', 'application_configuration'}:
        raise ValueError('Incomplete Save pair')
    directory = _resolve_resource_path(ROOT / reference[0]).resolve().parent
    for key, row in m['components'].items():
        p = _resolve_resource_path(ROOT / row['path']).resolve()
        if p.parent != directory or type(row['bytes']) is not int or (not 4 <= row['bytes'] <= 32 * 1024 ** 2):
            raise ValueError('Checkpoint component escaped its pair or byte budget')
    if m['observation']['player_id'] != 0 or m['observation']['turn'] != m['observed_game_turn'] or m['decisions']['player_id'] != 0 or (m['decisions']['turn'] != m['observed_game_turn']):
        raise ValueError('Checkpoint observation identity differs')
    return m

def lineage(reference):
    """Validate a bounded chain from the immediate input back to the official root.

    A chained manifest names the actual pair loaded by its producing session.
    No ancestor's hashes are substituted for those immediate input components.
    """
    from civ6_host.runtime.native.native_official_load import SINGLE_PROFILE
    nodes = []
    seen = set()
    for _ in range(MAX_CHAIN_DEPTH + 1):
        m = _manifest_node(reference)
        if reference[0] in seen:
            raise ValueError('Checkpoint ancestry contains a cycle')
        seen.add(reference[0])
        nodes.append((reference, m))
        if m['schema'] == SCHEMA:
            if 'parent_checkpoint' in m or 'lineage_depth' in m or m['input_components_sha256'] != {'gamecore': SINGLE_PROFILE.game_sha, 'application_configuration': SINGLE_PROFILE.config_sha}:
                raise ValueError('Original checkpoint input provenance differs')
            break
        if type(m.get('lineage_depth')) is not int or not 1 <= m['lineage_depth'] <= MAX_CHAIN_DEPTH or (not isinstance(m.get('parent_checkpoint'), Mapping)):
            raise ValueError('Missing or unbounded checkpoint ancestry')
        reference = normalize_reference(plain(m['parent_checkpoint']))
    else:
        raise ValueError('Checkpoint ancestry exceeds its bound')
    dependencies = [_node_dependencies(ref, m) for ref, m in nodes]
    if dependencies[-1][0].get('resume_checkpoint') is not None or dependencies[-1][0].get('initial_turn', 1) != 1:
        raise ValueError('Root checkpoint did not come from an original session')
    for i, (child_ref, child) in enumerate(nodes[:-1]):
        parent_ref, parent = nodes[i + 1]
        if child['lineage_depth'] != len(nodes) - i - 1 or child['input_components_sha256'] != {k: v['sha256'] for k, v in parent['components'].items()} or child['observed_game_turn'] < parent['observed_game_turn']:
            raise ValueError('Checkpoint parent pair, depth or turn differs')
        closure, after, _ = dependencies[i]
        if closure.get('resume_checkpoint') != {'path': parent_ref[0], 'sha256': parent_ref[1]} or closure.get('initial_turn') != parent['observed_game_turn']:
            raise ValueError('Checkpoint ancestry differs from its producing closure')
        before = dependencies[i + 1][1]
        if {k: v['sha256'] for k, v in before['databases'].items()} != {k: v['sha256'] for k, v in after['databases'].items()}:
            raise ValueError('Checkpoint ancestry changed database content')
        old_paths = {_resolve_resource_path(_resolve_resource_path(Path(v['path']))).resolve() for v in before['databases'].values()}
        new_paths = {_resolve_resource_path(_resolve_resource_path(Path(v['path']))).resolve() for v in after['databases'].values()}
        if len(old_paths) != 3 or len(new_paths) != 3 or old_paths & new_paths:
            raise ValueError('Checkpoint ancestors did not use private databases')
    return nodes

def _lineage_json(row):
    path = _resolve_resource_path(ROOT / row['path']).resolve()
    if not path.is_relative_to(ROOT / 'work') or type(row['bytes']) is not int or (not 1 <= row['bytes'] <= 4 * 1024 ** 2) or (_resolve_resource_path(path).stat().st_size != row['bytes']):
        raise ValueError('Checkpoint lineage dependency escaped its bound')
    return load_pinned_json(path, row['sha256'])

def _node_dependencies(reference, m):
    directory = _resolve_resource_path(ROOT / reference[0]).resolve().parent
    row = m['session_closure']
    fixture_row = m['fixture']
    if _resolve_resource_path(ROOT / row['path']).resolve() != directory.parent / 'closure.json':
        raise ValueError('Checkpoint ancestry has a foreign producing session')
    closure = _lineage_json(row)
    fixture = _lineage_json(fixture_row)
    fixture_path = _resolve_resource_path(ROOT / fixture_row['path']).resolve()
    if closure.get('checkpoint_on_close') is not True or closure.get('input_profile') != 'single' or closure.get('database_profile') != m['database_profile'] or (_resolve_resource_path(_resolve_resource_path(Path(closure['fixture']))).resolve() != fixture_path):
        raise ValueError('Checkpoint fixture differs from its producing closure')

    def pinned(path, expected):
        relative = path.relative_to(ROOT)
        keys = {str(relative), relative.as_posix(), str(path), path.as_posix()}
        found = [closure['pins'][k] for k in keys if k in closure['pins']]
        return bool(found) and all((value == expected for value in found))
    if not pinned(fixture_path, fixture_row['sha256']):
        raise ValueError('Producing session did not pin the checkpoint fixture')
    rows = []
    for database in fixture['databases'].values():
        path = _resolve_resource_path(_resolve_resource_path(Path(database['path']))).resolve()
        size = database['size_bytes']
        if path.parent != fixture_path.parent or not path.is_relative_to(ROOT / 'work') or type(size) is not int or (not 1 <= size <= 128 * 1024 ** 2) or (not pinned(path, database['sha256'])):
            raise ValueError('Checkpoint database differs from its producing session')
        rows.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=database['sha256'], bytes=size))
    if len(rows) != 3 or len({r['path'] for r in rows}) != 3:
        raise ValueError('Checkpoint needs three distinct databases')
    return (closure, fixture, rows)

def manifest(reference):
    return lineage(reference)[0][1]

def dependency_rows(reference):
    rows = []
    for ref, m in lineage(reference):
        rows.extend([dict(path=ref[0], sha256=ref[1]), *m['components'].values(), *m['source_proofs'], m['session_closure'], m['fixture']])
        rows.extend(_node_dependencies(ref, m)[2])
    return rows

def save_provenance(inputs, closure):
    from civ6_host.runtime.capture_profiles import LAN_PROFILE
    if inputs.profile is LAN_PROFILE:
        from civ6_host.runtime.network_checkpoint import save_provenance as lan_save_provenance
        return lan_save_provenance(inputs, closure)
    'Bind the output to the actual loaded pair before making any Save call.'
    if inputs.checkpoint is None:
        if closure.get('resume_checkpoint') is not None:
            raise ValueError('Original Save has a resumed closure')
        return dict(schema=SCHEMA)
    validate_inputs(inputs)
    reference = inputs.checkpoint
    parent = manifest(reference)
    if closure.get('resume_checkpoint') != {'path': reference[0], 'sha256': reference[1]}:
        raise ValueError('Save closure differs from the loaded parent')
    depth = parent.get('lineage_depth', 0) + 1
    if depth > MAX_CHAIN_DEPTH:
        raise ValueError('Checkpoint ancestry exceeds its bound')
    return dict(schema=CHAIN_SCHEMA, parent_checkpoint=dict(path=reference[0], sha256=reference[1], bytes=_resolve_resource_path(ROOT / reference[0]).stat().st_size), lineage_depth=depth)

def checked_file(row):
    p = _resolve_resource_path(ROOT / row['path']).resolve()
    if not p.is_relative_to(ROOT) or _resolve_resource_path(p).stat().st_size != row['bytes']:
        raise ValueError('Pair dependency size/path differs')
    raw = _resolve_resource_path(p).read_bytes()
    if sha(raw) != row['sha256']:
        raise ValueError('Pair dependency hash differs: ' + str(p))
    return raw

def validate_inputs(inputs):
    from civ6_host.runtime.native.native_official_load import SINGLE_PROFILE
    if inputs.profile is not SINGLE_PROFILE:
        raise ValueError('Resume must retain its original Single profile')
    m = manifest(inputs.checkpoint)
    for key, raw in (('gamecore', inputs.game), ('application_configuration', inputs.configuration)):
        row = m['components'][key]
        if type(raw) is not bytes or len(raw) != row['bytes'] or sha(raw) != row['sha256']:
            raise ValueError('Resumed immutable component does not match the Save pair')
    if inputs.game[:4] != b'\x05\x00\x00\x00':
        raise ValueError('Wrong native stream version')

def read_inputs(reference):
    from civ6_host.runtime.native.native_official_load import OfficialInputs
    from civ6_host.runtime.native.native_official_load import SINGLE_PROFILE
    from civ6_host.runtime.native.native_official_load import read_inputs as read_original
    from civ6_host.runtime.native.official_configuration import read_provider
    from civ6_host.runtime.native.native_game_configuration import game_configuration_hash
    reference = normalize_reference(reference)
    m = manifest(reference)
    original = read_original(SINGLE_PROFILE)
    configuration = checked_file(m['components']['application_configuration'])
    game = checked_file(m['components']['gamecore'])
    values, end = read_provider(configuration)
    if end != len(configuration):
        raise ValueError('Incomplete resumed B provider')
    roots = {v.key: v for v in values}
    game_root = {v.key: v for v in roots[game_configuration_hash('GAME_ROOT')].children}
    mode = game_root[game_configuration_hash('GAME_MODE')]
    if mode.tag != 3 or mode.scalar() != game_configuration_hash('SINGLEPLAYER'):
        raise ValueError('Resumed game mode changed')
    map_root = {v.key: v for v in roots[game_configuration_hash('MAP_ROOT')].children}
    for name, expected in original.map_values:
        v = map_root.get(game_configuration_hash(name))
        if expected is None:
            if v is not None:
                raise ValueError('Unexpected resumed map configuration')
        elif v is None or v.tag not in (2, 3) or v.flags != 0 or (v.scalar() != expected & 4294967295):
            raise ValueError('Resumed map configuration differs')
    for row in dependency_rows(reference):
        if 'bytes' in row:
            checked_file(row)
    result = OfficialInputs(configuration, game, original.map_values, SINGLE_PROFILE, reference)
    validate_inputs(result)
    return result

def validate_fixture(reference, path):
    m = manifest(reference)
    old = json.loads(checked_file(m['fixture']))
    new = json.loads(_resolve_resource_path(_resolve_resource_path(Path(path))).read_bytes())
    if set(old['databases']) != set(new['databases']):
        raise ValueError('Resumed database set differs')
    paths = set()
    for key, row in new['databases'].items():
        source = old['databases'][key]
        p = _resolve_resource_path(_resolve_resource_path(Path(row['path']))).resolve()
        if row['sha256'] != source['sha256'] or sha(_resolve_resource_path(p).read_bytes()) != source['sha256'] or p == _resolve_resource_path(_resolve_resource_path(Path(source['path']))).resolve() or (p == _resolve_resource_path(_resolve_resource_path(Path(row['source_path']))).resolve()) or (p.parent != _resolve_resource_path(_resolve_resource_path(Path(path))).resolve().parent):
            raise ValueError('Resume needs distinct matching private databases')
        paths.add(p)
    if len(paths) != 3:
        raise ValueError('Resume needs three distinct databases')

def configure_closure(closure, reference):
    m = manifest(reference)
    inputs = read_inputs(dict(path=reference[0], sha256=reference[1]))
    validate_fixture(reference, _resolve_resource_path(Path(closure['fixture'])))
    rows = dependency_rows(reference)
    for row in rows:
        closure['pins'][row['path']] = row['sha256']
    closure['resume_checkpoint'] = dict(path=reference[0], sha256=reference[1])
    closure['initial_turn'] = m['observed_game_turn']

def restore_placement_choice(value):
    """Rehydrate only JSON list encoding; keep native argument order/values."""
    from civ6_host.runtime.native.native_production_placement import _validate_choice
    choice = plain(value)
    if type(choice) is not dict or type(choice.get('arguments')) is not list or any((type(row) is not list or len(row) != 2 for row in choice['arguments'])):
        raise ValueError('Malformed serialized placement arguments')
    choice['arguments'] = tuple((tuple(row) for row in choice['arguments']))
    _validate_choice(choice)
    return choice

def prepare_owner(owner, initial):
    from civ6_host.runtime.native.native_official_postload import validate_owner
    validate_owner(owner, stage='official-public-observed-awaiting-controlled-stop')
    m = manifest(owner.inputs.checkpoint)
    if initial != plain(m['observation']):
        raise RuntimeError('Reloaded player observation differs from its saved witness')
    tracking = {}
    for row in m['host_placement_tracking']:
        key = tuple(row['key'])
        choice = restore_placement_choice(row['choice'])
        if len(key) != 2 or any((type(x) is not int for x in key)) or key != (choice['city_id'], choice['plot_id']) or (choice['player_id'] != 0) or (key in tracking):
            raise ValueError('Saved host placement identity differs')
        tracking[key] = choice
    if len(tracking) > 256:
        raise ValueError('Unbounded saved host placement tracking')
    owner.explicit_placements = tracking
    owner.emit('official_session_checkpoint_observation_matched', checkpoint=owner.inputs.checkpoint, turn=initial['turn'], player_id=0, complete_state_compared=False, strategic_training_ready=False)

def semantic_decisions(value):
    result = plain(value)
    for key in ('episode_id', 'game_generation', 'sequence', 'decision_id'):
        result.pop(key)
    result['candidates'] = sorted((r['action'] for r in result['candidates']), key=lambda v: json.dumps(v, sort_keys=True))
    return result

def _project_optional_choices(expected, actual, options):
    """Comparison-only projection of public queue metadata and explicit opt-ins.

    Never changes the live catalogue or actor mask. Old state/queue entries must
    still compare exactly; newly exposed choices must match the current native
    catalogue. Opt-in changes require the pinned producing closure.
    """
    from civ6_host.runtime.native import native_saved_production_queue as queues
    added = []
    sort = lambda rows: sorted(rows, key=lambda v: json.dumps(v, sort_keys=True))
    if options is not None:
        keys = {'production_queue_diagnostic', 'forced_endturn_diagnostic'}
        if type(options) is not dict or set(options) != {'saved', 'current'} or any((type(options[k]) is not dict or set(options[k]) != keys or any((type(v) is not bool for v in options[k].values())) for k in options)):
            raise ValueError('Checkpoint diagnostic options require exact saved/current booleans')
        if any((options['saved'][k] and (not options['current'][k]) for k in keys)):
            raise ValueError('Checkpoint comparison refuses removing previously exposed choices')
    if 'production_queues' in expected and 'production_queues' in actual:
        old = queues.validate_all(expected['production_queues'], expected['player_id'], expected['turn'])
        new = queues.validate_all(actual['production_queues'], actual['player_id'], actual['turn'])
        if [v['city_id'] for v in old] != [v['city_id'] for v in new]:
            raise RuntimeError('Reloaded production queue city roster differs')
        queues.check_heads(new, actual['production'])
        offers = sort([a for v in new for a in queues.actions(v)])
        selected = [a for a in actual['candidates'] if a['kind'] in queues.FIELDS]
        if actual['candidates'] and selected != offers:
            raise ValueError('Current queue gestures differ from native queue offers')
        enabled_change = False
        for before, after in zip(old, new):
            if 'schema' not in before and after.get('schema') == queues.PUBLIC_SCHEMA:
                after.pop('schema')
                for entry in after['entries']:
                    entry.pop('formation_display')
                if 'queue_public_metadata' not in added:
                    added.append('queue_public_metadata')
            if before['enabled'] != after['enabled']:
                if options is None or options['saved']['production_queue_diagnostic'] or (not options['current']['production_queue_diagnostic']) or (before['enabled'] is not False) or (after['enabled'] is not True):
                    raise ValueError('Unexplained queue gesture enablement change')
                after['enabled'] = False
                after['offers'] = []
                enabled_change = True
        if enabled_change:
            if any((v['enabled'] for v in old)):
                raise ValueError('Mixed prior queue diagnostic state')
            actual['candidates'] = [a for a in actual['candidates'] if a['kind'] not in queues.FIELDS]
            added.append('explicit_queue_gesture_opt_in')
    if options is not None and (not options['saved']['forced_endturn_diagnostic'] and options['current']['forced_endturn_diagnostic']):
        old = [a for a in expected['candidates'] if a['kind'] == 'force_end_turn']
        new = [a for a in actual['candidates'] if a['kind'] == 'force_end_turn']
        if old or new != ([dict(kind='force_end_turn')] if actual['candidates'] else []):
            raise ValueError('Forced-turn opt-in differs from its exact current gesture')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'force_end_turn']
        added.append('explicit_forced_turn_opt_in')
    return added

def _project_multiturn_movement(expected, actual, legacy_movement_multiturn, movement_options):
    """Project only a declared single-turn to multi-turn movement expansion."""
    if movement_options is None:
        if legacy_movement_multiturn is not None:
            raise ValueError('Legacy movement projection requires explicit movement options')
        return []
    keys = {'multiturn_movement_diagnostic'}
    if type(movement_options) is not dict or set(movement_options) != {'saved', 'current'} or any((type(movement_options[k]) is not dict or set(movement_options[k]) != keys or type(movement_options[k]['multiturn_movement_diagnostic']) is not bool for k in movement_options)):
        raise ValueError('Movement comparison options require exact saved/current booleans')
    saved = movement_options['saved']['multiturn_movement_diagnostic']
    current = movement_options['current']['multiturn_movement_diagnostic']
    if saved and (not current):
        raise ValueError('Checkpoint comparison refuses removing previously exposed multi-turn movement')
    if saved == current:
        if legacy_movement_multiturn is not None:
            raise ValueError('Legacy movement projection supplied outside its explicit opt-in transition')
        return []
    from civ6_host.runtime.native.native_saved_actions import validate_movement_action
    from civ6_host.runtime.native.native_saved_actions import digest
    if type(legacy_movement_multiturn) is not list or len(legacy_movement_multiturn) > 4096:
        raise ValueError('Multi-turn movement expansion requires freshly observed legacy movement')
    legacy_ids = set()
    for action in legacy_movement_multiturn:
        validate_movement_action(action, actual['player_id'])
        key = digest(action)
        if key in legacy_ids:
            raise ValueError('Duplicate legacy multi-turn movement observation')
        legacy_ids.add(key)
    current_ids = set()
    for action in actual['candidates']:
        if action.get('kind') != 'move':
            continue
        validate_movement_action(action, actual['player_id'])
        key = digest(action)
        if key in current_ids:
            raise ValueError('Duplicate current multi-turn movement choice')
        current_ids.add(key)
    if not legacy_ids <= current_ids:
        raise ValueError('Multi-turn movement expansion lost a legacy choice')
    actual['candidates'] = sorted([a for a in actual['candidates'] if a.get('kind') != 'move'] + plain(legacy_movement_multiturn), key=lambda v: json.dumps(v, sort_keys=True))
    return ['multiturn_movement_diagnostic']

def _project_movement_information(expected, actual, options, observation, current):
    """Compare old snapshots without inventing the absent native route preview."""
    if options is None:
        if ('movement_preview' in expected) != ('movement_preview' in actual):
            raise ValueError('Movement information requires explicit comparison options')
        return []
    if type(options) is not dict or set(options) != {'saved', 'current'} or any((type(v) is not bool for v in options.values())):
        raise ValueError('Movement information comparison needs exact booleans')
    if options['saved'] and (not options['current']):
        raise ValueError('Cannot remove previously observed movement information')
    if ('movement_preview' in expected) != options['saved'] or ('movement_preview' in actual) != options['current']:
        raise ValueError('Movement preview fields differ from comparison options')
    if options['current']:
        from civ6_host.runtime.native.native_movement_preview import validate_and_index
        validate_and_index(current['movement_preview'], observation, current['candidates'])
    if not options['saved'] and options['current']:
        del actual['movement_preview']
        return ['movement_preview']
    return []

def _project_unit_order_cancel(expected, actual, options):
    """Remove only newly admitted native cancel offers for legacy comparison."""
    from civ6_host.runtime.native import native_saved_unit_orders as orders
    is_cancel = lambda a: a.get('kind') == 'unit_order' and a.get('item_type') == orders.CANCEL_NAME

    def offered(value):
        return [r for r in value.get('unit_orders', {}).get('offers', []) if is_cancel(r['action'])]
    if options is None:
        if offered(expected) != offered(actual):
            raise ValueError('Unit cancel requires explicit comparison options')
        return []
    if type(options) is not dict or set(options) != {'saved', 'current'} or any((type(v) is not bool for v in options.values())):
        raise ValueError('Unit cancel comparison needs exact booleans')
    if options['saved'] and (not options['current']):
        raise ValueError('Cannot remove previously exposed unit cancel choices')
    for label, value in (('saved', expected), ('current', actual)):
        if not options[label] and (offered(value) or any((is_cancel(a) for a in value['candidates']))):
            raise ValueError('Unit cancel offers differ from explicit options')
    if options['current']:
        catalog = orders.validate_catalog(actual['unit_orders'], actual['player_id'], actual['turn'])
        sort = lambda rows: sorted(rows, key=lambda a: json.dumps(a, sort_keys=True))
        native = sort([a for a in orders.actions(catalog) if is_cancel(a)])
        published = sort([a for a in actual['candidates'] if is_cancel(a)])
        if actual['candidates'] and published != native:
            raise ValueError('Unit cancel candidates differ from native offers')
    if not options['saved'] and options['current']:
        actual['unit_orders']['offers'] = [r for r in actual['unit_orders']['offers'] if not is_cancel(r['action'])]
        actual['candidates'] = [a for a in actual['candidates'] if not is_cancel(a)]
        return ['unit_order_cancel_diagnostic']
    return []

def compare_decision_versions(saved, current, *, legacy_movement=None, legacy_movement990=None, legacy_movement_multiturn=None, diagnostic_options=None, movement_options=None, movement_information_options=None, movement_observation=None, unit_order_cancel_options=None, world_input_options=None):
    expected = semantic_decisions(saved)
    actual = semantic_decisions(current)
    added = []
    if world_input_options is not None:
        if type(world_input_options) is not dict or set(world_input_options) != {'saved', 'current'} or any((type(v) is not bool for v in world_input_options.values())):
            raise ValueError('World input comparison requires exact booleans')
        if world_input_options['saved']:
            raise ValueError('Reload of saved world-input selection remains unqualified')
        if 'world_input' in expected or ('world_input' in actual) != world_input_options['current']:
            raise ValueError('World-input fields differ from comparison options')
        if world_input_options['current']:
            from civ6_host.runtime.native import native_world_input as world
            state = world.validate(actual['world_input'], actual['player_id'], actual['turn'])
            if state['selected_unit_id'] is not None or state['war_prompt'] is not None:
                raise ValueError('Legacy reset cannot invent a selected unit or war prompt')
            world.validate_candidates(state, current['candidates'])
            actual['candidates'] = [a for a in actual['candidates'] if a.get('kind') not in world.FIELDS]
            del actual['world_input']
            added.append('world_input_diagnostic')
    elif ('world_input' in expected) != ('world_input' in actual):
        raise ValueError('World input requires explicit comparison options')
    added.extend(_project_movement_information(expected, actual, movement_information_options, movement_observation, current))
    added.extend(_project_unit_order_cancel(expected, actual, unit_order_cancel_options))
    added.extend(_project_optional_choices(expected, actual, diagnostic_options))
    added.extend(_project_multiturn_movement(expected, actual, legacy_movement_multiturn, movement_options))
    older_movement = tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962, 963, 964, 965, 967, 968, 972, 980, 982, 983, 988)))
    if actual['schema'] == 'civ6rl.saved_decisions.city_management.v1' and expected['schema'] in older_movement + tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (989, 990, 999, 1000))):
        from civ6_host.runtime.native import native_saved_citizens as citizens
        catalogs = actual.get('citizen_catalogs')
        if type(catalogs) is not list or len(catalogs) > 4096 or 'citizen_catalogs' in expected:
            raise ValueError('Invalid citizen catalogue version transition')
        cities = set()
        offers = []
        for catalog in catalogs:
            citizens.validate_catalog(catalog, actual['player_id'], actual['turn'])
            if catalog['city_id'] in cities:
                raise ValueError('Duplicate migrated citizen city')
            cities.add(catalog['city_id'])
            offers.extend(citizens.actions(catalog))
        if cities != {c['city_id'] for c in actual['purchases']}:
            raise ValueError('Migrated citizen roster differs from own cities')
        selected = [a for a in actual['candidates'] if a['kind'] == 'city_citizen']
        if actual['candidates'] and sorted(selected, key=lambda a: json.dumps(a, sort_keys=True)) != sorted(offers, key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Migrated citizen gesture set differs')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'city_citizen']
        del actual['citizen_catalogs']
        actual['schema'] = 'civ6rl.saved_decisions1000.v1'
        added.append('city_management')
    if actual['schema'] == 'civ6rl.saved_decisions1000.v1' and expected['schema'] in older_movement + ('civ6rl.saved_decisions989.v1', 'civ6rl.saved_decisions990.v1', 'civ6rl.saved_decisions999.v1'):
        from civ6_host.runtime.native import native_saved_city_focus1000 as focus
        catalogs = actual.get('city_focus_catalogs')
        if type(catalogs) is not list or len(catalogs) > 4096 or 'city_focus_catalogs' in expected:
            raise ValueError('Invalid focus catalogue version transition')
        cities = set()
        offers = []
        for catalog in catalogs:
            focus.validate_catalog(catalog, actual['player_id'], actual['turn'])
            if catalog['city_id'] in cities:
                raise ValueError('Duplicate migrated focus city')
            cities.add(catalog['city_id'])
            offers.extend(focus.actions(catalog))
        if cities != {c['city_id'] for c in actual['purchases']}:
            raise ValueError('Migrated focus roster differs from own cities')
        selected = [a for a in actual['candidates'] if a['kind'] == 'city_focus']
        if actual['candidates'] and sorted(selected, key=lambda a: json.dumps(a, sort_keys=True)) != sorted(offers, key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Migrated focus gesture set differs')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'city_focus']
        del actual['city_focus_catalogs']
        actual['schema'] = 'civ6rl.saved_decisions999.v1'
        added.append('city_focus1000')
    if expected['schema'] in older_movement + ('civ6rl.saved_decisions989.v1', 'civ6rl.saved_decisions990.v1') and actual['schema'] == 'civ6rl.saved_decisions999.v1':
        from civ6_host.runtime.native.native_saved_actions import validate_movement_action
        from civ6_host.runtime.native.native_saved_actions import digest
        if type(legacy_movement990) is not list or len(legacy_movement990) > 4096:
            raise ValueError('Movement999 migration requires freshly observed schema990 movement')
        legacy_ids = set()
        for action in legacy_movement990:
            validate_movement_action(action, actual['player_id'])
            key = digest(action)
            if key in legacy_ids:
                raise ValueError('Duplicate schema990 movement observation')
            legacy_ids.add(key)
        current_ids = set()
        for action in actual['candidates']:
            if action.get('kind') != 'move':
                continue
            validate_movement_action(action, actual['player_id'])
            key = digest(action)
            if key in current_ids:
                raise ValueError('Duplicate current movement observation')
            current_ids.add(key)
        if not legacy_ids <= current_ids:
            raise ValueError('Own-city movement lost a schema990 choice')
        actual['candidates'] = sorted([a for a in actual['candidates'] if a.get('kind') != 'move'] + plain(legacy_movement990), key=lambda v: json.dumps(v, sort_keys=True))
        actual['schema'] = 'civ6rl.saved_decisions990.v1'
        added.append('own_city_movement999')
    elif legacy_movement990 is not None:
        raise ValueError('Schema990 movement supplied outside its explicit version transition')
    if expected['schema'] in older_movement + ('civ6rl.saved_decisions989.v1',) and actual['schema'] == 'civ6rl.saved_decisions990.v1':
        from civ6_host.contracts.plot_display990 import validate_and_index
        validate_and_index(actual.get('plot_info'), actual['player_id'], actual['turn'], actual['player_map'])
        if 'plot_info' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes plot display information')
        del actual['plot_info']
        actual['schema'] = 'civ6rl.saved_decisions989.v1'
        added.append('plot_info')
    if expected['schema'] in older_movement and actual['schema'] == 'civ6rl.saved_decisions989.v1':
        from civ6_host.runtime.native.native_saved_actions import validate_movement_action
        from civ6_host.runtime.native.native_saved_actions import digest
        if type(legacy_movement) is not list or len(legacy_movement) > 4096:
            raise ValueError('Movement989 migration requires freshly observed legacy movement')
        legacy_ids = set()
        for action in legacy_movement:
            validate_movement_action(action, actual['player_id'])
            key = digest(action)
            if key in legacy_ids:
                raise ValueError('Duplicate legacy movement observation')
            legacy_ids.add(key)
        current_moves = [a for a in actual['candidates'] if a.get('kind') == 'move']
        current_ids = set()
        for action in current_moves:
            validate_movement_action(action, actual['player_id'])
            key = digest(action)
            if key in current_ids:
                raise ValueError('Duplicate current movement observation')
            current_ids.add(key)
        if not legacy_ids <= current_ids:
            raise ValueError('Expanded native movement lost a legacy choice')
        actual['candidates'] = sorted([a for a in actual['candidates'] if a.get('kind') != 'move'] + plain(legacy_movement), key=lambda v: json.dumps(v, sort_keys=True))
        actual['schema'] = 'civ6rl.saved_decisions988.v1'
        added.append('ordinary_improvement_movement989')
    elif legacy_movement is not None:
        raise ValueError('Legacy movement supplied outside its explicit version transition')
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962, 963, 964, 965, 967, 968, 972, 980, 982, 983))) and actual['schema'] == 'civ6rl.saved_decisions988.v1':
        from civ6_host.contracts.production_info988 import validate
        validate(actual.get('production_info'), actual['player_id'], actual['turn'], candidates=current['candidates'])
        if 'production_info' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes production information')
        del actual['production_info']
        actual['schema'] = 'civ6rl.saved_decisions983.v1'
        added.append('production_info')
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962, 963, 964, 965, 967, 968, 972, 980, 982))) and actual['schema'] == 'civ6rl.saved_decisions983.v1':
        from civ6_host.contracts.research_info983 import validate
        validate(actual.get('research_info'), actual['player_id'], actual['turn'], research=actual['research'], candidates=current['candidates'])
        if 'research_info' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes research information')
        del actual['research_info']
        actual['schema'] = 'civ6rl.saved_decisions982.v1'
        added.append('research_info')
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962, 963, 964, 965, 967, 968, 972, 980))) and actual['schema'] == 'civ6rl.saved_decisions982.v1':
        from civ6_host.contracts.yield_display982 import validate
        validate(actual.get('yield_display'), actual['player_id'], actual['turn'])
        if 'yield_display' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes yield display')
        del actual['yield_display']
        actual['schema'] = 'civ6rl.saved_decisions980.v1'
        added.append('yield_display')
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962, 963, 964, 965, 967, 968, 972))) and actual['schema'] == 'civ6rl.saved_decisions980.v1':
        from civ6_host.runtime.native import native_saved_treasury980 as treasury
        treasury.validate(actual.get('treasury'), actual['player_id'], actual['turn'])
        if 'treasury' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes treasury details')
        del actual['treasury']
        actual['schema'] = 'civ6rl.saved_decisions972.v1'
        added.append('treasury')
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962, 963, 964, 965, 967, 968))) and actual['schema'] == 'civ6rl.saved_decisions972.v1':
        from civ6_host.runtime.native import native_saved_research_progress971 as research_progress
        research_progress.validate(actual.get('research_progress'), actual['player_id'], actual['turn'], actual['research'])
        if 'research_progress' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes research progress')
        del actual['research_progress']
        actual['schema'] = 'civ6rl.saved_decisions968.v1'
        added.append('research_progress')
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962, 963, 964, 965, 967))) and actual['schema'] == 'civ6rl.saved_decisions968.v1':
        from civ6_host.runtime.native import native_saved_trade_origin as origin
        value = origin.validate_catalog(actual.get('trade_origins'), actual['player_id'], actual['turn'])
        if 'trade_origins' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes trade origins')
        new = [a for a in actual['candidates'] if a['kind'] == 'change_trade_origin']
        if new != sorted(origin.actions(value), key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Added origin actions differ from native offers')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'change_trade_origin']
        del actual['trade_origins']
        actual['schema'] = 'civ6rl.saved_decisions967.v1'
        added.extend(['trade_origins', 'change_trade_origin_candidates'])
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962, 963, 964, 965))) and actual['schema'] == 'civ6rl.saved_decisions967.v1':
        from civ6_host.runtime.native import native_saved_trade as trade
        value = trade.validate_catalog(actual.get('trade_routes'), actual['player_id'], actual['turn'])
        if 'trade_routes' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes trade routes')
        new = [a for a in actual['candidates'] if a['kind'] == 'make_trade_route']
        if new != sorted(trade.actions(value), key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Added trade actions differ from native offers')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'make_trade_route']
        del actual['trade_routes']
        actual['schema'] = 'civ6rl.saved_decisions965.v1'
        added.extend(['trade_routes', 'make_trade_route_candidates'])
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962, 963, 964))) and actual['schema'] == 'civ6rl.saved_decisions965.v1':
        from civ6_host.runtime.native import native_saved_placement as placed
        offers = placed.validate_offers(actual.get('placement_offers'), player_id=actual['player_id'])
        if 'placement_offers' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes placement offers')
        occupied = {r['city_id'] for r in actual['production'].get('cities', []) if r['queue_size'] > 0}
        actions = [a for a in actual['candidates'] if a['kind'] in ('production_placement', 'production_resume')]
        if any((a not in offers for a in actions)):
            raise ValueError('Added placements differ from native offers')
        actual['candidates'] = [a for a in actual['candidates'] if not (a['kind'] == 'production_resume' or (a['kind'] == 'production_placement' and a['city_id'] in occupied))]
        del actual['placement_offers']
        actual['schema'] = 'civ6rl.saved_decisions964.v1'
        added.extend(['placement_offers', 'production_resume_and_occupied_placement_candidates'])
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962, 963))) and actual['schema'] == 'civ6rl.saved_decisions964.v1':
        from civ6_host.runtime.native import native_saved_district_shot as shot
        value = shot.validate_catalog(actual.get('district_shots'), actual['player_id'], actual['turn'])
        if 'district_shots' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes district shots')
        new = [a for a in actual['candidates'] if a['kind'] == 'district_range_attack']
        if new != sorted(shot.actions(value), key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Added district shots differ from native offers')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'district_range_attack']
        del actual['district_shots']
        actual['schema'] = 'civ6rl.saved_decisions963.v1'
        added.extend(['district_shots', 'district_range_attack_candidates'])
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962))) and actual['schema'] == 'civ6rl.saved_decisions963.v1':
        from civ6_host.runtime.native import native_saved_city_shot as shot
        value = shot.validate_catalog(actual.get('city_shots'), actual['player_id'], actual['turn'])
        if 'city_shots' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes city shots')
        new = [a for a in actual['candidates'] if a['kind'] == 'city_range_attack']
        if new != sorted(shot.actions(value), key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Added city shots differ from native offers')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'city_range_attack']
        del actual['city_shots']
        actual['schema'] = 'civ6rl.saved_decisions962.v1'
        added.extend(['city_shots', 'city_range_attack_candidates'])
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961))) and actual['schema'] == 'civ6rl.saved_decisions962.v1':
        from civ6_host.runtime.native import native_saved_production_queue as queues
        values = queues.validate_all(actual.get('production_queues'), actual['player_id'], actual['turn'])
        queues.check_heads(values, actual['production'])
        if 'production_queues' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes queue entries')
        new = [a for a in actual['candidates'] if a['kind'] in queues.FIELDS]
        offers = [a for v in values for a in queues.actions(v)]
        if new != sorted(offers, key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Added queue actions differ from native offers')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] not in queues.FIELDS]
        del actual['production_queues']
        actual['schema'] = 'civ6rl.saved_decisions961.v1'
        added.extend(['production_queues', 'production_queue_candidates'])
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960))) and actual['schema'] == 'civ6rl.saved_decisions961.v1':
        if actual['production'] != expected['production']:
            raise RuntimeError('Saved production changed during replacement projection')
        occupied = {r['city_id'] for r in actual['production'].get('cities', []) if r['queue_size'] > 0}
        actual['candidates'] = [a for a in actual['candidates'] if not (a['kind'] == 'production' and a['city_id'] in occupied)]
        actual['schema'] = 'civ6rl.saved_decisions960.v1'
        added.append('occupied_production_candidates')
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958))) and actual['schema'] == 'civ6rl.saved_decisions960.v1':
        from civ6_host.runtime.native.native_saved_unit_upgrade import validate_catalog
        from civ6_host.runtime.native.native_saved_unit_upgrade import actions
        upgrades = validate_catalog(actual.get('unit_upgrades'), actual['player_id'], actual['turn'])
        if 'unit_upgrades' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes upgrades')
        new = [a for a in actual['candidates'] if a['kind'] == 'upgrade_unit']
        if new != sorted(actions(upgrades), key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Added upgrades differ from native offers')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'upgrade_unit']
        del actual['unit_upgrades']
        actual['schema'] = 'civ6rl.saved_decisions958.v1'
        added.extend(['unit_upgrades', 'upgrade_unit_candidates'])
    if expected['schema'] in tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957))) and actual['schema'] == 'civ6rl.saved_decisions958.v1':
        from civ6_host.runtime.native.native_saved_unit_orders import validate_catalog
        from civ6_host.runtime.native.native_saved_unit_orders import actions
        orders = validate_catalog(actual.get('unit_orders'), actual['player_id'], actual['turn'])
        if 'unit_orders' in expected:
            raise ValueError('Legacy catalogue unexpectedly contains unit orders')
        new = [a for a in actual['candidates'] if a['kind'] == 'unit_order']
        if new != sorted(actions(orders), key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Added unit orders differ from native offers')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'unit_order']
        del actual['unit_orders']
        actual['schema'] = 'civ6rl.saved_decisions957.v1'
        added.extend(['unit_orders', 'unit_order_candidates'])
    if expected['schema'] in ('civ6rl.saved_decisions938.v1', 'civ6rl.saved_decisions942.v1', 'civ6rl.saved_decisions953.v1', 'civ6rl.saved_decisions954.v1', 'civ6rl.saved_decisions955.v1', 'civ6rl.saved_decisions956.v1') and actual['schema'] == 'civ6rl.saved_decisions957.v1':
        from civ6_host.runtime.native.native_saved_envoy_panel import validate_catalog
        from civ6_host.runtime.native.native_saved_envoy_panel import actions
        from civ6_host.runtime.native.native_saved_envoys import validate_catalog as validate_influence
        panel = validate_catalog(actual.get('envoy_panel'), actual['turn'], player_id=actual['player_id'])
        influence = validate_influence(actual['envoys'], actual['turn'], player_id=actual['player_id'])
        if 'envoy_panel' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes envoy panel')
        new = [a for a in actual['candidates'] if a['kind'] == 'review_envoys']
        if new != actions(panel, influence):
            raise ValueError('Added envoy panel actions differ from native access')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'review_envoys']
        del actual['envoy_panel']
        actual['schema'] = 'civ6rl.saved_decisions956.v1'
        added.extend(['envoy_panel', 'envoy_panel_candidates'])
    if expected['schema'] in ('civ6rl.saved_decisions938.v1', 'civ6rl.saved_decisions942.v1', 'civ6rl.saved_decisions953.v1', 'civ6rl.saved_decisions954.v1', 'civ6rl.saved_decisions955.v1') and actual['schema'] == 'civ6rl.saved_decisions956.v1':
        from civ6_host.runtime.native.native_saved_religion import validate_catalog
        from civ6_host.runtime.native.native_saved_religion import actions
        from civ6_host.runtime.native.native_saved_religion import FIELDS
        v = validate_catalog(actual.get('religion'), actual['turn'], player_id=actual['player_id'])
        if 'religion' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes religion')
        new = [a for a in actual['candidates'] if a['kind'] in FIELDS]
        if new != sorted(actions(v), key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Added religion actions differ from the native offers')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] not in FIELDS]
        del actual['religion']
        actual['schema'] = 'civ6rl.saved_decisions955.v1'
        added.extend(['religion', 'religion_candidates'])
    if expected['schema'] in ('civ6rl.saved_decisions938.v1', 'civ6rl.saved_decisions942.v1', 'civ6rl.saved_decisions953.v1', 'civ6rl.saved_decisions954.v1') and actual['schema'] == 'civ6rl.saved_decisions955.v1':
        from civ6_host.runtime.native.native_saved_great_people import validate_catalog
        from civ6_host.runtime.native.native_saved_great_people import actions
        v = validate_catalog(actual.get('great_people'), actual['turn'], player_id=actual['player_id'])
        if 'great_people' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes Great People')
        new = [a for a in actual['candidates'] if a['kind'] == 'recruit_great_person']
        if new != sorted(actions(v), key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Added Great Person actions differ from the native offers')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'recruit_great_person']
        del actual['great_people']
        actual['schema'] = 'civ6rl.saved_decisions954.v1'
        added.extend(['great_people', 'great_person_candidates'])
    if expected['schema'] in ('civ6rl.saved_decisions938.v1', 'civ6rl.saved_decisions942.v1', 'civ6rl.saved_decisions953.v1') and actual['schema'] == 'civ6rl.saved_decisions954.v1':
        from civ6_host.runtime.native.native_saved_envoys import validate_catalog
        from civ6_host.runtime.native.native_saved_envoys import actions
        v = validate_catalog(actual.get('envoys'), actual['turn'], player_id=actual['player_id'])
        if 'envoys' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes envoys')
        new = [a for a in actual['candidates'] if a['kind'] in ('send_envoy', 'retain_envoys')]
        if new != sorted(actions(v), key=lambda a: json.dumps(a, sort_keys=True)):
            raise ValueError('Added envoy actions differ from the native offers')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] not in ('send_envoy', 'retain_envoys')]
        del actual['envoys']
        actual['schema'] = 'civ6rl.saved_decisions953.v1'
        added.extend(['envoys', 'envoy_candidates'])
    if expected['schema'] in ('civ6rl.saved_decisions938.v1', 'civ6rl.saved_decisions942.v1') and actual['schema'] == 'civ6rl.saved_decisions953.v1':
        from civ6_host.runtime.native.native_saved_promotions import validate_catalog
        p = validate_catalog(actual.get('unit_promotions'), actual['player_id'], actual['turn'])
        if 'unit_promotions' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes promotions')
        new = [a for a in actual['candidates'] if a['kind'] == 'promote_unit']
        sort = lambda rows: sorted(rows, key=lambda v: json.dumps(v, sort_keys=True))
        if new != sort(p['offers']):
            raise ValueError('Added promotion actions differ from the native offers')
        actual['candidates'] = [a for a in actual['candidates'] if a['kind'] != 'promote_unit']
        del actual['unit_promotions']
        actual['schema'] = 'civ6rl.saved_decisions942.v1'
        added.extend(['unit_promotions', 'promotion_candidates'])
    if expected['schema'] == 'civ6rl.saved_decisions938.v1' and actual['schema'] == 'civ6rl.saved_decisions942.v1':
        from civ6_host.runtime.native.native_saved_combat import validate_queued_orders
        validate_queued_orders(actual.get('queued_orders'), actual['player_id'], actual['turn'], actual['player_map']['width'], actual['player_map']['height'], [u['unit_id'] for u in actual['combat_units']])
        if 'queued_orders' in expected:
            raise ValueError('Legacy catalogue unexpectedly includes queued orders')
        del actual['queued_orders']
        actual['schema'] = expected['schema']
        added.append('queued_orders')
    if actual != expected:
        different = sorted((k for k in set(expected) | set(actual) if actual.get(k) != expected.get(k)))
        raise RuntimeError('Reloaded native decision catalogue differs: ' + str(different))
    return dict(saved_schema=saved['schema'], current_schema=current['schema'], saved_decision_fields_matched=True, added_native_observation_fields=added, all_current_fields_compared_to_saved=not added)

def compare_loaded_decisions(owner, observation, decisions):
    m = manifest(owner.inputs.checkpoint)
    if observation != plain(m['observation']):
        raise RuntimeError('Reloaded decision observation changed')
    legacy_movement = None
    legacy_movement990 = None
    producing = _lineage_json(m['session_closure'])
    movement_information_options = dict(saved=producing.get('movement_information_diagnostic', False), current=getattr(owner, 'movement_information_diagnostic', False))
    unit_order_cancel_options = dict(saved=producing.get('unit_order_cancel_diagnostic', False), current=getattr(owner, 'unit_order_cancel_diagnostic', False))
    world_input_options = dict(saved=producing.get('world_input_diagnostic', False), current=getattr(owner, 'world_input_diagnostic', False))
    saved_multiturn = producing.get('multiturn_movement_diagnostic', False)
    current_multiturn = getattr(owner, 'multiturn_movement_diagnostic', False)
    if type(saved_multiturn) is not bool or type(current_multiturn) is not bool:
        raise ValueError('Checkpoint movement option is not an explicit Boolean')
    movement_options = dict(saved={'multiturn_movement_diagnostic': saved_multiturn}, current={'multiturn_movement_diagnostic': current_multiturn})
    if saved_multiturn and (not current_multiturn):
        raise ValueError('Checkpoint comparison refuses removing previously exposed multi-turn movement')
    legacy_movement_multiturn = None
    prior_movement_schemas = tuple(('civ6rl.saved_decisions' + str(n) + '.v1' for n in (938, 942, 953, 954, 955, 956, 957, 958, 960, 961, 962, 963, 964, 965, 967, 968, 972, 980, 982, 983, 988)))
    queries = []
    if decisions['schema'] in ('civ6rl.saved_decisions999.v1', 'civ6rl.saved_decisions1000.v1', 'civ6rl.saved_decisions.city_management.v1') and m['decisions']['schema'] in prior_movement_schemas + ('civ6rl.saved_decisions989.v1', 'civ6rl.saved_decisions990.v1'):
        queries.append(('990', True, b'@reload_legacy_movement999'))
    if decisions['schema'] in ('civ6rl.saved_decisions989.v1', 'civ6rl.saved_decisions990.v1', 'civ6rl.saved_decisions999.v1', 'civ6rl.saved_decisions1000.v1', 'civ6rl.saved_decisions.city_management.v1') and m['decisions']['schema'] in prior_movement_schemas:
        queries.append(('988', False, b'@reload_legacy_movement989'))
    if queries:
        from civ6_host.runtime.native import native_unit_movement as movement
        from civ6_host.runtime.native.native_saved_actions import boundary
        from civ6_host.runtime.native.native_saved_actions import movement_action
        from civ6_host.runtime.native.native_saved_actions import snapshot
        from civ6_host.runtime.native.native_player_observation import observe_player
        pid = observation['player_id']
        turn = observation['turn']
        p = boundary(owner, player_id=pid)
        for version, allow_improvements, tag in queries:
            before = snapshot(owner, 'before')
            catalog = movement.parse_candidates(p.runtime.evaluate_text(p.ui_child, movement.candidate_source(pid, turn, allow_improvements=allow_improvements, allow_own_cities=False), tag, capacity=524289), pid, turn)
            actions = [movement_action(row) for row in catalog['choices']]
            owner.control(empty=True)
            if snapshot(owner, 'after') != before:
                raise RuntimeError('Legacy movement observation changed native scheduler')
            if observe_player(p.runtime, p.ui_child, pid) != observation:
                raise RuntimeError('Legacy movement observation crossed public state')
            if version == '990':
                legacy_movement990 = actions
            else:
                legacy_movement = actions
    if not saved_multiturn and current_multiturn:
        from civ6_host.runtime.native import native_unit_movement as movement
        from civ6_host.runtime.native.native_saved_actions import boundary
        from civ6_host.runtime.native.native_saved_actions import movement_action
        from civ6_host.runtime.native.native_saved_actions import snapshot
        from civ6_host.runtime.native.native_player_observation import observe_player
        pid = observation['player_id']
        turn = observation['turn']
        p = boundary(owner, player_id=pid)
        if p.runtime.evaluate_text(p.game_child, movement.guard_case(), b'@reload_multiturn_movement_guard') != b'unit-movement-guards-ok':
            raise RuntimeError('Native multi-turn movement guard failed')
        before = snapshot(owner, 'before')
        catalog = movement.parse_candidates(p.runtime.evaluate_text(p.ui_child, movement.candidate_source(pid, turn, allow_improvements=True, allow_own_cities=True, allow_multiturn=False), b'@reload_legacy_movement_multiturn', capacity=524289), pid, turn)
        legacy_movement_multiturn = [movement_action(row) for row in catalog['choices']]
        owner.control(empty=True)
        if snapshot(owner, 'after') != before:
            raise RuntimeError('Legacy multi-turn movement observation changed native scheduler')
        if observe_player(p.runtime, p.ui_child, pid) != observation:
            raise RuntimeError('Legacy multi-turn movement observation crossed public state')
    option_keys = ('production_queue_diagnostic', 'forced_endturn_diagnostic')
    options = dict(saved={k: producing.get(k, False) for k in option_keys}, current={k: getattr(owner, k, False) for k in option_keys})
    try:
        comparison = compare_decision_versions(plain(m['decisions']), decisions, legacy_movement=legacy_movement, legacy_movement990=legacy_movement990, legacy_movement_multiturn=legacy_movement_multiturn, diagnostic_options=options, movement_options=movement_options, movement_information_options=movement_information_options, movement_observation=observation, unit_order_cancel_options=unit_order_cancel_options, world_input_options=world_input_options)
    except (ValueError, RuntimeError):
        owner.emit('official_session_checkpoint_decisions_mismatch', checkpoint=owner.inputs.checkpoint, saved_decisions=plain(m['decisions']), current_decisions=decisions, diagnostic_options=options, movement_options=movement_options, legacy_movement_native=legacy_movement, legacy_movement990_native=legacy_movement990, legacy_movement_multiturn_native=legacy_movement_multiturn)
        raise
    owner.emit('official_session_checkpoint_decisions_matched', checkpoint=owner.inputs.checkpoint, turn=observation['turn'], candidate_count=len(decisions['candidates']), episode_identity_renewed=True, decision_version_comparison=comparison, diagnostic_option_comparison=options, movement_option_comparison=movement_options, movement_information_comparison=movement_information_options, unit_order_cancel_comparison=unit_order_cancel_options, world_input_comparison=world_input_options, legacy_movement_native=legacy_movement, legacy_movement990_native=legacy_movement990, legacy_movement_multiturn_native=legacy_movement_multiturn, candidate_ids_rebound=True, complete_action_space=False, strategic_training_ready=False)

"""Marshal explicit visible placements using existing native adapters."""
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _PLACEMENT_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_production_placement as placement
from civ6_host.runtime.native import native_district_completion as districts
from civ6_host.runtime.native import native_wonder_completion as wonders
FIELDS = {'kind', 'city_id', 'category', 'index', 'hash', 'item_type', 'mode', 'plot_id', 'x', 'y'}
RESUME_FIELDS = {'kind', 'city_id', 'category', 'index', 'hash', 'item_type'}

def action(city_id, row, *, player_id=0):
    pid = _player_id(player_id)
    if row.get('player_id') != pid:
        raise ValueError('Placement row belongs to another actor')
    if row['mode'] == 'resume':
        return dict(kind='production_resume', city_id=city_id, category=row['kind'], **{k: row[k] for k in ('index', 'hash', 'item_type')})
    return dict(kind='production_placement', city_id=city_id, category=row['kind'], **{k: row[k] for k in ('index', 'hash', 'item_type', 'mode', 'plot_id', 'x', 'y')})

def actions(catalog, city_id, *, player_id=0):
    pid = _player_id(player_id)
    if type(catalog) is not dict or type(catalog.get('player_id')) is not int or catalog['player_id'] != pid or (catalog.get('city_id') != city_id):
        raise ValueError('Placement catalogue belongs to another actor or city')
    return [action(city_id, placement.choose(catalog, r['kind'], r['index'], r['plot_id']), player_id=pid) for r in catalog['candidates']]

def catalog(prefix, city_id, turn, *, player_id=0, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    pid = _player_id(player_id)
    return placement.parse_catalog(prefix.runtime.evaluate_text(prefix.ui_child, placement.catalog_source(pid, city_id, turn, visible_only=True, replace_current=True, core_sha256=core_sha256), b'@explicit_placement_catalog', capacity=65536), pid, city_id, turn)

def selected(prefix, value, turn, *, player_id=0, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    pid = _player_id(player_id)
    validate_action(value, player_id=pid)
    current = catalog(prefix, value['city_id'], turn, player_id=pid, core_sha256=core_sha256)
    choice = placement.choose(current, value['category'], value['index'], value.get('plot_id', -1))
    if choice['player_id'] != pid or action(value['city_id'], choice, player_id=pid) != value:
        raise RuntimeError('Placement definition, mode or coordinates changed')
    return choice

def item_progress(prefix, choice, *, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    """Read the native progress for a selected type, even while it is inactive."""
    header = placement._selection_source(choice, visible_only=True, replace_current=True, core_sha256=core_sha256)
    raw = prefix.runtime.evaluate_text(prefix.ui_child, header + "\nlocal method=kind=='district' and 'GetDistrictProgress' or 'GetBuildingProgress'\nlocal value=queue[method](queue,index)\nassert(type(value)=='number' and value%1==0 and value>=0 and value<=2147483647,'invalid inactive production progress')\nready()\nreturn table.concat({'resume-progress-v1',n(pid),n(cityID),n(expectedTurn),kind,n(index),n(hash),n(value)},'|')\n".encode(), b'@explicit_placed_item_progress')
    expected = '|'.join((str(v) for v in ('resume-progress-v1', choice['player_id'], choice['city_id'], choice['current_game_turn'], choice['kind'], choice['index'], choice['hash']))) + '|'
    if type(raw) is not bytes or not raw.startswith(expected.encode()) or len(raw) > 256:
        raise ValueError('Foreign inactive progress')
    value = raw[len(expected):].decode('ascii')
    if not value.isascii() or not value.isdigit() or str(int(value)) != value:
        raise ValueError('Noncanonical inactive progress')
    return placement._uint(int(value), 'inactive progress', 2147483647)

def progress(owner, prefix, turn, *, player_id=0, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    if core_sha256 != _PLACEMENT_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_production_placement_profile import source_reference
        selected_proof = source_reference(core_sha256)
    pid = _player_id(player_id)
    tracked = getattr(owner, 'explicit_placements', {})
    if len(tracked) > 256:
        raise RuntimeError('Too many tracked explicit placements')
    results = []
    for key, choice in sorted(tracked.items(), key=lambda row: repr(row[0])):
        if type(choice) is not dict:
            raise ValueError('Malformed tracked placement identity')
        actor = choice.get('player_id', 0)
        if type(actor) is not int or actor != pid:
            continue
        expected_key = (pid, choice.get('city_id'), choice.get('plot_id'))
        legacy_key = (choice.get('city_id'), choice.get('plot_id'))
        if key != expected_key and (not (pid == 0 and key == legacy_key)):
            raise ValueError('Tracked placement actor/city/plot key differs')
        reader = districts if choice['kind'] == 'district' else wonders
        receipt = reader.parse_readback(prefix.runtime.evaluate_text(prefix.ui_child, reader.readback_source(choice, turn, core_sha256=core_sha256), b'@explicit_placement_progress'), choice, turn)
        complete = receipt['native_is_complete'] if choice['kind'] == 'district' else receipt['city_has_building']
        exists = not receipt.get('wonder_absent', False)
        summary = dict(city_id=choice['city_id'], category=choice['kind'], index=choice['index'], item_type=choice['item_type'], plot_id=choice['plot_id'], x=choice['x'], y=choice['y'], placement_turn=choice['current_game_turn'], observed_turn=turn, exists=exists, complete=complete)
        results.append(summary)
        owner.emit('official_explicit_placement_progress', summary=summary, native_receipt=receipt, native_gameplay_mutated=False, source_proof_sha256=reader.PROOF_SHA256 if core_sha256 == _PLACEMENT_BASE_CORE_SHA256 else selected_proof[1])
    return results
from civ6_host.contracts.placement import _player_id, validate_action, validate_offers, validate_progress

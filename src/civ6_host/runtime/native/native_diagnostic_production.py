"""Deterministic, diagnostic-only ranking of already-approved production choices.

This preference is a test policy, not a Civilization VI rule. It never creates
or edits candidates and does not call the game. It must not be used by the Mac
scorers (``mac-cpu`` / ``mac-mps``).
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from collections.abc import Mapping
MAX_CANDIDATES = 4096
MAX_ID_BYTES = 256
_BASE_ACTION_KEYS = {'kind', 'city_id', 'category', 'item_index', 'item_hash', 'item_type'}
_PLACEMENT_KEYS = {'placement_mode', 'plot_id', 'x', 'y'}
_PREFIX = {'unit': 'UNIT_', 'building': 'BUILDING_', 'project': 'PROJECT_', 'district': 'DISTRICT_'}

def _uint(value, label, maximum=4294967295):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'Invalid {label}')
    return value

def _candidate_rank(candidate):
    action = candidate['action']
    if action.get('placement_mode') == 'place':
        return 0
    category = action['category']
    return {'building': 1, 'project': 2, 'district': 3, 'unit': 4}[category]

def select_development(candidates):
    """Return the ID of the top-ranked native-approved diagnostic candidate.

    Input candidates follow ``native_map_script``'s ``{candidate_id, action}``
    shape. Ranking is: new placement, building, project, non-placement
    district, then unit. Candidate ID breaks ties lexically, so input order
    cannot change the result. No candidate means an explicit refusal.
    """
    if type(candidates) not in (list, tuple):
        raise ValueError('Candidates must be a finite list or tuple')
    if not candidates or len(candidates) > MAX_CANDIDATES:
        raise ValueError('Candidate count is empty or exceeds the diagnostic bound')
    seen_ids = set()
    validated = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or set(candidate) != {'candidate_id', 'action'}:
            raise ValueError('Invalid candidate structure')
        candidate_id = candidate['candidate_id']
        if type(candidate_id) is not str or not candidate_id or len(candidate_id.encode('utf-8')) > MAX_ID_BYTES or (not candidate_id.isascii()) or any((ord(c) < 33 for c in candidate_id)):
            raise ValueError('Invalid candidate ID')
        if candidate_id in seen_ids:
            raise ValueError('Duplicate candidate identity')
        seen_ids.add(candidate_id)
        action = candidate['action']
        if not isinstance(action, Mapping):
            raise ValueError('Candidate action must be a mapping')
        keys = set(action)
        if keys not in (_BASE_ACTION_KEYS, _BASE_ACTION_KEYS | _PLACEMENT_KEYS):
            raise ValueError('Unknown or incomplete production action fields')
        if action['kind'] != 'choose_production':
            raise ValueError('Unsupported candidate action')
        category = action['category']
        if type(category) is not str or category not in _PREFIX:
            raise ValueError('Unknown production category')
        _uint(action['city_id'], 'city ID')
        _uint(action['item_index'], 'item index', 2147483647)
        _uint(action['item_hash'], 'item hash')
        item_type = action['item_type']
        if type(item_type) is not str or not item_type.isascii() or (not item_type.startswith(_PREFIX[category])) or (len(item_type) > 128):
            raise ValueError('Production type does not match its category')
        if 'placement_mode' in action:
            mode = action['placement_mode']
            if type(mode) is not str or mode not in ('place', 'resume') or category not in ('building', 'district'):
                raise ValueError('Unsupported production placement mode')
            coordinates = tuple((action[k] for k in ('plot_id', 'x', 'y')))
            if mode == 'place':
                for name, value in zip(('plot ID', 'X', 'Y'), coordinates):
                    _uint(value, name, 65535)
            elif coordinates != (-1, -1, -1):
                raise ValueError('Resume candidates must not claim a new plot')
        validated.append(candidate)
    selected = min(validated, key=lambda c: (_candidate_rank(c), c['candidate_id']))
    return selected['candidate_id']

"""Reuse the current UI research/production queries on the retained XP1 owner."""
from copy import deepcopy


def read_research(saved, observation, *, core_sha256):
    """Read chooser rows and current choices for the native UI's player."""
    from . import xp1_research_profile
    from .native import native_research_catalog as research
    from .native import native_research_actions as effects
    b, p = saved.backend, saved.prefix
    xp1_research_profile.bind_owner(b, b.core, b.runtime.read)
    pid, turn = observation['player_id'], observation['turn']
    choices, current = {}, {}
    for kind in ('research', 'civic'):
        catalogue = research.catalog_source(pid, kind, turn, core_sha256=core_sha256)
        raw = p.runtime.evaluate_text(p.ui_child, catalogue, b'@explicit_research_catalog',
                                      capacity=131072)
        choices[kind] = research.parse_catalog(raw, pid, kind, turn)
        effect = effects.effect_source(pid, kind, 0, core_sha256=core_sha256)
        raw = p.runtime.evaluate_text(p.ui_child, effect, b'@explicit_current_research',
                                      capacity=131072)
        current[kind] = effects.parse_effect(raw, pid, kind, 0, turn)['observed_index']
    return choices, current


def read_production(saved, observation, *, core_sha256):
    from . import xp1_production_profile
    from .native import native_production_catalog as production
    from .native import native_city_production_observation as queues
    b, p = saved.backend, saved.prefix
    xp1_production_profile.bind_owner(b, b.core, b.runtime.read)
    pid, turn = observation['player_id'], observation['turn']

    def query(source, label):
        return p.runtime.evaluate_text(p.ui_child, source, label, capacity=131072)

    snapshot = queues.parse_production_snapshot(query(queues.production_snapshot_source(
        pid, core_sha256=core_sha256), b'@explicit_queue_snapshot'), pid)
    if snapshot['game_turn'] != turn or {r['city_id'] for r in snapshot['cities']} != {
            c['id'] for c in observation['cities']}:
        raise RuntimeError('XP1 queue observation crossed turns or owned-city boundaries')
    actions = []
    for city in observation['cities']:
        catalogue = production.parse_catalog(query(production.catalog_source(
            pid, city['id'], turn, replace_current=True, core_sha256=core_sha256),
            b'@explicit_production_catalog'), pid, city['id'], turn)
        if catalogue['status'] != 'catalog':
            raise RuntimeError('XP1 replacement query did not enumerate the actual queue choices')
        for row in catalogue['candidates']:
            action = dict(kind='production', city_id=city['id'], category=row['kind'],
                          index=row['index'], hash=row['hash'], item_type=row['item_type'])
            actions.append(action)
    return snapshot, actions


def read(saved, observation):
    from .captured_session_profile import select
    from .native import native_production_catalog as production
    from civ6_host.contracts.capability_choices import project_state
    from civ6_host.contracts.network_turn import digest

    core_sha256 = select(saved.backend.load_abi.core_sha256).candidate.core_sha256
    research, selections = read_research(saved, observation, core_sha256=core_sha256)
    snapshot, actions = read_production(saved, observation, core_sha256=core_sha256)
    candidates, families = [], {}
    for kind, catalogue in research.items():
        rows = [dict(kind=kind, index=r['index'], hash=r['hash']) for r in catalogue['choices']]
        offers = [dict(candidate_id=digest(action), action=action) for action in rows]
        candidates.extend(offers)
        families[kind] = dict(status='queried_complete',
                              candidate_ids=[offer['candidate_id'] for offer in offers])
    offers = [dict(candidate_id=digest(action), action=action) for action in actions]
    candidates.extend(offers)
    families['production'] = dict(status='queried_partial', candidate_ids=[r['candidate_id'] for r in offers],
        unqualified=list(production.NOT_WIRED))
    # Private exact snapshot protects replacement identity. Raw progress/yield
    # precision is not copied into the public current-choice projection.
    saved.continuation.explicit_production_snapshot = deepcopy(snapshot)
    return candidates, families, project_state(selections, snapshot)

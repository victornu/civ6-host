"""Reuse the current UI research/production queries on the retained XP1 owner."""
from copy import deepcopy
from .configuration_profiles import XP1_CORE_SHA256


def read(saved, observation):
    from . import xp1_research_profile, xp1_production_profile
    from .native import native_research_catalog as research
    from .native import native_research_actions as research_effect
    from .native import native_production_catalog as production
    from .native import native_city_production_observation as queues
    from civ6_host.contracts.capability_choices import project_state
    from civ6_host.contracts.network_turn import digest
    b, p = saved.backend, saved.prefix
    from .captured_session_profile import select
    core_sha256=select(b.load_abi.core_sha256).candidate.core_sha256
    xp1_research_profile.bind_owner(b, b.core, b.runtime.read)
    xp1_production_profile.bind_owner(b, b.core, b.runtime.read)
    pid, turn = observation['player_id'], observation['turn']

    def query(source, label):
        return p.runtime.evaluate_text(p.ui_child, source, label, capacity=131072)

    candidates, families, selections = [], {}, {}
    for kind in ('research', 'civic'):
        catalogue = research.parse_catalog(query(research.catalog_source(
            pid, kind, turn, core_sha256=core_sha256), b'@explicit_research_catalog'), pid, kind, turn)
        selected = research_effect.parse_effect(query(research_effect.effect_source(
            pid, kind, 0, core_sha256=core_sha256), b'@explicit_current_research'), pid, kind, 0, turn)
        selections[kind] = selected['observed_index']
        rows = [dict(kind=kind, index=r['index'], hash=r['hash']) for r in catalogue['choices']]
        ids = []
        for action in rows:
            identity = digest(action)
            candidates.append(dict(candidate_id=identity, action=action)); ids.append(identity)
        families[kind] = dict(status='queried_complete', candidate_ids=ids)

    snapshot = queues.parse_production_snapshot(query(queues.production_snapshot_source(
        pid, core_sha256=core_sha256), b'@explicit_queue_snapshot'), pid)
    if snapshot['game_turn'] != turn or {r['city_id'] for r in snapshot['cities']} != {
            c['id'] for c in observation['cities']}:
        raise RuntimeError('XP1 queue observation crossed turns or owned-city boundaries')
    ids = []
    for city in observation['cities']:
        catalogue = production.parse_catalog(query(production.catalog_source(
            pid, city['id'], turn, replace_current=True, core_sha256=core_sha256),
            b'@explicit_production_catalog'), pid, city['id'], turn)
        if catalogue['status'] != 'catalog':
            raise RuntimeError('XP1 replacement query did not enumerate the actual queue choices')
        for row in catalogue['candidates']:
            action = dict(kind='production', city_id=city['id'], category=row['kind'],
                          index=row['index'], hash=row['hash'], item_type=row['item_type'])
            identity = digest(action)
            candidates.append(dict(candidate_id=identity, action=action)); ids.append(identity)
    families['production'] = dict(status='queried_partial', candidate_ids=ids,
        unqualified=list(production.NOT_WIRED))
    # Private exact snapshot protects replacement identity. Raw progress/yield
    # precision is not copied into the public current-choice projection.
    saved.continuation.explicit_production_snapshot = deepcopy(snapshot)
    return candidates, families, project_state(selections, snapshot)

"""Shared explicit production replacement, placement and resumption.

Extracted from the existing saved-action path. The caller selects a native
offer; legality, request, placement and effect remain official Core operations.
"""
from .configuration_profiles import BASE_CORE_SHA256


def apply(owner, p, action, turn, *, player_id, core_sha256=BASE_CORE_SHA256):
    from .native import native_production_catalog as production
    from .native import native_city_production_observation as queues
    from .native.native_player_observation import observe_player
    pid = player_id
    if action.get('kind') != 'production':
        raise ValueError('Explicit ordinary production action required')
    prior_queue = queues.parse_production_snapshot(p.runtime.evaluate_text(
        p.ui_child, queues.production_snapshot_source(pid, core_sha256=core_sha256),
        b'@explicit_production_before'), pid)
    if prior_queue != getattr(owner, 'explicit_production_snapshot', None):
        raise RuntimeError('Production snapshot changed since the published choice')
    prior_rows = [r for r in prior_queue['cities'] if r['city_id'] == action['city_id']]
    if len(prior_rows) != 1:
        raise RuntimeError('Production city missing from own snapshot')
    prior_production = prior_rows[0]
    raw = p.runtime.evaluate_text(p.ui_child, production.catalog_source(
        pid, action['city_id'], turn, replace_current=True, core_sha256=core_sha256),
        b'@explicit_production_revalidation')
    catalog = production.parse_catalog(raw, pid, action['city_id'], turn)
    choice = production.choose(catalog, action['category'], action['index'])
    if choice['hash'] != action['hash'] or choice['item_type'] != action['item_type']:
        raise RuntimeError('Production choice identity changed')
    request = production.request_source(choice, replace_current=True, core_sha256=core_sha256)
    submitted = p.runtime.evaluate_text(p.ui_child, request, b'@explicit_production_request')
    if submitted != b'submitted' or len(p.actions.pending) != 1:
        raise RuntimeError('Expected one native production request')
    p.actions.deliver_one()
    p.deferred_events.drain_empty_receivers()
    p.view_publisher.publish()
    production_state = queues.parse_production_snapshot(p.runtime.evaluate_text(
        p.ui_child, queues.production_snapshot_source(pid, core_sha256=core_sha256),
        b'@explicit_production_effect'), pid)
    rows = [row for row in production_state['cities'] if row['city_id'] == action['city_id']]
    expected_size = max(1, prior_production['queue_size'])
    if (production_state['game_turn'] != turn or len(rows) != 1
            or rows[0]['queue_size'] != expected_size
            or rows[0]['current_production_hash'] & 0xffffffff != choice['hash']
            or rows[0]['kind'] != {'unit':'U','building':'B','project':'P','district':'D'}[choice['kind']]
            or rows[0]['item_index'] != choice['index']):
        raise RuntimeError('Native production effect differs')
    owner.emit('official_explicit_production_effect', choice=choice, production=rows[0],
               item_completed=False, production_before=prior_production)
    return observe_player(p.runtime, p.ui_child, pid)


def apply_placement(owner, p, action, turn, before, *, player_id,
                    core_sha256=BASE_CORE_SHA256):
    """Shared existing placement/resume path, with explicit engine selection."""
    from copy import deepcopy
    from .native import native_saved_placement as placed
    from .native import native_city_production_observation as queues
    from .native import native_official_load as official
    from .native.native_player_observation import observe_player
    pid, kind = player_id, action['kind']
    placed.validate_action(action, player_id=pid)
    prior_queue = queues.parse_production_snapshot(p.runtime.evaluate_text(
        p.ui_child, queues.production_snapshot_source(pid, core_sha256=core_sha256),
        b'@explicit_production_before'), pid)
    if prior_queue != getattr(owner, 'explicit_production_snapshot', None):
        raise RuntimeError('Production snapshot changed since the published choice')
    prior_rows = [r for r in prior_queue['cities'] if r['city_id'] == action['city_id']]
    if len(prior_rows) != 1:
        raise RuntimeError('Production city missing from own snapshot')
    prior_production = prior_rows[0]
    choice = placed.selected(p, action, turn, player_id=pid, core_sha256=core_sha256)
    tracked = getattr(owner, 'explicit_placements', {})
    tracked_before = deepcopy(tracked)
    if kind == 'production_placement':
        key = ((pid, choice['city_id'], choice['plot_id'])
               if core_sha256 != BASE_CORE_SHA256 or owner.inputs.profile is official.HOTSEAT_FOUR_PROFILE
               else (choice['city_id'], choice['plot_id']))
        if key in tracked or len(tracked) >= 256:
            raise RuntimeError('Duplicate or excessive tracked placement')
    else:
        progress_before = placed.item_progress(p, choice, core_sha256=core_sha256)
        placements_before = placed.progress(owner, p, turn, player_id=pid, core_sha256=core_sha256)
    request = placed.placement.request_source(choice, visible_only=True, replace_current=True,
                                             core_sha256=core_sha256)
    submitted = p.runtime.evaluate_text(p.ui_child, request, b'@explicit_production_request')
    if submitted != b'submitted' or len(p.actions.pending) != 1:
        raise RuntimeError('Expected one native production request')
    p.actions.deliver_one()
    p.deferred_events.drain_empty_receivers()
    p.view_publisher.publish()
    production_state = queues.parse_production_snapshot(p.runtime.evaluate_text(
        p.ui_child, queues.production_snapshot_source(pid, core_sha256=core_sha256),
        b'@explicit_production_effect'), pid)
    rows = [row for row in production_state['cities'] if row['city_id'] == action['city_id']]
    expected_size = max(1, prior_production['queue_size'])
    if (production_state['game_turn'] != turn or len(rows) != 1
            or rows[0]['queue_size'] != expected_size
            or rows[0]['current_production_hash'] & 0xffffffff != choice['hash']
            or rows[0]['kind'] != {'unit':'U','building':'B','project':'P','district':'D'}[choice['kind']]
            or rows[0]['item_index'] != choice['index']):
        raise RuntimeError('Native production effect differs')
    owner.emit('official_explicit_production_effect', choice=choice, production=rows[0],
               item_completed=False, production_before=prior_production)
    after = observe_player(p.runtime, p.ui_child, pid)
    label = b'@explicit_placement_effect' if kind == 'production_placement' else b'@explicit_placement_resume_effect'
    effect = placed.placement.parse_effect(p.runtime.evaluate_text(p.ui_child,
        placed.placement.effect_source(choice, visible_only=True, replace_current=True,
                                       core_sha256=core_sha256), label), choice)
    if kind == 'production_placement':
        tracked[key] = deepcopy(choice)
        owner.explicit_placements = tracked
        owner.emit('official_explicit_placement_effect', action=action, choice=choice, effect=effect,
                   observation_before=before, observation_after=after, automatic_choices_applied=False)
    else:
        progress_after = placed.item_progress(p, choice, core_sha256=core_sha256)
        placements_after = placed.progress(owner, p, turn, player_id=pid, core_sha256=core_sha256)
        if progress_before != progress_after or rows[0]['progress'] != progress_after:
            raise RuntimeError('Native resumption changed retained production progress')
        if tracked != tracked_before or placements_before != placements_after:
            raise RuntimeError('Production resume changed tracked plot identity/completion')
        owner.emit('official_explicit_production_resume_effect', action=action, choice=choice,
                   effect=effect, production_before=prior_production, production_after=rows[0],
                   progress_before=progress_before, progress_after=progress_after,
                   placements_before=placements_before, placements_after=placements_after,
                   observation_before=before, observation_after=after, automatic_choices_applied=False)
    return after

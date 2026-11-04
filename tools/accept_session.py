"""Bounded public-client acceptance; explicit test choices, never a learner.

Preserves raw receipts in the supervised private run. Input configuration is
user supplied; this script contains no game assets, captures or installation paths.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from civ6_host.runtime.stdout_transport_profiles import session_records


def public_exploration_choice(view, visits):
    """Rank native offers using revealed coordinates only, for this test client.

    This is an exploration heuristic, not a pathfinder, visibility rule or host
    action mask. The official catalogue still supplies every selected action.
    """
    observation = view['observation']
    # The visible observation deliberately omits explored tiles under fog.
    # Reuse the public revealed-map channel, instead of forgetting those tiles.
    known = {(p['x'], p['y']) for p in view['decisions']['player_map']['plots']
             if p['revealed']}
    width, height = observation['width'], observation['height']
    moves = [r['action'] for r in view['decisions']['candidates']
             if r['action']['kind'] == 'move']
    if not moves:
        return None

    def rank(action):
        x, y, uid = action['destination_x'], action['destination_y'], action['unit_id']
        # Only the known/unknown boundary is used; no terrain, owner or entity
        # value is read from a tile outside the actor's revealed coordinates.
        frontier = sum((px, py) not in known
            for px in range(max(0, x-2), min(width, x+3))
            for py in range(max(0, y-2), min(height, y+3)))
        revisits = visits.get((uid, action['destination_plot_id']), 0)
        separation = min((abs(x-u['x']) + abs(y-u['y'])
                          for u in observation['units'] if u['id'] != uid), default=0)
        return (revisits > 0, -frontier, revisits, -separation,
                uid, action['destination_plot_id'])

    return min(moves, key=rank)


def exercise_city_controls(get_view, choose, *, include_queue=True):
    """Explicit client choices from the public catalogue; no diagnostic flags."""
    view = get_view()
    cities = view['observation']['cities']
    if len(cities) != 1:
        raise ValueError('City-control acceptance requires its one founded city')
    city_id = cities[0]['id']

    def catalog(name):
        return next(row for row in get_view()['decisions'][name] if row['city_id'] == city_id)

    original_focus = catalog('city_focus_catalogs')
    for _ in range(3):
        choose('city_focus', city_id=city_id, yield_type='YIELD_PRODUCTION')
    if catalog('city_focus_catalogs') != original_focus:
        raise RuntimeError('Three official focus clicks did not restore initial flags')

    candidates = [row['action'] for row in get_view()['decisions']['candidates']
                  if row['action']['kind'] == 'city_citizen'
                  and row['action']['city_id'] == city_id
                  and row['action']['occupied'] and not row['action']['locked']
                  and (row['action']['x'], row['action']['y']) !=
                      (cities[0]['x'], cities[0]['y'])]
    if not candidates:
        raise ValueError('No currently worked, unlocked citizen tile is offered')
    tile = min(candidates, key=lambda action: action['plot_id'])['plot_id']
    choose('city_citizen', city_id=city_id, plot_id=tile)
    row = next(row for row in catalog('citizen_catalogs')['plots'] if row['plot_id'] == tile)
    if not row['locked']:
        raise RuntimeError('Native citizen click did not lock the offered tile')
    choose('city_citizen', city_id=city_id, plot_id=tile)
    row = next(row for row in catalog('citizen_catalogs')['plots'] if row['plot_id'] == tile)
    if row['locked']:
        raise RuntimeError('Second native citizen click did not unlock the tile')

    if not include_queue:
        return dict(city_id=city_id, citizen_plot_id=tile, focus_restored=True,
            citizen_unlocked=True)

    if catalog('production_queues')['entries']:
        raise ValueError('City-control acceptance expects the initially empty queue')
    choose('queue_append', city_id=city_id, item_type='UNIT_SCOUT')
    choose('queue_append', city_id=city_id, item_type='UNIT_WARRIOR')
    two = [dict(row) for row in catalog('production_queues')['entries']]
    if len(two) != 2:
        raise RuntimeError('Native queue append pair did not create two entries')
    choose('queue_swap', city_id=city_id, source_position=0, destination_position=1)
    swapped = catalog('production_queues')['entries']
    if [row['hash'] for row in swapped] != [two[1]['hash'], two[0]['hash']]:
        raise RuntimeError('Native queue swap did not reverse the two selected entries')
    choose('queue_remove', city_id=city_id, position=1)
    final = catalog('production_queues')['entries']
    if len(final) != 1 or final[0]['hash'] != two[1]['hash']:
        raise RuntimeError('Native queue removal did not preserve the selected head')
    return dict(city_id=city_id, citizen_plot_id=tile, focus_restored=True,
        citizen_unlocked=True, queue_before_swap=two, final_queue=final,
        diagnostic_flags_used=False)


def exercise_map_controls(get_view, choose, advance):
    """Public client exercise: queued click/cancel and an affordable plot buy."""
    view = get_view()
    units = view['observation']['units']
    selectable = {r['action']['unit_id'] for r in view['decisions']['candidates']
                  if r['action']['kind'] == 'world_select_unit'}
    unit = next(u for u in units if u['id'] in selectable)
    uid = unit['id']
    choose('world_select_unit', unit_id=uid)
    selected = get_view()
    clicks = [r['action'] for r in selected['decisions']['candidates']
              if r['action']['kind'] == 'world_plot_click']
    if len(clicks) != selected['observation']['width'] * selected['observation']['height']:
        raise RuntimeError('World-click offers are pruned by hidden or strategic target properties')
    # Explicit test-client target ranking from the public visible observation.
    # No private path, ownership or terrain query selects the destination.
    targets = [p for p in selected['observation']['plots']
               if p['visible'] and not p['water'] and not p['impassable']
               and (p['x'], p['y']) != (unit['x'], unit['y'])]
    targets.sort(key=lambda p: (-abs(p['x']-unit['x'])-abs(p['y']-unit['y']), p['index']))
    attempts = []

    def queued():
        return next(r['plot_id'] for r in get_view()['decisions']['queued_orders']['units']
                    if r['unit_id'] == uid)

    for target in targets[:4]:
        choose('world_plot_click', unit_id=uid, plot_id=target['index'])
        attempts.append(dict(plot_id=target['index'], queued_destination=queued()))
        if queued() is not None:
            break
    else:
        raise RuntimeError('No queued destination witnessed from the bounded public clicks')
    queued_before_cancel = queued()
    choose('unit_order', unit_id=uid, item_type='UNITCOMMAND_CANCEL')
    if queued() is not None:
        raise RuntimeError('Native CANCEL did not clear the queued destination')
    choose('world_deselect_unit')
    if get_view()['decisions']['world_input']['selected_unit_id'] is not None:
        raise RuntimeError('Explicit deselection did not clear the player selection')
    turns = 0
    for turns in range(13):
        offers = [r['action'] for r in get_view()['decisions']['candidates']
                  if r['action']['kind'] == 'purchase' and 'plot_id' in r['action']]
        if offers:
            break
        if turns == 12:
            raise RuntimeError('No affordable native plot purchase within the bounded turn budget')
        advance()
    purchase = min(offers, key=lambda a: (a['city_id'], a['plot_id']))
    gold_before = get_view()['observation']['economy']['gold']
    choose('purchase', city_id=purchase['city_id'], plot_id=purchase['plot_id'])
    gold_after = get_view()['observation']['economy']['gold']
    return dict(unit_id=uid, click_attempts=attempts, queued_before_cancel=queued_before_cancel,
                queued_after_cancel=None, all_grid_targets_offered=True,
                purchase=purchase, gold_before=gold_before, gold_after=gold_after,
                turns_waited_for_native_affordability=turns, diagnostic_flags_used=False)


def exercise_world_input_group(get_view, choose):
    """Short explicit public-client group, without foundation or turn pumping.

    Destination ranking is a test choice based only on the public observation.
    The host still offers every coordinate; this does not define its action mask.
    Native request/delivery authentication belongs to the retained-receipt review.
    """
    from civ6_host.contracts.network_turn import CAPABILITY_WORLD_SCHEMA, CAPABILITY_UNIT_ORDERS_SCHEMA, CAPABILITY_PRODUCTION_QUEUE_SCHEMA, CAPABILITY_PLACEMENT_SCHEMA, CAPABILITY_PLACEMENT_INVENTORY_SCHEMA, CAPABILITY_UNIT_ATTACKS_SCHEMA, CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA
    initial=copy.deepcopy(get_view())
    if initial['decisions']['schema'] not in (CAPABILITY_WORLD_SCHEMA,CAPABILITY_UNIT_ORDERS_SCHEMA,CAPABILITY_PRODUCTION_QUEUE_SCHEMA,CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA):
        raise ValueError('World-input group requires the explicit v4 public boundary')
    offers=[r['action'] for r in initial['decisions']['candidates']]
    selectable={a['unit_id'] for a in offers if a['kind']=='world_select_unit'}
    founders={a['unit_id'] for a in offers if a['kind']=='found_city'}
    units=[u for u in initial['observation']['units'] if u['id'] in selectable]
    if not units:raise ValueError('No public own unit can be selected')
    unit=min(units,key=lambda u:(u['id'] in founders,u['id']))
    uid=unit['id'];turn=initial['observation']['turn']
    choose('world_select_unit',unit_id=uid)
    selected=copy.deepcopy(get_view())
    if (selected['decisions']['world_input']['selected_unit_id']!=uid
            or selected['observation']!=initial['observation']
            or selected['decisions']['queued_orders']!=initial['decisions']['queued_orders']):
        raise RuntimeError('Explicit selection changed simulation or lost its own unit')
    grid=[r['action'] for r in selected['decisions']['candidates'] if r['action']['kind']=='world_plot_click']
    width,height=selected['observation']['width'],selected['observation']['height']
    if {a['plot_id'] for a in grid}!=set(range(width*height)) or len(grid)!=width*height:
        raise RuntimeError('World-click offers do not preserve the complete public grid')
    occupied={(u['x'],u['y']) for u in selected['observation']['units']
              if u['id']!=uid}
    occupied.update((u['x'],u['y']) for u in selected['observation']['visible_enemy_units'])
    targets=[p for p in selected['observation']['plots']
             if p['visible'] and not p['water'] and not p['impassable']
             and (p['x'],p['y'])!=(unit['x'],unit['y'])
             and (p['x'],p['y']) not in occupied]
    targets.sort(key=lambda p:(abs(p['x']-unit['x'])+abs(p['y']-unit['y']),p['index']))
    attempts=[]
    def unit_and_queue(view):
        current=next(u for u in view['observation']['units'] if u['id']==uid)
        queued=next(r['plot_id'] for r in view['decisions']['queued_orders']['units'] if r['unit_id']==uid)
        return copy.deepcopy(current),queued
    for target in targets[:4]:
        prior=copy.deepcopy(get_view());before,queued_before=unit_and_queue(prior)
        command=choose('world_plot_click',unit_id=uid,plot_id=target['index'],
                       _expected_status=('completed','refused'))
        current=get_view();after,queued_after=unit_and_queue(current)
        moved=(before['x'],before['y'])!=(after['x'],after['y'])
        target_queued=queued_after==target['index']
        if command['status']=='refused' and (current['observation']!=prior['observation']
                or current['decisions']['world_input']!=prior['decisions']['world_input']
                or current['decisions']['queued_orders']!=prior['decisions']['queued_orders']
                or current['applied_action'] is not None
                or command['reason']!='native_world_input_branch_unqualified'):
            raise RuntimeError('Unsupported click changed the public simulation or claimed completion')
        attempts.append(dict(sequence=current['sequence'],target=copy.deepcopy(target),
            unit_before=before,unit_after=after,queued_before=queued_before,queued_after=queued_after,
            command_result=copy.deepcopy(command),position_changed=moved,target_queued=target_queued))
        if command['status']=='completed' and (moved or target_queued):break
    else:
        raise RuntimeError('Bounded public clicks did not witness position or queued destination')
    # The official WorldInput route decides whether this input is a no-op or a
    # real request; do not manufacture a no-op expectation from coordinates.
    current,_=unit_and_queue(get_view());own_plot=current['y']*width+current['x']
    command=choose('world_plot_click',unit_id=uid,plot_id=own_plot,
                   _expected_status=('completed','refused'))
    own_cell=dict(sequence=get_view()['sequence'],plot_id=own_plot,
                  command_result=copy.deepcopy(command))
    before_deselect=copy.deepcopy(get_view())
    choose('world_deselect_unit')
    final=get_view()
    if (final['decisions']['world_input']['selected_unit_id'] is not None
            or final['observation']!=before_deselect['observation']
            or final['decisions']['queued_orders']!=before_deselect['decisions']['queued_orders']
            or final['observation']['turn']!=turn):
        raise RuntimeError('Explicit deselection changed simulation or the captured turn')
    return dict(unit_id=uid,initial_turn=turn,final_turn=final['observation']['turn'],
        selection_sequence=selected['sequence'],click_attempts=attempts,own_cell=own_cell,
        deselection_sequence=final['sequence'],all_grid_targets_offered=True,
        poll_calls=0,foundation_performed=False,private_target_queries_used=False)


def exercise_unit_order_group(get_view, choose):
    """Rest/wake and actual queue cancellation; no turn or hidden target query."""
    from civ6_host.contracts.network_turn import CAPABILITY_UNIT_ORDERS_SCHEMA, CAPABILITY_PRODUCTION_QUEUE_SCHEMA, CAPABILITY_PLACEMENT_SCHEMA, CAPABILITY_PLACEMENT_INVENTORY_SCHEMA, CAPABILITY_UNIT_ATTACKS_SCHEMA, CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA
    initial=copy.deepcopy(get_view())
    if initial['decisions']['schema'] not in (CAPABILITY_UNIT_ORDERS_SCHEMA,CAPABILITY_PRODUCTION_QUEUE_SCHEMA,CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA):
        raise ValueError('Unit-order group requires the explicit v5 catalogue')
    turn=initial['observation']['turn'];steps=[];healing=[]
    release_step=None;selection_sequence=None;deselection_sequence=None;attempts=[];cancel=None
    def offers(name):
        return [r['action'] for r in get_view()['decisions']['candidates']
                if r['action']['kind']=='unit_order' and r['action']['item_type']==name]
    def state(view,uid):
        return copy.deepcopy(next(u for u in view['decisions']['unit_orders']['units'] if u['unit_id']==uid))
    def perform(action):
        prior=copy.deepcopy(get_view());uid=action['unit_id']
        command=choose('unit_order',**{k:v for k,v in action.items() if k!='kind'})
        current=get_view()
        row=dict(sequence=current['sequence'],action=copy.deepcopy(action),
            command_result=copy.deepcopy(command),unit_before=state(prior,uid),unit_after=state(current,uid))
        steps.append(row);return row
    def release_offer(unit_id):
        for name in ('UNITCOMMAND_WAKE','UNITCOMMAND_CANCEL'):
            available=[a for a in offers(name) if a['unit_id']==unit_id]
            if available:return available[0]
        return None
    def finish(reason=None):
        return dict(complete=cancel is not None,incomplete_reason=reason,unit_id=uid,initial_turn=turn,
            final_turn=get_view()['observation']['turn'],rest_sequence=rest_step['sequence'],
            release_sequence=release_step['sequence'] if release_step else None,
            release_action=copy.deepcopy(release_step['action']) if release_step else None,
            orders=steps,healing=healing,selection_sequence=selection_sequence,click_attempts=attempts,
            cancel=cancel,deselection_sequence=deselection_sequence,poll_calls=0,foundation_performed=False,
            private_target_queries_used=False,healing_over_turns_qualified=False)
    selectable={r['action']['unit_id'] for r in initial['decisions']['candidates']
                if r['action']['kind']=='world_select_unit'}
    founders={r['action']['unit_id'] for r in initial['decisions']['candidates']
              if r['action']['kind']=='found_city'}
    rests=[a for name in ('UNITOPERATION_SLEEP','UNITOPERATION_FORTIFY') for a in offers(name)
           if a['unit_id'] in selectable]
    if not rests:raise RuntimeError('No native rest order offered for a selectable own unit')
    rest=min(rests,key=lambda a:(a['unit_id'] in founders,a['item_type']!='UNITOPERATION_SLEEP',a['unit_id']))
    uid=rest['unit_id'];rest_step=perform(rest)
    if rest_step['unit_before']==rest_step['unit_after']:
        raise RuntimeError('Rest did not witness a native activity/readiness change')
    release=release_offer(uid)
    if release is None:return finish('native_rest_release_not_offered')
    release_step=perform(release)
    if (release_step['unit_before']==release_step['unit_after']
            or release_step['unit_after']['activity_type']!=rest_step['unit_before']['activity_type']):
        raise RuntimeError('Offered native release did not restore the witnessed initial activity')
    for name in ('UNITOPERATION_HEAL','UNITOPERATION_RELIGIOUS_HEAL'):
        available=[a for a in offers(name) if a['unit_id']==uid]
        if not available:
            healing.append(dict(item_type=name,executed=False,checked_sequence=get_view()['sequence'],
                                reason='not_natively_offered_for_selected_unit'))
            continue
        action=min(available,key=lambda a:a['unit_id']);step=perform(action)
        release=release_offer(action['unit_id'])
        if release is None:
            healing.append(dict(item_type=name,executed=True,sequence=step['sequence'],release_sequence=None,release_action=None))
            return finish('native_healing_release_not_offered')
        released=perform(release)
        if released['unit_after']['activity_type']!=step['unit_before']['activity_type']:
            raise RuntimeError('Healing release did not restore the witnessed initial activity')
        healing.append(dict(item_type=name,executed=True,sequence=step['sequence'],
                            release_sequence=released['sequence'],release_action=copy.deepcopy(released['action'])))
    choose('world_select_unit',unit_id=uid)
    selected=copy.deepcopy(get_view());selection_sequence=selected['sequence']
    if selected['decisions']['world_input']['selected_unit_id']!=uid:
        raise RuntimeError('Explicit unit-order selection was not returned publicly')
    grid=[r['action'] for r in selected['decisions']['candidates'] if r['action']['kind']=='world_plot_click']
    if {a['plot_id'] for a in grid}!=set(range(selected['observation']['width']*selected['observation']['height'])):
        raise RuntimeError('Unit-order exercise lost unrestricted public grid inputs')
    unit=next(u for u in selected['observation']['units'] if u['id']==uid)
    occupied={(u['x'],u['y']) for u in selected['observation']['units'] if u['id']!=uid}
    occupied.update((u['x'],u['y']) for u in selected['observation']['visible_enemy_units'])
    targets=[p for p in selected['observation']['plots'] if p['visible'] and not p['water']
             and not p['impassable'] and (p['x'],p['y'])!=(unit['x'],unit['y'])
             and (p['x'],p['y']) not in occupied]
    targets.sort(key=lambda p:(-abs(p['x']-unit['x'])-abs(p['y']-unit['y']),p['index']))
    def queued(view):
        return next(r['plot_id'] for r in view['decisions']['queued_orders']['units'] if r['unit_id']==uid)
    for target in targets[:4]:
        prior=copy.deepcopy(get_view());qb=queued(prior)
        command=choose('world_plot_click',unit_id=uid,plot_id=target['index'],
                       _expected_status=('completed','refused'))
        current=get_view();qa=queued(current)
        if command['status']=='refused' and (current['observation']!=prior['observation']
                or current['decisions']['world_input']!=prior['decisions']['world_input']
                or current['decisions']['queued_orders']!=prior['decisions']['queued_orders']
                or current['applied_action'] is not None
                or command['reason']!='native_world_input_branch_unqualified'):
            raise RuntimeError('Unsupported queue input changed public state or claimed success')
        attempts.append(dict(sequence=current['sequence'],target=copy.deepcopy(target),
                             queued_before=qb,queued_after=qa,command_result=copy.deepcopy(command)))
        if command['status']=='completed' and qa==target['index']:
            cancellations=[a for a in offers('UNITCOMMAND_CANCEL') if a['unit_id']==uid]
            if not cancellations:break
            step=perform(cancellations[0]);after=queued(get_view())
            if after is not None:raise RuntimeError('Native CANCEL did not clear the witnessed queued destination')
            cancel=dict(sequence=step['sequence'],queued_before=qa,queued_after=after)
            break
    before_deselect=copy.deepcopy(get_view());choose('world_deselect_unit');final=get_view()
    deselection_sequence=final['sequence']
    if (final['decisions']['world_input']['selected_unit_id'] is not None
            or final['observation']!=before_deselect['observation']
            or final['decisions']['queued_orders']!=before_deselect['decisions']['queued_orders']
            or final['observation']['turn']!=turn):
        raise RuntimeError('Unit-order deselection changed the same-turn simulation')
    reason=None
    if cancel is None:
        reason=('native_cancel_not_offered_for_witnessed_queue' if attempts
                and attempts[-1]['command_result']['status']=='completed'
                and attempts[-1]['queued_after']==attempts[-1]['target']['index']
                else 'native_queued_destination_not_witnessed')
    return finish(reason)


def exercise_production_queue_group(get_view, choose):
    """Exercise offered queue permutations; zero turns and no private queries."""
    from civ6_host.contracts.network_turn import CAPABILITY_PRODUCTION_QUEUE_SCHEMA, CAPABILITY_PLACEMENT_SCHEMA, CAPABILITY_PLACEMENT_INVENTORY_SCHEMA, CAPABILITY_UNIT_ATTACKS_SCHEMA, CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA
    from civ6_host.contracts.production_queue import check_effect
    initial=copy.deepcopy(get_view());turn=initial['observation']['turn'];steps=[];foundation=None
    if initial['decisions']['schema'] not in (CAPABILITY_PRODUCTION_QUEUE_SCHEMA,CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA):
        raise ValueError('Production queue group requires the explicit v6 catalogue')
    if not initial['observation']['cities']:
        command=choose('found_city');current=get_view()
        if (len(current['observation']['cities'])!=1
                or len(current['observation']['units'])!=len(initial['observation']['units'])-1):
            raise RuntimeError('Queue preparation lacks the actual public foundation effect')
        foundation=dict(sequence=current['sequence'],action=copy.deepcopy(current['applied_action']),
                        command_result=copy.deepcopy(command))
    available=get_view()['decisions']['production_queues']
    if available is None:raise RuntimeError('Native production queue query unavailable')
    cities=[r for r in available if r['enabled'] and not r['entries']]
    if not cities:raise RuntimeError('Queue exercise requires a natively enabled empty own-city queue')
    city_id=min(r['city_id'] for r in cities)
    def queue():return next(r for r in get_view()['decisions']['production_queues'] if r['city_id']==city_id)
    def offers(kind):return [a for a in queue()['offers'] if a['kind']==kind]
    def perform(action):
        before=copy.deepcopy(queue())
        command=choose(action['kind'],**{k:v for k,v in action.items() if k!='kind'})
        after=copy.deepcopy(queue());check_effect(action,before,after)
        if get_view()['observation']['turn']!=turn:raise RuntimeError('Queue edit unexpectedly crossed a turn')
        step=dict(sequence=get_view()['sequence'],action=copy.deepcopy(action),command_result=copy.deepcopy(command),
                  queue_before=before,queue_after=after)
        steps.append(step);return step
    def key(action):return (action['category'],action['index'],action['hash'])
    first=None
    for position in range(8):
        choices=[a for a in offers('queue_append') if a['category']=='unit' and a['mode']=='append']
        if position==1:choices=[a for a in choices if key(a)!=first]
        if not choices:raise RuntimeError('Native queue offers lack the required distinct repeatable unit entries')
        action=min(choices,key=key);perform(action)
        if position==0:first=key(action)
    full_sequence=get_view()['sequence']
    swap=next((a for a in offers('queue_swap') if a['source_position']==0 and a['destination_position']==1),None)
    if swap is None:raise RuntimeError('Native queue swap was not offered')
    swap_step=perform(swap)
    tail=queue()['entries'][-1]
    choices=[a for a in offers('queue_append') if a['mode']=='replace_tail'
             and key(a)!=(tail['category'],tail['index'],tail['hash'])]
    if not choices:raise RuntimeError('Native eighth-slot replacement lacks a different offered item')
    replacement=perform(min(choices,key=key))
    remove=next((a for a in offers('queue_remove') if a['position']==1),None)
    if remove is None:raise RuntimeError('Native queue removal was not offered')
    removal=perform(remove)
    return dict(city_id=city_id,initial_turn=turn,final_turn=get_view()['observation']['turn'],
        foundation=foundation,steps=steps,full_queue_sequence=full_sequence,
        swap_sequence=swap_step['sequence'],replace_tail_sequence=replacement['sequence'],
        remove_sequence=removal['sequence'],poll_calls=0,private_target_queries_used=False,
        complete_append_catalogue_claimed=False,placement_or_formation_qualified=False)


def placement_preparation_identity(config, *, shrine=False):
    """Read the selected captured database; its rowid never selects an action."""
    import sqlite3
    from civ6_host.runtime.paths import resource_root
    root=Path(config.get('resources',resource_root()))
    reference=config['prepared_capture'];manifest_path=Path(reference['path'])
    if not manifest_path.is_absolute():manifest_path=root/manifest_path
    raw=manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=reference['sha256']:
        raise ValueError('Placement preparation capture identity changed')
    row=json.loads(raw)['files']['database_gameplay'];database=(manifest_path.parent/row['path']).resolve()
    if hashlib.sha256(database.read_bytes()).hexdigest()!=row['sha256']:
        raise ValueError('Placement preparation gameplay database changed')
    connection=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
    try:
        technology=connection.execute('SELECT t.Type,t.Hash,t.Kind,r.Cost FROM Types t JOIN Technologies r '
            'ON r.TechnologyType=t.Type WHERE t.Type=?',('TECH_ASTROLOGY',)).fetchall()
        target=connection.execute('SELECT DistrictType,PrereqTech,PrereqCivic FROM Districts '
            'WHERE DistrictType=?',('DISTRICT_HOLY_SITE',)).fetchall()
        building=connection.execute('SELECT t.Type,t.Hash,t.Kind,b.PrereqDistrict,b.PrereqTech,'
            'b.PrereqCivic,b.CitizenSlots FROM Types t JOIN Buildings b ON b.BuildingType=t.Type '
            'WHERE t.Type=?',('BUILDING_SHRINE',)).fetchall() if shrine else None
    finally:connection.close()
    if (len(technology)!=1 or technology[0][2]!='KIND_TECH'
            or target!=[('DISTRICT_HOLY_SITE','TECH_ASTROLOGY',None)]):
        raise ValueError('Captured Astrology/Holy Site prerequisite differs')
    result=dict(technology_type=technology[0][0],action_hash=technology[0][1]&0xffffffff,
                database_cost=technology[0][3],target_type=target[0][0],
                database=dict(path=str(database),sha256=row['sha256']))
    if shrine:
        if (len(building)!=1 or building[0][2:]!=('KIND_BUILDING','DISTRICT_HOLY_SITE',
                                                   'TECH_ASTROLOGY',None,1)):
            raise ValueError('Captured Shrine prerequisite or specialist slots differ')
        result.update(shrine_type=building[0][0],shrine_hash=building[0][1]&0xffffffff)
    return result


def prepare_placement_boundary(get_view, choose, poll, *, max_turns, remaining, identity, receipt,
                               target_type=None, total_group_seconds=1200, reset_reserve_seconds=180):
    """Bounded caller policy using only current public offers and real updates."""
    if type(max_turns) is not int or not 1<=max_turns<=12:
        raise ValueError('Placement preparation requires one to twelve turns')
    initial=copy.deepcopy(get_view());initial_turn=initial['observation']['turn']
    receipt.update(initial_sequence=initial['sequence'],initial_turn=initial_turn,max_turns=max_turns,
        max_polls_per_turn=32,total_group_seconds=total_group_seconds,
        reset_reserve_seconds=reset_reserve_seconds,public_selector=True,checkpoint_used=False,
        source_identity=copy.deepcopy(identity),transitions=[],poll_calls=0,turns_advanced=0,prepared_boundary=None)
    def guard():
        if remaining()<60:raise RuntimeError('Placement preparation reached its reserved close/reset time')
    def active():
        controls=get_view()['decisions']['turn_controls']
        return (controls['active'] is True and controls['active_complete'] is True
                and controls['can_unready'] is False and controls['timer_elapsed'] is False)
    def offers(kind):return [r['action'] for r in get_view()['decisions']['candidates'] if r['action']['kind']==kind]
    def ready():
        values=get_view()['decisions'].get('placement_offers')
        if values is None:raise RuntimeError('Native placement query unavailable during preparation')
        return any(a['kind']=='production_placement' and a['category']=='district'
                   and (target_type is None or a['item_type']==target_type) for a in values)
    def step(action=None):
        guard();before=get_view()['observation']['turn']
        command=(choose(action['kind'],**{k:v for k,v in action.items() if k!='kind'}) if action is not None else poll())
        receipt['transitions'].append(dict(sequence=get_view()['sequence'],action=copy.deepcopy(action),
            command_result=copy.deepcopy(command) if action is not None else None,
            turn_before=before,turn_after=get_view()['observation']['turn']))
        receipt['poll_calls']+=int(action is None)
    for turn_index in range(max_turns+1):
        view=get_view()
        if not active() or view['outcome']['terminated'] or view['outcome']['truncated']:
            raise RuntimeError('Placement preparation lacks a live active human boundary')
        receipt['turns_advanced']=view['observation']['turn']-initial_turn
        if ready():
            receipt['prepared_boundary']=dict(sequence=view['sequence'],turn=view['observation']['turn'])
            return receipt
        if turn_index==max_turns:raise RuntimeError('No native placement offer within the explicit preparation turn limit')
        if not view['observation']['cities']:
            candidates=offers('found_city')
            if not candidates:raise RuntimeError('Placement preparation has no offered foundation')
            step(min(candidates,key=lambda a:(a['unit_id'],a['x'],a['y'])))
            if ready():
                receipt['prepared_boundary']=dict(sequence=get_view()['sequence'],turn=get_view()['observation']['turn'])
                return receipt
        astrology=[a for a in offers('research') if a['hash']==identity['action_hash']]
        if astrology:
            if len(astrology)!=1:raise RuntimeError('Ambiguous public Astrology offer')
            if get_view()['decisions']['choice_state']['research']['research']!=astrology[0]['index']:step(astrology[0])
            receipt['astrology_native_index']=astrology[0]['index']
        elif 'astrology_native_index' not in receipt:
            raise RuntimeError('Astrology is not publicly offered; preparation cannot infer completion')
        for kind in ('research','civic'):
            if get_view()['decisions']['choice_state']['research'][kind] is None:
                candidates=offers(kind)
                if candidates:step(min(candidates,key=lambda a:(a['index'],a['hash'])))
        for city in list(get_view()['decisions']['choice_state']['production']):
            if city['queue_size']==0:
                candidates=[a for a in offers('production') if a['city_id']==city['city_id']]
                if not candidates:raise RuntimeError('Placement preparation has no ordinary production offer')
                step(min(candidates,key=lambda a:(a['item_type']!='BUILDING_MONUMENT',a['item_type']!='UNIT_WARRIOR',a['item_type'])))
        candidates=offers('end_turn') or offers('force_end_turn')
        if len(candidates)!=1:raise RuntimeError('Placement preparation lacks a unique offered turn request')
        start_turn=get_view()['observation']['turn'];step(candidates[0])
        for _ in range(32):
            if get_view()['observation']['turn']==start_turn+1 and active():break
            step()
        if get_view()['observation']['turn']!=start_turn+1 or not active():
            raise RuntimeError('Placement preparation did not reach the next active turn within 32 updates')


def continue_city_specialist(get_view, choose, poll, *, max_turns, remaining, identity, receipt,
                             building_readback=None):
    """Follow the native Holy Site and Shrine offers through a resumable Save boundary."""
    from civ6_host.contracts.network_turn import CAPABILITY_CITY_CONTROLS_SCHEMA

    if type(max_turns) is not int or not 1<=max_turns<=12:
        raise ValueError('Specialist preparation requires one to twelve turns')
    initial=get_view()
    initial_turn=initial['observation']['turn']
    if initial['decisions']['schema']!=CAPABILITY_CITY_CONTROLS_SCHEMA:
        raise ValueError('Specialist preparation requires an exact v12 native checkpoint')
    city_ids={city['id'] for city in initial['observation']['cities']}
    if len(city_ids)!=1:
        raise ValueError('Specialist preparation expects the one original city')
    city_id,=city_ids

    def holy_site(view):
        rows=[row for row in view['decisions']['placement_inventory']['rows']
              if row['city_id']==city_id and row['category']=='district'
              and row['item_type']=='DISTRICT_HOLY_SITE']
        if len(rows)!=1:
            raise ValueError('Specialist preparation requires the native placed Holy Site')
        return rows[0]

    district=holy_site(initial)
    receipt.update(initial_turn=initial_turn,initial_sequence=initial['sequence'],
                   city_id=city_id,holy_site=copy.deepcopy(district),transitions=[],poll_calls=0,
                   save_reserve_seconds=65,minimum_turn_seconds=120,max_turns=max_turns,
                   source_identity=copy.deepcopy(identity),specialist_qualified=False)

    def active(view):
        controls=view['decisions']['turn_controls']
        return (controls['active'] is True and controls['active_complete'] is True
                and controls['can_unready'] is False and controls['timer_elapsed'] is False
                and not view['outcome']['terminated'] and not view['outcome']['truncated'])

    def offers(kind, **fields):
        return [row['action'] for row in get_view()['decisions']['candidates']
                if row['action']['kind']==kind
                and all(row['action'].get(key)==value for key,value in fields.items())]

    def step(action):
        before=get_view()
        if action is None:
            poll()
            receipt['poll_calls']+=1
        else:
            result=choose(action['kind'],**{k:v for k,v in action.items() if k!='kind'})
            receipt['transitions'].append(dict(sequence_before=before['sequence'],
                sequence_after=get_view()['sequence'],action=copy.deepcopy(action),command_result=result))

    def citizen(view):
        rows=[r for catalog in view['decisions']['citizen_catalogs'] if catalog['city_id']==city_id
              for r in catalog['plots'] if r['plot_id']==district['plot_id']]
        if len(rows)>1:
            raise RuntimeError('Ambiguous native specialist target')
        return rows[0] if rows else None

    observed_turn_seconds=120
    while True:
        view=get_view()
        if not active(view):
            raise RuntimeError('Specialist preparation lacks an active complete Save boundary')
        current=holy_site(view)
        if any(current[key]!=district[key] for key in ('city_id','plot_id','district_id','index','hash')):
            raise RuntimeError('Holy Site identity changed')
        queues=[r for r in view['decisions']['production_queues'] if r['city_id']==city_id]
        if len(queues)!=1:
            raise RuntimeError('Missing or ambiguous native city production queue')
        queue=queues[0]['entries']
        head=queue[0]['hash'] if queue else None
        receipt.update(turns_advanced=view['observation']['turn']-initial_turn,
                       final_holy_site=copy.deepcopy(current),production_head=head,
                       final_sequence=view['sequence'],final_turn=view['observation']['turn'])
        building=building_readback(view,current) if current['complete'] and building_readback else None
        if building is not None:
            receipt.setdefault('building_readbacks',[]).append(building)
        if building is not None and building['building']['present']:
            target=citizen(view)
            actions=offers('city_citizen',city_id=city_id,plot_id=current['plot_id'])
            if target is None or not actions:
                receipt['stop_reason']='native_specialist_offer_unavailable'
                return receipt
            if len(actions)!=1 or any(actions[0][key]!=target[key] for key in ('occupied','locked','x','y')):
                raise RuntimeError('Native specialist action differs from its exact target')
            if target['locked'] or remaining()<95:
                receipt['stop_reason']='specialist_already_locked' if target['locked'] else 'save_reserve'
                return receipt
            step(actions[0])
            final=get_view()
            after=citizen(final)
            post_building=building_readback(final,holy_site(final))
            if (not active(final) or after is None or after['locked'] is not True
                    or after['occupied'] is not True or post_building is None
                    or post_building['building']['present'] is not True):
                raise RuntimeError('Native specialist click did not produce a locked, occupied district target')
            receipt['building_readbacks'].append(post_building)
            receipt.update(specialist_qualified=True,stop_reason='specialist_assigned',
                           specialist_before=copy.deepcopy(target),specialist_after=copy.deepcopy(after),
                           final_sequence=final['sequence'],final_turn=final['observation']['turn'])
            return receipt
        if current['complete'] and head!=identity['shrine_hash']:
            shrine=offers('production',city_id=city_id,item_type='BUILDING_SHRINE',
                          hash=identity['shrine_hash'])
            if not shrine:
                # Production can disappear for multiple reasons. Stop at the
                # native boundary and require a separate HasBuilding readback.
                receipt['stop_reason']='shrine_readback_required'
                return receipt
            if len(shrine)!=1:
                raise RuntimeError('Ambiguous native Shrine offer')
            if remaining()<95:
                receipt['stop_reason']='save_reserve'
                return receipt
            step(shrine[0])
            entries=next(r['entries'] for r in get_view()['decisions']['production_queues']
                         if r['city_id']==city_id)
            if not entries or entries[0]['hash']!=identity['shrine_hash']:
                raise RuntimeError('Native Shrine selection did not become production head')
            continue
        if not current['complete'] and head!=district['hash']:
            resume=offers('production_resume',city_id=city_id,item_type='DISTRICT_HOLY_SITE',
                          hash=district['hash'],index=district['index'])
            if len(resume)!=1:
                raise RuntimeError('Unfinished Holy Site has no unique public resume offer')
            if remaining()<95:
                receipt['stop_reason']='save_reserve'
                return receipt
            step(resume[0])
            entries=next(r['entries'] for r in get_view()['decisions']['production_queues']
                         if r['city_id']==city_id)
            if not entries or entries[0]['hash']!=district['hash']:
                raise RuntimeError('Native Holy Site resume did not become production head')
            continue
        if receipt['turns_advanced']>=max_turns or remaining()<65+observed_turn_seconds:
            receipt['stop_reason']='turn_limit' if receipt['turns_advanced']>=max_turns else 'save_reserve'
            return receipt
        candidates=offers('end_turn') or offers('force_end_turn')
        if len(candidates)!=1:
            raise RuntimeError('Specialist preparation lacks a unique offered turn request')
        start_turn=view['observation']['turn']
        started=time.perf_counter()
        step(candidates[0])
        for _ in range(32):
            if get_view()['observation']['turn']==start_turn+1 and active(get_view()):
                break
            if remaining()<35:
                raise RuntimeError('Native turn transition exhausted the poll time allowance')
            step(None)
        if get_view()['observation']['turn']!=start_turn+1 or not active(get_view()):
            raise RuntimeError('Specialist preparation did not reach the next active turn within 32 updates')
        observed_turn_seconds=max(observed_turn_seconds,time.perf_counter()-started)




def city_specialist_readbacks(run, identity):
    """Read the flushed private receipts after accepting each public response."""
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    from civ6_host.runtime.xp2_placement_inventory_source import SOURCE

    offset=0
    def read(view, district):
        nonlocal offset
        matches=[]
        observed=view['observation']
        revision={key:view[key] for key in ('episode_id','game_generation','sequence')}
        revision.update(turn=observed['turn'],player_id=observed['player_id'])
        with (run/'events.jsonl').open('rb') as events:
            events.seek(offset)
            for raw in events:
                if not raw.endswith(b'\n'):
                    break
                offset+=len(raw)
                if b'native_city_specialist_preparation_readback' not in raw:
                    continue
                event=json.loads(raw)
                if (event.get('stage')=='native_city_specialist_preparation_readback'
                        and all(event.get(k)==v for k,v in revision.items())
                        and event.get('district_plot_id')==district['plot_id']):
                    matches.append(event)
        if not matches:
            return None
        if len(matches)!=1:
            raise ValueError('Duplicate private Shrine readback for a public revision')
        event=matches[0]
        building=event['building']
        if (event.get('source_proof_sha256')!=SOURCE[1] or event.get('core_sha256')!=XP2_CORE_SHA256
                or event.get('diagnostic_only') is not True or building.get('city_id')!=district['city_id']
                or building.get('building_type')!='BUILDING_SHRINE'
                or building.get('hash')!=identity['shrine_hash']
                or type(building.get('index')) is not int or not 0<=building['index']<=2147483647
                or type(building.get('present')) is not bool):
            raise ValueError('Private Shrine readback source or building identity differs')
        return event
    return read



def exercise_placement_group(get_view, choose, *, category, defer_resume=False):
    """Explicit place/replace/resume on an already prepared native boundary."""
    from civ6_host.contracts.network_turn import CAPABILITY_PLACEMENT_SCHEMA, CAPABILITY_PLACEMENT_INVENTORY_SCHEMA, CAPABILITY_UNIT_ATTACKS_SCHEMA, CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA
    if category not in ('district','building'):raise ValueError('Select a placement category explicitly')
    if type(defer_resume) is not bool:raise ValueError('Resumption boundary must be explicit')
    initial=copy.deepcopy(get_view());steps=[];turn=initial['observation']['turn']
    if initial['decisions']['schema'] not in (CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA):
        raise ValueError('Placement group requires the explicit v7 catalogue')
    choices=[a for a in initial['decisions']['placement_offers'] or []
             if a['kind']=='production_placement' and a['category']==category]
    if not choices:raise RuntimeError('Prepared native boundary has no offered '+category+' placement')
    action=min(choices,key=lambda a:(a['city_id'],a['index'],a['plot_id']));city_id=action['city_id']
    def state(view):
        d=view['decisions']
        return dict(production=copy.deepcopy(next(r for r in d['choice_state']['production'] if r['city_id']==city_id)),
                    placements=copy.deepcopy(d['placements']),production_queues=copy.deepcopy(d['production_queues']))
    def perform(a):
        before=state(get_view());command=choose(a['kind'],**{k:v for k,v in a.items() if k!='kind'})
        after=state(get_view())
        if get_view()['observation']['turn']!=turn:raise RuntimeError('Placement group crossed an unexpected turn')
        step=dict(sequence=get_view()['sequence'],action=copy.deepcopy(a),command_result=copy.deepcopy(command),
                  before=before,after=after)
        steps.append(step);return step
    placed=perform(action)
    row=next((r for r in placed['after']['placements'] if r['city_id']==city_id and r['plot_id']==action['plot_id']),None)
    if (row is None or not row['exists'] or row['complete']
            or any(row[k]!=action[k] for k in ('category','index','item_type','x','y'))):
        raise RuntimeError('Native placement did not expose the selected unfinished own plot')
    ordinary=[r['action'] for r in get_view()['decisions']['candidates'] if r['action']['kind']=='production'
              and r['action']['city_id']==city_id and r['action']['hash']!=action['hash']]
    if not ordinary:raise RuntimeError('No native ordinary replacement offered for the placed item')
    replaced=perform(min(ordinary,key=lambda a:(a['category']!='unit',a['index'],a['hash'])))
    if (replaced['after']['production']['hash']!=replaced['action']['hash']
            or replaced['after']['placements']!=placed['after']['placements']):
        raise RuntimeError('Native replacement lost current production or tracked placement')
    resume=next((a for a in get_view()['decisions']['placement_offers'] if a['kind']=='production_resume'
                 and all(a[k]==action[k] for k in ('city_id','category','index','hash','item_type'))),None)
    if resume is None:raise RuntimeError('Native resumption of the same placed item is not offered')
    if not defer_resume:
        resumed=perform(resume)
        if (resumed['after']['production']['hash']!=action['hash']
                or resumed['after']['placements']!=placed['after']['placements']):
            raise RuntimeError('Native resumption did not restore production on the same tracked plot')
    return dict(category=category,city_id=city_id,plot_id=action['plot_id'],item_type=action['item_type'],
        steps=steps,initial_turn=turn,final_turn=get_view()['observation']['turn'],poll_calls=0,
        observation_scope='host_tracked',completion_witnessed=False,other_category_qualified=False,
        unobserved_placement_inventory_complete=False)


def compare_checkpoint_public(expected, actual):
    """Rebind only episode identity/revision; every qualified public value stays."""
    from civ6_host.runtime.native.native_session_resume import semantic_decisions
    if (actual['episode_id']==expected['episode_id'] or actual['game_generation']==expected['game_generation']
            or actual['sequence']!=0 or actual['observation']!=expected['observation']
            or semantic_decisions(actual['decisions'])!=semantic_decisions(expected['decisions'])):
        raise RuntimeError('Checkpoint reload changed qualified public state/choices or reused episode identity')


def checkpoint_rest_action(view):
    from civ6_host.contracts.network_turn import CAPABILITY_UNIT_ORDERS_SCHEMA, CAPABILITY_PRODUCTION_QUEUE_SCHEMA, CAPABILITY_PLACEMENT_SCHEMA, CAPABILITY_PLACEMENT_INVENTORY_SCHEMA, CAPABILITY_UNIT_ATTACKS_SCHEMA, CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA
    if view['decisions']['schema'] not in (CAPABILITY_UNIT_ORDERS_SCHEMA,CAPABILITY_PRODUCTION_QUEUE_SCHEMA,CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA):
        raise ValueError('XP1 checkpoint group requires qualified native unit orders')
    offered=[r['action'] for r in view['decisions']['candidates']]
    selectable={a['unit_id'] for a in offered if a['kind']=='world_select_unit'}
    founders={a['unit_id'] for a in offered if a['kind']=='found_city'}
    rests=[a for a in offered if a['kind']=='unit_order' and a['unit_id'] in selectable
           and a['item_type'] in ('UNITOPERATION_FORTIFY','UNITOPERATION_SLEEP')]
    if not rests:raise ValueError('No native rest action offered for checkpoint exercise')
    return min(rests,key=lambda a:(a['unit_id'] in founders,a['item_type']!='UNITOPERATION_SLEEP',a['unit_id']))


def exercise_unit_work(get_view, choose, advance, *, consume_all=False, reopen=None):
    """Produce and use one builder through existing native client adapters.

    This witnesses the public inputs and native effects. UnitPanel event/UI
    parity remains a separately reported gap, never inferred from this test.
    All target selection below reads only the public view and native offers.
    """
    def offers(kind):
        return [r['action'] for r in get_view()['decisions']['candidates']
                if r['action']['kind'] == kind]

    def unit_state(uid):
        return next(r for r in get_view()['decisions']['unit_work_state']['units']
                    if r['unit_id'] == uid)

    def plot_state(plot_id):
        return next(r for r in get_view()['decisions']['plot_info']['plots']
                    if r['plot_id'] == plot_id)

    initial = get_view()
    original_ids = {u['id'] for u in initial['observation']['units']}
    production = next(a for a in offers('production') if a['item_type'] == 'UNIT_BUILDER')
    choose('production', city_id=production['city_id'], item_type='UNIT_BUILDER')
    builder = None
    for waited in range(13):
        builder = next((u for u in get_view()['observation']['units']
                        if u['id'] not in original_ids and u['type'] == production['index']), None)
        if builder is not None:
            break
        if waited == 12:
            raise RuntimeError('No naturally produced builder within twelve native turns')
        advance()
    uid = builder['id']
    born = dict(unit_state(uid))
    visits = set()
    selected = None
    for _ in range(8):
        state = unit_state(uid)
        rows = [a for a in offers('build_improvement') if a['unit_id'] == uid]
        if rows:
            selected = min(rows, key=lambda a:(a['plot_id'],a['index']))
            break
        if float(state['moves_token']) == 0:
            advance()
            continue
        public = {p['index']:p for p in get_view()['observation']['plots']
                  if p['visible'] and p['owner'] == get_view()['observation']['player_id']}
        city_plots = {(c['x'],c['y']) for c in get_view()['observation']['cities']}
        rows = [a for a in offers('move') if a['unit_id'] == uid
                and a['destination_plot_id'] in public
                and a['destination_plot_id'] not in visits
                and (a['destination_x'],a['destination_y']) not in city_plots]
        if not rows:
            raise RuntimeError('No unvisited native builder move to a public owned tile')
        target = min(rows,key=lambda a:a['destination_plot_id'])
        visits.add(target['destination_plot_id'])
        choose('move',unit_id=uid,destination_plot_id=target['destination_plot_id'])
    if selected is None:
        raise RuntimeError('No improvement offer on the bounded public builder route')
    before = dict(unit_state(uid))
    plot_before = plot_state(selected['plot_id'])
    other=next(u['id'] for u in get_view()['observation']['units'] if u['id']!=uid)
    choose('world_select_unit',unit_id=other)
    choose('build_improvement', unit_id=uid, plot_id=selected['plot_id'], item_type=selected['item_type'])
    if get_view()['decisions']['world_input']['selected_unit_id']!=uid:
        raise RuntimeError('Compound build did not select its requested unit')
    after = dict(unit_state(uid))
    plot_after = plot_state(selected['plot_id'])
    if (after['charges'] != before['charges'] - 1
            or plot_after['improvement'] is None
            or plot_after['improvement']['type'] != selected['item_type']):
        raise RuntimeError('Public builder charge/improvement effect differs from the command')
    if float(after['moves_token']) != 0:
        raise RuntimeError('This witness did not reach the intended exhausted-builder observation')
    advance()
    choose('world_select_unit',unit_id=other)
    choose('terrain_operation', unit_id=uid, operation='REMOVE_IMPROVEMENT')
    if get_view()['decisions']['world_input']['selected_unit_id']!=uid:
        raise RuntimeError('Compound removal did not select its requested unit')
    removed = plot_state(selected['plot_id'])
    if removed['improvement'] is not None:
        raise RuntimeError('Native removal still leaves a public improvement')
    result=dict(unit_id=uid, production=production, production_turns=waited,
        born=born, visited_public_plots=sorted(visits), build_action=selected,
        before=before, after=after, plot_before=plot_before, plot_after=plot_after,
        after_removal=dict(unit_state(uid)), plot_after_removal=removed,
        exhausted_builder_charges_visible=True, native_requests_used=True,
        compound_selection_verified=True,selection_mode='manual_logical_own_unit',
        unit_panel_parity_qualified=False, strategic_training_ready=False)
    if consume_all:
        if reopen is not None:
            result['prepared_checkpoint']=reopen()
        tail=[]
        for _ in range(8):
            advance()
            previous=dict(unit_state(uid))
            choose('build_improvement',unit_id=uid,plot_id=selected['plot_id'],item_type=selected['item_type'])
            view=get_view()
            alive=any(u['id']==uid for u in view['observation']['units'])
            tail.append(dict(turn=view['observation']['turn'],charges_before=previous['charges'],unit_present=alive,
                             selected_unit_id=view['decisions']['world_input']['selected_unit_id']))
            if not alive:
                if previous['charges']!=1:
                    raise RuntimeError('Builder disappeared before the expected final charge witness')
                if (view['decisions']['world_input']['selected_unit_id'] is not None
                        or any(r['unit_id']==uid for r in view['decisions']['unit_work_state']['units'])
                        or any(r['action'].get('unit_id')==uid for r in view['decisions']['candidates'])):
                    raise RuntimeError('Consumed builder left a stale selection, state or action')
                result.update(final_charge_consumed=True,consumption_tail=tail,
                    final_plot=plot_state(selected['plot_id']),replacement_unit_not_selected=True)
                break
            if unit_state(uid)['charges']!=previous['charges']-1:
                raise RuntimeError('Additional native build did not consume the expected charge')
            advance()
            choose('terrain_operation',unit_id=uid,operation='REMOVE_IMPROVEMENT')
        else:
            raise RuntimeError('Builder not consumed within the bounded charge exercise')
    return result


def exercise_terrain_work(get_view, choose, advance, *, growth_only=False):
    """Use the retained prepared builder; never synthesize a pillaged tile.

    This exact Base checkpoint has wheat at the builder's tile and adjacent
    owned woods. Technology IDs 0/2 come from its pinned final database. The
    offered commands remain the sole admission authority for every gesture.
    """
    def actions(kind):return [r['action'] for r in get_view()['decisions']['candidates'] if r['action']['kind']==kind]
    builders=[u for u in get_view()['decisions']['unit_work_state']['units'] if u['charges']==2]
    if len(builders)!=1:raise RuntimeError('Expected the prepared two-charge builder')
    uid=builders[0]['unit_id'];result={'unit_id':uid,'builder_production_repeated':False,'effects':[]}
    def offered(op):return next((a for a in actions('terrain_operation') if a['unit_id']==uid and a['operation']==op),None)
    def perform(op):
        action=offered(op)
        if action is None:raise RuntimeError('Required native terrain offer absent: '+op)
        view=get_view();before=next(p for p in view['observation']['plots'] if p['index']==action['plot_id'])
        detail=next(r for r in view['decisions']['unit_work_info']['offers'] if r['action']==action)
        cities=view['observation']['cities'];production=view['decisions']['production_info']
        growth=view['decisions'].get('city_growth');before_sequence=view['sequence']
        choose('terrain_operation',unit_id=uid,operation=op)
        view=get_view();after=next(p for p in view['observation']['plots'] if p['index']==action['plot_id'])
        field='resource_type' if op=='HARVEST_RESOURCE' else 'feature_type'
        if before.get(field,-1)<0 or after.get(field,-1)!=-1:raise RuntimeError('Public terrain removal absent')
        result['effects'].append(dict(operation=op,turn=view['observation']['turn'],offered_information=detail,
            plot_before=before,plot_after=after,cities_before=cities,cities_after=view['observation']['cities'],
            production_before=production,production_after=view['decisions']['production_info'],
            growth_before=growth,growth_after=view['decisions'].get('city_growth'),
            before_sequence=before_sequence,after_sequence=view['sequence']))
    choose('research',index=0)
    for _ in range(5):
        if offered('HARVEST_RESOURCE'):break
        advance()
    else:raise RuntimeError('Wheat harvest not unlocked within bounded native turns')
    perform('HARVEST_RESOURCE')
    if growth_only:
        effect=result['effects'][-1]
        if effect['growth_before'] is None or effect['growth_after'] is None:
            raise RuntimeError('Growth acceptance lacks public city inputs')
        before=effect['growth_before']['cities'][0];after=effect['growth_after']['cities'][0]
        if before['display']['FoodNeededForGrowth']==after['display']['FoodNeededForGrowth']:
            raise RuntimeError('Harvest did not change displayed food remaining')
        result['scope']='Native harvest credit and new growth inputs; retained clearing witness not repeated'
        return result
    choose('research',index=2)
    choose('production',item_type='BUILDING_MONUMENT')
    reached=False
    for _ in range(8):
        if offered('REMOVE_FEATURE'):break
        if not reached:
            v=get_view();plots={p['index']:p for p in v['observation']['plots'] if p['visible'] and p['owner']==v['observation']['player_id'] and p['feature_type']==3}
            moves=[a for a in actions('move') if a['unit_id']==uid and a['destination_plot_id'] in plots]
            if moves:
                a=min(moves,key=lambda a:a['destination_plot_id'])
                choose('move',unit_id=uid,destination_plot_id=a['destination_plot_id']);reached=True
                continue
        advance()
    else:raise RuntimeError('Owned woods removal not available within bounded native turns')
    perform('REMOVE_FEATURE')
    view=get_view()
    if any(u['id']==uid for u in view['observation']['units']):raise RuntimeError('Two native removals did not consume the last charges')
    if any(r['action'].get('unit_id')==uid for r in view['decisions']['candidates']):raise RuntimeError('Consumed work unit still actionable')
    result.update(final_unit_absent=True,repair_positive_effects_qualified=False,
                  limitation='No naturally pillaged improvement/route exists in this prepared witness; repairs are not reported as executed.')
    return result


def exercise_production_inputs(get_view,choose,advance):
    """Native queue progress, completion and following-item credit; no rule port."""
    def actions(kind):return [r['action'] for r in get_view()['decisions']['candidates'] if r['action']['kind']==kind]
    def current():return get_view()['decisions']['production']['cities'][0]
    builders=[u for u in get_view()['decisions']['unit_work_state']['units'] if u['charges']==2]
    if len(builders)!=1:raise RuntimeError('Production witness needs the retained prepared builder')
    uid=builders[0]['unit_id'];result=dict(initial=current(),snapshots=[],builder_production_repeated=False)
    choose('research',index=2)
    choose('production',item_type='BUILDING_MONUMENT')
    result['after_selection']=current()
    choose('queue_append',item_type='UNIT_SCOUT')
    reached=False
    for _ in range(6):
        view=get_view();row=current()
        if row['state']!='current' or row['item']['item_type']!='BUILDING_MONUMENT':
            raise RuntimeError('Monument finished before the intended chop boundary')
        result['snapshots'].append(dict(sequence=view['sequence'],turn=view['observation']['turn'],production=row))
        operation=next((a for a in actions('terrain_operation') if a['unit_id']==uid and a['operation']=='REMOVE_FEATURE'),None)
        if operation is not None and 0<row['item']['cost']-row['item']['progress']<11:
            details=next(r for r in view['decisions']['unit_work_info']['offers'] if r['action']==operation)
            result.update(before=copy.deepcopy(row),before_sequence=view['sequence'],before_turn=view['observation']['turn'],offered_information=details)
            choose('terrain_operation',unit_id=uid,operation='REMOVE_FEATURE')
            result.update(after=copy.deepcopy(current()),after_sequence=get_view()['sequence'],after_turn=get_view()['observation']['turn'])
            if result['after_turn']!=result['before_turn'] or current()['state']!='current' or current()['item']['item_type']!='UNIT_SCOUT':
                raise RuntimeError('Native chop did not complete the current item and advance the queue in the same turn')
            result['remaining_queue']=copy.deepcopy(get_view()['decisions']['production_queues'])
            return result
        if not reached:
            owned={p['index'] for p in view['observation']['plots'] if p['visible'] and p['owner']==view['observation']['player_id'] and p['feature_type']==3}
            move=next((a for a in actions('move') if a['unit_id']==uid and a['destination_plot_id'] in owned),None)
            if move is not None:
                choose('move',unit_id=uid,destination_plot_id=move['destination_plot_id']);reached=True
                continue
        advance()
    raise RuntimeError('No near-completion native production/chop boundary within the bounded continuation')


def replay_information(evidence_path, group, output):
    """Check new read-only client projections on exact retained native replies.

    Recorded commands are replayed through SessionClient, never executed in the
    engine. This intentionally proves no new native-call or gameplay behavior.
    """
    from civ6_host import InformationUnavailable, SessionClient
    from civ6_host.contracts.information import PUBLIC_GROUPS
    from civ6_host.runtime.information_store import InformationStore
    from civ6_host.runtime.production_inputs import SOURCE as production_source
    from civ6_host.runtime.city_growth import SOURCE as growth_source
    groups = PUBLIC_GROUPS if group == 'all' else (group,)

    def ref(path):
        with path.open('rb') as stream:
            pin = hashlib.file_digest(stream, 'sha256').hexdigest()
        return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=pin)

    evidence_path = evidence_path.resolve()
    original = json.loads(evidence_path.read_text(encoding='utf-8'))
    if original.get('all_pinned_sources_unchanged') is not True:
        raise ValueError('Replay requires an unchanged-source native receipt')
    root = evidence_path.parent.parent

    def checked_file(key):
        expected = original[key]
        path = (root / expected['path']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Retained evidence path leaves its resource root')
        actual = ref(path)
        if any(actual[k] != expected[k] for k in ('bytes','sha256')):
            raise ValueError('Retained native evidence changed: ' + key)
        return path

    events = checked_file('events')
    acceptance = checked_file('native_acceptance')
    checked_file('supervisor')
    commands_file = events.parent / 'commands.jsonl'
    commands = []
    with commands_file.open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip() == 'go':
                continue
            if len(line) > 1024 * 1024 or len(commands) >= 4096:
                raise ValueError('Recorded command trace exceeds the replay bound')
            commands.append(json.loads(line))

    class ReplayBackend:
        def __init__(self, stream):
            self.stream = stream
            self.cursor = 0
            self.prefix_lines = 0
            self.records = iter(session_records(events.parent))
            self.aborts = []
            self.store = InformationStore(
                {'production':production_source[1], 'growth':growth_source[1]})

        def response(self):
            while True:
                try:
                    _,line,event=next(self.records)
                except StopIteration:
                    raise ValueError('Missing recorded native response')
                self.prefix_lines += int(not line.lstrip().startswith(b'{'))
                self.store.ingest(event)
                if event.get('stage') == 'official_session_response':
                    return event

        def reset(self):
            response = self.response()
            if response.get('operation') != 'reset':
                raise ValueError('Native replay does not start with reset')
            return response

        def request(self, request):
            if self.cursor >= len(commands) or request != commands[self.cursor]:
                raise ValueError('Client request differs from the recorded native request')
            self.cursor += 1
            return self.response()

        def abort(self, reason):
            self.aborts.append(reason)

        def read_administrative(self, group, response):
            return self.store.read(group, response)

    report = dict(schema='civ6-host.information-replay.v1',
        classification='retained_native_client_replay', group=group,
        source_receipt=ref(evidence_path), native_acceptance=ref(acceptance),
        events=ref(events), commands=ref(commands_file), queries=[], unavailable=[],
        native_processes_started=0, training_started=False,
        proves_new_native_calls=False, strategic_training_ready=False)
    started = time.monotonic()
    with events.open('rb') as stream:
        backend = ReplayBackend(stream)
        client = SessionClient(backend, allow_administrative=True)
        view = client.reset()

        def check_group(selected_group):
            try:
                public = client.information(selected_group)
            except InformationUnavailable as exc:
                report['unavailable'].append(dict(group=selected_group,sequence=view['sequence'], reason=str(exc)))
                return
            admin = None
            if selected_group != 'unit_work':
                admin = client.information(selected_group, channel='administrative')
            identity = ('episode_id','game_generation','player_id','sequence','turn',
                        'native_decision_id','source_contracts')
            if admin is not None and any(public[k] != admin[k] for k in identity):
                raise ValueError('Public and administrative query boundaries differ')
            d = view['decisions']
            if selected_group == 'economy':
                for field in ('treasury','yield_display','research_info','research_progress'):
                    if admin['data'][field] != d[field]:
                        raise ValueError('Administrative query changed its native snapshot')
            elif selected_group == 'unit_work':
                try:
                    client.information(selected_group,channel='administrative')
                except InformationUnavailable:
                    pass
                else:
                    raise ValueError('Unqualified unit-work administrative query was accepted')
            row = dict(group=selected_group,
                **{k:public[k] for k in ('episode_id','game_generation','player_id','sequence','turn')},
                public_sha256=hashlib.sha256(json.dumps(public,sort_keys=True).encode()).hexdigest(),
                administrative_sha256=(None if admin is None else hashlib.sha256(
                    json.dumps(admin,sort_keys=True).encode()).hexdigest()))
            if selected_group == 'economy':
                row.update(treasury=public['data']['treasury'],global_yields=public['data']['global_yields'],
                    research_selected={topic:public['data']['research'][topic]['selected']
                                       for topic in ('technology','civic')})
            elif selected_group == 'production':
                row['current']=public['data']['current']
            report['queries'].append(row)

        def check():
            for selected_group in groups:
                check_group(selected_group)

        check()
        for command in commands:
            operation, pid = command['operation'], command['player_id']
            if operation == 'act':
                selection = command['selection']
                view = client.act(pid, selection['decision_id'], selection['candidate_id'],
                                  parameters=selection.get('parameters'))
            elif operation in ('observe','poll','close'):
                view = getattr(client, operation)(pid)
            else:
                raise ValueError('Unsupported recorded command')
            check()
        if backend.aborts or backend.cursor != len(commands) or not report['queries']:
            raise ValueError('Client replay was not fully accepted')
        # Exhaust the retained transcript to authenticate its exact native-text
        # occurrence ledger; do not stop validation at the last public reply.
        for _,_,event in backend.records:
            if event.get('stage') in ('official_session_response','official_session_refused'):
                raise ValueError('Unexpected public reply after the replayed command stream')
        report.update(status='passed', replayed_commands=backend.cursor,
                      prefixed_event_lines=backend.prefix_lines, seconds=time.monotonic()-started)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'], output=str(output),
        queries=len(report['queries']), unavailable=len(report['unavailable']),
        replayed_commands=report['replayed_commands'],seconds=report['seconds'])))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--config', type=Path)
    inputs.add_argument('--replay-information', type=Path,
        help='Native receipt to replay through a new read-only information query; no engine execution')
    parser.add_argument('--information-group', choices=('economy','production','growth','unit_work','all'), default='economy')
    parser.add_argument('--replay-output', type=Path)
    parser.add_argument('--replacement-reset', action='store_true')
    parser.add_argument('--capability-cycle', action='store_true',
        help='Exercise an explicit capability family, real close and new-process reset, without claiming turns')
    parser.add_argument('--choice-group', action='store_true',
        help='With --capability-cycle, exercise explicit research/civic and production replacement')
    parser.add_argument('--world-input-group', action='store_true',
        help='With --capability-cycle, exercise own-unit selection, public grid click and deselection')
    parser.add_argument('--placement-group', action='store_true',
        help='With --capability-cycle, place/replace/resume one actually offered district or wonder')
    parser.add_argument('--placement-inventory-cycle', action='store_true',
        help='Place/switch/Save, reload native inventory and resume, then reset the same checkpoint')
    parser.add_argument('--placement-category', choices=('district','building'), default='district')
    parser.add_argument('--placement-prepare-turns',type=int,default=0,
        help='Prepare a district placement witness or, with --city-controls, save the placed Holy Site')
    parser.add_argument('--city-specialist-turns',type=int,default=0,
        help='Continue the v12 Holy Site checkpoint through bounded Shrine preparation and Save')
    parser.add_argument('--production-queue-group', action='store_true',
        help='With --capability-cycle, exercise offered append/swap/eighth-slot replacement/remove and reset')
    parser.add_argument('--unit-order-group', action='store_true',
        help='With --capability-cycle, exercise native rest/wake and witnessed queued-move cancellation')
    parser.add_argument('--unit-attack-group', action='store_true',
        help='With --capability-cycle, execute one offered attack on a prepared native boundary and reset')
    parser.add_argument('--prepare-unit-attack', type=Path,
        help='Prepare a real contact by bounded public exploration; write receipts to this new directory')
    parser.add_argument('--preparation-lifetimes',type=int,default=4)
    parser.add_argument('--preparation-seconds',type=int,default=900)
    parser.add_argument('--turn-group',action='store_true',
        help='With --capability-cycle, exercise native readiness/unready, one turn, close and reset')
    parser.add_argument('--repeat-forced-turn',action='store_true',
        help='With --turn-group, submit Shift+Enter again while the local human is inactive')
    parser.add_argument('--turn-action', choices=('normal', 'forced'), default='normal')
    parser.add_argument('--dialogue-turns', type=int, default=0,
        help='Bounded public exploration acceptance; require a real native dialogue')
    parser.add_argument('--stdout-limit-mib', type=int,
        help='Explicit diagnostic trace budget; the native supervisor enforces its ceiling')
    parser.add_argument('--city-controls', action='store_true',
        help='Exercise source-admitted city focus, citizens and production queue as a group')
    parser.add_argument('--map-controls', action='store_true',
        help='Exercise native world click/cancel and plot purchase through the public client')
    parser.add_argument('--checkpoint-cycle', action='store_true',
        help='Save and reopen two successive native LAN component pairs through the existing client')
    parser.add_argument('--unit-work', action='store_true',
        help='Read public charges and execute native builder production/build/removal; UI parity stays explicit')
    parser.add_argument('--unit-panel-cycle', action='store_true',
        help='Verify the newly integrated native UnitPanel event guard over one turn, without repeating builder production')
    parser.add_argument('--consume-builder', action='store_true',
        help='With --unit-work, continue through native final-charge disappearance and selection cleanup')
    parser.add_argument('--terrain-work',action='store_true',
        help='Use the prepared builder checkpoint for native harvest/feature removal and public UnitPanel information')
    parser.add_argument('--growth-harvest',action='store_true',
        help='Qualify new public growth inputs and native food credit on the prepared harvest boundary only')
    parser.add_argument('--production-inputs',action='store_true',
        help='Qualify public production progress, native completion and queue advancement from the retained builder')
    args = parser.parse_args()
    if args.replay_information:
        if args.replay_output is None:
            parser.error('--replay-output is required with --replay-information')
        return replay_information(args.replay_information,args.information_group,args.replay_output)
    config = json.loads(args.config.read_text(encoding='utf-8'))
    if args.city_specialist_turns and (
            not 1<=args.city_specialist_turns<=12 or not args.city_controls
            or args.placement_prepare_turns or args.prepare_unit_attack is not None
            or args.replacement_reset or config.get('input_profile')!='xp2-lan'
            or not config.get('checkpoint') or config.get('checkpoint_on_close') is not True
            or config.get('city_focus_diagnostic') is not True
            or config.get('city_management_diagnostic') is not True
            or type(config.get('lifetime_seconds')) is not int
            or not 1<=config['lifetime_seconds']<=900):
        parser.error('Specialist continuation requires city controls, a native XP2 checkpoint, Save, and a bounded lifetime')
    if args.prepare_unit_attack is not None:
        if (args.capability_cycle or args.checkpoint_cycle or args.placement_inventory_cycle
                or args.replacement_reset or args.dialogue_turns or args.city_controls or args.map_controls
                or args.unit_work or args.unit_panel_cycle or args.terrain_work or args.growth_harvest
                or args.production_inputs or args.turn_action!='normal'):
            parser.error('--prepare-unit-attack is a separate bounded scenario preparation')
        from unit_attack_preparation import prepare
        result=prepare(config,args.prepare_unit_attack,total_seconds=args.preparation_seconds,
                       max_lifetimes=args.preparation_lifetimes)
        print(json.dumps(dict(status=result['status'],output=str(args.prepare_unit_attack/'result.json'),
                              seconds=result['seconds'],error=result.get('error'))))
        return 1 if result['status']=='refused' else 0
    if args.choice_group and not args.capability_cycle:
        parser.error('--choice-group requires the existing --capability-cycle')
    if args.world_input_group and (not args.capability_cycle or args.choice_group or args.turn_group):
        parser.error('--world-input-group requires --capability-cycle and excludes choice/turn groups')
    if args.unit_order_group and (not args.capability_cycle or args.choice_group or args.turn_group or args.world_input_group):
        parser.error('--unit-order-group requires --capability-cycle and excludes other capability groups')
    if args.turn_group and (not args.capability_cycle or args.choice_group):
        parser.error('--turn-group requires --capability-cycle and excludes --choice-group')
    if args.production_queue_group and (not args.capability_cycle or args.choice_group or args.turn_group or args.world_input_group or args.unit_order_group):
        parser.error('--production-queue-group requires --capability-cycle and excludes other capability groups')
    if args.placement_group and (not args.capability_cycle or args.choice_group or args.turn_group or args.world_input_group or args.unit_order_group or args.production_queue_group):
        parser.error('--placement-group requires --capability-cycle and excludes other capability groups')
    city_placement_checkpoint = bool(args.city_controls and args.placement_prepare_turns)
    if args.placement_prepare_turns:
        if (not 1<=args.placement_prepare_turns<=12 or config.get('checkpoint') is not None
                or config.get('input_profile')!='xp2-lan'):
            parser.error('--placement-prepare-turns requires an original XP2 capture and 1..12 turns')
        if city_placement_checkpoint:
            if (config.get('checkpoint_on_close') is not True
                    or config.get('city_focus_diagnostic') is not True
                    or config.get('city_management_diagnostic') is not True):
                parser.error('City placement preparation requires both city controls and checkpoint_on_close')
        elif (not args.placement_group or args.placement_category!='district'
              or config.get('checkpoint_on_close')):
            parser.error('Placement preparation requires a district --placement-group without checkpoint_on_close')
    if args.repeat_forced_turn and not args.turn_group:
        parser.error('--repeat-forced-turn requires --turn-group')
    if args.unit_attack_group and (not args.capability_cycle or args.choice_group or args.turn_group
            or args.world_input_group or args.unit_order_group or args.production_queue_group or args.placement_group):
        parser.error('--unit-attack-group requires --capability-cycle and excludes other capability groups')
    if args.placement_inventory_cycle and (args.capability_cycle or args.checkpoint_cycle
            or args.replacement_reset or args.dialogue_turns or args.city_controls or args.map_controls
            or args.unit_work or args.unit_panel_cycle or args.terrain_work or args.growth_harvest
            or args.production_inputs or args.turn_action!='normal'):
        parser.error('--placement-inventory-cycle is a separate bounded acceptance group')
    if args.capability_cycle and (args.growth_harvest or args.terrain_work or args.production_inputs
            or args.unit_work or args.unit_panel_cycle or args.checkpoint_cycle or args.map_controls
            or args.city_controls or args.dialogue_turns or args.replacement_reset
            or args.turn_action != 'normal'):
        parser.error('--capability-cycle is a separate bounded acceptance group')
    if sum((args.growth_harvest,args.terrain_work,args.production_inputs))>1:
        parser.error('Select only one prepared-builder acceptance group')
    if (args.terrain_work or args.growth_harvest or args.production_inputs) and (args.unit_work or args.unit_panel_cycle or args.checkpoint_cycle or args.map_controls or args.city_controls or args.dialogue_turns or args.replacement_reset or args.turn_action!='normal'):
        parser.error('--terrain-work is a separate acceptance group')
    if args.consume_builder and not args.unit_work:
        parser.error('--consume-builder requires --unit-work')
    if not 0 <= args.dialogue_turns <= 16:
        parser.error('--dialogue-turns must be between 0 and 16')
    if args.city_controls and (args.dialogue_turns or args.turn_action != 'normal'):
        parser.error('--city-controls is a separate acceptance group')
    if args.map_controls and (args.city_controls or args.dialogue_turns or args.turn_action != 'normal'):
        parser.error('--map-controls is a separate acceptance group')
    if args.checkpoint_cycle and (args.map_controls or args.city_controls or args.dialogue_turns or args.replacement_reset or args.turn_action != 'normal'):
        parser.error('--checkpoint-cycle is a separate acceptance group')
    if args.unit_work and (args.checkpoint_cycle or args.map_controls or args.city_controls or args.dialogue_turns or args.replacement_reset or args.turn_action != 'normal'):
        parser.error('--unit-work is a separate acceptance group')
    if args.unit_panel_cycle and (args.unit_work or args.checkpoint_cycle or args.map_controls or args.city_controls or args.dialogue_turns or args.replacement_reset or args.turn_action != 'normal'):
        parser.error('--unit-panel-cycle is a separate acceptance group')
    if args.checkpoint_cycle or args.placement_inventory_cycle:
        config['checkpoint_on_close'] = True
    if args.stdout_limit_mib is not None:
        config['stdout_limit_mib'] = args.stdout_limit_mib
    if args.dialogue_turns:
        config['round_limit'] = args.dialogue_turns + 1
    if args.map_controls:
        config['round_limit'] = 14
    if args.unit_work:
        config['round_limit'] = 24
        if args.consume_builder:
            config['checkpoint_on_close'] = True
    if args.terrain_work or args.growth_harvest or args.production_inputs:
        config['round_limit']=24
    if args.placement_prepare_turns:config['round_limit']=args.placement_prepare_turns+1
    if args.city_specialist_turns:config['round_limit']=args.city_specialist_turns+1
    from civ6_host import SessionClient
    from civ6_host.runtime.backend import NetworkBackend
    backend = NetworkBackend(**config)
    client = (SessionClient(backend,allow_administrative=True)
              if config.get('administrative_information') is True else SessionClient(backend))
    started = time.perf_counter()
    record = dict(status='running', native_exercise='LAN explicit turn cycle',
        started_at=datetime.now(timezone.utc).isoformat(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        commands=[], replays=[], supervised_runs=[], training=False)
    record['turn_action'] = args.turn_action
    record['dialogue_turns'] = args.dialogue_turns
    record['stdout_limit_mib'] = config.get('stdout_limit_mib', 64)
    try:
        if args.city_specialist_turns:
            from civ6_host.contracts.network_turn import CAPABILITY_CITY_CONTROLS_SCHEMA
            from civ6_host.runtime.network_checkpoint import _read as read_checkpoint
            seed=read_checkpoint(backend._session.network_checkpoint_ref)
            if seed['decisions']['schema']!=CAPABILITY_CITY_CONTROLS_SCHEMA:
                raise ValueError('Specialist preparation requires a producing v12 checkpoint')
            record['input_checkpoint']=copy.deepcopy(config['checkpoint'])
        view = client.reset()
        pid, initial_turn = view['observation']['player_id'], view['observation']['turn']
        initial_episode = view['episode_id']

        def save_view(view):
            path = backend.run / ('public-%04d.json' % view['sequence'])
            path.write_text(json.dumps(view), encoding='utf-8')
            record['replays'].append(str(path))

        def choose(kind, *, _expected_status='completed', **match):
            nonlocal view
            offers = [r for r in view['decisions']['candidates']
                      if r['action']['kind'] == kind and all(
                          r['action'].get(k) == v for k,v in match.items())]
            if not offers:
                raise ValueError('Required acceptance action unavailable: ' + kind)
            # This ordering is an explicit test choice, not a host policy.
            row = min(offers, key=lambda r:r['candidate_id'])
            view = client.act(pid, view['decisions']['decision_id'], row['candidate_id'])
            record['commands'].append(client.command_result)
            save_view(view)
            expected=(_expected_status,) if type(_expected_status) is str else _expected_status
            if client.command_result['status'] not in expected:
                raise RuntimeError('Acceptance command did not complete: ' + kind)
            return copy.deepcopy(client.command_result)

        def answer_dialogues():
            answers = 0
            for _ in range(8):
                rows = [r['action'] for r in view['decisions']['candidates']
                        if r['action']['kind'] == 'diplomacy_response']
                if not rows:
                    return answers
                # Explicit harness choice, never a response selected by the host.
                choice = next((a['choice'] for a in rows if a['choice']=='CHOICE_POSITIVE'),
                              rows[0]['choice'])
                choose('diplomacy_response', choice=choice)
                answers += 1
            raise RuntimeError('Acceptance dialogue exceeded eight explicit responses')

        def search_dialogue():
            nonlocal view
            record['native_exercise'] = 'LAN public exploration and explicit native dialogue'
            record['dialogue_answers'] = 0
            record['initial_session_requests'] = 0
            visits = {}
            record['exploration_selector'] = 'public_revealed_frontier_v2'
            record['public_exploration'] = []

            def try_initial_session():
                if record['initial_session_requests']:
                    return
                initial = [r['action'] for r in view['decisions']['candidates']
                           if r['action']['kind'] == 'diplomacy_initiate']
                if initial:
                    # Test only a currently offered official request. Prefer a
                    # delegation/friendship before unrelated hostile choices.
                    priority = {'CHOICE_DIPLOMATIC_DELEGATION':0,
                                'CHOICE_DECLARE_FRIENDSHIP':1}
                    action=min(initial,key=lambda a:(priority.get(a['choice'],2),
                               a['target_player_id'],a['choice']))
                    choose('diplomacy_initiate',target_player_id=action['target_player_id'],
                           choice=action['choice'])
                    record['initial_session_requests'] += 1

            for _ in range(args.dialogue_turns):
                record['dialogue_answers'] += answer_dialogues()
                if not record['dialogue_answers']:
                    try_initial_session()
                    record['dialogue_answers'] += answer_dialogues()
                if record['dialogue_answers']:
                    return
                origin = view['observation']['turn']
                for _ in range(8):
                    action = public_exploration_choice(view, visits)
                    if action is None:
                        break
                    record['public_exploration'].append(dict(
                        sequence=view['sequence'], turn=view['observation']['turn'],
                        revealed_plots=len(view['decisions']['player_map']['plots']),
                        action=action))
                    choose('move', unit_id=action['unit_id'],
                           destination_plot_id=action['destination_plot_id'])
                    for plot in (action['source_plot_id'], action['destination_plot_id']):
                        key = (action['unit_id'], plot)
                        visits[key] = visits.get(key, 0) + 1
                    record['dialogue_answers'] += answer_dialogues()
                    if not record['dialogue_answers']:
                        try_initial_session()
                        record['dialogue_answers'] += answer_dialogues()
                    if record['dialogue_answers']:
                        return
                choose('force_end_turn')
                record['dialogue_answers'] += answer_dialogues()
                for _ in range(64):
                    controls = view['decisions']['turn_controls']
                    if (view['observation']['turn'] > origin and controls['active']
                            and controls['active_complete']):
                        break
                    view = client.poll(pid)
                    save_view(view)
                    record['dialogue_answers'] += answer_dialogues()
                else:
                    raise RuntimeError('Dialogue acceptance native turn did not advance')
                if record['dialogue_answers']:
                    return
            return False

        save_view(view)
        if args.unit_panel_cycle:
            record['native_exercise']='LAN UnitPanel native event processing guard cycle'
            choose('force_end_turn')
            for _ in range(64):
                controls=view['decisions']['turn_controls']
                if view['observation']['turn']>initial_turn and controls['active'] and controls['active_complete']:
                    break
                view=client.poll(pid);save_view(view)
            else:
                raise RuntimeError('UnitPanel cycle did not reach the next active boundary')
            client.close(pid)
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            transitions=[]
            for _,_,event in session_records(backend.run):
                    if event.get('stage')=='native_unit_panel_gate_event' and event['player_id']==pid:
                        transitions.append(event)
            if (not any(e['processing_allowed'] is False for e in transitions)
                    or not transitions or transitions[-1]['processing_allowed'] is not True):
                raise RuntimeError('Local UnitPanel gate did not close and reopen from native events')
            record['unit_panel_transitions']=transitions
            record['final_turn']=view['observation']['turn']
            record['status']='native_lan_unit_panel_event_cycle_verified'
            return 0
        if args.unit_work or args.terrain_work or args.growth_harvest or args.production_inputs:
            def reopen_prepared_builder():
                nonlocal backend,client,view
                from civ6_host.runtime.native.native_session_resume import semantic_decisions
                before=view
                client.close(pid)
                record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
                reference=backend.checkpoint
                if reference is None:
                    raise RuntimeError('Prepared builder checkpoint was not saved')
                backend=NetworkBackend(**dict(config,checkpoint=reference,checkpoint_on_close=False))
                client=SessionClient(backend)
                view=client.reset();save_view(view)
                if (view['episode_id']==before['episode_id'] or view['observation']!=before['observation']
                        or semantic_decisions(view['decisions'])!=semantic_decisions(before['decisions'])):
                    raise RuntimeError('Prepared builder reload changed public state, selection or choices')
                return reference
            def advance_for_work():
                nonlocal view
                origin = view['observation']['turn']
                choose('force_end_turn')
                for _ in range(64):
                    controls = view['decisions']['turn_controls']
                    if (view['observation']['turn'] > origin and controls['active']
                            and controls['active_complete']):
                        return
                    view = client.poll(pid)
                    save_view(view)
                raise RuntimeError('Builder exercise did not reach the next active turn')
            record['native_exercise'] = 'LAN public own-unit state and native builder operation diagnostic'
            if args.production_inputs:
                record['native_exercise']='LAN public production stock, native completion and following queue item'
                record['production_inputs']=exercise_production_inputs(lambda:view,choose,advance_for_work)
                client.close(pid)
                record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
                record['final_turn']=view['observation']['turn']
                record['status']='native_lan_public_production_completion_and_queue_verified'
                return 0
            if args.terrain_work or args.growth_harvest:
                record['native_exercise']='LAN native harvest/feature removal and public work information'
                record['terrain_work']=exercise_terrain_work(lambda:view,choose,advance_for_work,growth_only=args.growth_harvest)
                client.close(pid)
                record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
                record['status']='native_lan_harvest_clear_information_verified_repairs_pending'
                if args.growth_harvest:
                    effect=record['terrain_work']['effects'][0]
                    readbacks={}
                    for _,_,event in session_records(backend.run):
                            if event.get('stage')=='native_city_growth_administrative_readback':
                                if (event['episode_id']!=view['episode_id'] or event['game_generation']!=view['game_generation']
                                        or event['player_id']!=pid or event['actor_channel'] is not False):
                                    raise RuntimeError('Growth administrative readback identity differs')
                                readbacks[event['sequence']]=event
                    before=readbacks[effect['before_sequence']];after=readbacks[effect['after_sequence']]
                    cid=effect['growth_before']['cities'][0]['city_id']
                    b=next(c for c in before['cities'] if c['city_id']==cid)
                    a=next(c for c in after['cities'] if c['city_id']==cid)
                    if before['turn']!=after['turn'] or a['growth_threshold']!=b['growth_threshold'] or a['food_stock']-b['food_stock']!=10:
                        raise RuntimeError('Prepared witness did not credit the native-announced 10 food without a turn change')
                    record['growth_credit']=dict(before=before,after=after,food_stock_delta=10,actor_received_raw_stock=False)
                    record['native_exercise']='LAN public city-growth display and native harvest food-stock credit'
                    record['status']='native_lan_city_growth_and_harvest_credit_verified'
                record['final_turn']=view['observation']['turn']
                return 0
            if not view['observation']['cities']:
                choose('found_city')
            record['unit_work'] = exercise_unit_work(lambda:view,choose,advance_for_work,consume_all=args.consume_builder,
                reopen=reopen_prepared_builder if args.consume_builder else None)
            client.close(pid)
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            record['status']='native_lan_unit_work_inputs_effects_verified_ui_parity_pending'
            record['final_turn']=view['observation']['turn']
            return 0
        if args.placement_inventory_cycle:
            from civ6_host.contracts.network_turn import CAPABILITY_PLACEMENT_INVENTORY_SCHEMA, CAPABILITY_UNIT_ATTACKS_SCHEMA, CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA
            if view['decisions']['schema'] not in (CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA):
                raise ValueError('Placement inventory requires the versioned native inventory catalogue')
            initial=copy.deepcopy(view);save_view(initial)
            prep=exercise_placement_group(lambda:view,choose,category=args.placement_category,defer_resume=True)
            action=prep['steps'][0]['action']
            def inventory_row(current):
                inv=current['decisions']['placement_inventory']
                matches=[r for r in inv['rows'] if r['city_id']==action['city_id']
                         and r['category']==action['category'] and r['plot_id']==action['plot_id']]
                if len(matches)!=1:raise RuntimeError('Native inventory lacks the single selected placement')
                result=matches[0]
                if result['complete'] or any(result[k]!=action[k] for k in ('index','hash','item_type','x','y')):
                    raise RuntimeError('Native inventory differs from the newly placed unfinished item')
                return copy.deepcopy(result)
            saved_boundary=copy.deepcopy(view);native_row=inventory_row(view)
            save_view(client.close(pid))
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            original_run=str(backend.run);ref=backend.checkpoint
            if ref is None:raise RuntimeError('Placement preparation did not return its actual native Save')
            record['checkpoints']=[ref]
            backend=NetworkBackend(**dict(config,checkpoint=ref,checkpoint_on_close=False))
            client=SessionClient(backend);view=client.reset();save_view(view)
            compare_checkpoint_public(saved_boundary,view)
            if inventory_row(view)!=native_row:raise RuntimeError('Native Load changed placed-item inventory')
            resumed=copy.deepcopy(view);resumed_run=str(backend.run)
            resume=next((a for a in view['decisions']['placement_offers'] if a['kind']=='production_resume'
                         and all(a[k]==action[k] for k in ('city_id','category','index','hash','item_type'))),None)
            if resume is None:raise RuntimeError('Loaded native placement has no actual resume offer')
            choose('production_resume',**{k:v for k,v in resume.items() if k!='kind'})
            resume_sequence=view['sequence']
            if inventory_row(view)!=native_row:raise RuntimeError('Native resumption changed placed-item inventory')
            save_view(client.close(pid))
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            view=client.reset();save_view(view);compare_checkpoint_public(saved_boundary,view)
            if inventory_row(view)!=native_row:raise RuntimeError('Reset changed the saved native placement inventory')
            if (len({original_run,resumed_run,str(backend.run)})!=3
                    or len({initial['episode_id'],resumed['episode_id'],view['episode_id']})!=3):
                raise RuntimeError('Placement inventory cycle reused a process or episode')
            record['inventory_group']=dict(preparation=prep,checkpoint=ref,
                resumed_episode=resumed['episode_id'],reset_episode=view['episode_id'],
                resume_action=resume,resume_sequence=resume_sequence,turn=initial['observation']['turn'],
                native_row=native_row,poll_calls=0,native_tracking_empty_witness=False)
            save_view(client.close(pid))
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            record.update(status='native_placement_inventory_checkpoint_reset_verified',
                native_exercise='Native own placement inventory across Save/Load, explicit resumption and reset',
                scope='Witnessed unfinished placement; tracking is preserved but not an input to the native inventory reader')
            return 0
        if args.capability_cycle:
            from civ6_host.contracts.network_turn import is_capability_catalogue, CAPABILITY_CHOICES_SCHEMA, CAPABILITY_TURNS_SCHEMA, CAPABILITY_WORLD_SCHEMA, CAPABILITY_UNIT_ORDERS_SCHEMA, CAPABILITY_PRODUCTION_QUEUE_SCHEMA, CAPABILITY_PLACEMENT_SCHEMA, CAPABILITY_PLACEMENT_INVENTORY_SCHEMA, CAPABILITY_UNIT_ATTACKS_SCHEMA, CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA
            if not is_capability_catalogue(view['decisions']):
                raise ValueError('Capability acceptance requires the explicit partial-family schema')
            initial = copy.deepcopy(view)
            save_view(initial)
            if args.world_input_group:
                record['world_input_group']=exercise_world_input_group(lambda:view,choose)
            elif args.unit_order_group:
                record['unit_order_group']=exercise_unit_order_group(lambda:view,choose)
            elif args.production_queue_group:
                record['production_queue_group']=exercise_production_queue_group(lambda:view,choose)
            elif args.placement_group:
                if args.placement_prepare_turns:
                    from unit_attack_preparation import native_remaining
                    def poll_placement():
                        nonlocal view
                        view=client.poll(pid);save_view(view)
                    record['placement_preparation']={}
                    prepare_placement_boundary(lambda:view,choose,poll_placement,
                        max_turns=args.placement_prepare_turns,
                        remaining=lambda:min(native_remaining(backend),1200-(time.perf_counter()-started)-180),
                        identity=placement_preparation_identity(config),receipt=record['placement_preparation'])
                record['placement_group']=exercise_placement_group(lambda:view,choose,category=args.placement_category)
            elif args.unit_attack_group:
                from civ6_host.contracts.network_turn import CAPABILITY_UNIT_ATTACKS_SCHEMA, CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA
                if view['decisions']['schema'] not in (CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA):
                    raise ValueError('Unit attack group requires the native v9 catalogue')
                from unit_attack_preparation import select_offered_attack,combat_information_snapshot
                attack=select_offered_attack(view)
                if config.get('administrative_information') is True:
                    record['combat_information']=[combat_information_snapshot(client,view)]
                elif config.get('input_profile')=='xp2-lan':
                    raise ValueError('XP2 combat qualification requires explicit administrative_information')
                choose('unit_attack',**{k:v for k,v in attack.items() if k!='kind'})
                record['unit_attack_group']=dict(action=attack,poll_calls=0)
                if config.get('administrative_information') is True:
                    record['combat_information'].append(combat_information_snapshot(client,view))
            else:
                choose('found_city')
            if not (args.world_input_group or args.unit_order_group or args.production_queue_group or args.placement_group or args.unit_attack_group) and (len(view['observation']['cities']) != len(initial['observation']['cities'])+1
                    or len(view['observation']['units']) != len(initial['observation']['units'])-1):
                raise RuntimeError('Native selected foundation did not update the public entities')
            if args.choice_group:
                if view['decisions']['schema'] not in (CAPABILITY_CHOICES_SCHEMA,CAPABILITY_TURNS_SCHEMA,CAPABILITY_WORLD_SCHEMA,CAPABILITY_UNIT_ORDERS_SCHEMA,CAPABILITY_PRODUCTION_QUEUE_SCHEMA,CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA):
                    raise ValueError('Choice group requires the versioned public choice state')
                changes = []
                for kind in ('research', 'civic', 'research'):
                    prior = view['decisions']['choice_state']['research'][kind]
                    offers = [r['action'] for r in view['decisions']['candidates']
                              if r['action']['kind'] == kind and r['action']['index'] != prior]
                    if not offers and kind == 'civic':
                        # The official initial capture already selects Code of
                        # Laws and offers no different civic. Submit that actual
                        # offered choice; do not fabricate a replacement witness.
                        offers = [r['action'] for r in view['decisions']['candidates']
                                  if r['action']['kind'] == kind]
                    if not offers:
                        raise RuntimeError('No different native choice for replacement exercise: '+kind)
                    action = min(offers, key=lambda a:a['index'])
                    choose(kind,index=action['index'],hash=action['hash'])
                    current = view['decisions']['choice_state']['research'][kind]
                    if current != action['index']:
                        raise RuntimeError('Public native research readback differs from explicit choice')
                    changes.append(dict(kind=kind,before=prior,after=current,
                                        selection_changed=prior!=current))
                cid = view['observation']['cities'][0]['id']
                for category in ('unit', 'building', 'unit'):
                    offers = [r['action'] for r in view['decisions']['candidates']
                              if r['action']['kind'] == 'production'
                              and r['action']['city_id'] == cid and r['action']['category'] == category]
                    if not offers:
                        raise RuntimeError('No native production replacement for '+category)
                    action = min(offers,key=lambda a:a['index'])
                    before = copy.deepcopy(view['decisions']['choice_state']['production'])
                    choose('production',city_id=cid,category=category,index=action['index'])
                    current = next(r for r in view['decisions']['choice_state']['production'] if r['city_id']==cid)
                    if current['hash'] != action['hash'] or current['item_index'] != action['index']:
                        raise RuntimeError('Public production choice differs from the requested item')
                    changes.append(dict(kind='production',action=action,before=before,after=copy.deepcopy(current)))
                if view['observation']['turn'] != initial['observation']['turn']:
                    raise RuntimeError('Explicit same-turn choice group unexpectedly advanced the turn')
                record['choice_group'] = changes
            if args.turn_group:
                if view['decisions']['schema'] not in (CAPABILITY_TURNS_SCHEMA,CAPABILITY_WORLD_SCHEMA,CAPABILITY_UNIT_ORDERS_SCHEMA,CAPABILITY_PRODUCTION_QUEUE_SCHEMA,CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA):
                    raise ValueError('Turn group requires native turn availability')
                # Explicit test-client choices prepare the real city. The host
                # offers the complete qualified families and makes no choices.
                for kind in ('research','civic','production'):
                    offers=[r['action'] for r in view['decisions']['candidates'] if r['action']['kind']==kind]
                    if not offers:raise RuntimeError('No preparation choice offered for '+kind)
                    chosen=min(offers,key=lambda a:(a.get('category',''),a['index']))
                    choose(kind,**{k:v for k,v in chosen.items() if k!='kind'})
                start_turn=view['observation']['turn']
                availability=copy.deepcopy(view['decisions']['turn_availability'])
                initial_request='end_turn' if availability['end_turn'] is True else 'force_end_turn'
                choose(initial_request)
                ready=copy.deepcopy(view['decisions']['turn_controls'])
                unready=None
                if view['decisions']['turn_availability']['unready_turn'] is True:
                    choose('unready_turn')
                    unready=copy.deepcopy(view['decisions']['turn_controls'])
                    if unready['can_unready']:
                        raise RuntimeError('Explicit native Unready did not clear readiness')
                    choose('force_end_turn')
                repeated=None
                if args.repeat_forced_turn:
                    prior=copy.deepcopy(view['decisions']['turn_controls'])
                    if prior['active'] is not False:
                        raise RuntimeError('Repeated-force acceptance requires an actually inactive human')
                    choose('force_end_turn',_expected_status='submitted')
                    after=copy.deepcopy(view['decisions']['turn_controls'])
                    if (after!=prior or view['applied_action'] is not None
                            or client.command_result['reason']!='native_turn_controls_unchanged'):
                        raise RuntimeError('Repeated force must distinguish submitted request from confirmed effect')
                    repeated=dict(sequence=view['sequence'],before=prior,after=after,
                                  command_result=copy.deepcopy(client.command_result))
                polls=0
                def next_active_turn():
                    controls=view['decisions']['turn_controls']
                    return (view['observation']['turn']==start_turn+1 and controls['active']
                            and controls['active_complete'] and not controls['can_unready'])
                while not next_active_turn() and polls<32:
                    view=client.poll(pid);save_view(view);polls+=1
                if not next_active_turn():
                    raise RuntimeError('Bounded native turn group did not reach the next turn')
                record['turn_group']=dict(initial_turn=start_turn,final_turn=view['observation']['turn'],
                    initial_availability=availability,initial_request=initial_request,
                    ready=ready,unready=unready,unready_executed=unready is not None,poll_calls=polls,
                    final_controls=copy.deepcopy(view['decisions']['turn_controls']))
                if repeated is not None:record['turn_group']['repeated_forced_request']=repeated
            save_view(client.close(pid))
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            first_run = str(backend.run)
            if args.placement_prepare_turns and time.perf_counter()-started>1200-180:
                raise RuntimeError('Placement group exhausted its reserved fresh-reset time')
            fresh = client.reset()
            save_view(fresh)
            if (fresh['episode_id'] == initial['episode_id'] or str(backend.run) == first_run
                    or fresh['game_generation'] == initial['game_generation']
                    or fresh['observation'] != initial['observation']
                    or fresh['decisions']['families'] != initial['decisions']['families']
                    or fresh['decisions']['candidates'] != initial['decisions']['candidates']
                    or fresh['decisions'].get('choice_state') != initial['decisions'].get('choice_state')):
                raise RuntimeError('Fresh native process did not restore the same saved player boundary')
            record['replacement_episode'] = fresh['episode_id']
            if args.unit_attack_group and config.get('administrative_information') is True:
                record['combat_information'].append(combat_information_snapshot(client,fresh))
            save_view(client.close(pid))
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            if any(not row['report']['reaped'] or row['report']['exit_code'] != 90
                   or row['report']['error'] is not None
                   or not all(row['report']['source_unchanged'].values())
                   for row in record['supervised_runs']):
                raise RuntimeError('Native session cycle did not retain clean supervised lifetimes')
            record['native_exercise'] = 'Native public capability query, explicit foundation, close and new-process reset'
            record['status'] = 'native_capability_foundation_reset_verified'
            record['scope'] = 'Exact captured engine/save and one named action family; no turn/result transition or complete gameplay admission'
            if args.choice_group:
                record['native_exercise'] = 'Native public foundation/research/civic/current-production choices and replacements, close, fresh reset'
                record['status'] = 'native_capability_choice_group_reset_verified'
                record['scope'] = 'Exact captured engine/save; explicit choices and replacements only, partial production catalogue; turn progression and complete gameplay remain unqualified'
            if args.turn_group:
                if fresh['decisions']['turn_availability']!=initial['decisions']['turn_availability']:
                    raise RuntimeError('Reset native turn availability differs from the initial save')
                record['native_exercise']='Native choice preparation, readiness/unready, explicit updates to next turn, close and reset'
                record['status']='native_capability_turn_group_reset_verified'
                record['scope']='Exact captured engine/save and one turn interval; full game, all actions and long continuations remain unqualified'
            if args.world_input_group:
                if any(fresh['decisions'][k]!=initial['decisions'][k]
                       for k in ('world_input','queued_orders','turn_availability')):
                    raise RuntimeError('Reset did not restore the exact public world-input boundary')
                record['native_exercise']='Native own-unit selection, public world clicks, deselection, close and fresh reset'
                record['status']='native_capability_world_input_group_reset_verified'
                record['scope']='Exact captured engine/save and observed MOVE_TO inputs; other operations, complete movement/entry effects and full gameplay remain unqualified'
            if args.unit_order_group:
                if any(fresh['decisions'][k]!=initial['decisions'][k]
                       for k in ('unit_orders','world_input','queued_orders','turn_availability')):
                    raise RuntimeError('Reset did not restore exact native unit orders and public world state')
                record['native_exercise']='Native rest/wake, observed queued MOVE_TO and explicit CANCEL, close and fresh reset'
                record['status']=('native_capability_unit_order_group_reset_verified' if record['unit_order_group']['complete']
                                  else 'native_capability_unit_order_group_incomplete')
                record['scope']='Only delivered native orders on this captured engine/save; cancellation requires nonempty-to-empty queue; no healing-over-turns or complete gameplay claim'
            if args.production_queue_group:
                if any(fresh['decisions'][k]!=initial['decisions'][k]
                       for k in ('production_queues','unit_orders','world_input','queued_orders','turn_availability')):
                    raise RuntimeError('Reset did not restore exact native production queues and public state')
                record['native_exercise']='Native offered queue append, observable swap, eighth-slot replacement and removal, close and reset'
                record['status']='native_capability_production_queue_group_reset_verified'
                record['scope']='Exact captured engine/save and offered queue edits; placement-required items and nonstandard formations remain unqualified'
            if args.placement_group:
                if any(fresh['decisions'][k]!=initial['decisions'][k] for k in
                        ('placements','placement_offers','placement_observation_scope','production_queues',
                         'unit_orders','world_input','queued_orders','turn_availability')):
                    raise RuntimeError('Reset did not restore exact native placement and public state')
                record['native_exercise']='Native explicit placement, ordinary replacement, same-item resumption, close and reset'
                record['status']='native_capability_placement_group_reset_verified'
                record['scope']='Only the actually exercised category on this prepared captured engine/save; no completion, other-category or full placement inventory claim'
                if args.placement_prepare_turns and time.perf_counter()-started>1200:
                    raise RuntimeError('Placement group exceeded its total 1200-second budget')
            if args.unit_attack_group:
                if fresh['decisions']['unit_attacks']!=initial['decisions']['unit_attacks']:
                    raise RuntimeError('Reset changed the prepared native attack state or offers')
                record.update(native_exercise='Native offered unit attack, actual readback, clean close and fresh reset',
                    status='native_capability_unit_attack_group_reset_verified',
                    scope='Only the offered operation and its observed native effects; other targets/routes remain unqualified')
            return 0
        if args.checkpoint_cycle and config.get('input_profile')=='xp1-lan':
            initial=copy.deepcopy(view);save_view(initial)
            rest=checkpoint_rest_action(view);uid=rest['unit_id']
            initial_unit=copy.deepcopy(next(u for u in view['decisions']['unit_orders']['units'] if u['unit_id']==uid))
            choose('unit_order',**{k:v for k,v in rest.items() if k!='kind'})
            rested=next(u for u in view['decisions']['unit_orders']['units'] if u['unit_id']==uid)
            if rested==initial_unit:raise RuntimeError('Checkpoint preparation lacks a changed native unit state')
            rest_sequence=view['sequence']
            choose('world_select_unit',unit_id=uid)
            saved_boundary=copy.deepcopy(view)
            if saved_boundary['decisions']['world_input']['selected_unit_id']!=uid:
                raise RuntimeError('Checkpoint preparation lost explicit selection')
            save_view(client.close(pid))
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            original_run=str(backend.run);ref=backend.checkpoint
            if ref is None:raise RuntimeError('XP1 native checkpoint was not returned after supervised close')
            record['checkpoints']=[ref]
            backend=NetworkBackend(**dict(config,checkpoint=ref,checkpoint_on_close=False))
            client=SessionClient(backend);view=client.reset();save_view(view)
            compare_checkpoint_public(saved_boundary,view)
            resumed=copy.deepcopy(view);resumed_run=str(backend.run)
            if resumed_run==original_run:raise RuntimeError('Checkpoint resume reused its producing process')
            releases=[r['action'] for r in view['decisions']['candidates'] if r['action']['kind']=='unit_order'
                      and r['action']['unit_id']==uid and r['action']['item_type'] in ('UNITCOMMAND_WAKE','UNITCOMMAND_CANCEL')]
            if not releases:raise RuntimeError('Reloaded rest state has no native offered release')
            release=min(releases,key=lambda a:a['item_type']!='UNITCOMMAND_WAKE')
            choose('unit_order',**{k:v for k,v in release.items() if k!='kind'})
            released=next(u for u in view['decisions']['unit_orders']['units'] if u['unit_id']==uid)
            if released['activity_type']!=initial_unit['activity_type'] or released==rested:
                raise RuntimeError('Native command after checkpoint resume did not restore initial activity')
            release_sequence=view['sequence'];choose('world_deselect_unit')
            if view['decisions']['world_input']['selected_unit_id'] is not None:
                raise RuntimeError('Resumed explicit deselection was not applied')
            deselection_sequence=view['sequence'];save_view(client.close(pid))
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            view=client.reset();save_view(view);compare_checkpoint_public(saved_boundary,view)
            if str(backend.run) in (original_run,resumed_run) or view['episode_id']==resumed['episode_id']:
                raise RuntimeError('Checkpoint reset did not create another independent process/episode')
            reset_episode=view['episode_id'];save_view(client.close(pid))
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            if any(r['report']['exit_code']!=90 or r['report']['reaped'] is not True
                   or r['report']['normal_destroy_called'] is not True or r['report']['error'] is not None
                   or not all(r['report']['source_unchanged'].values()) for r in record['supervised_runs']):
                raise RuntimeError('XP1 checkpoint group lacks three clean native lifetimes')
            record['checkpoint_cycle']=dict(unit_id=uid,rest_action=rest,rest_sequence=rest_sequence,
                selection_sequence=saved_boundary['sequence'],release_action=release,release_sequence=release_sequence,
                deselection_sequence=deselection_sequence,checkpoint=ref,save_count=1,poll_calls=0,
                resumed_episode=resumed['episode_id'],reset_episode=reset_episode,
                turn=initial['observation']['turn'],complete_hidden_state_compared=False)
            record['native_exercise']='XP1 native checkpoint, public-state resume, explicit command and fresh checkpoint reset'
            record['status']='native_xp1_checkpoint_cycle_verified'
            record['scope']='Exact XP1 capture and one component-pair Save/Load; qualified public states only, no complete hidden-state or content compatibility claim'
            return 0
        if args.city_specialist_turns:
            from unit_attack_preparation import native_remaining

            def poll_city_specialist():
                nonlocal view
                view=client.poll(pid)
                save_view(view)

            record['native_exercise']='Native Holy Site and Shrine checkpoint continuation'
            record['city_specialist_preparation']={}
            identity=placement_preparation_identity(config,shrine=True)
            result=continue_city_specialist(lambda:view,choose,poll_city_specialist,
                max_turns=args.city_specialist_turns,remaining=lambda:native_remaining(backend),
                identity=identity,receipt=record['city_specialist_preparation'],
                building_readback=city_specialist_readbacks(backend.run,identity))
            save_view(client.close(pid))
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            if backend.checkpoint is None:
                raise RuntimeError('Native specialist preparation did not return a Save checkpoint')
            record.update(status=('native_xp2_city_specialist_click_checkpoint_observed'
                                  if result['specialist_qualified']
                                  else 'native_xp2_city_specialist_preparation_checkpoint_observed'),
                          checkpoint=backend.checkpoint)
            return 0
        if city_placement_checkpoint:
            from unit_attack_preparation import native_remaining
            from civ6_host.contracts.network_turn import CAPABILITY_CITY_CONTROLS_SCHEMA
            if view['decisions']['schema'] != CAPABILITY_CITY_CONTROLS_SCHEMA:
                raise ValueError('City placement checkpoint requires the v12 catalogue')

            def poll_city_preparation():
                nonlocal view
                view=client.poll(pid)
                save_view(view)

            record['native_exercise']='Native city preparation and placed Holy Site checkpoint'
            identity=placement_preparation_identity(config)
            record['placement_preparation']={}
            prepare_placement_boundary(lambda:view,choose,poll_city_preparation,
                max_turns=args.placement_prepare_turns,remaining=lambda:native_remaining(backend),
                identity=identity,receipt=record['placement_preparation'],
                target_type=identity['target_type'],total_group_seconds=config['lifetime_seconds'],
                reset_reserve_seconds=0)
            offers=[a for a in view['decisions']['placement_offers']
                    if a['kind']=='production_placement' and a['item_type']==identity['target_type']]
            action=min(offers,key=lambda a:(a['city_id'],a['plot_id']))
            if native_remaining(backend)<60:
                raise RuntimeError('City placement reached the reserved Save time')
            choose(action['kind'],**{k:v for k,v in action.items() if k!='kind'})
            inventory=view['decisions']['placement_inventory']
            if not any(row['city_id']==action['city_id'] and row['plot_id']==action['plot_id']
                       and row['item_type']==action['item_type'] and row['complete'] is False
                       for row in inventory['rows']):
                raise RuntimeError('Native inventory does not confirm the unfinished Holy Site')
            save_view(client.close(pid))
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            if backend.checkpoint is None:
                raise RuntimeError('Native Save did not return a checkpoint')
            record.update(status='native_xp2_city_placement_checkpoint_observed',
                          placement_action=action,checkpoint=backend.checkpoint,
                          final_turn=view['observation']['turn'])
            return 0
        choose('found_city')
        if args.checkpoint_cycle:
            from civ6_host.runtime.native.native_session_resume import semantic_decisions
            record['native_exercise']='LAN native checkpoint close/reopen and chained continuation'
            xp2_checkpoint=config.get('input_profile')=='xp2-lan'
            if xp2_checkpoint:record['poll_calls']=0
            choose('force_end_turn')
            for _ in range(64):
                controls=view['decisions']['turn_controls']
                if view['observation']['turn']>initial_turn and controls['active'] and controls['active_complete']:
                    break
                view=client.poll(pid);save_view(view)
                if xp2_checkpoint:record['poll_calls']+=1
            else:
                raise RuntimeError('Checkpoint exercise did not reach the next active turn')
            choose('world_select_unit')
            record['checkpoints']=[]
            saved_sequences=[];resumed_episodes=[];post_resume_actions=[]
            selected_unit_id=view['decisions']['world_input']['selected_unit_id']
            for index in range(2):
                before=view
                saved_sequences.append(before['sequence'])
                client.close(pid)
                record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
                ref=backend.checkpoint
                if ref is None:
                    raise RuntimeError('Native checkpoint receipt missing after close')
                record['checkpoints'].append(ref)
                backend=NetworkBackend(**dict(config,checkpoint=ref,checkpoint_on_close=index==0))
                client=SessionClient(backend)
                view=client.reset();save_view(view)
                if xp2_checkpoint:
                    compare_checkpoint_public(before,view)
                elif (view['episode_id']==before['episode_id']
                        or view['observation']!=before['observation']
                        or semantic_decisions(view['decisions'])!=semantic_decisions(before['decisions'])):
                    raise RuntimeError('LAN checkpoint roundtrip changed the public boundary')
                resumed_episodes.append(view['episode_id'])
                post_resume_actions.append(choose('world_deselect_unit' if index==0 else 'civic')['requested_action'])
            # Final close without producing an untested extra checkpoint.
            client.close(pid)
            record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
            record['status']='native_lan_checkpoint_cycle_verified'
            record['final_turn']=view['observation']['turn']
            if xp2_checkpoint:
                if (len(record['supervised_runs'])!=3
                        or len({r['run'] for r in record['supervised_runs']})!=3
                        or any(r['report']['exit_code']!=90 or r['report']['reaped'] is not True
                            or r['report']['normal_destroy_called'] is not True or r['report']['error'] is not None
                            or not all(r['report']['source_unchanged'].values()) for r in record['supervised_runs'])):
                    raise RuntimeError('XP2 checkpoint group lacks three clean independent native lifetimes')
                record['checkpoint_cycle']=dict(save_count=2,poll_calls=record['poll_calls'],
                    initial_turn=initial_turn,saved_turn=record['final_turn'],unit_id=selected_unit_id,
                    saved_sequences=saved_sequences,resumed_episodes=resumed_episodes,
                    post_resume_actions=post_resume_actions,final_command_sequence=view['sequence'],
                    complete_hidden_state_compared=False)
                record['status']='native_xp2_checkpoint_cycle_verified'
                record['native_exercise']='XP2 two native Saves, fresh matched public resumes, child ancestry and explicit post-resume commands'
                record['scope']='Exact XP2 capture and two derived component pairs across three clean lifetimes; qualified public states only'
            return 0
        if args.map_controls:
            def advance_for_purchase():
                nonlocal view
                origin = view['observation']['turn']
                choose('force_end_turn')
                for _ in range(64):
                    controls = view['decisions']['turn_controls']
                    if (view['observation']['turn'] > origin and controls['active']
                            and controls['active_complete']):
                        return
                    view = client.poll(pid)
                    save_view(view)
                raise RuntimeError('Purchase acceptance did not reach the next active turn')
            record['native_exercise'] = 'LAN source-admitted world clicks, cancel and plot purchase'
            record['map_controls'] = exercise_map_controls(lambda: view, choose, advance_for_purchase)
            client.close(pid)
            record['supervised_runs'].append(dict(run=str(backend.run), report=backend.report))
            record['status'] = 'native_lan_map_controls_verified'
            record['final_turn'] = view['observation']['turn']
            return 0
        if args.city_controls:
            from civ6_host.contracts.network_turn import CAPABILITY_CITY_CONTROLS_SCHEMA
            if view['decisions']['schema'] == CAPABILITY_CITY_CONTROLS_SCHEMA:
                record['native_exercise'] = 'Expansion native focus and citizen controls'
                record['city_controls'] = exercise_city_controls(
                    lambda: view, choose, include_queue=False)
                save_view(client.close(pid))
                record['supervised_runs'].append(dict(run=str(backend.run), report=backend.report))
                record['status'] = 'native_expansion_city_controls_observed'
                record['final_turn'] = view['observation']['turn']
                return 0
            record['native_exercise'] = 'LAN source-admitted city controls and production queue'
            record['city_controls'] = exercise_city_controls(lambda: view, choose)
            client.close(pid)
            record['supervised_runs'].append(dict(run=str(backend.run), report=backend.report))
            record['status'] = 'native_lan_city_controls_verified'
            record['final_turn'] = view['observation']['turn']
            return 0
        if args.dialogue_turns:
            choose('research')
            choose('civic')
            # This dialogue-specific test needs exploration, and the retained
            # native catalogue offers a scout. Require that actual offer rather
            # than falling back to another unit or changing any host masks.
            choose('production', item_type='UNIT_SCOUT')
            record['exploration_production'] = 'UNIT_SCOUT'
            search_dialogue()
            record['final_turn'] = view['observation']['turn']
            client.close(pid)
            record['supervised_runs'].append(dict(run=str(backend.run), report=backend.report))
            if record['dialogue_answers']:
                record['status'] = 'native_lan_dialogue_cycle_verified'
                return 0
            record['status'] = 'native_lan_dialogue_unwitnessed'
            record['reason'] = 'No real dialogue encountered within the bounded public route'
            return 2
        if args.turn_action == 'forced':
            offered = {row['action']['kind'] for row in view['decisions']['candidates']}
            if 'end_turn' in offered or 'force_end_turn' not in offered:
                raise RuntimeError('Forced acceptance must preserve unresolved normal blockers')
            record['unresolved_before_force'] = dict(blockers=view['decisions']['blockers'],
                ready_units=view['decisions']['ready_units'],
                production=view['decisions']['production'])
            choose('force_end_turn')
        else:
            choose('research')
            choose('civic')
            choose('production', item_type='UNIT_WARRIOR')
            for _ in range(8):
                if not any(r['action']['kind'] == 'skip_unit' for r in view['decisions']['candidates']):
                    break
                choose('skip_unit')
            choose('end_turn')
        record['after_end_turn_controls'] = view['decisions']['turn_controls']
        if any(r['action']['kind'] == 'unready_turn' for r in view['decisions']['candidates']):
            choose('unready_turn')
            record['unready_effect'] = view['decisions']['turn_controls']
            choose('end_turn')
        for updates in range(64):
            controls = view['decisions']['turn_controls']
            if (view['observation']['turn'] > initial_turn
                    and controls['active'] and controls['active_complete']):
                break
            view = client.poll(pid)
            save_view(view)
        else:
            raise RuntimeError('Bounded LAN update calls did not reach the next ready turn')
        record['poll_calls'] = updates
        record['final_turn'] = view['observation']['turn']
        client.close(pid)
        record['supervised_runs'].append(dict(run=str(backend.run), report=backend.report))
        if args.replacement_reset:
            fresh = client.reset()
            assert fresh['episode_id'] != initial_episode
            assert fresh['observation']['turn'] == initial_turn
            record['replacement_episode'] = fresh['episode_id']
            client.close()
            record['supervised_runs'].append(dict(run=str(backend.run), report=backend.report))
        record['status'] = 'native_lan_turn_cycle_verified'
    except BaseException as exc:
        record.update(status='refused', error=repr(exc), traceback=traceback.format_exc())
        if (args.placement_prepare_turns or args.city_specialist_turns) and not backend.finished:
            try:
                from unit_attack_preparation import native_remaining
                controls=view['decisions']['turn_controls']
                if controls['active'] and controls['active_complete'] and native_remaining(backend)>=30:
                    save_view(client.close(pid))
                    record['supervised_runs'].append(dict(run=str(backend.run),report=backend.report))
                    if (city_placement_checkpoint or args.city_specialist_turns) and backend.checkpoint is not None:
                        record['partial_checkpoint']=backend.checkpoint
            except BaseException as closing:
                record['close_error']=repr(closing)
    finally:
        client.abort()
        record['seconds'] = time.perf_counter() - started
        if backend.run:
            if not record['supervised_runs'] or record['supervised_runs'][-1]['run'] != str(backend.run):
                record['supervised_runs'].append(dict(run=str(backend.run), report=backend.report))
            path = backend.run / 'client-acceptance.json'
            path.write_text(json.dumps(record, indent=2), encoding='utf-8')
            print(json.dumps(dict(status=record['status'], error=record.get('error'),
                                  result=str(path), seconds=record['seconds'])))
        else:
            # Parent admission can fail before a native run directory exists.
            # Always expose that failure instead of returning a silent code 1.
            print(json.dumps(dict(status=record['status'], error=record.get('error'),
                                  result=None, native_run_created=False, seconds=record['seconds'])))
    return 0 if record['status'] != 'refused' else 1


if __name__ == '__main__':
    raise SystemExit(main())

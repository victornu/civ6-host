"""Prepare a real contact through public client choices, never by editing state."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time


def select_offered_attack(view):
    """Select one exact public offer; administrative information is not an input."""
    from civ6_host.contracts.capability_unit_attacks import validate_action
    state=view['decisions'].get('unit_attacks')
    if type(state) is not dict or not state.get('offers'):
        raise RuntimeError('Prepared boundary has no actual native unit attack offer')
    offers=state['offers'];candidates=view['decisions']['candidates'];obs=view['observation']
    for action in offers:
        validate_action(action,obs['width'],obs['height'])
        if sum(row['action']==action for row in candidates)!=1:
            raise ValueError('Attack offer lacks its unique current public candidate')
    return deepcopy(min(offers,key=lambda a:(a['operation']!='RANGE_ATTACK',a['unit_id'],a['plot_id'],a['input_route'])))


def combat_information_snapshot(client,view):
    """Read both explicitly opted-in channels at the existing cached boundary."""
    public=client.information('combat');admin=client.information('combat',channel='administrative')
    identity=('episode_id','game_generation','player_id','sequence','turn','native_decision_id','source_contracts')
    expected=dict(episode_id=view['episode_id'],game_generation=view['game_generation'],
        player_id=view['observation']['player_id'],sequence=view['sequence'],turn=view['observation']['turn'],
        native_decision_id=view['decisions']['decision_id'])
    if (any(public[k]!=admin[k] for k in identity)
            or any(public[k]!=value for k,value in expected.items())):
        raise ValueError('Combat information query crossed the actual public boundary')
    return dict(public=deepcopy(public),administrative=deepcopy(admin))


def select_exploration(view,visited):
    """A test policy, not a host action mask or a prediction of move legality."""
    d=view['decisions'];obs=view['observation'];state=d['unit_attacks']
    if state is None:return None
    offers=[r['action'] for r in d['candidates']]
    # Orders can depend on the current selection. Requiring a FORTIFY offer
    # here prevented selecting the other mobile units. This test policy may
    # explore with any own mobile unit; it never changes the host's choices.
    units=[u for u in state['units'] if u['moves']>0]
    own_cities={(c['x'],c['y']) for c in obs['cities']}
    plots=[p for p in obs['plots'] if p['visible'] and not p['water'] and not p['impassable']
           and (p['x'],p['y']) not in own_cities]
    clicks={(a['x'],a['y']):a for a in offers if a['kind']=='world_plot_click'}
    selectable={a['unit_id'] for a in offers if a['kind']=='world_select_unit'}
    selected=d['world_input']['selected_unit_id']
    choices=[]
    for u in units:
        for p in plots:
            key=(u['unit_id'],p['index'])
            if (p['x'],p['y'])==(u['x'],u['y']) or key in visited:continue
            # Grid distance orders exploration only; Core decides whether the
            # clicked plot can be reached and which operation it represents.
            distance=max(abs(u['x']-p['x']),abs(u['y']-p['y']))
            if distance>2:continue
            if selected==u['unit_id']:
                if (p['x'],p['y']) not in clicks:continue
            elif u['unit_id'] not in selectable:continue
            outward=min((abs(p['x']-x)+abs(p['y']-y) for x,y in own_cities),default=0)
            choices.append(((-outward,distance,u['unit_id'],p['index']),u,p))
    if not choices:return None
    _,unit,plot=min(choices,key=lambda r:r[0])
    if d['world_input']['selected_unit_id']!=unit['unit_id']:
        return next((a for a in offers if a['kind']=='world_select_unit' and a['unit_id']==unit['unit_id']),None)
    return clicks[plot['x'],plot['y']]


def prepare(config,output,*,total_seconds=900,max_lifetimes=4):
    """Bounded exploration using the existing session/Save/Load supervisors."""
    from civ6_host import SessionClient
    from civ6_host.runtime.backend import NetworkBackend
    from civ6_host.contracts.network_turn import is_waiting
    if (type(total_seconds) is not int or not 300<=total_seconds<=900
            or type(max_lifetimes) is not int or not 1<=max_lifetimes<=4):
        raise ValueError('Preparation exceeds the 900 s / four-lifetime envelope')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    config=deepcopy(config);config['checkpoint_on_close']=True
    started=time.monotonic();visited=set();checkpoint=config.get('checkpoint');turns=0
    record=dict(status='running',training=False,public_selector=True,commands=[],runs=[],
        input_checkpoint=deepcopy(checkpoint),turns_advanced=0,poll_calls=0,
        selector_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    try:
        for lifetime in range(max_lifetimes):
            if time.monotonic()-started>total_seconds-230:break
            current=dict(config)
            if checkpoint is not None:current['checkpoint']=checkpoint
            backend=NetworkBackend(**current)
            client=(SessionClient(backend,allow_administrative=True)
                    if current.get('administrative_information') is True else SessionClient(backend))
            prior_command_count=len(record['commands']);prior_turns=turns
            try:
                view=client.reset();pid=view['observation']['player_id'];initial_turn=view['observation']['turn']
                last_counted_turn=initial_turn
                reset_timings=deepcopy(backend._session.reset_timings_seconds)
                initial_native_remaining=native_remaining(backend)
                if current.get('administrative_information') is True:
                    record.setdefault('combat_information',[]).append(dict(
                        **combat_information_snapshot(client,view)))
                for decision in range(48):
                    path=backend.run/('public-%04d.json'%view['sequence'])
                    path.write_text(json.dumps(view),encoding='utf-8')
                    state=view['decisions']['unit_attacks']
                    if state is not None and state['offers']:
                        record['offered_attacks']=deepcopy(state['offers']);record['prepared_public']=str(path)
                        record['status']='native_unit_attack_checkpoint_prepared_pending_review'
                        break
                    # Leave time for native Save/Unload/Destroy. No timeout or
                    # empty query is converted into success.
                    active=not is_waiting(view['decisions']['turn_controls'])
                    remaining=native_remaining(backend)
                    if active and (remaining<65 or time.monotonic()-started>total_seconds-65):break
                    if not active and remaining<65:
                        raise RuntimeError('Preparation could not finish its waiting turn within the native lifetime')
                    action=select_exploration(view,visited)
                    if action is not None:
                        if action['kind']=='world_plot_click':
                            selected=view['decisions']['world_input']['selected_unit_id']
                            visited.add((selected,action['y']*view['observation']['width']+action['x']))
                    else:
                        if active and remaining<105:break
                        action=(next((r['action'] for r in view['decisions']['candidates']
                                      if r['action']['kind']=='force_end_turn'),None) if active else None)
                    if action is None:
                        view=client.poll(pid);record['poll_calls']+=1
                    else:
                        row=next(r for r in view['decisions']['candidates'] if r['action']==action)
                        view=client.act(pid,view['decisions']['decision_id'],row['candidate_id'])
                        record['commands'].append(deepcopy(client.command_result))
                    (backend.run/('public-%04d.json'%view['sequence'])).write_text(json.dumps(view),encoding='utf-8')
                    if (view['observation']['turn']>last_counted_turn
                            and not is_waiting(view['decisions']['turn_controls'])):
                        turns+=view['observation']['turn']-last_counted_turn
                        last_counted_turn=view['observation']['turn']
                        state=view['decisions']['unit_attacks']
                        if state is not None and state['offers']:
                            record['offered_attacks']=deepcopy(state['offers'])
                            record['prepared_public']=str(backend.run/('public-%04d.json'%view['sequence']))
                            record['status']='native_unit_attack_checkpoint_prepared_pending_review'
                            break
                        # Keep this owned lifetime while its actual deadline,
                        # global wall budget and 48-decision cap permit it.
                if is_waiting(view['decisions']['turn_controls']):
                    raise RuntimeError('Preparation exhausted its bounded decisions before native readiness')
                closed=client.close(pid)
                (backend.run/('public-%04d.json'%closed['sequence'])).write_text(json.dumps(closed),encoding='utf-8')
                checkpoint=deepcopy(backend.checkpoint)
                if checkpoint is None:raise RuntimeError('Preparation closed without its actual native checkpoint')
                record['runs'].append(dict(run=str(backend.run),report=backend.report,checkpoint=checkpoint,
                    reset_timings_seconds=reset_timings,initial_native_remaining_seconds=initial_native_remaining))
                record['checkpoint']=checkpoint;record['turns_advanced']=turns
                if record['status']=='native_unit_attack_checkpoint_prepared_pending_review':break
                if len(record['commands'])==prior_command_count and turns==prior_turns:
                    record['stop_reason']='no_action_or_turn_progress_in_this_lifetime'
                    break
            finally:
                client.abort()
                if backend.run and not any(r['run']==str(backend.run) for r in record['runs']):
                    record['runs'].append(dict(run=str(backend.run),report=backend.report,checkpoint=None))
        if record['status']=='running':record['status']='partial_public_exploration_checkpoint_retained'
    except BaseException as exc:
        record.update(status='refused',error=repr(exc))
    record['seconds']=time.monotonic()-started
    (output/'result.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return record


def native_remaining(backend):
    """Use the actual native supervisor clock, excluding parent preparation."""
    session=backend._session
    seconds=session.lifetime_seconds
    begun=session.started
    if (type(seconds) is not int or type(begun) not in (int,float)
            or seconds<=0 or begun<=0):
        raise ValueError('Preparation needs the actual supervised native deadline')
    return max(0.0,seconds-(time.perf_counter()-begun))

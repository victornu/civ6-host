"""Caller-selected ordinary government changes on the existing saved owner."""
from civ6_host.contracts import government as contract
from .native import native_government_actions as native
from .native import native_government_consideration as consideration
from .native.native_saved_government import catalog as shared_catalog
from .xp2_government_source import bind_owner, SOURCE


def project(raw,player_id,turn):
    """Project the shared native query without losing any government row."""
    state,ack=raw['catalog'],raw['consideration']
    if ((state['player_id'],state['current_game_turn'],ack['player_id'],ack['current_game_turn']) != (player_id,turn,player_id,turn)
            or ack['government_index']!=state['current_government_index']):
        raise ValueError('Government projection belongs to another decision')
    public=dict(player_id=player_id,turn=turn,current_index=state['current_government_index'],
        can_change=state['can_change_government_at_all'],changed=state['government_change_made'],
        civic_completed=state['civic_completed_this_turn'],considered=ack['considered'],
        consideration_blocker=ack['consideration_blocker_present'],choices=[
            dict(index=row['index'],hash=row['hash']&0xffffffff,unlocked=row['unlocked'],
                 can_change=row['can_change'],anarchy_turns=row['anarchy_turns'])
            for row in state['choices']])
    contract.validate_catalogue(public,player_id,turn)
    return public


def read(saved,observation):
    bind_owner(saved)
    pid,turn=observation['player_id'],observation['turn']
    raw=shared_catalog(saved.prefix,turn,player_id=pid)
    public=project(raw,pid,turn)
    saved.continuation.explicit_government_raw=raw
    saved.continuation.explicit_government=public
    return public


def apply(saved,action,before):
    from .native.native_player_observation import observe_player
    pid,turn=before['player_id'],before['turn']
    expected=saved.continuation.explicit_government
    fresh=read(saved,before)
    if fresh!=expected or action not in contract.actions(fresh):
        raise RuntimeError('Government choice is stale or not offered')
    p=saved.prefix
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('Government choice requires drained owned queues')
    raw=saved.continuation.explicit_government_raw
    if action['kind']=='government':
        choice=native.choose(raw['catalog'],action['index'])
        if choice['selected_hash']&0xffffffff!=action['hash']:
            raise ValueError('Government hash differs from its native row')
        submitted=native.parse_request_result(p.runtime.evaluate_text(p.ui_child,
            native.request_source(choice),b'@xp2_government_request',capacity=16384),choice)
        if len(p.actions.pending)!=1:
            raise RuntimeError('Government request does not match its single native archive')
        native.validate_native_archive(p.actions.pending[0],choice)
        saved.emit('xp2_government_request_submitted',action=action,submitted=submitted,
                   source_proof_sha256=SOURCE[1],native_effect_verified=False)
        p.actions.deliver_one()
        p.deferred_events.drain()
        p.view_publisher.publish()
        effect=native.parse_effect(p.runtime.evaluate_text(p.ui_child,native.effect_source(choice),
            b'@xp2_government_effect',capacity=16384),choice)
        if not effect['confirmed'] or not effect['government_change_made']:
            raise RuntimeError('Native government adoption differs from the requested target')
    elif action['kind']=='retain_government':
        result=consideration.parse_request_result(p.runtime.evaluate_text(p.ui_child,
            consideration.request_source(pid,turn,action['index']),b'@xp2_retain_government',
            capacity=4096),pid,turn,action['index'])
        if p.actions.pending:
            raise RuntimeError('Government consideration unexpectedly enqueued a game request')
        p.deferred_events.drain()
        p.view_publisher.publish()
        effect=dict(confirmed=result['consideration_marked'],government_changed=False,
                    current_government_index=action['index'])
    else:
        raise ValueError('Unsupported government decision')
    observed=observe_player(p.runtime,p.ui_child,pid)
    after=read(saved,observed)
    if observed['turn']!=turn or after['current_index']!=action['index']:
        raise RuntimeError('Government transition changed its turn or target')
    if action['kind']=='retain_government' and (not after['considered'] or after['consideration_blocker']):
        raise RuntimeError('Government consideration did not clear its native blocker')
    from .xp2_policies import read as read_policies
    policies=read_policies(saved,observed)
    saved.emit('xp2_government_effect_verified',action=action,before=fresh,after=after,
        policy_slot_count=len(policies['slots']),effect=effect,
        source_proof_sha256=SOURCE[1],automatic_choices_applied=False)
    return dict(observation=observed,effect=effect)

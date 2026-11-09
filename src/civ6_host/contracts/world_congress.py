"""Portable Congress observations, parameterized offers and local ballot drafts.

One actor action confirms the complete official form. Its internal native
request sequence is non-atomic and permits no actor decision between packets.
A draft is local data, never a native transaction. Opaque discussion/proposal indices resolve
against the exact owned catalogue; hidden Sender/Target values stay in runtime.
This schema does not qualify native getters, requests or effect readback.
"""
from copy import deepcopy
import hashlib
import json
import math

SCHEMA = 'civ6-host.world-congress.v1'
DRAFT_SCHEMA = 'civ6-host.world-congress-draft.v1'
PLAN_SCHEMA = 'civ6-host.world-congress-plan.v1'
GAPS = ('review_unqualified', 'resolution_preferences_unqualified',
        'emergency_details_unqualified', 'participant_roster_unqualified',
        'active_effects_unqualified', 'available_proposals_acknowledgement_lifetime_unqualified')
UNAVAILABLE = GAPS
_I32, _U32, _LIMIT = 0x7fffffff, 0xffffffff, 4096
_FIELDS = frozenset(('schema', 'player_id', 'turn', 'sequence', 'turn_segment',
    'stage', 'paused', 'in_session', 'local_alive', 'turn_active', 'presentation', 'meeting', 'favor', 'current_favor',
    'vote_cost', 'resolutions', 'discussions', 'proposals', 'offers',
    'unavailable'))
_RESOLUTION = frozenset(('resolution_hash', 'resolution_type', 'name',
    'effect_a', 'effect_b', 'target_type', 'targets'))
_DISCUSSION = frozenset(('index', 'type_name', 'sender', 'target', 'name',
    'description', 'disabled', 'no_upvote', 'no_downvote', 'blocker', 'vote_cost'))
_PROPOSAL = frozenset(('index', 'type_name', 'sender', 'target', 'name',
    'description', 'disabled', 'blocker', 'favor_cost', 'target_key'))
_FLAGS = frozenset(('open', 'confirm_ballot', 'confirm_proposals', 'close'))

CANDIDATE_FIELDS = {
    'congress_open': frozenset(('kind', 'sequence')),
    'congress_confirm_ballot': frozenset(('kind', 'sequence')),
    'congress_confirm_proposals': frozenset(('kind', 'sequence')),
    'congress_close': frozenset(('kind', 'sequence')),
}
PARAMETER_FIELDS = {
    'congress_confirm_ballot': frozenset(('resolutions', 'discussions')),
    'congress_confirm_proposals': frozenset(('proposal_indices',)),
}
ACTION_FIELDS = {kind: fields | PARAMETER_FIELDS.get(kind, frozenset())
                 for kind, fields in CANDIDATE_FIELDS.items()}
# Internal transport descriptors: never network candidates or actor actions.
OPERATION_FIELDS = {
    'congress_resolution_vote': frozenset(('kind', 'sequence', 'resolution_hash',
                                         'option', 'target_index', 'votes')),
    'congress_discussion_vote': frozenset(('kind', 'sequence', 'discussion_index', 'votes')),
    'congress_discussion_selection': frozenset(('kind', 'sequence', 'proposal_index')),
    'congress_submit': frozenset(('kind', 'sequence')),
    'congress_looked_at_available': frozenset(('kind', 'sequence')),
}
_RESOLUTION_SELECTION = frozenset(('resolution_hash', 'option', 'target_index', 'votes'))
_DISCUSSION_SELECTION = frozenset(('discussion_index', 'votes'))


def _shape(value, fields, label):
    if type(value) is not dict or set(value) != fields:
        raise ValueError('Malformed Congress ' + label)


def _int(value, label, low=0, high=_I32):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Invalid Congress ' + label)


def _number(value, label, low=0, high=_I32):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        raise ValueError('Invalid Congress ' + label)


def _text(value, label):
    if type(value) is not str or '\0' in value or len(value.encode('utf8')) > 32768:
        raise ValueError('Invalid Congress ' + label)


def _rows(value, label, limit=_LIMIT):
    if type(value) is not list or len(value) > limit:
        raise ValueError('Unbounded or malformed Congress ' + label)
    return value


def _unique(items, label):
    if len(items) != len(set(items)):
        raise ValueError('Duplicate Congress ' + label)


def _player(value):
    _shape(value, {'player_id', 'label'}, 'visible player reference')
    if value['player_id'] is not None:
        _int(value['player_id'], 'visible player', 0, 63)
    _text(value['label'], 'visible player label')


def validate_candidate(action):
    kind = action.get('kind') if type(action) is dict else None
    if type(kind) is not str or kind not in CANDIDATE_FIELDS:
        raise ValueError('Unknown Congress actor candidate')
    _shape(action, CANDIDATE_FIELDS[kind], 'candidate')
    _int(action['sequence'], 'sequence', 0, _U32)
    return action


def _resolution_selection(row):
    _shape(row, _RESOLUTION_SELECTION, 'resolution selection')
    _int(row['resolution_hash'], 'resolution hash', 0, _U32)
    _int(row['option'], 'A/B option', 1, 2)
    _int(row['target_index'], 'original zero-based target index', 0, _LIMIT - 1)
    _int(row['votes'], 'resolution votes', 1)


def _discussion_selection(row, *, actor):
    _shape(row, _DISCUSSION_SELECTION, 'discussion selection')
    _int(row['discussion_index'], 'discussion index', 0, _LIMIT - 1)
    _int(row['votes'], 'signed discussion votes', -_I32 - 1)
    if actor and row['votes'] == 0:
        raise ValueError('Congress editable discussion requires a nonzero vote')


def validate_action(action):
    kind = action.get('kind') if type(action) is dict else None
    if type(kind) is not str or kind not in ACTION_FIELDS:
        raise ValueError('Unknown Congress actor action; primitive requests are internal')
    _shape(action, ACTION_FIELDS[kind], 'actor action')
    validate_candidate({key: action[key] for key in CANDIDATE_FIELDS[kind]})
    if kind == 'congress_confirm_ballot':
        for row in _rows(action['resolutions'], 'ballot resolutions'):
            _resolution_selection(row)
        for row in _rows(action['discussions'], 'ballot discussions'):
            _discussion_selection(row, actor=True)
        _unique([r['resolution_hash'] for r in action['resolutions']], 'resolution selection')
        _unique([r['discussion_index'] for r in action['discussions']], 'discussion selection')
    elif kind == 'congress_confirm_proposals':
        items = _rows(action['proposal_indices'], 'proposal selections')
        if not items:
            raise ValueError('Congress proposal confirmation is empty')
        for index in items: _int(index, 'proposal index', 0, _LIMIT - 1)
        _unique(items, 'proposal selection')
    return action


def validate_operation(operation):
    """Internal source transport only; signed zero is not an actor choice."""
    kind = operation.get('kind') if type(operation) is dict else None
    if type(kind) is not str or kind not in OPERATION_FIELDS:
        raise ValueError('Unknown Congress internal operation')
    _shape(operation, OPERATION_FIELDS[kind], 'internal operation')
    _int(operation['sequence'], 'sequence', 0, _U32)
    if kind == 'congress_resolution_vote':
        _resolution_selection({k: operation[k] for k in _RESOLUTION_SELECTION})
    elif kind == 'congress_discussion_vote':
        _discussion_selection({k: operation[k] for k in _DISCUSSION_SELECTION}, actor=False)
    elif kind == 'congress_discussion_selection':
        _int(operation['proposal_index'], 'proposal index', 0, _LIMIT - 1)
    return operation


def _votable(row):
    return not row['disabled'] and not (row['no_upvote'] and row['no_downvote'])


def _cost(value):
    _shape(value, {'max_votes', 'costs'}, 'vote costs')
    _int(value['max_votes'], 'maximum votes')
    for number in _rows(value['costs'], 'cumulative vote costs'):
        _number(number, 'cumulative cost')


def validate_catalogue(value, pid, turn, sequence=None):
    _int(pid, 'player', 0, 63)
    _int(turn, 'turn')
    _shape(value, _FIELDS, 'catalogue')
    if (value['schema'] != SCHEMA or type(value['player_id']) is not int
            or value['player_id'] != pid or type(value['turn']) is not int
            or value['turn'] != turn):
        raise ValueError('Foreign Congress catalogue')
    _int(value['sequence'], 'sequence', 0, _U32)
    if sequence is not None:
        _int(sequence, 'expected sequence', 0, _U32)
        if value['sequence'] != sequence:
            raise ValueError('Stale Congress catalogue sequence')
    _int(value['turn_segment'], 'native turn segment', 0, _U32)
    if type(value['stage']) is not str or value['stage'] not in ('ordinary', 'regular', 'special', 'resolving'):
        raise ValueError('Unknown Congress stage')
    for key in ('paused', 'in_session', 'local_alive', 'turn_active'):
        if type(value[key]) is not bool:
            raise ValueError('Invalid Congress ' + key)
    if ((value['stage'] == 'ordinary' and value['in_session'])
            or (value['stage'] in ('regular', 'special') and not value['in_session'])):
        raise ValueError('Congress stage differs from native session state')
    if (type(value['presentation']) is not str
            or value['presentation'] not in ('closed', 'available_proposals')
            or (value['presentation'] == 'available_proposals' and value['stage'] != 'ordinary')):
        raise ValueError('Congress presentation crosses its owned review scope')
    for key, present in (('meeting', value['stage'] == 'ordinary'),
                         ('vote_cost', value['stage'] == 'regular'),
                         ('resolutions', value['stage'] == 'regular'),
                         ('discussions', value['stage'] in ('regular', 'special')),
                         ('proposals', value['stage'] == 'ordinary')):
        if (value[key] is not None) != present:
            raise ValueError('Congress ' + key + ' crosses its source display stage')
    if value['meeting'] is not None:
        _shape(value['meeting'], {'turns_left', 'percentage'}, 'meeting')
        _int(value['meeting']['turns_left'], 'meeting turns', -_I32 - 1)
        _number(value['meeting']['percentage'], 'meeting percentage', 0, 100)
    _number(value['favor'], 'favor')
    _number(value['current_favor'], 'current favor')
    if value['presentation'] != 'available_proposals' and value['favor'] != value['current_favor']:
        raise ValueError('Congress form budget differs from current favor outside owned review')
    cost = value['vote_cost']
    if cost is not None:
        _cost(cost)
    hashes = []
    for row in _rows(value['resolutions'] if value['resolutions'] is not None else [], 'resolutions'):
        _shape(row, _RESOLUTION, 'resolution')
        _int(row['resolution_hash'], 'resolution hash', 0, _U32)
        hashes.append(row['resolution_hash'])
        for key in ('resolution_type', 'name', 'effect_a', 'effect_b', 'target_type'):
            _text(row[key], key)
        for index, target in enumerate(_rows(row['targets'], 'resolution targets')):
            _shape(target, {'index', 'value', 'label', 'player_id'}, 'target')
            _int(target['index'], 'target index', 0, _LIMIT - 1)
            if target['index'] != index:
                raise ValueError('Congress target indices lost native order')
            _player({key: target[key] for key in ('player_id', 'label')})
            if row['target_type'] == 'PlayerType':
                expected = None if target['player_id'] is None else str(target['player_id'])
                if target['value'] != expected:
                    raise ValueError('Congress player target exposes inconsistent identity')
            elif target['player_id'] is not None or target['value'] is None:
                raise ValueError('Congress non-player target has an invalid identity')
            if target['value'] is not None:
                _text(target['value'], 'target value')
    _unique(hashes, 'resolution hash')
    known_targets, opaque_targets = {}, {}
    for field, fields in (('discussions', _DISCUSSION), ('proposals', _PROPOSAL)):
        for index, row in enumerate(_rows(value[field] if value[field] is not None else [], field)):
            _shape(row, fields, field + ' row')
            _int(row['index'], field + ' index', 0, _LIMIT - 1)
            if row['index'] != index:
                raise ValueError('Congress row indices lost source order')
            for key in ('type_name', 'name', 'description'):
                _text(row[key], key)
            _player(row['sender']); _player(row['target'])
            if row['blocker'] is not None:
                _text(row['blocker'], 'blocker')
            for key in ('disabled', 'no_upvote', 'no_downvote'):
                if key in row and type(row[key]) is not bool:
                    raise ValueError('Invalid Congress blocker flag')
            if field == 'proposals':
                _number(row['favor_cost'], 'proposal cost')
                _int(row['target_key'], 'opaque proposal target key', 0, _LIMIT - 1)
                target = row['target']['player_id']
                previous = opaque_targets.setdefault(row['target_key'], target)
                if previous != target:
                    raise ValueError('Congress opaque target has inconsistent visible identity')
                if target is not None and known_targets.setdefault(target, row['target_key']) != row['target_key']:
                    raise ValueError('Congress known target has inconsistent opaque key')
            else:
                _cost(row['vote_cost'])
    _shape(value['offers'], _FLAGS, 'offer flags')
    if any(type(flag) is not bool for flag in value['offers'].values()):
        raise ValueError('Invalid Congress offer flag')
    offers = value['offers']
    if (offers['open'] and (value['presentation'] != 'closed'
            or value['stage'] != 'ordinary' or value['paused'] or not value['proposals'])):
        raise ValueError('Congress available-proposals opening is not offered')
    if ((offers['confirm_proposals'] or offers['close'])
            and value['presentation'] != 'available_proposals'):
        raise ValueError('Congress action requires the owned available-proposals view')
    if ((value['paused'] or not value['local_alive'] or not value['turn_active'])
            and any(offers[k] for k in ('confirm_ballot', 'confirm_proposals'))):
        raise ValueError('Congress action offered while paused or player unavailable')
    voting = value['in_session'] and value['stage'] in ('regular', 'special')
    if ((offers['confirm_ballot'] and not voting)
            or (any(offers[k] for k in ('confirm_proposals', 'close'))
                and (value['in_session'] or value['stage'] != 'ordinary'))):
        raise ValueError('Congress offers cross the official session stage')
    if offers['confirm_ballot'] and not _has_ballot_choices(value):
        raise ValueError('Congress empty phase is automatic, not an actor confirmation')
    if offers['confirm_proposals']:
        locked_targets = {r['target_key'] for r in value['proposals'] if r['disabled']}
        if not any(not r['disabled'] and r['target_key'] not in locked_targets
                   and r['favor_cost'] <= value['favor'] for r in value['proposals']):
            raise ValueError('Congress proposal confirmation has no selectable proposal')
    if type(value['unavailable']) is not list or value['unavailable'] != list(GAPS):
        raise ValueError('Congress catalogue must retain its explicit observation gaps')
    return value


def compare_own(value, observation, sequence=None):
    if type(observation) is not dict or not {'player_id', 'turn'} <= set(observation):
        raise ValueError('Missing Congress player observation')
    return validate_catalogue(value, observation['player_id'], observation['turn'], sequence)


def _has_ballot_choices(value):
    return bool(value['resolutions']) or any(_votable(r) for r in (value['discussions'] or []))


def actions(value):
    """Offer logical UI confirmations only, never their individual opcodes."""
    if value is None:
        return []
    if type(value) is not dict:
        raise ValueError('Missing Congress catalogue')
    validate_catalogue(value, value.get('player_id'), value.get('turn'))
    result = []
    for flag, kind in (('open', 'congress_open'),
                       ('confirm_ballot', 'congress_confirm_ballot'),
                       ('confirm_proposals', 'congress_confirm_proposals'),
                       ('close', 'congress_close')):
        if value['offers'][flag]:
            result.append(dict(kind=kind, sequence=value['sequence']))
    return result


def _vote_cost(cost, votes):
    count = abs(votes)
    if not 1 <= count <= min(cost['max_votes'], len(cost['costs'])):
        raise ValueError('Congress votes exceed the source cost domain')
    return cost['costs'][count - 1]


def _checked(value, action):
    """Check the entire form before any operation is prepared or emitted."""
    kind, total = action['kind'], 0
    if kind == 'congress_confirm_ballot':
        resolutions = {r['resolution_hash']: r for r in action['resolutions']}
        discussions = {r['discussion_index']: r for r in action['discussions']}
        required_resolutions = value['resolutions'] or []
        required_discussions = [r for r in value['discussions'] if _votable(r)]
        if (set(resolutions) != {r['resolution_hash'] for r in required_resolutions}
                or set(discussions) != {r['index'] for r in required_discussions}):
            raise ValueError('Congress confirmation must contain every offered ballot item')
        for row in required_resolutions:
            selected = resolutions[row['resolution_hash']]
            if selected['target_index'] >= len(row['targets']):
                raise ValueError('Congress target index is not offered')
            total += _vote_cost(value['vote_cost'], selected['votes'])
        for row in required_discussions:
            votes = discussions[row['index']]['votes']
            if (votes > 0 and row['no_upvote']) or (votes < 0 and row['no_downvote']):
                raise ValueError('Congress discussion direction is blocked')
            total += _vote_cost(row['vote_cost'], votes)
        action['resolutions'] = [deepcopy(resolutions[r['resolution_hash']]) for r in required_resolutions]
        action['discussions'] = [deepcopy(discussions[r['index']]) for r in required_discussions]
    elif kind == 'congress_confirm_proposals':
        selected, targets = set(action['proposal_indices']), set()
        locked_targets = {r['target_key'] for r in value['proposals'] if r['disabled']}
        if any(i >= len(value['proposals']) for i in selected):
            raise ValueError('Congress proposal is not offered')
        for index in selected:
            row = value['proposals'][index]
            if row['disabled']:
                raise ValueError('Congress proposal is disabled')
            if row['target_key'] in locked_targets:
                raise ValueError('Congress proposal target is locked by an existing disabled proposal')
            if row['target_key'] in targets:
                raise ValueError('Congress confirmation proposes two discussions for one target')
            targets.add(row['target_key'])
            total += row['favor_cost']
        action['proposal_indices'] = [r['index'] for r in value['proposals'] if r['index'] in selected]
    if total > value['favor']:
        raise ValueError('Congress combined form exceeds available favor')
    return action, total


def choose(value, candidate, parameters=None):
    """Validate one complete UI confirmation; no native effects or RPC here."""
    validate_candidate(candidate)
    if candidate not in actions(value):
        raise ValueError('Stale or absent Congress candidate')
    kind = candidate['kind']
    if kind in PARAMETER_FIELDS:
        _shape(parameters, PARAMETER_FIELDS[kind], 'confirmation parameters')
        action = deepcopy({**candidate, **parameters})
    else:
        if parameters is not None:
            raise ValueError('Congress presentation action has no public parameters')
        action = dict(candidate)
    validate_action(action)
    return _checked(value, action)[0]


def operation_plan(value, action):
    """Private non-atomic request sequence for one fully checked actor action.

    The runtime must prepare and revalidate the complete sequence before its
    first emission, own it without actor interleaving, and report partial
    delivery explicitly. This pure plan proves neither native success nor
    the UI's within-family pairs iteration; runtime retains that source order.
    """
    validate_action(action)
    candidate = {k: action[k] for k in CANDIDATE_FIELDS[action['kind']]}
    parameters = ({k: action[k] for k in PARAMETER_FIELDS[action['kind']]}
                  if action['kind'] in PARAMETER_FIELDS else None)
    checked = choose(value, candidate, parameters)
    operations, seq = [], checked['sequence']
    kind = checked['kind']
    if kind == 'congress_confirm_ballot':
        operations.extend(dict(kind='congress_resolution_vote', sequence=seq, **r)
                          for r in checked['resolutions'])
        operations.extend(dict(kind='congress_discussion_vote', sequence=seq, **r)
                          for r in checked['discussions'])
        operations.append(dict(kind='congress_submit', sequence=seq))
    elif kind == 'congress_confirm_proposals':
        operations.extend(dict(kind='congress_discussion_selection', sequence=seq, proposal_index=i)
                          for i in checked['proposal_indices'])
    elif kind == 'congress_close':
        operations.append(dict(kind='congress_looked_at_available', sequence=seq))
    for operation in operations: validate_operation(operation)
    return dict(atomic=False, actor_decisions_between_operations=False,
        operations=operations,
        following_ui_action=('ACTION_ENDTURN' if kind == 'congress_confirm_ballot'
                             else 'ClosePopup' if kind == 'congress_confirm_proposals'
                             else 'OpenAvailableProposals' if kind == 'congress_open' else None))


def empty_phase_plan(value):
    """Private automatic SetPhase path; never an actor candidate."""
    if type(value) is not dict:
        raise ValueError('Missing Congress empty-phase catalogue')
    validate_catalogue(value, value.get('player_id'), value.get('turn'))
    if (value['stage'] not in ('regular', 'special') or not value['in_session']
            or value['paused'] or not value['local_alive'] or not value['turn_active']
            or _has_ballot_choices(value)):
        raise ValueError('Congress automatic empty-phase path is unavailable')
    return dict(atomic=False, actor_decisions_between_operations=False,
        operations=[dict(kind='congress_submit', sequence=value['sequence'])],
        following_ui_action='ACTION_ENDTURN')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=True, allow_nan=False).encode('ascii')).hexdigest()


def ballot_draft(value, parameters):
    """Prepare a complete detached form locally; this sends nothing."""
    if type(value) is not dict:
        raise ValueError('Missing Congress draft catalogue')
    kind = ('congress_confirm_ballot' if value.get('stage') in ('regular', 'special')
            else 'congress_confirm_proposals')
    candidate = dict(kind=kind, sequence=value.get('sequence'))
    action = choose(value, candidate, parameters)
    _, total = _checked(value, deepcopy(action))
    return dict(schema=DRAFT_SCHEMA, player_id=value['player_id'], turn=value['turn'],
        sequence=value['sequence'], catalogue_digest=_digest(value), action=action,
        total_favor_cost=total, native_submission_issued=False)


def draft_plan(value, draft):
    """Review metadata; individual native requests are not actor choices."""
    _shape(draft, {'schema', 'player_id', 'turn', 'sequence', 'catalogue_digest',
        'action', 'total_favor_cost', 'native_submission_issued'}, 'draft')
    if draft['schema'] != DRAFT_SCHEMA or draft['native_submission_issued'] is not False:
        raise ValueError('Congress draft cannot claim native submission')
    _int(draft['player_id'], 'draft player', 0, 63)
    _int(draft['turn'], 'draft turn')
    _int(draft['sequence'], 'draft sequence', 0, _U32)
    _number(draft['total_favor_cost'], 'draft total')
    validate_action(draft['action'])
    kind = draft['action']['kind']
    if kind not in PARAMETER_FIELDS:
        raise ValueError('Congress close is not a ballot draft')
    rebuilt = ballot_draft(value, {k: draft['action'][k] for k in PARAMETER_FIELDS[kind]})
    if draft != rebuilt:
        raise ValueError('Stale or altered Congress draft')
    private = operation_plan(value, draft['action'])
    return dict(schema=PLAN_SCHEMA, catalogue_digest=draft['catalogue_digest'],
        atomic=False, actor_decisions_between_operations=False,
        request_count=len(private['operations']),
        following_ui_action=private['following_ui_action'], native_submission_issued=False)

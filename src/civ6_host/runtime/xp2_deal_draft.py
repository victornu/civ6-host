"""Official outgoing deal session with a met AI player."""

from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import struct

from civ6_host.contracts.diplomacy_decisions import (
    DEAL_OTHER_TERMS_GAP, DEAL_RESOURCE_WRITE_GAP, EQUALIZE, FINALIZE,
    GOLD_TERM_FIELDS, OPEN_BORDERS_CHOICES,
    RESOURCE_CHOICES, SET_GOLD, SET_RECURRING_GOLD, SET_REQUESTED_GOLD, SET_REQUESTED_RECURRING_GOLD,
    open_borders_choices, resolve_resource, resource_choices, validate_open_borders, validate_peace_terms,
)

from . import xp2_deal_gold as gold
from . import xp2_deal_history as deal_history
from . import xp2_deal_open_borders as borders
from . import xp2_deal_peace as treaty
from . import xp2_deal_resources as resources
from . import xp2_deal_value as deal_value
from .xp2_major_deals import counterparty_terms
from .configuration_profiles import _source
from .execution_images import identity
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-major-deal-draft-source.json',
          '7f092d94fefea923358c98390bfa318016796ca76c1ff43b87cd87b08f913985')
STATEMENT_SOURCE = ('evidence/host-xp2-empty-deal-statement-native-source.json',
                    '4f56dd2c6e0adf29cdb85ead16d96b336d3ef3721018d0299871aa9cb2820ae9')
EQUALIZE_SOURCE = ('evidence/host-xp2-deal-equalize-source.json',
                   '056168ef32fcc1c5e74982be80d67ac37d3c11233b48ae72b0ebf2197bd0e829')
EQUALIZE_WIRE = ('evidence/host-xp2-deal-equalize-wire-source.json',
                 '974f6cb6d39849e592b6ffa7b1824562fbe12b9cccb58df5b8c7c4664ac5c9b6')
DEMAND_SOURCE = ('evidence/host-xp2-deal-demand-source.json',
                 '836b4389e706d19a789628320d3fc926c6d65de78c3483fa7e41ea1dd49c7180')
DEMAND_ARCHIVE_SOURCE = ('evidence/host-xp2-deal-demand-reply-archive.json',
                         'cac9b70f29078edbb902808f7aff350718a5c4809aa4a3f90f7ff0d98f93f232')
DEMAND_SETTLEMENT_SOURCE = ('evidence/host-xp2-demand-accepted-archive-source.json',
                            'f9ec297661326ce7165d16678b47d80d558d9e3c66bc204b8bf006c70e738803')


def _proof(image):
    selected = identity(image)
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-major-deal-draft.static.v1'
            or proof['native_execution'] is not False
            or proof['image']['sha256'] != selected['image_sha256']
            or Path(proof['image']['path']).resolve() != Path(selected['path']).resolve()
            or proof['factory']['request'] != 'MAKE_DEAL'
            or proof['factory']['expected_registration'] is not True
            or len(proof['factory']['slots']) != 8
            or set(proof['native_spans']) != {'ClearWorkingDeal','GetWorkingDeal','GetItemCount','FindOpenSessionID'}):
        raise ValueError('Native empty AI deal source differs')
    return proof


def source_dependencies(*, execution_image):
    proof = _proof(execution_image)
    demand = _demand_proof()
    _negotiation_proof()
    pins = {str(resolve_path(resource_root() / path).resolve()): digest
            for path, digest in (SOURCE, STATEMENT_SOURCE, EQUALIZE_SOURCE, EQUALIZE_WIRE,
                                 DEMAND_SOURCE, DEMAND_ARCHIVE_SOURCE, DEMAND_SETTLEMENT_SOURCE)}
    for row in (*proof['parents'], *proof['ui_files'].values(), *demand['parents'], *demand['ui'].values()):
        path = resolve_path(resource_root() / row['path']).resolve()
        if sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Native empty AI deal dependency changed')
        pins[str(path)] = row['sha256']
    pins.update(gold.dependencies(execution_image))
    pins.update(resources.dependencies(execution_image))
    pins.update(borders.dependencies(execution_image))
    pins.update(deal_value.dependencies())
    return pins


def _demand_proof():
    proof = _source(DEMAND_SOURCE)
    archive = _source(DEMAND_ARCHIVE_SOURCE)
    settlement = _source(DEMAND_SETTLEMENT_SOURCE)
    if (proof['schema']!='civ6-host.xp2-deal-demand.static.v1' or proof['native_execution'] is not False
            or proof['factory']['request']!='MAKE_DEMAND'
            or int(proof['factory']['statement_hash'],16)!=gold.DEMAND_STATEMENT
            or proof['proposal_code']!=5 or proof['confirmation_uses_demand_type'] is not True
            or archive['schema']!='civ6-host.xp2-demand-reply-archive.v1'
            or (archive['parent']['path'],archive['parent']['sha256'])!=DEMAND_SOURCE
            or archive['observed']['kind']!=0xf06250e4 or archive['observed']['action']!=2
            or archive['observed']['terms_offset']!=16
            or settlement['schema']!='civ6-host.xp2-demand-accepted-archive.v1'
            or (settlement['demand_source']['path'],settlement['demand_source']['sha256'])!=DEMAND_SOURCE
            or settlement['local_confirmation_duplicated_native_application'] is not True):
        raise ValueError('Unknown native demand source')
    return proof


def _negotiation_proof():
    source = _source(EQUALIZE_SOURCE)
    wire = _source(EQUALIZE_WIRE)
    if (source['schema'] != 'civ6-host.xp2-deal-equalize.static.v1'
            or wire['schema'] != 'civ6-host.xp2-deal-equalize-wire.static.v1'
            or source['native_execution'] is not False or wire['native_execution'] is not False
            or (wire['source']['path'], wire['source']['sha256']) != EQUALIZE_SOURCE
            or source['image']['sha256'] != wire['image_sha256']
            or tuple(source['proposal_actions'][key] for key in ('ADJUSTED','EQUALIZE','EQUALIZE_FAILED')) != (3,6,10)
            or wire['request'] != 6
            or wire['outcome'] != {'3':'adjusted', '10':'equalize_failed', '2':'rejected'}
            or wire['fields'].keys() != wire['outcome'].keys()):
        raise ValueError('Invalid native deal negotiation source')
    return source, wire


def verify_request(saved, image, *, demand=False):
    from .xp2_initial_statement_factory import _registered_request

    proof = _proof(image)
    gold.verify(saved, image)
    resources.verify(saved, image)
    negotiation, wire = _negotiation_proof()
    if wire['image_sha256'] != identity(image)['image_sha256']:
        raise ValueError('Native deal negotiation requires its exact installed image')
    if not hasattr(saved, '_xp2_deal_value_writer'):
        saved._xp2_deal_value_writer = deal_value.bind(saved,image_sha256=identity(image)['image_sha256'])
    deal_history.verify_live(saved.backend.core._handle,saved.backend.runtime.read)
    source, request_name, factory = SOURCE, 'MAKE_DEAL', proof['factory']
    demand_spans = ()
    if demand:
        demand_source = _demand_proof()
        if demand_source['image']['sha256']!=identity(image)['image_sha256']:
            raise ValueError('Native demand requires the installed GameCore image')
        source, request_name, factory = DEMAND_SOURCE, 'MAKE_DEMAND', demand_source['factory']
        demand_spans = demand_source['native_spans']
    base, read = saved.backend.core._handle, saved.backend.runtime.read
    spans = list(factory['spans'])
    spans.extend(demand_spans)
    spans.extend(_source(STATEMENT_SOURCE)['native_spans'])
    spans.extend(negotiation['enum_spans'])
    spans.extend(wire['spans'])
    for group in proof['native_spans'].values():
        spans.extend(group)
    for span in spans:
        raw = read(base + span['rva'], span['size'])
        if type(raw) is not bytes or len(raw) != span['size'] or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live native deal draft source changed')
    slots = struct.pack('<8Q', *(base + rva for rva in factory['slots']))
    if read(base + int(factory['vtable_rva'],16), len(slots)) != slots:
        raise ValueError('Native deal factory virtual targets changed')
    return _registered_request(base,read,request_name,factory,source_sha256=source[1])


@contextmanager
def statement_scope(continuation, player_id, target, *, operation=None, demand=False):
    """Allow an acknowledgement or a solicited reply on this request."""
    if getattr(continuation, '_xp2_deal_statement_scope', None) is not None:
        raise RuntimeError('Overlapping native deal request')
    proof = _source(STATEMENT_SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-empty-deal-statement.native-source.v1'
            or (proof['source']['path'], proof['source']['sha256']) != SOURCE
            or proof['wire_player_order'] != 'target-to-local-acknowledgement'):
        raise ValueError('Unknown native deal acknowledgement source')
    if operation not in (None, 'inspect', 'propose', 'accept', 'equalize', 'edit', 'demand'):
        raise ValueError('Unknown deal statement operation')
    if ((operation in ('edit','demand') and not demand)
            or (demand and operation not in (None,'edit','demand','accept'))):
        raise ValueError('Native demand operation crossed the negotiation mode')
    if demand:
        _demand_proof()
        proof = dict(proof,statement_type=gold.DEMAND_STATEMENT)
    continuation._xp2_deal_statement_scope = (player_id, target, proof, operation)
    try:
        yield
    finally:
        del continuation._xp2_deal_statement_scope


def project_statement_fields(fields, scope, *, reply=None):
    """Validate deal extensions in both reads and leave the owned map intact."""
    from .native.native_application_mirror import decode_scalar
    from .native.native_diplomacy_statement import BLOB_KEY, NAMES, OPAQUE_KEY

    if scope is None:
        return fields
    player, target, proof, operation = scope
    keys = proof['extra_keys']
    deal = fields.get(keys['encoded_native_deal'])
    headers = set(NAMES.values()) | {OPAQUE_KEY}
    allowed = headers | set(keys.values())
    if set(fields) not in (allowed, allowed | {BLOB_KEY}):
        raise ValueError('Unknown native deal acknowledgement fields')
    if (type(deal) is not bytes or len(deal) != 24
            or struct.unpack_from('<H', deal)[0] != proof['native_variant_type']
            or struct.unpack_from('<I', deal, 20)[0] != proof['native_variant_flags']):
        raise ValueError('Unknown native deal object variant')
    # The engine's owned argument-map clone handles this value's lifetime.
    # We retain its shape only and never follow the payload address.
    pointer = struct.unpack_from('<Q', deal, 8)[0]
    if not 0x10000 <= pointer < 1 << 47 or pointer % 8:
        raise ValueError('Invalid native deal object address')
    expected = dict(StatementType=proof['statement_type'], FromPlayer=target, ToPlayer=player)
    for name, value in expected.items():
        tag = 2 if name in ('FromPlayer', 'ToPlayer') else 3
        if decode_scalar(fields[NAMES[name]], tag) != value:
            raise ValueError('Native deal acknowledgement differs from the active request')
    subtype, response = (decode_scalar(fields[NAMES[name]], 3)
                         for name in ('StatementSubType','ResponseType'))
    action, responding = (decode_scalar(fields[keys[name]], 3)
                          for name in ('DealAction','RespondingToDealAction'))
    if operation is None:
        if (subtype,response,action,responding) != (proof['subtype'],proof['response_type'],
                proof['deal_action'],proof['responding_to_deal_action']):
            raise ValueError(f'Native deal acknowledgement contains another proposal action {(action,responding,subtype,response)}')
    elif operation == 'accept':
        echo = deal_history.source()['confirmation_echo']
        if (subtype,response,action,responding) != (
                echo['subtype'],echo['response'],echo['deal_action'],echo['responding_to_deal_action']):
            raise ValueError('Native confirmation acknowledgement differs')
        if reply is not None:
            reply.update(operation=operation,outcome='accepted')
    elif operation == 'equalize':
        _, wire = _negotiation_proof()
        signature = wire['fields'].get(str(action))
        if responding != wire['request'] or signature != (subtype,response):
            raise ValueError(f'Unknown native negotiation reply {(action,responding,subtype,response)}')
        if reply is not None:
            reply.update(operation=operation,outcome=wire['outcome'][str(action)])
    elif operation == 'edit':
        raise ValueError('Editing a native demand produced an unsolicited reply')
    else:
        reply_proof = gold.proof()
        disposition = {1:'accepted', 2:'rejected'}.get(action)
        request_code = (_demand_proof()['proposal_code'] if operation=='demand' else
                        reply_proof['proposal_actions']['INSPECT' if operation=='inspect' else 'PROPOSED'])
        if (disposition is None or responding != request_code
                or (subtype,response) != reply_proof['reply_wire'][disposition]):
            raise ValueError(f'Native gold reply differs from the current proposal {(action,responding,subtype,response)}')
        if reply is not None:
            reply.update(operation=operation, outcome=disposition)
    return {key: value for key, value in fields.items() if key not in keys.values()}


def _state_source(statement, player_id, target, turn):
    from .native.native_pending_diplomacy import source

    if type(target) is not int or not 0<=target<64 or target==player_id or type(turn) is not int or turn<0:
        raise ValueError('Invalid native draft query scope')
    session = statement['fields']['SessionID']
    return (b'local function identity()\n' + source(statement,player_id) + b'\nend\nidentity()\n'
         + f'local me,other,sid,turn={player_id},{target},{session},{turn}\n'.encode('ascii') + b"""
assert(Game.GetCurrentGameTurn()==turn and
 DiplomacyManager.FindOpenSessionID(me,other)==sid,'Deal draft session changed')
local details=DiplomacyManager.GetSessionInfo(sid)
-- The statement speaker can be the AI acknowledgement of our session.
assert(details.FromPlayer==me and details.ToPlayer==other,'The deal draft was not initiated here')
local peer=Players[other]
assert(peer and peer:IsAlive() and peer:IsMajor() and peer:IsHuman()==false
 and Players[me]:GetDiplomacy():HasMet(other),'Deal draft lost its met AI counterpart')
assert(DealManager.HasPendingDeal(me,other)==false,'A submitted deal cannot be closed as an empty draft')
local deal=DealManager.GetWorkingDeal(DealDirection.OUTGOING,me,other)
assert(deal~=nil,'Native outgoing deal is absent')
local queued=DiplomacyManager.HasQueuedSession(me)
assert(type(queued)=='boolean','Deal session queue status unavailable')
""")


def inspect_initial_peace(saved):
    b, p, context = saved.backend, saved.prefix, saved._xp2_diplomacy
    active = context.validate(b)
    original = active.pending.statement
    pid, target, turn = saved._xp2_requested_deal
    if active.turn != turn or active.pending.session['statement_type'] != 'MAKE_DEAL':
        raise RuntimeError('Initial peace inspection lost its native session')
    prefix = _state_source(original, pid, target, turn)
    raw = p.runtime.evaluate_text(p.ui_child, prefix + treaty.READ_OPENING, b'@xp2_initial_peace_terms', capacity=64)
    _, terms = treaty.parse_opening(raw)
    ledger = p.deferred_events.pending_diplomacy_statements
    outcome = None
    before = saved.continuation.observation
    context.begin_response(b)
    try:
        with statement_scope(saved.continuation, pid, target, operation='inspect'):
            code = gold.inspect_resource_source(treaty.working_source(prefix), include_borders=True)
            result = p.runtime.evaluate_text(p.ui_child, code, b'@xp2_inspect_initial_peace', capacity=64)
            p.actions.require_empty_native_queue()
            p.deferred_events.drain_empty_receivers()
        if result == b'inspected':
            if len(ledger) != 2 or ledger[0] != original:
                raise RuntimeError('Initial peace inspection did not produce its native reply')
            reply = ledger[1].get('deal_reply', {})
            outcome = reply.get('outcome')
            if (reply.get('operation') != 'inspect' or outcome not in ('accepted', 'rejected')
                    or ledger[1]['fields']['SessionID'] != active.pending.session['session_id']):
                raise RuntimeError('Initial peace inspection returned a foreign reply')
            code = gold.copy_source(prefix + treaty.INVENTORY, 0, requested=(0,0), peace_terms=terms)
            if p.runtime.evaluate_text(p.ui_child, code, b'@xp2_verify_initial_peace_reply', capacity=64) != b'verified':
                raise RuntimeError('Initial peace inspection changed the offered terms')
            saved._xp2_deal_gold_disposition = outcome
            ledger.pop(0)
            p.view_publisher.publish()
        elif result != b'invalid_draft' or ledger != [original]:
            raise RuntimeError('Unexpected native settlement inspection result')
        context.end_response(b)
        if outcome is not None and context.resume(b) != before:
            raise RuntimeError('Initial peace inspection changed the strategic observation')
    except BaseException:
        context.poison(b)
        raise
    saved.emit('native_xp2_major_peace_inspected', player_id=pid, target_player_id=target, turn=turn,
               terms=terms, response=outcome, receipt=result.decode('ascii'))


def read(saved, sequence):
    from .native import native_diplomacy_choices as shared
    from .native.native_episode_identity import require_episode
    from .native.native_player_observation import observe_player
    from .native.native_saved_actions import GAPS, digest
    from .native.native_saved_player_map import observe as observe_map

    b, p = saved.backend, saved.prefix
    context = saved._xp2_diplomacy
    active = context.validate(b)
    event, session = active.pending.statement, active.pending.session
    pid, target, turn = saved._xp2_requested_deal
    demand = getattr(saved,'_xp2_demand',False)
    peace = getattr(saved, '_xp2_major_peace', False)
    statement_type = 'MAKE_DEMAND' if demand else 'MAKE_DEAL'
    reply = event.get('deal_reply', {})
    if (session['statement_type']!=statement_type
            or (session['statement_subtype'] not in ('NONE','AI_ACCEPT_DEAL','AI_REFUSE_DEAL','HUMAN_ACCEPT_DEAL')
                and reply.get('operation')!='equalize')
            or session['player_id']!=pid or {session['from_player'],session['to_player']}!={pid,target}
            or session['is_open'] is not True or turn!=active.turn):
        raise RuntimeError('Native statement is outside the requested outgoing deal draft')
    before=shared._snapshot(b,'before',context)
    disposition=getattr(saved,'_xp2_deal_gold_disposition','none')
    a0 = getattr(p.deferred_events.host,'_a0_family_owner',None)
    profile = getattr(a0,'diplomacy_event_profile',None)
    acceptance_ready = (profile is not None
        and profile.record_types_by_kind.get(deal_history.KIND)==frozenset((deal_history.RECORD,)))
    source = _state_source(event,pid,target,turn)
    live_peace = peace and disposition != 'settled'
    if live_peace:
        source = treaty.working_source(source)
    code = gold.read_source(source,disposition,acceptance_ready=acceptance_ready,recurring=True,
                            bilateral=True,include_resources=True,negotiation=not demand,
                            include_borders=not demand,demand=demand,peace=live_peace)
    raw = p.runtime.evaluate_text(p.ui_child,code,b'@xp2_public_deal_draft',capacity=resources.READ_CAPACITY)
    peace_terms = []
    if live_peace:
        raw, outgoing, incoming = raw.rsplit(b'|',2)
        _, peace_terms = treaty.parse_opening(b'closable|' + outgoing + b'|' + incoming)
    elif peace:
        # GameCore clears the working draft on enactment. Show the terms from
        # the verified transaction while the completed dialogue can still close.
        peace_terms = deepcopy(validate_peace_terms(saved._xp2_settled_peace))
    if demand:
        raw_gold, raw_resources = raw.rsplit(b'|',1)
        queued, *terms = gold.parse(raw_gold,disposition,recurring=True,bilateral=True,demand=True)
        rows = resources.parse(raw_resources)
        if any(row['direction']=='outgoing' and row['amount'] for row in rows):
            raise RuntimeError('Native demand contains outgoing resources')
        resource_rows = [row for row in rows if row['direction']=='incoming']
        border_rows = []
        mode = dict(deal_demand=True)
    else:
        raw_gold, raw_resources, raw_borders = raw.rsplit(b'|',2)
        queued, *terms, can_equalize = gold.parse(raw_gold,disposition,recurring=True,bilateral=True,negotiation=True)
        resource_rows = resources.parse(raw_resources)
        border_rows = validate_open_borders(json.loads(raw_borders))
        mode = dict(deal_equalize=can_equalize,deal_open_borders=border_rows)
        if peace:
            mode['deal_peace'] = peace_terms
    obs=observe_player(p.runtime,p.ui_child,pid)
    player_map=observe_map(p,obs)
    if (obs['player_id'],obs['turn'])!=(pid,turn):
        raise RuntimeError('Native deal draft crossed the active turn')
    identity=require_episode(p)
    choices = gold.offer_choices(queued, *terms, demand=demand)
    can_edit_resources = getattr(saved,'_xp2_deal_value_writer',None) is not None
    terms_closed = disposition=='settled' or (demand and disposition=='rejected')
    choices[-1:-1] = resource_choices(resource_rows,settled=terms_closed,can_edit=can_edit_resources)
    if not demand:
        choices[-1:-1] = open_borders_choices(border_rows,settled=terms_closed)
        choices.insert(-1,(EQUALIZE,not can_equalize))
    item_count = (sum(term['amount']>0 for term in (*terms,*resource_rows))
                  + sum(row['duration'] is not None for row in border_rows) + (len(peace_terms) if live_peace else 0))
    mode.update(deal_resources=resource_rows, **dict(zip(GOLD_TERM_FIELDS.values(),terms)))
    unsupported = [*GAPS, DEAL_OTHER_TERMS_GAP]
    if not can_edit_resources:
        unsupported.append(DEAL_RESOURCE_WRITE_GAP)
    if not acceptance_ready:
        unsupported.append('deal_acceptance_receiver_unavailable')
    template=dict(kind='diplomacy_response',session_id=session['session_id'],
                  statement_sequence=event['event_sequence'])
    offers=[dict(template,choice=key) for key,disabled in choices if not disabled]
    result=dict(schema=shared.SCHEMA,episode_id=identity.episode_id,game_generation=identity.game_generation,
        sequence=sequence,player_id=pid,turn=turn,origin_turn=turn,player_map=player_map,
        statement=deepcopy(event),data=dict(session=deepcopy(session),selections=[
            dict(key=key,sort=index,text=None,tooltip=None,diplomatic_action_type=None,disabled=disabled)
            for index,(key,disabled) in enumerate(choices)],
            deal_draft=dict(target_player_id=target,item_count=item_count,pending=False), **mode),
        candidates=[dict(candidate_id=digest(action),action=action) for action in offers],
        unsupported=unsupported,
        complete_action_space=False)
    result['decision_id']=digest(result)
    context.validate(b)
    if shared._snapshot(b,'after',context)!=before:
        raise RuntimeError('Deal draft query changed the native scheduler')
    b.explicit_observation=deepcopy(obs)
    b.explicit_diplomacy=deepcopy(result)
    fields = dict(player_id=pid,target_player_id=target,turn=turn,
                  session_id=session['session_id'],statement_sequence=event['event_sequence'])
    if peace:
        saved.emit('native_xp2_major_peace_draft_observed', terms=peace_terms, response=disposition, **fields)
    else:
        saved.emit('native_xp2_deal_draft_observed', **fields,
                   gold_terms=terms[0],recurring_gold_terms=terms[1],
                   requested_gold_terms=terms[2],requested_recurring_gold_terms=terms[3],
                   resource_terms=resource_rows,open_borders=border_rows)
    return obs,result


def apply_gold(saved, action):
    from .native.native_player_observation import observe_player

    b, p, context = saved.backend, saved.prefix, saved._xp2_diplomacy
    old = b.explicit_diplomacy
    observation, current = read(saved, old['sequence'])
    data = current['data']
    peace_terms = data.get('deal_peace', ())
    demand = data.get('deal_demand') is True
    choice = action['choice']
    template = {key: value for key, value in action.items() if key not in ('amount','resource_index')}
    if current != old or template not in [row['action'] for row in current['candidates']]:
        raise ValueError('Stale or unavailable native gold choice')
    pid,target,turn = saved._xp2_requested_deal
    prefix = _state_source(current['statement'], pid, target, turn)
    if peace_terms:
        prefix = treaty.working_source(prefix)
    amounts = {key: data[field]['amount'] for key, field in GOLD_TERM_FIELDS.items()}
    active_resources = {(row['direction'],row['resource_index']): row
                        for row in data['deal_resources'] if row['amount']>0}
    active_borders = {row['direction']:row for row in data.get('deal_open_borders',()) if row['duration'] is not None}
    resource_index_to_write = None
    if choice in GOLD_TERM_FIELDS:
        term = data[GOLD_TERM_FIELDS[choice]]
        requested = action['amount']
        if type(requested) is not int or not 0 <= requested <= term['max_amount'] or requested == term['amount']:
            raise ValueError('Invalid gold amount at the active choice')
        verb = 'edit' if demand else 'inspect'
        code = gold.edit_source(prefix, requested, recurring=True, bilateral=True,
            edit_recurring=choice in (SET_RECURRING_GOLD, SET_REQUESTED_RECURRING_GOLD),
            edit_requested=choice in (SET_REQUESTED_GOLD, SET_REQUESTED_RECURRING_GOLD),
            include_resources=True,include_borders=not demand,inspect=not demand)
        amounts[choice] = requested
    elif choice in RESOURCE_CHOICES:
        writer = getattr(saved,'_xp2_deal_value_writer',None)
        if writer is None:
            raise ValueError('Native resource type writer is unavailable')
        selected = resolve_resource(data['deal_resources'],choice,
                                    {key:action[key] for key in ('resource_index','amount')})
        verb = 'edit' if demand else 'inspect'
        key = (RESOURCE_CHOICES[choice],selected['resource_index'])
        if selected['amount']>0 and key not in active_resources:
            resource_index_to_write = selected['resource_index']
        code = gold.resource_edit_source(prefix,choice,selected['resource_index'],selected['amount'],
                                         stage_only=resource_index_to_write is not None,
                                         include_borders=not demand,inspect=not demand)
        if selected['amount']==0:
            del active_resources[key]
        else:
            term = next(row for row in data['deal_resources'] if (row['direction'],row['resource_index'])==key)
            duration = term['duration']
            if duration is None:
                duration = resources.draft_duration(p,pid,turn,term['resource_index'])
            active_resources[key] = dict(term,amount=selected['amount'],duration=duration)
    elif choice in OPEN_BORDERS_CHOICES and set(action) == set(template):
        direction, remove = OPEN_BORDERS_CHOICES[choice]
        verb = 'inspect'
        code = gold.border_edit_source(prefix, direction, remove)
        if remove:
            del active_borders[direction]
        else:
            row = next(row for row in data['deal_open_borders'] if row['direction']==direction)
            active_borders[direction] = dict(row,duration=row['available_duration'],available_duration=None)
    elif choice == FINALIZE and set(action) == set(template):
        verb = data['deal_gold']['finalize']
        if peace_terms:
            if verb != 'accept':
                raise ValueError('Native peace confirmation requires acceptance of matching working deals')
            prefix += b"assert(Players[me]:GetDiplomacy():IsAtWarWith(other)==true,'Peace requires a native war')\n"
        code = gold.finalize_source(prefix, verb, recurring=True,bilateral=True,
                                    include_resources=True,include_borders=not demand)
    elif choice == EQUALIZE and set(action) == set(template):
        verb = 'equalize'
        code = gold.equalize_source(prefix, data['deal_gold']['response'],include_borders=True)
    else:
        raise ValueError('Unknown native gold command')

    previous_statement = current['statement']
    ledger = p.deferred_events.pending_diplomacy_statements
    amount, per_turn = amounts[SET_GOLD], amounts[SET_RECURRING_GOLD]
    incoming, incoming_per_turn = amounts[SET_REQUESTED_GOLD], amounts[SET_REQUESTED_RECURRING_GOLD]
    requested = (incoming, incoming_per_turn)
    resource_terms = tuple(active_resources.values())
    border_terms = tuple(active_borders.values())
    rights_before = borders.read_rights(p,pid,turn,target) if verb=='accept' and border_terms else None
    rights_after = None
    may_settle = verb in ('accept','demand')
    active_before = (counterparty_terms(p, pid, turn, target)
                     if may_settle and (per_turn or incoming_per_turn or resource_terms) else None)
    stock_delta = {}
    if may_settle:
        for row in resource_terms:
            if row['duration']==0:
                index = row['resource_index']
                stock_delta[index] = stock_delta.get(index,0) + (1 if row['direction']=='incoming' else -1)*row['amount']
    stock_before = resources.stockpile(p,pid,turn,sorted(stock_delta))
    stock_after = {}
    refusal = None
    accepted = False
    demand_reply = None
    archive_reply = None

    def accept_native(request):
        with statement_scope(saved.continuation, pid, target, operation='accept', demand=demand):
            result = p.runtime.evaluate_text(p.ui_child,request,b'@xp2_native_accept_gold_deal',capacity=64)
            if result == b'sent':
                gold.deliver_acceptance(p.actions, pid, target, action['session_id'], amount, per_turn,
                                        requested=requested,resource_terms=resource_terms,border_terms=border_terms,
                                        demand=demand,peace_terms=peace_terms)
            p.actions.require_empty_native_queue()
            p.deferred_events.drain_empty_receivers()
        return result

    context.begin_response(b)
    try:
        if verb == 'accept':
            raw = accept_native(code)
            accepted = raw == b'sent'
        else:
            with statement_scope(saved.continuation, pid, target, operation=verb, demand=demand):
                if resource_index_to_write is not None:
                    raw, calls = writer.evaluate(code,resource_index_to_write)
                    saved.emit('native_xp2_deal_resource_type_write_observed',player_id=pid,target_player_id=target,
                               resource_index=resource_index_to_write,callbacks=calls,receipt=raw.decode('ascii'))
                    if raw == b'edited':
                        validation = (gold.validate_demand_source(prefix) if demand else
                                      gold.inspect_resource_source(prefix,include_borders=True))
                        raw = p.runtime.evaluate_text(p.ui_child,validation,
                                                      b'@xp2_native_inspect_resource_deal',capacity=64)
                else:
                    raw = p.runtime.evaluate_text(p.ui_child,code,b'@xp2_native_gold_deal',capacity=64)
                if verb=='demand' and raw==b'sent' and p.actions.pending:
                    archive_reply = gold.deliver_demand_reply(p.actions,pid,target,requested,resource_terms)
                p.actions.require_empty_native_queue()
                p.deferred_events.drain_empty_receivers()
        if raw not in (b'unavailable', b'removed', b'edited', b'invalid_draft', b'inspected', b'sent'):
            raise RuntimeError('Native gold command returned an unknown result')
        if not ledger or ledger[0] != previous_statement or len(ledger) > 2:
            raise RuntimeError('Native gold command crossed its statement ledger')
        changed_statement = len(ledger) == 2
        if raw == b'unavailable':
            if changed_statement:
                raise RuntimeError('Native refusal produced a new gold statement')
            refusal = 'native_gold_choice_unavailable'
        elif changed_statement:
            reply = ledger[1].get('deal_reply')
            fields = ledger[1]['fields']
            if (raw not in (b'inspected', b'sent') or type(reply) is not dict
                    or reply['operation'] != verb or fields['SessionID'] != action['session_id']):
                raise RuntimeError('Native gold response belongs to another command or session')
            if verb != 'accept':
                copy_code = (gold.copy_adjusted_source(prefix,include_borders=True,peace_terms=peace_terms)
                             if reply['outcome']=='adjusted' else
                             gold.copy_source(prefix, amount, per_turn, requested=requested,
                                              resource_terms=resource_terms,border_terms=border_terms,
                                              peace_terms=peace_terms))
                if p.runtime.evaluate_text(p.ui_child,copy_code,b'@xp2_gold_reply_terms',capacity=64)!=b'verified':
                    raise RuntimeError('Native incoming gold readback differs')
                saved._xp2_deal_gold_disposition = reply['outcome']
            ledger.pop(0)
            if verb == 'demand':
                demand_reply = reply['outcome']
                if archive_reply is not None and archive_reply!=demand_reply:
                    raise RuntimeError('Native demand archive and diplomatic reply disagree')
                if demand_reply == 'accepted':
                    if archive_reply is None:
                        # A statement without a transaction uses the official confirmation.
                        response = ledger[0]
                        confirmation = gold.finalize_source(_state_source(response,pid,target,turn),'accept',
                            recurring=True,bilateral=True,include_resources=True)
                        if accept_native(confirmation) != b'sent' or not ledger or ledger[0] != response or len(ledger)>2:
                            raise RuntimeError('Native demand acceptance did not join the solicited reply')
                        if len(ledger)==2:
                            echo = ledger[1]
                            if (echo.get('deal_reply') != dict(operation='accept',outcome='accepted')
                                    or echo['fields']['SessionID'] != action['session_id']):
                                raise RuntimeError('Native demand confirmation returned another session')
                            ledger.pop(0)
                    # The accepted LAN archive already applies the transaction.
                    # The common readback below verifies its native effect.
                    accepted = True
        elif raw == b'sent' and verb=='demand' and archive_reply=='rejected':
            # A delivered rejection archive can resolve without a new UI statement.
            demand_reply = archive_reply
            saved._xp2_deal_gold_disposition = demand_reply
        elif raw == b'sent' and verb != 'accept':
            raise RuntimeError('Native deal request produced no correlated AI reply')
        elif verb != 'accept':
            saved._xp2_deal_gold_disposition = 'none'
        if accepted:
            check = (f"local open=DiplomacyManager.IsSessionIDOpen({action['session_id']})\n"
                     f"assert(type(open)=='boolean' and DealManager.HasPendingDeal({pid},{target})==false,"
                     "'Native gold acceptance left an unknown session')\n"
                     "return open and 'open' or 'closed'").encode('ascii')
            closure = p.runtime.evaluate_text(p.ui_child,check,b'@xp2_gold_acceptance_state',capacity=64)
            if closure not in (b'closed', b'open'):
                raise RuntimeError('Unknown native gold acceptance closure')
            if closure == b'closed':
                ledger.pop(0)
            else:
                saved._xp2_deal_gold_disposition = 'settled'
        p.view_publisher.publish()
        context.end_response(b)
        after = context.resume(b) if changed_statement or not ledger else observe_player(p.runtime,p.ui_child,pid)
        if (after['player_id'], after['turn']) != (pid,turn):
            raise RuntimeError('Native gold action crossed the actor turn')
        if accepted:
            if after['economy']['gold'] - observation['economy']['gold'] != incoming - amount:
                raise RuntimeError('GameCore did not transfer the accepted net lump-sum gold amount')
            if active_before is not None:
                active_after = counterparty_terms(p, pid, turn, target)
                expected_terms = []
                for direction, rate in (('outgoing',per_turn), ('incoming',incoming_per_turn)):
                    if rate:
                        expected_terms.append(dict(direction=direction,kind='gold',amount=rate,
                                                   remaining_turns=gold.RECURRING_DURATION,resource_index=None))
                expected_terms.extend(dict(direction=row['direction'],kind='resource',amount=row['amount'],
                                           remaining_turns=row['duration'],resource_index=row['resource_index'])
                                      for row in resource_terms if row['duration']>0)
                for term in expected_terms:
                    if active_after.count(term) != active_before.count(term)+1:
                        raise RuntimeError('GameCore did not enact the accepted recurring deal term')
            stock_after = resources.stockpile(p,pid,turn,sorted(stock_delta))
            if any(stock_after[index]-stock_before[index] != change for index,change in stock_delta.items()):
                raise RuntimeError('GameCore did not transfer the accepted one-time resource quantity')
            if rights_before is not None:
                rights_after = borders.read_rights(p,pid,turn,target)
                if any(rights_after[row['direction']] is not True for row in border_terms):
                    raise RuntimeError('GameCore did not grant the accepted open-borders rights')
            if peace_terms:
                from .xp2_world_war import _read_state
                if _read_state(p,pid,turn,target)['at_war'] is not False:
                    raise RuntimeError('GameCore did not end the war after the accepted peace terms')
                if ledger:
                    saved._xp2_settled_peace = deepcopy(peace_terms)
                saved.emit('native_xp2_major_peace_enacted', player_id=pid,target_player_id=target,
                           turn=turn, terms=peace_terms, at_war_before=True, at_war_after=False)
            if not ledger:
                del saved._xp2_requested_deal
                if demand:
                    del saved._xp2_demand
                if peace_terms:
                    del saved._xp2_major_peace
                if hasattr(saved,'_xp2_deal_gold_disposition'):
                    del saved._xp2_deal_gold_disposition
        elif after != observation:
            raise RuntimeError('Draft modification changed the strategic player observation')
    except BaseException:
        context.poison(b)
        raise
    saved.emit('native_xp2_gold_deal_command_observed', player_id=pid,target_player_id=target,turn=turn,
               verb=verb,amount=amount,amount_per_turn=per_turn,receipt=raw.decode('ascii'),refusal=refusal,
               requested_amount=incoming,requested_amount_per_turn=incoming_per_turn,
               resource_terms=resource_terms,stock_before=stock_before,stock_after=stock_after,
               border_terms=border_terms,border_rights_before=rights_before,border_rights_after=rights_after,
               peace_terms=peace_terms,
               demand_reply=demand_reply,demand_archive_reply=archive_reply,accepted=accepted,
               ai_disposition=getattr(saved,'_xp2_deal_gold_disposition',None),
               gold_before=observation['economy']['gold'],gold_after=after['economy']['gold'])
    return dict(status='refused' if refusal else 'completed', reason=refusal,
                requested_action=deepcopy(action), observation=after)


def close(saved, action):
    from .native.native_diplomacy_choices import deliver_response

    b, p, context = saved.backend, saved.prefix, saved._xp2_diplomacy
    old=b.explicit_diplomacy
    _, current=read(saved,old['sequence'])
    if current!=old or action not in [r['action'] for r in current['candidates']]:
        raise ValueError('Stale or unavailable native deal draft close')
    sid=action['session_id']
    pid,target,turn=saved._xp2_requested_deal
    code=(f'assert(DiplomacyManager.FindOpenSessionID({pid},{target})=={sid} and '
          f'DiplomacyManager.HasQueuedSession({pid})==false,"Deal changed before close")\n'
          f'assert(DiplomacyManager.CloseSession({sid})==true,"Native deal close refused")\n'
          'return "closed"').encode('ascii')
    context.begin_response(b)
    try:
        if p.runtime.evaluate_text(p.ui_child,code,b'@xp2_close_deal_draft',capacity=64)!=b'closed':
            raise RuntimeError('Native deal close response differs')
        deliver_response(p.actions,'CHOICE_EXIT')
        ledger=p.deferred_events.pending_diplomacy_statements
        if ledger!=[current['statement']]:
            raise RuntimeError('Deal draft close changed the ledger identity')
        ledger.pop(0)
        p.deferred_events.drain_empty_receivers()
        p.view_publisher.publish()
        check=(f'assert(DiplomacyManager.IsSessionIDOpen({sid})==false and '
               f'DealManager.HasPendingDeal({pid},{target})==false,"Deal did not close")\n'
               'return "verified"').encode('ascii')
        if p.runtime.evaluate_text(p.ui_child,check,b'@xp2_deal_draft_close_readback',capacity=64)!=b'verified':
            raise RuntimeError('GameCore did not close the deal draft')
        context.end_response(b)
        observation=context.resume(b)
    except BaseException:
        context.poison(b)
        raise
    del saved._xp2_requested_deal
    if getattr(saved,'_xp2_demand',False):
        del saved._xp2_demand
    if getattr(saved, '_xp2_major_peace', False):
        del saved._xp2_major_peace
        if hasattr(saved, '_xp2_settled_peace'):
            del saved._xp2_settled_peace
    if hasattr(saved,'_xp2_deal_gold_disposition'):
        del saved._xp2_deal_gold_disposition
    if context.pending is not None:
        raise RuntimeError('Close produced a new unqualified deal statement')
    saved.emit('native_xp2_deal_draft_closed', player_id=pid,target_player_id=target,turn=turn,
               session_id=sid,session_open=False,pending_deal=False)
    return dict(status='completed',reason=None,requested_action=deepcopy(action),observation=observation,
                pending_statement_retained=False,game_update_called=False,automatic_response=False)

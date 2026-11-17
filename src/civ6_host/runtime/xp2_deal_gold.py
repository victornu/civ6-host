"""Native lump-sum and recurring gold terms in a locally opened XP2 AI deal."""

from hashlib import sha256
from pathlib import Path
import struct

from civ6_host.contracts.diplomacy_decisions import FINALIZE, GOLD_TERM_FIELDS

from .configuration_profiles import _source
from .execution_images import identity
from .paths import resource_root
from .resource_resolution import resolve_path
from . import xp2_deal_resources as resources
from . import xp2_deal_open_borders as borders
from . import xp2_deal_peace as treaty


SOURCE = ('evidence/host-xp2-deal-gold-source-v2.json',
          'd04fa8781b19a2ac672febd0cd1370dcfece141d9f16fa128cec3f28663c7d74')
ACCEPT_SOURCE = ('evidence/host-xp2-deal-gold-acceptance-archive-source.json',
                 '7bb647c509ba4ece46e3ad6b7e445ca6b8caa93c2b6701eaac7846128d4f33f6')
RECURRING_SOURCE = ('evidence/host-xp2-deal-recurring-gold-source.json',
                    '716cb23b7051eac8cd54c6570f878dd73298c35774f00f1946423262c389e444')
BILATERAL_SOURCE = ('evidence/host-xp2-deal-bilateral-gold-source.json',
                    '296cda7983d5c960c9109100fa20c7d8adb20e507d8ccd12559a95fac12d7a4b')
RECURRING_DURATION = 30
DEMAND_STATEMENT = 0x134ca13e


def proof():
    value = _source(SOURCE)
    if (value['schema'] != 'civ6-host.xp2-deal-gold.static.v1'
            or value['native_execution'] is not False
            or value['proposal_actions'] != {
                'ACCEPTED': 1, 'REJECTED': 2, 'PROPOSED': 4, 'INSPECT': 7, 'PENDING': 9}):
        raise ValueError('Invalid native gold deal source')
    return value


def _recurring_proof():
    value = _source(RECURRING_SOURCE)
    if (value['schema'] != 'civ6-host.xp2-recurring-gold.static.v1'
            or (value['parent']['path'], value['parent']['sha256']) != SOURCE
            or value['native_execution'] is not False or value['duration'] != RECURRING_DURATION):
        raise ValueError('Invalid recurring gold source')
    return value


def dependencies(image):
    source = proof()
    image_info = identity(image)
    if (source['image']['sha256'] != image_info['image_sha256']
            or Path(source['image']['path']).resolve() != Path(image_info['path']).resolve()):
        raise ValueError('Lump-sum gold deal requires its exact installed image')
    path = resolve_path(Path(source['ui']['path']))
    if sha256(path.read_bytes()).hexdigest() != source['ui']['sha256']:
        raise ValueError('Official gold deal controls changed')
    acceptance = _source(ACCEPT_SOURCE)
    if (acceptance['schema'] != 'civ6-host.xp2-gold-acceptance-archives.v1'
            or (acceptance['parent']['path'],acceptance['parent']['sha256']) != SOURCE):
        raise ValueError('Gold acceptance archive source differs')
    if _recurring_proof()['image_sha256'] != image_info['image_sha256']:
        raise ValueError('Recurring gold requires its exact installed image')
    bilateral = _source(BILATERAL_SOURCE)
    if (bilateral['schema'] != 'civ6-host.xp2-bilateral-gold.static.v1'
            or (bilateral['parent']['path'], bilateral['parent']['sha256']) != SOURCE
            or bilateral['image_sha256'] != image_info['image_sha256']
            or bilateral['ui_sha256'] != source['ui']['sha256']
            or tuple(bilateral['inventories']) != ('local_player', 'counterparty')
            or bilateral['native_execution'] is not False):
        raise ValueError('Native counterparty gold controls changed')
    return {str(resolve_path(resource_root() / name)): digest
            for name,digest in (SOURCE, ACCEPT_SOURCE, RECURRING_SOURCE, BILATERAL_SOURCE)}


def verify(saved, image):
    dependencies(image)
    source = proof()
    base, read = saved.backend.core._handle, saved.backend.runtime.read
    spans = (*source['native_spans'], *(s for rows in source['bindings'].values() for s in rows),
             *_recurring_proof()['native_spans'])
    for span in spans:
        data = read(base + span['rva'], span['size'])
        if type(data) is not bytes or len(data) != span['size'] or sha256(data).hexdigest() != span['sha256']:
            raise ValueError('Live native gold deal source changed')


_ITEM = b"""
local GOLD,NONE=DealItemTypes.GOLD,DealItemSubTypes.NONE
local function u31(n)
 return type(n)=='number' and n%1==0 and n>=0 and n<=2147483647
end
local count=resourceCount+borderCount+treatyCount
local function inventory(giver,receiver)
 local lump,rate={amount=0,maximum=0},{amount=0,maximum=0}
 local rows=deal:FindItemsByType(GOLD,NONE,giver) or {}
 assert(type(rows)=='table' and #rows<=1+(recurringDuration>0 and 1 or 0),'Invalid native gold inventory')
 count=count+#rows
 for _,item in ipairs(rows) do
  local duration=item:GetDuration()
  local term=duration==0 and lump or (recurringDuration>0 and duration==recurringDuration and rate or nil)
  assert(term and term.item==nil,'Unqualified or duplicate gold term')
  term.item,term.amount,term.maximum=item,item:GetAmount(),item:GetMaxAmount()
 end
 if lump.item==nil or (recurringDuration>0 and rate.item==nil) then
  local choices=DealManager.GetPossibleDealItems(giver,receiver,GOLD,deal) or {}
  assert(type(choices)=='table' and #choices<=2,'Invalid native gold quotes')
  for _,entry in ipairs(choices) do
   assert(u31(entry.Duration),'Invalid native gold quote duration')
   if lump.item==nil and entry.Duration==0 then
    lump.maximum=math.floor(Players[giver]:GetTreasury():GetGoldBalance())
   elseif recurringDuration>0 and rate.item==nil and entry.Duration>0 then
    rate.maximum=entry.MaxAmount
   end
  end
 end
 for _,term in ipairs({lump,rate}) do
  assert(u31(term.amount) and u31(term.maximum) and term.maximum>=term.amount,'Invalid native amount or limit')
 end
 return lump,rate
end
local give,giveRate=inventory(me,other)
local want,wantRate
if bilateral then want,wantRate=inventory(other,me) end
assert(count==deal:GetItemCount(),'The draft contains unqualified items')
"""


_SEND = b"""
assert(DealProposalAction.ACCEPTED==1 and DealProposalAction.REJECTED==2 and
 DealProposalAction.PROPOSED==4 and DealProposalAction.INSPECT==7,
 'Native deal action enum changed')
"""

_INSPECT = b"""
deal:Validate()
if deal:IsValid()~=true then return 'invalid_draft' end
assert(DealManager.SendWorkingDeal(DealProposalAction.INSPECT,me,other)==1,
 'Native deal inspection refused')
return 'inspected'
"""

_NEGOTIATION = b"""
assert(DealProposalAction.ADJUSTED==3 and DealProposalAction.EQUALIZE==6
 and DealProposalAction.EQUALIZE_FAILED==10,'Native deal negotiation enum changed')
local fromLocal=deal:GetItemCount(me,other)
local fromOther=deal:GetItemCount(other,me)
-- Each locked peace agreement appears in both directional counts.
assert(u31(fromLocal) and u31(fromOther) and fromLocal+fromOther==count+treatyCount,
 'Native deal negotiation directions differ')
local valid=count>0 and deal:IsValid()==true and deal:HasUnacceptableItems()==false
local function canEqualize(response)
 if not valid or response=='settled' or response=='equalize_failed' then return false end
 if fromLocal>0 and fromOther==0 then return true end
 if deal:IsGift() and fromOther>0 then return false end
 if fromLocal==0 then return fromOther>0 end
 return response~='accepted' and response~='adjusted'
end
"""


def _items(prefix, recurring, bilateral, include_resources=False, include_borders=False):
    if bilateral and not recurring:
        raise ValueError('Bilateral gold requires recurring term support')
    options = f'\nlocal recurringDuration,bilateral={RECURRING_DURATION if recurring else 0},{str(bilateral).lower()}\n'
    inventory = resources.INVENTORIES if include_resources else b'\nlocal resourceCount=0\n'
    agreements = borders.INVENTORY if include_borders else b'\nlocal borderCount=0\n'
    return b'local treatyCount=0\n' + prefix + inventory + agreements + options.encode('ascii') + _ITEM


def read_source(prefix, response, *, acceptance_ready, recurring=False, bilateral=False, include_resources=False,
                negotiation=False, include_borders=False, demand=False, peace=False):
    responses = ('none', 'accepted', 'rejected', 'settled')
    if negotiation:
        responses += ('adjusted', 'equalize_failed')
    if response not in responses or type(acceptance_ready) is not bool:
        raise ValueError('Unknown gold deal disposition')
    suffix = b',giveRate.amount,giveRate.maximum' if recurring else b''
    if bilateral:
        suffix += b',want.amount,want.maximum,wantRate.amount,wantRate.maximum'
    if negotiation:
        suffix += b",canEqualize(response) and 'equalize' or 'fixed'"
    if include_resources:
        suffix += b',publicResourceTerms()'
    if include_borders:
        suffix += b',borderTerms()'
    if peace:
        suffix += b',peaceOut,peaceIn'
    source = _items(prefix, recurring, bilateral, include_resources, include_borders)
    if negotiation:
        source += _NEGOTIATION
    source += f"\nlocal response='{response}'\nlocal canAccept={str(acceptance_ready).lower()}\n".encode('ascii')
    source += b"\nlocal canPropose=response=='none'\n"
    if peace:
        source += b'canPropose=false\n'
    if demand:
        source += b"""
assert(give.amount==0 and giveRate.amount==0 and deal:GetItemCount(me,other)==0,'Demand contains outgoing terms')
give.maximum,giveRate.maximum=0,0
canPropose=canPropose and canAccept
"""
        version = b"demand"
    else:
        version = b"propose"
    return source + b"""
local finalize='none'
if count>0 and deal:IsValid()==true and deal:HasUnacceptableItems()==false then
 if canPropose then
  finalize='""" + version + b"""'
 elseif (response=='accepted' or response=='adjusted') and canAccept
  and DealManager.AreWorkingDealsEqual(me,other)==true then
  finalize='accept'
 end
end
return table.concat({queued and 'queued' or 'closable',give.amount,give.maximum,finalize""" + suffix + b"},'|')\n"


def parse(raw, response, *, recurring=False, bilateral=False, negotiation=False, demand=False):
    if type(raw) is not bytes or len(raw) > 128:
        raise ValueError('Unbounded native gold deal result')
    closure, amount, maximum, finalize, *quote = raw.decode('ascii').split('|')
    finalizers = ('none','demand') if demand else ('none','propose','accept')
    if closure not in ('queued', 'closable') or finalize not in finalizers:
        raise ValueError('Unknown native gold deal result')
    if negotiation:
        if not quote or quote[-1] not in ('equalize', 'fixed'):
            raise ValueError('Unknown deal negotiation availability')
        can_equalize = quote.pop() == 'equalize'
    def term(values, *, per_turn=False):
        amount, maximum = map(int, values)
        if not 0 <= amount <= maximum <= 0x7fffffff:
            raise ValueError('Invalid native gold term limit')
        state = dict(amount=amount, max_amount=maximum)
        if per_turn:
            state['duration'] = RECURRING_DURATION
        return state

    if len(quote) != 2*int(recurring) + 4*int(bilateral):
        raise ValueError('Unexpected native gold inventory shape')
    lump = dict(term((amount,maximum)), response=response, finalize=None if finalize=='none' else finalize)
    states = [lump]
    if recurring:
        states.append(term(quote[:2], per_turn=True))
    if bilateral:
        states.extend((term(quote[2:4]), term(quote[4:6], per_turn=True)))
    return (closure == 'queued', *states, can_equalize) if negotiation else (closure == 'queued', *states)


def edit_source(prefix, amount, *, recurring=False, edit_recurring=False, bilateral=False, edit_requested=False,
                include_resources=False, include_borders=False, inspect=True):
    if type(amount) is not int or not 0 <= amount <= 0x7fffffff:
        raise ValueError('Gold amount is outside the native integer domain')
    if (edit_recurring and not recurring) or (edit_requested and not bilateral):
        raise ValueError('Gold edit requires its source')
    giver, name = ('other', 'want') if edit_requested else ('me', 'give')
    if edit_recurring:
        name += 'Rate'
    duration = 'recurringDuration' if edit_recurring else '0'
    select = f'\nlocal term,giver,duration,requested={name},{giver},{duration},{amount}\n'
    tail = _INSPECT if inspect else b"deal:Validate()\nreturn 'edited'\n"
    return _items(prefix, recurring, bilateral, include_resources, include_borders) + _SEND + select.encode('ascii') + b"""
if requested==term.amount or requested>term.maximum then return 'unavailable' end
local item=term.item
if requested==0 then
 assert(item~=nil,'No gold item to remove')
 deal:RemoveItemByID(item:GetID())
 assert(deal:GetItemCount()==count-1,'Native gold removal did not apply')
 if count==1 then return 'removed' end
else
 local created=item==nil
 if created then
  item=deal:AddItemOfType(GOLD,giver)
  if item==nil then return 'unavailable' end
  item:SetDuration(duration)
 end
 if not u31(item:GetMaxAmount()) or requested>item:GetMaxAmount() then
  if created then
   deal:RemoveItemByID(item:GetID())
   assert(deal:GetItemCount()==count,'Native rejected gold item was not removed')
  end
  return 'unavailable'
 end
 item:SetAmount(requested)
 assert(deal:GetItemCount()==count+(created and 1 or 0) and item:GetDuration()==duration and
  item:GetAmount()==requested,'Native gold change did not apply')
end
""" + tail


def resource_edit_source(prefix, choice, index, amount, *, stage_only=False, include_borders=False, inspect=True):
    tail = b"return 'edited'\n" if stage_only else _INSPECT if inspect else b"deal:Validate()\nreturn 'edited'\n"
    return _items(prefix, True, True, True, include_borders) + _SEND + resources.edit_source(choice,index,amount) + tail


def inspect_resource_source(prefix, *, include_borders=False):
    return _items(prefix, True, True, True, include_borders) + _SEND + _INSPECT


def validate_demand_source(prefix):
    return _items(prefix, True, True, True) + b"deal:Validate()\nreturn 'edited'\n"


def border_edit_source(prefix, direction, remove):
    return _items(prefix, True, True, True, True) + _SEND + borders.edit_source(direction,remove) + _INSPECT


def equalize_source(prefix, response, *, include_borders=False):
    if response not in ('none', 'accepted', 'rejected', 'adjusted'):
        raise ValueError('Unavailable native deal negotiation')
    check = f"\nif not canEqualize('{response}') then return 'unavailable' end\n".encode('ascii')
    return _items(prefix, True, True, True, include_borders) + _NEGOTIATION + check + b"""
if DealManager.SendWorkingDeal(DealProposalAction.EQUALIZE,me,other)~=1 then return 'unavailable' end
return 'sent'
"""


def copy_adjusted_source(prefix, *, include_borders=False, peace_terms=()):
    incoming = prefix + b"""
deal=DealManager.GetWorkingDeal(DealDirection.INCOMING,me,other)
assert(deal~=nil,'Native adjusted deal is absent')
"""
    if peace_terms:
        incoming += treaty.compare_source(peace_terms, 'deal')
    return _items(incoming, True, True, True, include_borders) + b"""
-- ADJUSTED describes the reply, even when the resulting draft is not valid.
DealManager.CopyIncomingToOutgoingWorkingDeal(me,other)
assert(DealManager.AreWorkingDealsEqual(me,other)==true,'GameCore did not copy the adjusted terms')
local copied=DealManager.GetWorkingDeal(DealDirection.OUTGOING,me,other)
assert(copied and copied:GetItemCount()==count,'Native adjusted copy changed the item count')
if count>0 then copied:Validate() end
return 'verified'
"""


def finalize_source(prefix, verb, *, recurring=False, bilateral=False, include_resources=False, include_borders=False):
    if verb not in ('propose','accept','demand'):
        raise ValueError('Unknown final gold deal operation')
    check = (b"assert(DealManager.AreWorkingDealsEqual(me,other)==true,'Native gold terms differ')\n"
             if verb=='accept' else b'')
    suffix = {'accept':b'ACCEPTED','propose':b'PROPOSED','demand':b'DEMANDED'}[verb]
    demand_check = (b"assert(DealProposalAction.DEMANDED==5 and deal:GetItemCount(me,other)==0,"
                    b"'Native demand action or ownership differs')\n") if verb=='demand' else b''
    return _items(prefix, recurring, bilateral, include_resources, include_borders) + _SEND + b"""
if count==0 or deal:IsValid()~=true or deal:HasUnacceptableItems()~=false
then return 'unavailable' end
""" + demand_check + check + b'if DealManager.SendWorkingDeal(DealProposalAction.' + suffix + b""",me,other)~=1
then return 'unavailable' end
return 'sent'
"""


def copy_source(prefix, amount, per_turn=0, *, requested=None, resource_terms=(), border_terms=(), peace_terms=()):
    sides = [('me', (amount, per_turn))]
    if requested is not None:
        sides.append(('other', requested))
    if any(type(n) is not int or not 0 <= n <= 0x7fffffff for _, terms in sides for n in terms):
        raise ValueError('Invalid expected gold terms')
    count = sum(n>0 for _, terms in sides for n in terms) + len(resource_terms) + len(border_terms) + len(peace_terms)
    rows = ','.join(f'[{actor}]={{[0]={lump},[{RECURRING_DURATION}]={rate}}}' for actor, (lump,rate) in sides)
    expected = f'\nlocal expected,count={{{rows}}},{count}\n'
    verify_resources = b''
    if resource_terms:
        by_side = dict(me=[],other=[])
        for row in resource_terms:
            index, amount, duration = (row[k] for k in ('resource_index','amount','duration'))
            if any(type(n) is not int or not 0 <= n <= 0x7fffffff for n in (index,amount,duration)):
                raise ValueError('Invalid expected resource term')
            side = 'me' if row['direction']=='outgoing' else 'other'
            by_side[side].append(f'[{index}]={{{amount},{duration}}}')
        literal = ','.join(f'[{side}]={{{",".join(items)}}}' for side,items in by_side.items())
        verify_resources = f'local resources={{{literal}}}\n'.encode('ascii') + b"""
for giver,terms in pairs(resources) do
 local items=inbound:FindItemsByType(DealItemTypes.RESOURCES,DealItemSubTypes.NONE,giver) or {}
 assert(type(items)=='table' and #items<=256,'Malformed AI resource terms')
 for _,term in ipairs(items) do
  local index=term:GetValueType()
  local wanted=terms[index]
  assert(wanted and wanted[1]==term:GetAmount() and wanted[2]==term:GetDuration() and
   inbound:GetItemParent(term)==nil,'AI changed the proposed resource term')
  terms[index]=nil
  verified=verified+1
 end
end
"""
    verify_borders = borders.verify_copy_source(border_terms) if border_terms else b''
    verify_peace = treaty.verify_copy_source(peace_terms) if peace_terms else b''
    return prefix + expected.encode('ascii') + b"""
local inbound=DealManager.GetWorkingDeal(DealDirection.INCOMING,me,other)
assert(inbound~=nil and inbound:GetItemCount()==count,'AI response changed the scope of the deal')
local verified=0
for giver,terms in pairs(expected) do
 local items=inbound:FindItemsByType(DealItemTypes.GOLD,DealItemSubTypes.NONE,giver) or {}
 assert(type(items)=='table' and #items<=2,'AI changed a proposed gold item')
 for _,term in ipairs(items) do
  local duration=term:GetDuration()
  assert(terms[duration] and terms[duration]>0 and term:GetAmount()==terms[duration],
   'AI changed the proposed gold amount or duration')
  terms[duration]=nil
  verified=verified+1
 end
end
""" + verify_resources + verify_borders + verify_peace + b"""
assert(verified==count,'AI changed a proposed deal item')
DealManager.CopyIncomingToOutgoingWorkingDeal(me,other)
assert(DealManager.AreWorkingDealsEqual(me,other)==true,'GameCore did not copy the returned terms')
return 'verified'
"""


def offer_choices(queued, gold, recurring=None, requested=None, requested_recurring=None, *, demand=False):
    settled = gold['response']=='settled' or (demand and gold['response']=='rejected')
    states = (gold, recurring, requested, requested_recurring)
    terms = [(key, term['max_amount'] == 0 or settled)
             for key, term in zip(GOLD_TERM_FIELDS, states) if term is not None]
    return [('CHOICE_EXIT', queued), *terms, (FINALIZE, gold['finalize'] is None)]


def _archive_items(player_id, target, amount, per_turn, requested, resource_terms, border_terms, peace_terms=()):
    layout = _recurring_proof()['payload']
    expected = {(giver, receiver, duration): value
                for giver, receiver, amounts in ((player_id, target, (amount,per_turn)),
                                                  (target, player_id, requested))
                for duration, value in zip((0, RECURRING_DURATION), amounts) if value > 0}
    expected_resources = resources.wire_terms(resource_terms,player_id,target)
    borders.verify_copy_source(border_terms)
    expected_borders = {(player_id,target) if row['direction']=='outgoing' else (target,player_id):row['duration']
                        for row in border_terms}
    expected_peace = dict(zip(((player_id,target),(target,player_id)), treaty.expected_durations(peace_terms))) if peace_terms else {}
    count = len(expected) + len(expected_resources) + len(expected_borders) + len(expected_peace)
    if not count:
        raise RuntimeError('Cannot validate an empty deal archive')
    size = (layout['header_bytes'] + len(expected)*layout['item_bytes']
            + len(expected_resources)*resources.ITEM_BYTES + len(expected_borders)*borders.ITEM_BYTES
            + len(expected_peace)*treaty.ITEM_BYTES)
    return layout, size, count, expected, expected_resources, expected_borders, expected_peace


def _verify_archive_items(payload, inventory):
    layout, size, count, expected, expected_resources, expected_borders, expected_peace = inventory
    if len(payload)!=size or struct.unpack_from('<I',payload,layout['item_count_offset'])[0]!=count:
        raise RuntimeError('Native deal archive item count or size differs')
    offset = layout['header_bytes']
    for _ in range(count):
        if len(payload)-offset < borders.ITEM_BYTES:
            raise RuntimeError('Truncated native deal term')
        kind, = struct.unpack_from('<I', payload, offset)
        duration, giver, recipient = struct.unpack_from('<III', payload, offset + layout['duration_offset'])
        if kind == layout['kind'] and len(payload)-offset >= layout['item_bytes']:
            value, = struct.unpack_from('<I', payload, offset + layout['amount_offset'])
            if expected.pop((giver, recipient, duration), None) != value:
                raise RuntimeError('Native gold acceptance archives contain different terms')
            offset += layout['item_bytes']
        elif kind == resources.KIND and len(payload)-offset >= resources.ITEM_BYTES:
            resources.check_archive(payload,offset,duration,giver,recipient,expected_resources)
            offset += resources.ITEM_BYTES
        elif kind == borders.KIND:
            subtype, = struct.unpack_from('<I',payload,offset+20)
            if subtype == treaty.MAKE_PEACE:
                treaty.check_archive(payload,offset,expected_peace)
                offset += treaty.ITEM_BYTES
            else:
                borders.check_archive(payload,offset,expected_borders)
                offset += borders.ITEM_BYTES
        else:
            raise RuntimeError('Unqualified native deal item kind')
    if offset != len(payload) or expected or expected_resources or expected_borders or expected_peace:
        raise RuntimeError('Native deal archives contain different terms')


def deliver_demand_reply(transport, player_id, target, requested, resource_terms):
    pending = transport.pending
    offer = _source(ACCEPT_SOURCE)['first_archive']
    offset = offer['native_term_payload_offset']
    if len(pending)!=1 or type(pending[0]) is not bytes or len(pending[0])<=offset:
        raise RuntimeError('Unexpected native demand reply archive sequence')
    archive = pending[0]
    kind, action, sender, recipient = struct.unpack_from('<4I',archive)
    if kind!=offer['kind'] or (sender,recipient)!=(target,player_id) or action not in (1,2):
        raise RuntimeError('Native demand response archive crossed its participants or outcome')
    inventory = _archive_items(player_id,target,0,0,requested,resource_terms,())
    _verify_archive_items(archive[offset:],inventory)
    transport.deliver_one()
    transport.require_empty_native_queue()
    return 'accepted' if action==1 else 'rejected'


def validate_acceptance(archives, player_id, target, session_id, amount, per_turn=0, *, requested=(0,0),
                        resource_terms=(), border_terms=(), demand=False, peace_terms=()):
    captured = _source(ACCEPT_SOURCE)
    offer, confirm = captured['first_archive'],captured['second_archive']
    inventory = _archive_items(player_id,target,amount,per_turn,requested,resource_terms,border_terms,peace_terms)
    offset = offer['native_term_payload_offset']
    deal_size = offset+inventory[1]
    confirm_size = confirm['bytes']+(deal_size-offer['bytes'])
    if (len(archives) != 2 or any(type(data) is not bytes for data in archives)
            or tuple(map(len,archives)) != (deal_size,confirm_size)):
        raise RuntimeError('Unexpected native gold acceptance archive sequence')
    deal, statement = archives
    payload = deal[offset:]
    if (struct.unpack_from('<IIII', deal) != (offer['kind'],offer['action'],player_id,target)
            or struct.unpack_from('<III', statement) != (confirm['kind'],player_id,session_id)
            or statement.count(payload) != 1):
        raise RuntimeError('Native gold acceptance archives identify a different trade')
    _verify_archive_items(payload,inventory)
    variants = dict(confirm['native_statement_variants'])
    if demand:
        variants['statement'] = (*variants['statement'][:2],DEMAND_STATEMENT)
    variants['from'] = (*variants['from'][:2],player_id)
    variants['to'] = (*variants['to'][:2],target)
    for fields in variants.values():
        if statement.count(struct.pack('<II8xI',*fields)) != 1:
            raise RuntimeError('Gold confirmation statement differs from its designated session')


def deliver_acceptance(transport, player_id, target, session_id, amount, per_turn=0, *, requested=(0,0),
                        resource_terms=(), border_terms=(), demand=False, peace_terms=()):
    """Deliver the native transaction, then its own positive statement."""
    from .native.native_diplomacy_choices import deliver_statement_request

    validate_acceptance(transport.pending,player_id,target,session_id,amount,per_turn,requested=requested,
                        resource_terms=resource_terms,border_terms=border_terms,demand=demand,peace_terms=peace_terms)
    transport.deliver_one()
    deliver_statement_request(transport)
    transport.require_empty_native_queue()

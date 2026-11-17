"""Player-visible resource terms of the installed XP2 trade screen."""

import json
from hashlib import sha256
from pathlib import Path
import struct
from zlib import crc32

from civ6_host.contracts.diplomacy_decisions import RESOURCE_CHOICES, validate_resource_terms

from .configuration_profiles import _source
from .execution_images import identity
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-deal-resources-source.json',
          '23170a6c5695325a464cae3cbcb8d1758b6f766dd2d6ee1bda0cd5fcc031ad8d')
DURATION_SOURCE = ('evidence/host-xp2-deal-resource-duration-source.json',
                   '555161a53ef2fb653b86848c7a0fa68829fd6d1bdaeded4510c4b207abdbb5d5')
KIND = 0xc03f9783
DURATION = 30
RESOURCE_HASH_KEY = 0x234988cf
ITEM_BYTES = 80
READ_CAPACITY = 65536


def _proof(image):
    source = _source(SOURCE)
    selected = identity(image)
    if (source['schema'] != 'civ6-host.xp2-resource-deal.static.v1'
            or source['native_execution'] is not False
            or source['image']['sha256'] != selected['image_sha256']
            or Path(source['image']['path']).resolve() != Path(selected['path']).resolve()
            or source['resource_kind'] != KIND or source['default_added_duration'] != DURATION
            or source['keys']['serialized_resource_hash'] != RESOURCE_HASH_KEY):
        raise ValueError('Unknown native resource negotiation source')
    return source


def _duration_proof(source):
    proof = _source(DURATION_SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-deal-resource-duration.static.v1'
            or proof['native_execution'] is not False
            or (proof['parent']['path'],proof['parent']['sha256']) != SOURCE
            or proof['image'] != source['image']
            or proof['duration'] != {'accumulating':0,'otherwise':DURATION}):
        raise ValueError('Unknown Expansion2 deal duration source')
    return proof


def dependencies(image):
    source = _proof(image)
    duration = _duration_proof(source)
    pins = {str(resolve_path(resource_root()/path)): digest for path,digest in (SOURCE,DURATION_SOURCE)}
    for ui in (source['ui'],duration['extension']):
        path = resolve_path(Path(ui['path']))
        if sha256(path.read_bytes()).hexdigest() != ui['sha256']:
            raise ValueError('Official resource deal controls changed')
        pins[str(path)] = ui['sha256']
    return pins


def verify(saved, image):
    source = _proof(image)
    duration = _duration_proof(source)
    base, read = saved.backend.core._handle, saved.backend.runtime.read
    spans = (*source['native_spans'], *(s for rows in source['bindings'].values() for s in rows),
             *duration['native_spans'])
    for span in spans:
        data = read(base + span['rva'], span['size'])
        if type(data) is not bytes or len(data) != span['size'] or sha256(data).hexdigest() != span['sha256']:
            raise ValueError('Live native resource negotiation source changed')
    targets = {int(slot):rva for slot,rva in source['vtable_targets'].items()}
    targets[duration['settle_slot']] = duration['settle_rva']
    for slot, target in targets.items():
        if read(base + source['vtable_rva'] + slot,8) != struct.pack('<Q',base+target):
            raise ValueError('Live native resource item virtual target changed')


DURATION_LUA = b"""
local function defaultResourceDuration(info)
 assert(info and type(info.ResourceType)=='string' and GameInfo.Resource_Consumption,
  'Missing Expansion2 consumption rules')
 local consumption=GameInfo.Resource_Consumption[info.ResourceType]
 return consumption~=nil and consumption.Accumulate and 0 or 30
end
"""


INVENTORIES = DURATION_LUA + b"""
local RESOURCE=DealItemTypes.RESOURCES
assert(RESOURCE==3225393027 or RESOURCE==-1069574269,'Native resource deal enum changed')
local resourceCount,resourceRows,resourceTerms=0,{},{}
local function resourceInteger(n)
 return type(n)=='number' and n%1==0 and n>=0 and n<=2147483647
end
local function resourceInventory(giver,receiver,direction)
 local rows={}
 resourceTerms[giver]=rows
 local function add(index)
  local info=GameInfo.Resources[index]
  if info==nil or (info.ResourceClassType~='RESOURCECLASS_LUXURY' and
      info.ResourceClassType~='RESOURCECLASS_STRATEGIC') then return nil end
  assert(type(info.ResourceType)=='string' and string.match(info.ResourceType,'^RESOURCE_[A-Z0-9_]+$'),
   'Malformed public resource name')
  local row={direction=direction,index=index,name=info.ResourceType,class=info.ResourceClassType,
   amount=0,maximum=0,available=false,defaultDuration=defaultResourceDuration(info)}
  rows[index]=row
  resourceRows[#resourceRows+1]=row
  assert(#resourceRows<=256,'Too many resource negotiation terms')
  return row
 end
 local quotes=DealManager.GetPossibleDealItems(giver,receiver,RESOURCE,deal) or {}
 assert(type(quotes)=='table' and #quotes<=256,'Invalid resource quotes')
 for _,quote in ipairs(quotes) do
  assert(resourceInteger(quote.ForType) and resourceInteger(quote.MaxAmount) and
   type(quote.IsValid)=='boolean','Malformed native resource quote')
  if quote.MaxAmount>0 then
   assert(rows[quote.ForType]==nil,'Duplicate resource quote')
   local row=add(quote.ForType)
   if row then row.maximum,row.available=quote.MaxAmount,quote.IsValid end
  end
 end
 local items=deal:FindItemsByType(RESOURCE,DealItemSubTypes.NONE,giver) or {}
 assert(type(items)=='table' and #items<=256,'Invalid resource items')
 for _,item in ipairs(items) do
  local index,amount,maximum,duration=item:GetValueType(),item:GetAmount(),item:GetMaxAmount(),item:GetDuration()
  assert(resourceInteger(index) and resourceInteger(amount) and amount>0 and
   resourceInteger(maximum) and resourceInteger(duration) and deal:GetItemParent(item)==nil,
   'Unknown resource term in working deal')
  local row=rows[index] or add(index)
  assert(row and row.item==nil,'Unqualified or duplicate resource item')
  row.item,row.amount,row.maximum,row.duration=item,amount,maximum,duration
  row.available=maximum>0
  resourceCount=resourceCount+1
 end
end
resourceInventory(me,other,'outgoing')
resourceInventory(other,me,'incoming')
local function publicResourceTerms()
 local result={}
 for _,row in ipairs(resourceRows) do
  result[#result+1]='{"direction":"'..row.direction..'","resource_index":'..row.index..
   ',"resource_type":"'..row.name..'","class_type":"'..row.class..'","amount":'..row.amount..
   ',"max_amount":'..row.maximum..',"duration":'..(row.duration or 'null')..
   ',"available":'..tostring(row.available)..'}'
 end
 return '['..table.concat(result,',')..']'
end
"""


def edit_source(choice, index, amount):
    direction = RESOURCE_CHOICES[choice]
    if any(type(value) is not int or not 0 <= value <= 0x7fffffff for value in (index,amount)):
        raise ValueError('Invalid resource negotiation edit')
    giver = 'me' if direction=='outgoing' else 'other'
    return f'\nlocal giver,index,amount={giver},{index},{amount}\n'.encode('ascii') + b"""
local row=resourceTerms[giver][index]
if row==nil or row.amount==amount or (amount>0 and (not row.available or amount>row.maximum))
then return 'unavailable' end
local item=row.item
if amount==0 then
 assert(item~=nil,'No resource to remove')
 deal:RemoveItemByID(item:GetID())
 assert(deal:GetItemCount()==count-1,'Native resource removal did not apply')
 if count==1 then return 'removed' end
else
 local created=item==nil
 if created then
  item=deal:AddItemOfType(RESOURCE,giver)
  if item==nil then return 'unavailable' end
  item:SetValueType(index)
  item:SetAmount(1)
  item:SetDuration(row.defaultDuration)
  if not item:IsValid() or amount>item:GetMaxAmount() then
   deal:RemoveItemByID(item:GetID())
   assert(deal:GetItemCount()==count,'Native rejected resource item was not removed')
   return 'unavailable'
  end
 end
 item:SetAmount(amount)
 assert(deal:GetItemCount()==count+(created and 1 or 0) and item:GetValueType()==index and
  item:GetAmount()==amount and item:GetDuration()==(row.duration or row.defaultDuration),'Native resource change did not apply')
end
"""


def parse(raw):
    rows = validate_resource_terms(json.loads(raw))
    return sorted(rows,key=lambda row: (row['direction'],row['resource_index']))


def draft_duration(prefix, pid, turn, index):
    source = DURATION_LUA + f'\nlocal pid,turn,index={pid},{turn},{index}\n'.encode('ascii') + b"""
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
 'Resource duration crossed the player boundary')
return tostring(defaultResourceDuration(GameInfo.Resources[index]))
"""
    raw = prefix.runtime.evaluate_text(prefix.ui_child,source,b'@xp2_deal_resource_duration',capacity=16)
    if raw not in (b'0',b'30'):
        raise RuntimeError('Unknown native Expansion2 resource duration')
    return int(raw)


def stockpile(prefix, pid, turn, indexes):
    if not indexes:
        return {}
    query = f'local pid,turn,indexes={pid},{turn},{{{",".join(map(str,indexes))}}}\n'.encode('ascii') + b"""
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
 'Resource readback crossed the player boundary')
local stock=Players[pid]:GetResources()
local values={}
for _,index in ipairs(indexes) do values[#values+1]=stock:GetResourceAmount(index) end
return table.concat(values,'|')
"""
    raw = prefix.runtime.evaluate_text(prefix.ui_child,query,b'@xp2_native_deal_stockpile',capacity=4096)
    values = list(map(int,raw.decode('ascii').split('|')))
    if len(values)!=len(indexes) or any(not 0<=value<=0x7fffffff for value in values):
        raise RuntimeError('Invalid native deal stockpile readback')
    return dict(zip(indexes,values))


def wire_terms(rows, player_id, target):
    result = {}
    for row in rows:
        if row['amount']:
            giver, receiver = ((player_id,target) if row['direction']=='outgoing' else (target,player_id))
            key = (giver, receiver, row['duration'], crc32(row['resource_type'].encode('ascii')) ^ 0xffffffff)
            if key in result:
                raise ValueError('Duplicate serialized resource term')
            result[key] = row['amount']
    return result


def check_archive(payload, offset, duration, giver, receiver, expected):
    count, key, tag, resource_hash = struct.unpack_from('<4xIII8xI', payload, offset+44)
    value, = struct.unpack_from('<I',payload,offset+ITEM_BYTES-4)
    if (count != 1 or key != RESOURCE_HASH_KEY or tag != 2
            or expected.pop((giver,receiver,duration,resource_hash),None) != value):
        raise RuntimeError('Native resource acceptance contains different terms')

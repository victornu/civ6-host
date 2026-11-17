"""Open-borders inventory, commands and wire verification for installed XP2."""

from hashlib import sha256
import json
from pathlib import Path
import struct

from .configuration_profiles import _source
from .execution_images import identity
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-deal-open-borders-source.json',
          '36a1265453d9138bfe225593d4666f9402908a6741e7b674f4e9b465adfb26ee')
WIRE = ('evidence/host-xp2-deal-open-borders-wire-source.json',
        '0cd74c95847d4203a525887be325976c26bb771c289bd7700a1adf119f62fb36')
KIND, SUBTYPE, ITEM_BYTES = 0x8bbf84cc, 0xf18dfd9a, 56


def _proof(image):
    source, wire = _source(SOURCE), _source(WIRE)
    selected = identity(image)
    if (source['schema'] != 'civ6-host.xp2-deal-open-borders.static.v1'
            or wire['schema'] != 'civ6-host.xp2-open-borders-wire.static.v1'
            or (wire['parent']['path'],wire['parent']['sha256']) != SOURCE
            or source['image']['sha256'] != selected['image_sha256']
            or wire['image_sha256'] != selected['image_sha256']
            or Path(source['image']['path']).resolve() != Path(selected['path']).resolve()
            or source['enums'] != dict(AGREEMENTS=KIND,OPEN_BORDERS=SUBTYPE,MISSING_DEPENDENCY=2)
            or wire['layout'] != dict(item_bytes=ITEM_BYTES,kind_offset=0,subtype_offset=20,duration_offset=28,
                                      giver_offset=32,recipient_offset=36,tail_offset=44,tail=(1,0,2))):
        raise ValueError('Open borders requires its qualified installed image')
    return source, wire


def dependencies(image):
    source, _ = _proof(image)
    paths = {str(resolve_path(resource_root()/path)): digest for path,digest in (SOURCE,WIRE)}
    for row in source['ui'].values():
        path = resolve_path(Path(row['path'])).resolve()
        if sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Official open-borders controls changed')
        paths[str(path)] = row['sha256']
    return paths


def verify(base, read, image):
    dependencies(image)
    source, wire = _proof(image)
    spans = (*source['native_spans'], *wire['native_spans'],
             *(span for group in source['bindings'].values() for span in group))
    for span in spans:
        data = read(base+span['rva'],span['size'])
        if type(data) is not bytes or len(data) != span['size'] or sha256(data).hexdigest() != span['sha256']:
            raise ValueError('Live open-borders source differs')
    targets = dict(source['vtable_targets'], **{str(wire['vtable_slot']):wire['vtable_target']})
    for slot, target in targets.items():
        if read(base+source['vtable_rva']+int(slot),8) != struct.pack('<Q',base+target):
            raise ValueError('Live open-borders virtual method differs')


LUA_TYPES = b"""
local AGREEMENTS,BORDERS=DealItemTypes.AGREEMENTS,DealAgreementTypes.OPEN_BORDERS
local function enum(n)
 assert(type(n)=='number' and n%1==0 and n>=-2147483648 and n<4294967296,'Invalid agreement enum')
 return n%4294967296
end
assert(enum(AGREEMENTS)==2344584396 and enum(BORDERS)==4052614554
 and DealValidationResult.MISSING_DEPENDENCY==2,'Native agreement enum changed')
local function borderDuration(n)
 return type(n)=='number' and n%1==0 and n>0 and n<=2147483647
end
local function openBorders(deal,giver)
 local items=deal:FindItemsByType(AGREEMENTS,BORDERS,giver) or {}
 assert(type(items)=='table' and #items<=1,'Unexpected open-borders items')
 local item=items[1]
 if item~=nil then
  assert(enum(item:GetSubType())==enum(BORDERS) and borderDuration(item:GetDuration())
   and deal:GetItemParent(item)==nil,'Unqualified open-borders item')
 end
 return item
end
"""


INVENTORY = LUA_TYPES + b"""
local borderCount,borderRows=0,{}
local function borderInventory(giver,receiver,direction)
 local item=openBorders(deal,giver)
 local row={item=item,duration=item and item:GetDuration() or nil}
 if item~=nil then borderCount=borderCount+1 end
 local matches=0
 local quotes=DealManager.GetPossibleDealItems(giver,receiver,AGREEMENTS,deal) or {}
 assert(type(quotes)=='table' and #quotes<=64,'Unbounded native agreement quotes')
 for _,entry in ipairs(quotes) do
  if enum(entry.SubType)==enum(BORDERS) then
   matches=matches+1
   assert(matches==1 and borderDuration(entry.Duration) and type(entry.IsValid)=='boolean',
    'Invalid open-borders quote')
   if item==nil and (entry.IsValid or entry.ValidationResult==DealValidationResult.MISSING_DEPENDENCY) then
    row.available_duration=entry.Duration
   end
  end
 end
 borderRows[direction]=row
end
borderInventory(me,other,'outgoing')
borderInventory(other,me,'incoming')
local function borderTerms()
 local rows={}
 for _,direction in ipairs({'outgoing','incoming'}) do
  local row=borderRows[direction]
  rows[#rows+1]='{"direction":"'..direction..'","duration":'..tostring(row.duration or 'null')..
    ',"available_duration":'..tostring(row.available_duration or 'null')..'}'
 end
 return '['..table.concat(rows,',')..']'
end
"""


def edit_source(direction, remove):
    if direction not in ('outgoing','incoming') or type(remove) is not bool:
        raise ValueError('Unknown native open-borders decision')
    giver = 'me' if direction=='outgoing' else 'other'
    scope = f"\nlocal giver,row={giver},borderRows['{direction}']\n".encode('ascii')
    if remove:
        return scope + b"""
if row.item==nil then return 'unavailable' end
deal:RemoveItemByID(row.item:GetID())
assert(deal:GetItemCount()==count-1 and openBorders(deal,giver)==nil,'Open-borders removal did not apply')
if count==1 then return 'removed' end
"""
    return scope + b"""
if row.item~=nil or row.available_duration==nil then return 'unavailable' end
local item=deal:AddItemOfType(AGREEMENTS,giver)
if item==nil then return 'unavailable' end
item:SetSubType(BORDERS)
item:SetDuration(row.available_duration)
assert(deal:GetItemCount()==count+1 and openBorders(deal,giver)~=nil and
 item:GetDuration()==row.available_duration,'Open-borders draft did not apply')
"""


def verify_copy_source(terms):
    by_side = {'outgoing':0,'incoming':0}
    for term in terms:
        direction, duration = term['direction'], term['duration']
        if direction not in by_side or by_side[direction] or type(duration) is not int or not 0<duration<=0x7fffffff:
            raise ValueError('Invalid expected open-borders directions')
        by_side[direction] = duration
    return LUA_TYPES + f"""
for giver,expected in pairs({{[me]={by_side['outgoing']},[other]={by_side['incoming']}}}) do
 local item=openBorders(inbound,giver)
 assert((item and item:GetDuration() or 0)==expected,'AI changed the proposed open-borders term')
 if item then verified=verified+1 end
end
""".encode('ascii')


RIGHTS = b"""
local function borderRights(actor,peer)
 local incoming=actor:GetDiplomacy():HasOpenBordersFrom(peer:GetID())
 local outgoing=peer:GetDiplomacy():HasOpenBordersFrom(actor:GetID())
 assert(type(incoming)=='boolean' and type(outgoing)=='boolean','Native open-borders rights unavailable')
 return '{"outgoing":'..tostring(outgoing)..',"incoming":'..tostring(incoming)..'}'
end
"""


def read_rights(prefix, player_id, turn, target):
    if (type(turn) is not int or turn<0 or player_id==target
            or any(type(pid) is not int or not 0<=pid<64 for pid in (player_id,target))):
        raise ValueError('Invalid open-borders perspective')
    code = RIGHTS + f"""
local pid,peer,turn={player_id},{target},{turn}
assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
 'Open-borders query crossed its player or turn')
local actor,target=Players[pid],Players[peer]
assert(actor and target and target:IsAlive() and target:IsMajor() and actor:GetDiplomacy():HasMet(peer),
 'Open-borders partner is outside the visible diplomatic overview')
return borderRights(actor,target)
""".encode('ascii')
    result = json.loads(prefix.runtime.evaluate_text(prefix.ui_child, code, b'@xp2_open_borders_rights',capacity=80))
    if type(result) is not dict or set(result)!={'outgoing','incoming'} or any(type(v) is not bool for v in result.values()):
        raise ValueError('Invalid native open-borders rights')
    return result


def check_archive(data, offset, expected):
    kind, = struct.unpack_from('<I', data, offset)
    subtype, = struct.unpack_from('<I', data, offset+20)
    duration,giver,recipient = struct.unpack_from('<III',data,offset+28)
    tail = struct.unpack_from('<III',data,offset+44)
    if (kind,subtype,tail)!=(KIND,SUBTYPE,(1,0,2)) or expected.pop((giver,recipient),None)!=duration:
        raise RuntimeError('Native deal archives contain different open-borders rights')

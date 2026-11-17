"""Installed XP2's native locked treaty items and their draft readback."""

from hashlib import sha256
from pathlib import Path
import struct

from .configuration_profiles import _source
from .execution_images import identity
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-major-peace-opening-source.json',
          '0e3c837572325352abdb381abf1348a2c6d21e41dd503a018545b1c6c7de831e')
SETTLEMENT = ('evidence/host-xp2-major-peace-settlement-source.json',
              '9b11b57fc85df088b899f4fb9ac0d0640a761c6887f72643f2f70cf1a3e50f4e')
DIRECTION_COUNT = ('evidence/host-xp2-major-peace-direction-count-source.json',
                   '9ef4c46f104c4300a88cdd177bc77c7267e012d286afe695e5f31c56e6810a75')
NATIVE_WIRE = ('evidence/host-xp2-major-peace-native-wire-source.json',
               '5287e771b369fafc649904af6eb4827aa7eb52a90e6edad4ece9ef426958ca10')
AGREEMENTS, MAKE_PEACE = 0x8BBF84CC, 0x209AFA81
ITEM_BYTES = 76
ARGUMENT_MAP = (1, 1, 0x234988CF, 2, 0, 0, 0xFFFFFFFF, 2)


def _proof(image):
    proof, settlement, directions, archive = (_source(pin) for pin in (SOURCE,SETTLEMENT,DIRECTION_COUNT,NATIVE_WIRE))
    selected = identity(image)
    if (proof['schema'] != 'civ6-host.xp2-major-peace.static.v1'
            or proof['image']['sha256'] != selected['image_sha256']
            or proof['agreement_kind'] != AGREEMENTS or proof['agreement_subtype'] != MAKE_PEACE
            or proof['action'] != 'CHOICE_MAKE_PEACE' or proof['session_request'] != 'MAKE_DEAL'
            or set(proof['bindings']) != {'IsLocked', 'SetLocked'}):
        raise ValueError('Major peace requires the qualified installed image')
    wire = settlement['writer']
    if (settlement['schema'] != 'civ6-host.xp2-major-peace-settlement.static.v1'
            or settlement['image'] != proof['image']
            or settlement['ui'] != proof['ui']['deal']
            or (settlement['parents'][0]['path'], settlement['parents'][0]['sha256']) != SOURCE
            or settlement['ui_operations'] != dict(on_show='INSPECT', proposal='PROPOSED', confirmation='ACCEPTED')
            or wire['kind'] != AGREEMENTS or wire['subtype'] != MAKE_PEACE or wire['lock_byte_offset'] != 42
            or wire['peace_extra_argument_inserted'] is not False):
        raise ValueError('Major peace settlement source changed')
    if (directions['schema'] != 'civ6-host.xp2-peace-direction-count.static.v1'
            or directions['image'] != proof['image'] or directions['agreement_subtype'] != MAKE_PEACE
            or (directions['opening']['path'], directions['opening']['sha256']) != SOURCE
            or directions['vtable_rva'] != proof['vtable_rva']
            or directions['counted_in_both_directions'] is not True):
        raise ValueError('Major peace directional count source changed')
    if (archive['schema'] != 'civ6-host.xp2-major-peace-archive.native-source.v1'
            or archive['image_sha256'] != selected['image_sha256']
            or (archive['static_source']['path'], archive['static_source']['sha256']) != SETTLEMENT
            or archive['layout'] != dict(item_bytes=ITEM_BYTES, argument_map_offset=44,
                                         argument_map=ARGUMENT_MAP, lock_byte_offset=42)
            or archive['transfer_delivered'] is not False):
        raise ValueError('Major peace native confirmation archive source changed')
    return proof, settlement, directions


def dependencies(image):
    proof, _, _ = _proof(image)
    refs = {str(resolve_path(resource_root()/path)): digest
            for path,digest in (SOURCE,SETTLEMENT,DIRECTION_COUNT,NATIVE_WIRE)}
    for pin in proof['ui'].values():
        path = resolve_path(Path(pin['path'])).resolve()
        if sha256(path.read_bytes()).hexdigest() != pin['sha256']:
            raise ValueError('Official major peace controls changed')
        refs[str(path)] = pin['sha256']
    return refs


def verify(base, read, image):
    dependencies(image)
    proof, settlement, directions = _proof(image)
    wire = settlement['writer']
    spans = (*proof['native_spans'], *settlement['native_spans'], *directions['spans'],
             *(span for rows in proof['bindings'].values() for span in rows))
    for span in spans:
        raw = read(base+span['rva'], span['size'])
        if type(raw) is not bytes or len(raw) != span['size'] or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live major peace source changed')
    targets = {**proof['vtable_targets'], **wire['vtable_targets'],
               str(directions['vtable_slot']):directions['vtable_target']}
    for slot, target in targets.items():
        if read(base+proof['vtable_rva']+int(slot), 8) != struct.pack('<Q', base+target):
            raise ValueError('Live major peace virtual method changed')


# Bind only these locals. The official peace choice sets the subtype and lock,
# then GameCore Validate produces the reciprocal term.
INVENTORY = f"""
local PEACE_AGREEMENTS,PEACE_SUBTYPE=DealItemTypes.AGREEMENTS,DealAgreementTypes.MAKE_PEACE
assert(type(PEACE_AGREEMENTS)=='number' and PEACE_AGREEMENTS%4294967296=={AGREEMENTS}
 and type(PEACE_SUBTYPE)=='number' and PEACE_SUBTYPE%4294967296=={MAKE_PEACE},
 'Major treaty agreement enums changed')
local function peaceTerm(working,giver)
 local items=working:FindItemsByType(PEACE_AGREEMENTS,PEACE_SUBTYPE,giver)
 assert(type(items)=='table' and #items==1,'Missing or duplicate peace treaty term')
 local item=items[1]
 local subtype,duration=item:GetSubType(),item:GetDuration()
 assert(subtype==PEACE_SUBTYPE and item:IsLocked()==true and
  type(duration)=='number' and duration%1==0 and duration>=0 and duration<=2147483647,
  'Invalid locked peace treaty term')
 return duration
end
local function openingTreaty(working,me,other)
 assert(working~=nil and working:GetItemCount()==2,'Missing or extra items in the opening peace treaty')
 return peaceTerm(working,me),peaceTerm(working,other)
end
""".encode('ascii')

READ_OPENING = INVENTORY + b"""
local outgoing,incoming=openingTreaty(deal,me,other)
return (queued and 'queued' or 'closable')..'|'..tostring(outgoing)..'|'..tostring(incoming)
"""


def parse_opening(raw):
    if type(raw) is not bytes or len(raw) > 64:
        raise ValueError('Invalid native peace draft size')
    queue, *durations = raw.split(b'|')
    if queue not in (b'queued', b'closable') or len(durations) != 2:
        raise ValueError('Invalid native peace draft dimensions')
    if any(not duration.isdigit() or int(duration) > 0x7fffffff for duration in durations):
        raise ValueError('Invalid native peace treaty duration')
    return queue == b'queued', [
        dict(direction=side, duration=int(duration), locked=True)
        for side, duration in zip(('outgoing', 'incoming'), durations)
    ]


def working_source(prefix):
    return prefix + INVENTORY + b"""
local peaceOut,peaceIn=peaceTerm(deal,me),peaceTerm(deal,other)
local treatyCount=2
"""


def expected_durations(terms):
    from civ6_host.contracts.diplomacy_decisions import validate_peace_terms
    return tuple(row['duration'] for row in validate_peace_terms(list(terms)))


def compare_source(terms, variable):
    if variable not in ('inbound', 'deal', 'copied'):
        raise ValueError('Unknown peace working-deal direction')
    outgoing, incoming = expected_durations(terms)
    return f"""
assert(peaceTerm({variable},me)=={outgoing} and peaceTerm({variable},other)=={incoming},
 'Native reply changed locked peace terms')
""".encode('ascii')


def verify_copy_source(terms):
    return compare_source(terms, 'inbound') + b'\nverified=verified+2\n'


def check_archive(payload, offset, expected):
    if len(payload)-offset < ITEM_BYTES:
        raise RuntimeError('Truncated native locked peace term')
    kind, = struct.unpack_from('<I', payload, offset)
    subtype, = struct.unpack_from('<I', payload, offset+20)
    duration,giver,recipient = struct.unpack_from('<III', payload, offset+28)
    tail = struct.unpack_from('<8I', payload, offset+44)
    if ((kind,subtype) != (AGREEMENTS,MAKE_PEACE) or payload[offset+42] != 1
            or tail != ARGUMENT_MAP or expected.pop((giver,recipient),None) != duration):
        raise RuntimeError('Native deal archive contains a different locked peace term')

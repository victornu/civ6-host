"""Receiver seam spec for a received MAKE_DEAL statement (source-only).

Piste "couture recepteur" of the XP2 alliance orchestration. This module is the
receiving-side counterpart of the OUTGOING-only scope
``continuation._xp2_deal_statement_scope``: a0_diplomacy_statement._statement_fields
forwards the raw argument map untouched when no scope is present, and
native_diplomacy_statement.decode_fields then rejects any key outside
NAMES + opaque (+ blob). That is correct for plain statements, but a received
MAKE_DEAL legitimately carries three extra deal keys on the wire.

Seam rule (both reads): when a MAKE_DEAL statement is received WITHOUT an
outgoing scope, BOTH reads of the exchange (the initial statement and its
reply, mirroring project_statement_fields' "validate deal extensions in both
reads") must accept the extra deal keys {encoded_native_deal, DealAction,
RespondingToDealAction} IN ADDITION TO the exact NAMES set (+ opaque/blob),
validate them against the pinned wire proof, and store the result in a
per-statement sidecar ``entry['deal_offer']`` -- a dict with exactly
action/response/subtype/provenance. The deal extensions are NEVER stored in
``fields`` and NAMES is NEVER bypassed for non-deal statements (a non-deal
statement carrying the extra keys is rejected, not patched).

Everything here is pinned and source-only: no GameCore, no native read, no
modification of any existing file. Wire facts come from
evidence/host-xp2-empty-deal-statement-native-source.json (sha 4f56dd2c...) and
the private native receipt host-xp2-human-make-deal-native-source.json
(sha 124a5898...); the record codec constants mirror
native/native_diplomacy_statement.py (PROOF_SHA256 b78799f5...).
"""
from __future__ import annotations

import struct

__all__ = [
    'STATEMENT_SOURCE', 'HUMAN_NATIVE_SOURCE', 'PROOF_SHA256',
    'EVENT_KIND', 'RECORD_TYPE', 'RECORD_SIZE',
    'WIRE_NAMES', 'WIRE_OPAQUE_KEY', 'WIRE_BLOB_KEY', 'WIRE_EXTRA_KEYS',
    'STATEMENT_TYPE', 'SUBTYPE', 'RESPONSE_TYPE', 'DEAL_ACTION',
    'RESPONDING_TO_DEAL_ACTION', 'NATIVE_VARIANT_TYPE', 'NATIVE_VARIANT_FLAGS',
    'PROPOSED', 'DEAL_ACTIONS', 'WIRE_KEYS', 'RECEIVED_STATEMENT_ARCHIVE',
    'TERMINAL_PAIR_ARCHIVE', 'BOTH_READS', 'WIRE_PROOF',
    'deal_read_allowed_keys', 'is_make_deal_wire', 'extract_deal_offer',
    'seam_entry', 'check_sidecar', 'RECEPTION_SIDECAR_LUA',
]

# Pinned source receipts (path relative to CIV6_HOST_RESOURCE_ROOT, sha256).
STATEMENT_SOURCE = ('evidence/host-xp2-empty-deal-statement-native-source.json',
                    '4f56dd2c6e0adf29cdb85ead16d96b336d3ef3721018d0299871aa9cb2820ae9')
HUMAN_NATIVE_SOURCE = ('evidence/host-xp2-human-make-deal-native-source.json',
                       '124a5898edae9d37c814ee3bb8a37d8c0ab859d51592be5d3001e280ba4e7efa')
# Receiver-wide codec proof of native/native_diplomacy_statement.py.
PROOF_SHA256 = 'b78799f583992bcddcb16f76d3714869bf547dda7f96b79a0e9fc3abe32f13f8'
EVENT_KIND = 4235402789          # host event kind (0xfc731e25)
RECORD_TYPE = 132                # statement FIFO record type
RECORD_SIZE = 112                # statement FIFO record size

# Exact NAMES map of the native record codec (native_diplomacy_statement.NAMES).
WIRE_NAMES = {'StatementType': 3136235966, 'StatementSubType': 304523663,
              'ResponseType': 2612666305, 'SessionID': 2133911650,
              'FromPlayer': 2623097599, 'ToPlayer': 406339414,
              'Initiator': 940935371, 'FromPlayerMood': 3012028737,
              'ToPlayerMood': 1206716586, 'AiReason': 3960653642,
              'AiModifier': 2854660138, 'IsFirstStatementOfType': 654530884}
WIRE_OPAQUE_KEY = 2663773416
WIRE_BLOB_KEY = 2684726792

# Extra deal keys accepted on a received MAKE_DEAL (wire argument map only).
WIRE_EXTRA_KEYS = {'encoded_native_deal': 653299807, 'DealAction': 1009080843,
                   'RespondingToDealAction': 4263390813}

# Pinned values of the observed fil (AI-seat empty deal statement):
# MAKE_DEAL / NONE / ACKNOWLEDGE with deal_action 0 on this thread.
STATEMENT_TYPE = 2229918858      # MAKE_DEAL (0x84e9dc8a)
SUBTYPE = 3069842052             # NONE (0xb6fa1284)
RESPONSE_TYPE = 3405713603       # ACKNOWLEDGE
DEAL_ACTION = 0
RESPONDING_TO_DEAL_ACTION = 0
NATIVE_VARIANT_TYPE = 22         # encoded_native_deal envelope tag
NATIVE_VARIANT_FLAGS = 1090519040

# DealProposalAction enum (a received offer is PROPOSED=4; INITIAL alone
# proves nothing, see private receipt 557445ff).
PROPOSED = 4
DEAL_ACTIONS = {'ACCEPTED': 1, 'REJECTED': 2, 'ADJUSTED': 3, 'PROPOSED': 4,
                'DEMANDED': 5, 'EQUALIZE': 6, 'INSPECT': 7, 'CLOSED': 8,
                'EQUALIZE_FAILED': 10, 'REJECTED_PERMANENT': 12}

# Diplomacy statement/response key names observed on the human MAKE_DEAL wire.
WIRE_KEYS = {'MAKE_DEAL': 2229918858, 'NONE': 3069842052, 'INITIAL': 2124225610,
             'ACKNOWLEDGE': 3405713603, 'POSITIVE': 1932720086, 'NEGATIVE': 373588173,
             'HUMAN_ACCEPT_DEAL': 3255760895, 'HUMAN_REFUSE_DEAL': 927636149}
RECEIVED_STATEMENT_ARCHIVE = 2752979857   # native archive kind of a received statement
TERMINAL_PAIR_ARCHIVE = 4032975076        # terminal pair archive (no session id)

# A deal exchange is read twice (initial statement + reply): the seam applies
# to BOTH reads while no outgoing scope is present.
BOTH_READS = 2

# Internal-consistency view of the pinned wire proof (source-only mirror of
# STATEMENT_SOURCE + the received_statement envelope of HUMAN_NATIVE_SOURCE).
WIRE_PROOF = {
    'statement_source': STATEMENT_SOURCE,
    'human_native_source': HUMAN_NATIVE_SOURCE,
    'dispatch_kind': EVENT_KIND,
    'record_type': RECORD_TYPE,
    'record_size': RECORD_SIZE,
    'statement_type': STATEMENT_TYPE,
    'subtype': SUBTYPE,
    'response_type': RESPONSE_TYPE,
    'deal_action': DEAL_ACTION,
    'responding_to_deal_action': RESPONDING_TO_DEAL_ACTION,
    'native_variant_type': NATIVE_VARIANT_TYPE,
    'native_variant_flags': NATIVE_VARIANT_FLAGS,
    'extra_keys': dict(WIRE_EXTRA_KEYS),
    'received_statement_archive': RECEIVED_STATEMENT_ARCHIVE,
    'terminal_pair_archive': TERMINAL_PAIR_ARCHIVE,
}

# Scalar envelope tags used by the codec (mirrors decode_fields).
_TAG_BOOL, _TAG_PLAYER, _TAG_SCALAR = 1, 2, 3


def _decode_scalar(raw, expected_tag):
    """Mirror of native_application_mirror.decode_scalar (source-only copy)."""
    if type(raw) is not bytes or len(raw) != 24:
        raise ValueError('Incomplete native scalar envelope')
    tag = struct.unpack_from('<H', raw)[0]
    flags = struct.unpack_from('<I', raw, 20)[0]
    if tag != expected_tag or flags:
        raise ValueError('Unverified native scalar type or ownership')
    value = struct.unpack_from('<I', raw, 8)[0]
    if tag == _TAG_BOOL and value not in (0, 1):
        raise ValueError('Noncanonical native boolean')
    return value


def deal_read_allowed_keys():
    """Exact key set admitted on BOTH reads of a received MAKE_DEAL wire map.

    NAMES + opaque + the three extra deal keys; the blob key is admitted as an
    optional addition exactly like decode_fields admits it for plain records.
    """
    return frozenset(WIRE_NAMES.values()) | {WIRE_OPAQUE_KEY} | set(WIRE_EXTRA_KEYS.values())


def is_make_deal_wire(fields):
    """True when the raw wire map decodes StatementType to the pinned MAKE_DEAL."""
    raw = fields.get(WIRE_NAMES['StatementType'])
    if raw is None:
        return False
    return _decode_scalar(raw, _TAG_SCALAR) == STATEMENT_TYPE


def extract_deal_offer(fields):
    """Validate the extra deal keys against the pinned proof and build the sidecar.

    ``fields`` is the raw hash-keyed wire argument map of one received MAKE_DEAL
    statement. Returns the per-statement sidecar dict with exactly
    action/response/subtype/provenance; the deal extensions themselves are
    never copied into the named fields.
    """
    allowed = deal_read_allowed_keys()
    if set(fields) not in (allowed, allowed | {WIRE_BLOB_KEY}):
        raise ValueError('Received MAKE_DEAL carries unknown fields or lacks a required scalar')
    if not is_make_deal_wire(fields):
        raise ValueError('Seam deal keys accepted only on a MAKE_DEAL statement')
    # encoded_native_deal envelope: shape only, the payload pointer stays
    # opaque (serialized through deal object virtual slot 0x1c0).
    deal = fields[WIRE_EXTRA_KEYS['encoded_native_deal']]
    if (type(deal) is not bytes or len(deal) != 24
            or struct.unpack_from('<H', deal)[0] != NATIVE_VARIANT_TYPE
            or struct.unpack_from('<I', deal, 20)[0] != NATIVE_VARIANT_FLAGS):
        raise ValueError('Unknown native deal object variant')
    pointer = struct.unpack_from('<Q', deal, 8)[0]
    if not 0x10000 <= pointer < 1 << 47 or pointer % 8:
        raise ValueError('Invalid native deal object address')
    action = _decode_scalar(fields[WIRE_EXTRA_KEYS['DealAction']], _TAG_SCALAR)
    responding = _decode_scalar(fields[WIRE_EXTRA_KEYS['RespondingToDealAction']], _TAG_SCALAR)
    subtype = _decode_scalar(fields[WIRE_NAMES['StatementSubType']], _TAG_SCALAR)
    response = _decode_scalar(fields[WIRE_NAMES['ResponseType']], _TAG_SCALAR)
    # 0 is the pinned "no action" value of the AI-seat fil; other values must
    # belong to the pinned DealProposalAction enum.
    if action not in set(DEAL_ACTIONS.values()) | {0} or responding not in set(DEAL_ACTIONS.values()) | {0}:
        raise ValueError('Unknown native deal action on a received MAKE_DEAL')
    if (subtype, response) not in ((SUBTYPE, RESPONSE_TYPE),):
        raise ValueError('Received MAKE_DEAL differs from the pinned fil subtype/response')
    if (action, responding) not in ((DEAL_ACTION, RESPONDING_TO_DEAL_ACTION), (PROPOSED, 0)):
        raise ValueError('Received MAKE_DEAL carries an unpinned action pair')
    return {'action': action, 'response': response, 'subtype': subtype,
            'provenance': 'native_event'}


def seam_entry(sequence, fields, opaque, blob_hex, *, outgoing_scope):
    """Build one consumed-statement ledger entry through the receiver seam.

    Mirrors native_diplomacy_statement.StatementReceiver.consume's entry shape
    (event_sequence top-level, fields = named NAMES dict, source_proof_sha256).
    When ``outgoing_scope`` is false and the statement is a MAKE_DEAL, the extra
    deal keys are accepted at this read and projected into the sidecar
    ``entry['deal_offer']``; they are stripped from the named fields. A
    non-deal statement carrying the extra keys is rejected outright: NAMES is
    never bypassed for non-deal statements.
    """
    if type(sequence) is not int or sequence <= 0:
        raise ValueError('Statement entry requires its top-level event_sequence')
    if type(fields) is not dict or type(opaque) is not int or not 0 <= opaque <= 4294967295:
        raise ValueError('Malformed statement entry inputs')
    if outgoing_scope:
        # Outgoing scope path is owned by xp2_deal_draft.project_statement_fields;
        # the receiver seam must not second-guess it here.
        allowed = frozenset(WIRE_NAMES.values()) | {WIRE_OPAQUE_KEY}
        if set(fields) not in (allowed, allowed | {WIRE_BLOB_KEY}):
            raise ValueError('Statement has unknown fields or lacks a required scalar')
        offer = None
    elif is_make_deal_wire(fields):
        offer = extract_deal_offer(fields)
    else:
        allowed = frozenset(WIRE_NAMES.values()) | {WIRE_OPAQUE_KEY}
        if set(fields) not in (allowed, allowed | {WIRE_BLOB_KEY}):
            raise ValueError('Non-deal statement must not carry the extra deal keys')
        offer = None
    named = {}
    for name, key in WIRE_NAMES.items():
        tag = _TAG_BOOL if name == 'IsFirstStatementOfType' else (
            _TAG_PLAYER if name in ('FromPlayer', 'ToPlayer', 'Initiator') else _TAG_SCALAR)
        value = _decode_scalar(fields[key], tag)
        named[name] = bool(value) if tag == _TAG_BOOL else value
    entry = dict(event_sequence=sequence, fields=named, opaque_9ec5f4e8=opaque,
                 opaque_a005ae08_hex=blob_hex, source_proof_sha256=PROOF_SHA256,
                 learner_exposure_validated=False, automatic_response=False)
    if offer is not None:
        # Sidecar only: never inside entry['fields'].
        entry['deal_offer'] = offer
    return entry


def check_sidecar(sidecar, *, expect_proposed):
    """Source-only mirror of RECEPTION_SIDECAR_LUA: validate one deal_offer sidecar."""
    if type(sidecar) is not dict or set(sidecar) != {'action', 'response', 'subtype', 'provenance'}:
        raise ValueError('deal_offer sidecar must carry exactly action/response/subtype/provenance')
    if sidecar['provenance'] != 'native_event':
        raise ValueError('Sidecar provenance must be native_event')
    for key in ('action', 'response', 'subtype'):
        if type(sidecar[key]) is not int or not 0 <= sidecar[key] <= 4294967295:
            raise ValueError('Sidecar scalar is not uint32: ' + key)
    if sidecar['subtype'] != SUBTYPE or sidecar['response'] != RESPONSE_TYPE:
        raise ValueError('Sidecar differs from the pinned fil subtype/response')
    if expect_proposed:
        if sidecar['action'] != PROPOSED:
            raise ValueError('Received offer is not an authenticated PROPOSED (4)')
    elif sidecar['action'] != DEAL_ACTION:
        raise ValueError('AI-seat acknowledgement fil must carry deal_action 0')
    return True


# Reception-side Lua excerpt (source-only, ASCII): reads and validates the
# per-statement deal_offer sidecar on the receiving seat. `entry` is the
# consumed ledger entry (event_sequence top-level, fields = named NAMES dict);
# `expect_proposed` selects the received-offer check (PROPOSED=4) against the
# AI-seat acknowledgement fil (deal_action 0).
RECEPTION_SIDECAR_LUA = b"""
-- Reception-side validation of the per-statement deal_offer sidecar.
local entry, expect_proposed = ...
assert(type(entry) == 'table', 'Statement entry must be a table')
local fields = entry.fields
assert(type(fields) == 'table', 'Statement entry must carry its named fields')
local sidecar = entry.deal_offer
assert(type(sidecar) == 'table', 'MAKE_DEAL reception requires the deal_offer sidecar')
local count = 0
for k, v in pairs(sidecar) do
  count = count + 1
  assert(k == 'action' or k == 'response' or k == 'subtype' or k == 'provenance',
    'Unknown deal_offer sidecar key')
  assert(k == 'provenance' or type(v) == 'number', 'Sidecar scalar must be a number')
end
assert(count == 4, 'deal_offer sidecar must carry exactly action/response/subtype/provenance')
assert(sidecar.provenance == 'native_event', 'Sidecar provenance must be native_event')
-- The deal extensions never leak into the named fields (NAMES is not bypassed).
assert(fields.DealAction == nil and fields.RespondingToDealAction == nil and
  fields.encoded_native_deal == nil, 'Deal extension leaked into the statement fields')
-- The named fields carry exactly the twelve pinned NAMES keys.
local names = {'StatementType', 'StatementSubType', 'ResponseType', 'SessionID',
  'FromPlayer', 'ToPlayer', 'Initiator', 'FromPlayerMood', 'ToPlayerMood',
  'AiReason', 'AiModifier', 'IsFirstStatementOfType'}
for _, name in ipairs(names) do
  assert(fields[name] ~= nil, 'Missing NAMES field: ' .. name)
end
for k in pairs(fields) do
  local known = false
  for _, name in ipairs(names) do
    if k == name then known = true break end
  end
  assert(known, 'Non-NAMES key stored in the statement fields: ' .. tostring(k))
end
-- Pinned wire values of the fil: MAKE_DEAL (2229918858) / NONE / ACKNOWLEDGE.
assert(fields.StatementType == 2229918858, 'Statement is not MAKE_DEAL')
assert(sidecar.subtype == 3069842052, 'Received subtype is not the pinned NONE hash')
assert(sidecar.response == 3405713603, 'Received response is not the pinned ACKNOWLEDGE hash')
if expect_proposed then
  assert(sidecar.action == DealProposalAction.PROPOSED and DealProposalAction.PROPOSED == 4,
    'Received offer is not an authenticated PROPOSED (4)')
else
  assert(sidecar.action == 0, 'AI-seat acknowledgement fil must carry deal_action 0')
end
return 'deal_offer_valid'
"""

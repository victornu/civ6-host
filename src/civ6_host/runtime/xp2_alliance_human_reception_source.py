"""Static source facts for a human seat receiving a MAKE_DEAL proposal.

SOURCE-ONLY module (lot 98d405f3, corrections 2e608d3d/28d7fb8a): pins the
native statement wire of a deal received on the AI seat, the private UI drop
(11 scripts byte-exact, manifest 3195e4b127b4), and the REAL custom handler
found in the drop: DiplomacyActionView.lua (2464...) lines 2627-2629 register
MAKE_DEAL (MakeDeal_ApplyStatement line 2545, MakeDeal_TestValid 2611); in GS
the loaded deal UI is DLC/Expansion2/UI/Replacements/DiplomacyDealView.lua
(0cd3b32a...) + DiplomacyDealView_Expansion2.lua (b873237d...). The H2H
native payload/runner envelopes come from the support worker's Core source
and are NOT asserted here.
"""
from __future__ import annotations

# Native statement wire of a deal received on the AI seat (target-to-local
# acknowledgement), pinned by evidence/host-xp2-empty-deal-statement-native-
# source.json (sha 4f56dd2c...). AI-seat wire only.
STATEMENT_SOURCE = ('evidence/host-xp2-empty-deal-statement-native-source.json',
                    '4f56dd2c6e0adf29cdb85ead16d96b336d3ef3721018d0299871aa9cb2820ae9')
DRAFT_SOURCE = ('evidence/host-xp2-major-deal-draft-source.json',
                '7f092d94fefea923358c98390bfa318016796ca76c1ff43b87cd87b08f913985')
DISPATCH_KIND = 4235402789
STATEMENT_TYPE = 2229918858          # MAKE_DEAL
SUBTYPE = 3069842052
RESPONSE_TYPE = 3405713603
WIRE_PLAYER_ORDER = 'target-to-local-acknowledgement'   # AI seat only
NATIVE_VARIANT_TYPE = 22
NATIVE_VARIANT_FLAGS = 1090519040
DEAL_ACTION = 0
RESPONDING_TO_DEAL_ACTION = 0
EXTRA_KEYS = {'encoded_native_deal': 653299807, 'DealAction': 1009080843,
              'RespondingToDealAction': 4263390813}
DEAL_POINTER_ROLE = 'serialized through deal object virtual slot 0x1c0; leave opaque in native argument map'

# Official UI pins (dispatch chain + private drop, verified byte-exact).
VIEW_SHA256 = '246409606568dc3f6f2b913334dbc626d9b59e81efc02df0d28409a6ae959cfc'
XP1_VIEW_SHA256 = 'aee6e35dba8a732a7a98674153965bd197fe90f4cfee3c51fecaf57167dc0e6a'
XP2_VIEW_SHA256 = '652552cff5f5bb18634ed16ce4951a4f18d4ca33e7085b18371490b4555d2648'
ALLIANCE_ROW_SHA256 = '34990895aecfa4330b026939fc214b8f041caa231ecdc0f69ee9b8b86e4772aa'
ALLIANCE_TAB_SHA256 = '560ba69ff03e0d26b557083da104c161357e7c705a2ece1555484a48fa13a591'
DEAL_VIEW_SHA256 = '34f5054482ba8afaf4d1641eeb2d5c7cc0819238a0b7fb807bfc0ce9d3ed7686'
# In Gathering Storm the LOADED deal view is the Expansion2 replacement:
DEAL_VIEW_XP2_SHA256 = '0cd3b32a80725067e3c0d73a2dbab75ad968dd0cec8858fa297c07e85ceaf705'
DEAL_VIEW_XP2_EXTRA_SHA256 = 'b873237d444943b66c81113d520e04f8f93a5a15121e1d50470f56855d2d5e01'
RIBBON_SHA256 = '120f9f54161d41510a1f3c031b1a0284ee0b91289923d25b395baf3729a3477c'
RIBBON_SUPPORT_SHA256 = 'c91b6f49d1a8e176dcd64ada171e33c490164bfcc442ec6d5fa4f3af1779be2b'
CORE_SHA256 = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
READBACK_PROOF_SHA256 = 'be15eca6792e6c10675d4a9931de7ad12d262a5b86f035c5bb4d24a91a1b6b07'

# Private UI drop (FTP aes zip sha 44a357d2..., embedded MANIFEST sha
# 3195e4b127b4..., 11 scripts byte-exact verified).
UI_DROP_SHA256 = '44a357d2957dc50a8c4e7ca0be1340b7d6738dee8134fa0bb937ba1a953efce9'
UI_MANIFEST_SHA256 = '3195e4b127b42c2997739e4bb8177042ea749f4a0383daa2e009d1a7c833599f'
UI_DROP_ROOT = 'C:/civ6-private/alliances-ui-drop/3195e4b127b4'

# DealProposalAction enum pinned by the deal pipeline (deal_gold._SEND) plus
# the support native source (e29ed1c3): CLOSED=8, REJECTED_PERMANENT=12.
DEAL_ACTIONS = {'ACCEPTED': 1, 'REJECTED': 2, 'ADJUSTED': 3, 'PROPOSED': 4,
                'DEMANDED': 5, 'EQUALIZE': 6, 'INSPECT': 7, 'EQUALIZE_FAILED': 10,
                'CLOSED': 8, 'REJECTED_PERMANENT': 12}

# Native human-branch facts from the support source (557445ff/e29ed1c3):
# RequestSession (rva 0x6952cc) transmits payload NIL; the MAKE_DEAL
# constructor zeroes the actions, so INITIAL only opens the conversation and
# proves neither PROPOSED nor an incoming item. SendWorkingDeal chain
# 0x693be0 -> 0x6d1e80 -> 0x58bfb0; the human branch emits archive kind
# 0xf06250e4 for actions {1,2,8,12} carrying action/from/to/deal WITHOUT sid;
# runner 0xfc731e25 closes by retained sid BEFORE publishing. A received
# offer must therefore be tied to an authenticated PROPOSED-from-peer plus a
# real valid INCOMING deal, never to session existence alone.
REQUEST_SESSION_RVA = 0x6952CC
SEND_WORKING_DEAL_CHAIN = (0x693BE0, 0x6D1E80, 0x58BFB0)
HUMAN_ARCHIVE_KIND = 0xF06250E4
RUNNER_CLOSE_RVA = 0xFC731E25

# Handler registration in DiplomacyActionView.lua (VIEW_SHA256):
#   2627: SetDefaultHandlers("MAKE_DEAL")
#   2628: StatementHandlers["MAKE_DEAL"].ApplyStatement = MakeDeal_ApplyStatement
#   2629: StatementHandlers["MAKE_DEAL"].TestValid = MakeDeal_TestValid
MAKE_DEAL_HANDLER_REGISTRATION = ('Base/Assets/UI/DiplomacyActionView.lua', 2627)
# Official open condition (ApplyStatement, line 2548): subtype 'NONE' with
# ResponseType INITIAL/ACKNOWLEDGE (or ADJUSTED while not showing) opens the
# deal UI via LuaEvents.DiploPopup_ShowMakeDeal(other). TestValid (2611):
# sessionInfo.FromPlayer==other requires INCOMING deal non-nil, item count>0,
# IsValid(). Return subtypes compared unprefixed at 2559/2648:
# HUMAN_ACCEPT_DEAL / HUMAN_REFUSE_DEAL / AI_ACCEPT_DEAL / AI_REFUSE_DEAL.
DEAL_SUBTYPES = ('AI_ACCEPT_DEAL', 'AI_REFUSE_DEAL',
                 'HUMAN_ACCEPT_DEAL', 'HUMAN_REFUSE_DEAL')
# Human answer path in the loaded XP2 DiplomacyDealView (0cd3b32a):
# accept = incoming action in {ACCEPTED,PROPOSED,ADJUSTED} + AreWorkingDealsEqual
#          -> SendWorkingDeal(ACCEPTED) (emits POSITIVE natively); deals
#          differ -> ADJUSTED; otherwise re-PROPOSE. Refuse = session found
#          BEFORE any send, HasPendingDeal -> CLOSED, else REJECTED only if
#          initiator ~= local, then CloseSession. A received offer is valid
#          only with DealAction==PROPOSED from the peer (native source
#          557445ff: INITIAL alone proves nothing).
ANSWER_ACTIONS = ('ACCEPTED', 'REJECTED', 'REJECTED_PERMANENT', 'CLOSED', 'ADJUSTED')

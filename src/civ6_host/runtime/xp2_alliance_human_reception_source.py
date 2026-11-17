"""Static source facts for a human seat receiving a MAKE_DEAL proposal.

SOURCE-ONLY module (lot 98d405f3): it pins the native statement wire of a
received deal and the official UI images, without wiring any session,
borrowed seat or candidate. The custom UI handler for MAKE_DEAL is registered
outside the default handler (native_diplomacy_default denies
CUSTOM_HANDLERS = MAKE_DEAL/MAKE_DEMAND, proof sha 7e8623c3...); no DealScreen
lua is captured in our packages (no Steam install here), so the human-side UI
handler is NOT pinned and is never simulated.
"""
from __future__ import annotations

# Native statement wire of a deal received on the AI seat (target-to-local
# acknowledgement), pinned by evidence/host-xp2-empty-deal-statement-native-
# source.json (sha 4f56dd2c...). This is the AI-seat wire only: the H2H
# payload/runner envelopes (INITIAL/ACKNOWLEDGE, PROPOSED/REJECTED/CLOSED
# with pair+sid) come from the support worker's native runner source on the
# installed Core and are NOT asserted here.
STATEMENT_SOURCE = ('evidence/host-xp2-empty-deal-statement-native-source.json',
                    '4f56dd2c6e0adf29cdb85ead16d96b336d3ef3721018d0299871aa9cb2820ae9')
DRAFT_SOURCE = ('evidence/host-xp2-major-deal-draft-source.json',
                '7f092d94fefea923358c98390bfa318016796ca76c1ff43b87cd87b08f913985')
DISPATCH_KIND = 4235402789
STATEMENT_TYPE = 2229918858          # MAKE_DEAL
SUBTYPE = 3069842052
RESPONSE_TYPE = 3405713603
WIRE_PLAYER_ORDER = 'target-to-local-acknowledgement'
NATIVE_VARIANT_TYPE = 22
NATIVE_VARIANT_FLAGS = 1090519040
DEAL_ACTION = 0
RESPONDING_TO_DEAL_ACTION = 0
EXTRA_KEYS = {'encoded_native_deal': 653299807, 'DealAction': 1009080843,
              'RespondingToDealAction': 4263390813}
DEAL_POINTER_ROLE = 'serialized through deal object virtual slot 0x1c0; leave opaque in native argument map'

# Official UI pins (same chain as the alliance dispatch lot).
VIEW_SHA256 = '246409606568dc3f6f2b913334dbc626d9b59e81efc02df0d28409a6ae959cfc'
XP1_VIEW_SHA256 = 'aee6e35dba8a732a7a98674153965bd197fe90f4cfee3c51fecaf57167dc0e6a'
XP2_VIEW_SHA256 = '652552cff5f5bb18634ed16ce4951a4f18d4ca33e7085b18371490b4555d2648'
ALLIANCE_ROW_SHA256 = '34990895aecfa4330b026939fc214b8f041caa231ecdc0f69ee9b8b86e4772aa'
ALLIANCE_TAB_SHA256 = '560ba69ff03e0d26b557083da104c161357e7c705a2ece1555484a48fa13a591'
CORE_SHA256 = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
READBACK_PROOF_SHA256 = 'be15eca6792e6c10675d4a9931de7ad12d262a5b86f035c5bb4d24a91a1b6b07'

# Private UI drop (FTP, aes zip sha 44a357d2..., embedded MANIFEST sha
# 3195e4b127b4..., 11 scripts byte-exact verified): the real deal UI is
# DiplomacyDealView (DealScreen.lua does NOT exist), plus ribbon support.
UI_DROP_SHA256 = '44a357d2957dc50a8c4e7ca0be1340b7d6738dee8134fa0bb937ba1a953efce9'
UI_MANIFEST_SHA256 = '3195e4b127b42c2997739e4bb8177042ea749f4a0383daa2e009d1a7c833599f'
DEAL_VIEW_SHA256 = '34f5054482ba8afaf4d1641eeb2d5c7cc0819238a0b7fb807bfc0ce9d3ed7686'
DEAL_VIEW_XP1_SHA256 = '0cd3b32a80725067e3c0d73a2dbab75ad968dd0cec8858fa297c07e85ceaf705'
DEAL_VIEW_XP2_SHA256 = 'b873237d444943b66c81113d520e04f8f93a5a15121e1d50470f56855d2d5e01'
RIBBON_SHA256 = '120f9f54161d41510a1f3c031b1a0284ee0b91289923d25b395baf3729a3477c'
RIBBON_SUPPORT_SHA256 = 'c91b6f49d1a8e176dcd64ada171e33c490164bfcc442ec6d5fa4f3af1779be2b'

# Custom MAKE_DEAL handler, registered in the base DiplomacyActionView.lua
# (VIEW_SHA256) lines 2627-2629: SetDefaultHandlers("MAKE_DEAL");
# StatementHandlers["MAKE_DEAL"].ApplyStatement = MakeDeal_ApplyStatement;
# .TestValid = MakeDeal_TestValid. Reception: on an INITIAL/ACKNOWLEDGE
# response MakeDeal_ApplyStatement (line 2545) calls ApplyStatement then
# LuaEvents.DiploPopup_ShowMakeDeal(ms_OtherPlayerID) -> the deal UI opens on
# the INCOMING working deal. Returning HUMAN_ACCEPT_DEAL/HUMAN_REFUSE_DEAL
# with a human counterparty closes the session via
# DiplomacyManager.CloseSession(ms_ActiveSessionID).
MAKE_DEAL_HANDLER_REGISTRATION = ('Base/Assets/UI/DiplomacyActionView.lua', 2627)

# Human answer path in DiplomacyDealView (DEAL_VIEW_SHA256): accept =
# OnProposeOrAcceptDeal -> AreWorkingDealsEqual -> SendWorkingDeal(ACCEPTED)
# (which also sends the POSITIVE response statement natively); refuse =
# OnRefuseDeal -> SendWorkingDeal(REJECTED) then CloseSession; cancel =
# SendWorkingDeal(CLOSED). Refusal of an AI-initiated deal uses
# AddResponse(sessionID, local, "NEGATIVE") instead.
ANSWER_ACTIONS = ('ACCEPTED', 'REJECTED', 'REJECTED_PERMANENT', 'CLOSED')

# DealProposalAction enum pinned by the deal pipeline (_SEND in deal_gold):
# ACCEPTED=1, REJECTED=2, ADJUSTED=3, PROPOSED=4, DEMANDED=5, EQUALIZE=6,
# INSPECT=7, EQUALIZE_FAILED=10.
DEAL_ACTIONS = {'ACCEPTED': 1, 'REJECTED': 2, 'ADJUSTED': 3, 'PROPOSED': 4,
                'DEMANDED': 5, 'EQUALIZE': 6, 'INSPECT': 7, 'EQUALIZE_FAILED': 10}

# MAKE_DEAL-family statement subtypes (official DiplomacySelections): the
# received-deal dialogues offer only CHOICE_EXIT; the answer itself is sent
# from the deal screen via SendWorkingDeal on the incoming working deal.
# These are the AI-seat subtypes; the H2H subtype set is not asserted here.
DEAL_SUBTYPES = ('MAKE_DEAL_AI_ACCEPT_DEAL', 'MAKE_DEAL_AI_REFUSE_DEAL',
                 'MAKE_DEAL_AI_ACCEPT_DEMAND', 'MAKE_DEAL_AI_REFUSE_DEMAND')

# Stable local copy of the private UI drop (verified byte-exact against the
# embedded MANIFEST, sha 3195e4b127b4...).
UI_DROP_ROOT = 'C:/civ6-private/alliances-ui-drop/3195e4b127b4'

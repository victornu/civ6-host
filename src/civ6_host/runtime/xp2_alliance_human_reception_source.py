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

# Native statement wire of a received (empty) deal, pinned by
# evidence/host-xp2-empty-deal-statement-native-source.json (sha 4f56dd2c...).
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

# DealProposalAction enum pinned by the deal pipeline (_SEND in deal_gold):
# ACCEPTED=1, REJECTED=2, ADJUSTED=3, PROPOSED=4, DEMANDED=5, EQUALIZE=6,
# INSPECT=7, EQUALIZE_FAILED=10.
DEAL_ACTIONS = {'ACCEPTED': 1, 'REJECTED': 2, 'ADJUSTED': 3, 'PROPOSED': 4,
                'DEMANDED': 5, 'EQUALIZE': 6, 'INSPECT': 7, 'EQUALIZE_FAILED': 10}

# MAKE_DEAL-family statement subtypes (official DiplomacySelections): the
# received-deal dialogues offer only CHOICE_EXIT; the answer itself is sent
# from the deal screen via SendWorkingDeal on the incoming working deal.
DEAL_SUBTYPES = ('MAKE_DEAL_AI_ACCEPT_DEAL', 'MAKE_DEAL_AI_REFUSE_DEAL',
                 'MAKE_DEAL_AI_ACCEPT_DEMAND', 'MAKE_DEAL_AI_REFUSE_DEMAND')

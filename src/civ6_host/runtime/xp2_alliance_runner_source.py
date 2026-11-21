"""Static source facts for the XP2 human MAKE_DEAL runner/transport lane.

SOURCE-ONLY module (orchestrator lane "runner-facts", branch
feat/xp2-alliance-actions): pins the native runner/transport facts of a
human MAKE_DEAL conversation on Core092 (GameCore_XP2_FinalRelease.dll,
sha 4de40abf7c739f53c1f3f825863ace84dc220e5a42d87620e56fceaf3fbd4dc8)
plus the official answer path in the loaded XP2 deal view. No native
execution, no receiver install, no mutation: constants and hashes only.
File bytes are pure ASCII.

Every constant cites its source through SOURCES below. MCP handoff paths
are relative to the file-exchange share root (handoffs/...); the two local
paths are relative to CIV6_HOST_RESOURCE_ROOT (C:\\civ6-current). For .b64
deposits, sha_b64 is the SHA-256 of the deposited .b64 bytes and sha_decoded
the SHA-256 of the base64-decoded bytes (all five decode to UTF-8 readable
payloads). For the two local plain files there is no base64 layer, so the
deposited bytes are the readable bytes and both slots carry the file SHA.
AES key files were never read (existence check only).
"""

from __future__ import annotations

# name -> (path, sha256 of the .b64 as deposited, sha256 of the decoded bytes)
SOURCES = {
    'human_make_deal_native_py': (
        'handoffs/private-env/alliances/human-make-deal-native/124a5898edae/'
        'xp2_human_make_deal_native_source.py.b64',
        '730a2f108b6f642c493740d6ad96852f1069602dfcd8eb43c55314c5b80c532f',
        '43a3c39bab0d79ac6cabbb368d59bf838504a6772985351eb6f0016be641cc67'),
    'human_make_deal_native_json': (
        'handoffs/private-env/alliances/human-make-deal-native/124a5898edae/'
        'host-xp2-human-make-deal-native-source.json.b64',
        '793b581cb0bd9fe71cafea7c8d06a8e6d6d27f6011ada232e15e5aa377bda587',
        '124a5898edae9d37c814ee3bb8a37d8c0ab859d51592be5d3001e280ba4e7efa'),
    'human_make_deal_proposed_py': (
        'handoffs/private-env/alliances/human-make-deal-proposed/5bba696d21b6/'
        'xp2_human_make_deal_proposed.py.b64',
        '8ea719ae56587e42c32a4a086653d75cb5032b20be9e3c2b96b778af1c3223b7',
        '7e319903e088dcb8a03bae821033db62ac9900154df8e24bf9af32b1a9fe460a'),
    'human_make_deal_resume_py': (
        'handoffs/private-env/alliances/human-make-deal-resume/d6055dc5d500/'
        'xp2_human_make_deal_resume.py.b64',
        '19e187cfdcd35f6a23a5d159e63bd8121b1d035d10dff9b4eeaf9d74cf8108e4',
        '69682bc6bd5acb29f8fea289267d47cef9e09a9e5c712b028cc68c006485b457'),
    'alliance_readback_py': (
        'handoffs/private-env/alliances/readback/'
        '92fa450c5d39240f29071e3b55caeaaf9de43ce9474e18f8e2c339940ff20660/'
        'xp2_alliance_readback_source.py.b64',
        '47751699ed5e6d723ae1939f11575bcff33c7e7d6ac5de124a285a8a6742544c',
        '92fa450c5d39240f29071e3b55caeaaf9de43ce9474e18f8e2c339940ff20660'),
    'ui_drop_manifest': (
        'work/alliances-ui-drop/3195e4b127b4/MANIFEST.json',
        '3195e4b127b42c2997739e4bb8177042ea749f4a0383daa2e009d1a7c833599f',
        '3195e4b127b42c2997739e4bb8177042ea749f4a0383daa2e009d1a7c833599f'),
    'empty_deal_statement_json': (
        'evidence/host-xp2-empty-deal-statement-native-source.json',
        '4f56dd2c6e0adf29cdb85ead16d96b336d3ef3721018d0299871aa9cb2820ae9',
        '4f56dd2c6e0adf29cdb85ead16d96b336d3ef3721018d0299871aa9cb2820ae9'),
}

# ---------------------------------------------------------------------------
# 1. RequestSession (human_make_deal_native_json request_callback.0, and the
#    124a5898edae README "Open" row). The official three-argument Lua
#    RequestSession zeroes the payload argument at rva 0x6952cc (6902224);
#    request start then assigns INITIAL (2124225610) with both action fields
#    zeroed by the MAKE_DEAL constructor. A NIL payload plus INITIAL only
#    opens the conversation: it proves neither PROPOSED nor any incoming item.
# ---------------------------------------------------------------------------
REQUEST_SESSION_RVA = 0x6952CC            # 6902224 = request_callback.0
REQUEST_SESSION_PAYLOAD = 'NIL'           # payload argument zeroed at 0x6952cc
REQUEST_INITIAL_RESPONSE_TYPE = 0x7E9D1C4A  # 2124225610 = INITIAL key
REQUEST_INITIAL_PROVES_NOTHING = True     # action 0: conversation opener only

# ---------------------------------------------------------------------------
# 2. SendWorkingDeal chain (human_make_deal_native_json native_spans):
#    send_working_deal_thunk 0x693be0 (6896608, 5 bytes) ->
#    send_working_deal_lua  0x6d1e80 (7151232, 200 bytes) ->
#    send_working_deal      0x58bfb0 (5816240, 943 bytes).
# ---------------------------------------------------------------------------
SEND_WORKING_DEAL_CHAIN = (0x693BE0, 0x6D1E80, 0x58BFB0)

# ---------------------------------------------------------------------------
# 3. Human terminal pair archive (human_make_deal_native_json
#    envelopes.terminal_pair_archive): archive kind 0xf06250e4 (4032975076),
#    header words (kind, action, from, to), native deal at offset 16, and
#    carries_session_id False: the archive carries action/from/to/deal WITHOUT
#    any sid. eligible_actions [1, 2, 8, 12] =
#    ACCEPTED / REJECTED / CLOSED / REJECTED_PERMANENT.
# ---------------------------------------------------------------------------
HUMAN_ARCHIVE_KIND = 0xF06250E4           # 4032975076
HUMAN_ARCHIVE_HEADER = ('kind', 'action', 'from', 'to')
HUMAN_ARCHIVE_DEAL_OFFSET = 16
HUMAN_ARCHIVE_CARRIES_SID = False
HUMAN_ARCHIVE_ACTIONS = (1, 2, 8, 12)
# DealProposalAction values (native json "actions"; ADJUSTED=3 is used by the
# XP2 answer path below and pinned with the sibling reception source):
DEAL_ACTIONS = {'ACCEPTED': 1, 'REJECTED': 2, 'ADJUSTED': 3, 'PROPOSED': 4,
                'CLOSED': 8, 'REJECTED_PERMANENT': 12}
DEAL_ACTION_CLOSED = 8
DEAL_ACTION_REJECTED_PERMANENT = 12

# ---------------------------------------------------------------------------
# 4. Runner event and close-before-publish (124a5898edae README "Statement
#    receive"/"Complete" rows + human_make_deal_native_json): the runner
#    publishes through vtable slot +0x28 and event 0xfc731e25 (4235402789 =
#    envelopes.received_statement.host_event; the same dispatch kind appears
#    in empty_deal_statement_json). On the human terminal route the runner
#    at 0x18b420 instead closes by the RETAINED sid BEFORE publishing
#    0xfc731e25: closure must be confirmed on the retained instance, never
#    inferred from a terminal event or from a successful command return.
# ---------------------------------------------------------------------------
RUNNER_EVENT = 0xFC731E25                 # 4235402789
RUNNER_TERMINAL_RVA = 0x18B420            # human terminal route
RUNNER_CLOSES_BY_RETAINED_SID_BEFORE_PUBLISH = True

# ---------------------------------------------------------------------------
# 5. sid calculation / anti-stale (human_make_deal_native_json "session" +
#    124a5898edae README): pair_key_rva 0x188c00 (1608704) is symmetric in the
#    two player IDs (smaller ID in the high word) and the same pair can REOPEN
#    with that same sid (same_pair_can_reuse_sid True). sid+pair alone prove
#    nothing: anti-stale requires event_sequence, the turn/generation, the
#    lifetime phase and the authenticated deal before any mutation. Native
#    session existence is READ (DiplomacyManager.IsSessionIDOpen /
#    FindOpenSessionID in human_make_deal_resume_py), never computed to
#    fabricate a proof.
# ---------------------------------------------------------------------------
SID_CALC_RVA = 0x188C00                   # 1608704 = pair_key_rva
SAME_PAIR_CAN_REUSE_SID = True
ANTI_STALE_REQUIRED = ('event_sequence', 'turn_or_generation',
                       'lifetime_phase', 'authenticated_deal')
NATIVE_EXISTENCE_READ_NOT_COMPUTED = True

# ---------------------------------------------------------------------------
# 6. Answer path in the loaded XP2 deal view (ui_drop_manifest: 11 scripts
#    byte-exact + MANIFEST 3195e4b127b4...; the GS-loaded deal UI is
#    DLC/Expansion2/UI/Replacements/DiplomacyDealView.lua, sha 0cd3b32a...).
#    Accept = OnProposeOrAcceptDeal (lines 526-585): incoming action in
#    {ACCEPTED, PROPOSED, ADJUSTED} (line 537) AND AreWorkingDealsEqual
#    (line 539) -> SendWorkingDeal(ACCEPTED) (line 544); deals differ ->
#    SendWorkingDeal(ADJUSTED) (line 581). Refuse = OnRefuseDeal (lines
#    589-668): the open session is looked up BEFORE any send
#    (FindOpenSessionID line 599); human peer with HasPendingDeal ->
#    SendWorkingDeal(CLOSED) (line 633), else REJECTED only when the
#    initiator is not the local player (lines 635/637), then
#    CloseSession(sessionID) (line 641). The official UI calls
#    DealManager.SendWorkingDeal(...) as a bare statement (lines 544/581/633/
#    637) and never reads its return value.
# ---------------------------------------------------------------------------
UI_DROP_REL = 'work/alliances-ui-drop/3195e4b127b4'
UI_MANIFEST_SHA256 = '3195e4b127b42c2997739e4bb8177042ea749f4a0383daa2e009d1a7c833599f'
DEAL_VIEW_XP2_REL = 'DLC/Expansion2/UI/Replacements/DiplomacyDealView.lua'
DEAL_VIEW_XP2_SHA256 = '0cd3b32a80725067e3c0d73a2dbab75ad968dd0cec8858fa297c07e85ceaf705'
ANSWER_ACCEPT_INCOMING_ACTIONS = ('ACCEPTED', 'PROPOSED', 'ADJUSTED')
ANSWER_ACCEPT_REQUIRES_EQUAL_WORKING_DEALS = True   # AreWorkingDealsEqual
ANSWER_ACCEPT_SENDS = 'ACCEPTED'
ANSWER_ACCEPT_ELSE_SENDS = 'ADJUSTED'
ANSWER_REFUSE_SESSION_BEFORE_SEND = True            # FindOpenSessionID first
ANSWER_REFUSE_PENDING_SENDS = 'CLOSED'              # HasPendingDeal branch
ANSWER_REFUSE_ELSE_SENDS = 'REJECTED'               # only if initiator != local
ANSWER_REFUSE_THEN_CLOSES_SESSION = True            # CloseSession(sessionID)
SEND_WORKING_DEAL_RETURN_IGNORED_BY_UI = True

# Private UI drop, 11 scripts verified byte-exact against MANIFEST.json
# (sha 3195e4b127b4...), resolved under CIV6_HOST_RESOURCE_ROOT.
UI_DROP_FILES = {
    'Base/Assets/UI/DiplomacyRibbon.lua':
        '120f9f54161d41510a1f3c031b1a0284ee0b91289923d25b395baf3729a3477c',
    'Base/Assets/UI/DiplomacyActionView.lua':
        '246409606568dc3f6f2b913334dbc626d9b59e81efc02df0d28409a6ae959cfc',
    'Base/Assets/UI/DiplomacyStatementSupport.lua':
        'b9d573f6a93a8dc43bc8804b4faf53510dcbe795862f64dece76e1434bc5a0fb',
    'DLC/Expansion2/UI/Replacements/DiplomacyActionView_Expansion1.lua':
        'aee6e35dba8a732a7a98674153965bd197fe90f4cfee3c51fecaf57167dc0e6a',
    'DLC/Expansion2/UI/Replacements/DiplomacyActionView_Expansion2.lua':
        '652552cff5f5bb18634ed16ce4951a4f18d4ca33e7085b18371490b4555d2648',
    'DLC/Expansion2/UI/Additions/DiplomacyActionView_AllianceRow.lua':
        '34990895aecfa4330b026939fc214b8f041caa231ecdc0f69ee9b8b86e4772aa',
    'DLC/Expansion2/UI/Additions/DiplomacyActionView_AllianceTab.lua':
        '560ba69ff03e0d26b557083da104c161357e7c705a2ece1555484a48fa13a591',
    'Base/Assets/UI/DiplomacyDealView.lua':
        '34f5054482ba8afaf4d1641eeb2d5c7cc0819238a0b7fb807bfc0ce9d3ed7686',
    'Base/Assets/UI/DiplomacyRibbonSupport.lua':
        'c91b6f49d1a8e176dcd64ada171e33c490164bfcc442ec6d5fa4f3af1779be2b',
    'DLC/Expansion2/UI/Replacements/DiplomacyDealView.lua':
        '0cd3b32a80725067e3c0d73a2dbab75ad968dd0cec8858fa297c07e85ceaf705',
    'DLC/Expansion2/UI/Replacements/DiplomacyDealView_Expansion2.lua':
        'b873237d444943b66c81113d520e04f8f93a5a15121e1d50470f56855d2d5e01',
}

# AI-seat empty-statement wire (empty_deal_statement_json): the received
# MAKE_DEAL acknowledgement dispatches under kind 4235402789 == 0xfc731e25
# with statement_type 2229918858 (MAKE_DEAL), subtype NONE, response
# ACKNOWLEDGE, deal_action 0, target-to-local order, deal variant tag 22
# flags 0x41000000.
EMPTY_STATEMENT_DISPATCH_KIND = 0xFC731E25   # 4235402789

"""Source-selected XP1 result reads using the shared facts and victory policy.

The selected proof covers getter registration/bodies, not a terminal write or
write-before-notification transition. No facts are synthesized. Game termination
is the existing first-observed-winner episode policy, never an engine-halt claim.
"""
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from .xp1_status_profiles import SOURCE, bind_owner, source_dependencies,source_reference

BASE_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
RESULT_PROFILE = 'xp1-status-observation-v1'


def verify_reader_source(core_sha256):
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unqualified result reader engine')
    from .xp1_status_profiles import verify_source
    return verify_source(core_sha256)


def result_provenance(core_sha256):
    """Explicit expected wire identity; never select from untrusted reply data."""
    if core_sha256 == BASE_CORE_SHA256:
        from .native.native_victory_episode import PROOF_SHA256
        from .native.native_episode_facts import PROOF_SHA256 as FACTS_SHA
        return dict(source_proof_sha256=PROOF_SHA256,facts_source_proof_sha256=FACTS_SHA)
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unqualified result provenance engine')
    selected=source_reference(core_sha256)
    return dict(source_proof_sha256=selected[1],facts_source_proof_sha256=selected[1],
        result_source_profile=(RESULT_PROFILE if core_sha256==XP1_CORE_SHA256 else 'xp2-status-observation-v1'),
        core_sha256=core_sha256,
        native_write_before_notification_qualified=False,native_terminal_transition_qualified=False)


def bind_facts_provenance(value, core_sha256):
    if core_sha256 == BASE_CORE_SHA256:
        return value
    provenance = result_provenance(core_sha256)
    value['source_proof_sha256'] = provenance['facts_source_proof_sha256']
    value.update({k:v for k,v in provenance.items()
                  if k not in ('source_proof_sha256','facts_source_proof_sha256')})
    return value


def bind_policy_provenance(value, core_sha256):
    if core_sha256 != BASE_CORE_SHA256:
        value.update(result_provenance(core_sha256))
    return value


def read(saved, player_id=None):
    """Read the current local UI result from one exact live SavedLoadOwner."""
    from .xp1_saved_load_owner import SavedLoadOwner
    from .native.native_episode_identity import require_episode
    from .native import native_winning_team as winning, native_episode_facts as facts
    from .native.native_victory_episode import FirstOfficialVictory
    if type(saved) is not SavedLoadOwner:
        raise TypeError('Result read requires the exact saved-Load owner')
    saved._check('commands',requested='unit_commands_candidate')
    b,p,c = saved.backend,saved.prefix,saved.continuation
    core_sha256=b.load_abi.core_sha256
    verify_reader_source(core_sha256)
    c.check(active=False);c.transport.require_empty_native_queue();b.control(empty=True)
    identity = require_episode(p)
    current = c.observation
    local,turn = current['player_id'],current['turn']
    if player_id is None:player_id = local
    if type(player_id) is not int or player_id != local:
        raise ValueError('Additional XP1 result perspective is not qualified')
    bound = bind_owner(b,saved.core,b.runtime.read)
    if bound.owner is not b or bound.core is not saved.core or bound.core_sha256 != core_sha256:
        raise ValueError('Result source lost its exact backend/module owner')
    policy = getattr(p,'_first_official_victory_policy',None)
    if policy is not None and (type(policy) is not FirstOfficialVictory
            or policy.episode_id != identity.episode_id
            or policy._core_sha256 != core_sha256):
        raise ValueError('Result policy belongs to another episode or engine')
    with saved._attempt():
        first = winning.parse(p.runtime.evaluate_text(p.ui_child,
            winning.source(core_sha256=core_sha256),b'@xp1_session_winner',capacity=48))
        payload = p.runtime.evaluate_text(p.ui_child,
            facts.build_source(player_id,turn,core_sha256=core_sha256),
            b'@xp1_session_episode_facts',capacity=facts.MAX_RESPONSE)
        parsed = facts.parse_facts(payload,player_id,turn,core_sha256=core_sha256)
        if first != {key:parsed[key] for key in ('winner_present','winning_team','victory_type')}:
            raise ValueError('Consecutive native XP1 winner reads disagree')
        c.check(active=False);c.transport.require_empty_native_queue();b.control(empty=True)
        if policy is None:
            policy = FirstOfficialVictory(identity.episode_id,core_sha256=core_sha256)
            p._first_official_victory_policy = policy
        result = policy.observe(payload,player_id,turn)
        result['game_generation'] = identity.game_generation
        p.emit('native_victory_episode_policy_observed',result=result,
               engine_state_modified=False,eligible_for_training=False)
    return result

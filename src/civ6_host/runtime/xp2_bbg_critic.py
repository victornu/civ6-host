"""Opt-in private critic trace for one admitted BBG LAN profile."""

from hashlib import sha256
import os
from pathlib import Path

from . import xp2_bbg_inputs
from .native import native_privileged_snapshot977 as collector
from .native.native_episode_identity import require_episode
from .saved_load_profiles import XP2_CORE_SHA256
from .xp1_session_inputs import SAVED_LOAD_CLOSURE_ENV


def source_files():
    return Path(__file__).resolve(), Path(collector.__file__).resolve()


class CriticReadback:
    def __init__(self, closure, path):
        reference = dict(zip(('path', 'sha256'), xp2_bbg_inputs.REFERENCE))
        transport = closure['stdout_transport']
        if (closure.get('privileged_critic_diagnostic') is not True
                or closure.get('input_profile') != 'xp2-lan'
                or closure.get('official_bundle') != reference
                or transport['core_sha256'] != XP2_CORE_SHA256):
            raise ValueError('The LAN critic diagnostic requires the exact BBG XP2 capture')
        self.path = Path(path).resolve()
        self.closure_sha256 = sha256(self.path.read_bytes()).hexdigest()
        if self.closure_sha256 != os.environ.get(SAVED_LOAD_CLOSURE_ENV):
            raise ValueError('LAN critic closure differs from the admitted session')
        for source in source_files():
            if closure['pins'].get(str(source)) != sha256(source.read_bytes()).hexdigest():
                raise ValueError('LAN critic source differs from its closure pin')
        self.collector_sha256 = closure['pins'][str(source_files()[1])]
        self.host_sha256 = transport['host_sha256']

    def emit_ready(self, owner, response, emit):
        decisions = response['decisions']
        turn_controls = decisions['turn_controls']
        if not (turn_controls['active'] and turn_controls['active_complete']):
            return
        observation = response['observation']
        player, turn = observation['player_id'], observation['turn']
        prefix = owner.prefix
        continuation = owner.continuation
        continuation.check(active=False)
        continuation.transport.require_empty_native_queue()
        identity = require_episode(prefix)
        if ((identity.episode_id, identity.game_generation) !=
                (response['episode_id'], response['game_generation'])
                or response['session']['human_player_ids'] != [player]):
            raise ValueError('LAN critic read requires the exact captured human boundary')
        raw = prefix.runtime.evaluate_text(prefix.ui_child, collector._source_for(player, turn),
                                           b'@privileged_critic_snapshot977', capacity=collector.MAX_BYTES)
        payload = collector.parse_payload(raw, player_id=player, turn=turn)
        continuation.check(active=False)
        continuation.transport.require_empty_native_queue()
        if require_episode(prefix) is not identity:
            raise ValueError('LAN critic read crossed its episode')
        own_units = {(u['id'], u['type'], u['x'], u['y']) for u in payload['units'] if u['owner'] == player}
        public_units = {(u['id'], u['type'], u['x'], u['y']) for u in observation['units']}
        own_gold = next(p['gold'] for p in payload['players'] if p['player_id'] == player)
        if own_units != public_units or own_gold != observation['economy']['gold']:
            raise ValueError('LAN critic snapshot does not match the public seat')
        emit('privileged_critic_snapshot977', schema=collector.SCHEMA,
             episode_id=identity.episode_id, game_generation=identity.game_generation,
             player_id=player, sequence=response['sequence'], turn=turn,
             core_sha256=XP2_CORE_SHA256, host_sha256=self.host_sha256,
             closure_sha256=self.closure_sha256, collector_source_sha256=self.collector_sha256,
             snapshot=payload)

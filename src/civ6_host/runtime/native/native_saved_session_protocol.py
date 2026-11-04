"""Strict local protocol for an explicitly diagnostic saved-game session."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
SCHEMA = 'civ6rl.saved_session913.v1'
OPERATIONS = frozenset(('observe', 'found_city', 'diagnostic_development_turn', 'close'))
MAX_EXPLICIT_ROUNDS = 1024
MAX_EXPLICIT_COMMANDS = 4096

class SessionProtocol:
    require_city = True
    max_round_limit = 8
    max_commands = 32

    def __init__(self, identity, nonce, round_limit=8):
        if type(identity) is not DiagnosticEpisodeIdentity:
            raise ValueError('Native episode identity required')
        if type(nonce) is not str or len(nonce) != 32 or any((c not in '0123456789abcdef' for c in nonce)):
            raise ValueError('Session nonce must be 32 lowercase hex digits')
        if type(round_limit) is not int or not 1 <= round_limit <= self.max_round_limit:
            raise ValueError('Invalid configured diagnostic round limit')
        self.identity = identity
        self.nonce = nonce
        self.limit = round_limit
        self.sequence = 0
        self.rounds = 0
        self.city = False
        self.ended = False
        self.closed = False

    def validate(self, request):
        fields = {'schema', 'nonce', 'episode_id', 'game_generation', 'sequence', 'operation'}
        if type(request) is not dict or set(request) != fields:
            raise ValueError('Malformed session command')
        if request['schema'] != SCHEMA or request['nonce'] != self.nonce or request['episode_id'] != self.identity.episode_id or (request['game_generation'] != self.identity.game_generation):
            raise ValueError('Stale or foreign episode command')
        if type(request['sequence']) is not int or request['sequence'] != self.sequence + 1 or request['sequence'] > self.max_commands or self.closed:
            raise ValueError('Out-of-order or closed session command')
        op = request['operation']
        if type(op) is not str or op not in OPERATIONS:
            raise ValueError('Unsupported diagnostic operation')
        if self.ended and op != 'close':
            raise ValueError('Episode ended; reset required')
        if op == 'found_city' and (self.city or self.rounds):
            raise ValueError('City already founded')
        if op == 'diagnostic_development_turn' and (self.require_city and (not self.city) or self.rounds >= self.limit):
            raise ValueError('Turn requires a city and remaining diagnostic budget')
        return op

    def commit(self, request, *, native_terminated=False):
        op = self.validate(request)
        if type(native_terminated) is not bool:
            raise ValueError('Exact native terminal flag required')
        self.sequence = request['sequence']
        if op == 'found_city':
            self.city = True
        if op == 'diagnostic_development_turn':
            self.rounds += 1
        self.closed = op == 'close'
        self.ended = native_terminated or self.rounds == self.limit or self.closed

def outcome(native, rounds, limit, *, closed=False, maximum=8):
    if type(maximum) is not int or not 1 <= maximum <= MAX_EXPLICIT_ROUNDS or type(rounds) is not int or (type(limit) is not int) or (not 0 <= rounds <= limit <= maximum) or (limit < 1) or (type(closed) is not bool):
        raise ValueError('Exact bounded diagnostic counters required')
    if type(native) is not dict or native.get('schema') != 'civ6rl.native_victory_episode.observation.v1' or type(native.get('episode_terminated')) is not bool or (type(native.get('winner_present')) is not bool) or (native['episode_terminated'] != native['winner_present']):
        raise ValueError('Verified native victory policy receipt required')
    terminated = native['episode_terminated']
    reason = 'official_native_victory' if terminated else 'diagnostic_round_limit' if rounds == limit else 'requested_close' if closed else None
    return dict(terminated=terminated, truncated=not terminated and reason is not None, reason=reason, native_victory=native, global_engine_terminal=None, strategic_training_ready=False)

def validate_response(response, protocol, operation, *, request=None, expected_player=0, initial_turn=1):
    """Check the pipe envelope before committing the parent's request counter."""
    from civ6_host.runtime.native.native_victory_episode import POLICY_ID
    from civ6_host.runtime.native.native_victory_episode import PROOF_SHA256
    from civ6_host.runtime.native.native_episode_facts import PROOF_SHA256 as FACTS_SHA
    if type(expected_player) is not int or not 0 <= expected_player <= 63 or type(initial_turn) is not int or (not 0 <= initial_turn <= 100000):
        raise ValueError('Invalid explicit response perspective or initial turn')
    fields = {'stage', 'schema', 'nonce', 'episode_id', 'game_generation', 'sequence', 'operation', 'observation', 'rounds', 'outcome', 'automatic_choices_applied', 'action_interface_complete', 'strategic_training_ready'}
    if type(response) is not dict or set(response) != fields:
        raise ValueError('Malformed session response')
    expected_sequence = 0 if operation == 'reset' else protocol.sequence + 1
    expected_rounds = protocol.rounds + (operation == 'diagnostic_development_turn')
    if response['stage'] != 'official_session_response' or response['schema'] != SCHEMA or response['nonce'] != protocol.nonce or (response['episode_id'] != protocol.identity.episode_id) or (response['game_generation'] != protocol.identity.game_generation) or (type(response['sequence']) is not int) or (response['sequence'] != expected_sequence) or (response['operation'] != operation) or (type(response['rounds']) is not int) or (response['rounds'] != expected_rounds) or (response['automatic_choices_applied'] is not (operation == 'diagnostic_development_turn')) or (response['action_interface_complete'] is not False) or (response['strategic_training_ready'] is not False):
        raise ValueError('Foreign, out-of-order or unverified session response')
    result = response['outcome']
    if type(result) is not dict:
        raise ValueError('Missing outcome')
    native = result.get('native_victory')
    if type(native) is not dict or native.get('episode_id') != protocol.identity.episode_id or native.get('game_generation') != protocol.identity.game_generation or (native.get('policy_id') != POLICY_ID) or (native.get('source_proof_sha256') != PROOF_SHA256) or (native.get('facts_source_proof_sha256') != FACTS_SHA) or (type(native.get('player_id')) is not int) or (native['player_id'] != expected_player) or (native.get('observation_only') is not True) or (native.get('eligible_for_training') is not False) or (native.get('exposed_to_learner') is not False) or (native.get('global_engine_terminal') is not None) or (native.get('engine_halted') is not None):
        raise ValueError('Native outcome identity or source differs')
    expected = outcome(native, expected_rounds, protocol.limit, closed=operation == 'close', maximum=protocol.max_round_limit)
    if result != expected or type(result.get('terminated')) is not bool or type(result.get('truncated')) is not bool:
        raise ValueError('Outcome classification differs')
    observed = response['observation']
    if observed is None:
        if result['terminated'] is not True:
            raise ValueError('Non-terminal response needs its observation')
    elif type(observed) is not dict or type(observed.get('turn')) is not int or observed['turn'] != native.get('current_game_turn') or (type(observed.get('player_id')) is not int) or (observed['player_id'] != expected_player) or (not result['terminated'] and observed['turn'] != initial_turn + expected_rounds):
        raise ValueError('Observation and native outcome boundaries differ')
    return response

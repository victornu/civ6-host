"""Explicit short native score setup and public bound readback, not a win oracle."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.native import native_game_configuration as config
from civ6_host.runtime.native import native_score_turn_limit as contract
from civ6_host.runtime.native.native_episode_facts import _integer
from civ6_host.runtime.native.native_source_cache import load_pinned_json
MAX_RESPONSE = 128
CONTEXT_PROOF_SHA256 = '6dd4f257de13b97ac15b5f4712c94e545d1230459e07695ae748855ea9323bb0'

def verify_context_source():
    proof = load_pinned_json(contract.ROOT / 'evidence/native-score-configuration-context' / (CONTEXT_PROOF_SHA256 + '.json'), CONTEXT_PROOF_SHA256)
    details = proof.get('contract', {})
    if proof.get('schema') != 'civ6rl.native_score_configuration_context.static.v1' or proof.get('source_turn_limit_sha256') != contract.PROOF_SHA256 or proof.get('images', {}).get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (details.get('reader_callback_va') != '0x18055f900') or (details.get('reader_result_arity') != 1) or (details.get('reader_is_ui_game_cache') is not False) or (details.get('new_native_registration_required') is not False):
        raise RuntimeError('Native score configuration context proof changed')

def _limit(value):
    if type(value) is not int or not 2 <= value <= 32:
        raise ValueError('Short score diagnostic requires an explicit 2..32 turn limit')
    return value

def configure(core_base, context, database, limit, emit):
    """After ruleset/default setup, set the two original options and read them back."""
    selected = contract.plan(_limit(limit))
    records = []
    for key, value in selected['settings']:
        result = config.set_named_integer(core_base, context, database, 'Game', key, value)
        if result['roundtrip_verified'] is not True:
            raise RuntimeError('Custom score option did not persist')
        records.append(result)
    score = config.set_standard_victory_enabled(core_base, context, database, 'VICTORY_SCORE')
    if score['roundtrip_verified'] is not True or score['readback_value'] is not True:
        raise RuntimeError('Native score victory was not enabled')
    emit('native_custom_score_setup_configured', requested_limit=limit, settings=records, score_victory=score, source_proof_sha256=contract.PROOF_SHA256, options_applied_before_new_game=True, effective_end_turn_verified=False, native_victory_inferred=False, eligible_for_training=False)

def readback_source(player_id, turn, limit, published_start_turn):
    if type(player_id) is not int or not 0 <= player_id <= 63:
        raise ValueError('Invalid actor for score-limit readback')
    if type(turn) is not int or not 0 <= turn <= 2147483647:
        raise ValueError('Invalid turn for score-limit readback')
    _limit(limit)
    if type(published_start_turn) is not int or not 0 <= published_start_turn <= turn:
        raise ValueError('Invalid published native start turn')
    contract.verify_source()
    return f'local pid,expectedTurn,limit,start={player_id},{turn},{limit},{published_start_turn}\n'.encode() + _READ
_READ = "\nlocal function integer(label,...)\n assert(select('#',...)==1,'score limit invalid '..label..' arity')\n local v=...\n assert(type(v)=='number' and v%1==0 and v>=0 and v<=2147483647,\n        'score limit invalid '..label)\n return v\nend\nassert(Game and type(Game.GetGameEndTurn)=='function' and\n type(Game.GetCurrentGameTurn)=='function' and type(Game.GetLocalPlayer)=='function' and\n type(Game.GetLocalObserver)=='function','score limit Game API unavailable')\nlocal function context()\n assert(integer('actor',Game.GetLocalPlayer())==pid and\n        integer('observer',Game.GetLocalObserver())==pid and\n        integer('turn',Game.GetCurrentGameTurn())==expectedTurn,\n        'score limit foreign actor or stale context')\nend\ncontext()\nlocal finish=integer('end',Game.GetGameEndTurn())\nlocal score=GameInfo and GameInfo.Victories and GameInfo.Victories['VICTORY_SCORE']\nassert(score and score.VictoryType=='VICTORY_SCORE','score limit victory definition unavailable')\nlocal scoreIndex=integer('score index',score.Index)\nassert(finish==start+limit,'score limit effective end differs: start='..tostring(start)..\n       ', end='..tostring(finish)..', requested='..tostring(limit))\nassert(expectedTurn>=start and expectedTurn<finish,'score limit initial turn outside bound')\ncontext()\nassert(integer('end',Game.GetGameEndTurn())==finish,'score limit snapshot changed')\ncontext()\nreturn string.format('score-limit-v1|%d|%d|%d|%d|%d|%d',pid,expectedTurn,start,finish,limit,scoreIndex)\n".encode('ascii')
_MAX_READ = b"assert(GameConfiguration and type(GameConfiguration.GetMaxTurns)=='function',\n 'score native maximum API unavailable')\nlocal function read(...)\n assert(select('#',...)==1,'score native maximum arity differs')\n local v=...\n assert(type(v)=='number' and v%1==0 and v>=1 and v<=2147483647,\n        'score native maximum invalid')\n return string.format('%.0f',v)\nend\nreturn read(GameConfiguration.GetMaxTurns())"
_START_READ = "\nlocal function integer(label,...)\n assert(select('#',...)==1,'score start invalid '..label..' arity')\n local value=...\n assert(type(value)=='number' and value%1==0 and value>=0 and value<=2147483647,\n        'score start invalid '..label)\n return value\nend\nassert(GameConfiguration and type(GameConfiguration.GetStartTurn)=='function',\n       'score start native configuration API unavailable')\nassert(Game and type(Game.GetCurrentGameTurn)=='function','score start Game API unavailable')\nlocal turn=integer('turn',Game.GetCurrentGameTurn())\nlocal start=integer('start',GameConfiguration.GetStartTurn())\nassert(integer('turn',Game.GetCurrentGameTurn())==turn and\n       integer('start',GameConfiguration.GetStartTurn())==start,'score start snapshot changed')\nreturn string.format('score-start-v1|%d|%d',turn,start)\n".encode('ascii')

def parse_start(payload, expected_turn):
    if type(expected_turn) is not int or not 0 <= expected_turn <= 2147483647:
        raise ValueError('Invalid expected turn for native start readback')
    if type(payload) is not bytes or len(payload) > MAX_RESPONSE:
        raise ValueError('Invalid native start payload')
    parts = payload.split(b'|')
    if len(parts) != 3 or parts[0] != b'score-start-v1':
        raise ValueError('Malformed native start payload')
    turn, start = [_integer(p, 'score start', 0, 2147483647) for p in parts[1:]]
    if turn != expected_turn or start > turn:
        raise ValueError('Native start readback has stale or invalid game turn')
    return start

def parse_readback(payload, player_id, turn, limit):
    _limit(limit)
    if type(player_id) is not int or not 0 <= player_id <= 63 or type(turn) is not int or (not 0 <= turn <= 2147483647):
        raise ValueError('Invalid expected score-limit context')
    if type(payload) is not bytes or len(payload) > MAX_RESPONSE:
        raise ValueError('Invalid score-limit payload')
    parts = payload.split(b'|')
    if len(parts) != 7 or parts[0] != b'score-limit-v1':
        raise ValueError('Malformed score-limit readback')
    pid, actual_turn, start, finish, actual_limit, score_index = [_integer(p, 'score limit', 0, 2147483647) for p in parts[1:]]
    if (pid, actual_turn, actual_limit) != (player_id, turn, limit) or finish != start + limit or (not start <= turn < finish):
        raise ValueError('Score-limit readback differs from explicit setup/context')
    return dict(player_id=pid, current_game_turn=actual_turn, start_turn=start, effective_end_turn=finish, requested_limit=limit, end_turn_exclusive=True, score_victory_index=score_index, score_victory_type='VICTORY_SCORE', effective_bound_verified=True, native_victory_inferred=False, source_proof_sha256=contract.PROOF_SHA256, eligible_for_training=False)

def observe(host, player_id, turn, limit):
    if host.ui_child is None or host.actions.pending or host.deferred_events.pending:
        raise RuntimeError('Score-limit readback requires a drained published player state')
    verify_context_source()
    before = parse_start(host.runtime.evaluate_text(host.game_child, _START_READ, b'@native_score_start_before_ui', capacity=MAX_RESPONSE), turn)
    native_max = _integer(host.runtime.evaluate_text(host.game_child, _MAX_READ, b'@native_score_max_before_ui', capacity=16), 'native configured max', 1, 2147483647)
    host.emit('native_custom_score_configuration_read', player_id=player_id, current_game_turn=turn, start_turn=before, native_configured_max=native_max, requested_limit=limit, effective_end_turn_verified=False, eligible_for_training=False)
    if native_max != limit:
        raise RuntimeError('Native configured maximum differs from requested score diagnostic')
    result = parse_readback(host.runtime.evaluate_text(host.ui_child, readback_source(player_id, turn, limit, before), b'@native_custom_score_bound', capacity=MAX_RESPONSE), player_id, turn, limit)
    after = parse_start(host.runtime.evaluate_text(host.game_child, _START_READ, b'@native_score_start_after_ui', capacity=MAX_RESPONSE), turn)
    after_max = _integer(host.runtime.evaluate_text(host.game_child, _MAX_READ, b'@native_score_max_after_ui', capacity=16), 'native configured max', 1, 2147483647)
    if before != after or result['start_turn'] != before or native_max != after_max:
        raise RuntimeError('Native published start turn changed across UI readback')
    result['start_turn_source'] = 'Original GameConfiguration.GetStartTurn in native gameplay child'
    result['start_turn_unchanged_across_ui_read'] = True
    result['native_configured_max'] = native_max
    result['context_source_proof_sha256'] = CONTEXT_PROOF_SHA256
    host.emit('native_custom_score_bound_verified', **result)
    return result

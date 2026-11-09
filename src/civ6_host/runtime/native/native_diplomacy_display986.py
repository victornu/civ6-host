"""Public rendered diplomatic text, read through the pinned official Lua APIs.

Raw AI causes only enter the official display queries and are never copied
into this public projection.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import json
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_diplomacy_display986.py')))).resolve().parents[1]
SCHEMA = 'civ6rl.diplomacy_public_display986.v2'
_RAW_SCHEMA = 'civ6rl.diplomacy_public_display986.v1'
PROOF_SHA = 'fb80a444174b1bf54a05c5be7329d1cd889c6eae15a24ed6f689fa39a493ea4e'
PROOF = ROOT / 'evidence/native-diplomacy-display' / (PROOF_SHA + '.json')
MAX_BYTES = 131072

def verify_source():
    from civ6_host.runtime.native.native_diplomacy_choices import VIEW_SHA
    from civ6_host.runtime.native.native_diplomacy_choices import SUPPORT_SHA
    from civ6_host.runtime.native.native_diplomacy_choices import official_source
    from civ6_host.runtime.native.native_diplomacy_statement import PROOF_SHA256
    from civ6_host.runtime.native.native_diplomacy_statement import NAMES
    from civ6_host.runtime.native.native_diplomacy_statement import OPAQUE_KEY
    from civ6_host.runtime.native.native_diplomacy_statement import BLOB_KEY
    proof = load_pinned_json(PROOF, PROOF_SHA)
    if proof['schema'] != 'civ6rl.native_diplomacy_display986.static.v1' or proof['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['ui_sha256'] != VIEW_SHA or (proof['support_sha256'] != SUPPORT_SHA) or (proof['statement_source_sha256'] != PROOF_SHA256) or (not proof['validation']['all_captured_instructions_match_pinned_pe']) or (not proof['contract']['from_mood_absent_in_pinned_statement']) or (345504345 in {*NAMES.values(), OPAQUE_KEY, BLOB_KEY}):
        raise ValueError('Diplomatic display source contract changed')
    official_source('DiplomacyActionView.lua', VIEW_SHA)
    official_source('DiplomacyStatementSupport.lua', SUPPORT_SHA)
    return proof

def lua_projection(statement, *, execution_image=None):
    """Tail in the existing default-handler scope (parsed/mood/quote/from/to)."""
    if execution_image is None:
        verify_source()
    else:
        from ..xp2_diplomacy_display_source import source
        source(execution_image=execution_image)
    from civ6_host.runtime.native.native_diplomacy_statement import NAMES
    fields = statement['fields']
    if set(fields) != set(NAMES):
        raise ValueError('Unqualified native statement fields')
    values = [fields[key] for key in ('AiReason', 'AiModifier')]
    if any((type(value) is not int or not 0 <= value <= 4294967295 for value in values)):
        raise ValueError('Invalid internal reason input')
    reason, modifier = [value if value < 2147483648 else value - (1 << 32) for value in values]
    return '\nlocal leaderText,reasonText=\'\',\'\'\nif parsed.StatementText~=nil then\n -- The official view asks for FromMood, absent in this pinned event map.\n -- FromPlayerMood is only used above by ExtractStatement; do not substitute it.\n local key=DiplomacyManager.FindTextKey(parsed.StatementText,from,nil,to)\n assert(type(key)==\'string\',\'Diplomacy text key unavailable\')\n leaderText=Locale.Lookup(key)\n local reasonKey=DiplomacyManager.FindReasonTextKey(parsed.ReasonText,from,%d,%d)\n if reasonKey~=nil then\n  assert(type(reasonKey)==\'string\',\'Malformed public reason key\')\n  reasonText=Locale.Lookup(reasonKey)\n  local agenda=DiplomacyManager.FindReasonAgendaTextKey(from,to,%d,%d)\n  if agenda~=nil then\n   assert(type(agenda)==\'string\',\'Malformed displayed agenda\')\n   reasonText=reasonText..agenda\n  end\n end\nend\nlocal selections={}\nfor _,s in ipairs(parsed.Selections) do\n local tooltip=nil\n if s.IsDisabled==true and s.FailureReasons~=nil then\n  tooltip=Locale.Lookup(s.FailureReasons[1])\n end\n selections[#selections+1]=\'{"key":\'..quote(s.Key)..\',"sort":\'..tostring(s.Sort)..\n  \',"text":\'..quote(Locale.Lookup(s.Text))..\',"disabled":\'..(s.IsDisabled==true and \'true\' or \'false\')..\n  \',"tooltip":\'..quote(tooltip)..\'}\'\nend\nlocal leader=PlayerConfigurations[from]:GetLeaderTypeName()\nreturn \'{"schema":"civ6rl.diplomacy_public_display986.v1","speaker_leader":\'..quote(leader)..\n \',"mood_name":\'..quote(DiplomacySupport_GetMoodName(mood))..\n \',"statement_text":\'..quote(leaderText)..\',"reason_text":\'..quote(reasonText)..\n \',"selections":[\'..table.concat(selections,\',\')..\']}\'\n' % (reason, modifier, reason, modifier)

def parse(raw, data, configuration):
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise ValueError('Unbounded public diplomatic display')
    value = json.loads(raw)
    if type(value) is not dict or set(value) != {'schema', 'speaker_leader', 'mood_name', 'statement_text', 'reason_text', 'selections'} or value['schema'] != _RAW_SCHEMA:
        raise ValueError('Malformed public diplomatic display')
    from_player = data['session']['from_player']
    if value['speaker_leader'] != configuration[from_player]['leader']:
        raise ValueError('Diplomatic speaker differs from restored public configuration')
    for key in ('speaker_leader', 'mood_name', 'statement_text', 'reason_text'):
        text = value[key]
        if text is None and key in ('speaker_leader', 'mood_name'):
            continue
        if type(text) is not str or len(text.encode('utf8')) > 4096 or '\x00' in text:
            raise ValueError('Malformed diplomatic display text: ' + key)
    if type(value['selections']) is not list or len(value['selections']) != len(data['selections']):
        raise ValueError('Diplomatic display menu differs from native choices')
    for row, native in zip(value['selections'], data['selections']):
        if type(row) is not dict or set(row) != {'key', 'sort', 'text', 'disabled', 'tooltip'} or type(row['sort']) is not int or (type(row['disabled']) is not bool) or any((row[k] != native[k] for k in ('key', 'sort', 'disabled'))):
            raise ValueError('Diplomatic display choice identity differs')
        if type(row['text']) is not str or len(row['text'].encode('utf8')) > 4096 or '\x00' in row['text']:
            raise ValueError('Malformed displayed diplomatic choice')
        if row['tooltip'] is not None and (type(row['tooltip']) is not str or len(row['tooltip'].encode('utf8')) > 4096 or '\x00' in row['tooltip']):
            raise ValueError('Malformed displayed diplomatic tooltip')
        if not row['disabled'] and row['tooltip'] is not None:
            raise ValueError('Enabled conversation choice has no official tooltip')
    del value['mood_name']
    for row in value['selections']:
        del row['sort']
    value['schema'] = SCHEMA
    return validate_public(value, data)

def validate_public(value, data):
    """Validate the redacted display and its visible order against the native menu.

    This helper is pure: it does not load the DLL, query localization, or turn
    internal dialogue fields into learned features. Rendered text is bound by
    the enclosing decision digest; parsing binds the speaker to configuration.
    """
    if type(value) is not dict or set(value) != {'schema', 'speaker_leader', 'statement_text', 'reason_text', 'selections'} or value['schema'] != SCHEMA:
        raise ValueError('Malformed public diplomatic projection')

    def text(item, label, *, nullable=False):
        if item is None and nullable:
            return
        if type(item) is not str or len(item.encode('utf8')) > 4096 or '\x00' in item:
            raise ValueError('Malformed public diplomatic ' + label)
    text(value['speaker_leader'], 'speaker', nullable=True)
    text(value['statement_text'], 'statement')
    text(value['reason_text'], 'reason')
    if type(data) is not dict or type(data.get('selections')) is not list or (not 1 <= len(data['selections']) <= 64) or (type(value['selections']) is not list) or (len(value['selections']) != len(data['selections'])):
        raise ValueError('Public diplomatic menu differs from native choices')
    seen = set()
    for row, native in zip(value['selections'], data['selections']):
        if type(row) is not dict or set(row) != {'key', 'text', 'disabled', 'tooltip'} or type(row['key']) is not str or (row['key'] in seen) or (type(row['disabled']) is not bool) or (type(native) is not dict) or any((row[k] != native.get(k) for k in ('key', 'disabled'))):
            raise ValueError('Public diplomatic choice identity or order differs')
        text(row['key'], 'choice key')
        text(row['text'], 'choice text')
        text(row['tooltip'], 'tooltip', nullable=True)
        if not row['disabled'] and row['tooltip'] is not None:
            raise ValueError('Enabled conversation choice has no official tooltip')
        seen.add(row['key'])
    return value

def read(owner, statement, data, configuration, sequence, *, saved_context=None):
    from civ6_host.runtime.native.native_diplomacy_choices import _snapshot
    from civ6_host.runtime.native.native_diplomacy_choices import lua_source
    from civ6_host.runtime.native.native_locale_arguments import attach
    from civ6_host.runtime.native.native_episode_identity import require_episode
    image=None
    source_sha=PROOF_SHA
    if saved_context is not None:
        from ..xp2_diplomacy_display_source import verify_live,SOURCE
        image=getattr(owner.core,'_civ6_host_execution_image',None)
        verify_live(owner.core._handle,owner.runtime.read,execution_image=image)
        source_sha=SOURCE[1]
    before = _snapshot(owner, 'before', saved_context)
    prefix = owner.prefix
    attach(prefix)
    raw = prefix.runtime.evaluate_text(prefix.ui_child, lua_source(statement, data['session']['player_id'], configuration, public_display=True,execution_image=image), b'@official_diplomacy_public_display', capacity=MAX_BYTES)
    value = parse(raw, data, configuration)
    if _snapshot(owner, 'after', saved_context) != before:
        raise RuntimeError('Diplomatic display read changed scheduler')
    identity = require_episode(prefix)
    owner.emit('official_diplomacy_public_display_observed', episode_id=identity.episode_id, game_generation=identity.game_generation, player_id=data['session']['player_id'], sequence=sequence, display=value, source_sha256=source_sha, actor_encoding_integrated=False, training_eligible=False)
    return value

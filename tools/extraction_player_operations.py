"""Reproduce only the source-qualified shared player-operation request changes.

The measured extractor output omitted two already-installed adaptations. Restore
those exact bytes first, then add the separately qualified Congress permit. Each
stage is pinned; no historical source, ABI proof or arbitrary caller is admitted.
"""
from hashlib import sha256

MODULE = 'civ6rl.native_player_operation_request'
LABEL = 'source-pinned reproduction of existing XP2 UNLOCK_POLICIES empty-map and execution-image forwarding; sealed Congress permits retain exact UI direct-request semantics'
HISTORICAL_SOURCE_SHA256 = 'c2df4e4764ee708f6161267c3711ddef6b7f9ee39683384f08bdeb7b7e0dabcc'
EXTRACTED_SHA256 = '036334282cdd7d234647442ac54e7d897aca91462b6eb30a04170447a7966d84'
INSTALLED_LEGACY_SHA256 = 'd333b38f3e2e6b53a83957205b0a6b64fed5c3d642530488424f4eefe93cbbd7'
DESTINATION_SHA256 = 'd26cba66939589a7afdb0b62b547d65260b0ab845904c53534f4863aea8f3fd9'

_LEGACY_EDITS = (('\n'
  'def request_player_operation(core, context, player, operation, parameters, *, read=None, '
  'native_api=None, submit=True, '
  "core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):\n",
  '\n'
  'def request_player_operation(core, context, player, operation, parameters, *, read=None, '
  'native_api=None, submit=True, '
  "core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', "
  'allow_empty=False):\n'),
 ('    """Run native CanStart and, when true, submit the identical scalar map.\n',
  '    """Run native CanStart and, when true, submit the identical scalar map.\n'
  '\n'
  '    ``allow_empty`` is restricted to the source-qualified XP2 UNLOCK_POLICIES\n'
  '    operation, whose official UI submits an empty table. All other callers\n'
  '    retain the nonempty parameter contract.\n'),
 ("        raise ValueError('Player operation must be a uint32 native value')\n"
  '    if not isinstance(parameters, dict) or not 1 <= len(parameters) <= 8 or any((type(k) is not '
  'int or type(v) is not int or (not 0 <= k <= 4294967295) or (not 0 <= v <= 4294967295) for k, v '
  'in parameters.items())):\n',
  "        raise ValueError('Player operation must be a uint32 native value')\n"
  '    if type(allow_empty) is not bool:\n'
  "        raise ValueError('Empty player-operation parameters require explicit qualification')\n"
  '    if allow_empty:\n'
  '        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256\n'
  '        from civ6_host.runtime.xp2_policy_controls_source import UNLOCK_POLICIES, source\n'
  '        if core_sha256 != XP2_CORE_SHA256 or operation != UNLOCK_POLICIES:\n'
  "            raise ValueError('Unqualified empty player-operation map')\n"
  '        source()\n'
  '    if not isinstance(parameters, dict) or not (0 if allow_empty else 1) <= len(parameters) <= '
  '8 or any((type(k) is not int or type(v) is not int or (not 0 <= k <= 4294967295) or (not 0 <= v '
  '<= 4294967295) for k, v in parameters.items())):\n'),
 ('        from civ6_host.runtime.xp1_research_profile import verify_live\n'
  '        verify_live(base, read, core_sha256=core_sha256)\n',
  '        from civ6_host.runtime.xp1_research_profile import verify_live\n'
  "        image=getattr(core,'_civ6_host_execution_image',None)\n"
  '        verify_live(base, read, core_sha256=core_sha256,\n'
  "                    **({'execution_image':image} if image is not None else {}))\n"))

_CONGRESS_EDITS = (('\n'
  'def request_player_operation(core, context, player, operation, parameters, *, read=None, '
  'native_api=None, submit=True, '
  "core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', "
  'allow_empty=False):\n',
  '\n'
  'def request_player_operation(core, context, player, operation, parameters, *, read=None, '
  'native_api=None, submit=True, '
  "core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', "
  'allow_empty=False, congress_permit=None):\n'),
 ('    ``allow_empty`` is restricted to the source-qualified XP2 UNLOCK_POLICIES\n'
  '    operation, whose official UI submits an empty table. All other callers\n'
  '    retain the nonempty parameter contract.\n',
  '    ``allow_empty`` is restricted to the source-qualified XP2 UNLOCK_POLICIES\n'
  '    operation, whose official UI submits an empty table. An internal sealed\n'
  '    Congress permit additionally admits its exact source-described empty maps\n'
  '    and direct requests without CanStart. Other callers retain their contract.\n'),
 ("        raise ValueError('Empty player-operation parameters require explicit qualification')\n"
  '    if allow_empty:\n',
  "        raise ValueError('Empty player-operation parameters require explicit qualification')\n"
  '    congress_name = None\n'
  '    if congress_permit is not None:\n'
  '        from civ6_host.runtime.xp2_world_congress_source import authorize_request\n'
  '        congress_name = authorize_request(congress_permit, core, context, player, operation,\n'
  '            parameters, core_sha256=core_sha256, submit=submit, allow_empty=allow_empty)\n'
  '    elif allow_empty:\n'),
 ("            raise RuntimeError('Native reason-map constructor identity differs')\n"
  "        allowed = native_api['can_start'](context, player, operation, params.address, False, "
  'reasons.address)\n',
  "            raise RuntimeError('Native reason-map constructor identity differs')\n"
  '        # These source-bound UI requests do not call CanStart. The native\n'
  '        # request still applies its own requested-player active-state guard.\n'
  '        allowed = (True if congress_name is not None else\n'
  "                   native_api['can_start'](context, player, operation, params.address, False, "
  'reasons.address))\n'),
 ('            check()\n'
  "        return {'player_id': player, 'operation': operation, 'can_start': bool(allowed), "
  "'request_invoked': bool(allowed and submit), 'request_return_interpreted': False, "
  "'parameter_count': len(parameters), 'native_parameter_vtable_rva': hex(abi.parameters), "
  "'test_visible': False, 'native_reason_map': True, 'archive_fabricated': False, "
  "'gameplay_outcome_verified': False, 'eligible_for_training': False, 'source_sha256': "
  'abi.source_sha256}\n',
  '            check()\n'
  "        receipt = {'player_id': player, 'operation': operation, 'can_start': bool(allowed), "
  "'request_invoked': bool(allowed and submit), 'request_return_interpreted': False, "
  "'parameter_count': len(parameters), 'native_parameter_vtable_rva': hex(abi.parameters), "
  "'test_visible': False, 'native_reason_map': True, 'archive_fabricated': False, "
  "'gameplay_outcome_verified': False, 'eligible_for_training': False, 'source_sha256': "
  'abi.source_sha256}\n'
  '        if congress_name is not None:\n'
  '            receipt.update(can_start=None, native_can_start_called=False,\n'
  '                           source_qualified_request_only=congress_name)\n'
  '        return receipt\n'))


def _digest(text):
    return sha256(text.encode('utf-8')).hexdigest()


def _apply(text, edits, expected):
    for before, after in edits:
        if text.count(before) != 1:
            raise ValueError('Player-operation extraction anchor changed')
        text = text.replace(before, after, 1)
    if _digest(text) != expected:
        raise ValueError('Player-operation extraction result changed')
    return text


def parameterize(name, text):
    if name != MODULE:
        return text
    if _digest(text) != EXTRACTED_SHA256:
        raise ValueError('Player-operation extraction input changed; rebase source explicitly')
    text = _apply(text, _LEGACY_EDITS, INSTALLED_LEGACY_SHA256)
    return _apply(text, _CONGRESS_EDITS, DESTINATION_SHA256)

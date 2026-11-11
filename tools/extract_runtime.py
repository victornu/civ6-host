"""Reproducible, source-mapped extraction of the retained native backend.

This migration tool reads original project Python, never game binaries, SQL,
captured saves, decompiled output or learner weights. The old tree is untouched.
Only the declared import closure is extracted; historical schemas stay unchanged.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
from extraction_application_mirror import MODULES as APPLICATION_MIRROR_MODULES, parameterize as parameterize_application_mirror
from extraction_deferred_queue import MODULES as DEFERRED_QUEUE_MODULES, parameterize as parameterize_deferred_queue
from extraction_event_arguments import MODULE as EVENT_ARGUMENT_MODULE, parameterize as parameterize_event_arguments
from extraction_retained_game import MODULE as RETAINED_GAME_MODULE, parameterize as parameterize_retained_game
from extraction_a0_dispatch import share as share_a0_dispatch
from extraction_cache_facades import MODULES as CACHE_FACADE_MODULES, parameterize as parameterize_cache_facades
from extraction_player_notifications import MODULE as PLAYER_NOTIFICATION_MODULE, parameterize as parameterize_player_notifications
from extraction_xp1_bundle_inputs import qualify_inputs as qualify_xp1_bundle_inputs
from extraction_postload160 import parameterize as parameterize_postload160
from extraction_postload_aux90 import parameterize as parameterize_postload_aux90
from extraction_loaded_cache import parameterize as parameterize_loaded_cache, parameterize_official as parameterize_official_loaded_cache
from extraction_job_registry import parameterize as parameterize_job_registry
from extraction_xp1_saved_load import parameterize as parameterize_xp1_saved_load
from extraction_xp1_saved_handoff import parameterize as parameterize_xp1_saved_handoff, worker as parameterize_xp1_saved_worker
from extraction_xp1_saved_init import MODULES as XP1_SAVED_INIT_MODULES, parameterize as parameterize_xp1_saved_init
from extraction_xp1_load_capability import MODULES as XP1_LOAD_CAPABILITY_MODULES, parameterize as parameterize_xp1_load_capability
from extraction_xp1_capability_cache import MODULES as XP1_CAPABILITY_CACHE_MODULES, parameterize as parameterize_xp1_capability_cache
from extraction_xp1_load_options import parameterize as parameterize_xp1_load_options
from extraction_xp1_postload_candidate import parameterize as parameterize_xp1_postload_candidate
from extraction_xp1_cache_publication import parameterize as parameterize_xp1_cache_publication
from extraction_xp1_loaded_lifetime import parameterize as parameterize_xp1_loaded_lifetime
from extraction_xp1_publication_events import parameterize as parameterize_xp1_publication_events
from extraction_xp1_ui_binding import parameterize as parameterize_xp1_ui_binding
from extraction_action_transport import parameterize as parameterize_action_transport
from extraction_xp1_turns import parameterize as parameterize_xp1_turns
from extraction_xp1_turn_units import parameterize as parameterize_xp1_turn_units
from extraction_xp1_world_input import parameterize as parameterize_xp1_world_input, MODULES as XP1_WORLD_MODULES
from extraction_xp1_unit_orders import parameterize as parameterize_xp1_unit_orders, MODULES as XP1_ORDER_MODULES
from extraction_capture_continuation import parameterize as parameterize_capture_continuation
from extraction_capture_continuation import parameterize_consumer as parameterize_capture_continuation_consumer
from extraction_capture_script_paths import parameterize_collector as parameterize_capture_script_paths_collector
from extraction_capture_script_paths import parameterize_provider as parameterize_capture_script_paths_provider
from extraction_script_binding_profiles import parameterize as parameterize_script_binding_profiles
from extraction_script_binding_profiles import parameterize_services as parameterize_script_services

NATIVE = 'civ6_host.runtime.native'
WORKERS = 'civ6_host.runtime.workers'
CONTRACTS = {n:'civ6_host.contracts.'+n for n in
    ('plot_display990','production_info988','research_info983','yield_display982')}
SPECIAL = {'civ6rl.learning.diagnostic_budget998':NATIVE+'.legacy_budget',
           'civ6rl.learning.skill_task991':NATIVE+'.public_continuity'}
SEEDS = ('civ6rl.native_hotseat_session','tools.official_hotseat_worker923',
         'tools.official_action_worker920','tools.run_official_postload909',
         'civ6rl.native_xp1_prepare_type_registry', 'civ6rl.native_xp1_archive_access',
         'civ6rl.native_xp1_archive_registration', 'civ6rl.native_xp1_prepare_dispatch',
         'civ6rl.native_xp1_map_setup', 'civ6rl.native_xp1_application_configuration',
         'civ6rl.native_context_lifetime', 'civ6rl.native_context_notify',
         'civ6rl.native_xp1_performance')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parameterize_active_list_reader(raw):
    """Keep the existing bounded reader, selecting only source-pinned layouts.

    Base defaults and receipt identities remain unchanged. The extension path
    reads memory only; it does not admit an expansion saved game to the host.
    """
    def change(old, new, count=1):
        nonlocal raw
        if raw.count(old) != count:
            raise ValueError('Active-list extraction boundary changed: ' + old[:90])
        raw = raw.replace(old, new)

    change("SCHEMA = 'civ6rl.official_gameplay_empty.capture.v1'", """from civ6_host.runtime.gameplay_active_profiles import (
    SUPPORTED_CORES as _active_supported, expansion_profile as _active_profile,
    source_digest as _active_source_sha, state_schema as _active_state_schema,
)
SCHEMA = 'civ6rl.official_gameplay_empty.capture.v1'""")
    change('def source_profile():', '''def source_profile(core_sha256=BASE_CORE_SHA256):
    if core_sha256 != BASE_CORE_SHA256:
        return _active_profile(core_sha256)''')
    change('def read_gameplay_state(read_memory, core_base, *, expected_inner=None,',
           'def read_gameplay_state(read_memory, core_base, *, core_sha256=BASE_CORE_SHA256, expected_inner=None,')
    change('source = source_profile(); deadline.check(); layout = source[\'layout\']',
           'source = source_profile(core_sha256); deadline.check(); layout = source[\'layout\']')
    change('return dict(schema=STATE_SCHEMA, source_sha256=SOURCE_SHA256, core_sha256=BASE_CORE_SHA256,',
           'return dict(schema=_active_state_schema(core_sha256), source_sha256=_active_source_sha(core_sha256), core_sha256=core_sha256,')
    change("supported = core['sha256'] == BASE_CORE_SHA256", "supported = core['sha256'] in _active_supported")
    change("expected_vtable = first['exe_module']['base'] + source_profile()['layout']['auxiliary_exe_vtable_rva']",
           "expected_vtable = first['exe_module']['base'] + source_profile(core['sha256'] if supported else BASE_CORE_SHA256)['layout']['auxiliary_exe_vtable_rva']")
    change("read_gameplay_state(process.read, core['base'],",
           "read_gameplay_state(process.read, core['base'], core_sha256=core['sha256'],", 2)
    change('source_sha256=SOURCE_SHA256, observations_repeated=True,',
           "source_sha256=_active_source_sha(core['sha256']), observations_repeated=True,")
    change("scope='Current Base GameplayScripts selection and retained active-list absence only; no historical execution certificate'",
           "scope=('Current Base GameplayScripts selection and retained active-list absence only; no historical execution certificate' if not supported or core['sha256'] == BASE_CORE_SHA256 else 'Current hash-pinned GameplayScripts selection and retained active-list absence only; no historical execution certificate')")
    change("    required = {'schema', 'status', 'process', 'exe_module', 'gamecore_module',", """    core_module = report.get('gamecore_module') if type(report) is dict else None
    core_sha = core_module.get('sha256') if type(core_module) is dict else None
    required = {'schema', 'status', 'process', 'exe_module', 'gamecore_module',""")
    change("report['source_sha256'] != SOURCE_SHA256", "report['source_sha256'] != _active_source_sha(core_sha)")
    change("state = report['state']; supported = report['gamecore_module']['sha256'] == BASE_CORE_SHA256",
           "state = report['state']; supported = core_sha in _active_supported")
    change("state.get('schema') != STATE_SCHEMA", "state.get('schema') != _active_state_schema(core_sha)")
    change("state.get('source_sha256') != SOURCE_SHA256", "state.get('source_sha256') != _active_source_sha(core_sha)")
    change("state.get('core_sha256') != BASE_CORE_SHA256", "state.get('core_sha256') != core_sha")
    change("layout = source_profile()['layout']; sentinel = layout['sentinel']",
           "layout = source_profile(core_sha)['layout']; sentinel = layout['sentinel']")
    change("'gamecore_module': report['gamecore_module'], 'source_sha256': SOURCE_SHA256,",
           "'gamecore_module': report['gamecore_module'], 'source_sha256': _active_source_sha(core_sha),")
    return raw


def parameterize_saved_load(name, raw):
    """Route the retained Load backend through one engine ABI selection.

    This changes neither Base call signatures nor addresses. Expansion profiles
    are selected for inspection but refused before any native backend setup.
    The configuration/provider and all existing source guards remain intact.
    """
    def change(old, new, count=1):
        nonlocal raw
        if raw.count(old) != count:
            raise ValueError('Saved-Load extraction boundary changed: ' + old[:90])
        raw = raw.replace(old, new)

    if name == 'civ6rl.native_checkpoint_load':
        change("        super().__init__(core, context, fixture, dll_directory, profile, proofs['provider'], emit)",
               """        from civ6_host.runtime.saved_load_profiles import profile_for_sha, require_saved_load_admission
        self.load_abi = require_saved_load_admission(profile_for_sha(profile.core_sha256))
        super().__init__(core, context, fixture, dll_directory, profile, proofs['provider'], emit)""")
        change('if q(self.context) != base + 0x79E020:',
               'if q(self.context) != base + self.load_abi.outer_vtable_rva:')
        change('if not inner or q(inner) != base + 0x7C7078:',
               'if not inner or q(inner) != base + self.load_abi.inner_vtable_rva:')
        change('''for vt, slot, target in ((0x79E020,0x40,0x42F5A0), (0x79E020,0x120,0x42F470),
                (0x79E020,0x170,0x42E420), (0x7C7078,0x50,0x03CA90),
                (0x7C7078,0x70,0x03C260)):''',
               'for vt, slot, target in self.load_abi.virtual_targets:')
        change('if not game or q(game) != base+0x7C7270:',
               'if not game or q(game) != base+self.load_abi.game_vtable_rva:')
        change('base+0x4C3F60', 'base+self.load_abi.game_initialized_rva', count=2)
        change('prepare_context(self.core,self.context,self.emit)',
               'prepare_context(self.core,self.context,self.emit, saved_load_abi=self.load_abi)')
        change('self.core._handle+0x42F470', 'self.core._handle+self.load_abi.copy_rva')
        change('self.core._handle+0x42E420', 'self.core._handle+self.load_abi.load_rva')
        change('''    def copy_b_to_a(self):
        before = self.topology(game_required=True)''', '''    def copy_b_to_a(self):
        if self.load_abi.ruleset != 'base':
            from civ6_host.runtime.configuration_profiles import verify_context_copy
            verify_context_copy(self.load_abi, self.core._handle, self.runtime.read)
        before = self.topology(game_required=True)''')
        change('indexed = setup._linked_snapshot(self.core._handle,self.context,self.runtime.read,None)',
               'indexed = setup._linked_snapshot(self.core._handle,self.context,self.runtime.read,None, core_sha256=self.load_abi.core_sha256)')
        change("a = application.provider_snapshot(self.core._handle,after['provider'],self.runtime.read)",
               "a = application.provider_snapshot(self.core._handle,after['provider'],self.runtime.read, core_sha256=self.load_abi.core_sha256)")
    elif name == 'civ6rl.native_host':
        change('def prepare_context(core, context, emit):',
               'def prepare_context(core, context, emit, *, saved_load_abi=None):')
        change('''    from .native_localization import initialize_localization
    host = core._diagnostic_host''', '''    from .native_localization import initialize_localization
    from civ6_host.runtime.saved_load_profiles import (
        BASE_CORE_SHA256, profile_for_sha, require_saved_load_admission)
    abi = require_saved_load_admission(
        profile_for_sha(BASE_CORE_SHA256) if saved_load_abi is None else saved_load_abi)
    host = core._diagnostic_host''')
        change('prepare = virtual(core, context, 0x40, 0x42f5a0, None)',
               'prepare = virtual(core, context, 0x40, abi.prepare_rva, None)')
    return raw


def parameterize_configuration_tree(name, tree):
    """Reuse provider ownership, codec and indexed-context algorithms by ABI.

    Only the declared functions change. Other Base finalization/NewGame paths
    retain their source guards and are not admitted for an expansion by this.
    """
    functions = {n.name:n for n in tree.body if isinstance(n, ast.FunctionDef)}
    classes = {n.name:n for n in tree.body if isinstance(n, ast.ClassDef)}

    def methods(cls):
        return {n.name:n for n in classes[cls].body if isinstance(n, ast.FunctionDef)}

    def argument(fn, default):
        if any(a.arg == 'core_sha256' for a in (*fn.args.args, *fn.args.kwonlyargs)):
            raise ValueError('Configuration extraction parameter already exists')
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
        fn.args.kw_defaults.append(ast.parse(default, mode='eval').body)

    def expressions(fn, replacements):
        lookup = {ast.dump(ast.parse(old, mode='eval').body):new for old,new in replacements.items()}
        hits = {old:0 for old in lookup}
        class Rewriter(ast.NodeTransformer):
            def visit(self, node):
                key = ast.dump(node)
                if key in lookup:
                    hits[key] += 1
                    return ast.copy_location(ast.parse(lookup[key], mode='eval').body, node)
                return super().visit(node)
        Rewriter().visit(fn)
        if any(count == 0 for count in hits.values()):
            missing = [old for old in replacements if hits[ast.dump(ast.parse(old,mode='eval').body)] == 0]
            raise ValueError('Configuration expression boundary changed: ' + repr(missing))

    def calls(fn, callee, value, expected):
        found = 0
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and ast.unparse(n.func) == callee:
                n.keywords.append(ast.keyword(arg='core_sha256',value=ast.parse(value,mode='eval').body))
                found += 1
        if found != expected:
            raise ValueError('Configuration call boundary changed: ' + callee)

    common = '''
from civ6_host.runtime.configuration_profiles import (
    configuration_abi as _configuration_abi,
    require_owner_profile as _require_owner_profile,
    application_source as _expansion_application_source,
    codec_source as _expansion_codec_source,
)
'''
    tree.body.extend(ast.parse(common).body)

    if name == 'civ6rl.native_application_configuration':
        argument(functions['verify_source'], 'setup.CORE_SHA256')
        functions['verify_source'].body[:0] = ast.parse('''
if core_sha256 != setup.CORE_SHA256:
    return _expansion_application_source(core_sha256)
''').body
        for fn_name in ('_live_code', 'provider_snapshot'):
            fn = functions[fn_name]
            argument(fn, 'setup.CORE_SHA256')
            calls(fn, 'verify_source', 'core_sha256', 1)
        expressions(functions['_live_code'], {'_LIVE':"(*_LIVE, *proof.get('additional_live_names', ()))"})
        fn = functions['provider_snapshot']
        fn.body[:0] = ast.parse('abi = _require_owner_profile(_configuration_abi(core_sha256))').body
        expressions(fn, {'VTABLE':'abi.vtable_rva', 'LOOKUP':'abi.lookup_rva',
            'ASSIGN':'abi.assign_rva', '0x7450A0':'abi.copy_rva',
            '0x8BCC58':'abi.root_key_rva','0x8BCD08':'abi.map_key_rva',
            '0x8BCD50':'abi.player_key_table_rva'})
        m = methods('NativeApplicationConfiguration')
        argument(m['__init__'], 'setup.CORE_SHA256')
        m['__init__'].body[:0] = ast.parse('self._configuration_abi = _require_owner_profile(_configuration_abi(core_sha256))').body
        for fn_name in ('__init__','snapshot','verify_core_copy_topology','player','close'):
            fn = m[fn_name]
            fields = {'VTABLE':'vtable_rva','CTOR':'constructor_rva','DTOR':'destructor_rva',
                      'ASSIGN':'assign_rva','LOOKUP':'lookup_rva','PROOF_SHA256':'application_proof_sha256'}
            present = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
            expressions(fn, {k:'self._configuration_abi.'+v for k,v in fields.items() if k in present})
        for fn_name,callee,count in (
            ('__init__','_live_code',1),('__init__','setup._linked_snapshot',1),
            ('__init__','provider_snapshot',2),('snapshot','provider_snapshot',1),
            ('verify_core_copy_topology','setup._linked_snapshot',1),('player','verify_source',1)):
            calls(m[fn_name],callee,'self._configuration_abi.core_sha256',count)
        expressions(m['player'], {'0x8BCD50':'self._configuration_abi.player_key_table_rva'})

    elif name == 'civ6rl.native_configuration_finalization':
        for fn_name in ('_snapshot','_linked_snapshot'):
            fn = functions[fn_name]
            argument(fn, 'CORE_SHA256')
            fn.body[:0] = ast.parse('abi = _require_owner_profile(_configuration_abi(core_sha256))').body
        expressions(functions['_snapshot'], {
            'OUTER_VTABLE':'abi.load.outer_vtable_rva','INNER_VTABLE':'abi.load.inner_vtable_rva',
            'CONFIG_VTABLE':'abi.vtable_rva','LOOKUP_RVA':'abi.lookup_rva',
            'PREPARATION':'abi.preparation','0x42E3A0':'abi.initialized_getter_rva',
            '0x7465A0':'abi.uint_setter_rva','0x7450A0':'abi.copy_rva'})
        expressions(functions['_linked_snapshot'], {
            '0x42E3A0':'abi.initialized_getter_rva','LOOKUP_RVA':'abi.lookup_rva',
            '0x8BCC58':'abi.root_key_rva','0x8BCD08':'abi.map_key_rva',
            '0x8BCD50':'abi.player_key_table_rva'})
        calls(functions['_linked_snapshot'],'_snapshot','core_sha256',2)

    elif name == 'civ6rl.native_checkpoint_provider':
        argument(functions['verify_source'], 'CORE_SHA256')
        functions['verify_source'].body[:0] = ast.parse('''
if core_sha256 != CORE_SHA256:
    return _expansion_codec_source(core_sha256)
''').body
        runtime = methods('_Runtime')
        expressions(runtime['image'], {'CORE_SHA256':"proof['images']['core']['sha256']"})
        runtime['image'].body[:0] = ast.parse("_require_owner_profile(_configuration_abi(proof['images']['core']['sha256']))").body
        m = methods('_Session')
        m['__init__'].body[:0] = ast.parse("self.abi = _require_owner_profile(getattr(owner, '_configuration_abi', None))").body
        calls(m['__init__'],'verify_source','self.abi.core_sha256',1)
        expressions(m['_validate_owner'], {
            '0x79E020':'self.abi.load.outer_vtable_rva','0x7C7078':'self.abi.load.inner_vtable_rva',
            'VTABLE_RVA':'self.abi.vtable_rva','METHODS | DEPENDENCY_SLOTS':'dict(self.abi.codec_slots)'})
        m['_validate_owner'].body[:0] = ast.parse('''
if getattr(self.owner, '_configuration_abi', None) is not self.abi:
    raise ValueError('Provider owner changed its engine ABI identity')
''').body
        calls(m['_live_code'],'application._live_code','self.abi.core_sha256',1)
        calls(m['_identity'],'application.provider_snapshot','self.abi.core_sha256',2)
        expressions(m['execute'], {
            'METHODS[0x1E8 if restoring else 0x1F0]':'dict(self.abi.codec_slots)[0x1E8 if restoring else 0x1F0]',
            'PROOF_SHA256':'self.abi.codec_proof_sha256','CORE_SHA256':'self.abi.core_sha256'})
    else:
        raise ValueError('Unexpected configuration extraction module')
    return tree


XP1_PREPARE_MODULES = (
    'civ6rl.native_xp1_prepare_type_registry',
    'civ6rl.native_xp1_archive_access',
    'civ6rl.native_xp1_archive_registration',
    'civ6rl.native_xp1_prepare_dispatch',
)


def migrate_xp1_prepare_sources(name, tree):
    """Retain historical proof identities while moving to the reviewed host.

    The host delta adds only the Base achievement service, revoked by XP1 Init.
    Registry/archive/Tuner bodies are unchanged. Never relabel the older proof.
    """
    old = 'daac085ea97d94d2d9ceded07ef90bcc9d7a1f2ab6aa301f3efa155b8cea8db5'
    new = 'ebd7d0f3e0026e35ef04b89d92698764466887578cc1819351a794dce4b8e3d6'
    found = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and n.value == old]
    if len(found) != 1:
        raise ValueError('XP1 Prepare host source migration boundary changed: ' + name)
    found[0].value = new
    if name == 'civ6rl.native_xp1_archive_registration':
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'verify_source')
        raw = ast.unparse(fn)
        boundary = "revision.get('new_sha256') != SOURCE_PINS['civ6rl/native_host.py']"
        if raw.count(boundary) != 1:
            raise ValueError('Historical archive revision check changed')
        # The retained 888 proof describes the parent, not today's host.
        raw = raw.replace(boundary, "revision.get('new_sha256') != " + repr(old))
        # Keep the native helper body in the private proof. The extracted
        # validator pins the same canonical encoding and binary digest.
        comparisons = [node for node in ast.walk(fn)
                       if isinstance(node, ast.Compare)
                       and ast.unparse(node.left) == "helper.get('raw_hex')"]
        helper_sha256 = '37835c992dde1ce38148674011b2ec344d40dc8752488e06ef0dbeaa494eb4dc'
        if len(comparisons) != 1:
            raise ValueError('Historical archive helper comparison changed')
        comparison = comparisons[0]
        value = comparison.comparators[0]
        if (len(comparison.comparators) != 1 or not isinstance(comparison.ops[0], ast.NotEq)
                or not isinstance(value, ast.Constant) or type(value.value) is not str
                or len(value.value) != 190 or value.value != value.value.lower()
                or hashlib.sha256(bytes.fromhex(value.value)).hexdigest() != helper_sha256
                or raw.count(ast.unparse(comparison)) != 1
                or raw.count("helper.get('sha256') != " + repr(helper_sha256)) != 1):
            raise ValueError('Historical archive helper byte identity changed')
        raw = raw.replace(ast.unparse(comparison),
            "type(helper_hex) is not str or len(helper_hex) != 190"
            " or any(char not in '0123456789abcdef' for char in helper_hex)"
            " or hashlib.sha256(bytes.fromhex(helper_hex)).hexdigest() != helper['sha256']")
        helper_assignment = "    helper = proof.get('captures', {}).get('register_helper_83c820', {})"
        if raw.count(helper_assignment) != 1:
            raise ValueError('Historical archive helper acquisition changed')
        raw = raw.replace(helper_assignment, helper_assignment + "\n    helper_hex = helper.get('raw_hex')")
        tree.body[tree.body.index(fn)] = ast.parse(raw).body[0]
    if name == 'civ6rl.native_xp1_prepare_dispatch':
        old_locale = '07a3519f50711a964edef0419fdc2e09b0600e79bd379081f45d669d498e5e89'
        found = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and n.value == old_locale]
        if len(found) != 1:
            raise ValueError('XP1 localization source migration boundary changed')
        found[0].value = '7ddac11af2a3ec117db11de262eec450665c2a8606851dfedb0a8df84d771721'
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare_xp1_context')
        fn.args.kwonlyargs.append(ast.arg(arg='null_tuner_diagnostic'))
        fn.args.kw_defaults.append(ast.Constant(False))
        raw = ast.unparse(fn)
        boundary = "if getattr(host, 'tuner_unavailable_probe', False):\n        raise ValueError('This XP1 Prepare path does not enable the unavailable-Tuner diagnostic')"
        if raw.count(boundary) != 1:
            raise ValueError('XP1 NULL Tuner refusal boundary changed')
        raw = raw.replace(boundary, """if getattr(host, 'tuner_unavailable_probe', False):
        from civ6_host.runtime.xp1_prepare import require_null_tuner_diagnostic
        require_null_tuner_diagnostic(host, null_tuner_diagnostic)
    elif null_tuner_diagnostic:
        raise ValueError('NULL Tuner diagnostic requires the explicit host probe')""")
        tree.body[tree.body.index(fn)] = ast.parse(raw).body[0]
    return tree


def parameterize_context_lifecycle(name, tree):
    """Reuse verified XP1 Init/teardown in the existing configuration backend.

    Saved Load admission is deliberately elsewhere. Base keeps its callbacks;
    XP1 uses its retained stricter callback allowlist and exact diagnostic DBs.
    """
    def replace(fn, before, after):
        raw = ast.unparse(fn)
        if raw.count(before) != 1:
            raise ValueError('Context lifecycle extraction boundary changed: ' + before)
        return ast.parse(raw.replace(before, after)).body[0]

    if name in ('civ6rl.native_xp1_context_init', 'civ6rl.native_xp1_teardown_adapter'):
        # Explicit source-pair migration qualified by the 30 October native
        # Init/provider/Destroy receipt. Historical source files stay unchanged.
        pins = next(n for n in tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'SOURCE_PINS' for t in n.targets))
        values = ast.literal_eval(pins.value)
        if values['civ6rl/native_host.py'] != 'daac085ea97d94d2d9ceded07ef90bcc9d7a1f2ab6aa301f3efa155b8cea8db5':
            raise ValueError('XP1 helper host parent differs from explicit source migration')
        values['civ6rl/native_host.py'] = 'ebd7d0f3e0026e35ef04b89d92698764466887578cc1819351a794dce4b8e3d6'
        pins.value = ast.parse(repr(values), mode='eval').body
        return tree

    if name == 'civ6rl.native_host':
        prepare = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare_context')
        prepare.args.kwonlyargs.extend([ast.arg(arg='context_profile'), ast.arg(arg='null_tuner_diagnostic')])
        prepare.args.kw_defaults.extend([ast.Constant(None), ast.Constant(False)])
        prepare.body[1:1] = ast.parse('''
if context_profile is not None:
    if saved_load_abi is not None:
        raise ValueError('Context-only preparation cannot claim saved Load admission')
    from civ6_host.runtime.xp1_prepare import prepare as prepare_xp1
    return prepare_xp1(core, context, core._diagnostic_host, context_profile, emit,
                       null_tuner_diagnostic=null_tuner_diagnostic)
if null_tuner_diagnostic:
    raise ValueError('Explicit NULL Tuner diagnostic requires an XP1 context profile')
''').body
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'initialize_context')
        index = tree.body.index(fn)
        fn.args.kwonlyargs.append(ast.arg(arg='context_profile'))
        fn.args.kw_defaults.append(ast.Constant(None))
        fn.body[:0] = ast.parse('''
expansion = False
if context_profile is not None:
    from .native_core_context_profiles import NativeCoreContextProfile, profile_for_core
    if type(context_profile) is not NativeCoreContextProfile:
        raise ValueError('Expected an exact native context profile')
    if (context_profile.ruleset, context_profile.mode) not in (('base', 'init'), ('xp1', 'context')):
        raise ValueError('Context initialization profile is not admitted')
    actual_profile = profile_for_core(core._name, mode=context_profile.mode,
                                      shared_dependency_directory=dll_directory)
    if actual_profile != context_profile:
        raise ValueError('Context profile differs from installed source-bound engine')
    expansion = context_profile.ruleset == 'xp1'
''').body
        raw = ast.unparse(fn)
        start = raw.index('    free_address = ')
        end = raw.index('    host = DiagnosticHost', start)
        base_free = raw[start:end]
        raw = raw[:start] + '    native_free = None\n    if not expansion:\n' + ''.join('    '+line+'\n' for line in base_free.splitlines()) + raw[end:]
        start = raw.index('    from .native_events import NativeEventRecorder')
        end = raw.index('    host.database = ', start)
        recorder = raw[start:end]
        raw = raw[:start] + '    if not expansion:\n' + ''.join('    '+line+'\n' for line in recorder.splitlines()) + raw[end:]
        fn = ast.parse(raw).body[0]
        fn = replace(fn, '    core._diagnostic_host = host', '''    core._diagnostic_host = host
    if expansion:
        from .native_xp1_context_init import initialize_xp1_context
        from .native_xp1_teardown_adapter import install_xp1_teardown_callbacks
        from .native_probe import Windows
        root = Path(__file__).resolve().parents[1]
        host.context_init_receipt = initialize_xp1_context(
            core, context, host,
            configuration_path=Path(manifest['databases']['configuration']['path']),
            gameplay_path=Path(manifest['databases']['gameplay']['path']),
            private_root=Path(manifest_path).resolve().parent,
            module_paths=Windows().modules(), emit=emit)
        emit('xp1_adapter_receipt', receipt=host.context_init_receipt)
        host.context_teardown_receipt = install_xp1_teardown_callbacks(
            core, context, host, host.context_init_receipt,
            project_root=root, module_paths=Windows().modules(), emit=emit)
        if host.context_teardown_receipt.get('installed') is not True:
            raise RuntimeError('XP1 teardown binding did not complete')
        return host''')
        tree.body[index] = fn
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'finish_database')
        fn = replace(fn, '    host.event_recorder.close()',
            "    if getattr(host, 'event_recorder', None) is not None:\n        host.event_recorder.close()")
        fn.body.append(ast.Return(value=ast.Name(id='result', ctx=ast.Load())))
        tree.body[next(i for i,n in enumerate(tree.body) if isinstance(n,ast.FunctionDef) and n.name=='finish_database')] = fn
        return tree

    if name == 'civ6rl.native_checkpoint_configuration_only':
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_NativeBackend')
        for i, fn in enumerate(cls.body):
            if not isinstance(fn, ast.FunctionDef):
                continue
            if fn.name == '__init__':
                fn = replace(fn, "profile.ruleset != 'base' or profile.core_sha256 != provider.CORE_SHA256 or (profile.mode != 'init')",
                             "(profile.ruleset, profile.mode) not in (('base', 'init'), ('xp1', 'context'))")
                fn = replace(fn, "Expected a fresh Base Init worker context, with no prior host/provider",
                             "Expected a fresh admitted configuration context, with no prior host/provider")
                fn = replace(fn, '    self.runtime = provider._Runtime()', '''    from civ6_host.runtime.configuration_profiles import configuration_abi
    self.configuration_abi = configuration_abi(profile.core_sha256)
    if self.configuration_abi.load.ruleset != profile.ruleset or proof['images']['core']['sha256'] != profile.core_sha256:
        raise ValueError('Configuration provider/context engine identities disagree')
    self.runtime = provider._Runtime()''')
                fn = replace(fn, "str(Path(proof['images']['core']['path']).parent)", 'str(profile.shared_dependency_directory)')
                fn = replace(fn, 'Dependency directory differs from pinned Base', 'Dependency directory differs from pinned shared dependencies')
            elif fn.name == 'state':
                fn = replace(fn, 'base + 8155256', 'base + self.configuration_abi.load.inner_vtable_rva')
            elif fn.name == 'initialize':
                fn = replace(fn, 'initialize_context(self.core, self.context, self.fixture, self.dll_directory, self.emit)',
                             'initialize_context(self.core, self.context, self.fixture, self.dll_directory, self.emit, context_profile=self.profile)')
            elif fn.name == 'clone':
                fn = replace(fn, 'NativeApplicationConfiguration(self.core, self.context, emit=self.emit)',
                             'NativeApplicationConfiguration(self.core, self.context, emit=self.emit, core_sha256=self.profile.core_sha256)')
            elif fn.name == 'restore':
                # The original Base sidecar remains the default. Explicit XP
                # bytes require their own expected digest, never Base fallback.
                fn.args.kwonlyargs.append(ast.arg(arg='expected_sha256'))
                fn.args.kw_defaults.append(ast.Constant(None))
                fn.body[:0] = ast.parse('''
if expected_sha256 is None:
    if self.profile.ruleset != 'base':
        raise ValueError('Expansion configuration restore requires an explicit input digest')
    expected_sha256 = SIDECAR_SHA
''').body
                fn = replace(fn, 'expected_sha256=SIDECAR_SHA', 'expected_sha256=expected_sha256')
            elif fn.name == 'destroy_context':
                fn.body[:0] = ast.parse('''
if self.profile.ruleset == 'xp1':
    if self.owner is not None and not self.owner.closed:
        raise ValueError('XP1 context destruction requires its owned provider closed')
    if getattr(self.host, 'context_teardown_receipt', {}).get('installed') is not True:
        raise ValueError('XP1 context destruction requires verified teardown callbacks')
''').body
            elif fn.name == 'finish_database':
                fn = replace(fn, '    finish_database(self.host, self.emit)',
                             '    return finish_database(self.host, self.emit)')
            cls.body[i] = fn
        cls.body[0] = ast.Expr(value=ast.Constant('Shared Base/XP1 configuration lifecycle; saved Load has separate admission.'))
        return tree
    raise ValueError('Unexpected context lifecycle extraction module')


def share_nested_map_decoder(raw):
    """Factor the existing tree reader and emitter; one bounded map decoder."""
    tree=ast.parse(raw)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='snapshot_parameter_map')
    fn.args.kwonlyargs.append(ast.arg(arg='allow_nested_maps'))
    fn.args.kw_defaults.append(ast.Constant(False))
    fn.args.kwonlyargs.append(ast.arg(arg='native_copy_budget'))
    fn.args.kw_defaults.append(ast.Constant(False))
    start=next(i for i,n in enumerate(fn.body) if ast.unparse(n).startswith('header = copy(map_pointer, 84)'))
    end=next(i for i,n in enumerate(fn.body) if ast.unparse(n)=='wire = bytearray()')
    reader=ast.parse('def read_map(map_pointer):\n    pass').body[0]
    reader.body=fn.body[start:end]+ast.parse('return rows, keys, resolver, count').body
    fn.body[start:end]=[reader]
    fn.body.insert(start,ast.parse('''
if type(allow_nested_maps) is not bool or (allow_nested_maps and transport_version != 2):
    raise ValueError('Nested map transport requires explicit V2 admission')
''').body[0])
    # Insert the remaining admission statements alongside the first if.
    fn.body[start+1:start+1]=ast.parse('''
if allow_nested_maps:
    from civ6_host.runtime.script_map_argument_source import source_for_core
    source_for_core(core_sha256)
active_maps = set()
copy_bytes = 0
if type(native_copy_budget) is not bool or (native_copy_budget and not allow_nested_maps):
    raise ValueError('Native copy bounds require the nested-map source profile')
def charge_copy(size):
    nonlocal copy_bytes
    if native_copy_budget:
        copy_bytes += size
        if size < 0 or copy_bytes > MAX_READ_BYTES:
            raise ValueError('Native map copy allocation budget exceeded')
''').body
    resolver=next(n for n in fn.body if isinstance(n,ast.FunctionDef) and n.name=='resolver_lookup')
    resolver.args.args.insert(0,ast.arg(arg='resolver'))
    named=next(n for n in fn.body if isinstance(n,ast.FunctionDef) and n.name=='named_key')
    named.args.args.append(ast.arg(arg='resolver'))
    for n in ast.walk(named):
        if isinstance(n,ast.Call) and ast.unparse(n.func)=='resolver_lookup':
            n.args.insert(0,ast.Name(id='resolver',ctx=ast.Load()))
    value=next(n for n in fn.body if isinstance(n,ast.FunctionDef) and n.name=='value')
    slot=next(i for i,n in enumerate(value.body) if isinstance(n,ast.If))
    value.body[slot:slot]=ast.parse('''
if native_copy_budget and flags & 0x20000000:
    extent = size * (flags & 0x00FFFFFF)
    charge_copy(extent)
    if extent:
        copy(pointer, extent)
''').body
    # The official list clone allocates one container and its 24-byte variants.
    class CopyListBudget(ast.NodeTransformer):
        def visit_Assign(self,node):
            if ast.unparse(node)=='length = (end - start) // 24':
                return [node]+ast.parse('charge_copy(256 + 24 * length)').body
            return node
    CopyListBudget().visit(value)
    branch=next(n for n in value.body if isinstance(n,ast.If) and ast.unparse(n.test).startswith('flags == 0'))
    inserted=ast.parse('''
if allow_nested_maps and tag == 10 and flags == 0x05000000:
    if pointer:
        emit_map(pointer, depth + 1)
    else:
        charge_copy(88)
        op(NIL)
    types.append((tag,flags,1 if pointer else 0))
''').body[0]
    inserted.orelse=branch.orelse;branch.orelse=[inserted]
    start=next(i for i,n in enumerate(fn.body) if ast.unparse(n)=='op(TABLE, 0, count)')
    stop=start+2
    if not isinstance(fn.body[start+1],ast.For):raise ValueError('Map root emitter changed')
    emit=ast.parse('def emit_map(map_address, depth):\n    pass').body[0]
    emit.body=ast.parse('''
nonlocal elements
if depth >= MAX_LIST_DEPTH or map_address in active_maps:
    raise ValueError('AUX map recursion depth or cycle refused')
rows, keys, resolver, count = read_map(map_address)
charge_copy(88 + 64 * count)
if allow_nested_maps:
    elements += count
    if elements > MAX_ELEMENTS:
        raise ValueError('AUX map aggregate field budget exceeded')
active_maps.add(map_address)
''').body
    original=fn.body[start:stop]
    for n in ast.walk(ast.Module(body=original,type_ignores=[])):
        if isinstance(n,ast.Call) and ast.unparse(n.func)=='named_key':n.args.append(ast.Name(id='resolver',ctx=ast.Load()))
        if isinstance(n,ast.Call) and ast.unparse(n.func)=='value':n.args.append(ast.Name(id='depth',ctx=ast.Load()))
    guarded=ast.Try(body=original,handlers=[],orelse=[],finalbody=ast.parse('active_maps.remove(map_address)').body)
    emit.body += [guarded]+ast.parse('return count').body
    fn.body[start:stop]=[emit]+ast.parse('count = emit_map(map_pointer, 0)').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'


def parameterize_aux_maps(name, raw):
    """Reuse one decoder/transport; preserve legacy engine/version defaults."""
    def change(before, after, count=1):
        nonlocal raw
        if raw.count(before) != count:
            raise ValueError('AUX map extraction boundary changed: '+before[:90])
        raw = raw.replace(before, after)
    base = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
    if name == 'civ6rl.native_aux_map_conversion':
        change('STRING_BYTES = 7', 'STRING_BYTES = 7\nNIL = 8')
        change('*, use_string_keys: bool) -> MapSnapshot:',
               f"*, use_string_keys: bool, core_sha256='{base}', transport_version=1) -> MapSnapshot:")
        change('    verify_source_evidence()\n', '''    verify_source_evidence()
    from civ6_host.runtime.aux_map_profiles import profile_for_sha
    map_abi = profile_for_sha(core_sha256)
    if type(transport_version) is not int or transport_version not in (1,2):
        raise ValueError('Unknown AUX map transport version')
    if transport_version == 2:
        from civ6_host.runtime.configuration_lua_source import source
        source()  # Common official EXE converter, including UTF-16/null semantics.
''')
        change('    if use_string_keys:\n        proof=',
               f"    if use_string_keys and core_sha256 == '{base}':\n        proof=")
        change('core_base + _VT_RVA', 'core_base + map_abi.vtable_rva')
        change('for offset,rva in _SLOTS.items():','for offset,rva in map_abi.slots:')
        change('core_base+0x74e850','core_base+map_abi.name_getter_rva',2)
        change('        elif opcode == RAWSETI:', '''        elif opcode == NIL:
            if arg or payload:
                raise ValueError('Invalid AUX map nil transport')
            stack.append('nil')
        elif opcode == RAWSETI:''')
        change("        if not pointer:\n            raise ValueError('AUX+A8 null byte-string pointer is not admitted')", """        if not pointer:
            if transport_version == 2:
                op(NIL)
                return 0
            raise ValueError('AUX+A8 null byte-string pointer is not admitted')""")
        change('    def resolver_lookup(', '''    def utf16_string(pointer):
        nonlocal string_bytes
        from civ6_host.runtime.variant_text import lua_utf16_snapshot
        data, units = lua_utf16_snapshot(pointer, copy, remember)
        if data is None:
            op(NIL)
            return units
        string_bytes += len(data)
        if string_bytes > MAX_TOTAL_STRING_BYTES:
            raise ValueError('AUX map total string budget exceeded')
        payload_size = ((len(data)+1+15)//16)*16
        if len(wire)//16+1+payload_size//16 > MAX_OPS:
            raise ValueError('AUX map transport operation bound exceeded')
        op(STRING_BYTES,len(data),0)
        wire.extend(data)
        wire.extend(bytes(payload_size-len(data)))
        return units

    def resolver_lookup(''')
        change('        elif flags & 0xFF000000 in (0x20000000,0x21000000) and tag == 5:', '''        elif transport_version == 2 and flags & 0xFF000000 in (0x20000000,0x21000000) and tag == 6:
            units = utf16_string(pointer)
            types.append((tag,flags,units))
        elif flags & 0xFF000000 in (0x20000000,0x21000000) and tag == 5:''')
    elif name == 'civ6rl.native_aux_map_adapter':
        change('*, read=None):', f"*, read=None, core_sha256='{base}', allow_nested_maps=False, state_validator=None, on_refusal=None):")
        change('        self.host = host', '''        from civ6_host.runtime.aux_map_profiles import profile_for_sha
        self.map_abi = profile_for_sha(core_sha256)
        self.core_sha256 = core_sha256
        if type(allow_nested_maps) is not bool:
            raise ValueError('Nested map adapter option must be Boolean')
        self.allow_nested_maps = allow_nested_maps
        if state_validator is not None and not callable(state_validator):
            raise TypeError('AUX state validator must be callable')
        if on_refusal is not None and not callable(on_refusal):
            raise TypeError('AUX refusal handler must be callable')
        self.state_validator = state_validator
        self.on_refusal = on_refusal
        self.transport_version = 1
        self.host = host''')
        # close() also names the export. Replace only the first install branch.
        before='            install = self.host.LAB_AuxMapInstall'
        if raw.count(before)!=2:raise ValueError('Expected AUX map install and close exports')
        raw=raw.replace(before,'''            from civ6_host.runtime.aux_map_profiles import verify_live
            verify_live(self.map_abi, self.core._handle, self.read)
            if hasattr(self.host, 'LAB_AuxMapTransportVersion'):
                version = self.host.LAB_AuxMapTransportVersion
                version.argtypes, version.restype = [], C.c_int
                self.transport_version = version()
                if self.transport_version != 2:
                    raise ValueError('Unknown exported AUX map transport version')
            if self.allow_nested_maps and self.transport_version != 2:
                raise ValueError('Nested map adapter requires native V2 transport')
            install = self.host.LAB_AuxMapInstall''',1)
        change('core_base, pointer, self.read, use_string_keys=bool(names))',
               'core_base, pointer, self.read, use_string_keys=bool(names), core_sha256=self.core_sha256, transport_version=self.transport_version, allow_nested_maps=self.allow_nested_maps)')
        change('                       callback_abi=', '''                       core_sha256=self.core_sha256, transport_version=self.transport_version,
                       layout_source_sha256=self.map_abi.source_sha256,
                       callback_abi=''')
        change('''                if context is None or registry.validate(context) != state_pointer:
                    raise ValueError("AUX callback HKS state is not an active runtime child")''', '''                if context is None:
                    if self.state_validator is None or self.state_validator(state_pointer) is not True:
                        raise ValueError("AUX callback HKS state is not an active runtime child or event frame")
                elif registry.validate(context) != state_pointer:
                    raise ValueError("AUX callback HKS state is not an active runtime child")''')
        change('''                           hks_calls_in_python_callback=False, fallback_used=False)
                return 0''', '''                           hks_calls_in_python_callback=False, fallback_used=False)
                if self.on_refusal is not None:
                    self.on_refusal(str(exc)[:256])
                return 0''')
    if name == 'civ6rl.native_aux_map_conversion':
        return share_nested_map_decoder(raw)
    return raw


def prepare_tree(name, raw):
    if name == 'civ6rl.native_saved_session':
        before = '            for pipe in (process.stdin,process.stdout,process.stderr):pipe.close()'
        after = '''            from civ6_host.runtime.supervisor_cleanup import close_reaped_process_pipes
            pipe_cleanup_errors = close_reaped_process_pipes(process)
            if pipe_cleanup_errors and self.error is None:
                self.error = 'Native pipe cleanup failed: ' + repr(pipe_cleanup_errors)
                self.stop_reason = self.stop_reason or 'pipe_cleanup_failed' '''.rstrip()
        if raw.count(before) != 1:
            raise ValueError('Saved session pipe cleanup boundary changed')
        raw = raw.replace('        job_assigned=self.job is not None',
                          '        pipe_cleanup_errors = []\n        job_assigned=self.job is not None', 1)
        raw = raw.replace(before, after, 1)
        before = "        write_json(self.run/'supervisor.json',self.report);self.finished=True"
        if raw.count(before) != 1:
            raise ValueError('Saved session cleanup receipt boundary changed')
        raw = raw.replace(before, "        self.report['pipe_cleanup_errors'] = pipe_cleanup_errors\n" + before, 1)
    if name=='civ6rl.native_script_arguments':
        before='def argument_evidence(arguments):'
        if raw.count(before)!=1:raise ValueError('Script argument evidence boundary changed')
        raw=raw.replace(before,before+'''
    arguments = tuple(arguments)
    from civ6_host.runtime.script_event_strings import has_strings, argument_evidence as string_evidence
    if has_strings(arguments):
        return string_evidence(arguments)
    from civ6_host.runtime.script_event_maps import has_maps, argument_evidence as map_evidence
    if has_maps(arguments):
        return map_evidence(arguments)
''')
    if name=='civ6rl.native_script_runtime':
        argument_boundary = '        arguments=tuple(arguments)\n        from .native_script_arguments import HKSArgument, pack_arguments'
        if raw.count(argument_boundary) != 2:
            raise ValueError('Protected event string dispatch boundary changed')
        prefix = '        arguments=tuple(arguments)\n        from civ6_host.runtime.script_event_strings import has_strings, dispatch_strings\n'
        raw = raw.replace(argument_boundary, prefix + '''        if has_strings(arguments):
            valid, output = dispatch_strings(self, name, arguments, method='Call', output_initial=0)
            return bool(output) if valid else False
        from .native_script_arguments import HKSArgument, pack_arguments''', 1)
        raw = raw.replace(argument_boundary, prefix + '''        if has_strings(arguments):
            return dispatch_strings(self, name, arguments, method=method, output_initial=output_initial)
        from .native_script_arguments import HKSArgument, pack_arguments''', 1)
        # Retain scalar-only exports and their results. Explicit map payloads
        # opt into a new native export using the same protected dispatcher.
        before='''        data=pack_arguments(arguments)
        valid,output=C.c_uint8(0),C.c_uint8(output_initial)'''
        after='''        from civ6_host.runtime.script_event_maps import has_maps, dispatch_maps
        if has_maps(arguments):
            return dispatch_maps(self,name,arguments,method=method,output_initial=output_initial)
        data=pack_arguments(arguments)
        valid,output=C.c_uint8(0),C.c_uint8(output_initial)'''
        if raw.count(before)!=1:raise ValueError('Protected event result boundary changed')
        raw=raw.replace(before,after)
    if name in ('civ6rl.native_aux_map_conversion','civ6rl.native_aux_map_adapter'):
        raw = parameterize_aux_maps(name, raw)
    if name in ('civ6rl.native_checkpoint_load', 'civ6rl.native_host'):
        raw = parameterize_saved_load(name, raw)
    if name == 'civ6rl.native_gameplay_empty':
        raw = parameterize_active_list_reader(raw)
    if name == 'tools.capture_phase1_bundle994':
        old = "if process['gamecore_module']['sha256'] == BASE_CORE_SHA256:"
        if raw.count(old) != 1:
            raise ValueError('Expected one official capture active-list engine boundary')
        raw = raw.replace(old, "from civ6_host.runtime.gameplay_active_profiles import SUPPORTED_CORES\n    if process['gamecore_module']['sha256'] in SUPPORTED_CORES:")
        old = 'return {name: _file(ROOT / name, deadline, 4 * 1024 * 1024) for name in TOOL_FILES}'
        if raw.count(old) != 1:
            raise ValueError('Expected one official capture source-pin collection')
        raw = raw.replace(old, '''pins = {name: _file(ROOT / name, deadline, 4 * 1024 * 1024) for name in TOOL_FILES}
    from civ6_host.runtime.provenance import installed_source_pins
    for path, expected in installed_source_pins().items():
        current = _file(Path(path), deadline, 4 * 1024 * 1024)
        require(current['sha256'] == expected, 'Installed capture source changed during pinning')
        pins['installed:' + path] = current
    return pins''')
    tree = ast.parse(raw)
    if name == 'tools.capture_phase1_bundle994':
        tree = parameterize_capture_continuation(tree)
        tree = parameterize_capture_script_paths_collector(tree)
    if name == 'civ6rl.native_gameplay_source_capture':
        tree = parameterize_capture_script_paths_provider(tree)
    if name == 'civ6rl.native_official_bundle':
        tree = parameterize_capture_continuation_consumer(tree)
    if name == EVENT_ARGUMENT_MODULE:
        tree = parameterize_event_arguments(tree)
    if name == RETAINED_GAME_MODULE:
        tree = parameterize_retained_game(tree)
    if name in DEFERRED_QUEUE_MODULES and name!='civ6rl.native_host_events':
        tree = parameterize_deferred_queue(name, tree)
    if name in APPLICATION_MIRROR_MODULES:
        tree = parameterize_application_mirror(name, tree)
    if name in XP1_PREPARE_MODULES:
        tree = migrate_xp1_prepare_sources(name, tree)
    if name == 'civ6rl.native_script_runtime':
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeScriptRuntime')
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'bind_native_game_api')
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
        fn.args.kw_defaults.append(ast.Constant('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
        fn.body[1:1] = ast.parse('''
if core_sha256 == '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83':
    from .native_xp1_script_bindings import bind_xp1_game_api
    from .native_probe import Windows
    if not hasattr(self.host, 'LAB_XP1ScriptCoreBindingsInstall'):
        raise ValueError('XP1 native API requires its qualified executable export')
    return bind_xp1_game_api(self, context, core_context, core_library,
                           project_root=Path(__file__).resolve().parents[1],
                           module_paths=Windows().modules())
if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
    raise ValueError('Native script API engine is not admitted')
''').body
        tree = parameterize_script_binding_profiles(tree)
        tree = parameterize_script_services(tree)
    if name in ('civ6rl.native_host', 'civ6rl.native_checkpoint_configuration_only',
                'civ6rl.native_xp1_context_init', 'civ6rl.native_xp1_teardown_adapter'):
        tree = parameterize_context_lifecycle(name, tree)
    if name in ('civ6rl.native_application_configuration',
                'civ6rl.native_configuration_finalization', 'civ6rl.native_checkpoint_provider'):
        tree = parameterize_configuration_tree(name, tree)
    if name == 'civ6rl.native_locale_diagnostic':
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_native_lookup')
        fn.args.kwonlyargs.append(ast.arg(arg='explicit_length'));fn.args.kw_defaults.append(ast.Constant(False))
        body=next(n for n in fn.body if isinstance(n,ast.Try)).body
        at=[i for i,n in enumerate(body) if isinstance(n,ast.Assign)
            and ast.unparse(n)=='result = C.string_at(pointer, length.value + 1)']
        if len(at)!=1:raise ValueError('Expected one native String oracle read')
        body[at[0]:at[0]]=ast.parse('''
if explicit_length is True:
    return C.string_at(pointer, length.value)
''').body
    if name == 'civ6rl.native_saved_unit_work':
        node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LUA' for t in n.targets))
        text=node.value.value
        replacements=[
            ('local function add(u,head,tail,legal,row,operation,params)', 'local function add(u,head,tail,legal,row,operation,params,results)'),
            ('row=row,operation=operation,params=params}', 'row=row,operation=operation,params=params,results=results}'),
            ("local legal=bool(UnitManager.CanStartOperation(u,op.BUILD_IMPROVEMENT,nil,selected,true),'improvement legality')", "local permitted,results=UnitManager.CanStartOperation(u,op.BUILD_IMPROVEMENT,nil,selected,true)\n     local legal=bool(permitted,'improvement legality')"),
            ('legal,row,op.BUILD_IMPROVEMENT,request)', 'legal,row,op.BUILD_IMPROVEMENT,request,results)'),
            ("local legal=bool(UnitManager.CanStartOperation(u,operation,nil,false,OperationResultsTypes.NO_TARGETS),'operation legality')", "local permitted,results=UnitManager.CanStartOperation(u,operation,nil,false,OperationResultsTypes.NO_TARGETS)\n      local legal=bool(permitted,'operation legality')"),
            ('legal,row,operation,nil)', 'legal,row,operation,nil,results)'),
        ]
        for old,new in replacements:
            if text.count(old)!=1:raise ValueError('UnitPanel result retention boundary changed')
            text=text.replace(old,new)
        node.value=ast.Constant(text)
    if name == 'civ6rl.native_host_events':
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeDeferredHostEvents')
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_drain_empty_receivers_once')
        changed = 0
        for node in ast.walk(fn):
            if isinstance(node, ast.If) and node.orelse:
                for index, item in enumerate(node.orelse):
                    if (isinstance(item, ast.Assign) and isinstance(item.value, ast.Call)
                            and ast.unparse(item.value.func) == 'validate_empty_profile_record'):
                        node.orelse[index+1:index+1] = ast.parse('''
from civ6_host.runtime.unit_panel_gate import observe_consumed_record
observe_consumed_record(self, record)
''').body
                        changed += 1
                        break
        if changed != 1:
            raise ValueError('Expected one validated empty-receiver FIFO boundary')
        tree = parameterize_deferred_queue(name, tree)
    if name == 'civ6rl.native_saved_actions':
        class WorkGate(ast.NodeTransformer):
            def visit_Call(self, node):
                self.generic_visit(node)
                if ast.unparse(node.func) == 'unit_work.catalog':
                    node.func = ast.Name(id='_unit_panel_work_catalog', ctx=ast.Load())
                    node.args.insert(0, ast.Name(id='owner', ctx=ast.Load()))
                return node
        tree = WorkGate().visit(tree)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'apply_choice')
        changed = 0
        for node in ast.walk(fn):
            if isinstance(node, ast.If):
                for index,item in enumerate(node.body):
                    if (isinstance(item, ast.Assign) and isinstance(item.value, ast.Call)
                            and ast.unparse(item.value.func) == 'unit_work.apply'):
                        item.value.func = ast.Name(id='_apply_unit_panel_terrain',ctx=ast.Load())
                        changed += 1
                        break
        if changed != 1:
            raise ValueError('Expected one terrain-work command boundary')
        tree.body.append(ast.ImportFrom(module='civ6_host.runtime.unit_panel_gate',names=[
            ast.alias(name='catalog',asname='_unit_panel_work_catalog'),
            ast.alias(name='apply_terrain',asname='_apply_unit_panel_terrain')],level=0))
    if name == 'civ6rl.native_plot_purchases':
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'apply')
        changed = 0
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and ast.unparse(node.func) == 'owner.emit':
                for keyword in node.keywords:
                    if keyword.arg == 'ui_tutorial_gate_qualified':
                        keyword.value = ast.parse("gate_admitted(owner, 'plot_purchase')", mode='eval').body
                        changed += 1
        if changed != 1:
            raise ValueError('Expected one plot-purchase source admission receipt')
        tree.body.append(ast.ImportFrom(module='civ6rl.native_ui_profile',
            names=[ast.alias(name='gate_admitted')], level=0))
    if name in ('civ6rl.native_saved_actions', 'civ6rl.native_saved_unit_orders'):
        # Replace only the feature switches whose source-admitted LAN paths
        # reuse these exact adapters. Legacy diagnostic behavior is preserved.
        flags = {'world_input_diagnostic': 'world_input',
                 'unit_order_cancel_diagnostic': 'unit_order_cancel'}
        class FeatureAdmission(ast.NodeTransformer):
            def visit_Call(self, node):
                node = self.generic_visit(node)
                if (isinstance(node.func, ast.Name) and node.func.id == 'getattr'
                        and len(node.args) == 3 and ast.unparse(node.args[0]) == 'owner'
                        and isinstance(node.args[1], ast.Constant)
                        and node.args[1].value in flags
                        and isinstance(node.args[2], ast.Constant) and node.args[2].value is False):
                    return ast.copy_location(ast.Call(func=ast.Name(id='_action_feature_enabled', ctx=ast.Load()),
                        args=[node.args[0], ast.Constant(flags[node.args[1].value])], keywords=[]), node)
                return node
        tree = FeatureAdmission().visit(tree)
        tree.body.append(ast.ImportFrom(module='civ6_host.runtime.network_ui',
            names=[ast.alias(name='feature_enabled', asname='_action_feature_enabled')], level=0))
    if name == 'civ6rl.native_action_session':
        class PublicProductionValidation(ast.NodeTransformer):
            changed=0
            def visit_Call(self,node):
                node=self.generic_visit(node)
                if ast.unparse(node.func)=='production_info.validate':
                    node.func=ast.Name(id='_validate_production_inputs',ctx=ast.Load());self.changed+=1
                return node
        projection=PublicProductionValidation();projection.visit(tree)
        if projection.changed!=2:raise ValueError('Expected two production information validators')
        tree.body.append(ast.ImportFrom(module='civ6_host.contracts.production_inputs',
            names=[ast.alias(name='validate',asname='_validate_production_inputs')],level=0))
        validation = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                          and n.name == 'validate_decisions')
        validation.args.kwonlyargs.append(ast.arg(arg='map_coordinates'))
        validation.args.kw_defaults.append(ast.Constant(False))
        guards = [n for n in validation.body if isinstance(n, ast.If)
                  and ast.unparse(n.test) == 'type(rows) is not list or len(rows) > 4096']
        if len(guards) != 1:
            raise ValueError('Expected one legacy candidate-count guard')
        pos = validation.body.index(guards[0])
        validation.body[pos:pos+1] = ast.parse('''
if type(rows) is not list:
    raise ValueError('Unbounded action catalogue')
from civ6_host.contracts.action_budget import validate_action_count
validate_action_count([row.get('action') if type(row) is dict else None for row in rows],
    world_input=value.get('world_input'), map_coordinates=map_coordinates)
''').body
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeActionSession')
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_configure_closure')
        # Verify/pin the shared sources on LAN even though the diagnostic
        # override remains false. Actual availability is admitted in the worker.
        matched = 0
        for node in fn.body:
            if isinstance(node, ast.If) and ast.unparse(node.test) in (
                    'self.world_input_diagnostic', 'self.unit_order_cancel_diagnostic'):
                flag = ast.unparse(node.test)
                if (flag == 'self.unit_order_cancel_diagnostic'
                        and not any(isinstance(child, ast.Attribute) and child.attr == 'CANCEL_PROOF'
                                    for child in ast.walk(node))):
                    continue
                node.test = ast.parse(flag + " or self.input_profile == 'lan'", mode='eval').body
                if flag == 'self.world_input_diagnostic':
                    for item in node.body:
                        if (isinstance(item, ast.Assign)
                                and ast.unparse(item.targets[0]) == "closure['world_input_diagnostic']"):
                            item.value = ast.Attribute(value=ast.Name(id='self',ctx=ast.Load()),
                                attr='world_input_diagnostic',ctx=ast.Load())
                matched += 1
        if matched != 2:
            raise ValueError('Expected both shared map source-pinning branches')
        accepted = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_accepted_response')
        class CancelAdmissionHook(ast.NodeTransformer):
            changed = 0
            def visit_Call(self, node):
                node = self.generic_visit(node)
                if ast.unparse(node) == "getattr(self, 'unit_order_cancel_diagnostic', False)":
                    self.changed += 1
                    return ast.parse('self._cancel_offer_admitted()', mode='eval').body
                return node
        hook = CancelAdmissionHook()
        hook.visit(accepted)
        if hook.changed != 1:
            raise ValueError('Expected one parent CANCEL admission guard')
        cls.body.extend(ast.parse('''
def _cancel_offer_admitted(self):
    return getattr(self, 'unit_order_cancel_diagnostic', False)
''').body)
    if name == 'civ6rl.native_ui_profile':
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'gate_admitted')
        # Keep the original unknown-name guard and Hotseat receipt path intact.
        guard = next(i for i, n in enumerate(fn.body)
                     if isinstance(n, ast.If) and ast.unparse(n.test) == 'name not in GATE_NAMES')
        fn.body[guard+1:guard+1] = ast.parse('''
from civ6_host.runtime.capture_profiles import LAN_PROFILE
if getattr(getattr(owner, 'inputs', None), 'profile', None) is LAN_PROFILE:
    from civ6_host.runtime.network_ui import gate_available
    return gate_available(owner, name)
''').body
    if name == 'civ6rl.native_official_load':
        # Preserve all frozen diagnostic profiles. The added profile is only
        # usable with exact official-bundle inputs; it has no fixture fallback.
        tree.body.extend(ast.parse('from civ6_host.runtime.capture_profiles import LAN_PROFILE').body)
        functions = {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        fn = functions['validate_profile']
        fn.body[:0] = ast.parse('if profile is LAN_PROFILE:\n    return profile').body
        functions['validate_inputs'].body[:0] = ast.parse('''
if type(inputs) is OfficialInputs and inputs.profile is LAN_PROFILE and inputs.official_bundle is None:
    raise ValueError('LAN inputs require a validated exact official capture')
''').body
        functions['read_inputs'].body[:0] = ast.parse('''
if profile is LAN_PROFILE:
    raise ValueError('There is no historical LAN fixture; supply an exact official capture')
''').body
        functions['roster_readback_source'].body[:0] = ast.parse('''
if profile is LAN_PROFILE:
    from civ6_host.runtime.lan_load import roster_readback_source as lan_roster_source
    return lan_roster_source()
''').body
        cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name == 'OfficialLoadBackend')
        readback = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name == 'read_loaded_diagnostic')
        if not isinstance(readback.body[-1],ast.Return):
            raise ValueError('Official roster readback return boundary changed')
        readback.body[-1:-1] = ast.parse('''
if profile is LAN_PROFILE:
    from civ6_host.runtime.lan_load import human_status_readback_source, validate_loaded_roster
    humans = self.prefix.runtime.evaluate_text(self.prefix.game_child,
        human_status_readback_source(values[3:]), b'@official_loaded_lan_humans', capacity=256)
    result.update(validate_loaded_roster(self, roster, humans))
''').body
    if name == 'tools.run_official_postload909':
        fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name == 'open_official_backend')
        fn.body[:0] = ast.parse('from civ6_host.runtime.capture_profiles import LAN_PROFILE').body
        changed = 0
        for node in fn.body:
            if isinstance(node,ast.Assign) and [ast.unparse(t) for t in node.targets] == ['selected']:
                if not isinstance(node.value,ast.Subscript) or not isinstance(node.value.value,ast.Dict):
                    raise ValueError('Official worker mode selection changed')
                node.value.value.keys.append(ast.Constant('lan'))
                node.value.value.values.append(ast.Name(id='LAN_PROFILE',ctx=ast.Load()))
                changed += 1
        if changed != 1:
            raise ValueError('Expected one official worker mode selection')
        branches = [n for n in fn.body if isinstance(n,ast.If)
                    and ast.unparse(n.test) == "closure.get('official_bundle') is not None"]
        if len(branches) != 1:
            raise ValueError('Expected one captured Load input branch')
        branch=branches[0]
        at=next(i for i,n in enumerate(branch.body) if isinstance(n,ast.Assign)
                and [ast.unparse(t) for t in n.targets]==['captured'])
        branch.body[at+1:at+1]=ast.parse('''
if closure.get('network_checkpoint') is not None:
    from civ6_host.runtime.network_checkpoint import resume_bundle
    captured = resume_bundle(captured, closure)
''').body
    if name == 'civ6rl.native_checkpoint_diagnostic':
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='check_control_boundary')
        fn.args.kwonlyargs.append(ast.arg(arg='allow_uninitialized_private'))
        fn.args.kw_defaults.append(ast.Constant(False))
        guards=[n for n in fn.body if isinstance(n,ast.If) and ast.unparse(n.test)==
                'ring is None or ring.poisoned or ring.cursors[ring.selector & 1] != 0']
        if len(guards)!=1:raise ValueError('Expected one checkpoint private-ring guard')
        at=fn.body.index(guards[0])
        fn.body[at:at+1]=ast.parse('''
if type(allow_uninitialized_private) is not bool:
    raise TypeError('Checkpoint private-ring admission must be Boolean')
if ring is None:
    if not allow_uninitialized_private:
        raise RuntimeError('Checkpoint requires an initialized private bank')
elif ring.poisoned or ring.cursors[ring.selector & 1] != 0:
    raise RuntimeError('Checkpoint requires a drained active private bank')
''').body
        result=next(n.value for n in fn.body if isinstance(n,ast.Return))
        for i,key in enumerate(result.keys):
            if isinstance(key,ast.Constant) and key.value in ('private_selector','private_cursors'):
                result.values[i]=ast.IfExp(test=ast.parse('ring is None',mode='eval').body,
                                          body=ast.Constant(None),orelse=result.values[i])
    if name == 'civ6rl.native_checkpoint_retained_save':
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeRetainedSaveBackend')
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='prepare')
        changed=0
        for node in ast.walk(fn):
            if isinstance(node,ast.Call) and ast.unparse(node.func)=='Win64Stream':
                for keyword in node.keywords:
                    if keyword.arg=='max_calls' and ast.unparse(keyword.value)=='MAX_CALLS':
                        keyword.value=ast.parse("getattr(self, 'stream_call_limit', MAX_CALLS)",mode='eval').body
                        changed+=1
        if changed!=1:raise ValueError('Expected one retained Save writer call budget')
        controls=0
        for node in ast.walk(cls):
            if isinstance(node,ast.Call) and ast.unparse(node.func)=='diagnostic.check_control_boundary':
                node.keywords.append(ast.keyword(arg='allow_uninitialized_private',value=ast.parse(
                    "getattr(self, 'allow_uninitialized_private', False)",mode='eval').body))
                controls+=1
        if controls!=3:raise ValueError('Expected three retained Save boundary checks')
    if name == 'civ6rl.native_session_checkpoint':
        functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        option=functions['validate_option']
        class SaveProfiles(ast.NodeTransformer):
            def visit_Compare(self,node):
                if ast.unparse(node)=="closure.get('input_profile') != 'single'":
                    return ast.parse("closure.get('input_profile') not in ('single','lan')",mode='eval').body
                if ast.unparse(node)=='owner.inputs.profile is not official.SINGLE_PROFILE':
                    return ast.parse('owner.inputs.profile not in (official.SINGLE_PROFILE, official.LAN_PROFILE)',mode='eval').body
                return self.generic_visit(node)
            def visit_Call(self,node):
                if isinstance(node.func,ast.Name) and node.func.id=='boundary':
                    node.func=ast.Name(id='_checkpoint_boundary',ctx=ast.Load())
                return self.generic_visit(node)
        SaveProfiles().visit(option)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SessionSaveBackend')
        SaveProfiles().visit(cls)
        publish=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='publish')
        at=next(i for i,n in enumerate(publish.body) if isinstance(n,ast.Assign)
                and [ast.unparse(t) for t in n.targets]==['manifest'])
        publish.body[at+1:at+1]=ast.parse('''
if self.inputs.profile is official.LAN_PROFILE:
    from civ6_host.runtime.network_checkpoint import finalize_manifest
    manifest = finalize_manifest(self, manifest)
''').body
        tree.body.append(ast.ImportFrom(module='civ6_host.runtime.network_checkpoint',
            names=[ast.alias(name='checkpoint_boundary',asname='_checkpoint_boundary')],level=0))
    if name == 'civ6rl.native_session_resume':
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='save_provenance')
        fn.body[:0]=ast.parse('''
from civ6_host.runtime.capture_profiles import LAN_PROFILE
if inputs.profile is LAN_PROFILE:
    from civ6_host.runtime.network_checkpoint import save_provenance as lan_save_provenance
    return lan_save_provenance(inputs, closure)
''').body
    if name == 'civ6rl.native_official_postload':
        functions = {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        fn = functions['run_postload']
        changed = 0
        for index,node in enumerate(fn.body):
            if isinstance(node,ast.Assign) and [ast.unparse(t) for t in node.targets] == ['major_ids']:
                fn.body[index+1:index+1] = ast.parse('''
if owner.inputs.profile is official.LAN_PROFILE:
    from civ6_host.runtime.lan_load import reference_state
    major_ids = reference_state(owner.captured_bundle)['major_player_ids']
    if tuple(map(int, owner.loaded_roster.decode('ascii').split('|')[3:])) != major_ids:
        raise ValueError('LAN postload roster differs from checked Load readback')
''').body
                changed += 1
                break
        if changed != 1:
            raise ValueError('Expected one postload roster selection')
        fn = functions['observe_saved_player']
        changed = 0
        for node in fn.body:
            if isinstance(node,ast.If) and ast.unparse(node.test) == 'inputs.profile is not official.SINGLE_PROFILE or type(found_city) is not bool':
                node.test = ast.parse('inputs.profile not in (official.SINGLE_PROFILE, official.LAN_PROFILE) or type(found_city) is not bool or (inputs.profile is official.LAN_PROFILE and found_city)',mode='eval').body
                changed += 1
        if changed != 1:
            raise ValueError('Expected one official public observation profile guard')
    if name == 'civ6rl.native_checkpoint_postload160':
        fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name == '_validate_readback')
        class RosterDomain(ast.NodeTransformer):
            changed = 0
            def visit_Compare(self,node):
                if ast.unparse(node) == 'expected_major_ids not in ((0, 1), (0, 1, 2, 3))':
                    self.changed += 1
                    return ast.parse('not 1 <= len(expected_major_ids) <= 64 or any(not 0 <= pid < 64 for pid in expected_major_ids) or tuple(sorted(set(expected_major_ids))) != expected_major_ids',mode='eval').body
                return self.generic_visit(node)
        visitor = RosterDomain()
        visitor.visit(fn)
        if visitor.changed != 1:
            raise ValueError('Expected one postload roster-domain guard')
    if name == 'civ6rl.native_checkpoint_load':
        cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name == 'NativeLoadBackend')
        fn = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name == 'create_reader')
        changed = 0
        for node in ast.walk(fn):
            if isinstance(node,ast.Call) and ast.unparse(node.func) == 'Win64Stream':
                for keyword in node.keywords:
                    if keyword.arg == 'max_calls' and ast.unparse(keyword.value) == 'GAME_READ_MAX_CALLS':
                        keyword.value = ast.Name(id='call_limit',ctx=ast.Load())
                        changed += 1
        if changed != 1:
            raise ValueError('Expected one game stream call limit')
        fn.body[:0] = ast.parse('''
from civ6_host.runtime.capture_profiles import LAN_PROFILE
call_limit = GAME_READ_MAX_CALLS
if getattr(inputs, 'profile', None) is LAN_PROFILE:
    if not 0 < len(inputs.game) <= MAX_BYTES:
        raise ValueError('Captured LAN stream exceeds the byte limit')
    call_limit = max(GAME_READ_MAX_CALLS, len(inputs.game) * 2)
    self.emit('native_lan_stream_budget', game_bytes=len(inputs.game), call_limit=call_limit,
              stream_byte_limit=MAX_BYTES, simulation_rules_changed=False)
''').body
    if name == 'civ6rl.native_app_ownership':
        tree.body.extend(ast.parse('''
from civ6_host.runtime.capture_profiles import LAN_PROFILE
from civ6_host.runtime.lan_capabilities import LAN, ClosedLanBranch, verify_source as verify_lan_source
''').body)
        functions = {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        functions['verify_closed_mode'].body[:0] = ast.parse('''
if type(required_mode) is int and required_mode == LAN:
    verify_lan_source()
    return 'LAN'
''').body
        fn = functions['_verify_captured_bundle_profile']
        changed = 0
        for node in fn.body:
            if isinstance(node,ast.If) and ast.unparse(node.test) == 'profile is SINGLE_PROFILE':
                tail = node.orelse[0]
                if not isinstance(tail,ast.If) or ast.unparse(tail.test) != 'profile is HOTSEAT_FOUR_PROFILE':
                    raise ValueError('Ownership bundle profile boundary changed')
                branch = ast.parse("if profile is LAN_PROFILE:\n    profile_name, expected_mode = ('lan', LAN)").body[0]
                branch.orelse = tail.orelse
                tail.orelse = [branch]
                changed += 1
        if changed != 1:
            raise ValueError('Expected one ownership bundle profile selection')
        cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name == 'ClosedBaseOwnership')
        methods = {n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
        methods['__init__'].body.extend(ast.parse('''
self.lan_branch = ClosedLanBranch(application, captured_bundle) if required_mode == LAN else None
''').body)
        fn = methods['status']
        result = fn.body[-1]
        if not isinstance(result,ast.Return) or not isinstance(result.value,ast.Tuple):
            raise ValueError('Closed ownership status return boundary changed')
        # Keep every existing mode/catalogue/numeric-entry guard before this.
        assignment = ast.Assign(targets=[ast.Tuple(elts=[ast.Name(id='result',ctx=ast.Store()),ast.Name(id='information',ctx=ast.Store())],ctx=ast.Store())],value=result.value)
        fn.body[-1:] = [assignment, *ast.parse('''
if self.lan_branch is not None:
    information.update(self.lan_branch.details(player))
return result, information
''').body]
    if name == 'civ6rl.native_official_bundle':
        # Extend the *input* validation route, including the retained parent
        # admission and localization handoff. Native session guards stay put.
        functions = {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        functions['validate_inputs'].body[:0]=ast.parse('''
from civ6_host.runtime.capture_profiles import LAN_PROFILE
if inputs.profile is LAN_PROFILE and inputs.checkpoint is not None:
    from civ6_host.runtime.network_checkpoint import validate_inputs as validate_lan_checkpoint
    return validate_lan_checkpoint(inputs)
''').body
        functions['validate_closure_profile'].body[:0]=ast.parse('''
if closure.get('input_profile') == 'lan':
    from civ6_host.runtime.network_checkpoint import validate_closure as validate_lan_checkpoint_closure
    return validate_lan_checkpoint_closure(closure)
''').body
        class CaptureModes(ast.NodeTransformer):
            def __init__(self):
                self.changed = 0
            def visit_Tuple(self, node):
                if ast.unparse(node) == "('single', 'hotseat-four')":
                    self.changed += 1
                    return ast.Tuple(elts=[*node.elts,ast.Constant('lan')],ctx=node.ctx)
                return self.generic_visit(node)
        for fn_name in ('create_parent_localization_handoff', 'consume_parent_localization_handoff',
                        '_remember_prepared_bundle', 'read_bundle'):
            if fn_name not in functions:
                raise ValueError('Captured mode extension boundary changed: '+fn_name)
            transform = CaptureModes()
            transform.visit(functions[fn_name])
            if transform.changed != 1:
                raise ValueError('Expected one input-family guard in '+fn_name)
        functions = {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        fn = functions['read_bundle']
        replaced = 0
        for index,node in enumerate(fn.body):
            if isinstance(node,ast.Assign) and [ast.unparse(t) for t in node.targets] == ['profile']:
                if ast.unparse(node.value) != "SINGLE_PROFILE if input_profile == 'single' else HOTSEAT_FOUR_PROFILE":
                    raise ValueError('Capture profile selection boundary changed')
                fn.body[index] = ast.parse('profile = profile_for_capture(input_profile)').body[0]
                replaced += 1
        if replaced != 1:
            raise ValueError('Expected one capture profile selection')
        for node in ast.walk(fn):
            if isinstance(node,ast.Constant) and node.value == 'Only Base Single and four-human Hotseat Load families are supported':
                node.value = 'Unsupported Base official capture input family'
        fn.body[:0] = ast.parse('from civ6_host.runtime.capture_profiles import profile_for_capture').body
        fn = functions['_reuse_prepared_bundle']
        replaced = 0
        for node in fn.body:
            if isinstance(node,ast.Assign) and [ast.unparse(t) for t in node.targets] == ['expected_profile']:
                if not isinstance(node.value,ast.Dict) or len(node.value.keys) != 2:
                    raise ValueError('Prepared capture profile registry boundary changed')
                node.value.keys.append(ast.Constant('lan'))
                node.value.values.append(ast.Name(id='LAN_PROFILE',ctx=ast.Load()))
                replaced += 1
        if replaced != 1:
            raise ValueError('Expected one prepared capture profile registry')
        fn.body[:0] = ast.parse('from civ6_host.runtime.capture_profiles import LAN_PROFILE').body
    if name in ('civ6rl.native_diagnostic_roster', 'civ6rl.native_unit_skip'):
        target = 'validate_roster' if name.endswith('native_diagnostic_roster') else '_validated_player_ids'
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == target)
        fn.body = ast.parse('''
from civ6_host.runtime.network_owner import roster
return roster(player_ids)
''').body
    if name == 'civ6rl.native_action_transport':
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == 'NativeActionTransport']
        if len(classes) != 1 or any(isinstance(n, ast.FunctionDef)
                and n.name == 'request_unready_turn' for n in classes[0].body):
            raise ValueError('Native turn transport extension boundary changed')
        classes[0].body.extend(ast.parse('''
def request_unready_turn(self, player, *, player_ids=(0, 1)):
    from civ6_host.runtime.turn_requests import request_unready_turn
    return request_unready_turn(self, player, player_ids=player_ids)
''').body)
    if name == 'civ6rl.native_host_events':
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == 'NativeDeferredHostEvents')
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == '_dispatch_fields')
        if ast.unparse(fn.body[0]) != 'self._require_no_f391_reentry()':
            raise ValueError('Host notification reentry guard changed')
        fn.body[1:1] = ast.parse('''
if kind == 0xC08FC0F9:
    from civ6_host.runtime.goody_hut_reward import enqueue
    return enqueue(self, raw_fields)
''').body
    if name == 'civ6rl.native_deferred_empty_profile':
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == '_load_rows')
        if not isinstance(fn.body[-1], ast.Return) or ast.unparse(fn.body[-1].value) != 'rows':
            raise ValueError('Deferred receiver row loader changed')
        fn.body[-1:-1] = ast.parse('''
from civ6_host.runtime.goody_hut_reward import receiver_row as goody_hut_reward_row
if 0x103 in rows:
    raise RuntimeError('GoodyHutReward row collides with historical profile')
rows[0x103] = goody_hut_reward_row()
''').body
    if name == 'civ6rl.native_turn_continuation':
        functions = {n.name:n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for operation in ('validate', 'resume'):
            functions[operation].body[:0] = ast.parse(f'''
if getattr(getattr(owner, 'turn_continuation', None), 'origin', None) == 'network':
    from civ6_host.runtime.network_dialogue import {operation} as network_{operation}
    return network_{operation}(owner)
''').body
    if name == 'civ6rl.native_saved_actions':
        functions = {n.name:n for n in tree.body if isinstance(n, ast.FunctionDef)}
        catalogue = functions['read_decisions']
        guards = [n for n in catalogue.body if isinstance(n, ast.If)
                  and ast.unparse(n.test) == 'len(actions) > 4096']
        if len(guards) != 1:
            raise ValueError('Expected one legacy producer action-count guard')
        pos = catalogue.body.index(guards[0])
        catalogue.body[pos:pos+1] = ast.parse('''
from civ6_host.contracts.action_budget import validate_action_count
validate_action_count(actions, world_input=world_state,
    map_coordinates=owner.inputs.profile is official.LAN_PROFILE)
''').body
        functions['_check_player_context'].body[:0] = ast.parse('''
if profile is official.LAN_PROFILE:
    from civ6_host.runtime.network_owner import roster as validate_network_roster, STAGE
    validate_network_roster(player_ids)
    if stage != STAGE or player_ids != roster or type(player_id) is not int or player_id not in roster:
        raise RuntimeError('LAN decisions require the exact admitted roster and boundary')
    return player_id
''').body
        boundary_fn = functions['boundary']
        boundary_fn.body[-1:-1] = ast.parse('''
if owner.inputs.profile is official.LAN_PROFILE:
    from civ6_host.runtime.network_owner import require_actor
    require_actor(owner, player_id, player_ids)
''').body
        read_fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'read_decisions'), None)
        apply_fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
                         and n.name == 'apply_choice'), None)
        if read_fn is None or apply_fn is None:
            raise ValueError('Decision context wrapper boundaries changed')
        read_fn.name = '_read_decisions_without_context'
        apply_fn.name = '_apply_choice_without_context'
        # A command can publish a statement. Retain it before the old generic
        # empty-control check, without fabricating a Single turn continuation.
        at = next(i for i,n in enumerate(apply_fn.body) if isinstance(n,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id == 'interrupted' for t in n.targets))
        apply_fn.body[at:at] = ast.parse('''
if owner.inputs.profile is official.LAN_PROFILE:
    from civ6_host.runtime.network_dialogue import retain
    retain(owner)
''').body
        interrupt = next(n for n in apply_fn.body if isinstance(n,ast.If)
                         and isinstance(n.test,ast.Name) and n.test.id == 'interrupted')
        branch = next(n for n in interrupt.body if isinstance(n,ast.If))
        network_branch = ast.parse('''
if retained.origin == 'network':
    if type(after) is not dict or after['player_id'] != pid or after['turn'] != turn:
        raise RuntimeError('LAN action-created dialogue changed actor or turn')
''').body[0]
        network_branch.orelse = [branch]
        interrupt.body[interrupt.body.index(branch)] = network_branch
        # Preserve the actor-offer check in both multi-actor profiles. The
        # earlier Hotseat-only actor/turn assertion intentionally stays intact.
        for node in ast.walk(apply_fn):
            if (isinstance(node, ast.If) and node.body
                    and isinstance(node.body[0], ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'offers'
                            for t in node.body[0].targets)):
                node.test = ast.parse("getattr(getattr(owner, 'inputs', None), 'profile', None) in (official.HOTSEAT_FOUR_PROFILE, official.LAN_PROFILE)", mode='eval').body
        wrappers = ast.parse('''
def read_decisions(owner, sequence, rounds, *, closed=False, round_limit=8,
                   player_id=0, player_ids=(0, 1)):
    if getattr(owner, 'turn_continuation', None) is not None:
        return _read_decisions_without_context(owner, sequence, rounds,
            closed=closed, round_limit=round_limit, player_id=player_id,
            player_ids=player_ids)
    # Keep the existing actor/profile admission in front of cache access.
    prefix = boundary(owner, player_id=player_id, player_ids=player_ids)
    from civ6_host.runtime.native.native_episode_identity import require_episode
    from civ6_host.runtime.decision_context import store_for
    store = store_for(owner)
    store.invalidate_player(owner, player_id, reason='decision_read_replaced')
    missing = object()
    previous_world_input = getattr(owner, 'explicit_world_input', missing)
    if previous_world_input is not missing:
        delattr(owner, 'explicit_world_input')
    try:
        result = _read_decisions_without_context(owner, sequence, rounds,
            closed=closed, round_limit=round_limit, player_id=player_id,
            player_ids=player_ids)
        identity = require_episode(prefix)
        observation = result[0]
        decision = result[1]
        store.capture(owner, episode_id=identity.episode_id,
            game_generation=identity.game_generation, roster=player_ids,
            player_id=player_id, turn=observation['turn'],
            decision_id=decision['decision_id'], sequence=decision['sequence'])
        return result
    except BaseException:
        if previous_world_input is not missing:
            owner.explicit_world_input = previous_world_input
        store.invalidate_player(owner, player_id, reason='decision_read_failed')
        raise

def apply_choice(owner, action, turn, *, player_id=0, player_ids=(0, 1)):
    from civ6_host.runtime.decision_context import store_for
    store = store_for(owner)
    if getattr(owner, 'turn_continuation', None) is not None:
        try:
            result = _apply_choice_without_context(owner, action, turn,
                player_id=player_id, player_ids=player_ids)
        except BaseException:
            store.invalidate_all(owner, reason='continuation_command_failed')
            raise
        store.invalidate_player(owner, player_id, reason='continuation_command_consumed')
        return result
    # Never let the snapshot cache bypass the original profile/actor guards.
    prefix = boundary(owner, player_id=player_id, player_ids=player_ids)
    from civ6_host.runtime.native.native_episode_identity import require_episode
    identity = require_episode(prefix)
    activated = False
    try:
        with store.activate(owner, episode_id=identity.episode_id,
                game_generation=identity.game_generation, roster=player_ids,
                player_id=player_id, turn=turn):
            activated = True
            try:
                result = _apply_choice_without_context(owner, action, turn,
                    player_id=player_id, player_ids=player_ids)
            except BaseException:
                store.invalidate_all(owner, reason='command_failed')
                raise
            store.invalidate_player(owner, player_id, reason='command_consumed')
            return result
    except BaseException:
        # A stale/missing activation did not enter native execution. Once the
        # adapter ran, its failure has uncertain world effects and clears all.
        if activated:
            store.invalidate_all(owner, reason='apply_failed')
        raise
''').body
        tree.body.extend(wrappers)
    if name == 'civ6rl.native_hotseat_session':
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeHotseatActionSession')
        if [ast.unparse(b) for b in cls.bases]!=['NativeActionSession']:
            raise ValueError('Hotseat session class boundary changed')
        cls.bases.insert(0,ast.Name(id='SessionViewsMixin',ctx=ast.Load()))
        tree.body.insert(tree.body.index(cls),ast.parse('from civ6_host.runtime.player_views import SessionViewsMixin').body[0])
    if name == 'tools.official_hotseat_worker923':
        replies=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='reply']
        if len(replies)!=1:raise ValueError('Hotseat reply hook boundary changed')
        fn=replies[0]
        at=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='fields' for t in n.targets))
        fn.body[at:at]=ast.parse('from civ6_host.runtime.player_views import publish_player_views\npublish_player_views(emit, owner, protocol, observation, closure, path)').body
    if name in ('tools.official_hotseat_worker923','tools.official_action_worker920'):
        for handler in ast.walk(tree):
            if isinstance(handler,ast.ExceptHandler) and any(
                isinstance(n,ast.Call) and n.args and isinstance(n.args[0],ast.Constant)
                and n.args[0].value=='official_session_refused' for n in ast.walk(handler)):
                handler.body[:0]=ast.parse('import traceback\ntraceback.print_exc(file=sys.stderr)').body
    reference_producers={'civ6rl.native_response_file_writer':'reference','tools.capture_phase1_bundle974':'_file_state'}
    if name in reference_producers:
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==reference_producers[name])
        fn.body.insert(0,ast.parse('from civ6_host.runtime.resource_resolution import historical_reference').body[0])
        for node in ast.walk(fn):
            if isinstance(node,ast.Return) and node.value is not None:
                node.value=ast.Call(func=ast.Name(id='historical_reference',ctx=ast.Load()),args=[node.value],keywords=[])
    if name == 'civ6rl.native_official_bundle':
        additions={
            'read_bundle':'''from civ6_host.runtime.capture_admission import try_bundle
prepared = try_bundle(reference, input_profile=input_profile)
if prepared is not None:
    return prepared
''',
            '_localization':'''from civ6_host.runtime.capture_admission import try_localization
prepared = try_localization(manifest, dependencies, reference=cache_key)
if prepared is not None:
    return prepared
''',
            'consume_parent_localization_handoff':'''from civ6_host.runtime.capture_admission import consume_prepared_closure
prepared = consume_prepared_closure(closure, environment=environment)
if prepared is not None:
    return prepared
'''}
        for fn in tree.body:
            if isinstance(fn,ast.FunctionDef) and fn.name in additions:
                at=1 if fn.body and isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant) and isinstance(fn.body[0].value.value,str) else 0
                fn.body[at:at]=ast.parse(additions[fn.name]).body
    if name == 'civ6rl.native_probe':
        keep = {'digest','prepare_init_fixture_copies','_source_manifest_entry'}
        tree.body = [n for n in tree.body if not isinstance(n,ast.FunctionDef) or n.name in keep]
        tree.body = [n for n in tree.body if not isinstance(n,ast.If)]
    if name == 'tools.run_official_postload909':
        tree.body = [n for n in tree.body if not isinstance(n,ast.FunctionDef)
                     or n.name in {'sha','open_official_backend'}]
        tree.body = [n for n in tree.body if not isinstance(n,ast.If)]
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='open_official_backend')
        fn.body[1:1]=ast.parse('from civ6_host.runtime.resource_resolution import validate_closure\nvalidate_closure(closure)').body
    if name == 'civ6rl.learning.skill_task991':
        keep = {'project_public_observation','validate_public_sources','validate_public_witness','_require','_int'}
        constants = {'PUBLIC_WITNESS_SCHEMA','PUBLIC_OBSERVATION_SCHEMA','_PUBLIC_SOURCES'}
        tree.body = [n for n in tree.body if
            isinstance(n,(ast.Import,ast.ImportFrom)) or
            isinstance(n,ast.FunctionDef) and n.name in keep or
            isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets)]
    if name == 'civ6rl.native_official_load':
        prefix=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='OfficialPrefix')
        method=next(n for n in prefix.body if isinstance(n,ast.FunctionDef) and n.name=='verify_configuration_scalar_marshalling')
        shared=ast.ClassDef(name='SavedConfigurationReadback',bases=[],keywords=[],body=[method],decorator_list=[])
        prefix.body.remove(method)
        prefix.bases.insert(0,ast.Name(id=shared.name,ctx=ast.Load()))
        tree.body.insert(tree.body.index(prefix),shared)
    if name == 'civ6rl.native_context_notify':
        fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verify_loaded_host')
        fn.body=ast.parse('from civ6_host.runtime.script_context_source import verify_notification_host\nverify_notification_host(host)').body
    if name == 'civ6rl.native_map_script':
        # Keep one implementation of synchronous GameEvents, usable without
        # constructing the retained NewGame diagnostic prefix. Its old class
        # inherits these exact methods, preserving existing Base behaviour.
        prefix = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                      and n.name == 'NativeMapScriptPrefix')
        names = {'check', 'game_event_call', 'game_event_test_all'}
        methods = [n for n in prefix.body if isinstance(n, ast.FunctionDef) and n.name in names]
        if {n.name for n in methods} != names or prefix.bases:
            raise ValueError('Shared script-event extraction boundary changed')
        shared = ast.ClassDef(name='NativeGameEventCallbacks', bases=[], keywords=[],
                              body=methods, decorator_list=[])
        prefix.body = [n for n in prefix.body if n not in methods]
        prefix.bases = [ast.Name(id=shared.name, ctx=ast.Load())]
        tree.body.insert(tree.body.index(prefix), shared)
        class RemoveEmbeddedChooser(ast.NodeTransformer):
            def visit_ImportFrom(self, node):
                if node.module == 'native_diagnostic_mac_chooser':
                    return ast.Raise(exc=ast.Call(func=ast.Name(id='RuntimeError',ctx=ast.Load()),args=[
                        ast.Constant('Embedded diagnostic policies are not part of the host; use explicit client choices')],keywords=[]),cause=None)
                return node
        tree = RemoveEmbeddedChooser().visit(tree)
    if name == 'civ6rl.native_city_range_attack':
        collector=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='collect_player_observation')
        if 'spec_from_file_location' not in ast.unparse(collector):
            raise ValueError('City observation loader boundary changed')
        collector.body=ast.parse('''
_pid(player_id)
from .native_player_observation import observe_player
return observe_player(runtime, child, player_id)
''').body
        tree.body=[n for n in tree.body if not (isinstance(n,ast.Import) and
            any(a.name=='importlib.util' for a in n.names))]
    if name=='civ6rl.native_host_events':
        tree=share_a0_dispatch(tree)
    if name in CACHE_FACADE_MODULES:
        tree=parameterize_cache_facades(name,tree)
    if name==PLAYER_NOTIFICATION_MODULE:
        tree=parameterize_player_notifications(tree)
    return ast.fix_missing_locations(tree)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args()
    source=args.source.resolve()
    repo=Path(__file__).resolve().parents[1]
    target=repo/'src/civ6_host/runtime'
    prior_map_path=target/'source-map.json'
    prior_map=json.loads(prior_map_path.read_text(encoding='utf-8')) if prior_map_path.is_file() else {}
    maintained_overlays = {
        'civ6rl.native_official_bundle': (
            'host-maintained exact stock XP2 response writer source archive validation',
            '7eb90487b13b23e2bdc2def6a8862c985e083a3d5d27ea1afc150c01864294bd'),
        'civ6rl.native_policy_catalog': (
            'host-maintained explicit opt-in active-policy relocation parser; legacy defaults unchanged',
            '1a1ccd4a1cd2ee51b4c56cddd621a6e583e070b0ee4af9ebb46710080115533e'),
        'civ6rl.native_event_e660_building_pillaged': (
            'host-maintained pinned snapshot archive and transitive codec source dependencies',
            '3c656c627e6b9f795d4ae926634e0f32373008b7096f4c9e5a300829221deb9d'),
        'civ6rl.native_event_e66012a7': (
            'host-maintained source-qualified XP2 wonder completion through the shared ordered producer',
            '5904d5e38b2d62ebc122124f845f44afed2db345f46e018d325a4be7becd9555'),
        'civ6rl.native_saved_city_targets': (
            'host-maintained shared city-target proof path for the installed source closure',
            '55e4f0d424b0b67bf72088c99b819c20f0195d90902d6320dd39b6d965cb73af'),
        'civ6rl.native_saved_captured_city': (
            'host-maintained captured-city profile admission and native occupation effect verification',
            'b85e62b78d2cfa423e81d469ddc2e8b74dca0e088c3356b7a5786c159b973bdc'),
        'civ6rl.native_saved_unit_work': (
            'host-maintained opt-in XP2 adjacent target adapter; not admitted by the saved-session API',
            '8b604a78767c97095fe81ee5128cede63abb7f6f1d3a3d5be50605d10b41887a'),
        'civ6rl.native_aux_map_conversion': (
            'host-maintained XP2 script operation vector and bounded table encoding',
            '09dd1f53adf71fe2662c6157754f2137fa9196a5c9632cd1cc3c505d77d5c394'),
        'tools.run_official_postload909': (
            'host-maintained single pre-Load expansion checkpoint lineage verification',
            '3ab578f3920df23030e95640e8e0324da253ff0c2f6c3ddd0f6f3762721106d1'),
        'civ6rl.native_saved_unit_orders': (
            'host-maintained XP2 native skip-turn order through the shared operation catalogue',
            'd46d0c0a212aacea81a473412c8a80a4078ebe8dda382fce5ba95c86fbbb3d1d'),
        'civ6rl.native_saved_trade': (
            'host-maintained opt-in World A BBG trade quote helper; stock legality and default helper preserved',
            'c4ff4f42cd482edcc581853378a96b708b2acfdde08398f94707c9b1a3a4bbeb'),
        'civ6rl.native_deferred_empty_profile': (
            'host-maintained current XP2 FeatureAddedToMap empty receiver row through the shared FIFO',
            'f1709d7135f7e78e29d56d923918f515f71e233d9e6c8e23f83a06982db684b9'),
    }
    paths={'civ6rl.'+p.stem:p for p in (source/'civ6rl').glob('*.py')}
    paths.update({'civ6rl.learning.'+p.stem:p for p in (source/'civ6rl/learning').glob('*.py')})
    paths.update({'tools.'+p.stem:p for p in (source/'tools').glob('*.py')})
    aliases={key.split('.',1)[1]:key for key in paths if key.startswith('tools.')}

    def absolute(node, current):
        base=node.module or ''
        if node.level:
            parts=current.split('.')[:-1]
            base='.'.join(parts[:len(parts)-node.level+1]+([base] if base else []))
        return aliases.get(base,base)

    def remap(name):
        name=aliases.get(name,name)
        if name in SPECIAL:return SPECIAL[name]
        if name.startswith('civ6rl.learning.'):
            return CONTRACTS[name.split('.')[-1]]
        if name=='civ6rl':return NATIVE
        if name.startswith('civ6rl.'):return NATIVE+name[len('civ6rl'):]
        if name=='tools':return WORKERS
        if name.startswith('tools.'):return WORKERS+name[len('tools'):]
        return name

    trees={};edges={};pending=list(SEEDS)
    while pending:
        name=pending.pop()
        if name in trees or name.split('.')[-1] in CONTRACTS and name.startswith('civ6rl.learning.'):continue
        if name not in paths:raise ValueError('Missing local module '+name)
        if name.startswith('civ6rl.learning.') and name not in SPECIAL:raise ValueError('Unreviewed learner dependency '+name)
        tree=prepare_tree(name,paths[name].read_text(encoding='utf-8-sig'))
        deps=set()
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):
                for a in n.names:
                    key=aliases.get(a.name,a.name)
                    if key in paths:deps.add(key)
            elif isinstance(n,ast.ImportFrom):
                base=absolute(n,name)
                if base in paths:deps.add(base)
                for a in n.names:
                    key=base+'.'+a.name if base else a.name
                    if key in paths:deps.add(key)
            elif isinstance(n,ast.Call) and ast.unparse(n.func) in ('__import__','importlib.import_module'):
                if not n.args or not isinstance(n.args[0],ast.Constant) or not isinstance(n.args[0].value,str):
                    raise ValueError('Dynamic module name must be explicitly reviewed: '+name)
                key=aliases.get(n.args[0].value,n.args[0].value)
                if key in paths:deps.add(key)
        trees[name]=tree;edges[name]=sorted(deps);pending.extend(deps)

    class Rewrite(ast.NodeTransformer):
        def __init__(self,name):
            self.name=name;self.origin=paths[name].relative_to(source).as_posix()

        def visit_ImportFrom(self,node):
            base=absolute(node,self.name)
            pieces=[]
            for a in node.names:
                key=base+'.'+a.name if base else a.name
                if key in paths and key in SPECIAL or key.startswith('civ6rl.learning.') and key.split('.')[-1] in CONTRACTS:
                    mapped=remap(key);parent,leaf=mapped.rsplit('.',1)
                    pieces.append(ast.ImportFrom(module=parent,names=[ast.alias(name=leaf,asname=a.asname or a.name)],level=0))
                else:
                    pieces.append(ast.ImportFrom(module=remap(base),names=[a],level=0))
            return pieces

        def visit_Import(self,node):
            for a in node.names:
                old=a.name;a.name=remap(old)
                if a.name!=old and a.asname is None:
                    raise ValueError('Qualified import needs explicit rewrite: '+self.name+' '+old)
            return node

        def visit_Name(self,node):
            if node.id=='__file__':
                return ast.Call(func=ast.Name(id='_historical_source_file',ctx=ast.Load()),args=[ast.Constant(self.origin)],keywords=[])
            return node

        def visit_Call(self,node):
            if ast.unparse(node.func) in ('__import__','importlib.import_module'):
                if not node.args or not isinstance(node.args[0],ast.Constant) or not isinstance(node.args[0].value,str):
                    raise ValueError('Unreviewed dynamic import in '+self.name)
                node.args[0]=ast.Constant(remap(node.args[0].value))
            return self.generic_visit(node)

        def visit_Attribute(self,node):
            if node.attr=='__file__':
                return ast.Call(func=ast.Name(id='_historical_module_file',ctx=ast.Load()),args=[self.visit(node.value)],keywords=[])
            return self.generic_visit(node)

        def visit_Expr(self,node):
            if isinstance(node.value,ast.Call) and ast.unparse(node.value.func).startswith('sys.path.'):
                return None
            return self.generic_visit(node)

        def visit_Assign(self,node):
            if any(isinstance(t,ast.Subscript) and ast.unparse(t.value)=='sys.path' for t in node.targets):return None
            return self.generic_visit(node)

        def visit_If(self,node):
            node=self.generic_visit(node)
            if not node.body:node.body=[ast.Pass()]
            return node

    class ResourcePaths(ast.NodeTransformer):
        def visit_Call(self,node):
            node=self.generic_visit(node)
            if ast.unparse(node.func).startswith('_BootstrapPath('):
                return node
            if isinstance(node.func,ast.Name) and node.func.id=='Path':
                return ast.Call(func=ast.Name(id='_resolve_resource_path',ctx=ast.Load()),args=[node],keywords=[])
            if isinstance(node.func,ast.Attribute) and node.func.attr in ('resolve','read_bytes','read_text','open','stat','is_file','is_dir','exists'):
                node.func.value=ast.Call(func=ast.Name(id='_resolve_resource_path',ctx=ast.Load()),args=[node.func.value],keywords=[])
            return node

    rows=[]
    helpers=ast.parse('from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins\nfrom civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path').body
    for name,original in sorted(trees.items()):
        tree=Rewrite(name).visit(copy.deepcopy(original));tree=ast.fix_missing_locations(tree)
        # Imports must follow future imports and the module docstring.
        at=0
        while at<len(tree.body) and (isinstance(tree.body[at],ast.Expr) and isinstance(tree.body[at].value,ast.Constant)
                and isinstance(tree.body[at].value.value,str) or isinstance(tree.body[at],ast.ImportFrom) and tree.body[at].module=='__future__'):
            at+=1
        tree.body[at:at]=copy.deepcopy(helpers)
        text=ast.unparse(ast.fix_missing_locations(tree))+'\n'
        transformations=['imports mapped to installed host modules','historical source paths retained for old proofs; executed files separately pinned','lab sys.path injection removed','filesystem Path references resolved through explicit private resource mapping; JSON evidence bytes unchanged']
        if name in CACHE_FACADE_MODULES:
            transformations.append('existing native cache-facade factory/copy/replacement/release sequence selects an explicit Base/XP1 ABI; copy helper preserves the same body; XP1 full publication remains refused; prepared metadata does not open the public cache gate')
        if name==PLAYER_NOTIFICATION_MODULE:
            transformations.append('existing Player/component lease, getter order, null handling and reverse releases select exact Base/XP1 ABI; Base constants/default remain unchanged')
        if name=='civ6rl.native_host_events':
            transformations.append('Player notification query uses an overridable lease seam; Base forwards its original arguments; enqueue remains inside the same context manager before temporary references release')
        if name=='civ6rl.native_official_load':
            transformations+=['extract saved configuration readback into shared mixin; historical OfficialPrefix inherits the same method, no Base execution change']
        if name=='civ6rl.native_context_notify':
            transformations+=['retain notification lifecycle and source capture; explicitly admit new source-built notification prefix without private oracle bytes, via separate executable identity verifier']
        if name=='civ6rl.native_context_lifetime':
            transformations+=['reuse retained single-owner lifetime without changing acquire/claim/unlink/release semantics']
        if name=='civ6rl.native_aux_map_conversion':
            transformations.append('one shared tree reader/emitter supports explicitly source-qualified nested maps in V2; per-map resolver, aggregate budget, cycle/depth and stability checks; legacy default still refuses nested map tags')
        if name=='civ6rl.native_script_arguments':
            transformations.append('argument evidence recognizes owned native ParameterMap arguments; scalar-only packing contract remains unchanged')
        if name=='civ6rl.native_script_runtime':
            transformations.append('mixed map arguments select explicit negotiated native export sharing protected dispatch and A8 transport; scalar-only export and result contracts preserved')
            transformations.append('XP2 game-API registration selects an explicit guarded official Core binder profile; Base/XP1 branches unchanged, no expansion Load admission')
            transformations.append('explicit XP2 script-service borrow verifies source-bound Init/connection owners before reusing the same three Lua binds; legacy reads retained, lease invalidated before unbind')
        if name == 'civ6rl.native_gameplay_empty':
            transformations.append('same bounded read-only active-list reader parameterized by hash-pinned Base/XP layouts; Base defaults unchanged, unknown engines explicit, no saved-Load admission')
        if name == EVENT_ARGUMENT_MODULE:
            transformations.append('same bounded borrowed event-tree copy with exact Base/XP1 layout and live method profile; Base default unchanged, pointee ownership and event semantics remain separate')
        if name == RETAINED_GAME_MODULE:
            transformations.append('same retained Game getter call and cache-branch checks with an explicit Base/XP1 ABI; no scalar substitution or extra Game construction')
        if name == 'tools.capture_phase1_bundle994':
            transformations.append('official capture reuses same active-list collector for source-qualified engine layouts; source/load/gameplay-script execution qualification remains separate')
            transformations.append('capture source closure retains historical sources and additionally pins actual installed Python/source-map files; no producer identity substitution')
            transformations.append('explicit closed response-prefix continuation selects existing direct transport with authenticated counters; default empty-directory admission unchanged, no command replay or fallback')
            transformations.append('explicit pinned relative script-path context is joined to actual process and raw selection before database reads; default absolute/empty capture unchanged')
        if name == 'civ6rl.native_gameplay_source_capture':
            transformations.append('optional observed working-directory/native path-copy witness preserves raw selected names separately from canonical sources; live capture rechecks process/CWD, offline reads retain immutable mapping and byte pins')
        if name == 'civ6rl.native_official_bundle':
            transformations.append('saved-input reader preserves explicitly authenticated capture predecessor, immutable log prefix and native payload pins; original direct/legacy captures unchanged')
        if name=='civ6rl.native_ui_profile':
            transformations+=['LAN city and plot-purchase gates delegate to separate source admission; unknown-name guard and Hotseat receipts unchanged; network_owner retains forced-turn composition']
        if name in ('civ6rl.native_saved_actions', 'civ6rl.native_saved_unit_orders'):
            transformations+=['world-input and ordinary-unit CANCEL reuse separately admitted LAN features; legacy explicit diagnostic switches preserved']
        if name=='civ6rl.native_action_session':
            transformations+=['production validators dispatch explicit public production-info v1 or unchanged historical diagnostic schema; native quote collection and source checks remain unchanged']
            transformations+=['explicit map-coordinate budget opt-in for network-decisions.v3; default legacy 4096-choice contract unchanged']
            transformations+=['LAN pins existing world-input and ordinary-unit CANCEL sources without turning on diagnostic overrides; worker source admission remains required']
            transformations+=['parent CANCEL offer validation uses an admission hook; legacy diagnostic rule unchanged, LAN subclass binds its verified source admission to the exact bundle']
        if name=='civ6rl.native_locale_diagnostic':
            transformations+=['explicit_length oracle mode reads exactly toUTF8 length as the official Lua callback; historical default terminator check remains unchanged']
        if name=='civ6rl.native_plot_purchases':
            transformations+=['plot effect receipt reports the actual separately admitted UI gate instead of a fixed diagnostic false value; native price/ownership/command logic unchanged']
        if name=='civ6rl.native_action_transport':
            transformations+=['internal UNREADY emission method delegates to pinned official Core+0x200 wrapper; native delivery, session admission and public action availability remain separate']
        if name=='civ6rl.native_host_events':
            transformations.append('one unchanged A0 dispatch body and reentry/scope helpers shared with Base; XP1 family admission remains separate and source-bound')
            transformations.append('shared empty-presentation consumer preserves existing validation/commit order; each owning service explicitly admits its record families')
            transformations+=['GoodyHutReward copies the source-proven unit/city notification into the existing bounded queue; Core reward/internal dispatch are not repeated']
        if name=='civ6rl.native_deferred_empty_profile':
            transformations+=['GoodyHutReward row 0x103 extends the same empty receiver validator through a separately pinned EXE initializer/handler proof']
        if name=='civ6rl.native_turn_continuation':
            transformations+=['network-origin continuations delegate to the LAN owner lifecycle; existing Single generators are unchanged and never reused to schedule LAN turns']
        if name=='civ6rl.native_saved_actions':
            transformations+=['terrain work on admitted Base LAN uses the source-bound UnitPanel processing guard; other profiles keep the retained adapter behavior']
            transformations+=['LAN map coordinates have a separate geometry-bound budget up to 16384 cells; ordinary actions remain bounded at 4096 and other profiles retain their original cap']
            transformations+=['decision aliases stored in a bounded episode/roster/turn/player cache; apply activates one player snapshot only after unchanged boundary guards; a consumed choice invalidates its player context while uncertain failures clear all; shared placement tracking stays episode-wide; optional world-input alias is cleared around reads']
            transformations+=['explicit LAN boundary binds saved roster and active captured human before reader/adapter access; immediate native catalogue revalidation is handled by network_owner; LAN turns remain explicitly refused']
            transformations+=['action-emitted LAN statements are retained before the empty-control check; responses reuse the original official diplomacy reader/transport without automatic updates']
        if name in ('civ6rl.native_diagnostic_roster','civ6rl.native_unit_skip'):
            transformations+=['shared roster syntax accepts unique native IDs 0..63; admission remains in exact saved-profile/active-human owner boundary, not in syntax helpers']
        if name=='tools.official_hotseat_worker923':
            transformations+=['opt-in latest-boundary public player views emitted separately before unchanged legacy reply']
        if name=='civ6rl.native_hotseat_session':
            transformations+=['opt-in public view mixin integrated in exact retained hotseat session class; exact-class admission preserved']
        if name=='civ6rl.native_saved_session':
            for old,new in (
                ("closure['lifetime_seconds'] <= 180", "closure['lifetime_seconds'] <= __import__('civ6_host.runtime.session_limits', fromlist=['standard_lifetime_limit']).standard_lifetime_limit(closure.get('input_profile'))"),
                ('MAX_EPISODE_SECONDS if budget is not None else 180', "MAX_EPISODE_SECONDS if budget is not None else __import__('civ6_host.runtime.session_limits', fromlist=['standard_lifetime_limit']).standard_lifetime_limit(self.input_profile)"),
                ('Native closure without an extended budget retains its 180-second ceiling', 'Native closure exceeds its standard profile lifetime ceiling')):
                if text.count(old)!=1:raise ValueError('Saved session standard lifetime guard changed')
                text=text.replace(old,new)
            transformations+=['standard diagnostic lifetime is selected by input profile: XP1 maximum300s; Base180s, memory, output, clock/watch/reaping and learner budgets unchanged']
            old='self.protocol.initial_turn = captured.initial_turn'
            if text.count(old)!=1:raise ValueError('Captured initial protocol turn binding changed')
            text=text.replace(old,"self.protocol.initial_turn = closure['initial_turn']")
            transformations+=['parent protocol initial turn binds to verified closure after administrative LAN checkpoint selection; original captured turns unchanged']
            old='class NativeSavedSession:'
            if text.count(old)!=1:raise ValueError('Saved session class changed')
            text=text.replace(old,old+'\n    event_line_limit_bytes = MAX_LINE')
            old='def _read_stream(self, pipe, name, limit, events):'
            if text.count(old)!=1:raise ValueError('Saved stream reader changed')
            text=text.replace(old,old+'\n        line_limit = self.event_line_limit_bytes if events else MAX_LINE')
            if text.count('pipe.readline(MAX_LINE + 1)')!=1 or text.count('len(line) > MAX_LINE')!=1:
                raise ValueError('Saved stream capacity checks changed')
            text=text.replace('pipe.readline(MAX_LINE + 1)','pipe.readline(line_limit + 1)')
            text=text.replace('len(line) > MAX_LINE','len(line) > line_limit')
            transformations+=['event-line bound is a profile hook; legacy and stderr remain 1 MiB, LAN explicitly admits 16 MiB full-coordinate replies; aggregate/process bounds unchanged']
            old="if event.get('stage') in ('official_session_response', 'official_session_refused'):"
            if text.count(old)!=1:raise ValueError('Native response queue hook changed')
            text=text.replace(old,"information_store = getattr(self, '_information_store', None)\n                        if information_store is not None:\n                            information_store.ingest(event)\n                        "+old)
            transformations+=['opt-in bounded administrative information store consumes existing events before response delivery; default path and native calls unchanged']
            old="if self.input_profile not in ('single', 'hotseat-four'):"
            if old not in text:raise ValueError('Saved profile guard changed')
            text=text.replace(old,"if self.input_profile not in ('single', 'hotseat-four', 'lan'):")
            old="selected = SINGLE_PROFILE if self.input_profile == 'single' else HOTSEAT_FOUR_PROFILE"
            if old not in text:raise ValueError('Saved profile selector changed')
            text=text.replace(old,"from civ6_host.runtime.capture_profiles import LAN_PROFILE\n        selected = {'single': SINGLE_PROFILE, 'hotseat-four': HOTSEAT_FOUR_PROFILE, 'lan': LAN_PROFILE}[self.input_profile]\n        if self.input_profile == 'lan' and self.official_bundle is None:\n            raise ValueError('LAN session requires its exact official bundle')")
            old="worker = ROOT / 'tools' / self.worker_name"
            if old not in text:raise ValueError('Worker launcher boundary changed')
            text=text.replace(old,'worker = _worker_path(self.worker_name)')
            old='self.pins = {str(p.relative_to(ROOT)): sha(p) for p in files if p.is_file()}'
            if old not in text:raise ValueError('Native pin builder changed')
            text=text.replace(old,'self.pins = {_pin_key(p): sha(p) for p in files if p.is_file()}\n        self.pins.update(_installed_source_pins())')
            old='if captured is not None:\n            envelope, handoff_key = create_parent_localization_handoff(closure)'
            if old not in text:raise ValueError('Localization handoff boundary changed')
            text=text.replace(old,'from civ6_host.runtime.capture_admission import configure_prepared_closure\n        compact = configure_prepared_closure(closure, captured)\n        if captured is not None and not compact:\n            envelope, handoff_key = create_parent_localization_handoff(closure)')
            old='self._configure_closure(closure)'
            if text.count(old)!=1:raise ValueError('Private resource closure boundary changed')
            text=text.replace(old,'from civ6_host.runtime.resource_resolution import configure_closure as configure_resources\n        configure_resources(closure)\n        self._configure_closure(closure)')
            transformations+=['launch installed worker, not historical script','pin actual installed sources in the native closure']
            transformations+=['explicit prepared-capture identity replaces only legacy localization handoff when configured']
            transformations+=['LAN subclass reuses the bounded supervisor with explicit capture-only profile; no fallback fixture or hotseat scheduler']
        if name.startswith('tools.official_'):
            bootstrap="from pathlib import Path as _BootstrapPath\nimport sys as _bootstrap_sys\n_bootstrap_sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[3]))\nfrom civ6_host.runtime.import_boundary import enable as _host_only_imports\n_host_only_imports()\n"
            text=bootstrap+text
            transformations+=['bootstrap installed package root for embedded Python']
            if name in ('tools.official_hotseat_worker923','tools.official_action_worker920'):
                transformations+=['private stderr retains refusal traceback; public refusal schema unchanged']
        if name in ('civ6rl.native_probe','tools.run_official_postload909'):
            transformations+=['retain runtime helpers; omit historical probe CLI/automatic experiment runners']
        if name=='civ6rl.learning.skill_task991':transformations+=['retain only public observation/witness joins; no rewards/tasks/evaluation']
        if name=='civ6rl.learning.diagnostic_budget998':transformations+=['legacy wire budget compatibility only; no optimizer or curriculum execution']
        if name=='civ6rl.native_map_script':transformations+=['embedded neural diagnostic selector explicitly refused; client chooses actions', 'exact synchronous GameEvents callbacks shared by inheritance with constructor-free services; original Base prefix inherits unchanged method bodies']
        if name=='civ6rl.native_script_runtime':
            transformations+=['native game API registration preserves Base default and selects the retained source-checked XP1 binder explicitly; unknown engines or absent XP1 executable export fail before dispatch; no saved Load admission']
        if name in ('civ6rl.native_aux_map_conversion','civ6rl.native_aux_map_adapter'):
            transformations+=['one map decoder selects explicit Base/XP1 provider ABI; legacy Base/V1 remains default; V2 UTF16/null transport requires native version negotiation, source-bound conversion and existing memory/stability limits; no saved Load admission', 'explicit XP2 source profile reuses the same decoder and owned-copy paths, including source-verified lists/maps; adapter nested-map option defaults off and requires V2 before registration; no XP2 native qualification']
        if name=='civ6rl.native_city_range_attack':transformations+=['observation collector imports installed module; historical file loader removed']
        if name=='civ6rl.native_checkpoint_resume':transformations+=['literal dynamic transport imports mapped to installed module']
        if name=='civ6rl.native_official_bundle':transformations+=['optional prepared-capture input uses the same PreparedBundle/Load path; original capture validation remains the exporter and fallback']
        if name in ('civ6rl.native_official_bundle','civ6rl.native_official_load'):
            transformations+=['LAN capture-only profile uses exact official bundle validation; no fixture fallback or native session admission']
        if name=='civ6rl.native_official_load':
            transformations+=['LAN load roster and native human flags compared to the exact one-human capture; no command/turn/network admission']
        if name=='tools.run_official_postload909':
            transformations+=['explicit LAN profile in shared official Load/postload worker; no hotseat substitution']
        if name in ('civ6rl.native_session_checkpoint','civ6rl.native_session_resume','civ6rl.native_official_bundle','tools.run_official_postload909'):
            transformations+=['LAN administrative checkpoint reuses generic native Save/Load with separate capture-bound ancestry and network boundary validation; Single checkpoint scope unchanged']
        if name=='civ6rl.native_checkpoint_retained_save':
            transformations+=['Save writer call-limit hook preserves legacy default; LAN scales to max(1000000,2*input bytes) after measured million-call refusal at 4228154 bytes; 32 MiB/time/process bounds unchanged']
            transformations+=['All three Save boundary snapshots share an explicit optional lazy-private-ring admission; default remains strict for historical checkpoints']
        if name=='civ6rl.native_checkpoint_diagnostic':
            transformations+=['LAN may record a never-created private event ring as null without allocation, draining or zero substitution; all ring producers allocate before enqueue and no caller resets it; initialized pending/poisoned rings still refuse, legacy default unchanged']
        if name in ('civ6rl.native_official_postload','civ6rl.native_checkpoint_postload160'):
            transformations+=['LAN uses exact captured/loaded major roster in postload; validates unique bounded native IDs; player0 read-only observation admitted without city action or turn']
        if name=='civ6rl.native_checkpoint_load':
            transformations+=['LAN stream-call bound scales to max(2000000,2*saved bytes) after an observed 2000000-call bounded refusal; 32MiB stream bound and supervisor time/memory limits retained']
        if name in ('civ6rl.native_checkpoint_load', 'civ6rl.native_host'):
            transformations+=['saved-Load ABI selection centralizes retained Base virtual targets and Prepare/copy/Load/getter addresses; Base signatures and checks unchanged; source-qualified XP metadata explicitly refused before native setup']
        if name == 'civ6rl.native_checkpoint_load':
            transformations+=['B-to-A copy retains one native algorithm; XP1 checks source/live copy and reindex bodies and forwards its engine identity into indexed/provider snapshots; production saved Load admission unchanged']
        if name in ('civ6rl.native_application_configuration', 'civ6rl.native_configuration_finalization', 'civ6rl.native_checkpoint_provider'):
            transformations+=['configuration ownership, indexed snapshots and bounded codec share explicit engine ABI; retained Base defaults and algorithms preserved; XP1 joins complete source bodies and ownership layout; XP2 incomplete ownership refused; saved-game admission unchanged']
        if name in APPLICATION_MIRROR_MODULES:
            transformations+=['application mirror/property copy/prelude share explicit engine profiles and existing indexed configuration snapshots; Base default algorithms retained; XP1 source/live guards and isolated qualification required; saved-game admission unchanged']
        if name in DEFERRED_QUEUE_MODULES:
            transformations+=['shared FIFO/counter/CacheUpdate producer and commit-on-native-return consumer extracted from existing class; Base inherits same methods; separate XP1 outer-dispatch source/live profile; no empty Core subscriber substitution']
        if name in ('civ6rl.native_host', 'civ6rl.native_checkpoint_configuration_only'):
            transformations+=['shared configuration lifecycle selects source-bound Base Init or retained XP1 context Init/teardown; shared dependency path, native owner, stream and shutdown reused; XP1 has no Base event recorder or pre-Init aligned-free; saved Load admission unchanged']
        if name in ('civ6rl.native_xp1_context_init', 'civ6rl.native_xp1_teardown_adapter'):
            transformations+=['explicit host source-parent migration daac085ea97d94d2d9ceded07ef90bcc9d7a1f2ab6aa301f3efa155b8cea8db5 to ebd7d0f3e0026e35ef04b89d92698764466887578cc1819351a794dce4b8e3d6; retained Init/provider/Destroy diagnostic qualified this source pair; originals unchanged']
        if name in XP1_PREPARE_MODULES:
            transformations+=['explicit XP1 Prepare source migration to current host; archive historical proof still validates its original parent; default absent-Tuner refusal retained; opt-in Prepare-only NULL diagnostic requires separate acquisition/cleanup source proof']
        if name == 'civ6rl.native_xp1_archive_registration':
            transformations.append('private native helper body checked by canonical hex length and pinned SHA-256 without embedding the body')
        if name == 'civ6rl.native_host':
            transformations+=['explicit context-only XP1 Prepare composes retained registry/archive/localization helpers; saved Load guard and Base path unchanged']
        if name=='civ6rl.native_app_ownership':
            transformations+=['Base LAN absent-numeric capability projection uses capture-bound read-only branch; existing catalogue/content refusals retained; no entitlement or network semantics claimed']
        text=ast.unparse(ast.fix_missing_locations(ResourcePaths().visit(ast.parse(text))))+'\n'
        text=parameterize_postload160(name,text)
        text=parameterize_postload_aux90(name,text)
        text=parameterize_loaded_cache(name,text)
        text=parameterize_official_loaded_cache(name,text)
        text=parameterize_job_registry(name,text)
        if name in ('civ6rl.native_checkpoint_jobs','civ6rl.native_checkpoint_postload_jobs'):
            transformations.append('shared strict all64 registry walker and structural transition; legacy Base identity/schema preserved; explicit XP1 source-bound observer has distinct honest identity')
        if name in ('civ6rl.native_ui_cache_facades','civ6rl.native_ui_cache_backend',
                    'civ6rl.native_player_view','civ6rl.native_checkpoint_postload_facades',
                    'civ6rl.native_official_postload'):
            transformations.append('shared source-bound loaded-cache publication; explicit XP1 candidate requires actual saved-Load owner and real native copy; public cache/+160 gates remain closed')
        if name == 'civ6rl.native_official_bundle':
            text=qualify_xp1_bundle_inputs(text)
            transformations.append('raw XP1 LAN inputs require exact engine/EXE/ruleset and empty source-pinned selected/active lists; Base consumer proof remains false; no native Load or prepared-cache admission')
        text=parameterize_xp1_saved_load(name,text)
        text=parameterize_xp1_saved_handoff(name,text)
        text=parameterize_xp1_saved_worker(name,text)
        text=parameterize_xp1_saved_init(name,text)
        text=parameterize_xp1_load_capability(name,text)
        text=parameterize_xp1_capability_cache(name,text)
        text=parameterize_xp1_load_options(name,text)
        text=parameterize_xp1_postload_candidate(name,text)
        text=parameterize_xp1_cache_publication(name,text)
        text=parameterize_xp1_loaded_lifetime(name,text)
        text=parameterize_xp1_publication_events(name,text)
        text=parameterize_xp1_ui_binding(name,text)
        text=parameterize_action_transport(name,text)
        text=parameterize_xp1_turns(name,text)
        text=parameterize_xp1_turn_units(name,text)
        text=parameterize_xp1_world_input(name,text)
        text=parameterize_xp1_unit_orders(name,text)
        from extraction_xp1_checkpoint import parameterize as xp1_checkpoint
        from extraction_xp1_session_checkpoint import parameterize as xp1_session_checkpoint
        text=xp1_checkpoint(name,text)
        text=xp1_session_checkpoint(name,text)
        if name in ('civ6rl.native_checkpoint_diagnostic', 'civ6rl.native_checkpoint_retained_save',
                    'civ6rl.native_session_checkpoint', 'civ6rl.native_official_bundle',
                    'tools.run_official_postload909'):
            transformations.append('selected Base/XP1/XP2 Save ABI and exact checkpoint lineage reuse shared session serialization, manifest and captured Load; Base/XP1 defaults retained; selected XP2 provider/source receipts and original capture ownership required')
        if name in XP1_ORDER_MODULES:
            transformations.append('XP1 native parameterless unit orders and ordinary-unit cancellation use shared catalogues and command delivery with selected source profiles; Base defaults preserved')
        if name in XP1_WORLD_MODULES:
            transformations.append('explicit XP1 world-input and queued-destination source selection; shared official Lua route, catalogue and apply preserved; unsupported operation branches refused before transmission; Base default unchanged')
            transformations.append('current XP2 attack no-effect disposition requires the live image and a complete native MOVE_TO lifecycle')
        from extraction_foundation_facades import transform as foundation_facades
        from extraction_foundation_queries import transform as foundation_queries
        from extraction_foundation_visibility import transform as foundation_visibility
        from extraction_foundation_dispatch import transform as foundation_dispatch
        for transform in (foundation_facades, foundation_queries, foundation_visibility, foundation_dispatch):
            text=transform(name,text)
        from extraction_civilization_getter import transform as civilization_getter
        text=civilization_getter(name,text)
        from extraction_city_scalar_events import transform as city_scalar_events
        text=city_scalar_events(name,text)
        if name=='civ6rl.native_found_city_event':
            # extraction_action_transport parameterizes this module earlier in
            # the same pass. Verify that stage ran; applying the hook here a
            # second time would duplicate the selected engine argument.
            found_unit_tree=ast.parse(text)
            found_unit_functions={node.name:node for node in found_unit_tree.body
                                  if isinstance(node,ast.FunctionDef)}
            for function_name in ('query_unit_parameters','unit_query_contract'):
                function=found_unit_functions.get(function_name)
                if (function is None or not any(argument.arg=='core_sha256'
                        for argument in (*function.args.args,*function.args.kwonlyargs))):
                    raise ValueError('Found-unit source-selection hook did not run before facade hooks')
            transformations.append('shared E23B unit query selects Base by default and XP1/XP2 only by explicit Core SHA; exact engine facade/query-map profile required; common EXE evidence remains separately pinned')
        from extraction_session_launch import parameterize as session_launch
        text=session_launch(name,text)
        from extraction_stdout_transport import parameterize as stdout_transport
        text=stdout_transport(name,text)
        from extraction_expansion_city_controls import parameterize as expansion_city_controls, MODULES as CITY_CONTROL_MODULES
        text=expansion_city_controls(name,text)
        if name in CITY_CONTROL_MODULES:
            transformations.append('explicit source-selected expansion focus/MANAGE callbacks and owned FIFO; original Lua/parsers/transitions retained and Base remains default')
        from extraction_xp1_session_readers import parameterize as xp1_session_readers, MODULES as XP1_SESSION_READERS
        text=xp1_session_readers(name,text)
        from extraction_xp1_result_readers import parameterize as xp1_result_readers
        text=xp1_result_readers(name,text)
        from extraction_xp1_research import parameterize as xp1_research
        from extraction_xp1_production import parameterize as xp1_production
        text=xp1_research(name,text)
        text=xp1_production(name,text)
        from extraction_xp1_placements import parameterize as xp1_placements
        from extraction_contract_placement import parameterize as placement_contract
        text=xp1_placements(name,text)
        text=placement_contract(name,text)
        from extraction_xp1_unit_attacks import parameterize as xp1_unit_attacks
        text=xp1_unit_attacks(name,text)
        from extraction_xp1_placement_events import parameterize as xp1_placement_events
        text=xp1_placement_events(name,text)
        from extraction_xp1_improvement_visibility import parameterize as xp1_improvement_visibility
        text=xp1_improvement_visibility(name,text)
        from extraction_xp1_game_history import parameterize as xp1_game_history
        text=xp1_game_history(name,text)
        from extraction_xp1_goody_hut import parameterize as xp1_goody_hut
        text=xp1_goody_hut(name,text)
        from extraction_xp1_absent_events import parameterize as xp1_absent_events
        text=xp1_absent_events(name,text)
        from extraction_xp1_combat_map import parameterize as xp1_combat_map
        from extraction_xp1_combat import parameterize as xp1_combat
        text=xp1_combat_map(name,text)
        text=xp1_combat(name,text)
        from extraction_xp1_improvement_changes import parameterize as xp1_improvement_changes
        text=xp1_improvement_changes(name,text)
        from extraction_xp1_district_damage import parameterize as xp1_district_damage
        text=xp1_district_damage(name,text)
        if name in ('civ6rl.native_event_30ae2a3d','civ6rl.native_event_7b65ff2e','civ6rl.native_host_events'):
            transformations.append('explicit XP1 selection for improvement/route notifications reusing retained A625 and 5D plot/configuration query bodies; Base default preserved')
        if name in ('civ6rl.native_combat_map_owner','civ6rl.native_combat_argument_snapshot',
                    'civ6rl.native_event_8256dbe1','civ6rl.native_combat_owner_predicate',
                    'civ6rl.native_unit_promotion_query','civ6rl.native_host_events'):
            transformations.append('explicit engine selection for retained combat map ownership, borrowed arguments, predicate and experience queries; shared Base algorithms and default preserved')
        if name == 'civ6rl.native_absent_d70ba51f':
            transformations.append('shared two-field unit normalization body retained behind source-qualified absent-registry family; historical D70-only public guard remains closed')
        if name == 'civ6rl.native_host_events':
            transformations.append('explicit engine identity selects the XP1 GoodyHutReward source while reusing the existing Base/default producer, descriptor copy and native deferred record codec')
        if name in ('civ6rl.native_event_6d7163b0','civ6rl.native_event_6d7163b0_selector',
                    'civ6rl.native_event_f391d7b3','civ6rl.native_event_b3495127'):
            transformations.append('explicit XP1 ABI selection for shared district progress, improvement visibility and faith event queries; Base algorithm, owner leases and record encoding retained')
        if name in ('civ6rl.native_production_placement','civ6rl.native_saved_placement',
                    'civ6rl.native_district_completion','civ6rl.native_wonder_completion'):
            transformations.append('engine-selected existing placement/resume/completion Lua; shared portable validation; Base default preserved')
        from extraction_xp1_production_queue import parameterize as xp1_production_queue
        from extraction_contract_production_queue import parameterize as production_queue_contract
        text=xp1_production_queue(name,text)
        text=production_queue_contract(name,text)
        if name == 'civ6rl.native_saved_production_queue':
            transformations.append('engine-selected queue catalogue/request with exact XP1 source and UI gate; portable queue validation shared with client; Base default and native algorithm retained')
        if name in ('civ6rl.native_research_actions','civ6rl.native_research_catalog',
                    'civ6rl.native_player_operation_request','civ6rl.native_map_script'):
            transformations.append('explicit XP1 research/civic source and player-operation ABI selection; shared catalogue, serializer, request and effect retained; Base default unchanged')
        if name in ('civ6rl.native_production_catalog','civ6rl.native_city_production_observation',
                    'civ6rl.native_saved_actions'):
            transformations.append('explicit XP1 production source selection; shared ordinary replacement helper also used by Base; placements and queue edits remain separate capabilities')
        if name in XP1_SESSION_READERS:
            transformations.append('explicit source-selected XP1 founder catalogue; original complete legality Lua and parser retained, Base default unchanged')
        if name in ('civ6rl.native_winning_team','civ6rl.native_episode_facts','civ6rl.native_victory_episode'):
            transformations.append('explicit XP1 status-source selection for existing winning-team/facts readers and episode policy; observation-only provenance does not qualify winner transition')
        if name == 'civ6rl.native_saved_session':
            transformations.append('bounded process launch extracted unchanged into shared session_launch; engine-specific preparation remains separate, readers/watch/reaping and validation retained')

        if name in XP1_CAPABILITY_CACHE_MODULES:
            transformations.append('owner-scoped immutable capability metadata verified at install/Load/cache boundaries; live mode, PLAYER keys, providers and vtables checked per query; source changes invalidate and default Base paths retain original verification')
        if name in XP1_LOAD_CAPABILITY_MODULES:
            transformations.append('explicit XP1 captured capability source binds the existing shared EXE ownership service to exact 92-row catalogue, actual owned providers and LAN POD-copy convergence; Base/default guards and producer inventory unchanged')
        if name in XP1_SAVED_INIT_MODULES:
            transformations.append('explicit owned XP1 saved capture selects final private database inputs through shared Init and retained teardown receipt; historical diagnostic pins and source proofs unchanged')
        if name in ('civ6rl.native_checkpoint_load','civ6rl.native_official_load',
                    'civ6rl.native_official_bundle','tools.run_official_postload909'):
            transformations.append('explicit exact XP1 saved-Load candidate uses registered prepared input handoff and actual shared service composition; existing worker returns real Load receipt before unqualified post160; public profiles unchanged')
        from extraction_database_bulk import parameterize as parameterize_database_bulk
        text=parameterize_database_bulk(name,text)
        if name == 'civ6rl.database_capture_bundle993':
            transformations.append('explicit bulk-file evidence reuses table pass, typed comparison and protected private-template materialization; legacy page producer and receipts preserved')
        from extraction_localization_stream import parameterize as parameterize_localization_stream
        text=parameterize_localization_stream(name,text)
        if name in ('civ6rl.native_localization_query','civ6rl.file_client','civ6rl.response_file_client'):
            transformations.append('opt-in exact-build row-file callback and stationary client channel; existing query, one-writer and timeout behavior retained')
        from extraction_localization_bulk_export import parameterize as parameterize_localization_bulk_export, MODULES as LOCALIZATION_BULK_MODULES
        text=parameterize_localization_bulk_export(name,text)
        if name in LOCALIZATION_BULK_MODULES:
            transformations.append('explicit source-pinned bulk Localization branch uses existing export/capture994/official-bundle validation, runtime/save association and dependency closure; ordinary producer remains default')
        from extraction_xp2_bundle_inputs import parameterize as parameterize_xp2_bundle_inputs
        text=parameterize_xp2_bundle_inputs(name,text)
        if name == 'civ6rl.native_official_bundle':
            transformations.append('exact private XP2 raw input family reuses complete database/save validation, joins nonempty WorldCongress disk sources and active-list witnesses, without native Load or public admission')
        if name in ('civ6rl.native_official_bundle','civ6rl.native_localization_logical_export'):
            transformations.append('explicit immutable producer-source snapshot consumption preserves historical profile identities after restoring the installed capture mod; live source checks remain strict')
        from extraction_expansion_initialization import parameterize as parameterize_expansion_initialization
        text=parameterize_expansion_initialization(name,text)
        if name in ('civ6rl.native_xp1_context_init','civ6rl.native_host','civ6rl.native_checkpoint_configuration_only'):
            transformations.append('shared expansion Init mechanics retain source-qualified XP1 profile and explicit captured input selection; no XP2 native admission from this extraction')
        from extraction_script_wire_paths import parameterize as parameterize_script_wire_paths
        text=parameterize_script_wire_paths(name,text)
        if name == 'civ6rl.native_gameplay_script_registry':
            transformations.append('explicit ordered native wire names are separate from approved physical source files; count/index buffers retain exact UTF-16 text and legacy selection defaults')
        from extraction_xp2_natural_wonder import parameterize as parameterize_natural_wonder
        text=parameterize_natural_wonder(name,text)
        if name in ('civ6rl.native_36c9b2b4','civ6rl.native_wonder_application'):
            transformations.append('actual XP2 natural-wonder source selects input-map, Game comparison and retained position ABI; shared Base/default producer, controller effects and paired FIFO codec preserved')
        if name == 'civ6rl.native_checkpoint_stream':
            anchor = "        if storage.raw[:16] != GUARD or storage.raw[-16:] != GUARD:\n            raise RuntimeError('Read staging canary changed')\n        return bytes(storage.raw[16:-16])"
            if text.count(anchor) != 1:
                raise ValueError('Checkpoint local read staging boundary changed')
            text = text.replace(anchor,
                "        snapshot = storage.raw\n"
                "        if snapshot[:16] != GUARD or snapshot[-16:] != GUARD:\n"
                "            raise RuntimeError('Read staging canary changed')\n"
                "        return snapshot[16:-16]")
            transformations.append('one immutable read staging snapshot serves both canary checks and returned bytes; OS checks and bounds preserved')
        if name == 'civ6rl.native_official_load':
            anchor = "        raw = self.prefix.runtime.evaluate_text(self.prefix.game_child, source, b'@official_loaded_diagnostic', capacity=4096)"
            if text.count(anchor) != 1:
                raise ValueError('Saved own-unit readback boundary changed')
            checkpoint_projection = '''        if self.inputs.checkpoint is not None:
            from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
            if self.load_abi.core_sha256 == XP2_CORE_SHA256:
                original = b'for _,u in p:GetUnits():Members() do units[#units+1]=u end'
                if source.count(original) != 1:
                    raise ValueError('Saved own-unit enumeration changed')
                source = source.replace(original,
                    b'for _,u in p:GetUnits():Members() do\\n'
                    b' assert(type(u.IsDelayedDeath)=="function","unit lifecycle getter unavailable")\\n'
                    b' if not (u:IsDelayedDeath() == true and u:GetX() == -9999 and u:GetY() == -9999) then\\n'
                    b'  units[#units+1]=u\\n'
                    b' end\\n'
                    b'end')
'''
            text = text.replace(anchor, checkpoint_projection + anchor)
            transformations.append('XP2 checkpoint raw own-unit comparison excludes only native delayed-death units with both off-map sentinels; all remaining fields still compare exactly')
        if name == 'civ6rl.native_policy_catalog':
            slots = text.index('def validate_slots(')
            parser = text.index('def parse_catalog(')
            chooser = text.index('def choose(')
            text = (text[:slots].replace('import re\n',
                'from civ6_host.contracts.policies import choose, validate_slots\n')
                + text[parser:chooser]).rstrip() + '\n'
            transformations.append('policy assignment validation shared with the portable client')
        from extraction_player_operations import (
            parameterize as player_operations, MODULE as PLAYER_OPERATION_MODULE,
            LABEL as PLAYER_OPERATION_LABEL, DEDICATION_LABEL as PLAYER_OPERATION_DEDICATION_LABEL)
        text=player_operations(name,text)
        if name == PLAYER_OPERATION_MODULE:
            transformations.extend((PLAYER_OPERATION_LABEL, PLAYER_OPERATION_DEDICATION_LABEL))
        mapped=remap(name)
        dest=repo/'src'/Path(*mapped.split('.')).with_suffix('.py')
        if name in maintained_overlays:
            label, baseline = maintained_overlays[name]
            for prior in prior_map.get('sources', ()):
                if prior['module'] == mapped and label in prior['transformations']:
                    if (prior['source_sha256'] != digest(paths[name].read_bytes())
                            or digest(text.encode('utf-8')) != baseline
                            or digest(dest.read_bytes()) != prior['destination_sha256']):
                        raise ValueError('Rebase the maintained host overlay before extraction: '+mapped)
                    text=dest.read_text(encoding='utf-8')
                    transformations.append(label)
                    break
        dest.parent.mkdir(parents=True,exist_ok=True)
        ast.parse(text)
        dest.write_text(text,encoding='utf-8',newline='\n')
        rows.append(dict(source=paths[name].relative_to(source).as_posix(),source_sha256=digest(paths[name].read_bytes()),
            module=mapped,destination=dest.relative_to(repo).as_posix(),destination_sha256=digest(dest.read_bytes()),transformations=transformations))
    # Portable v12 validators reuse the exact Base pure functions; no runtime
    # package import is permitted in a standalone model-independent client.
    from extraction_expansion_city_controls import portable_contract
    pure=portable_contract(paths['civ6rl.native_saved_city_focus1000'].read_text(encoding='utf-8'),
                           paths['civ6rl.native_saved_citizens'].read_text(encoding='utf-8'))
    dest=repo/'src/civ6_host/contracts/city_controls_base.py'
    ast.parse(pure);dest.write_text(pure,encoding='utf-8',newline='\n')
    rows.append(dict(source=paths['civ6rl.native_saved_city_focus1000'].relative_to(source).as_posix(),
        source_sha256=digest(paths['civ6rl.native_saved_city_focus1000'].read_bytes()),
        module='civ6_host.contracts.city_controls_base',destination=dest.relative_to(repo).as_posix(),
        destination_sha256=digest(dest.read_bytes()),transformations=[
            'AST-select unchanged pure Base focus and citizens validators/constants with separate local name prefixes',
            'citizens source is independently verified by the existing native_saved_citizens source-map row; no runtime import or source I/O in client']))
    for sub in ('native','workers'):
        (target/sub/'__init__.py').write_text('"""Extracted native host implementation; configure private resources before import."""\n',encoding='utf-8')
    manifest=dict(schema='civ6-host.runtime-extraction.v1',scope='Extracted host code; legacy private resource/proof layout still required',
        sources=rows,seeds=list(SEEDS),source_dependency_graph={name:edges[name] for name in sorted(edges)},
        original_code_executed=False,simultaneous_qualified=False,standalone_resource_bundle_ready=False)
    (target/'source-map.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'modules':len(rows),'source_bytes':sum(paths[n].stat().st_size for n in trees),
                      'learner_imports_remaining':False,'manifest':str(target/'source-map.json')}))


if __name__=='__main__':main()

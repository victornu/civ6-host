"""Reuse the retained Init algorithms with explicit expansion contracts."""
import ast


def parameterize(name, raw):
    if name == 'civ6rl.native_checkpoint_configuration_only':
        before="(('base', 'init'), ('xp1', 'context'))"
        if raw.count(before)!=1:raise ValueError('Shared backend context guard changed')
        raw=raw.replace(before,"(('base', 'init'), ('xp1', 'context'), ('xp2', 'context'))")
        raw=raw.replace("if self.profile.ruleset == 'xp1':", "if self.profile.ruleset in ('xp1', 'xp2'):")
        return raw
    if name == 'civ6rl.native_host':
        before="(('base', 'init'), ('xp1', 'context'))"
        if raw.count(before)!=1:raise ValueError('Shared host context guard changed')
        raw=raw.replace(before,"(('base', 'init'), ('xp1', 'context'), ('xp2', 'context'))")
        before="expansion = context_profile.ruleset == 'xp1'"
        if raw.count(before)!=1:raise ValueError('Shared host expansion branch changed')
        raw=raw.replace(before,"expansion = context_profile.ruleset in ('xp1', 'xp2')")
        before='        actual_profile = profile_for_core('
        after="""        if context_profile.ruleset == 'xp2':
            from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
            if context_profile.core_sha256 != XP2_CORE_SHA256:
                raise ValueError('XP2 context profile engine identity differs')
        actual_profile = profile_for_core("""
        if raw.count(before)!=1:raise ValueError('Expansion profile identity boundary changed')
        raw=raw.replace(before,after)
        before='        from civ6_host.runtime.xp1_saved_load import bind_candidate\n'
        after="""        if context_profile.ruleset == 'xp2':
            from civ6_host.runtime.xp2_saved_init import bind_candidate
        else:
            from civ6_host.runtime.xp1_saved_load import bind_candidate
"""
        if raw.count(before)!=1:raise ValueError('Captured Init input binding changed')
        raw=raw.replace(before,after)
        before='    manifest = validate_fixture(manifest_path)\n'
        after="""    if expansion and context_profile.ruleset == 'xp2' and candidate_bundle is None:
        raise ValueError('XP2 Init requires an explicit captured input owner')
    manifest = validate_fixture(manifest_path)
"""
        if raw.count(before)!=1:raise ValueError('Shared host fixture boundary changed')
        raw=raw.replace(before,after)
        before='    if expansion:\n        from civ6_host.runtime.native.native_xp1_context_init import initialize_xp1_context'
        after="""    if expansion and context_profile.ruleset == 'xp2':
        from civ6_host.runtime.xp2_context_lifecycle import initialize_xp2_context, install_xp2_teardown_callbacks
        from civ6_host.runtime.native.native_probe import Windows
        paths = Windows().modules()
        host.context_init_receipt = initialize_xp2_context(core, context, host,
            configuration_path=_resolve_resource_path(Path(manifest['databases']['configuration']['path'])),
            gameplay_path=_resolve_resource_path(Path(manifest['databases']['gameplay']['path'])),
            private_root=_resolve_resource_path(Path(manifest_path)).resolve().parent,
            module_paths=paths, emit=emit, candidate_bundle=candidate_bundle)
        emit('xp2_adapter_receipt', receipt=host.context_init_receipt)
        host.context_teardown_receipt = install_xp2_teardown_callbacks(core, context, host,
            host.context_init_receipt, module_paths=paths, emit=emit, candidate_bundle=candidate_bundle)
        if host.context_teardown_receipt.get('installed') is not True:
            raise RuntimeError('XP2 teardown binding did not complete')
        return host
    if expansion:
        from civ6_host.runtime.native.native_xp1_context_init import initialize_xp1_context"""
        if raw.count(before)!=1:raise ValueError('Shared host Init dispatch changed')
        return raw.replace(before,after)
    if name != 'civ6rl.native_xp1_context_init':
        return raw
    tree = ast.parse(raw)
    wrappers = {
        '_rebind_unapproved_host_callbacks': """def _rebind_unapproved_host_callbacks(host):
    from civ6_host.runtime.context_initialization import restrict_callbacks
    return restrict_callbacks(host, host_slots=XP1_HOST_VTABLE_ALLOWLIST,
        auxiliary_slots=XP1_AUX_VTABLE_ALLOWLIST, logger_slots=XP1_LOGGER_VTABLE_ALLOWLIST)
""",
        '_require_empty_xp1_host_globals': """def _require_empty_xp1_host_globals(core, read):
    from civ6_host.runtime.context_initialization import require_empty_globals
    return require_empty_globals(core, read, XP1_HOST_GLOBALS)
""",
        '_require_installed_xp1_host_globals': """def _require_installed_xp1_host_globals(core, host, read):
    from civ6_host.runtime.context_initialization import require_installed_globals
    return require_installed_globals(core, host, read, XP1_HOST_GLOBALS)
""",
        '_require_exact_xp1_declarations': """def _require_exact_xp1_declarations(host):
    from civ6_host.runtime.context_initialization import require_declarations
    return require_declarations(host, XP1_EVENT_DECLARATIONS)
""",
    }
    found = set()
    for index, fn in enumerate(tree.body):
        if not isinstance(fn, ast.FunctionDef):
            continue
        if fn.name in wrappers:
            found.add(fn.name)
            tree.body[index] = ast.parse(wrappers[fn.name]).body[0]
        if fn.name == 'initialize_xp1_context':
            positions = [i for i, node in enumerate(fn.body)
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == 'context_validator']
            if len(positions) != 1:
                raise ValueError('Expansion Init extraction boundary changed')
            fn.body[positions[0]:] = ast.parse("""
from civ6_host.runtime.context_initialization import initialize
boundary = _load_json_pinned(root, *PROOF_PINS['init_boundary'])
return initialize(core, context, host, profile=profile, source=source,
    input_receipt=input_receipt, callback_receipt=callback_receipt,
    slots=XP1_SLOTS, globals_rvas=XP1_HOST_GLOBALS, declarations=XP1_EVENT_DECLARATIONS,
    vtable_bytes=bytes.fromhex(boundary['rulesets']['xp1']['context_vtable_capture']['raw_hex']),
    context_validator=context_validator, virtual_factory=virtual_factory,
    read=read, emit=emit, error_type=XP1ContextInitError)
""").body
        if fn.name == 'validate_private_inputs':
            fn.args.kwonlyargs.append(ast.arg(arg='candidate_family'))
            fn.args.kw_defaults.append(ast.Constant('xp1-lan'))
            fn.body[1:1] = ast.parse("""
if candidate_family not in ('xp1-lan', 'xp2-lan') or (candidate_family == 'xp2-lan' and candidate_bundle is None):
    raise ValueError('Captured Init requires an exact expansion input family and owner')
""").body
            # Keep the historical private-file/ABI checks. Only the explicit
            # captured metadata selection differs; no offsets change here.
            for node in ast.walk(fn):
                if isinstance(node, ast.ImportFrom) and node.module == 'civ6_host.runtime.xp1_saved_init':
                    node.module = 'civ6_host.runtime.captured_init_inputs'
                    node.names = [ast.alias(name='selected_database_input_binding', asname='database_input_binding')]
            for call in ast.walk(fn):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'database_input_binding':
                    call.keywords.append(ast.keyword(arg='family', value=ast.Name(id='candidate_family', ctx=ast.Load())))
    if found != set(wrappers):
        raise ValueError('Expansion Init shared-helper extraction boundary changed')
    return ast.unparse(ast.fix_missing_locations(tree)) + '\n'

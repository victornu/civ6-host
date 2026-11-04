"""Thread the owned saved capture through the existing XP1 Init adapters."""
import ast

MODULES = ('civ6rl.native_checkpoint_configuration_only', 'civ6rl.native_host',
           'civ6rl.native_xp1_context_init', 'civ6rl.native_xp1_teardown_adapter')


def change(raw, before, after, count=1):
    if raw.count(before) != count:
        raise ValueError('XP1 captured Init extraction boundary changed: ' + before[:120])
    return raw.replace(before, after)


def parameterize(name, raw):
    if name not in MODULES:
        return raw
    if name == MODULES[0]:
        raw = change(raw, '        self.init_entered = True\n        self.host = initialize_context',
            '''        candidate_options = {}
        if getattr(self, '_saved_load_candidate', False):
            if getattr(self, 'captured_bundle', None) is None:
                raise ValueError('XP1 Init candidate lost its captured input owner')
            candidate_options['candidate_bundle'] = self.captured_bundle
        self.init_entered = True
        self.host = initialize_context''')
        raw = change(raw, 'self.emit, context_profile=self.profile)',
            'self.emit, context_profile=self.profile, **candidate_options)')
    elif name == MODULES[1]:
        raw = change(raw, 'def initialize_context(core, context, manifest_path, dll_directory, emit, *, context_profile=None):',
            'def initialize_context(core, context, manifest_path, dll_directory, emit, *, context_profile=None, candidate_bundle=None):')
        raw = change(raw, '    manifest = validate_fixture(manifest_path)\n    db_path = ',
            '''    if candidate_bundle is not None:
        if not expansion:
            raise ValueError('Captured Init inputs require the explicit XP1 context candidate')
        from civ6_host.runtime.xp1_saved_load import bind_candidate
        bind_candidate(candidate_bundle, context_profile, manifest_path)
    manifest = validate_fixture(manifest_path)
    db_path = ''')
        tree = ast.parse(raw)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'initialize_context')
        for callname in ('initialize_xp1_context', 'install_xp1_teardown_callbacks'):
            calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == callname]
            if len(calls) != 1:
                raise ValueError('XP1 Init adapter call changed: ' + callname)
            calls[0].keywords.append(ast.keyword(arg='candidate_bundle', value=ast.Name(id='candidate_bundle', ctx=ast.Load())))
        return ast.unparse(ast.fix_missing_locations(tree)) + '\n'
    elif name == MODULES[2]:
        raw = change(raw, 'path_reader=None, file_hash=_sha256_file) -> dict:',
            'path_reader=None, file_hash=_sha256_file, candidate_bundle=None) -> dict:')
        raw = change(raw, '    if config == gameplay:',
            '''    configuration_sha, configuration_bytes = XP1_CONFIG_SHA256, XP1_CONFIG_BYTES
    gameplay_sha, gameplay_bytes = XP1_GAMEPLAY_SHA256, XP1_GAMEPLAY_BYTES
    captured_binding = None
    if candidate_bundle is not None:
        from civ6_host.runtime.xp1_saved_init import database_input_binding
        captured_binding = database_input_binding(candidate_bundle, host,
            configuration_path, gameplay_path, private_root)
        configuration_pin = captured_binding['databases']['configuration']
        gameplay_pin = captured_binding['databases']['gameplay']
        configuration_sha, configuration_bytes = configuration_pin['sha256'], configuration_pin['size_bytes']
        gameplay_sha, gameplay_bytes = gameplay_pin['sha256'], gameplay_pin['size_bytes']
    if config == gameplay:''')
        raw = change(raw, 'stat().st_size != XP1_CONFIG_BYTES or file_hash(config) != XP1_CONFIG_SHA256',
            'stat().st_size != configuration_bytes or file_hash(config) != configuration_sha')
        raw = change(raw, 'stat().st_size != XP1_GAMEPLAY_BYTES or file_hash(gameplay) != XP1_GAMEPLAY_SHA256',
            'stat().st_size != gameplay_bytes or file_hash(gameplay) != gameplay_sha')
        raw = change(raw, "return {'configuration_path': str(config), 'configuration_sha256': XP1_CONFIG_SHA256, 'gameplay_path': str(gameplay), 'gameplay_sha256': XP1_GAMEPLAY_SHA256,",
            "return {**({'captured_input_binding': captured_binding} if captured_binding is not None else {}), 'configuration_path': str(config), 'configuration_sha256': configuration_sha, 'gameplay_path': str(gameplay), 'gameplay_sha256': gameplay_sha,")
        raw = change(raw, 'source_check=None, input_validator=validate_private_inputs) -> dict:',
            'source_check=None, input_validator=validate_private_inputs, candidate_bundle=None) -> dict:')
        raw = change(raw, '    input_receipt = input_validator(host, configuration_path, gameplay_path, private_root, path_reader=path_reader)',
            '''    if candidate_bundle is None:
        input_receipt = input_validator(host, configuration_path, gameplay_path, private_root, path_reader=path_reader)
    else:
        if input_validator is not validate_private_inputs:
            raise ValueError('Captured XP1 Init requires the existing private input validator')
        input_receipt = validate_private_inputs(host, configuration_path, gameplay_path,
            private_root, path_reader=path_reader, candidate_bundle=candidate_bundle)''')
    else:
        raw = change(raw, 'def _check_init_receipt(receipt, host):',
            'def _check_init_receipt(receipt, host, *, candidate_bundle=None):')
        raw = change(raw, '    inputs = receipt.get(\'inputs\')',
            '''    configuration_sha, gameplay_sha = XP1_CONFIG_SHA256, XP1_GAMEPLAY_SHA256
    if candidate_bundle is not None:
        from civ6_host.runtime.xp1_saved_init import validate_init_receipt_binding
        binding = validate_init_receipt_binding(candidate_bundle, host, receipt)
        configuration_sha = binding['databases']['configuration']['sha256']
        gameplay_sha = binding['databases']['gameplay']['sha256']
    inputs = receipt.get('inputs')''')
        raw = change(raw, "inputs.get('configuration_sha256') != XP1_CONFIG_SHA256", "inputs.get('configuration_sha256') != configuration_sha")
        raw = change(raw, "inputs.get('gameplay_sha256') != XP1_GAMEPLAY_SHA256", "inputs.get('gameplay_sha256') != gameplay_sha")
        raw = change(raw, 'owner_verifier=None, aligned_free_factory=None):',
            'owner_verifier=None, aligned_free_factory=None, candidate_bundle=None):')
        raw = change(raw, '    _check_init_receipt(init_receipt, host)',
            '    _check_init_receipt(init_receipt, host, candidate_bundle=candidate_bundle)')
    return ast.unparse(ast.parse(raw)) + '\n'

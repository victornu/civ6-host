"""Staged post-rewrite hooks for tools/extract_runtime.py; no native execution.

Apply after existing import/resource rewriting and XP1 input extraction. Only
the two existing loader modules change. Generated runtime files are never
edited directly by this helper.
"""
import ast


MODULES = ('civ6rl.native_checkpoint_load', 'civ6rl.native_official_load')


def _replace(node, before, after, *, count=1):
    raw = ast.unparse(node)
    if raw.count(before) != count:
        raise ValueError('XP1 saved-Load extraction boundary changed: ' + before[:110])
    return ast.parse(raw.replace(before, after)).body[0]


def _prepend(node, raw):
    at = int(bool(node.body and isinstance(node.body[0], ast.Expr)
                  and isinstance(node.body[0].value, ast.Constant)
                  and isinstance(node.body[0].value.value, str)))
    node.body[at:at] = ast.parse(raw).body


def parameterize(name, raw):
    if name not in MODULES:
        return raw
    tree = ast.parse(raw)
    if name == MODULES[0]:
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeLoadBackend')
        methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        init = _replace(methods['__init__'],
            'profile, proofs, emit):', 'profile, proofs, emit, *, candidate_bundle=None):')
        init = _replace(init,
            'self.load_abi = require_saved_load_admission(profile_for_sha(profile.core_sha256))',
            '''self._saved_load_candidate = candidate_bundle is not None
    if self._saved_load_candidate:
        from civ6_host.runtime.xp1_saved_load import bind_candidate
        self.load_abi = bind_candidate(candidate_bundle, profile, fixture)
        self.captured_bundle = candidate_bundle
    else:
        self.load_abi = require_saved_load_admission(profile_for_sha(profile.core_sha256))''')
        init = _replace(init, 'check_live_bodies(core._handle, self.runtime.read, proofs)',
            'self.verify_load_bodies()')
        cls.body[cls.body.index(methods['__init__'])] = init
        _prepend(methods['prepare'], '''
if getattr(self, '_saved_load_candidate', False):
    from civ6_host.runtime.xp1_saved_load import prepare_candidate
    return prepare_candidate(self, required_ownership_mode=required_ownership_mode)
''')
        _prepend(methods['control'], '''
if getattr(self, '_saved_load_candidate', False):
    from civ6_host.runtime.xp1_saved_load import control_snapshot
    return control_snapshot(self, empty=empty, allow_diplomacy=allow_diplomacy,
                            pending_round_actor=pending_round_actor)
''')
        reader = _replace(methods['create_reader'],
            "if getattr(inputs, 'profile', None) is LAN_PROFILE:",
            "if getattr(inputs, 'profile', None) is LAN_PROFILE or getattr(self, '_saved_load_candidate', False):")
        _prepend(reader, '''
if getattr(self, '_saved_load_candidate', False):
    from civ6_host.runtime.xp1_saved_load import validate_candidate_inputs
    validate_candidate_inputs(inputs, self.captured_bundle)
    if self.inputs is not inputs:
        raise ValueError('XP1 reader is not bound to the retained captured input pair')
''')
        observer = "self.jobs = make_job_observer(self.runtime.read, expected_executable_path=ROOT / 'work/native-script-services-host41/civ6rl-native-python.exe', owner_thread_id=self.thread[1], profile=PROFILE, exclusive_owner_entry=lambda: self.busy and self.snapshot_phase in ('before', 'after') and (self.runtime.thread() == self.thread))"
        reader = _replace(reader, observer, 'self.jobs = self.make_job_observer()')
        reader = _replace(reader, 'check_live_bodies(self.core._handle, self.runtime.read, self.proofs)',
                          'self.verify_load_bodies()')
        cls.body[cls.body.index(methods['create_reader'])] = reader
        validated = _replace(methods['validate_load_return'],
            'jobs_candidate = validate_quiescent_snapshot_transition(before_jobs, after_jobs)',
            'jobs_candidate = self.validate_job_transition(before_jobs, after_jobs)')
        validated = _replace(validated, 'load_source_sha256=LOAD_SHA256',
            'load_source_sha256=self.load_source_sha256')
        cls.body[cls.body.index(methods['validate_load_return'])] = validated
        cls.body.extend(ast.parse('''
def verify_load_bodies(self):
    if getattr(self, '_saved_load_candidate', False):
        from civ6_host.runtime.xp1_saved_load import verify_live, SOURCES
        result = verify_live(self.core._handle, self.runtime.read, self.proofs)
        self.load_source_sha256 = SOURCES[0][1]
        return result
    self.load_source_sha256 = LOAD_SHA256
    return check_live_bodies(self.core._handle, self.runtime.read, self.proofs)

def make_job_observer(self):
    if getattr(self, '_saved_load_candidate', False):
        from civ6_host.runtime.xp1_saved_load import make_job_observer
        return make_job_observer(self)
    from civ6_host.runtime.native.native_checkpoint_job_observer import make_job_observer
    from civ6_host.runtime.native.native_checkpoint_jobs import PROFILE
    return make_job_observer(self.runtime.read,
        expected_executable_path=ROOT / 'work/native-script-services-host41/civ6rl-native-python.exe',
        owner_thread_id=self.thread[1], profile=PROFILE,
        exclusive_owner_entry=lambda: self.busy and self.snapshot_phase in ('before', 'after')
            and self.runtime.thread() == self.thread)

def validate_job_transition(self, before_jobs, after_jobs):
    if getattr(self, '_saved_load_candidate', False):
        from civ6_host.runtime.saved_load_job_observer import validate_transition
        return validate_transition(self, before_jobs, after_jobs)
    from civ6_host.runtime.native.native_checkpoint_postload_jobs import validate_quiescent_snapshot_transition
    return validate_quiescent_snapshot_transition(before_jobs, after_jobs)
''').body)
    else:
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        validate = _replace(functions['validate_inputs'], 'def validate_inputs(inputs):',
                            'def validate_inputs(inputs, *, candidate_bundle=None):')
        _prepend(validate, '''
if candidate_bundle is not None:
    from civ6_host.runtime.xp1_saved_load import validate_candidate_inputs
    return validate_candidate_inputs(inputs, candidate_bundle)
''')
        tree.body[tree.body.index(functions['validate_inputs'])] = validate
        roster = _replace(functions['roster_readback_source'], 'def roster_readback_source(profile):',
                          'def roster_readback_source(profile, *, candidate_bundle=None):')
        _prepend(roster, '''
if candidate_bundle is not None:
    from civ6_host.runtime.xp1_saved_load import validate_candidate_inputs
    if validate_candidate_inputs(candidate_bundle.inputs, candidate_bundle) is not profile:
        raise ValueError('XP1 roster profile differs from its captured bundle')
    from civ6_host.runtime.lan_load import roster_readback_source as lan_source
    return lan_source()
''')
        tree.body[tree.body.index(functions['roster_readback_source'])] = roster
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'OfficialLoadBackend')
        methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        candidate = "getattr(self, 'captured_bundle', None) if getattr(self, '_saved_load_candidate', False) else None"
        restore = _replace(methods['restore_b'], 'profile = validate_inputs(inputs)',
            'profile = validate_inputs(inputs, candidate_bundle=' + candidate + ')')
        restore = _replace(restore,
            'native_members = read_saved_members(self.owner, inputs.configuration, stopped_configuration_phase=True)',
            '''if getattr(self, '_saved_load_candidate', False):
        native_members = dict(status='separate-native-member-reader-unqualified-for-xp1',
                              native_member_lookup_called=False, serialized_content_compared=True)
    else:
        native_members = read_saved_members(self.owner, inputs.configuration, stopped_configuration_phase=True)''')
        restore = _replace(restore,
            'comparison = compare_provider_roundtrip(inputs.configuration, output)',
            '''if getattr(self, '_saved_load_candidate', False) and self.load_abi.ruleset == 'xp2':
        from civ6_host.runtime.configuration_roundtrip import compare_provider_roundtrip as selected_comparison
        comparison = selected_comparison(inputs.configuration, output, core_sha256=self.load_abi.core_sha256)
    else:
        comparison = compare_provider_roundtrip(inputs.configuration, output)''')
        cls.body[cls.body.index(methods['restore_b'])] = restore
        prefix = _replace(methods['install_prefix'], 'def install_prefix(self):',
                          'def install_prefix(self, *, services=None):')
        _prepend(prefix, '''
if getattr(self, '_saved_load_candidate', False):
    from civ6_host.runtime.xp1_saved_load import attach_services
    return attach_services(self, services)
if services is not None:
    raise ValueError('Externally composed services require the explicit XP1 candidate')
''')
        cls.body[cls.body.index(methods['install_prefix'])] = prefix
        readback = _replace(methods['read_loaded_diagnostic'], 'profile = validate_inputs(self.inputs)',
            'profile = validate_inputs(self.inputs, candidate_bundle=' + candidate + ')')
        readback = _replace(readback, 'roster_readback_source(profile)',
            'roster_readback_source(profile, candidate_bundle=' + candidate + ')')
        readback.body[-1:-1] = ast.parse('''
if getattr(self, '_saved_load_candidate', False):
    from civ6_host.runtime.lan_load import human_status_readback_source
    from civ6_host.runtime.xp1_saved_load import validate_loaded_roster
    humans = self.prefix.runtime.evaluate_text(self.prefix.game_child,
        human_status_readback_source(values[3:]), b'@official_loaded_xp1_humans', capacity=256)
    result.update(validate_loaded_roster(self, roster, humans))
''').body
        cls.body[cls.body.index(methods['read_loaded_diagnostic'])] = readback
        run = _replace(functions['run_experiment'], 'def run_experiment(backend, inputs):',
                       'def run_experiment(backend, inputs, *, prepare_services=None):')
        _prepend(run, '''
candidate = getattr(backend, '_saved_load_candidate', False)
if candidate and not callable(prepare_services):
    raise ValueError('XP1 candidate requires explicit existing runtime/child/service composition')
if not candidate and prepare_services is not None:
    raise ValueError('Service composition is only admitted for the exact XP1 candidate')
''')
        run = _replace(run, 'profile = validate_inputs(inputs)',
            'profile = validate_inputs(inputs, candidate_bundle=backend.captured_bundle if candidate else None)')
        run = _replace(run, 'backend.install_prefix()',
            'backend.install_prefix(services=prepare_services(backend)) if candidate else backend.install_prefix()')
        tree.body[tree.body.index(functions['run_experiment'])] = run
    # The selected private boundary still delegates XP1 to its retained
    # implementation. XP2 is explicit and never inferred by public admission.
    rendered = ast.unparse(ast.fix_missing_locations(tree)) + '\n'
    return rendered.replace('from civ6_host.runtime.xp1_saved_load import ',
                            'from civ6_host.runtime.captured_saved_load import ')

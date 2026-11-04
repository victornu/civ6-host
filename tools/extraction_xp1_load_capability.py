"""Private candidate selection in the existing EXE ownership service."""
import ast

MODULES = ('civ6rl.native_host_capability_status', 'civ6rl.native_app_ownership')

def change(raw, old, new, count=1):
    if raw.count(old) != count:
        raise ValueError('XP1 capability extraction boundary changed: ' + old[:110])
    return raw.replace(old, new)


def select_candidate_profile(raw):
    """Apply the shared candidate's exact catalogue count and provenance."""
    raw = change(raw, "self.database_profile = 'official-captured-xp1-lan-candidate'",
                 "self.database_profile = catalogue.get('profile_name', 'official-captured-xp1-lan-candidate')")
    raw = change(raw, 'expected_count = 92', "expected_count = catalogue.get('admitted_count', 92)")
    raw = change(raw, "registry_profile='captured-xp1-lan-absent-numeric-candidate'",
                 "registry_profile='captured-'+details.get('candidate_family','xp1-lan')+'-absent-numeric-candidate'")
    raw = change(raw, "branch='captured_xp1_lan_absent_numeric_entry_read_only_projection'",
                 "branch='captured_'+details.get('candidate_family','xp1-lan').replace('-','_')+'_absent_numeric_entry_read_only_projection'")
    return ast.unparse(ast.parse(raw))+'\n'

def parameterize(name, raw):
    if name not in MODULES:return raw
    if name == MODULES[0]:
        raw = change(raw, 'def install_typed_refusal(host, *, base, read):',
            'def install_typed_refusal(host, *, base, read, candidate_backend=None):')
        begin = raw.index("    for fragment in proof['core_functions']['refresh_capabilities']['fragments']:")
        end = raw.index('\n    def refusal(', begin)
        block = raw[begin:end]
        raw = raw[:begin] + '''    if candidate_backend is not None:
        from civ6_host.runtime.xp1_load_capability import verify_candidate_live
        if candidate_backend.host is not host or candidate_backend.core._handle != base:
            raise ValueError('XP1 capability probe owner differs')
        verify_candidate_live(candidate_backend)
    else:
''' + ''.join('    '+line+'\n' for line in block.splitlines()) + raw[end:]
        raw = change(raw, '        details = request_details(player, capability)',
            '''        if candidate_backend is None:
            details = request_details(player, capability)
        else:
            from civ6_host.runtime.xp1_load_capability import candidate_details
            details = candidate_details(candidate_backend, player, capability)''')
        return ast.unparse(ast.parse(raw))+'\n'
    raw = change(raw, 'def read_application_mode(application):',
        '''def read_application_mode(application, *, candidate_backend=None):
    if candidate_backend is not None:
        from civ6_host.runtime.xp1_load_capability import read_mode
        return read_mode(application, candidate_backend)''')
    raw = change(raw, 'def __init__(self, application, installation, manifest, *, required_mode=HOTSEAT, captured_bundle=None):',
        'def __init__(self, application, installation, manifest, *, required_mode=HOTSEAT, captured_bundle=None, candidate_backend=None):\n        self.candidate_backend = candidate_backend')
    old = "        self.database_profile = verify_database_profile(manifest, catalogue['fixture']['gameplay_database_sha256'], captured_bundle=captured_bundle, required_mode=required_mode)"
    raw = change(raw, old, '''        if candidate_backend is None:
            self.database_profile = verify_database_profile(manifest, catalogue['fixture']['gameplay_database_sha256'], captured_bundle=captured_bundle, required_mode=required_mode)
            expected_count = 93
        else:
            from civ6_host.runtime.xp1_load_capability import captured_catalogue
            catalogue = captured_catalogue(candidate_backend, application, manifest, captured_bundle, required_mode)
            self.database_profile = 'official-captured-xp1-lan-candidate'
            expected_count = 92''')
    raw = change(raw, 'if count != 93 or sorted(', 'if count != expected_count or sorted(')
    raw = change(raw, 'len(self.allowed) != 93', 'len(self.allowed) != expected_count')
    start = raw.index('        from civ6_host.runtime.native.native_application_property_copy import verify_source as getter_proof')
    end = raw.index('        if read_application_mode(application)', start)
    block = raw[start:end]
    raw = raw[:start] + '''        if candidate_backend is not None:
            from civ6_host.runtime.xp1_load_capability import verify_candidate_live
            verify_candidate_live(candidate_backend)
        else:
''' + ''.join('    '+line+'\n' for line in block.splitlines()) + raw[end:]
    raw = change(raw, 'if read_application_mode(application) != self.required_mode:',
        'if (read_application_mode(application, candidate_backend=candidate_backend) if candidate_backend is not None else read_application_mode(application)) != self.required_mode:')
    raw = change(raw, 'self.lan_branch = ClosedLanBranch(application, captured_bundle) if required_mode == LAN else None',
        'self.lan_branch = (ClosedLanBranch(application, captured_bundle, candidate_backend=candidate_backend) if candidate_backend is not None else ClosedLanBranch(application, captured_bundle)) if required_mode == LAN else None')
    raw = change(raw, '        details = abi.request_details(player, capability)\n        mode = read_application_mode(self.application)',
        '''        candidate_backend = getattr(self, 'candidate_backend', None)
        if candidate_backend is None:
            details = abi.request_details(player, capability)
            mode = read_application_mode(self.application)
        else:
            from civ6_host.runtime.xp1_load_capability import candidate_details
            details = candidate_details(candidate_backend, player, capability)
            mode = read_application_mode(self.application, candidate_backend=candidate_backend)''')
    raw = change(raw, '        return (result, information)',
        '''        if candidate_backend is not None:
            information.update(registry_profile='captured-xp1-lan-absent-numeric-candidate',
                branch='captured_xp1_lan_absent_numeric_entry_read_only_projection',
                public_session_admitted=False)
        return (result, information)''')
    raw = change(raw, 'def install_closed_base_status(host, application, installation, *, required_mode=HOTSEAT, captured_bundle=None):',
        'def install_closed_base_status(host, application, installation, *, required_mode=HOTSEAT, captured_bundle=None, candidate_backend=None):')
    raw = change(raw, 'profile = ClosedBaseOwnership(application, installation, host.manifest, required_mode=required_mode, captured_bundle=captured_bundle)',
        "profile = ClosedBaseOwnership(application, installation, host.manifest, required_mode=required_mode, captured_bundle=captured_bundle, **({'candidate_backend': candidate_backend} if candidate_backend is not None else {}))")
    raw = change(raw, 'base_capability_count=93,', 'base_capability_count=93 if candidate_backend is None else None, admitted_capability_count=len(profile.allowed),')
    return select_candidate_profile(ast.unparse(ast.parse(raw))+'\n')


def lan_source(raw):
    raw = change(raw, '    def __init__(self, application, captured_bundle):',
        '    def __init__(self, application, captured_bundle, *, candidate_backend=None):\n        self.candidate_backend = candidate_backend')
    start = raw.index("        state = reference_state(captured_bundle)['state']")
    end = raw.index('        self.application = application', start)
    block = raw[start:end]
    raw = raw[:start]+'''        if candidate_backend is None:
'''+''.join('    '+line+'\n' for line in block.splitlines())+'''        else:
            from .xp1_load_capability import validate_lan_candidate
            self.candidate_projection = validate_lan_candidate(application, captured_bundle, candidate_backend)
'''+raw[end:]
    raw = change(raw, '        table = self.application.base + config.CONFIG_VTABLE',
        '''        table = self.application.base + config.CONFIG_VTABLE
        getter_rva = 7626176
        if getattr(self, 'candidate_backend', None) is not None:
            from .xp1_load_capability import source_profile
            proof, _ = source_profile()
            table = self.application.base + proof['configuration_vtable_rva']
            getter_rva = proof['slots']['0x68']['target_rva']''')
    raw = change(raw, 'self.application.base + 7626176', 'self.application.base + getter_rva')
    raw = change(raw, "'branch': 'closed_base_lan_absent_numeric_entry_read_only_projection',",
        "'branch': ('captured_xp1_lan_absent_numeric_entry_read_only_projection' if getattr(self, 'candidate_backend', None) is not None else 'closed_base_lan_absent_numeric_entry_read_only_projection'),")
    raw = change(raw, "'lan_record_source_sha256': SOURCE_PINS['records'][1],",
        """'lan_record_source_sha256': SOURCE_PINS['records'][1] if getattr(self, 'candidate_backend', None) is None else None,
            **(dict(historical_base_record_source_sha256=SOURCE_PINS['records'][1], **self.candidate_projection)
               if getattr(self, 'candidate_backend', None) is not None else {}),""")
    return raw

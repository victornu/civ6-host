"""Retain candidate static metadata across one existing exclusive Load call."""
import ast

MODULES = ('civ6rl.native_application_configuration', 'civ6rl.native_host_capability_status',
           'civ6rl.native_checkpoint_load', 'civ6rl.native_checkpoint_postload_facades')

def change(raw, old, new):
    if raw.count(old) != 1:
        raise ValueError('XP1 capability metadata extraction boundary changed: '+old[:100])
    return raw.replace(old,new)

def parameterize(name, raw):
    if name not in MODULES:
        return raw
    if name == MODULES[0]:
        raw = change(raw, 'def player(self, index):', 'def player(self, index, *, candidate_backend=None):')
        raw = change(raw, "        key = verify_source(core_sha256=self._configuration_abi.core_sha256)['player_keys'][index]['hash']", '''        if candidate_backend is None:
            key = verify_source(core_sha256=self._configuration_abi.core_sha256)['player_keys'][index]['hash']
        else:
            from civ6_host.runtime.xp1_load_capability import candidate_player_key
            key = candidate_player_key(self, index, candidate_backend)''')
    elif name == MODULES[1]:
        raw = change(raw, 'def request_details(player, capability):', 'def request_details(player, capability, *, candidate_backend=None):')
        raw = change(raw, "    verify_source()\n    catalogue = load_pinned_json(ROOT / 'evidence/native-capability-catalogue' / (CATALOGUE_SHA256 + '.json'), CATALOGUE_SHA256)", '''    if candidate_backend is None:
        verify_source()
        catalogue = load_pinned_json(ROOT / 'evidence/native-capability-catalogue' / (CATALOGUE_SHA256 + '.json'), CATALOGUE_SHA256)
    else:
        from civ6_host.runtime.xp1_load_capability import candidate_label_catalogue
        catalogue = candidate_label_catalogue(candidate_backend)''')
    elif name == MODULES[2]:
        raw = change(raw, '        return self.load_call(self.context, self.reader.pointer)', '''        if getattr(self, '_saved_load_candidate', False):
            from civ6_host.runtime.xp1_load_capability import capability_source_scope
            with capability_source_scope(self, 'load'):
                return self.load_call(self.context, self.reader.pointer)
        return self.load_call(self.context, self.reader.pointer)''')
    else:
        raw = change(raw, '            self.owner._saved_load_job_cache_owner = self.publication_owner', '''            self.owner._saved_load_job_cache_owner = self.publication_owner
            from civ6_host.runtime.xp1_load_capability import begin_cache_source_scope
            begin_cache_source_scope(self)''')
        raw = change(raw, '    def finish(self):\n', '''    def finish(self):
        from civ6_host.runtime.xp1_load_capability import finish_cache_source_scope
        finish_cache_source_scope(self)
''')
        tree=ast.parse(raw)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeFacadeBackend')
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='poison')
        cleanup=ast.parse('from civ6_host.runtime.xp1_load_capability import finish_cache_source_scope\nfinish_cache_source_scope(self)').body
        fn.body=[ast.Try(body=cleanup,handlers=[],orelse=[],finalbody=fn.body)]
        raw=ast.unparse(ast.fix_missing_locations(tree))
    return ast.unparse(ast.parse(raw))+'\n'

"""Narrow lifetime join in existing native owners; no alternate loader."""
import ast
MODULES=('civ6rl.native_checkpoint_load','civ6rl.native_checkpoint_configuration_only',
         'civ6rl.native_host','civ6rl.native_player_view')

def change(raw,old,new):
    if raw.count(old)!=1:raise ValueError('Loaded lifetime extraction boundary changed: '+old[:90])
    return raw.replace(old,new)

def parameterize(name,raw):
    if name not in MODULES:return raw
    if name==MODULES[0]:
        tree=ast.parse(raw);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeLoadBackend')
        if any(isinstance(n,ast.FunctionDef) and n.name=='close_loaded' for n in cls.body):
            raise ValueError('Existing loaded lifetime method requires review')
        cls.body+=ast.parse('''def close_loaded(self, *, completed):
    from civ6_host.runtime.xp1_loaded_lifetime import close_loaded
    return close_loaded(self, completed=completed)
''').body
        raw=ast.unparse(ast.fix_missing_locations(tree))
    elif name==MODULES[1]:
        raw=change(raw,'    def destroy_context(self):\n', '''    def destroy_context(self, *, loaded_lifetime=None):
        if loaded_lifetime is not None:
            from civ6_host.runtime.xp1_loaded_lifetime import require_lifetime
            require_lifetime(loaded_lifetime, self).before_destroy(self)
''')
        raw=change(raw,'            if self.owner is not None and (not self.owner.closed):',
                   '            if loaded_lifetime is None and self.owner is not None and (not self.owner.closed):')
        raw=change(raw,'        self.destroyed = True', '''        self.destroyed = True
        if loaded_lifetime is not None:
            loaded_lifetime.after_destroy(self)''')
        raw=change(raw,"self.emit('destroyed', operation_seconds=time.perf_counter() - started, configuration_only=True)",
                   "self.emit('destroyed', operation_seconds=time.perf_counter() - started, configuration_only=loaded_lifetime is None)")
    elif name==MODULES[2]:
        tree=ast.parse(raw);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='release_game_services')
        fn.args.kwonlyargs.append(ast.arg(arg='loaded_lifetime'));fn.args.kw_defaults.append(ast.Constant(None))
        insert=ast.parse('''if loaded_lifetime is not None:
    from civ6_host.runtime.xp1_loaded_lifetime import require_lifetime
    token = require_lifetime(loaded_lifetime)
    rva = token.before_unload(core, context)
    C.WINFUNCTYPE(None, C.c_void_p)(core._handle + rva)(context)
    token.after_unload()
    return
''').body
        # Keep docstring and the complete default Base route unchanged.
        fn.body[1:1]=insert;raw=ast.unparse(ast.fix_missing_locations(tree))
    else:
        raw=change(raw,"        if getattr(self, '_loaded_cache_candidate_owner', None) is not None:\n            raise RuntimeError('Loaded cache candidate retains its wrappers until qualified teardown')",
                   "        if getattr(self, '_loaded_cache_candidate_owner', None) is not None:\n            self._loaded_cache_candidate_owner.authorize_publisher_close(self)")
    return ast.unparse(ast.parse(raw))+'\n'

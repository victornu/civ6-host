"""Explicit private candidate in existing OfficialPost160Backend/sequence."""
import ast
MODULES=('civ6rl.native_official_postload','civ6rl.native_checkpoint_postload160',
         'civ6rl.native_checkpoint_postload_facades')

def change(raw,old,new,count=1):
    if raw.count(old)!=count:raise ValueError('Post160 candidate extraction boundary changed: '+old[:100])
    return raw.replace(old,new)

def parameterize(name,raw):
    if name not in MODULES:return raw
    if name==MODULES[0]:
        raw=change(raw,'def __init__(self, owner, facade, facade_result):',
                   "def __init__(self, owner, facade, facade_result, *, postload_mode='public'):")
        raw=change(raw,'        self.post160_abi = post160.require_runtime_admission(post160.profile_for_sha(owner.load_abi.core_sha256))',
                   '''        self.postload_mode = postload_mode
        from civ6_host.runtime.xp1_postload_candidate import select_profile
        self.post160_abi = select_profile(self, postload_mode)''')
        raw=change(raw,"        validate_owner(b, stage='facades-observed-awaiting-post160')",'''        if self.postload_mode == 'candidate':
            from civ6_host.runtime.xp1_postload_candidate import enter
            return enter(self)
        validate_owner(b, stage='facades-observed-awaiting-post160')''')
        raw=change(raw,'official.roster_readback_source(b.inputs.profile)',
                   "official.roster_readback_source(b.inputs.profile, candidate_bundle=b.captured_bundle if self.postload_mode == 'candidate' else None)")
    elif name==MODULES[1]:
        raw=change(raw,'from civ6_host.runtime.postload160_source import xp1_source',
                   'from civ6_host.runtime.postload160_source import expansion_source')
        raw=change(raw,'return xp1_source(core_sha256)','return expansion_source(core_sha256)')
        raw=change(raw,'from civ6_host.runtime.postload160_source import verify_xp1_live',
                   'from civ6_host.runtime.postload160_source import verify_expansion_live')
        raw=change(raw,'return verify_xp1_live(base, read, proof, core_sha256=core_sha256)',
                   'return verify_expansion_live(base, read, proof, core_sha256=core_sha256)')
        raw=change(raw,'    def observe(self):\n', '''    def observe(self):
        if getattr(self, 'postload_mode', 'public') == 'candidate':
            from civ6_host.runtime.xp1_postload_candidate import check_active
            check_active(self)
''')
        raw=change(raw,'        require_runtime_admission(self.post160_abi)', '''        if getattr(self, 'postload_mode', 'public') == 'candidate':
            from civ6_host.runtime.xp1_postload_candidate import before_call
            before_call(self)
        else:
            require_runtime_admission(self.post160_abi)''')
        call='        C.WINFUNCTYPE(None, C.c_void_p, C.c_uint8)(b.core._handle + self.post160_abi.target_rva)(b.context, 1)'
        raw=change(raw,call,call+'''
        if getattr(self, 'postload_mode', 'public') == 'candidate':
            from civ6_host.runtime.xp1_postload_candidate import after_call
            after_call(self)''')
        raw=change(raw,'    def finish(self):\n', '''    def finish(self):
        if getattr(self, 'postload_mode', 'public') == 'candidate':
            from civ6_host.runtime.xp1_postload_candidate import finish, FINISHED_STAGE
            finish(self)
            self.owner.stage = FINISHED_STAGE
            self.owner.busy = False
            return
''')
        tree=ast.parse(raw)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativePostload160Backend')
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='poison')
        cleanup=ast.parse("if getattr(self, 'postload_mode', 'public') == 'candidate':\n from civ6_host.runtime.xp1_postload_candidate import poison\n poison(self)").body
        fn.body=[ast.Try(body=cleanup,handlers=[],orelse=[],finalbody=fn.body)]
        raw=ast.unparse(ast.fix_missing_locations(tree))
    else:
        raw=change(raw,"        backend.finish()\n        emit('native_checkpoint_postload_facades_observed', **result)",
                   "        backend.finish()\n        backend.completed_result = result\n        emit('native_checkpoint_postload_facades_observed', **result)")
    return ast.unparse(ast.parse(raw))+'\n'

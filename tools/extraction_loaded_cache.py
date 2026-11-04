"""Apply after existing cache-facade AST transforms and final path rewriting."""
BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MODULES={'civ6rl.native_ui_cache_facades','civ6rl.native_ui_cache_backend',
         'civ6rl.native_player_view','civ6rl.native_checkpoint_postload_facades'}

def one(text,old,new):
    if text.count(old)!=1:raise ValueError('Loaded-cache extraction anchor changed: '+old[:100])
    return text.replace(old,new,1)

def method(text,name,new):
    start=text.index('    def '+name+'(')
    end=text.find('\n    def ',start+1)
    if end<0:raise ValueError('Loaded-cache method boundary changed: '+name)
    return text[:start]+new.rstrip()+'\n'+text[end:]

def parameterize(name,text):
    if name not in MODULES:return text
    if name.endswith('native_ui_cache_facades'):
        text=one(text,'    def refresh(self) -> CacheRefreshResult:\n        if not self.abi.full_refresh_admitted:\n            raise ValueError(\'Full cache population is not qualified for this engine\')', '''    def refresh(self, *, public_gate=True) -> CacheRefreshResult:
        if type(public_gate) is not bool:
            raise ValueError('Cache publication mode requires an exact Boolean')
        candidate = None
        if public_gate:
            if not self.abi.full_refresh_admitted:
                raise ValueError('Full public cache population is not qualified for this engine')
        else:
            candidate = self.backend.require_loaded_publication(self)''')
        return one(text,'        self.backend.set_public_cache_gate(True)\n        return result', '''        if public_gate:
            self.backend.set_public_cache_gate(True)
        else:
            candidate.copy_returned(self.backend, self)
        return result''')
    if name.endswith('native_ui_cache_backend'):
        text=one(text,"core_sha256='"+BASE+"'):","core_sha256='"+BASE+"', publication_owner=None):")
        text=one(text,'        self.abi = facade_abi(core_sha256)','        self.abi = facade_abi(core_sha256)\n        self.publication_owner = publication_owner')
        text=one(text,'        self.gate_changed(enabled)', '''        if self.publication_owner is not None and enabled is not False:
            raise ValueError('Candidate population cannot open the public cache gate')
        self.gate_changed(enabled)''')
        text=one(text,'    def call(self, target, *arguments):', '''    def call(self, target, *arguments):
        candidate = self.publication_owner
        if candidate is None:
            return self._call(target, *arguments)
        from civ6_host.runtime.loaded_cache_publication import LoadedCachePublication
        if type(candidate) is not LoadedCachePublication:
            raise ValueError('Foreign candidate publication capability')
        try:
            candidate.before_backend_call(self, target, arguments)
            result = self._call(target, *arguments)
            candidate.after_backend_call(self, target, result)
            return result
        except BaseException:
            candidate.poison()
            raise

    def _call(self, target, *arguments):''')
        text=one(text,'    def read_qword(self, address):', '''    def require_loaded_publication(self, facades=None):
        from civ6_host.runtime.loaded_cache_publication import require_candidate
        return require_candidate(self, facades)

    def read_qword(self, address):''')
        text=one(text,"            if not self.abi.full_refresh_admitted:\n                raise ValueError('Full cache population is not qualified for this engine')",'''            candidate = None if self.abi.full_refresh_admitted else self.require_loaded_publication()''')
        return one(text,'            C.WINFUNCTYPE(None, C.c_void_p, C.c_uint8)(target)(receiver, 1)\n            return None', '''            try:
                if candidate is not None:
                    candidate.begin(self, receiver)
                C.WINFUNCTYPE(None, C.c_void_p, C.c_uint8)(target)(receiver, 1)
                if candidate is not None:
                    candidate.native_returned(self)
                return None
            except BaseException:
                if candidate is not None:
                    candidate.poison()
                raise''')
    if name.endswith('native_player_view'):
        text=one(text,"initialization_profile='public-cache-facade'):","initialization_profile='public-cache-facade', *, core_sha256='"+BASE+"'):")
        text=one(text,'        self.core = core', '''        from civ6_host.runtime.loaded_cache_profiles import loaded_cache_abi
        self.cache_abi = loaded_cache_abi(core_sha256)
        self.core = core''')
        text=method(text,'_validate', '''    def _validate(self):
        from civ6_host.runtime.loaded_cache_profiles import service_state
        return service_state(self.core._handle, self.context, self.read, self.cache_abi)
''')
        text=one(text,'        result = read_retained_game_value(self._facades, self.read)', '        result = read_retained_game_value(self._facades, self.read, core_sha256=self.cache_abi.core_sha256)')
        text=one(text,"        from civ6_host.runtime.native.native_combat_owner_predicate import query_owner", "        if self.cache_abi.core_sha256 != '"+BASE+"':\n            raise ValueError('XP1 public combat cache queries are not qualified')\n        from civ6_host.runtime.native.native_combat_owner_predicate import query_owner")
        text=one(text,'        service, game = self._validate()',"        if self.cache_abi.core_sha256 != '"+BASE+"':\n            raise ValueError('XP1 dynamic kind4/public cache publication is not qualified')\n        service, game = self._validate()")
        text=one(text,'        try:\n            if self._facades is not None:\n                self._facades.close()', "        if getattr(self, '_loaded_cache_candidate_owner', None) is not None:\n            raise RuntimeError('Loaded cache candidate retains its wrappers until qualified teardown')\n        try:\n            if self._facades is not None:\n                self._facades.close()")
        return text
    text=one(text,'def verify_source():',"def verify_source(*, core_sha256='"+BASE+"'):\n    from civ6_host.runtime.loaded_cache_profiles import loaded_cache_abi, source\n    abi = loaded_cache_abi(core_sha256)\n    if abi.core_sha256 != '"+BASE+"':\n        return source(core_sha256=core_sha256)")
    text=one(text,'def check_live_code(base, read, proof):',"def check_live_code(base, read, proof, *, core_sha256='"+BASE+"'):\n    from civ6_host.runtime.loaded_cache_profiles import loaded_cache_abi, verify_live\n    abi = loaded_cache_abi(core_sha256)\n    if abi.core_sha256 != '"+BASE+"':\n        return verify_live(base, read, proof, core_sha256=core_sha256)")
    text=one(text,'    def __init__(self, owner, load_result):',"    def __init__(self, owner, load_result, *, publication_mode='public'):")
    text=one(text,'        self.proof = verify_source()', '''        self.configure_publication(publication_mode)

    def configure_publication(self, publication_mode):
        from civ6_host.runtime.loaded_cache_profiles import loaded_cache_abi, require_mode
        self.cache_abi = loaded_cache_abi(self.owner.load_abi.core_sha256)
        require_mode(self.cache_abi, publication_mode)
        self.publication_mode = publication_mode
        self.publication_owner = None
        self.proof = verify_source(core_sha256=self.cache_abi.core_sha256)''')
    text=one(text,"        if getattr(p, 'view_publisher', None) is not None or d.ui_cache_callbacks_enabled is not False or d.retained_game_getter is not None or (d.retained_combat_predicate is not None) or (p.configuration_readback_verified is not True):\n            raise RuntimeError('Post-load cache owner already exists or configuration is unverified')", '''        from civ6_host.runtime.loaded_cache_publication import initial_publisher_state
        initial_publisher_state(p, self.cache_abi.core_sha256)''')
    text=one(text,'        check_live_code(b.core._handle, b.runtime.read, self.proof)\n        b.busy = True', '''        check_live_code(b.core._handle, b.runtime.read, self.proof, core_sha256=self.cache_abi.core_sha256)
        b.busy = True
        self.begin_publication_owner()''')
    text=one(text,'    def observe(self):', '''    def begin_publication_owner(self):
        if self.publication_mode == 'candidate':
            from civ6_host.runtime.loaded_cache_publication import LoadedCachePublication
            if hasattr(self.owner, '_saved_load_job_cache_owner'):
                raise RuntimeError('Loaded-cache scheduler lease is already installed')
            self.publication_owner = LoadedCachePublication(self)
            self.owner._saved_load_job_cache_owner = self.publication_owner

    def observe(self):''')
    text=one(text,'before = b.runtime.read(b.core._handle + 9031072, 1)[0]','before = b.runtime.read(b.core._handle + self.cache_abi.notification_byte_rva, 1)[0]')
    # The byte occurs twice; retain strict separate anchors.
    text=one(text,'(b.core._handle + 4381856)(b.context, 1)','(b.core._handle + self.cache_abi.notification_rva)(b.context, 1)')
    text=text.replace('b.core._handle + 9031072','b.core._handle + self.cache_abi.notification_byte_rva')
    text=one(text,'        before = b.runtime.read(b.core._handle + self.cache_abi.notification_byte_rva, 1)[0]', '''        if self.publication_owner is not None:
            self.publication_owner._check()
        before = b.runtime.read(b.core._handle + self.cache_abi.notification_byte_rva, 1)[0]''')
    text=one(text,'        return returned\n\n    def acquire_facades', '''        if self.publication_owner is not None:
            self.publication_owner._check()
        return returned

    def acquire_facades''')
    text=one(text,'NativePlayerViewPublisher(b.core, b.context, b.emit, read=b.runtime.read)','NativePlayerViewPublisher(b.core, b.context, b.emit, read=b.runtime.read, core_sha256=self.cache_abi.core_sha256)')
    text=one(text,'context_alive=lambda: not b.destroyed and (not b.poisoned), read=b.runtime.read)', 'context_alive=lambda: not b.destroyed and (not b.poisoned), read=b.runtime.read, core_sha256=self.cache_abi.core_sha256, publication_owner=self.publication_owner)')
    text=one(text,'        facades = NativeUiCacheFacades.__new__(NativeUiCacheFacades)', '''        if self.publication_owner is not None:
            self.publisher._loaded_cache_candidate_owner = self.publication_owner
            self.publication_owner.attach(self.publisher, backend)
        facades = NativeUiCacheFacades.__new__(NativeUiCacheFacades)''')
    text=one(text,'        facades.__init__(backend, b.context)','        facades.__init__(backend, b.context, core_sha256=self.cache_abi.core_sha256)')
    text=one(text,'        copied = self.publisher._facades.refresh()',"        copied = self.publisher._facades.refresh(public_gate=self.publication_mode == 'public')")
    text=method(text,'bind_cache', '''    def bind_cache(self, copied):
        from civ6_host.runtime.loaded_cache_profiles import validate_copy
        b, p = self.owner, self.publisher
        expected = self.load_result['readback']
        state = validate_copy(b.core._handle, b.context, b.runtime.read, self.cache_abi,
            p._facades, copied, expected_game=b.bound_identity['game'],
            expected_dimensions=(expected['width'], expected['height']))
        if self.publication_mode == 'candidate':
            if p.native_cache_gate is not False or self.publication_owner.copied is not True:
                raise RuntimeError('Candidate publication opened a public gate or lacks its native copy')
            self.publication_owner.require(p._facades.backend, p._facades)
            p.cache_map_snapshot = copied
            self.validated_candidate_cache = state
            return
        if p.native_cache_gate is not True:
            raise RuntimeError('Native facade refresh did not enable its cache gate')
        p.cache_map_snapshot = copied
        p.full_facade_initialization_reproduced = True
        d = b.prefix.deferred_events
        d.admit_initialized_ui_cache_profile('public-cache-facade', state['dimensions'],
            full_facade_initialization_reproduced=True, cache_map_snapshot=copied)
        d.bind_retained_game_getter(p.read_retained_game_value)
        d.bind_retained_combat_predicate(p.query_combat_owner)
        d.bind_natural_wonder_facades(p)
''')
    text=one(text,"        self.owner.stage = 'facades-observed-awaiting-post160'", "        if self.publication_mode == 'candidate':\n            if getattr(self.owner, '_saved_load_job_cache_owner', None) is not self.publication_owner:\n                raise RuntimeError('Loaded-cache scheduler lease was replaced')\n            del self.owner._saved_load_job_cache_owner\n        self.owner.stage = ('facades-candidate-observed' if self.publication_mode == 'candidate'\n                            else 'facades-observed-awaiting-post160')")
    text=one(text,'    def poison(self):\n        self.owner.poisoned = True',
        "    def poison(self):\n        if self.publication_owner is not None:\n            self.publication_owner.poison()\n        self.owner.poisoned = True")
    text=one(text,"        backend.finish()\n        emit('native_checkpoint_postload_facades_observed', **result)", "        if getattr(backend, 'publication_mode', 'public') == 'candidate':\n            result.update(candidate_native_cache_only=True, public_cache_gate_enabled=False, post160_admitted=False)\n        backend.finish()\n        emit('native_checkpoint_postload_facades_observed', **result)")
    text=one(text,'def run_facades_only(core, context, load_result, emit):',"def run_facades_only(core, context, load_result, emit, *, publication_mode='public'):")
    return one(text,'backend = NativeFacadeBackend(owner, load_result)','backend = NativeFacadeBackend(owner, load_result, publication_mode=publication_mode)')
def parameterize_official(name, text):
    """Join the same candidate to the existing official saved-Load owner."""
    if name != 'civ6rl.native_official_postload':
        return text
    text=one(text, '    official.validate_inputs(inputs)',
        "    if getattr(owner, '_saved_load_candidate', False):\n"
        "        official.validate_inputs(inputs, candidate_bundle=owner.captured_bundle)\n"
        "    else:\n        official.validate_inputs(inputs)")
    text=one(text, '    def __init__(self, owner, receipt):',
        "    def __init__(self, owner, receipt, *, publication_mode='public'):")
    text=one(text, '        self.proof = facades.verify_source()',
        '        self.configure_publication(publication_mode)')
    text=one(text, "        if getattr(p, 'view_publisher', None) is not None or d.ui_cache_callbacks_enabled is not False or d.retained_game_getter is not None or (d.retained_combat_predicate is not None) or (p.configuration_readback_verified is not True):\n            raise RuntimeError('Official cache publisher already exists or configuration is unverified')",
        '        from civ6_host.runtime.loaded_cache_publication import initial_publisher_state\n'
        '        initial_publisher_state(p, self.cache_abi.core_sha256)')
    text=one(text, '        facades.check_live_code(b.core._handle, b.runtime.read, self.proof)\n        b.busy = True',
        '        facades.check_live_code(b.core._handle, b.runtime.read, self.proof, core_sha256=self.cache_abi.core_sha256)\n'
        '        b.busy = True\n        self.begin_publication_owner()')
    return text


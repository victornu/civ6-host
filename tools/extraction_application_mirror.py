"""Source-preserving engine selection for the existing application mirror.

The original algorithms stay in the lab. Only address/proof selection and the
already-shared indexed configuration reader are changed during extraction.
"""
import ast

MODULES = tuple('civ6rl.'+name for name in (
    'native_application_property_copy', 'native_application_mirror_dispatch',
    'native_game_value_prelude_snapshot', 'native_game_value_prelude_mutation',
    'native_player_allocator_inventory', 'native_application_mirror'))


def parameterize(name, tree):
    if name not in MODULES:
        return tree
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    classes={n.name:n for n in tree.body if isinstance(n,ast.ClassDef)}

    def methods(cls):
        return {n.name:n for n in classes[cls].body if isinstance(n,ast.FunctionDef)}

    def insert(fn, text):
        at=int(bool(fn.body and isinstance(fn.body[0],ast.Expr)
                    and isinstance(fn.body[0].value,ast.Constant)
                    and isinstance(fn.body[0].value.value,str)))
        fn.body[at:at]=ast.parse(text).body

    def argument(fn):
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
        fn.args.kw_defaults.append(ast.Name(id='_BASE_CORE',ctx=ast.Load()))

    def rewrite(fn, replacements):
        table={ast.dump(ast.parse(old,mode='eval').body):new for old,new in replacements.items()}
        hits={key:0 for key in table}
        class Replace(ast.NodeTransformer):
            def visit(self,node):
                key=ast.dump(node)
                if key in table:
                    hits[key]+=1
                    return ast.copy_location(ast.parse(table[key],mode='eval').body,node)
                return super().visit(node)
        Replace().visit(fn)
        if any(v==0 for v in hits.values()):
            raise ValueError('Application mirror expression changed: '+repr(replacements))

    def call(fn,callee,value,count=1):
        found=0
        for n in ast.walk(fn):
            if isinstance(n,ast.Call) and ast.unparse(n.func)==callee:
                n.keywords.append(ast.keyword(arg='core_sha256',value=ast.parse(value,mode='eval').body))
                found+=1
        if found!=count:raise ValueError('Application mirror call changed: '+callee)

    def route(fn,expr):
        argument(fn)
        insert(fn,'if core_sha256 != _BASE_CORE:\n    return '+expr)

    def local(fn):
        argument(fn)
        insert(fn,'abi = _mirror_abi(core_sha256)')

    imports='''
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _BASE_CORE
from civ6_host.runtime import application_mirror_profiles as _mirror_profiles
from civ6_host.runtime.application_mirror_profiles import mirror_abi as _mirror_abi
'''
    at=0
    while at<len(tree.body) and (isinstance(tree.body[at],ast.Expr)
            or isinstance(tree.body[at],ast.ImportFrom) and tree.body[at].module=='__future__'):
        at+=1
    tree.body[at:at]=ast.parse(imports).body
    if name.endswith('.native_application_property_copy'):
        route(functions['verify_source'],'_mirror_profiles.copy_source(core_sha256)')
        fn=functions['copy_existing'];local(fn)
        call(fn,'verify_source','core_sha256')
        rewrite(fn,{'_TABLE':'abi.configuration.vtable_rva','_LOOKUP':'abi.configuration.lookup_rva',
                    '_ALLOCATOR':'abi.allocator_get_rva','_ASSIGN':'abi.variant_assign_rva',
                    'PROOF_SHA256':'abi.copy_proof_sha256'})
    elif name.endswith('.native_game_value_prelude_snapshot'):
        route(functions['_sources'],'_mirror_profiles.snapshot_sources(core_sha256)')
        fn=functions['snapshot_game_value_prelude'];local(fn)
        call(fn,'_sources','core_sha256')
        rewrite(fn,{'MAP_TABLE':'abi.configuration.vtable_rva','LOOKUP':'abi.configuration.lookup_rva',
            '0x8BCC58':'abi.configuration.root_key_rva','0x8BCD08':'abi.configuration.map_key_rva',
            '0x8BCD50':'abi.configuration.player_key_table_rva','PROOF_SHA256':'abi.snapshot_proof_sha256',
            'ALIAS_SHA256':'abi.configuration.application_proof_sha256','TREE_SHA256':'abi.tree_proof_sha256'})
    elif name.endswith('.native_player_allocator_inventory'):
        route(functions['verify_source'],'_mirror_profiles.inventory_source(core_sha256)')
        fn=functions['snapshot_player_allocator_targets'];local(fn)
        call(fn,'verify_source','core_sha256')
        call(fn,'snapshot.snapshot_game_value_prelude','core_sha256',2)
        rewrite(fn,{'NEXT_RVA':'abi.successor_rva','LOOKUP_RVA':'abi.configuration.lookup_rva',
                    'PROOF_SHA256':'abi.prelude_proof_sha256','TREE_PROOF_SHA256':'abi.tree_proof_sha256'})
    elif name.endswith('.native_game_value_prelude_mutation'):
        route(functions['verify_source'],'_mirror_profiles.prelude_source(core_sha256)')
        route(functions['verify_lifetime_source'],'_mirror_profiles.lifetime_source(core_sha256)')
        m=methods('NativePreludeAttempt');argument(m['__init__'])
        insert(m['__init__'],'self.abi = _mirror_profiles.owner_abi(application_owner, core_sha256)')
        for callee in ('verify_source','verify_lifetime_source'):call(m['__init__'],callee,'core_sha256')
        replacements={'METHODS':'self.abi.methods','VTABLE':'self.abi.configuration.vtable_rva',
                      'PROOF_SHA256':'self.abi.prelude_proof_sha256',
                      'LIFETIME_SHA256':'self.abi.lifetime_proof_sha256',
                      'LIVE_INSPECTION_SHA256':'self.abi.live_inspection_sha256'}
        for fn in m.values():
            present={n.id for n in ast.walk(fn) if isinstance(n,ast.Name)}
            rewrite(fn,{k:v for k,v in replacements.items() if k in present})
        call(m['_snapshot'],'snapshot_module.snapshot_game_value_prelude','self.abi.configuration.core_sha256')
        call(m['_inventory_player'],'snapshot_module._sources','self.abi.configuration.core_sha256')
        call(m['apply'],'snapshot_module._sources','self.abi.configuration.core_sha256')
        call(m['apply'],'inventory_module.snapshot_player_allocator_targets','self.abi.configuration.core_sha256')
        # A failed expansion attempt is retained until worker termination. No
        # guessed release after a possible native transfer/callback effect.
        rewrite(m['apply'],{'self._release_untransferred()':
            '(self._release_untransferred() if self.abi.configuration.core_sha256 == _BASE_CORE else None)'})
    elif name.endswith('.native_application_mirror_dispatch'):
        route(functions['verify_source_evidence'],'_mirror_profiles.dispatch_source(core_sha256)')
        m=methods('BorrowedApplicationDispatcher');argument(m['__init__'])
        insert(m['__init__'],'self.abi = _mirror_profiles.owner_abi(application_owner, core_sha256)')
        call(m['__init__'],'verify_source_evidence','core_sha256')
        replacements={'ARGUMENT_VTABLE':'self.abi.argument_vtable_rva','GETTER':'self.abi.argument_getter_rva',
            'MAP_VTABLE':'self.abi.configuration.vtable_rva','LOOKUP':'self.abi.configuration.lookup_rva',
            'GAME_SHA256':'self.abi.game_proof_sha256','LIFETIME_SHA256':'self.abi.lifetime_proof_sha256',
            'DISPATCH_SHA256':'self.abi.dispatch_proof_sha256','COPY_SHA256':'self.abi.copy_proof_sha256'}
        for fn in m.values():
            present={n.id for n in ast.walk(fn) if isinstance(n,ast.Name)}
            rewrite(fn,{k:v for k,v in replacements.items() if k in present})
        call(m['_owners'],'setup._linked_snapshot','self.abi.configuration.core_sha256')
        fn=m['dispatch']
        rewrite(fn,{'0x8BCC7C':'self.abi.phase_key_rva'})
        call(fn,'prelude.NativePreludeAttempt','self.abi.configuration.core_sha256')
        call(fn,'copy_existing','self.abi.configuration.core_sha256',2)
        for n in ast.walk(fn):
            if (isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                    and n.func.id=='bounded_get_player_config'):
                n.func=ast.Attribute(value=ast.Name(id='_mirror_profiles',ctx=ast.Load()),attr='indexed_player',ctx=ast.Load())
                n.keywords.append(ast.keyword(arg='call',value=ast.parse('self._call',mode='eval').body))
                n.keywords.append(ast.keyword(arg='core_sha256',value=ast.parse('self.abi.configuration.core_sha256',mode='eval').body))
    elif name.endswith('.native_application_mirror'):
        m=methods('NativePlayerApplicationMirror');argument(m['__init__'])
        insert(m['__init__'],'''self.abi = _mirror_abi(core_sha256)
if core_sha256 != _BASE_CORE and getattr(host, 'application_configuration', None) is None:
    raise ValueError('Expansion mirror requires the existing configuration owner')''')
        rewrite(m['__init__'],{'0x745CB0':'self.abi.configuration.lookup_rva','0x73B410':'self.abi.successor_rva',
                              'PROOF_SHA256':'self.abi.records_proof_sha256'})
        # Keep the original implementation and callback ABI. The saved-Load
        # owner needs an explicit release boundary in addition to installation.
        insert(m['__init__'],'''from threading import get_native_id
self._mirror_thread = get_native_id()
self.closed = False
self._previous_callback = host.vtable[0x130 // 8]
self._binding_key = (C.addressof(host.vtable), 0x130)
self._previous_binding = getattr(host, '_slot_bindings', {}).get(self._binding_key)''')
        for i,n in enumerate(m['__init__'].body):
            if isinstance(n,ast.Assign) and ast.unparse(n).startswith('self.read = local_reader()'):
                m['__init__'].body[i+1:i+1]=ast.parse('''
if core_sha256 != _BASE_CORE:
    _mirror_profiles.owner_abi(self.application_configuration if hasattr(self, 'application_configuration') else host.application_configuration, core_sha256)
    _mirror_profiles.verify_live(self.base, self.read, core_sha256=core_sha256)
''').body
                break
        else:raise ValueError('Mirror reader assignment boundary changed')
        m['__init__'].body.extend(ast.parse('self._callback_address = host.vtable[0x130 // 8]').body)
        insert(m['dispatch'],'''from threading import get_native_id
if self.closed or get_native_id() != self._mirror_thread:
    raise ValueError('Application mirror closed or called from another thread')''')
        call(m['dispatch'],'BorrowedApplicationDispatcher','self.abi.configuration.core_sha256')
        classes['NativePlayerApplicationMirror'].body.extend(ast.parse('''
def close(self):
    from threading import get_native_id
    if get_native_id() != self._mirror_thread:
        raise ValueError('Application mirror close crossed its native thread')
    if self.closed:
        return
    if self.host.vtable[0x130 // 8] != self._callback_address:
        raise ValueError('Application mirror callback has been replaced')
    if self.mirror.changes:
        raise ValueError('Application mirror still has unconsumed player notifications')
    dispatcher = getattr(self, '_borrowed_dispatcher', None)
    if dispatcher is not None:
        dispatcher.close()
    self.host.vtable[0x130 // 8] = self._previous_callback
    if self._previous_binding is None:
        self.host._slot_bindings.pop(self._binding_key, None)
    else:
        self.host._slot_bindings[self._binding_key] = self._previous_binding
    self.closed = True
''').body)
    return tree

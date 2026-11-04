"""Staged additional facade-family extraction hook; no independent event logic."""
import ast
from civ6_host.runtime.foundation_facade_profiles import BASE_SHA256 as BASE,XP1_SHA256 as XP1,XP2_SHA256 as XP2,_BASE_OPERATIONS,_BASE_TABLES

# Each selected function either performs a shared query or forwards its engine
# identity to one. No other function/codec body is transformed.
FUNCTIONS={
 'native_event_fa5b1159':{'_query_plot_owner','query_callback_values','read_player_civilization_type_id'},
 'native_event_5d0f4014':{'query_descriptor'},
 'native_plot_ui_query':{'query_plot_ui'},
 'native_event_c3183902':{'_check_object','_api','produce_record_lease'},
 'native_event_28d6ebbe':{'_check','_api','produce_record_lease'},
 'native_event_07c83dae':{'plot_snapshot','produce_record_lease'},
 'native_event_037a1bee':{'produce_record_lease'},
 'native_event_e66012a7':{'_district_type_hash','produce_records'},
 'native_feature_visibility_event':{'_query_plot_snapshot_word'},
 'native_event_9aea8529':{'query_plot_word','encode_record','encode_scoped_record'},
 'native_event_10419f1f':{'produce_record'},
 'native_event_2b1ba0f8':{'produce_record'},
 'native_building_visibility_scope':{'dispatch_scoped'},
}
QUERIES={
 ('native_event_fa5b1159','_query_plot_owner'),('native_event_5d0f4014','query_descriptor'),
 ('native_plot_ui_query','query_plot_ui'),('native_event_c3183902','_check_object'),
 ('native_event_c3183902','_api'),('native_event_28d6ebbe','_check'),('native_event_28d6ebbe','_api'),
 ('native_event_07c83dae','plot_snapshot'),('native_event_e66012a7','_district_type_hash'),
 ('native_feature_visibility_event','_query_plot_snapshot_word'),
}
CONSTANTS={
 'OUTER_VTABLE':('table','outer'),'OUTER_MAP_GET':('rva','outer_map'),
 'OUTER_MAP_SLOT':('slot','outer_map'),
 'MAP_VTABLE':('table','map'),'MAP_RELEASE':('rva','release_map'),
 'MAP_RELEASE_SLOT':('slot','release_map'),
 'MAP_GET_PLOT':('rva','get_plot'),'PLOT_VTABLE':('table','plot'),
 'MAP_GET_PLOT_SLOT':('slot','get_plot'),
 'PLOT_RELEASE':('rva','release_plot'),'PLOT_RELEASE_SLOT':('slot','release_plot'),
 'PLOT_VALUE':('rva','plot_owner'),'PLOT_VALUE_SLOT':('slot','plot_owner'),
 'PLOT_SNAPSHOT':('rva','plot_snapshot180'),
 'OUTER_VTABLE_RVA':('table','outer'),'OUTER_POSITION_GETTER_RVA':('rva','outer_game'),
 'GAME_FACADE_VTABLE_RVA':('table','game'),'GAME_FACADE_RELEASE_RVA':('rva','release_game'),
 'GAME_FACADE_POSITION_QUERY_RVA':('rva','position_service'),
 'POSITION_FACADE_VTABLE_RVA':('table','position'),'POSITION_FACADE_RELEASE_RVA':('rva','release_position'),
 'POSITION_VALUE_RVA':('rva','position_value'),'POSITION_FLAG_RVA':('rva','position_flag'),
}
NUMBERS={v:('table',key) for key,v in _BASE_TABLES.items()}
NUMBERS.update({spec['rva']:('rva',name) for name,spec in _BASE_OPERATIONS.items()})

def expression(op,key):
    return ast.Call(ast.Attribute(ast.Name('_foundation_abi',ast.Load()),op,ast.Load()),[ast.Constant(key)],[])

def _called(node):return ast.unparse(node.func)

def _propagation(module):
    shared={'query_secondary_value','read_player_civilization_type_id','query_optional_position','shared.query_callback_values',
        'snapshot.plot_snapshot','shared.query_secondary_value','shared.read_player_civilization_type_id',
        '_query_plot_snapshot_word','query_plot_ui'}
    if module=='native_event_fa5b1159':shared.update({'_query_plot_owner'})
    if module=='native_event_c3183902':shared.update({'_api','_check_object'})
    if module=='native_event_28d6ebbe':shared.update({'_api','_check'})
    if module=='native_event_07c83dae':shared.update({'plot_snapshot'})
    if module=='native_event_e66012a7':shared.update({'_district_type_hash'})
    if module=='native_event_9aea8529':shared.update({'encode_record'})
    if module=='native_building_visibility_scope':shared.update({'event037.produce_record_lease'})
    return shared

def transform(module_name,source):
    name=module_name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if name not in FUNCTIONS:return source
    tree=ast.parse(source); selected={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in FUNCTIONS[name]}
    if set(selected)!=FUNCTIONS[name]:raise ValueError('Facade family helper set changed: '+name)
    replacements=[]
    for fname,fn in selected.items():
        if any(a.arg=='core_sha256' for a in (*fn.args.args,*fn.args.kwonlyargs)):
            raise ValueError('Extended facade hook already applied: '+name+'.'+fname)
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Constant(BASE))
        query=(name,fname) in QUERIES
        propagation=_propagation(name)
        class Rewrite(ast.NodeTransformer):
            def visit_Constant(self,node):
                if query and type(node.value) is int and node.value in NUMBERS:
                    return ast.copy_location(expression(*NUMBERS[node.value]),node)
                return node
            def visit_Name(self,node):
                if query and isinstance(node.ctx,ast.Load) and node.id in CONSTANTS:
                    return ast.copy_location(expression(*CONSTANTS[node.id]),node)
                return node
            def visit_Attribute(self,node):
                # FA5 reuses the map facade constants through its plot module.
                if query and name=='native_event_fa5b1159' and isinstance(node.value,ast.Name) and node.value.id=='plot' and node.attr in CONSTANTS:
                    return ast.copy_location(expression(*CONSTANTS[node.attr]),node)
                return self.generic_visit(node)
            def visit_Call(self,node):
                target=_called(node)
                self.generic_visit(node)
                if target in propagation:
                    if any(k.arg=='core_sha256' for k in node.keywords):raise ValueError('Duplicated propagated engine')
                    node.keywords.append(ast.keyword('core_sha256',ast.Name('core_sha256',ast.Load())))
                return node
            def visit_For(self,node):
                self.generic_visit(node)
                # Replace only Base live-byte validation loops. Both engines
                # retain evidence verification; XP1 checks its own pinned bytes.
                if query and ('CORE_CODE_PINS' in ast.unparse(node.iter) or 'runtime_code_pins' in ast.unparse(node.iter)):
                    return ast.If(ast.Compare(ast.Name('core_sha256',ast.Load()),[ast.Eq()],[ast.Constant(BASE)]),[node],
                        ast.parse('verify_xp1_once(core, base, read, resource_root(), core_sha256=core_sha256)').body)
                return node
        fn=Rewrite().visit(fn)
        preamble=ast.parse('if core_sha256 not in '+repr((BASE,XP1,XP2))+':\n    raise ValueError("Unqualified facade engine")').body
        if query:
            preamble.extend(ast.parse('from civ6_host.runtime.foundation_facade_profiles import query_abi, verify_xp1_once, select_tables\n'
                'from civ6_host.runtime.provenance import resource_root\n'
                '_foundation_abi = query_abi(core_sha256, None if core_sha256 == '+repr(BASE)+' else resource_root())').body)
        if fname in ('_check_object','_check') and name in ('native_event_c3183902','native_event_28d6ebbe'):
            # Bind retained Base slots by their source operation identity so
            # XP2 slot shifts cannot silently select a different method.
            preamble.extend(ast.parse("_TABLES = globals()['_TABLES']\n"
                "if core_sha256 != "+repr(BASE)+":\n"
                "    _TABLES = select_tables(core_sha256, _TABLES, resource_root())").body)
        if fname=='read_player_civilization_type_id':
            # Application configuration is the official EXE source; never fall
            # back to Base Core-only addresses on XP1.
            for i,node in enumerate(fn.body):
                if isinstance(node,ast.If) and ast.unparse(node.test)=='read is None':
                    fn.body[i:i]=ast.parse('if core_sha256 != '+repr(BASE)+':\n    raise ValueError("XP1 civilization query requires its bound application configuration")').body
                    break
            else:raise ValueError('Missing application configuration boundary')
        if name=='native_event_e66012a7' and fname=='produce_records':
            # This is a separate family, not an invisible Base-address fallback.
            matches=[node for node in ast.walk(fn) if isinstance(node,ast.If)
                     and any(isinstance(n,ast.Call) and _called(n)=='wonder_handler' for child in node.body for n in ast.walk(child))
                     and "result['type_hash']" in ast.unparse(node.test)]
            if len(matches)!=1:raise ValueError('Wonder branch ownership changed')
            matches[0].body[:0]=ast.parse('if core_sha256 != '+repr(BASE)+':\n    raise ValueError("XP1 wonder AE/AF/application effects require a separately qualified handler")').body
        doc=bool(fn.body and isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant) and isinstance(fn.body[0].value.value,str))
        fn.body[int(doc):int(doc)]=preamble
        ast.fix_missing_locations(fn)
        text=ast.unparse(fn)
        if fn.decorator_list:text=text.removeprefix('\n'.join('@'+ast.unparse(d) for d in fn.decorator_list)+'\n')
        replacements.append((fn.lineno-1,fn.end_lineno,text+'\n'))
    lines=source.splitlines(keepends=True)
    for start,end,text in sorted(replacements,reverse=True):lines[start:end]=[text]
    return ''.join(lines)

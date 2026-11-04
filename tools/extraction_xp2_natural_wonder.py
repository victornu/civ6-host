"""Select the actual XP2 queries in the retained natural-wonder algorithms."""
import ast
BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MODULES=('civ6rl.native_36c9b2b4','civ6rl.native_wonder_application')

def parameterize(name,raw):
    if name not in MODULES:return raw
    tree=ast.parse(raw)
    def function(name):
        found=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name]
        if len(found)!=1:raise ValueError('Natural-wonder extraction function differs: '+name)
        return found[0]
    def engine(fn):
        if any(a.arg=='core_sha256' for a in (*fn.args.args,*fn.args.kwonlyargs)):
            raise ValueError('Natural-wonder source already parameterized')
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Constant(BASE))
    def prepend(fn,text):
        at=int(bool(fn.body and isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant)
                    and isinstance(fn.body[0].value.value,str)))
        fn.body[at:at]=ast.parse(text).body
    def forward(fn,targets):
        seen=set()
        for call in ast.walk(fn):
            if isinstance(call,ast.Call) and ast.unparse(call.func) in targets:
                if any(k.arg=='core_sha256' for k in call.keywords):raise ValueError('Natural-wonder engine forwarded twice')
                seen.add(ast.unparse(call.func));call.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
        if seen!=set(targets):raise ValueError('Natural-wonder shared call seam differs: '+str(set(targets)-seen))
    proof=function('verify_source_evidence');engine(proof)
    prepend(proof,f'''if core_sha256 != {BASE!r}:
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    if core_sha256 != XP2_CORE_SHA256: raise ValueError('Unqualified natural-wonder source engine')
    from civ6_host.runtime.xp2_natural_wonder_source import source
    return source()''')
    if name==MODULES[0]:
        scope=function('verify_counter_neutral_scope');engine(scope)
        prepend(scope,f'''if core_sha256 != {BASE!r}:
    verify_source_evidence(core_sha256=core_sha256)
    from civ6_host.runtime.xp2_natural_wonder_source import counter_scope
    return counter_scope()''')
        lookup=function('_lookup_ignored_input_field');engine(lookup)
        prepend(lookup,f'''if core_sha256 != {BASE!r}:
    verify_source_evidence(core_sha256=core_sha256)
    from civ6_host.runtime.xp2_natural_wonder_source import lookup_ignored_input_field
    return lookup_ignored_input_field(core,input_parameter_map,read,native_api)''')
        produce=function('produce_pair_from_raw_fields');engine(produce)
        forward(produce,('verify_source_evidence','verify_counter_neutral_scope',
                         'native_wonder_application.apply_wonder_application_effects','_lookup_ignored_input_field'))
        calls=[n for n in ast.walk(produce) if isinstance(n,ast.Call) and ast.unparse(n.func)=='query_native_position_index']
        if len(calls)!=1:raise ValueError('Natural-wonder position query seam differs')
        calls[0].func=ast.Name(id='_selected_position_index',ctx=ast.Load())
        calls[0].keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
        tree.body.extend(ast.parse(f'''def _selected_position_index(core,facades,position,*,read,native_api=None,core_sha256={BASE!r}):
    if core_sha256 == {BASE!r}:
        return query_native_position_index(core,facades,position,read=read,native_api=native_api)
    verify_source_evidence(core_sha256=core_sha256)
    from civ6_host.runtime.xp2_natural_wonder_source import position_index
    return position_index(core,facades,position,read=read,native_api=native_api)
''').body)
    else:
        borrow=function('native_game_comparison_value');engine(borrow);forward(borrow,('verify_source_evidence',))
        prepend(borrow,f'''if core_sha256 == {BASE!r}:
    abi=dict(outer_table=7987232,get_game=4382432,game_table=7990488,release_game=4409168,read_value=4411696,
             bodies=((4411696,bytes.fromhex('e9bbdfc1ff')),(340208,bytes.fromhex('8b051a8e8600c3'))))
else:
    verify_source_evidence(core_sha256=core_sha256)
    from civ6_host.runtime.xp2_natural_wonder_source import comparison_abi
    abi=comparison_abi()''')
        class Select(ast.NodeTransformer):
            def visit_Constant(self,node):
                mapping={7987232:'outer_table',4382432:'get_game',7990488:'game_table',4409168:'release_game',4411696:'read_value'}
                if type(node.value) is int and node.value in mapping:
                    return ast.copy_location(ast.Subscript(value=ast.Name(id='abi',ctx=ast.Load()),slice=ast.Constant(mapping[node.value]),ctx=ast.Load()),node)
                return node
        # Transform only the original statements, keeping Base defaults above.
        for statement in borrow.body[2:]:Select().visit(statement)
        loops=[n for n in ast.walk(borrow) if isinstance(n,ast.For) and ast.unparse(n.target)=='(rva, raw_hex)']
        if len(loops)!=1:raise ValueError('Wonder comparison code-byte guard changed')
        loop=loops[0];loop.target=ast.Tuple(elts=[ast.Name(id='rva',ctx=ast.Store()),ast.Name(id='expected',ctx=ast.Store())],ctx=ast.Store())
        loop.iter=ast.Subscript(value=ast.Name(id='abi',ctx=ast.Load()),slice=ast.Constant('bodies'),ctx=ast.Load())
        if ast.unparse(loop.body[0])!='expected = bytes.fromhex(raw_hex)':raise ValueError('Wonder comparison byte guard changed')
        loop.body.pop(0)
        apply=function('apply_wonder_application_effects');engine(apply)
        forward(apply,('verify_source_evidence','native_game_comparison_value'))
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

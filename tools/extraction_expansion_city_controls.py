"""Select sources for the existing focus/MANAGE algorithms; Base stays default."""
import ast

MODULES=('civ6rl.native_saved_city_focus1000','civ6rl.native_saved_citizens')
FUNCTIONS=('verify_source','preamble','catalog_source','request_source','catalog','apply')


def parameterize(name,text):
    if name not in MODULES:return text
    tree=ast.parse(text)
    found={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in FUNCTIONS}
    if set(found)!=set(FUNCTIONS):raise ValueError('Shared city-control algorithm functions changed')
    for node in found.values():
        if any(arg.arg=='core_sha256' for arg in node.args.args+node.args.kwonlyargs):
            raise ValueError('City-control source is already parameterized')
        node.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
        node.args.kw_defaults.append(ast.Name(id='_CITY_CONTROL_BASE_CORE',ctx=ast.Load()))
    # Only the explicit source preface changes. The Lua strings, parser,
    # transition ordering, command count and native effect checks remain shared.
    found['verify_source'].body[:0]=ast.parse('''
if core_sha256 != _CITY_CONTROL_BASE_CORE:
    from civ6_host.runtime.expansion_city_controls_profile import verify_source as selected
    return selected(core_sha256)
''').body
    for name0,node in found.items():
        if name0=='verify_source':continue
        for call in ast.walk(node):
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id in FUNCTIONS:
                call.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
    apply=found['apply'];matches=[(i,n) for i,n in enumerate(apply.body)
        if isinstance(n,ast.Expr) and ast.unparse(n)=='prefix.deferred_events.drain_empty_receivers()']
    if len(matches)!=1:raise ValueError('Shared city-control FIFO boundary changed')
    index,node=matches[0]
    selected=ast.parse('''
if core_sha256 == _CITY_CONTROL_BASE_CORE:
    prefix.deferred_events.drain_empty_receivers()
else:
    prefix.deferred_events.drain()
''').body[0]
    apply.body[index]=selected
    index=int(bool(tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant)
                   and isinstance(tree.body[0].value.value,str)))
    while index<len(tree.body) and isinstance(tree.body[index],ast.ImportFrom) and tree.body[index].module=='__future__':index+=1
    tree.body[index:index]=ast.parse('from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _CITY_CONTROL_BASE_CORE').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'


def portable_contract(focus_text,citizen_text):
    """Extract existing Base validation verbatim except local name prefixes.

    These exact rules also remain in the historical runtime consumers. No
    runtime import or filesystem reference belongs in the portable client.
    """
    output=ast.parse('from types import SimpleNamespace')
    groups=(('focus',focus_text,('SCHEMA','YIELDS','FIELDS'),
             ('uint','validate_action','validate_catalog','actions')),
            ('citizens',citizen_text,('SCHEMA','PLOT_FIELDS','FIELDS','MAX_PLOTS'),
             ('uint','_validate_plot','validate_action','validate_catalog','actions')))
    for prefix,text,constants,functions in groups:
        tree=ast.parse(text);names=set(constants+functions);selected=[]
        for node in tree.body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in constants:selected.append(node)
            elif isinstance(node,ast.FunctionDef) and node.name in functions:selected.append(node)
        if len(selected)!=len(names):raise ValueError('Base portable city contract selection changed')
        class Prefix(ast.NodeTransformer):
            def visit_Name(self,node):
                if node.id in names:node.id=prefix+'_'+node.id
                return node
            def visit_FunctionDef(self,node):
                node.name=prefix+'_'+node.name
                return self.generic_visit(node)
        selected=[Prefix().visit(node) for node in selected]
        output.body.extend(selected)
        binding=prefix+'=SimpleNamespace('+','.join(name+'='+prefix+'_'+name for name in constants+functions)+')'
        output.body.extend(ast.parse(binding).body)
    return '\"\"\"Generated Base city contract selection; no native imports or I/O.\"\"\"\n'+ast.unparse(ast.fix_missing_locations(output))+'\n'

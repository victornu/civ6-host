"""Review-only extraction hook; reuse four existing query bodies, never events.

The caller applies this after the current lab-to-host transformation. It does
not write installed files. Core identity is an explicit keyword from admission.
"""
import ast

BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
COMMON={
 'OUTER_VTABLE':('table','outer'),'OUTER_MAP_GET':('rva','outer_map'),
 'MAP_VTABLE':('table','map'),'MAP_RELEASE':('rva','release_map'),
 'MAP_GET_PLOT':('rva','get_plot'),'PLOT_VTABLE':('table','plot'),
 'PLOT_RELEASE':('rva','release_plot')}
SPECS={
 'native_event_f4fe1b62':('query_plot_value_lease',dict(COMMON,
      PLOT_VALUE=('rva','plot_owner'),PLOT_VALUE_SLOT=('slot','plot_owner'))),
 'native_event_359703a2':('query_plot_words',dict(COMMON,
      MAP_NEIGHBOR_THUNK=('rva','neighbor'),PLOT_VALUE_THUNK=('rva','plot_value'),
      PLOT_VALUE_SLOT=('slot','plot_value'))),
 'native_event_fa5b1159':('query_secondary_value',{
      'OUTER_VTABLE':('table','outer'),'OUTER_ENTITY_GET':('rva','get_player'),
      'OUTER_PAIR_GET':('rva','outer_service'),'ENTITY_VTABLE':('table','player'),
      'ENTITY_RELEASE':('rva','release_player'),'ENTITY_VALUE':('rva','player_type'),
      'PAIR_PRIMARY_VTABLE':('table','type_service'),'PAIR_RELEASE':('rva','release_service'),
      'PAIR_INDEX_QUERY':('rva','service_player_type_hash')}),
 'native_event_827289e6':('query_optional_position',{})}

_OPTIONAL={7987232:('table','outer'),4382784:('rva','outer_map'),
           7991792:('table','map'),4416608:('rva','release_map'),4418768:('rva','optional_position')}

def transform(module_name,source):
    """Return unchanged source for other modules; refuse changed selected ABI."""
    name=module_name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if name not in SPECS:return source
    target,bindings=SPECS[name]
    tree=ast.parse(source)
    funcs=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==target]
    if len(funcs)!=1:raise ValueError('Foundation helper was moved or duplicated')
    fn=funcs[0]
    if any(a.arg=='core_sha256' for a in (*fn.args.args,*fn.args.kwonlyargs)):
        raise ValueError('Foundation facade hook already applied')
    fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
    fn.args.kw_defaults.append(ast.Constant(BASE))
    lines=["from civ6_host.runtime.foundation_facade_profiles import query_abi", 
           "from civ6_host.runtime.provenance import resource_root",
           "_foundation_abi = query_abi(core_sha256, resource_root())"]
    for var,(op,key) in bindings.items():lines.append(f"{var} = _foundation_abi.{op}({key!r})")
    if name=='native_event_fa5b1159':
        lines.append('PAIR_SECONDARY_VTABLE = _foundation_abi.service_secondary_vtable')
        matches=[n for n in ast.walk(fn) if isinstance(n,ast.If) and 'PAIR_SECONDARY_VTABLE' in ast.unparse(n.test)]
        if len(matches)!=1:raise ValueError('Expected exactly one optional secondary-service check')
        matches[0].test=ast.BoolOp(ast.And(),[ast.Compare(ast.Name('PAIR_SECONDARY_VTABLE',ast.Load()),[ast.IsNot()],[ast.Constant(None)]),matches[0].test])
    if name=='native_event_827289e6':
        class Addresses(ast.NodeTransformer):
            def visit_Constant(self,node):
                if type(node.value) is int and node.value in _OPTIONAL:
                    return ast.copy_location(ast.Name('_FOUNDATION_'+str(node.value),ast.Load()),node)
                return node
        fn=Addresses().visit(fn)
        initial=[]
        for value,(op,key) in _OPTIONAL.items():
            initial.extend(ast.parse(f'_FOUNDATION_{value} = {value}').body)
            lines.append(f'_FOUNDATION_{value} = _foundation_abi.{op}({key!r})')
    else:initial=[]
    # Preserve the exact Base fast path and its retained proof requirements.
    branch=ast.If(ast.Compare(ast.Name('core_sha256',ast.Load()),[ast.NotEq()],[ast.Constant(BASE)]),
                  ast.parse('\n'.join(lines)).body,[])
    doc=bool(fn.body and isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant)
             and isinstance(fn.body[0].value.value,str))
    # Locals assigned only on XP1 would shadow global Base constants: explicitly
    # bind their original globals once before the engine branch.
    for var in bindings:
        initial.extend(ast.parse(f'{var} = globals()[{var!r}]').body)
    if name=='native_event_fa5b1159':
        initial.extend(ast.parse("PAIR_SECONDARY_VTABLE = globals()['PAIR_SECONDARY_VTABLE']").body)
    fn.body[int(doc):int(doc)]=[*initial,branch]
    ast.fix_missing_locations(tree)
    lines_source=source.splitlines(keepends=True)
    start=fn.lineno-1;end=fn.end_lineno
    # Decorators sit outside this range and remain intact.
    result=''.join(lines_source[:start])+ast.unparse(fn).removeprefix(
        '\n'.join('@'+ast.unparse(d) for d in fn.decorator_list)+'\n' if fn.decorator_list else '\0')+'\n'+''.join(lines_source[end:])
    return result

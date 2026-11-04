"""Reuse the retained native map owner with a pinned recorded-input branch."""
import ast

MODULE='civ6rl.native_xp1_performance'

def parameterize(name,raw):
    if name!=MODULE:return raw
    tree=ast.parse(raw)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PerformanceDomain')
    init=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
    if [a.arg for a in init.args.kwonlyargs]!=['root','settings']:
        raise ValueError('Retained Performance owner signature changed')
    init.args.kw_defaults[-1]=ast.Constant(None)
    init.args.kwonlyargs.append(ast.arg(arg='recorded_input'));init.args.kw_defaults.append(ast.Constant(None))
    body=init.body
    def target(n,value):
        return isinstance(n,ast.Assign) and len(n.targets)==1 and ast.unparse(n.targets[0])==value
    index=next(i for i,n in enumerate(body) if target(n,'self.settings'))
    if not target(body[index+1],'self.derived') or ast.unparse(body[index+1].value)!='derive(settings)':
        raise ValueError('Retained Performance derivation boundary changed')
    branch=ast.parse('''if recorded_input is None:
    self.settings = dict(settings)
    self.derived = derive(settings)
else:
    if settings is not None:
        raise ValueError('Recorded options cannot mix with diagnostic settings')
    from civ6_host.runtime.xp1_load_options import recorded_values
    self.derived = {'values': recorded_values(recorded_input, borrower), recorded_input.kind: True}
    self.settings = dict(recorded_input.raw_settings)
''').body[0]
    body[index:index+2]=[branch]
    # Select the source and every native map operation inside the existing
    # owner; the outer callback's core hash alone never switches an XP1 getter.
    index=next(i for i,n in enumerate(body) if target(n,'self.proof'))
    if ast.unparse(body[index].value)!='source_profile(root)':
        raise ValueError('Retained Performance source selector changed')
    body[index:index+1]=ast.parse('''from civ6_host.runtime.xp2_load_options_capability_profile import performance_select
self.proof = performance_select(borrower, root, source_profile)
''').body
    replacements={0x844460:"self.proof['contract']['constructor_rva']",
                  0x844580:"self.proof['contract']['destructor_rva']",
                  0x845e90:"self.proof['contract']['slots']['0x130']",
                  0x845600:"self.proof['contract']['slots']['0x68']",
                  0x93f590:"self.proof['contract']['map_vtable_rva']"}
    class SelectedMap(ast.NodeTransformer):
        def visit_Constant(self,node):
            if type(node.value) is int and node.value in replacements:
                return ast.copy_location(ast.parse(replacements[node.value],mode='eval').body,node)
            return node
    SelectedMap().visit(cls)
    verify=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verify_code')
    class SelectedTable(ast.NodeTransformer):
        def visit_Constant(self,node):
            if type(node.value) is int and node.value==0x93f590:
                return ast.copy_location(ast.parse("proof['contract']['map_vtable_rva']",mode='eval').body,node)
            return node
    SelectedTable().visit(verify)
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

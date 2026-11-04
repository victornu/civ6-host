"""Engine selection and common executor for existing placement/completion paths."""
import ast

MODULES = {
    'civ6rl.native_production_placement': ('verify_source', 'verify_resume_source', '_preamble',
        'catalog_source', '_selection_source', 'request_source', 'effect_source'),
    'civ6rl.native_saved_placement': ('catalog', 'selected', 'item_progress', 'progress'),
    'civ6rl.native_district_completion': ('verify_source', 'readback_source'),
    'civ6rl.native_wonder_completion': ('verify_source', 'verify_absence_source', 'readback_source'),
}
DEFAULT = '_PLACEMENT_BASE_CORE_SHA256'


def _delegate(tree):
    wanted = ast.dump(ast.parse("kind in ('production_placement', 'production_resume')", mode='eval').body)
    found = []
    class Visitor(ast.NodeTransformer):
        def visit_If(self, node):
            self.generic_visit(node)
            if ast.dump(node.test) == wanted:
                if not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                           and n.func.attr == 'selected' for n in ast.walk(node)):
                    raise ValueError('Shared placement branch no longer selects its native choice')
                found.append(node)
                node.body = ast.parse('''
from civ6_host.runtime.explicit_production_operation import apply_placement
after = apply_placement(owner, p, action, turn, current, player_id=pid)
''').body
            return node
    tree = Visitor().visit(tree)
    if len(found) != 1:
        raise ValueError('Expected one existing placement/resume executor')
    return tree


def parameterize(name, raw):
    if name == 'civ6rl.native_saved_actions':
        return ast.unparse(ast.fix_missing_locations(_delegate(ast.parse(raw))))+'\n'
    if name not in MODULES:
        return raw
    tree=ast.parse(raw)
    targets=MODULES[name]
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    if not set(targets)<=set(functions):
        raise ValueError('Shared placement extraction functions changed')
    for target in targets:
        fn=functions[target]
        if any(a.arg=='core_sha256' for a in fn.args.kwonlyargs):
            raise ValueError('Placement is already engine selected')
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
        fn.args.kw_defaults.append(ast.Name(id=DEFAULT,ctx=ast.Load()))
        for call in ast.walk(fn):
            if not isinstance(call,ast.Call):continue
            selected=(isinstance(call.func,ast.Name) and call.func.id in (*targets,'base_preamble','_selection_source'))
            selected|=(isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name)
                       and ((call.func.value.id=='placement' and call.func.attr in ('catalog_source','_selection_source'))
                            or (call.func.value.id=='reader' and call.func.attr=='readback_source')))
            if selected:
                call.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
        if target.startswith('verify_'):
            index=int(bool(fn.body and isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant)
                           and isinstance(fn.body[0].value.value,str)))
            fn.body[index:index]=ast.parse(f'''
if core_sha256 != {DEFAULT}:
    from civ6_host.runtime.xp1_production_placement_profile import verify_source as selected_source
    return selected_source(core_sha256)
''').body
        if name=='civ6rl.native_saved_placement' and target=='progress':
            found=[]
            for call in ast.walk(fn):
                if not isinstance(call,ast.Call):continue
                for kw in call.keywords:
                    if kw.arg=='source_proof_sha256':
                        if ast.unparse(kw.value)!='reader.PROOF_SHA256':
                            raise ValueError('Placement progress source receipt changed')
                        kw.value=ast.parse(f'reader.PROOF_SHA256 if core_sha256 == {DEFAULT} else selected_proof[1]',mode='eval').body
                        found.append(kw)
            if len(found)!=1:raise ValueError('Missing placement progress source receipt')
            fn.body[:0]=ast.parse(f'''
if core_sha256 != {DEFAULT}:
    from civ6_host.runtime.xp1_production_placement_profile import source_reference
    selected_proof=source_reference(core_sha256)
''').body
    index=int(bool(tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant)
                   and isinstance(tree.body[0].value.value,str)))
    while index<len(tree.body) and isinstance(tree.body[index],ast.ImportFrom) and tree.body[index].module=='__future__':index+=1
    tree.body[index:index]=ast.parse(f'from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as {DEFAULT}').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

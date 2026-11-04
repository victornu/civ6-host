"""Extend the existing empty receiver registry with a verified expansion row."""
import ast
MODULES=('civ6rl.native_deferred_empty_profile',)

def parameterize(name,raw):
    if name not in MODULES:return raw
    tree=ast.parse(raw);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_load_rows')
    if not isinstance(fn.body[-1],ast.Return) or not isinstance(fn.body[-1].value,ast.Name) or fn.body[-1].value.id!='rows':
        raise ValueError('Empty receiver registry return changed')
    if 'a0_emergencies_updated' in raw:raise ValueError('EmergenciesUpdated receiver already installed')
    fn.body[-1:-1]=ast.parse('''from civ6_host.runtime.a0_emergencies_updated import receiver_rows
extra = receiver_rows()
if set(rows) & set(extra):
    raise ValueError('Publication receiver overlaps an existing source profile')
rows.update(extra)
''').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

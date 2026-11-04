"""Delegate the existing pure queue contract after XP1 source selection."""
import ast
from pathlib import Path

TARGETS=('uint','validate_action','action_wire','validate_catalog','catalog_wire',
         'validate_all','check_heads','check_effect')


class _Portable(ast.NodeTransformer):
    def visit_Attribute(self,node):
        if (isinstance(node.value,ast.Name) and node.value.id=='production'
                and node.attr in ('_uint','_type_name','KINDS')):
            return ast.copy_location(ast.Name(id=node.attr,ctx=node.ctx),node)
        return self.generic_visit(node)


def parameterize(name,raw):
    if name!='civ6rl.native_saved_production_queue':return raw
    tree=ast.parse(raw)
    contract=ast.parse((Path(__file__).resolve().parents[1]/
        'src/civ6_host/contracts/production_queue.py').read_text(encoding='utf-8'))
    shared={n.name:n for n in contract.body if isinstance(n,ast.FunctionDef)}
    found=set()
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in TARGETS:
            if ast.dump(_Portable().visit(node),include_attributes=False)!=ast.dump(shared[node.name],include_attributes=False):
                raise ValueError('Shared production queue contract changed: '+node.name)
            found.add(node.name)
    if found!=set(TARGETS):raise ValueError('Missing shared production queue contract functions')
    tree.body=[n for n in tree.body if not (isinstance(n,ast.FunctionDef) and n.name in TARGETS)]
    tree.body.append(ast.ImportFrom(module='civ6_host.contracts.production_queue',
        names=[ast.alias(name=n) for n in TARGETS],level=0))
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

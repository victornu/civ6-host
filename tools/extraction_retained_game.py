"""Select the engine ABI without duplicating the retained native getter."""
import ast

MODULE='civ6rl.native_retained_game_getter'


def parameterize(tree):
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='read_retained_game_value')
    fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
    fn.args.kw_defaults.append(ast.Constant('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
    if ast.unparse(fn.body[1])!='verify_source_evidence()':raise ValueError('Retained getter source boundary changed')
    fn.body[1:2]=ast.parse('''
from civ6_host.runtime.retained_game_source import getter_abi
abi=getter_abi(core_sha256)
if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
    verify_source_evidence()
''').body
    class Select(ast.NodeTransformer):
        def visit_Name(self,n):
            field={'GAME_FACADE_VTABLE_RVA':'facade_vtable_rva','CACHE_OWNER_VTABLE_RVA':'owner_vtable_rva',
                   'GETTER_SLOT':'getter_slot','GETTER_RVA':'getter_rva','GETTER_CODE_SHA256':'getter_sha256'}.get(n.id)
            if field:return ast.copy_location(ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),attr=field,ctx=n.ctx),n)
            return n
        def visit_Call(self,n):
            if ast.unparse(n)=='read(target, 28)':
                n.args[1]=ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),attr='getter_length',ctx=ast.Load())
            return self.generic_visit(n)
    Select().visit(fn)
    return tree

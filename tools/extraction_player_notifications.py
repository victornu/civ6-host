"""Reuse the notification lease and getter order with explicit engine targets."""
import ast

BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MODULE='civ6rl.native_player_notifications'


def parameterize(tree):
    constants={n.targets[0].id for n in tree.body if isinstance(n,ast.Assign)
        and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)
        and n.targets[0].id.endswith(('_RVA','_SLOT'))}
    if len(constants)!=15:raise ValueError('Player notification ABI constants changed')
    tree.body.insert(next(i for i,n in enumerate(tree.body) if not isinstance(n,(ast.Expr,ast.ImportFrom))),
        ast.parse('from civ6_host.runtime.player_notification_profiles import notification_abi, verify_player_wrapper, verify_component_wrapper').body[0])
    class ABI(ast.NodeTransformer):
        def visit_Name(self,node):
            if node.id in constants:
                return ast.copy_location(ast.parse(f'abi.constants[{node.id!r}]',mode='eval').body,node)
            return node
        def visit_Call(self,node):
            node=self.generic_visit(node)
            if isinstance(node.func,ast.Name) and node.func.id in ('_native_calls','query_player_notification_values'):
                node.keywords.append(ast.keyword(arg='core_sha256',value=ast.Name(id='core_sha256',ctx=ast.Load())))
            return node
    for fn in tree.body:
        if isinstance(fn,ast.FunctionDef) and fn.name in ('_native_calls','query_player_notification_values','get_native_player_notification_values'):
            fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Constant(BASE))
            ABI().visit(fn)
            if fn.name!='get_native_player_notification_values':
                index=int(isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant) and isinstance(fn.body[0].value.value,str))
                fn.body[index:index]=ast.parse('abi=notification_abi(core_sha256)').body
            if fn.name=='query_player_notification_values':
                block=next(n for n in fn.body if isinstance(n,ast.Try))
                for target,code in (
                    ('player_release_ready = True',"if core_sha256!=BASE:\n    player_live=verify_player_wrapper(read,core_base,player,core_sha256=core_sha256)"),
                    ('component_release_ready = True',"if core_sha256!=BASE:\n    verify_component_wrapper(read,core_base,component,player_live,core_sha256=core_sha256)")):
                    index=next(i for i,n in enumerate(block.body) if ast.unparse(n)==target)+1
                    block.body[index:index]=ast.parse(code.replace('!=BASE','!='+repr(BASE))).body
    return tree

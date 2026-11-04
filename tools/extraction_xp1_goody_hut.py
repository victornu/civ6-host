"""Forward explicit engine identity into the existing authored reward adapter."""
import ast
BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MODULES={'native_host_events'}


def parameterize(name,raw):
    short=name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if short not in MODULES:return raw
    tree=ast.parse(raw)
    methods=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_dispatch_fields']
    if len(methods)!=1:raise ValueError('Reward shared dispatcher changed')
    branches=[n for n in ast.walk(methods[0]) if isinstance(n,ast.If)
              and ast.unparse(n.test)==f'kind == {0xc08fc0f9}']
    if len(branches)!=1:raise ValueError('Reward shared branch changed')
    calls=[n for n in ast.walk(branches[0]) if isinstance(n,ast.Call) and ast.unparse(n.func)=='enqueue']
    if len(calls)!=1 or calls[0].keywords:raise ValueError('Reward enqueue source seam changed')
    calls[0].keywords.append(ast.keyword(arg='core_sha256',value=ast.parse(
        f"getattr(self,'placement_core_sha256',{BASE!r})",mode='eval').body))
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

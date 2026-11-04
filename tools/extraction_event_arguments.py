"""Select the exact engine layout for the existing borrowed event-tree reader."""
import ast

MODULE='civ6rl.native_event_argument_tree'


def parameterize(tree):
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='read_event_fields')
    fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
    fn.args.kw_defaults.append(ast.Constant('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'))
    if ast.unparse(fn.body[0])!='verify_source_evidence()':
        raise ValueError('Borrowed event reader source boundary changed')
    fn.body[:1]=ast.parse('''
from civ6_host.runtime.event_argument_source import reader_abi, verify_reader_live
abi = reader_abi(core_sha256)
if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
    verify_source_evidence()
else:
    verify_reader_live(core_base, read, core_sha256=core_sha256)
''').body
    class Select(ast.NodeTransformer):
        def visit_Name(self,n):
            if n.id=='VTABLE_RVA':
                return ast.copy_location(ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),attr='vtable_rva',ctx=n.ctx),n)
            return n
    Select().visit(fn)
    return tree

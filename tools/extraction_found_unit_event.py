"""Pure extraction hook for explicit Core selection in the shared E23B query.

The LAB source remains immutable. Base stays the function default; XP1 and XP2
are only selected when their actual owner supplies the Core SHA.
"""
import ast
from collections import Counter

NAMES={'CORE_PARAMETER_CTOR','CORE_PARAMETER_DTOR','CORE_PARAMETER_LOOKUP',
       'CORE_PARAMETER_VTABLE','CORE_UNIT_A8','CORE_UNIT_B0'}
BASE_EXE_SHA256='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'


def transform(source):
    tree=ast.parse(source)
    matches=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='query_unit_parameters']
    if len(matches)!=1:raise ValueError('Expected one original found-unit query')
    fn=matches[0]
    if any(a.arg=='core_sha256' for a in fn.args.kwonlyargs):raise ValueError('Found-unit query is already parameterized')
    counts=Counter()
    class Rebind(ast.NodeTransformer):
        def visit_ImportFrom(self,node):
            if ((node.module=='native_unit_created_event' and node.level==1)
                    or node.module in ('civ6rl.native_unit_created_event','civ6_host.runtime.native.native_unit_created_event')) and [(a.name,a.asname) for a in node.names]==[('TABLES',None)]:
                counts['tables_import']+=1
                return ast.Assign(targets=[ast.Name(id='TABLES',ctx=ast.Store())],
                    value=ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),attr='tables',ctx=ast.Load()))
            return node
        def visit_Name(self,node):
            if isinstance(node.ctx,ast.Load) and node.id in NAMES:
                counts[node.id]+=1
                return ast.Subscript(value=ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),attr='constants',ctx=ast.Load()),
                    slice=ast.Constant(node.id),ctx=ast.Load())
            if isinstance(node.ctx,ast.Load) and node.id=='CORE_CODE_PINS':
                counts['code_pins']+=1
                return ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),attr='code_pins',ctx=ast.Load())
            return node
        def visit_Constant(self,node):
            if type(node.value) is int and node.value==0x7c7078:
                counts['inner_vtable']+=1
                return ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),attr='inner_vtable_rva',ctx=ast.Load())
            return node
    fn=Rebind().visit(fn)
    expected={'tables_import':1,'code_pins':1,'inner_vtable':1,
        'CORE_PARAMETER_CTOR':1,'CORE_PARAMETER_DTOR':1,'CORE_PARAMETER_LOOKUP':2,
        'CORE_PARAMETER_VTABLE':3,'CORE_UNIT_A8':2,'CORE_UNIT_B0':2}
    if dict(counts)!=expected:raise ValueError('Found-unit query source structure changed: '+repr(dict(counts)))
    fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
    fn.args.kw_defaults.append(ast.Name(id='PINNED_CORE_SHA256',ctx=ast.Load()))
    fn.body[1:1]=ast.parse('from civ6_host.runtime.found_unit_event_profiles import query_abi\nabi = query_abi(core_sha256)').body

    # The retained E23B witness pins the shared EXE callback; its embedded
    # Core is XP1 and must not be mistaken for the selected XP2 Core profile.
    verifiers=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verify_selector_source']
    if len(verifiers)!=1:raise ValueError('Expected one E23B source verifier')
    verifier=verifiers[0]
    class SharedExeOnly(ast.NodeTransformer):
        def __init__(self):self.replaced=0
        def visit_Compare(self,node):
            node=self.generic_visit(node)
            if (ast.unparse(node.left)=="source['images']" and len(node.ops)==1
                    and isinstance(node.ops[0],ast.NotEq) and len(node.comparators)==1
                    and isinstance(node.comparators[0],ast.Dict)):
                self.replaced+=1
                return ast.copy_location(ast.Compare(
                    left=ast.Subscript(value=ast.Subscript(value=ast.Name(id='source',ctx=ast.Load()),
                        slice=ast.Constant('images'),ctx=ast.Load()),
                        slice=ast.Constant('exe_sha256'),ctx=ast.Load()),
                    ops=[ast.NotEq()],comparators=[ast.Constant(BASE_EXE_SHA256)]),node)
            return node
    exe_only=SharedExeOnly();verifier=exe_only.visit(verifier)
    if exe_only.replaced!=1:raise ValueError('Expected one EXE/Core evidence comparison')
    tree.body[tree.body.index(verifiers[0])]=verifier

    # Keep the public contract helper source-selected as well, so metadata
    # cannot report Base constants when its caller explicitly asks for XP2.
    contracts=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='unit_query_contract']
    if len(contracts)!=1:raise ValueError('Expected one query contract helper')
    contract=contracts[0]
    if any(a.arg=='core_sha256' for a in contract.args.kwonlyargs):
        raise ValueError('Found-unit query contract is already parameterized')
    contract.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
    contract.args.kw_defaults.append(ast.Name(id='PINNED_CORE_SHA256',ctx=ast.Load()))
    contract.body[1:1]=ast.parse('from civ6_host.runtime.found_unit_event_profiles import query_abi\nabi = query_abi(core_sha256)').body
    class ContractRebind(ast.NodeTransformer):
        def visit_Name(self,node):
            if isinstance(node.ctx,ast.Load) and node.id in NAMES:
                return ast.copy_location(ast.Subscript(
                    value=ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),attr='constants',ctx=ast.Load()),
                    slice=ast.Constant(node.id),ctx=ast.Load()),node)
            if isinstance(node.ctx,ast.Load) and node.id=='UNIT_VTABLE_SLOTS':
                unit_table=ast.Subscript(value=ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),
                    attr='tables',ctx=ast.Load()),slice=ast.Constant('unit'),ctx=ast.Load())
                return ast.copy_location(ast.Subscript(value=unit_table,slice=ast.Constant(1),ctx=ast.Load()),node)
            if isinstance(node.ctx,ast.Load) and node.id=='CORE_CODE_PINS':
                return ast.copy_location(ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),attr='code_pins',ctx=ast.Load()),node)
            if isinstance(node.ctx,ast.Load) and node.id=='PINNED_CORE_SHA256':
                return ast.copy_location(ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),attr='core_sha256',ctx=ast.Load()),node)
            return node
        def visit_Constant(self,node):
            if type(node.value) is int and node.value==0x1807A0090:
                unit_table=ast.Subscript(value=ast.Attribute(value=ast.Name(id='abi',ctx=ast.Load()),
                    attr='tables',ctx=ast.Load()),slice=ast.Constant('unit'),ctx=ast.Load())
                rva=ast.Subscript(value=unit_table,slice=ast.Constant(0),ctx=ast.Load())
                return ast.copy_location(ast.BinOp(left=ast.Constant(0x180000000),op=ast.Add(),right=rva),node)
            return node
    contract=ContractRebind().visit(contract)
    # ContractRebind selects the constant in the function body. Keep the
    # public keyword's Base/XP1-compatible default literal at module scope;
    # resolving abi in a default expression would run before the body binds it.
    contract.args.kw_defaults[-1]=ast.Name(id='PINNED_CORE_SHA256',ctx=ast.Load())
    tree.body[tree.body.index(contracts[0])]=contract
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)+'\n'

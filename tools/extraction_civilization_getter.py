"""Staged source selection for the existing application civilization read."""
import ast

def transform(name,source):
    name=name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if name not in ('native_application_property_copy','native_event_fa5b1159'):return source
    tree=ast.parse(source)
    if name=='native_application_property_copy':
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='read_civilization_result')
        if any(a.arg=='core_sha256' for a in fn.args.kwonlyargs):raise ValueError('Civilization getter already selected')
        fn.args.kwonlyargs.append(ast.arg('core_sha256'));fn.args.kw_defaults.append(ast.Name('_BASE_CORE',ast.Load()))
        class Select(ast.NodeTransformer):
            def visit_Call(self,node):
                self.generic_visit(node)
                if isinstance(node.func,ast.Name) and node.func.id=='verify_source':
                    node.func=ast.Attribute(ast.Name('_mirror_profiles',ast.Load()),'civilization_source',ast.Load())
                    node.args=[ast.Name('core_sha256',ast.Load())]
                return node
            def visit_Constant(self,node):
                if type(node.value) is int and node.value==7626176:
                    return ast.copy_location(ast.parse("proof['getter_rva']",mode='eval').body,node)
                return node
            def visit_Name(self,node):
                if isinstance(node.ctx,ast.Load) and node.id=='_TABLE':
                    return ast.copy_location(ast.parse('abi.configuration.vtable_rva',mode='eval').body,node)
                if isinstance(node.ctx,ast.Load) and node.id=='PROOF_SHA256':
                    return ast.copy_location(ast.parse("proof['source_sha256']",mode='eval').body,node)
                return node
        Select().visit(fn)
        fn.body[1:1]=ast.parse('abi = _mirror_profiles.owner_abi(application, core_sha256)').body
    else:
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='read_player_civilization_type_id')
        if not any(a.arg=='core_sha256' for a in fn.args.kwonlyargs):raise ValueError('Apply foundation facade hook before civilization hook')
        calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and ast.unparse(n.func)=='read_civilization_result']
        if len(calls)!=1 or any(k.arg=='core_sha256' for k in calls[0].keywords):raise ValueError('Civilization provider boundary changed')
        calls[0].keywords.append(ast.keyword('core_sha256',ast.Name('core_sha256',ast.Load())))
    ast.fix_missing_locations(fn)
    lines=source.splitlines(keepends=True)
    lines[fn.lineno-1:fn.end_lineno]=[ast.unparse(fn)+'\n']
    return ''.join(lines)

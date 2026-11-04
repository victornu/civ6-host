"""Select turn ABI in the retained algorithms without enabling a session turn."""
import ast

BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
ADDRESS_MAP={4384192:'request_rva',7621504:'tree_ctor_rva',7621792:'tree_dtor_rva',
    8507296:'tree_vtable_rva',7625984:'tree_lookup_rva',7649392:'vector_ctor_rva',
    7649520:'vector_dtor_rva',8509496:'vector_vtable_rva',7652848:'vector_lookup_rva',
    7657312:'string_setter_rva',7657632:'string_storage_rva',4781120:'reason_converter_rva',
    9156608:'processor_flags_rva'}


class Addresses(ast.NodeTransformer):
    def __init__(self):self.seen=set()
    def visit_Constant(self,node):
        if type(node.value) is int and node.value in ADDRESS_MAP:
            self.seen.add(node.value)
            return ast.copy_location(ast.Attribute(ast.Name('_turn_abi',ast.Load()),ADDRESS_MAP[node.value],ast.Load()),node)
        return node


def _first(fn):
    return int(bool(fn.body and isinstance(fn.body[0],ast.Expr)
        and isinstance(fn.body[0].value,ast.Constant) and isinstance(fn.body[0].value.value,str)))


def _keyword(node,name,value):
    if any(k.arg==name for k in node.keywords):raise ValueError('Turn hook keyword already present')
    node.keywords.append(ast.keyword(name,ast.parse(value,mode='eval').body))


def _core_keyword(fn):
    if any(k.arg=='core_sha256' for k in fn.args.kwonlyargs):raise ValueError('Turn signature already profiled')
    fn.args.kwonlyargs.append(ast.arg('core_sha256'));fn.args.kw_defaults.append(ast.Constant(BASE))


def parameterize(name,raw):
    if name not in ('civ6rl.native_action_transport','civ6rl.native_forced_endturn','civ6rl.native_game_turn_complete'):
        return raw
    tree=ast.parse(raw)
    if name=='civ6rl.native_action_transport':
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeActionTransport')
        methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
        expected={
          'request_end_turn':{4384192,7621504,7621792,8507296,7625984,7649392,7649520,8509496,7652848},
          'request_unready_turn':set(), 'validate_completed_round_echo':{9156608},
          'deliver_completed_round_echo':{9156608}}
        for method,addresses in expected.items():
            fn=methods[method];i=_first(fn);guard=fn.body[i]
            if (not isinstance(guard,ast.If) or ast.unparse(guard.test)!=f'self.transport_abi.core_sha256 != {BASE!r}'
                or 'Native turn-request/echo profile is not qualified for this engine' not in ast.unparse(guard)):
                raise ValueError('Turn hook needs the prior explicit engine guard: '+method)
            fn.body[i:i+1]=ast.parse('from civ6_host.runtime.xp1_turn_profile import prepare_transport\n_turn_abi=prepare_transport(self)').body
            visitor=Addresses();visitor.visit(fn)
            if visitor.seen!=addresses:raise ValueError('Turn primitive address anchor changed: '+method)
            for n in ast.walk(fn):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):
                    if n.func.id in ('write_reason','validate_pre_update_loopback'):
                        _keyword(n,'core_sha256','_turn_abi.core_sha256')
                    elif n.func.id=='request_unready_turn':_keyword(n,'profile','_turn_abi')
                    elif n.func.id=='verify_source_evidence':
                        n.func.id='verify_parameter_source';n.args=[ast.parse('_turn_abi.core_sha256',mode='eval').body]
                if isinstance(n,ast.ImportFrom) and any(a.name=='verify_source_evidence' for a in n.names):
                    n.module='civ6_host.runtime.xp1_turn_profile';n.names=[ast.alias('verify_parameter_source')]
                if isinstance(n,ast.keyword) and n.arg=='source_guard':
                    n.value=ast.parse('_turn_abi.completion_guard_description',mode='eval').body
    elif name=='civ6rl.native_forced_endturn':
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='write_reason')
        _core_keyword(fn)
        i=_first(fn);fn.body[i:i]=ast.parse('from civ6_host.runtime.xp1_turn_profile import turn_profile,forced_body_guards\n_turn_abi=turn_profile(core_sha256)').body
        visitor=Addresses();visitor.visit(fn)
        if visitor.seen!={8509496,7657632,7652848,7657312,4781120}:raise ValueError('Forced turn ABI anchors changed')
        loops=[n for n in ast.walk(fn) if isinstance(n,ast.For) and isinstance(n.iter,ast.Name) and n.iter.id=='_BODIES']
        if len(loops)!=1:raise ValueError('Forced turn body guard changed')
        loops[0].iter=ast.parse('forced_body_guards(_turn_abi,_BODIES)',mode='eval').body
        for n in ast.walk(fn):
            if isinstance(n,ast.keyword) and n.arg in ('native_parameter_vtable_rva','native_parameter_constructor_rva'):
                attr='vector_vtable_rva' if n.arg=='native_parameter_vtable_rva' else 'vector_ctor_rva'
                n.value=ast.parse('hex(_turn_abi.'+attr+')',mode='eval').body
    else:
        functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        for method in ('verify_source_evidence','decode_archive','validate_pre_update_loopback'):
            fn=functions[method];_core_keyword(fn)
            if method=='verify_source_evidence':
                i=_first(fn);fn.body[i:i]=ast.parse(f'''if core_sha256 != {BASE!r}:
    from civ6_host.runtime.xp1_turn_profile import turn_profile
    turn_profile(core_sha256)
    return
''').body
            else:
                for n in ast.walk(fn):
                    if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('verify_source_evidence','decode_archive'):
                        _keyword(n,'core_sha256','core_sha256')
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

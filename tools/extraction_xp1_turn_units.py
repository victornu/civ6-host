"""Select XP1 facade ABI inside existing Unit/Improvement algorithms."""
import ast

BASE = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
TARGETS = {
 'native_unit_created_event':('query_native_values','native_values'),
 'native_event_6e7ef927':('_check','_api','produce_record_lease','produce_record'),
 'native_event_a625c726':('_check','_api','query_native_values',
     'query_native_values_at_position','produce_record'),
 'native_event_e5b20b82':('query_local_flag','produce_record'),
}
MODE_TARGETS = {'native_unit_created_event':TARGETS['native_unit_created_event'],
                'native_event_e5b20b82':TARGETS['native_event_e5b20b82']}

def _kw(node, name, value):
    if any(k.arg == name for k in node.keywords):
        raise ValueError('Turn Unit keyword already present: '+name)
    node.keywords.append(ast.keyword(arg=name,value=ast.parse(value,mode='eval').body))

def _arg(fn,name,value):
    if any(a.arg == name for a in (*fn.args.args,*fn.args.kwonlyargs)):
        raise ValueError('Turn Unit extraction already applied: '+name)
    fn.args.kwonlyargs.append(ast.arg(arg=name));fn.args.kw_defaults.append(ast.parse(value,mode='eval').body)

def _insert(fn, source):
    i = int(bool(fn.body and isinstance(fn.body[0],ast.Expr)
        and isinstance(fn.body[0].value,ast.Constant) and isinstance(fn.body[0].value.value,str)))
    fn.body[i:i] = ast.parse(source).body

def _dispatch(tree):
    methods=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_dispatch_fields']
    if len(methods)!=1:raise ValueError('Shared dispatch seam moved')
    expected={0xb8515a41:('query_native_values',True),0x6e7ef927:('produce_record_lease',False),
              0xa625c726:('produce_record',False),0xe5b20b82:('produce_record',True)}
    changed=[]
    for node in ast.walk(methods[0]):
        if not (isinstance(node,ast.If) and isinstance(node.test,ast.Compare)
                and ast.unparse(node.test.left)=='kind' and len(node.test.comparators)==1
                and isinstance(node.test.comparators[0],ast.Constant)):continue
        kind=node.test.comparators[0].value
        if kind not in expected:continue
        name,mode=expected[kind]
        calls=[c for c in ast.walk(node) if isinstance(c,ast.Call)
               and isinstance(c.func,ast.Name) and c.func.id==name]
        if len(calls)!=1:raise ValueError('Shared Unit dispatch call changed')
        _kw(calls[0],'core_sha256',f"getattr(self, 'turn_unit_core_sha256', {BASE!r})")
        if mode:_kw(calls[0],'candidate_backend',"getattr(self, 'turn_unit_backend', None)")
        changed.append(kind)
    if set(changed)!=set(expected) or len(changed)!=4:
        raise ValueError('Expected four native-query Unit/Improvement branches')


def parameterize(name, raw):
    short=name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if short not in TARGETS and short!='native_host_events':return raw
    tree=ast.parse(raw)
    if short=='native_host_events':
        _dispatch(tree)
        return ast.unparse(ast.fix_missing_locations(tree))+'\n'
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    if not set(TARGETS[short]) <= set(functions):raise ValueError('Turn Unit source functions moved')
    for name in TARGETS[short]:
        fn=functions[name];_arg(fn,'core_sha256',repr(BASE))
        if name in MODE_TARGETS.get(short,()):_arg(fn,'candidate_backend','None')
        for call in ast.walk(fn):
            if not isinstance(call,ast.Call):continue
            called=call.func.id if isinstance(call.func,ast.Name) else None
            if called in TARGETS[short]:
                _kw(call,'core_sha256','core_sha256')
                if called in MODE_TARGETS.get(short,()):_kw(call,'candidate_backend','candidate_backend')
            if short=='native_event_a625c726' and called in ('query_secondary_value','read_player_civilization_type_id'):
                _kw(call,'core_sha256','core_sha256')
            if short=='native_event_e5b20b82' and ast.unparse(call.func)=='shared.query_native_values':
                _kw(call,'core_sha256','core_sha256')
            if ((short=='native_unit_created_event' and ast.unparse(call.func)=='native_app_ownership.read_application_mode')
                    or (short=='native_event_e5b20b82' and called=='read_application_mode')):
                call.func=ast.parse('_turn_units.read_application_mode',mode='eval').body
                _kw(call,'core_sha256','core_sha256');_kw(call,'candidate_backend','candidate_backend')
    if short=='native_unit_created_event':
        fn=functions['query_native_values']
        for node in ast.walk(fn):
            if isinstance(node,ast.Name) and node.id=='TABLES':node.id='_turn_tables'
        _insert(fn,'_turn_tables = _turn_units.select_tables(core_sha256, TABLES)')
    if short in ('native_event_6e7ef927','native_event_a625c726'):
        fn=functions['_check']
        for node in ast.walk(fn):
            if isinstance(node,ast.Subscript) and isinstance(node.value,ast.Name) and node.value.id=='_TABLES':
                node.value=ast.parse('_turn_units.select_tables(core_sha256, _TABLES)',mode='eval').body
        fn=functions['_api'];variable='entries' if short=='native_event_6e7ef927' else 'specs'
        assigns=[(i,n) for i,n in enumerate(fn.body) if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id==variable for t in n.targets)]
        if len(assigns)!=1:raise ValueError('Expected exact source operations dictionary')
        i,_=assigns[0];fn.body[i+1:i+1]=ast.parse(f'{variable} = _turn_units.select_specs(core_sha256, {variable})').body
    if short=='native_event_6e7ef927':
        fn=functions['produce_record_lease'];changed=[]
        for node in ast.walk(fn):
            if (isinstance(node,ast.BinOp) and isinstance(node.left,ast.Name) and node.left.id=='unit'
                    and isinstance(node.op,ast.Add) and isinstance(node.right,ast.Constant) and node.right.value==16):
                node.right=ast.parse('_turn_units.unit_live_offset(core_sha256)',mode='eval').body;changed.append(node)
        if len(changed)!=1:raise ValueError('Unit live-pointer layout seam changed')
    if short=='native_event_e5b20b82':
        fn=functions['query_local_flag']
        for i,node in enumerate(fn.body):
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='specs' for t in node.targets):
                fn.body[i+1:i+1]=ast.parse('specs = _turn_units.select_specs(core_sha256, specs)').body;break
        else:raise ValueError('Improvement local-query ABI seam changed')
        _insert(fn,"_turn_tables = _turn_units.select_tables(core_sha256, {'outer': (7987232, ((144, 4382432),)), 'game': (7990488, ((8, 4409168), (296, 4410112)))})")
        changed=[]
        for node in ast.walk(fn):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='check':
                key={'context':'outer','game':'game'}.get(ast.unparse(node.args[0]))
                if key is None:raise ValueError('Unexpected local-query interface')
                node.args[1:]=[ast.Starred(ast.parse(f'_turn_tables[{key!r}]',mode='eval').body,ast.Load())];changed.append(key)
        if set(changed)!={'outer','game'}:raise ValueError('Missing local-query interface guard')
    index=int(bool(tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant)))
    while index<len(tree.body) and isinstance(tree.body[index],ast.ImportFrom) and tree.body[index].module=='__future__':index+=1
    tree.body[index:index]=ast.parse('from civ6_host.runtime import turn_unit_event_profile as _turn_units').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

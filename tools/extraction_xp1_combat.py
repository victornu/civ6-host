"""Select XP1 ABI in retained combat producers without duplicating their bodies."""
import ast
BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MODULES={'native_combat_argument_snapshot','native_event_8256dbe1',
         'native_combat_owner_predicate','native_unit_promotion_query','native_host_events'}


def expr(text):return ast.parse(text,mode='eval').body
def statements(text):return ast.parse(text).body
def function(tree,name):
    rows=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(rows)!=1:raise ValueError('Combat extraction function changed: '+name)
    return rows[0]
def engine(fn):
    if any(a.arg=='core_sha256' for a in (*fn.args.args,*fn.args.kwonlyargs)):
        raise ValueError('Combat engine parameter already exists')
    fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Constant(BASE))
def prepend(fn,text):
    at=int(bool(fn.body and isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant) and isinstance(fn.body[0].value.value,str)))
    fn.body[at:at]=statements(text)
def forward(fn,target,value='core_sha256',compat=False):
    rows=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and ast.unparse(n.func)==target]
    if not rows:raise ValueError('Combat call seam absent: '+target)
    for call in rows:
        if any(k.arg=='core_sha256' for k in call.keywords):raise ValueError('Combat engine forwarded twice')
        call.keywords.append(ast.keyword(arg=None if compat else 'core_sha256',value=expr(
            f"({{'core_sha256':{value}}} if {value}!={BASE!r} else {{}})" if compat else value)))
class ReplaceNames(ast.NodeTransformer):
    def __init__(self,mapping):self.mapping=mapping
    def visit_Name(self,node):
        if isinstance(node.ctx,ast.Load) and node.id in self.mapping:return ast.copy_location(expr(self.mapping[node.id]),node)
        return node
class ReplaceValues(ast.NodeTransformer):
    def __init__(self,mapping):self.mapping=mapping
    def visit_Constant(self,node):
        if type(node.value) is int and node.value in self.mapping:return ast.copy_location(expr(self.mapping[node.value]),node)
        return node


def parameterize(name,raw):
    short=name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if short not in MODULES:return raw
    tree=ast.parse(raw)
    insert=next((i for i,n in enumerate(tree.body) if not isinstance(n,(ast.Import,ast.ImportFrom)) and not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))),len(tree.body))
    tree.body[insert:insert]=statements('from civ6_host.runtime import xp1_combat_profile as _combat_source')
    if short=='native_combat_argument_snapshot':
        fn=function(tree,'capture_borrowed_children');engine(fn)
        prepend(fn,'_combat_source.ensure_source(core_sha256)')
        forward(fn,'read_event_fields')
        ReplaceNames({'PROOF_SHA256':'_combat_source.source_sha(core_sha256, PROOF_SHA256)'}).visit(fn)
    elif short=='native_event_8256dbe1':
        fn=function(tree,'decode_fields');engine(fn);forward(fn,'capture_borrowed_children')
        loops=[n for n in fn.body if isinstance(n,ast.For)
               and ast.unparse(n.target)=='child' and ast.unparse(n.iter)=="capture['children'].values()"]
        if len(loops)!=1 or len(loops[0].body)!=3:
            raise ValueError('Combat child validation block changed')
        block=loops[0].body
        guard,scalars=block[1:]
        if (not isinstance(guard,ast.If) or not isinstance(guard.test,ast.Compare)
                or ast.unparse(guard.test.left)!='set(values)'
                or len(guard.test.comparators)!=1
                or not isinstance(guard.test.comparators[0],ast.BinOp)
                or ast.unparse(guard.test.comparators[0].left)!='CHILD_SCALAR_KEYS'
                or not isinstance(guard.test.comparators[0].right,ast.Set)
                or {n.value for n in guard.test.comparators[0].right.elts} != {1472654640,2515717998}
                or not isinstance(scalars,ast.For) or ast.unparse(scalars.target)!='key'
                or ast.unparse(scalars.iter)!='CHILD_SCALAR_KEYS'
                or len(scalars.body)!=1 or ast.unparse(scalars.body[0])!='decode_scalar(values[key], 2)'):
            raise ValueError('Combat retained fourteen-field scalar validation changed')
        block[1:]=statements('_combat_source.validate_child_fields(core_sha256,values,CHILD_SCALAR_KEYS)')
    elif short=='native_combat_owner_predicate':
        fn=function(tree,'query_owner');engine(fn)
        guard=fn.body[1]
        if not isinstance(guard,ast.If) or 'TARGET_SHA256' not in ast.unparse(guard.test):raise ValueError('Combat predicate retained source guard changed')
        guard.test=ast.BoolOp(op=ast.And(),values=[expr(f'core_sha256=={BASE!r}'),guard.test])
        ReplaceNames(dict(GAME_VTABLE='_game_table',TARGET='_target',STATE_GETTER='_state_getter',STATE_GLOBAL='_state_global')).visit(fn)
        fn.body[1:1]=statements('_game_table,_target,_state_getter,_state_global,proof=_combat_source.predicate_selection(core_sha256,(GAME_VTABLE,TARGET,STATE_GETTER,STATE_GLOBAL),proof)')
    elif short=='native_unit_promotion_query':
        fragments=function(tree,'_method_fragments');engine(fragments)
        ReplaceNames({'METHODS':'_layout.methods'}).visit(fragments)
        fragments.body[2:2]=statements('proof=_combat_source.promotion_proof(core_sha256,proof)')
        prepend(fragments,'_layout=_combat_source.promotion_layout(core_sha256,METHODS,SLOTS)')
        live=function(tree,'verify_live_methods');engine(live);forward(live,'_method_fragments')
        ReplaceNames({'SLOTS':'_layout.slots'}).visit(live)
        prepend(live,'_layout=_combat_source.promotion_layout(core_sha256,METHODS,SLOTS)')
        query=function(tree,'query_and_emit_promotion');engine(query);forward(query,'verify_live_methods')
        ReplaceNames({'METHODS':'_layout.methods','MAP_VTABLE':'_layout.map_table'}).visit(query)
        ReplaceValues({7987232:'_layout.outer_table',7995816:'_layout.service_table'}).visit(query)
        prepend(query,'_layout=_combat_source.promotion_layout(core_sha256,METHODS,SLOTS)')
    else:
        for name,targets in (('_enqueue_combat',('NativeCombatMapOwner','CombatMapRegistry','decode_fields')),
                             ('_enqueue_experience',('query_and_emit_promotion',))):
            fn=function(tree,name)
            for target in targets:forward(fn,target,'_core_sha256',compat=True)
            ReplaceNames({'PROOF_SHA256':'_combat_source.source_sha(_core_sha256,PROOF_SHA256)'}).visit(fn)
            prepend(fn,f"_core_sha256=getattr(self,'combat_core_sha256',{BASE!r})")
            if name=='_enqueue_combat':
                receipts=[n for n in ast.walk(fn) if isinstance(n,ast.Call)
                          and ast.unparse(n.func)=='self.emit' and n.args
                          and isinstance(n.args[0],ast.Constant)
                          and n.args[0].value=='native_combat_record_enqueued']
                if len(receipts)!=1 or any(k.arg is None for k in receipts[0].keywords):
                    raise ValueError('Combat administrative receipt shape changed')
                receipts[0].keywords.append(ast.keyword(arg=None,
                    value=expr('_combat_source.administrative_snapshot_policy(_core_sha256)')))
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

"""Share the existing event dispatcher; per-engine admission stays external."""
import ast


def share(tree):
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeDeferredHostEvents')
    names={'_dispatch_fields','_require_no_f391_reentry','_finish_counter_neutral_event',
           '_enqueue_city_command_started','_enqueue_unit_embarked_state_changed'}
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    if {n.name for n in methods}!=names:raise ValueError('Shared A0 dispatcher boundary changed')
    shared=ast.ClassDef(name='SharedHostEventDispatch',bases=[],keywords=[],body=methods,decorator_list=[])
    dispatch=next(n for n in methods if n.name=='_dispatch_fields')
    calls=[n for n in ast.walk(dispatch) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
        and n.func.id=='query_player_notification_values']
    if len(calls)!=1:raise ValueError('Player notification lease boundary changed')
    call=calls[0]
    if ast.unparse(call)!='query_player_notification_values(self.base, self.context, player)':
        raise ValueError('Player notification lease arguments changed')
    call.func=ast.parse('self._query_player_notification_values',mode='eval').body
    call.args=call.args[2:]
    shared.body+=ast.parse('''
def _query_player_notification_values(self,player):
    from civ6_host.runtime.native.native_player_notifications import query_player_notification_values
    return query_player_notification_values(self.base,self.context,player)
''').body
    cls.body=[n for n in cls.body if n not in methods]
    cls.bases.append(ast.Name(id=shared.name,ctx=ast.Load()))
    tree.body.insert(tree.body.index(cls),shared)
    return tree

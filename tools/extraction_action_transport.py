"""Select native transport layout once; preserve the existing command algorithm.

Only engine addresses in reviewed primitive methods are parameterized. Turn
requests keep their Base contracts until another engine's contract is explicit.
"""
import ast

BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
ADDRESSES={
    'inspect_processor_flags':{9156608:'processor_flags_rva'},
    'update_game_once':{4382432:'game_getter_rva',4409168:'game_release_rva',
                        7990488:'game_vtable_rva',4411488:'game_update_rva'},
    'capture':{8511040:'archive_vtable_rva',7670032:'archive_size_rva'},
    'deliver_one':{9156296:'receive_queue_rva',7669584:'view_ctor_rva',
                    7669776:'view_dtor_rva',8510944:'view_vtable_rva',
                    4384080:'receive_rva',4383952:'drain_rva',9156345:'optional_queue_flag_rva'},
}

class Addresses(ast.NodeTransformer):
    def __init__(self,mapping):self.mapping=mapping;self.seen=set()
    def visit_Constant(self,node):
        if type(node.value) is int and node.value in self.mapping:
            self.seen.add(node.value)
            return ast.copy_location(ast.parse('self.transport_abi.'+self.mapping[node.value],mode='eval').body,node)
        return node

def parameterize(name,raw):
    if name=='civ6rl.native_found_city_event':
        from extraction_found_unit_event import transform
        return transform(raw)
    if name=='tools.run_official_postload909':
        anchor='    if candidate:\n        from civ6_host.runtime.xp1_saved_load_composition import compose_saved_load_services\n'
        if raw.count(anchor)!=1:raise ValueError('XP1 saved owner setup anchor changed')
        return raw.replace(anchor,'''    if candidate:
        from civ6_host.runtime.captured_saved_load import configure_requested
        configure_requested(backend, closure)
        from civ6_host.runtime.xp1_saved_load_composition import compose_saved_load_services
''')
    if name=='civ6rl.native_player_view':
        anchor='            target_rva = validate_publisher(self, publication_owner)'
        if raw.count(anchor)!=1:raise ValueError('XP1 native publisher anchor changed')
        return raw.replace(anchor,'''            if publication_owner is None:
                publication_owner = getattr(self, '_xp1_continuation', None)
            target_rva = validate_publisher(self, publication_owner)''')
    if name!='civ6rl.native_action_transport':return raw
    tree=ast.parse(raw)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeActionTransport')
    methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
    fn=methods['__init__']
    if fn.args.kwonlyargs:raise ValueError('Native transport constructor signature changed')
    fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'));fn.args.kw_defaults.append(ast.Constant(BASE))
    # Source verification precedes binding host+70; the rest of Base setup stays
    # unchanged. Read callbacks are initialized immediately before this point.
    where=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign)
               and any(isinstance(t,ast.Attribute) and t.attr=='pending' for t in n.targets))
    fn.body[where:where]=ast.parse('''from civ6_host.runtime.action_transport_profiles import transport_profile
self.transport_abi=transport_profile(core_sha256,core,context,self.read)
''').body
    for method,mapping in ADDRESSES.items():
        visitor=Addresses(mapping);visitor.visit(methods[method])
        if visitor.seen!=set(mapping):raise ValueError('Action primitive address anchor changed: '+method)
    for method in ('request_end_turn','request_unready_turn','validate_completed_round_echo','deliver_completed_round_echo'):
        fn=methods[method]
        at=int(bool(fn.body and isinstance(fn.body[0],ast.Expr) and isinstance(fn.body[0].value,ast.Constant)
                    and isinstance(fn.body[0].value.value,str)))
        fn.body[at:at]=ast.parse(f'''if self.transport_abi.core_sha256 != {BASE!r}:
    raise ValueError('Native turn-request/echo profile is not qualified for this engine')
''').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

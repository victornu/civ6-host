"""Add the engine selector at precisely the shared foundation call sites.

This is an extraction hook, not a second dispatcher. All Base branches and
algorithms remain byte-for-byte unchanged except these keyword insertions.
"""
import ast

BASE = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
SELECTOR = "getattr(self, 'foundation_core_sha256', '" + BASE + "')"
BRANCHES = {
    0x878CD252: ('native_feature_visibility_event', ('query_plot_word',)),
    0x195088C7: ('native_event_195088c7', ('query_plot_word',)),
    0xF4FE1B62: ('native_event_f4fe1b62', ('query_plot_value_lease',)),
    0x359703A2: ('native_event_359703a2', ('query_plot_words',)),
    0x5D0F4014: ('native_event_5d0f4014', ('query_descriptor',)),
    0x9AEA8529: ('native_event_9aea8529', ('query_plot_word', 'encode_scoped_record')),
    0xFA5B1159: ('native_event_fa5b1159', ('query_callback_values',)),
    0x10419F1F: ('native_event_10419f1f', ('produce_record',)),
    0x2B1BA0F8: ('native_event_2b1ba0f8', ('produce_record',)),
    0xC3183902: ('native_event_c3183902', ('produce_record_lease',)),
    0x28D6EBBE: ('native_event_28d6ebbe', ('produce_record_lease',)),
    0x07C83DAE: ('native_event_07c83dae', ('produce_record_lease',)),
    0x037A1BEE: ('native_event_037a1bee', ('produce_record_lease',)),
    0xE66012A7: ('native_event_e66012a7', ('produce_records',)),
    0x33D8725A: ('native_event_33d8725a', ('encode_record',)),
    0x827289E6: ('native_event_827289e6', ('encode_scoped_record',)),
    0x1D355E83: ('native_event_1d355e83', ('encode_record',)),
    0xC1300EE7: ('native_unit_visibility_event', ('encode_scoped_record',)),
    # No engine query in its qualified D6!=3 codec. Preserve the branch intact.
    0x3182BC8E: ('native_event_3182bc8e', ()),
}
SCOPES = {
    'kind in (869823066, 685173694) and (self.host_notification_counter != 0 or self.host_metadata_counter != 0)':
        'native_found_city_notification_scope',
    'kind == 58334190 and (self.host_notification_counter or self.host_metadata_counter)':
        'native_building_visibility_scope',
    'kind == 490036867 and (self.host_notification_counter or self.host_metadata_counter)':
        'native_city_value_notification_scope',
}


def _one(items, message):
    values=list(items)
    if len(values)!=1:raise ValueError(message)
    return values[0]


def _function(tree):
    cls=_one((n for n in tree.body if isinstance(n,ast.ClassDef)
              and n.name=='SharedHostEventDispatch'), 'Shared dispatcher class changed')
    return _one((n for n in cls.body if isinstance(n,ast.FunctionDef)
                 and n.name=='_dispatch_fields'), 'Shared dispatcher method changed')


def anchors(source):
    """Return source call nodes only after exact branch/import membership checks."""
    fn=_function(ast.parse(source))
    conditions=[n for n in fn.body if isinstance(n,ast.If)]
    result=[]
    for kind,(module,names) in BRANCHES.items():
        expected=ast.dump(ast.parse(f'kind == {kind}', mode='eval').body)
        branch=_one((n for n in conditions if ast.dump(n.test)==expected),
                    'Foundation branch moved/duplicated: '+hex(kind))
        if not names:
            # Verify the unchanged pure codec still belongs to this source branch.
            _bound_call(branch,module,'encode_record')
        for name in names:
            result.append((hex(kind), module, name, _bound_call(branch,module,name)))
    for condition,module in SCOPES.items():
        expected=ast.dump(ast.parse(condition,mode='eval').body)
        branch=_one((n for n in conditions if ast.dump(n.test)==expected),
                    'Foundation scope condition changed: '+module)
        result.append(('scope:'+module,module,'dispatch_scoped',
                       _bound_call(branch,module,'dispatch_scoped')))
    if len(result)!=22 or len({(n.lineno,n.col_offset) for *_,n in result})!=22:
        raise ValueError('Foundation dispatcher must have exactly 22 distinct call anchors')
    return result


def _bound_call(branch,module,name):
    binding=_one((n for n in ast.walk(branch) if isinstance(n,ast.ImportFrom)
        and n.module=='civ6_host.runtime.native.'+module
        and any(a.name==name and a.asname is None for a in n.names)),
        'Foundation imported callable differs: '+module+'.'+name)
    # A second local import of the same callable name would make attribution
    # ambiguous even if the expected module were also present.
    imports=[n for n in ast.walk(branch) if isinstance(n,ast.ImportFrom)
             and any((a.asname or a.name)==name for a in n.names)]
    if imports!=[binding]:raise ValueError('Foundation callable shadowed: '+name)
    call=_one((n for n in ast.walk(branch) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Name) and n.func.id==name),
              'Foundation call moved/duplicated: '+module+'.'+name)
    if any(k.arg=='core_sha256' for k in call.keywords):
        raise ValueError('Foundation dispatch hook already applied')
    return call


def transform(module_name,source):
    name=module_name.rsplit('.',1)[-1]
    if module_name.endswith('.py'):
        name=module_name.replace('\\','/').rsplit('/',1)[-1][:-3]
    if name!='native_host_events':return source
    found=anchors(source)
    lines=source.splitlines(keepends=True)
    starts=[];total=0
    for line in lines:starts.append(total);total+=len(line)
    edits=[]
    for _,_,_,call in found:
        # AST columns use UTF-8 byte offsets; preserve all surrounding source.
        prefix=lines[call.end_lineno-1].encode('utf-8')[:call.end_col_offset].decode('utf-8')
        end=starts[call.end_lineno-1]+len(prefix)
        if source[end-1]!=')':raise ValueError('Call closing parenthesis changed')
        separator=' ' if source[:end-1].rstrip().endswith(',') else ', '
        edits.append((end-1,separator+'core_sha256='+SELECTOR))
    for offset,text in sorted(edits,reverse=True):source=source[:offset]+text+source[offset:]
    return source


def report(source):
    return [dict(branch=branch,module=module,function=name,line=call.lineno)
            for branch,module,name,call in anchors(source)]

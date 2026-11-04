"""Add one explicit record-profile selector and lazy receiver resolution."""
import ast


def transform(module_name,source):
    name=module_name.rsplit('.',1)[-1]
    if module_name.endswith('.py'):
        name=module_name.replace('\\','/').rsplit('/',1)[-1][:-3]
    if name not in ('native_event_8d005711','native_deferred_empty_profile'):return source
    tree=ast.parse(source)
    if name=='native_event_8d005711':
        fn=_function(tree,'encode_record')
        if any(a.arg=='record_profile' for a in fn.args.kwonlyargs):
            raise ValueError('City scalar codec hook already applied')
        fn.args.kwonlyargs.append(ast.arg(arg='record_profile'));fn.args.kw_defaults.append(ast.Constant(None))
        occurrences=[n for n in ast.walk(fn) if isinstance(n,ast.Name) and n.id=='RECORD_TYPE']
        if len(occurrences)!=1:raise ValueError('Expected one shared codec record-type write')
        occurrences[0].id='_selected_record_type'
        insert=ast.parse('''_selected_record_type = RECORD_TYPE
if record_profile is not None:
    from civ6_host.runtime.city_scalar_event_profiles import require_record_profile
    _selected_record_type = require_record_profile(record_profile).record_type
''').body
        index=int(bool(fn.body and isinstance(fn.body[0],ast.Expr)
                       and isinstance(fn.body[0].value,ast.Constant)
                       and isinstance(fn.body[0].value.value,str)))
        fn.body[index:index]=insert
        return _replace(source,fn)
    if any(isinstance(n,ast.FunctionDef) and n.name=='resolve_empty_receiver_row' for n in tree.body):
        raise ValueError('City scalar receiver hook already applied')
    fn=_function(tree,'validate_empty_profile_record')
    calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call)
           and ast.unparse(n)=='_ROWS.get(record_type)']
    if len(calls)!=1:raise ValueError('Expected one empty receiver row lookup')
    calls[0].func=ast.Name(id='resolve_empty_receiver_row',ctx=ast.Load())
    helper='''def resolve_empty_receiver_row(record_type):
    row = _ROWS.get(record_type)
    if row is None and type(record_type) is int and record_type in (0xf1, 0xf2, 0xf3):
        from civ6_host.runtime.city_scalar_event_profiles import receiver_row
        return receiver_row(record_type)
    return row

'''
    updated=_replace(source,fn)
    lines=updated.splitlines(keepends=True)
    lines[fn.lineno-1:fn.lineno-1]=[helper]
    return ''.join(lines)


def _function(tree,name):
    rows=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(rows)!=1:raise ValueError('Expected one shared function: '+name)
    return rows[0]


def _replace(source,fn):
    ast.fix_missing_locations(fn)
    lines=source.splitlines(keepends=True)
    lines[fn.lineno-1:fn.end_lineno]=[ast.unparse(fn)+'\n']
    return ''.join(lines)

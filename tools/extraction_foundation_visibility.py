"""Propagate explicit engine identity without changing shared codec algorithms.

Apply alongside the facade hook; that hook alone owns query_optional_position.
No installed writes and no whole-module replacement.
"""
import ast

BASE = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
ROUTES = {
    'native_feature_visibility_event': {'query_plot_word': {'_query_plot_snapshot_word'}},
    'native_event_195088c7': {'query_plot_word': {'_query_plot_snapshot_word'}},
    'native_event_827289e6': {
        'encode_record': {'encode_scoped_record'},
        'encode_scoped_record': {'query_optional_position'}},
    'native_event_33d8725a': {'encode_record': {'query_optional_position'}},
    'native_event_1d355e83': {'encode_record': {'query_optional_position'}},
    'native_unit_visibility_event': {
        'encode_record': {'query_optional_position'},
        'encode_scoped_record': {'encode_record'}},
    'native_found_city_notification_scope': {
        '_position_record': {'encode_record'},
        'dispatch_scoped': {'_position_record', 'produce_record_lease'}},
    'native_city_value_notification_scope': {
        'encode_scoped_record': {'event.encode_record'},
        'dispatch_scoped': {'encode_scoped_record'}},
}


def transform(module_name, source):
    name = module_name.rsplit('.', 1)[-1].removesuffix('.py')
    # The extraction caller may supply a stem or a bare filename.
    if module_name.endswith('.py'):
        name = module_name.replace('\\', '/').rsplit('/', 1)[-1][:-3]
    if name not in ROUTES:
        return source
    tree = ast.parse(source)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    changes = []
    for function_name, targets in ROUTES[name].items():
        if function_name not in functions:
            raise ValueError('Shared visibility function was moved: ' + function_name)
        fn = functions[function_name]
        if any(a.arg == 'core_sha256' for a in (*fn.args.args, *fn.args.kwonlyargs)):
            raise ValueError('Visibility hook already applied: ' + function_name)
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
        fn.args.kw_defaults.append(ast.Constant(BASE))
        seen = {target: 0 for target in targets}
        for call in (n for n in ast.walk(fn) if isinstance(n, ast.Call)):
            target = ast.unparse(call.func)
            if target not in targets:
                continue
            if any(kw.arg == 'core_sha256' for kw in call.keywords):
                raise ValueError('Unexpected preexisting visibility engine forwarding')
            call.keywords.append(ast.keyword(arg='core_sha256',
                                            value=ast.Name(id='core_sha256', ctx=ast.Load())))
            seen[target] += 1
        if any(count != 1 for count in seen.values()):
            raise ValueError('Shared visibility call sites changed: ' + str(seen))
        ast.fix_missing_locations(fn)
        # Keep decorators in the unchanged prefix, including @contextmanager.
        decorators = fn.decorator_list
        fn.decorator_list = []
        changes.append((fn.lineno - 1, fn.end_lineno, ast.unparse(fn) + '\n'))
        fn.decorator_list = decorators
    lines = source.splitlines(keepends=True)
    for start, end, replacement in sorted(changes, reverse=True):
        lines[start:end] = [replacement]
    return ''.join(lines)

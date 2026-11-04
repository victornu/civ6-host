"""Opt-in closed-prefix continuation of the existing stationary capture client."""
import ast


def parameterize(tree):
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    expected = ('_response_file_provenance', 'preflight', 'capture', 'main')
    if any(name not in functions for name in expected):
        raise ValueError('Capture continuation function boundaries changed')

    def keyword(fn, name):
        if any(a.arg == name for a in fn.args.kwonlyargs):
            raise ValueError('Capture continuation keyword already present')
        fn.args.kwonlyargs.append(ast.arg(arg=name))
        fn.args.kw_defaults.append(ast.Constant(None))

    provenance = functions['_response_file_provenance']
    keyword(provenance, 'predecessor')
    if not isinstance(provenance.body[-1], ast.Return):
        raise ValueError('Capture provenance return changed')
    original = provenance.body[-1].value
    provenance.body[-1:] = [ast.Assign(targets=[ast.Name(id='result', ctx=ast.Store())], value=original)] + ast.parse('''
if predecessor is not None:
    from civ6_host.runtime.capture_response_continuation import validate_predecessor
    if type(predecessor) is not dict:
        predecessor = writer.reference(Path(predecessor).resolve(strict=True))
    continued = validate_predecessor(predecessor, installation, exact_directory=False)
    require(continued['process'] == process['identity'], 'Continuation process identity differs')
    require(continued['prepared'] == checked['prepared'], 'Continuation writer identity differs')
    result['predecessor'] = dict(predecessor)
    result['predecessor_dependencies'] = [dict(predecessor), continued['prefix_snapshot'],
                                        *[row['response'] for row in continued['receipts']]]
    for item in result['predecessor_dependencies']:
        observed = _file(Path(item['path']), deadline, 64 * 1024 * 1024)
        require({key: observed[key] for key in ('path', 'bytes', 'sha256')} == item,
                'Capture predecessor dependency changed')
return result
''').body

    for name in ('preflight', 'capture'):
        fn = functions[name]
        keyword(fn, 'response_file_predecessor')
        fn.body[1:1] = ast.parse('''
require(response_file_predecessor is None or response_file_installation is not None,
        'Capture continuation requires its explicit writer installation')
''').body
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == '_response_file_provenance']
        if len(calls) != 1:
            raise ValueError('Capture provenance call boundary changed: ' + name)
        calls[0].keywords.append(ast.keyword(arg='predecessor', value=ast.Name(id='response_file_predecessor', ctx=ast.Load())))

    capture = functions['capture']
    calls = [n for n in ast.walk(capture) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == 'preflight']
    if len(calls) != 1:
        raise ValueError('Capture preflight forwarding boundary changed')
    calls[0].keywords.append(ast.keyword(arg='response_file_predecessor', value=ast.Name(id='response_file_predecessor', ctx=ast.Load())))

    selected = []
    for node in ast.walk(capture):
        if not isinstance(node, ast.If):
            continue
        for index, statement in enumerate(node.body):
            if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == 'factory'
                    and isinstance(statement.value, ast.Name) and statement.value.id == 'ResponseFileClient'):
                selected.append((node, index))
    if len(selected) != 1:
        raise ValueError('Capture direct-client factory boundary changed')
    owner, index = selected[0]
    owner.body[index + 1:index + 1] = ast.parse('''
if response.get('predecessor') is not None:
    from civ6_host.runtime.capture_response_continuation import ContinuedResponseFileClient
    factory = ContinuedResponseFileClient
    client_options['predecessor'] = response['predecessor']
''').body

    main = functions['main']
    options = [i for i, n in enumerate(main.body) if isinstance(n, ast.Expr)
               and isinstance(n.value, ast.Call) and n.value.args
               and isinstance(n.value.args[0], ast.Constant)
               and n.value.args[0].value == '--response-file-installation']
    if len(options) != 1:
        raise ValueError('Capture CLI writer option boundary changed')
    main.body[options[0] + 1:options[0] + 1] = ast.parse('''
parser.add_argument('--response-file-predecessor', type=Path,
    help='Explicit authenticated closed response prefix; no command replay or automatic fallback')
''').body
    common = [n for n in ast.walk(main) if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'common' for t in n.targets)]
    if len(common) != 1 or not isinstance(common[0].value, ast.Call):
        raise ValueError('Capture CLI common options boundary changed')
    common[0].value.keywords.append(ast.keyword(arg='response_file_predecessor', value=ast.Attribute(
        value=ast.Name(id='args', ctx=ast.Load()), attr='response_file_predecessor', ctx=ast.Load())))
    return tree


def parameterize_consumer(tree):
    """Keep exact continuation evidence in the existing saved-input reader."""
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_response_transport']
    if len(matches) != 1:
        raise ValueError('Saved-input response transport boundary changed')
    fn = matches[0]
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == '_response_file_provenance']
    if len(calls) != 1:
        raise ValueError('Saved-input capture provenance call changed')
    fn.body[1:1] = ast.parse("continuation_options = {}").body
    # Populate only after the existing absent-transport and equality guards.
    assignments = [i for i, n in enumerate(fn.body) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'verified' for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError('Saved-input provenance verification assignment changed')
    fn.body[assignments[0]:assignments[0]] = ast.parse('''
if current.get('predecessor') is not None:
    continuation_options['predecessor'] = current['predecessor']
''').body
    calls[0].keywords.append(ast.keyword(arg=None, value=ast.Name(id='continuation_options', ctx=ast.Load())))
    fn.body.extend(ast.parse('''
if current.get('predecessor') is not None:
    for item in current['predecessor_dependencies']:
        _file(item, dependencies, workspace=False, maximum=64 * 1024 * 1024)
''').body)
    return tree

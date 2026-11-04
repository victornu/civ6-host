"""Opt-in source-pinned script paths for the existing capture/provider APIs."""
import ast

MODULES = ('tools.capture_phase1_bundle994', 'civ6rl.native_gameplay_source_capture')


def _functions(tree, names):
    found = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    if any(name not in found for name in names):
        raise ValueError('Capture script-path function boundary changed')
    return found


def _keywords(fn):
    for name in ('script_path_context', 'script_path_cwd_reader'):
        if any(arg.arg == name for arg in fn.args.kwonlyargs):
            raise ValueError('Capture script-path option already present')
        fn.args.kwonlyargs.append(ast.arg(arg=name))
        fn.args.kw_defaults.append(ast.Constant(None))


def _location(owner, predicate):
    matches = []
    for node in ast.walk(owner):
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                matches.extend((value, i) for i, child in enumerate(value)
                               if isinstance(child, ast.stmt) and predicate(child))
    if len(matches) != 1:
        raise ValueError('Capture script-path statement seam changed')
    return matches[0]


def _assignment(node, name):
    return isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name


_HELPERS = '''
def _load_script_path_context(value, reader=None, *, live=False, process=None):
    if value is None:
        if reader is not None:
            raise ValueError('A script CWD observer requires an explicit script-path context')
        return None, None
    if (type(value) is not dict or set(value)!={'witness','process'}
            or type(value['witness']) is not dict or set(value['witness'])!={'path','bytes','sha256'}
            or type(value['process']) is not dict or set(value['process'])!={'pid','creation_filetime','image_path'}):
        raise ValueError('Script paths require an explicit pinned witness and exact process identity')
    if process is not None and value['process']!=process:
        raise ValueError('Script-path context differs from the actual capture process')
    from civ6_host.runtime import capture_script_paths as paths
    if live:
        if reader is None:
            reader=paths.observe_process_cwd
        context=paths.load_context(value['witness'],value['process'],cwd_reader=reader)
    else:
        context=paths.validate_context(value['witness'],value['process'])
    return context,reader

def _script_path_provenance(value, context):
    dependencies=[dict(value['witness'])]
    dependencies.extend(dict(path=path,bytes=size,sha256=sha) for path,size,sha in context.proof_files)
    dependencies.extend(dict(path=source.resolved_path,bytes=source.bytes,sha256=source.sha256)
                        for source in context.source_files)
    return dict(context=dict(witness=dict(value['witness']),process=dict(value['process'])),
        witness_sha256=context.witness_sha256,cwd=context.cwd,
        selected_order=list(context.selected_order),dependencies=dependencies,
        disk_bytes_only=True,execution_proven=False,load_admitted=False)

def _validate_script_path_roots(context,roots):
    if context is None:
        return
    if not roots:
        raise ValueError('Relative selected scripts require explicit approved source roots')
    if len(context.selected_order)>MAX_SELECTED_SCRIPTS:
        raise ValueError('Selected script context exceeds the existing selection bound')
    unique={}
    for source in context.source_files:
        candidate=Path(source.resolved_path)
        _reject_reparse_components(candidate)
        canonical=candidate.resolve(strict=True)
        if (not candidate.is_absolute() or '..' in candidate.parts
                or candidate.suffix.casefold()!='.lua' or canonical!=candidate
                or not 0<=source.bytes<=MAX_FILE_BYTES
                or not any(canonical.is_relative_to(root) for root in roots)):
            raise ValueError('Mapped selected script is not canonical beneath approved roots')
        unique[source.sha256]=source.bytes
    if sum(unique.values())>MAX_TOTAL_BYTES:
        raise ValueError('Selected script context exceeds the existing total byte bound')

def _selected_script_path(name, context, roots, reader):
    from civ6_host.runtime import capture_script_paths as paths
    source=context.source_by_selected.get(name)
    if source is None:
        raise ValueError('Selected script is absent from its exact context mapping')
    if reader is not None:
        resolved=paths.resolve_path(name,context,roots,cwd_reader=reader)
        return resolved.resolved_path,dict(bytes=resolved.bytes,sha256=resolved.sha256)
    # Offline provenance uses the immutable mapping and existing _read root,
    # reparse, byte and deadline guards. It never searches or observes an old PID.
    resolved=Path(source.resolved_path).resolve(strict=True)
    return resolved,dict(bytes=source.bytes,sha256=source.sha256)
'''


def parameterize_provider(tree):
    functions = _functions(tree, ('capture_selected_sources', 'recheck_selected_sources', '_read'))
    if any(isinstance(n, ast.FunctionDef) and n.name == '_load_script_path_context' for n in tree.body):
        raise ValueError('Script-path provider hook already applied')
    tree.body.extend(ast.parse(_HELPERS).body)
    capture, recheck = (functions[name] for name in ('capture_selected_sources','recheck_selected_sources'))
    for fn in (capture,recheck):_keywords(fn)
    body, index = _location(capture, lambda n: _assignment(n,'destination'))
    body[index:index] = ast.parse('''
path_context,path_reader=_load_script_path_context(script_path_context,script_path_cwd_reader,live=True)
_validate_script_path_roots(path_context,roots)
if path_context is not None and selected_paths!=list(path_context.selected_order):
    raise ValueError('Selected script order differs from its pinned context')
''').body
    body, index = _location(capture, lambda n: _assignment(n,'report'))
    body[index+1:index+1] = ast.parse('''
if path_context is not None:
    report['path_resolution']=_script_path_provenance(script_path_context,path_context)
''').body
    body, index = _location(capture, lambda n: isinstance(n,ast.Assign) and isinstance(n.value,ast.Call)
                            and isinstance(n.value.func,ast.Name) and n.value.func.id=='_read')
    original = body[index]
    body[index:index+1] = ast.parse('''
if path_context is not None:
    mapped_path,mapped_pin=_selected_script_path(name,path_context,roots,path_reader)
    raw,state=_read(mapped_path,roots,deadline)
    if {k:state[k] for k in ('bytes','sha256')}!=mapped_pin:
        raise ValueError('Mapped script bytes differ from their pinned context')
else:
    pass
''').body
    body[index].orelse = [original]
    body, index = _location(capture, lambda n: isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
        and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='append'
        and ast.unparse(n.value.func.value)=="report['records']")
    body[index+1:index+1] = ast.parse('''
if path_context is not None:
    report['records'][-1]['resolved_path']=str(mapped_path)
''').body

    body, index = _location(recheck, lambda n: _assignment(n,'roots'))
    body[index:index] = ast.parse('''
saved_resolution=report.get('path_resolution')
if saved_resolution is not None:
    saved_context=saved_resolution.get('context')
    if script_path_context is not None and script_path_context!=saved_context:
        raise ValueError('Selected-source context differs from its retained provenance')
    script_path_context=saved_context
elif script_path_context is not None:
    raise ValueError('Selected-source report has no explicit path-resolution provenance')
path_context,path_reader=_load_script_path_context(script_path_context,script_path_cwd_reader,
                                                  live=script_path_cwd_reader is not None)
if path_context is not None:
    if (report['selected_paths']!=list(path_context.selected_order)
            or saved_resolution!=_script_path_provenance(script_path_context,path_context)):
        raise ValueError('Retained selected path order or resolution provenance differs')
''').body
    body, index = _location(recheck, lambda n: _assignment(n,'roots'))
    body[index+1:index+1]=ast.parse('_validate_script_path_roots(path_context,roots)').body
    body, index = _location(recheck, lambda n: isinstance(n,ast.Assign) and isinstance(n.value,ast.Call)
        and isinstance(n.value.func,ast.Name) and n.value.func.id=='_read'
        and any(isinstance(child,ast.Subscript) and ast.unparse(child)=="row['source_path']"
                for child in ast.walk(n.value)))
    original = body[index]
    body[index:index+1] = ast.parse('''
if path_context is not None:
    mapped_path,mapped_pin=_selected_script_path(row['source_path'],path_context,roots,path_reader)
    if row.get('resolved_path')!=str(mapped_path):
        raise ValueError('Retained resolved path differs from its exact mapping')
    raw,state=_read(mapped_path,roots,deadline)
    if {k:state[k] for k in ('bytes','sha256')}!=mapped_pin:
        raise ValueError('Resolved script bytes changed')
else:
    pass
''').body
    body[index].orelse = [original]
    checks = [n for n in ast.walk(recheck) if isinstance(n,ast.If)
              and ast.unparse(n.test)=="row['index'] != index or state != row['source_state']"]
    if len(checks)!=1:raise ValueError('Selected source state recheck seam changed')
    checks[0].test=ast.parse("row['index'] != index or (state != row['source_state'] if path_context is None or path_reader is not None else any(state[k]!=row['source_state'][k] for k in ('bytes','sha256')))",mode='eval').body
    return tree


def parameterize_collector(tree):
    functions=_functions(tree,('preflight','capture','main'))
    preflight,capture,main=(functions[name] for name in ('preflight','capture','main'))
    for fn in (preflight,capture):
        _keywords(fn)
        fn.body[1:1]=ast.parse('''
if script_path_context is None and script_path_cwd_reader is not None:
    raise ValueError('A script CWD observer requires an explicit script-path context')
from civ6_host.runtime.native.native_gameplay_source_capture import _load_script_path_context, _script_path_provenance, _validate_script_path_roots
''').body
    body,index=_location(preflight,lambda n:_assignment(n,'identity'))
    body[index+1:index+1]=ast.parse('''
path_context,_=_load_script_path_context(script_path_context,process=identity)
_validate_script_path_roots(path_context,script_roots)
''').body
    body,index=_location(preflight,lambda n:isinstance(n,ast.Return))
    body[index:index]=ast.parse('''
if path_context is not None:
    result['script_path_resolution']=_script_path_provenance(script_path_context,path_context)
''').body
    calls=[n for n in ast.walk(capture) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='preflight']
    if len(calls)!=1:raise ValueError('Script-path capture preflight seam changed')
    for name in ('script_path_context','script_path_cwd_reader'):
        calls[0].keywords.append(ast.keyword(arg=name,value=ast.Name(id=name,ctx=ast.Load())))
    body,index=_location(capture,lambda n:_assignment(n,'runtime_before'))
    if index+2>=len(body) or 'runtime-selections-before.json' not in ast.unparse(body[index+2]):
        raise ValueError('Capture runtime-selection publication seam changed')
    original=body[index:index+3]
    body[index:index+3]=[ast.If(test=ast.Compare(left=ast.Name(id='script_path_context',ctx=ast.Load()),
        ops=[ast.Is()],comparators=[ast.Constant(None)]),body=original,orelse=[])]
    body,index=_location(capture,lambda n:_assignment(n,'before') and isinstance(n.value,ast.Call)
                         and isinstance(n.value.func,ast.Name) and n.value.func.id=='capture_bundle')
    body[index:index]=ast.parse('''
if script_path_context is not None:
    path_context,path_reader=_load_script_path_context(script_path_context,script_path_cwd_reader,
                                                     live=True,process=checked['process']['identity'])
    script_path_cwd_reader=path_reader
    _validate_script_path_roots(path_context,script_roots)
    runtime_before=_capture_runtime_selections(backend,pid,checked['process'])
    require(runtime_before['semantic']['selected_paths']==list(path_context.selected_order),
            'Raw selected script order differs from its pinned context before database capture')
    remaining()
    artifact('runtime-selections-before.json',runtime_before)
    manifest['script_path_resolution']=checked['script_path_resolution']
''').body
    for name,expected in (('capture_selected_sources',1),('recheck_selected_sources',2)):
        calls=[n for n in ast.walk(capture) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==name]
        if len(calls)!=expected:raise ValueError('Selected script forwarding seam changed: '+name)
        for call in calls:
            call.keywords.append(ast.keyword(arg=None,value=ast.parse("{} if script_path_context is None else dict(script_path_context=script_path_context,script_path_cwd_reader=script_path_cwd_reader)",mode='eval').body))
    options=[i for i,n in enumerate(main.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
             and n.value.args and isinstance(n.value.args[0],ast.Constant) and n.value.args[0].value=='--script-root']
    if len(options)!=1:raise ValueError('Script-root CLI seam changed')
    main.body[options[0]+1:options[0]+1]=ast.parse('''
parser.add_argument('--script-path-context',type=json.loads,
    help='Explicit JSON {witness:{path,bytes,sha256},process:{pid,creation_filetime,image_path}}; no path search')
''').body
    common=[n for n in ast.walk(main) if _assignment(n,'common')]
    if len(common)!=1 or not isinstance(common[0].value,ast.Call):raise ValueError('Capture common CLI seam changed')
    common[0].value.keywords.append(ast.keyword(arg='script_path_context',value=ast.Attribute(
        value=ast.Name(id='args',ctx=ast.Load()),attr='script_path_context',ctx=ast.Load())))
    return tree


def parameterize(name, raw):
    if name not in MODULES:return raw
    tree=ast.parse(raw)
    tree=(parameterize_collector(tree) if name==MODULES[0] else parameterize_provider(tree))
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

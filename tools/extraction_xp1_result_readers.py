"""Select source proofs for existing result readers; preserve their algorithms.

No runtime files are written here. The common extractor calls parameterize for
the three retained modules. Lua collectors, parsers and victory policy remain
the existing implementations; only proof selection and provenance are added.
"""
import ast

BASE = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
MODULES = {'native_winning_team', 'native_episode_facts', 'native_victory_episode'}


def _function(nodes, name):
    matches = [n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(matches) != 1:
        raise ValueError('Result reader anchor changed: '+name)
    return matches[0]


def _keyword(fn):
    if any(arg.arg == 'core_sha256' for arg in fn.args.args + fn.args.kwonlyargs):
        raise ValueError('Result reader already parameterized: '+fn.name)
    fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
    fn.args.kw_defaults.append(ast.Constant(BASE))


def _forward(fn, targets, expression='core_sha256'):
    found = {name: 0 for name in targets}
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if name in found:
                if any(k.arg == 'core_sha256' for k in node.keywords):
                    raise ValueError('Result call already selected: '+name)
                node.keywords.append(ast.keyword(arg='core_sha256', value=ast.parse(expression, mode='eval').body))
                found[name] += 1
    if found != targets:
        raise ValueError('Result reader call anchors changed: '+repr(found))


def _select_verifier(fn):
    _keyword(fn)
    at = int(bool(fn.body and isinstance(fn.body[0], ast.Expr)
                  and isinstance(fn.body[0].value, ast.Constant)
                  and isinstance(fn.body[0].value.value, str)))
    fn.body[at:at] = ast.parse(f'''
if core_sha256 != {BASE!r}:
    from civ6_host.runtime.xp1_session_result import verify_reader_source
    return verify_reader_source(core_sha256)
''').body


def _bind_return(fn, kind, core):
    returns = [node for node in ast.walk(fn) if isinstance(node, ast.Return)]
    if len(returns) != 1 or not isinstance(returns[0].value, ast.Dict):
        raise ValueError('Result dictionary anchor changed: '+fn.name)
    returned = returns[0]
    fn.body.insert(0, ast.ImportFrom(module='civ6_host.runtime.xp1_session_result',
        names=[ast.alias(name='bind_'+kind+'_provenance')], level=0))
    returned.value = ast.Call(func=ast.Name(id='bind_'+kind+'_provenance',ctx=ast.Load()),
        args=[returned.value, ast.parse(core,mode='eval').body], keywords=[])


def parameterize(name, raw):
    leaf = name.rsplit('.',1)[-1]
    if leaf not in MODULES:
        return raw
    tree = ast.parse(raw)
    if leaf == 'native_winning_team':
        fn = _function(tree.body,'source');_keyword(fn)
        if len(fn.body) != 3 or not isinstance(fn.body[-1],ast.Return):
            raise ValueError('Winning-team proof block changed')
        original = fn.body[:2]
        selected = ast.parse('from civ6_host.runtime.xp1_session_result import verify_reader_source\nverify_reader_source(core_sha256)').body
        fn.body = [ast.If(test=ast.Compare(left=ast.Name(id='core_sha256',ctx=ast.Load()),
            ops=[ast.Eq()],comparators=[ast.Constant(BASE)]),body=original,orelse=selected),fn.body[-1]]
        guard = _function(tree.body,'guard_case');_keyword(guard);_forward(guard,{'source':1})
    elif leaf == 'native_episode_facts':
        _select_verifier(_function(tree.body,'verify_source'))
        fn = _function(tree.body,'build_source');_keyword(fn);_forward(fn,{'verify_source':1})
        fn = _function(tree.body,'parse_facts');_keyword(fn);_bind_return(fn,'facts','core_sha256')
        fn = _function(tree.body,'guard_case');_keyword(fn);_forward(fn,{'build_source':1})
    else:
        _select_verifier(_function(tree.body,'verify_source'))
        fn = _function(tree.body,'build_source');_keyword(fn)
        _forward(fn,{'verify_source':1,'native_episode_facts.build_source':1})
        fn = _function(tree.body,'guard_case');_keyword(fn)
        _forward(fn,{'verify_source':1,'native_episode_facts.guard_case':1})
        classes = [n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='FirstOfficialVictory']
        if len(classes)!=1:raise ValueError('FirstOfficialVictory owner changed')
        cls = classes[0]
        fn = _function(cls.body,'__init__');_keyword(fn);_forward(fn,{'verify_source':1})
        verifier = next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Expr)
                        and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='verify_source')
        fn.body[verifier+1:verifier+1] = ast.parse('self._core_sha256 = core_sha256').body
        fn = _function(cls.body,'observe')
        _forward(fn,{'verify_source':1,'native_episode_facts.parse_facts':1},'self._core_sha256')
        _bind_return(fn,'policy','self._core_sha256')
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

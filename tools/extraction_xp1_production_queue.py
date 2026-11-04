"""Select the engine for the existing production queue; preserve its algorithm."""
import ast

MODULE = 'civ6rl.native_saved_production_queue'
TARGETS = ('verify_source', 'source', 'catalog', 'request_source', 'apply')
DEFAULT = '_QUEUE_BASE_CORE_SHA256'


def parameterize(name, raw):
    if name != MODULE:
        return raw
    tree = ast.parse(raw)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if not set(TARGETS) <= set(functions):
        raise ValueError('Shared production queue extraction functions changed')
    for target in TARGETS:
        fn = functions[target]
        if any(a.arg == 'core_sha256' for a in fn.args.kwonlyargs):
            raise ValueError('Production queue is already engine selected')
        fn.args.kwonlyargs.append(ast.arg(arg='core_sha256'))
        fn.args.kw_defaults.append(ast.Name(id=DEFAULT, ctx=ast.Load()))
        for call in ast.walk(fn):
            if not isinstance(call, ast.Call):
                continue
            if ((isinstance(call.func, ast.Name) and call.func.id in TARGETS)
                    or (isinstance(call.func, ast.Attribute)
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == 'production' and call.func.attr == '_preamble')):
                call.keywords.append(ast.keyword(arg='core_sha256', value=ast.Name(id='core_sha256', ctx=ast.Load())))
        if target == 'verify_source':
            fn.body[:0] = ast.parse(f'''
if core_sha256 != {DEFAULT}:
    from civ6_host.runtime.xp1_production_queue_profile import verify_source as selected_source
    return selected_source(core_sha256)
''').body
        if target == 'apply':
            fn.args.kwonlyargs.append(ast.arg(arg='gate_owner'))
            fn.args.kw_defaults.append(ast.Constant(None))
            gate = [n for n in fn.body if isinstance(n, ast.Assign)
                    and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                    and n.targets[0].id == 'admitted']
            if len(gate) != 1 or ast.unparse(gate[0].value) != "gate_admitted(owner, 'production_queue')":
                raise ValueError('Shared production queue admission seam changed')
            index = fn.body.index(gate[0])
            selected = ast.parse(f'''
if core_sha256 == {DEFAULT}:
    if gate_owner is not None:
        raise ValueError('Base queue admission does not accept a foreign gate owner')
    admitted = gate_admitted(owner, 'production_queue')
else:
    from civ6_host.runtime.xp1_production_queue_profile import gate_admitted as selected_gate
    selected_owner = owner if gate_owner is None else gate_owner
    if selected_owner.prefix is not prefix:
        raise ValueError('Queue admission belongs to a different native prefix')
    admitted = selected_gate(selected_owner)
''').body[0]
            fn.body[index:index+1] = [selected]
            guard = fn.body[index+1]
            if not isinstance(guard, ast.If) or 'production_queue_diagnostic' not in ast.unparse(guard.test):
                raise ValueError('Shared production queue diagnostic admission seam changed')
            guard.test = ast.parse(f"not admitted and (core_sha256 != {DEFAULT} or getattr(owner, 'production_queue_diagnostic', False) is not True)", mode='eval').body
            changes = []
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call):
                    continue
                for keyword in call.keywords:
                    if keyword.arg in ('source_proof_sha256', 'public_source_proof_sha256'):
                        expected = 'PROOF_SHA' if keyword.arg == 'source_proof_sha256' else 'PUBLIC_PROOF_SHA'
                        if not isinstance(keyword.value, ast.Name) or keyword.value.id != expected:
                            raise ValueError('Production queue event provenance changed')
                        keyword.value = ast.parse(f"{expected} if core_sha256 == {DEFAULT} else selected_queue_source[1]", mode='eval').body
                        changes.append(keyword.arg)
            if sorted(changes) != ['public_source_proof_sha256', 'source_proof_sha256']:
                raise ValueError('Shared queue lacks its two source receipts')
            fn.body[:0] = ast.parse(f'''
if core_sha256 != {DEFAULT}:
    from civ6_host.runtime.xp1_production_queue_profile import source_reference
    selected_queue_source = source_reference(core_sha256)
''').body
    index = int(bool(tree.body and isinstance(tree.body[0], ast.Expr)
                     and isinstance(tree.body[0].value, ast.Constant)
                     and isinstance(tree.body[0].value.value, str)))
    while index < len(tree.body) and isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    tree.body[index:index] = ast.parse(f'from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as {DEFAULT}').body
    return ast.unparse(ast.fix_missing_locations(tree)) + '\n'

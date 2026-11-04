"""Share the existing session launch tail without changing Base preparation."""
import ast
import hashlib

TAIL_SHA256 = 'c27be392a2065600b3f32b45753e6f25639fbdb18df27cb1550def92cbaffce8'


def parameterize(name, text):
    if name != 'civ6rl.native_saved_session':
        return text
    tree = ast.parse(text)
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeSavedSession')
    reset = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == 'reset')
    starts = [i for i, n in enumerate(reset.body) if isinstance(n, ast.Assign)
              and ast.unparse(n) == 'self.process = None']
    if len(starts) != 1:
        raise ValueError('Shared reset launch boundary changed')
    start = starts[0]
    tail = ast.dump(ast.Module(body=reset.body[start:], type_ignores=[]), include_attributes=False)
    if hashlib.sha256(tail.encode()).hexdigest() != TAIL_SHA256:
        raise ValueError('Shared reset launch algorithm changed before extraction')
    reset.body[start:] = ast.parse(
        'from civ6_host.runtime.session_launch import launch\n'
        'return launch(self, HOST, worker, closure, env, captured, reset_started)\n').body
    return ast.unparse(ast.fix_missing_locations(tree)) + '\n'

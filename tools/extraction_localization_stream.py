"""Opt-in row-file capture channel; old query registration stays byte-identical."""
import ast

def parameterize(name, raw):
    if name not in ('civ6rl.native_localization_query','civ6rl.file_client','civ6rl.response_file_client'):return raw
    tree=ast.parse(raw)
    def functions():return {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    if name=='civ6rl.native_localization_query':
        f=functions()
        verify=f['verify_build'];ret=verify.body[-1]
        if not isinstance(ret,ast.Return) or ast.unparse(ret.value)!='build':raise ValueError('Query build return changed')
        verify.body[-1:]=ast.parse('from civ6_host.runtime.localization_stream_bridge import verify_stream_build\nreturn verify_stream_build(build,path)').body
        fn=f['registration_command'];ret=fn.body[-1]
        if ast.unparse(ret.value)!='(event, command)':raise ValueError('Query registration return changed')
        fn.body[-1:]=ast.parse('from civ6_host.runtime.localization_stream_bridge import registration_command as stream_command\nreturn (event,stream_command(command,build,process,nonce))').body
        fn=f['install_command'];ret=fn.body[-1]
        if not isinstance(ret,ast.Return) or not isinstance(ret.value,ast.JoinedStr):raise ValueError('Query install return changed')
        fn.body[-1:]=[ast.parse('from civ6_host.runtime.localization_stream_bridge import install_command as stream_install').body[0],
            ast.Return(ast.Call(ast.Name('stream_install',ast.Load()),[ret.value,ast.Name('registration',ast.Load()),ast.Name('player_id',ast.Load()),ast.Name('turn',ast.Load())],[]))]
    elif name=='civ6rl.file_client':
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='FileClient')
        if any(isinstance(n,ast.FunctionDef) and n.name=='read_database_rows' for n in cls.body):raise ValueError('Row client already defined')
        cls.body+=ast.parse('''def read_database_rows(self, request, output_path, *, provider_nonce, timeout=None, envelope_sink=None):
    from civ6_host.runtime.localization_stream_bridge import read_rows
    return read_rows(self, request, output_path, provider_nonce=provider_nonce, timeout=timeout, envelope_sink=envelope_sink)
''').body
    else:
        node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ALLOWED_OPERATIONS' for t in n.targets))
        if not isinstance(node.value,ast.Call) or not isinstance(node.value.args[0],ast.Tuple):raise ValueError('Direct capture operation boundary changed')
        node.value.args[0].elts.append(ast.Constant('database_row_stream'))
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

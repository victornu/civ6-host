"""Select source identities in the existing bounded stdout decoder."""
import ast


def parameterize(name, raw):
    if name not in ('civ6rl.native_stdout_transport','civ6rl.native_saved_session'):
        return raw
    tree=ast.parse(raw)
    if name=='civ6rl.native_stdout_transport':
        functions={node.name:node for node in tree.body if isinstance(node,ast.FunctionDef)}
        fn=functions['decode_stdout']
        guard=ast.parse("if core_sha256 != CORE_SHA256 or host_sha256 != HOST_SHA256:\n raise ValueError('decoder requires exact Core and Host41 identities')").body[0]
        matches=[i for i,node in enumerate(fn.body) if ast.dump(node)==ast.dump(guard)]
        if len(matches)!=1:raise ValueError('Shared stdout identity guard changed')
        index=matches[0]
        if ast.unparse(fn.body[index+1])!='verify_source(source_path)':
            raise ValueError('Shared stdout proof selection seam changed')
        # Only provenance selection changes. Keep the parser and all its bounds.
        class Select(ast.NodeTransformer):
            def visit_Name(self,node):
                if isinstance(node.ctx,ast.Load) and node.id=='SOURCE_SHA256':
                    return ast.copy_location(ast.Name(id='selected_source',ctx=ast.Load()),node)
                return node
        Select().visit(fn)
        fn.body[index:index+2]=ast.parse(
            'selected_source=_transport_profile(core_sha256,host_sha256,source_path=source_path,base_verify=verify_source)').body
        complete=functions['require_complete']
        complete.body=ast.parse("""
if (type(result) is not dict or result.get('schema')!=SCHEMA
        or result.get('collection_complete') is not True or result.get('stdout_other')!=[]):
    raise ValueError('Unclassified or damaged stdout transport; no complete collection claim')
expected=_transport_profile(result.get('core_sha256'),result.get('host_sha256'),base_verify=verify_source)
if result.get('source_sha256')!=expected:
    raise ValueError('Stdout source profile does not match its native identities')
""").body
        tree.body[:0]=ast.parse('from civ6_host.runtime.stdout_transport_profiles import verify_selected as _transport_profile').body
    else:
        owner=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeSavedSession')
        fn=next(n for n in owner.body if isinstance(n,ast.FunctionDef) and n.name=='_read_stream')
        matches=[node for node in ast.walk(fn) if isinstance(node,ast.If)
                 and ast.unparse(node.test)=='events']
        if len(matches)!=1:raise ValueError('Shared stdout reader event boundary changed')
        branch=matches[0]
        tries=[i for i,node in enumerate(branch.body) if isinstance(node,ast.Try)
               and ast.unparse(node.body[0])=='event = json.loads(line)']
        if len(tries)!=1:raise ValueError('Shared stdout reader decoder seam changed')
        index=tries[0]
        if 'transport.decode_stdout' not in ast.unparse(branch.body[index]):
            raise ValueError('Shared stdout source decoder no longer retained')
        branch.body[index:index+1]=ast.parse('''
event,native_record=_decode_stdout_record(line,stdout_profile,line_number=line_number,line_limit=line_limit)
if native_record is not None:
    if len(self.stdout_native_records)>=4096:
        raise ValueError('Native diagnostic record budget exceeded')
    self.stdout_native_records.append(native_record)
if isinstance(event,dict) and event.get('stage')=='native_city_specialist_preparation_readback':
    # The same-pipe public response authorizes qualification to read this receipt.
    log.flush()
''').body
        # Verification is inside the existing fail-closed try boundary.
        outer=next(node for node in fn.body if isinstance(node,ast.Try))
        outer.body[:0]=ast.parse('''
from civ6_host.runtime.stdout_transport_profiles import decode_record as _decode_stdout_record, selected_profile as _stdout_profile
stdout_profile=_stdout_profile(**self.stdout_identity) if events else None
''').body
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

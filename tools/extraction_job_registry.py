"""Share the retained queue walker and structural transition validators.

Legacy Base source verification, schema and provenance are preserved exactly.
"""
import ast


def parameterize(name,text):
    if name not in ('civ6rl.native_checkpoint_jobs','civ6rl.native_checkpoint_postload_jobs'):
        return text
    tree=ast.parse(text)
    if name=='civ6rl.native_checkpoint_jobs':
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='capture_snapshot')
        boundary=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign)
                      and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='observed')
        if ast.unparse(fn.body[boundary])!='observed = {}':
            raise ValueError('Retained walker boundary differs')
        fn.body[boundary:]=ast.parse('''
from civ6_host.runtime.job_registry_snapshot import capture_registry
result=capture_registry(read,{name:host_base+rva for name,rva in RVA.items()},current_thread_id,
                        max_items=max_items,max_groups=max_groups)
return dict(result,schema='civ6rl.native_checkpoint_host41_job_snapshot.v1',
            source_proof_sha256=PROOF_SHA256,host_sha256=HOST_SHA256,profile=profile)
''').body
    else:
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_quiescent_snapshot_transition')
        # Preserve both complete legacy _identity calls, immutable identity
        # comparisons and the mismatch refusal before shared data validation.
        boundary=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.If)
                      and ast.unparse(n.test)=="before.get('stable_read') is not True or after.get('stable_read') is not True")
        fn.body[boundary:]=ast.parse('''
from civ6_host.runtime.job_registry_snapshot import validate_empty_transition_data
data=validate_empty_transition_data(before,after)
return dict(data,schema='civ6rl.native_checkpoint_postload_empty_jobs_transition.v1',
            source_proof_sha256=jobs.PROOF_SHA256,host_source_sha256=HOST_SOURCE_SHA256)
''').body
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)+'\n'

"""Share the retained two-field unit normalizer, preserving its public domain."""
import ast
import copy

MODULES={'native_absent_d70ba51f'}


def parameterize(name,raw):
    short=name.replace('\\','/').rsplit('/',1)[-1].removesuffix('.py').rsplit('.',1)[-1]
    if short not in MODULES:return raw
    tree=ast.parse(raw)
    candidates=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_absent_event']
    if len(candidates)!=1:raise ValueError('Absent unit normalizer source seam changed')
    public=candidates[0]
    start=1 if ast.get_docstring(public) is not None else 0
    if (ast.unparse(public.body[start])!='verify_source_evidence()'
            or not isinstance(public.body[start+1],ast.If)
            or ast.unparse(public.body[start+1].test)!='type(kind) is not int or kind != EVENT_KIND or kind in EXE_EVENT_CALLBACKS'):
        raise ValueError('Absent unit normalizer closed domain changed')
    shared=copy.deepcopy(public);shared.name='_validate_profile_event'
    shared.body[start+1].test=ast.parse('type(kind) is not int or not 0 <= kind <= 4294967295 or kind in EXE_EVENT_CALLBACKS',mode='eval').body
    shared.body[start+1].body=ast.parse("raise ValueError('Only uint32 kinds absent from the captured registry are admitted')").body
    public.body=[*copy.deepcopy(public.body[:start+2]),*ast.parse('''
return _validate_profile_event(kind,raw_fields,read,
    normalizer_transform_present=normalizer_transform_present,
    registry_profile=registry_profile,
    dynamic_registration_present=dynamic_registration_present,
    entity_listener_count=entity_listener_count)
''').body]
    tree.body.insert(tree.body.index(public),shared)
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'

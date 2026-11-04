"""Opt-in ExposedMembers attachment for explicitly selected script contexts."""
from secrets import token_hex

from .native.native_script_primitives import evaluate_lua


def attach_exposed_members(runtime, contexts):
    """Attach one root-owned Lua table to the selected children of this VM.

    A private temporary marker selects exact child environments in the native
    registry. Unselected contexts retain their existing namespaces. This
    attaches the table only; LuaEvents and native UI bindings are independent.
    """
    contexts = tuple(contexts)
    if not 1 <= len(contexts) <= 64:
        raise ValueError('ExposedMembers requires one to 64 owned contexts')
    pointers = [runtime.registry.validate(child) for child in contexts]
    if len(set(pointers)) != len(pointers):
        raise ValueError('Duplicate ExposedMembers context')

    marker = '_Civ6HostExposedMembers_' + token_hex(16)
    attach = (f"assert({marker} == nil); {marker} = true").encode('ascii')
    clear = f"{marker} = nil".encode('ascii')
    marked = []
    try:
        for child in contexts:
            runtime.execute(child, attach, b'@host_exposed_members_mark')
            marked.append(child)
        evaluate_lua(runtime.lua, runtime.root, f"""
local selected = {{}}
for _, env in pairs(Threads) do
    if rawget(env, '{marker}') == true then
        selected[#selected + 1] = env
    end
end
assert(#selected == {len(contexts)}, 'ExposedMembers child identity differs')
local shared = ExposedMembers
assert(shared == nil or type(shared) == 'table', 'Unsupported root ExposedMembers')
if shared == nil then shared = {{}} end
for i = 1, #selected do
    local current = rawget(selected[i], 'ExposedMembers')
    assert(current == nil or rawequal(current, shared), 'Foreign child ExposedMembers')
end
ExposedMembers = shared
for i = 1, #selected do
    rawset(selected[i], 'ExposedMembers', shared)
end
return 1
""", b'@host_exposed_members_attach')
    finally:
        for child in marked:
            runtime.execute(child, clear, b'@host_exposed_members_clear')

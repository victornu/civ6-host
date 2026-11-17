/* Scoped XP2 DealItem::SetValueType input conversion for the installed core. */
#include <windows.h>
#include <intrin.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

typedef struct DealVariant {
    uint32_t tag, reserved;
    uint64_t payload;
    uint32_t size, flags;
} DealVariant;

_Static_assert(sizeof(DealVariant) == 24 && offsetof(DealVariant, payload) == 8,
               "XP2 Variant ABI");

typedef int (__cdecl *GetTop)(void *state);
typedef int (__cdecl *GetType)(void *state, int index);
typedef double (__cdecl *GetNumber)(void *state, int index);
typedef void (__cdecl *Release)(DealVariant *value, void *resolver);

static __declspec(thread) struct {
    uintptr_t core;
    void *owner, *state;
    GetTop top;
    GetType type;
    GetNumber number;
    uint32_t expected;
    int calls;
} scope;

static __declspec(noreturn) void refuse(const char *why) {
    fprintf(stderr, "{\"event\":\"deal_resource_value_refused\",\"reason\":\"%s\"}\n", why);
    fflush(stderr);
    TerminateProcess(GetCurrentProcess(), 78);
    __fastfail(7);
}

__declspec(dllexport) int __cdecl LAB_DealValueBegin(
        uintptr_t core, void *owner, void *state, GetTop top, GetType type,
        GetNumber number, uint32_t expected) {
    if (scope.core || !core || !owner || !state || !top || !type || !number ||
            expected > INT32_MAX || top(state) != 0)
        return 0;
    scope.core = core;
    scope.owner = owner;
    scope.state = state;
    scope.top = top;
    scope.type = type;
    scope.number = number;
    scope.expected = expected;
    scope.calls = 0;
    return 1;
}

__declspec(dllexport) void __cdecl LAB_DealValueWrite(
        void *owner, void *state, DealVariant *value, void *resolver, int index) {
    if (!scope.core || scope.calls || scope.owner != owner || scope.state != state ||
            (uintptr_t)_ReturnAddress() != scope.core + 0x6d1063u)
        refuse("caller or scope");
    if (!resolver || *(uintptr_t *)resolver != scope.core + 0xabeff8u ||
            !value || ((uintptr_t)value & 7u) || value->tag || value->payload || value->size || value->flags)
        refuse("resolver or destination");
    if (index != 2 || scope.top(state) != 2 || scope.type(state, index) != 3 ||
            scope.number(state, index) != (double)scope.expected || scope.top(state) != 2)
        refuse("Lua resource index");
    Release release = (Release)(scope.core + 0x9a1560u);
    release(value, resolver);
    value->tag = 2;
    value->payload = scope.expected;
    scope.calls = 1;
}

__declspec(dllexport) int __cdecl LAB_DealValueEnd(void *owner, void *state) {
    if (!scope.core || scope.owner != owner || scope.state != state || scope.top(state) != 0)
        return -1;
    const int calls = scope.calls;
    scope.core = 0;
    scope.owner = scope.state = NULL;
    return calls;
}

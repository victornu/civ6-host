/* XP2 0x15479 -> EXE auxiliary +B8: Lua value to owned Variant.
 * Tables, booleans and numeric values use the exact XP2 producer ABI.
 */
#include <intrin.h>

typedef void (__cdecl *AuxB8Release)(MutableCoreVariant*, void*);
typedef MutableCoreVariant* (__cdecl *AuxB8Clone)(void*, MutableCoreVariant*, const MutableCoreVariant*);

static struct {
    LuaState* root;
    void* owner;
    uintptr_t core;
    DWORD thread;
    MutableMapRequest* request;
} aux_b8;

static void aux_b8_stop(const char* why, int status) {
    fprintf(stderr,"{\"event\":\"aux_b8_refused\",\"reason\":\"%s\",\"status\":%d}\n",why,status);
    fflush(stderr);
    TerminateProcess(GetCurrentProcess(),78);
    abort();
}

static int __cdecl aux_b8_write_table(LuaState* state) {
    MutableMapRequest* request=aux_b8.request;
    if(!request || request->state!=state || th_gettop(state)!=1 || th_type(state,1)!=5)
        return th_lerror(state,"XP2 AUX B8 protected table frame differs");
    return mutable_map_from_table(state,1,request->destination,request,0);
}

__declspec(dllexport) void __cdecl LAB_XP2AuxB8Table(
        void* owner,LuaState* state,MutableCoreVariant* output,void* resolver,int index) {
    if(!aux_b8.root || aux_b8.root!=thread_registry_root || aux_b8.owner!=owner ||
       aux_b8.thread!=GetCurrentThreadId() || aux_b8.request ||
       (uintptr_t)_ReturnAddress()!=aux_b8.core+0x1547f ||
       !state || !script_event_known_state(state) || !output || ((uintptr_t)output&7u) ||
       !resolver || *(uintptr_t*)resolver!=aux_b8.core+mutable_map_xp2.resolver_vtable_rva)
        aux_b8_stop("owner, callsite or Lua scope",0);
    int top=th_gettop(state);
    if(index<1 || index>top)
        aux_b8_stop("Lua input index",0);
    int input_type=th_type(state,index);
    if(input_type!=1 && input_type!=3 && input_type!=5)
        aux_b8_stop("unsupported Lua property value",input_type);

    HMODULE havok=NULL;
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (LPCWSTR)(uintptr_t)th_checknumber,&havok))
        aux_b8_stop("HKS module",0);
    FARPROC number=GetProcAddress(havok,"?lua_tonumber@@YANPEAUlua_State@@H@Z");
    if((uintptr_t)number!=(uintptr_t)havok+0x3d5f0)
        aux_b8_stop("HKS number ABI",0);

    double (__cdecl *read_number)(LuaState*,int);
    memcpy(&read_number,&number,sizeof(number));
    AuxB8Release release=(AuxB8Release)(aux_b8.core+0x9a1560);
    if(input_type==1 || input_type==3) {
        uint32_t tag, payload;
        if(input_type==1) {
            tag=1;
            payload=(uint32_t)(th_toboolean(state,index)!=0);
        } else {
            double value=read_number(state,index);
            /* EXE DB7185 uses signed CVTTSD2SI32 and compares back to double.
             * Unordered UCOMISD also takes its integer branch. */
            int32_t integer=_mm_cvttsd_si32(_mm_set_sd(value));
            if(_isnan(value) || value==(double)integer) {
                tag=2;
                memcpy(&payload,&integer,sizeof(payload));
            } else {
                tag=4;
                float single=(float)value;
                memcpy(&payload,&single,sizeof(payload));
            }
        }
        if(th_gettop(state)!=top) aux_b8_stop("scalar conversion changed Lua frame",0);
        release(output,resolver);
        output->tag=tag;
        output->pointer=payload;
        fprintf(stderr,"{\"event\":\"aux_b8_scalar_committed\",\"tag\":%u,\"event_scope\":%u}\n",
                tag,LAB_GameEventsStateIsActive(aux_b8.root,state));
        fflush(stderr);
        return;
    }

    th_checkstack(state,2,"XP2 AUX B8 protected frame");
    th_closure(state,aux_b8_write_table,0,"XP2 AUX B8 table conversion",0);
    th_pushvalue(state,index);

    MutableMapRequest request={0};
    request.state=state;
    request.module=aux_b8.core;
    request.abi=&mutable_map_xp2;
    request.number=read_number;
    AuxB8Clone clone=(AuxB8Clone)(aux_b8.core+mutable_map_xp2.clone_construct_rva);
    MutableCoreVariant empty={10,0,0,0,0x05000000u}, staged={0};
    if(clone(resolver,&staged,&empty)!=&staged || staged.tag!=10 ||
       staged.flags!=0x05000000u || !staged.pointer)
        aux_b8_stop("native table constructor",0);
    request.destination=(void*)(uintptr_t)staged.pointer;

    aux_b8.request=&request;
    int status=th_pcall(state,1,0,0);
    aux_b8.request=NULL;
    if(status || request.refused || th_gettop(state)!=top) {
        release(&staged,resolver);
        aux_b8_stop("protected table conversion",status);
    }
    release(output,resolver);
    *output=staged;  /* The caller's existing Variant now owns this map. */
    fprintf(stderr,"{\"event\":\"aux_b8_table_committed\",\"stack_index\":%d,\"fields\":%u,\"writes\":%u}\n",
            index,request.fields,request.writes);
    fflush(stderr);
}

__declspec(dllexport) int __cdecl LAB_XP2AuxB8Bind(LuaState* root,void* owner,void* module) {
    if(!thread_api_ready || !root || root!=thread_registry_root || th_gettop(root) ||
       !owner || !module || aux_b8.root) return 0;
    aux_b8.root=root;
    aux_b8.owner=owner;
    aux_b8.core=(uintptr_t)module;
    aux_b8.thread=GetCurrentThreadId();
    return 1;
}

__declspec(dllexport) int __cdecl LAB_XP2AuxB8Unbind(LuaState* root,void* owner) {
    if(!root || aux_b8.root!=root || aux_b8.owner!=owner || aux_b8.request ||
       aux_b8.thread!=GetCurrentThreadId()) return 0;
    memset(&aux_b8,0,sizeof(aux_b8));
    return 1;
}


/* Explicit XP2 in/out GameEvents table bridge. Source qualification and exact
 * native build admission are required by the Python owner before installation.
 * The caller's table is populated by official Core methods; no gameplay rules.
 */
#include <emmintrin.h>
/* A8 deliberately undefines its private macros at the end of its include. */
enum { MUTABLE_MAP_MAX_OPS=262144u, MUTABLE_MAP_MAX_STRING_BYTES=65536u,
       MUTABLE_MAP_MAX_TOTAL_STRING_BYTES=1048576u };

typedef struct MutableCoreVariant {
    uint32_t tag, reserved;
    uint64_t pointer;
    uint32_t size, flags;
} MutableCoreVariant;
_Static_assert(sizeof(MutableCoreVariant)==24,"Native Variant source ABI");

typedef struct MutableMapABI {
    uint32_t id;
    uintptr_t vtable_rva, clone_construct_rva, name_id_rva, resolver_vtable_rva;
} MutableMapABI;
static const MutableMapABI mutable_map_xp2={2,0xabf080,0x99d920,0x9a3f10,0xabeff8};

/* The wrapper declares the hook before including the retained dispatcher.
 * The hook changes only the pending in/out call and clears pending before
 * entering Lua, so unrelated/reentrant scalar Call/TestAll calls are unchanged.
 */
typedef struct MutableMapRequest {
    ScriptGameEventRequest base;
    const AuxMapOp* seed;
    uint32_t seed_count;
    void* destination;
    uintptr_t module;
    const MutableMapABI* abi;
    uint32_t refused, phase, fields, writes, string_bytes;
    int seed_index, pending;
    LuaState* state;
    double (__cdecl *number)(LuaState*,int);
    struct MutableMapRequest* previous;
    int active_tables[16];
} MutableMapRequest;
static MutableMapRequest* mutable_map_active=NULL;

static void __cdecl script_game_event_call_with_seed(LuaState* state,int nargs,int nresults) {
    MutableMapRequest* request=mutable_map_active;
    if(request && request->pending && request->state==state) {
        request->pending=0;
        th_pushvalue(state,request->seed_index);
        th_call(state,nargs+1,nresults);
    } else th_call(state,nargs,nresults);
}

static int mutable_map_refuse(LuaState* state,MutableMapRequest* request,const char* why) {
    request->refused=1;
    return th_lerror(state,"Mutable map bridge refused: %s",why);
}

/* Match CVTTSD2SI32/64 followed by the observed low-DWORD use. Do not rely on
 * implementation-defined C casts for out-of-range/NaN values. */
static uint32_t mutable_map_integer_candidate(double number) {
    if(number>2147483647.0)
        return (uint32_t)_mm_cvttsd_si64(_mm_set_sd(number));
    return (uint32_t)_mm_cvttsd_si32(_mm_set_sd(number));
}

static int mutable_map_this(LuaState* state,MutableMapRequest* request,void* object) {
    if(!object || ((uintptr_t)object & 7u) ||
       *(uintptr_t*)object!=request->module+request->abi->vtable_rva)
        return mutable_map_refuse(state,request,"foreign native provider");
    return 0;
}

static void* mutable_map_resolver(LuaState* state,MutableMapRequest* request,void* object) {
    typedef void* (__cdecl *GetResolver)(void*);
    uintptr_t* vtable=*(uintptr_t**)object;
    void* resolver=((GetResolver)vtable[0x20/8])(object);
    if(!resolver || *(uintptr_t*)resolver!=request->module+request->abi->resolver_vtable_rva) {
        mutable_map_refuse(state,request,"foreign key resolver");
        return NULL;
    }
    return resolver;
}

static const char* mutable_map_text(LuaState* state,int index,MutableMapRequest* request) {
    size_t length=0;
    const char* value=th_tolstring(state,index,&length);
    if(!value || length>MUTABLE_MAP_MAX_STRING_BYTES ||
       length>MUTABLE_MAP_MAX_TOTAL_STRING_BYTES-request->string_bytes) {
        mutable_map_refuse(state,request,"string budget");
        return NULL;
    }
    request->string_bytes+=(uint32_t)length;
    return value; /* Native setters consume a NUL-terminated string, as sourced. */
}

static void* mutable_map_empty_child(LuaState* state,MutableMapRequest* request,void* resolver) {
    /* 99D920 remaps RCX=resolver,RDX=destination,R8=source into the
     * ordinary assign ABI (destination,source,resolver). */
    typedef MutableCoreVariant* (__cdecl *CloneConstruct)(void*,MutableCoreVariant*,const MutableCoreVariant*);
    MutableCoreVariant input={10,0,0,0,0x05000000u},output={0};
    CloneConstruct clone=(CloneConstruct)(request->module+request->abi->clone_construct_rva);
    if(clone(resolver,&output,&input)!=&output) {
        mutable_map_refuse(state,request,"official clone destination differs");
        return NULL;
    }
    if(output.tag!=10 || output.flags!=0x05000000u || !output.pointer) {
        mutable_map_refuse(state,request,"official empty-child construction differs");
        return NULL;
    }
    void* child=(void*)(uintptr_t)output.pointer;
    if(mutable_map_this(state,request,child))return NULL;
    /* Ownership transfers through parent+A8 before recursive population.
     * This C temporary has no destructor and must not release the child again.
     */
    return child;
}

static int mutable_map_from_table(LuaState* state,int table,void* destination,
                                  MutableMapRequest* request,unsigned int depth) {
    if(depth>=16)return mutable_map_refuse(state,request,"table depth bound");
    if(mutable_map_this(state,request,destination))return 0;
    if(th_type(state,table)!=5)return mutable_map_refuse(state,request,"source is not a table");
    for(unsigned int i=0;i<depth;++i)
        if(th_rawequal(state,table,request->active_tables[i]))
            return mutable_map_refuse(state,request,"cyclic Lua table");
    request->active_tables[depth]=table;
    th_checkstack(state,8,"Mutable native map conversion");
    th_pushnil(state);
    while(th_next(state,table)) {
        if(++request->fields>65536u)return mutable_map_refuse(state,request,"field bound");
        uintptr_t* vtable=*(uintptr_t**)destination;
        uint32_t key=0;
        int key_type=th_type(state,-2),value_type=th_type(state,-1);
        if(key_type==4) {
            const char* name=mutable_map_text(state,-2,request);
            typedef uint32_t (__cdecl *NameID)(void*,const char*);
            void* resolver=mutable_map_resolver(state,request,destination);
            key=((NameID)(request->module+request->abi->name_id_rva))(resolver,name);
        } else {
            /* Native hks_obj_tonumber is used for every non-string key.
             * It returns zero for nonnumeric types, which still reach setters.
             * luaL_checknumber would incorrectly raise for these keys. */
            key=mutable_map_integer_candidate(request->number(state,-2));
        }
        typedef void (__cdecl *SetUInt)(void*,uint32_t,uint32_t);
        typedef void (__cdecl *SetBool)(void*,uint32_t,unsigned char);
        typedef void (__cdecl *SetFloat)(void*,uint32_t,float);
        typedef void (__cdecl *SetText)(void*,uint32_t,const char*);
        typedef void (__cdecl *SetMap)(void*,uint32_t,void*);
        switch(value_type) {
        case 0:((SetUInt)vtable[0x128/8])(destination,key,0);++request->writes;break;
        case 1:((SetBool)vtable[0x138/8])(destination,key,(unsigned char)(th_toboolean(state,-1)!=0));++request->writes;break;
        case 3: {
            double number=request->number(state,-1);
            uint32_t raw=mutable_map_integer_candidate(number);
            int32_t integer;
            memcpy(&integer,&raw,4);
            /* UCOMISD+JE takes the equal branch for unordered as well. */
            if(_isnan(number) || number==(double)integer)
                ((SetUInt)vtable[0x130/8])(destination,key,raw);
            else ((SetFloat)vtable[0x120/8])(destination,key,(float)number);
            ++request->writes;break;
        }
        case 4: {
            const char* value=mutable_map_text(state,-1,request);
            ((SetText)vtable[0x108/8])(destination,key,value);++request->writes;break;
        }
        case 5: {
            void* resolver=mutable_map_resolver(state,request,destination);
            void* child=mutable_map_empty_child(state,request,resolver);
            if(!child)return 0;
            ((SetMap)vtable[0xa8/8])(destination,key,child);++request->writes;
            int nested=th_gettop(state);
            if(mutable_map_from_table(state,nested,child,request,depth+1))return 0;
            break;
        }
        default:
            /* DB6350's known unmatched-type branch does not call a setter. */
            break;
        }
        th_settop(state,-2); /* keep lua_next's key */
    }
    return 0;
}

static int __cdecl mutable_map_dispatch_callback(LuaState* state) {
    MutableMapRequest* request=(MutableMapRequest*)th_userdata(state,1);
    if(!request)return th_lerror(state,"Missing mutable map request");
    int peak=LAB_AuxMapValidateTransport(request->seed,request->seed_count);
    if(!peak)return mutable_map_refuse(state,request,"invalid seed transport");
    aux_map_push(state,request->seed,request->seed_count,peak);
    request->seed_index=th_gettop(state);
    request->state=state;request->pending=1;request->phase=1;
    request->previous=mutable_map_active;mutable_map_active=request;
    /* Uses the retained shared argument pusher and Call implementation. The
     * wrapper's th_call hook appends a reference to this exact seeded table.
     */
    script_game_event_dispatch_callback(state);
    request->phase=2;
    mutable_map_from_table(state,request->seed_index,request->destination,request,0);
    request->phase=3;
    return 0;
}

__declspec(dllexport) int __cdecl LAB_GameEventsMutableMapVersion(void) {return 1;}

__declspec(dllexport) int __cdecl LAB_GameEventsDispatchMutableMapResult(
    LuaState* root,const char* name,const ScriptGameEventArgument* arguments,size_t count,
    const ScriptGameEventMap* maps,size_t map_count,const AuxMapOp* seed,uint32_t seed_count,
    void* destination,void* module,uint32_t profile_id,
    unsigned char* valid,unsigned char* truthiness,uint32_t* refused,uint32_t* phase) {
    if(!valid || !truthiness || !refused || !phase)return -1960;
    *valid=0;*truthiness=0;*refused=0;*phase=0;
    const MutableMapABI* abi=profile_id==2 ? &mutable_map_xp2 : NULL;
    if(!thread_api_ready || !abi || !abi->name_id_rva || root!=thread_registry_root || !root || th_gettop(root) ||
       !name || !*name || strnlen(name,256)>=256 || count>64 || (count && !arguments) ||
       map_count>count || (map_count && !maps) || !destination || !module ||
       !LAB_AuxMapValidateTransport(seed,seed_count))return -1960;
    for(size_t i=0;i<map_count;++i)
        if(maps[i].reserved || !LAB_AuxMapValidateTransport(maps[i].ops,maps[i].count))return -1960;
    uint32_t total_ops=seed_count;
    if(total_ops>MUTABLE_MAP_MAX_OPS)return -1960;
    for(size_t i=0;i<map_count;++i) {
        if(maps[i].count>MUTABLE_MAP_MAX_OPS-total_ops)return -1960;
        total_ops+=maps[i].count;
    }
    for(size_t i=0;i<count;++i)
        if(arguments[i].kind>2 || (arguments[i].kind==1 && arguments[i].value>255) ||
           (arguments[i].kind==2 && arguments[i].value>=map_count))return -1960;
    HMODULE havok=NULL;
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (LPCWSTR)(uintptr_t)th_checknumber,&havok))return -1960;
    FARPROC number=GetProcAddress(havok,"?lua_tonumber@@YANPEAUlua_State@@H@Z");
    if((uintptr_t)number!=(uintptr_t)havok+0x3d5f0)return -1960;
    MutableMapRequest request={0};
    memcpy(&request.number,&number,sizeof(number));
    request.base=(ScriptGameEventRequest){name,NULL,count,0,0,"Call",arguments,maps,map_count};
    request.seed=seed;request.seed_count=seed_count;request.destination=destination;
    request.module=(uintptr_t)module;request.abi=abi;
    MutableMapRequest* previous=mutable_map_active;
    if(!LAB_ScriptLockEnter())return -1601;
    int status=th_cpcall(root,mutable_map_dispatch_callback,&request);
    mutable_map_active=previous; /* also restore after longjmp */
    int left=LAB_ScriptLockLeave();
    *valid=request.base.valid;*truthiness=request.base.result;
    *refused=request.refused;*phase=request.phase;
    return left ? status : -1602;
}

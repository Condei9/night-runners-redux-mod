typedef unsigned char *Obj;
typedef unsigned long long Size;
extern char __ImageBase;
#define FN(r,t) ((t)(&__ImageBase - 0x33b4000 + (r)))
#define PTR(o,n) (*(Obj*)((o)+(n)))
#define INT(o,n) (*(int*)((o)+(n)))
typedef Obj (*Getter)(Obj);
typedef Obj (*Get2)(Obj,Obj);
typedef Obj (*GetIndex)(Obj,int,Obj);
static int count(Obj l){return l ? INT(l,24) : 0;}
static Obj at(Obj l,int i){return PTR(PTR(l,16),32+sizeof(Obj)*i);}
static Obj entries(void){Obj c=FN(0x7e5ed0,Getter)(0);return c?PTR(c,24):0;}
static int type(Obj engine){return FN(0x2fd5b0,int(*)(Obj,Obj))(engine,0);}
static Obj record(Obj list,int id){
    for(int i=0;i<count(list);i++){Obj e=at(list,i);if(e && e[16] && INT(e,20)==id)return e;}return 0;
}
static Obj catalogEngines(Obj entry){Obj data=entry?PTR(entry,32):0;return data?PTR(data,96):0;}
static Obj findPrefab(Obj list,int id,int *index){
    for(int i=0;i<count(list);i++){Obj e=at(list,i);if(e && type(e)==id){if(index)*index=i;return e;}}return 0;
}
static Obj root(Obj o){return FN(0x22fb70,Obj(*)(Obj,int))(o,0);}
static Obj target(Obj h){return h?FN(0x1e2080,Obj(*)(Obj))(h):0;}
static void drop(Obj h){if(h)FN(0x1e1ff0,void(*)(Obj))(h);}
typedef struct {Obj entry,origin,asset; void *load[2];} Donor;
static Donor donors[256];
static unsigned donorCount;
static Obj loadDonor(Obj e){
    for(unsigned i=0;i<donorCount;i++)if(target(donors[i].entry)==e)return target(donors[i].origin);
    if(donorCount>=256 || !PTR(e,16))return 0;
    Donor d={0};Obj origin=FN(0x765b60,Obj(*)(Obj,void*,Obj))(e,d.load,0);
    if(!origin)return 0;
    if(d.load[0])d.asset=root((Obj)d.load[0]);d.entry=root(e);d.origin=root(origin);donors[donorCount++]=d;return origin;
}
static Obj foreign(int id,Obj *owner,int *index){
    Obj all=entries();
    for(int i=0;i<count(all);i++){Obj e=at(all,i);if(!record(catalogEngines(e),id))continue;
        Obj o=loadDonor(e);Obj v=o?findPrefab(PTR(o,224),id,index):0;
        if(v){if(owner)*owner=o;return v;}
    }return 0;
}
static void store(Obj obj,int off,Obj value){
    FN(0x22fb30,void(*)(Obj,Obj*,Obj))(obj,(Obj*)(obj+off),value);
}
__declspec(dllexport) Obj menuList;
static Obj unionRoot,stockRoot,browseRoot;
static void resetMenu(void){
    menuList=0;drop(unionRoot);drop(stockRoot);drop(browseRoot);unionRoot=stockRoot=browseRoot=0;
}
static void append(Obj l,Obj e){
    Obj a=PTR(l,16);int n=count(l);store(a,32+8*n,e);INT(l,24)=n+1;
}
__declspec(dllexport) void build(Obj browser,Obj method){
    resetMenu();
    Obj car=browser?PTR(browser,32):0, origin=car?PTR(car,80):0, stock=origin?PTR(origin,224):0;
    if(stock){

        stockRoot=root(stock);browseRoot=root(browser);menuList=stock;
        Obj all=entries();int capacity=count(stock);
        for(int i=0;i<count(all);i++)capacity+=count(catalogEngines(at(all,i)));
        Obj src=PTR(stock,16);
        if(src && capacity>count(stock)){
            Obj list=FN(0x22ff10,Getter)(PTR(stock,0));unionRoot=root(list);
            Obj array=FN(0x22f410,Obj(*)(Obj,Size))(PTR(src,0),capacity);
            store(list,16,array);
            for(int i=0;i<count(stock);i++)append(list,at(stock,i));
            for(int i=0;i<count(all);i++){
                Obj e=at(all,i), spec=catalogEngines(e);
                for(int j=0;j<count(spec);j++){
                    Obj rec=at(spec,j);if(!rec||!rec[16])continue;
                    int id=INT(rec,20);if(!id||findPrefab(list,id,0))continue;
                    Obj o=loadDonor(e), p=o?findPrefab(PTR(o,224),id,0):0;
                    if(p)append(list,p);
                }
            }
            menuList=list;
        }
    }
    FN(0x77b1c0,void(*)(Obj,Obj))(browser,method);
}
__declspec(dllexport) Obj enumerate(Obj out,Obj list,Obj method){
    Obj browser=target(browseRoot);
    if(browser && browser[64] && !browser[65] && list==target(stockRoot) && menuList)list=menuList;
    return FN(0xb82990,Obj(*)(Obj,Obj,Obj))(out,list,method);
}
__declspec(dllexport) Obj stockParts(Obj origin,Obj parts,int index,Obj method){
    if(origin && menuList && index>=count(PTR(origin,224)) && index<count(menuList)){
        Obj prefab=at(menuList,index), donor=0;int nativeIndex=0;
        if(!prefab||!foreign(type(prefab),&donor,&nativeIndex))return 0;
        origin=donor;index=nativeIndex;
    }
    return FN(0x875aa0,Obj(*)(Obj,Obj,int,Obj))(origin,parts,index,method);
}
__declspec(dllexport) Obj resolveEngine(Obj stock,int requested){
    if(requested){Obj p=foreign(requested,0,0);if(p)return p;}
    return FN(0xb8a260,GetIndex)(stock,0,0);
}
__declspec(dllexport) Obj resolveCatalog(Obj entry,int requested,Obj method){
    Obj local=FN(0x4ea9e0,GetIndex)(entry,requested,method);
    if(!requested||(local && local[16] && INT(local,20)==requested))return local;
    Obj all=entries();
    for(int i=0;i<count(all);i++){Obj match=record(catalogEngines(at(all,i)),requested);if(match)return match;}
    return local;
}

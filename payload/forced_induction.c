typedef unsigned char *Obj;
extern char __ImageBase;
#define AT(r) ((Obj)&__ImageBase-INJECT+(r))
#define FN(r,t) ((t)AT(r))
#define P(o,n) (*(Obj*)((o)+(n)))
#define I(o,n) (*(int*)((o)+(n)))
typedef void (*Action)(Obj,Obj);
static void init(unsigned r){FN(0x1c0e50,void(*)(Obj))(AT(r));}
static Obj iface(void){init(0x2bd1540);return P(AT(0x2bd1540),0);}

static Obj method(Obj host,int slot){
 Obj k=P(host,0),ifc=iface(),offs=P(k,0x90);
 unsigned short n=*(unsigned short*)(k+0x126);
 for(unsigned short i=0;i<n;i++)
  if(P(offs,16*i)==ifc)return k+16*((long long)I(offs,16*i+8)+slot+0x13);
 return FN(0x1c9230,Obj(*)(Obj,Obj,int))(host,ifc,slot);
}
static int hostBool(Obj host,int slot,int amount){Obj m=method(host,slot);return ((unsigned char(*)(Obj,int,Obj))P(m,0))(host,amount,P(m,8));}
static void action(Obj host,int slot){FN(0x2860,void(*)(int,Obj,Obj))(slot,iface(),host);}
static void call(unsigned r,Obj o){FN(r,Action)(o,0);}
static Obj str(const char *s){return FN(0x20b2b0,Obj(*)(const char*))(s);}
__declspec(dllexport) int price(int i){return i==0?150000:i==1?290000:i==2?400000:i==3?340000:0;}
__declspec(dllexport) int induction(int i){return i==0?0:i==1?2:i==2?3:i==3?1:-1;}
__declspec(dllexport) int superchargerReady(Obj d){
 Obj rcc=FN(0x2f9430,Obj(*)(Obj,Obj))(d,0);
 if(!rcc||!P(rcc,0x728))return 0;
 Obj curves=P(rcc,0x3b8);int lvl=I(d,0xdc);
 if(!curves||lvl<0||lvl>=I(curves,0x18))return 0;
 return P(curves,0x20+8*lvl)!=0;
}
static Obj data(Obj b){Obj car=P(b,0x20);return car?P(car,0x158):0;}
static void refresh(Obj b){FN(0x77e530,void(*)(Obj,int,Obj))(b,0,0);call(0x77e000,b);}
static void active(Obj component,int on){if(!component)return;Obj go=FN(0x21745b0,Obj(*)(Obj,Obj))(component,0);if(go)FN(0x217ece0,void(*)(Obj,int,Obj))(go,on,0);}
static void text(Obj ui,int offset,const char *s){Obj c=P(ui,offset);if(c){active(c,1);FN(0x4ae200,void(*)(Obj,Obj,Obj))(c,str(s),0);}}
__declspec(dllexport) void ui(Obj b,Obj u,Obj mi){
 if(I(b,0x44)!=2){FN(0x77db90,void(*)(Obj,Obj,Obj))(b,u,mi);return;}
 if(!u)return;
 int i=I(b,0x4c),s=I(b,0x6c);
 Obj d=data(b);int here=d&&I(d,0xd4)==induction(i);
 text(u,0x280,i==0?"NATURALLY ASPIRATED":i==1?"SINGLE TURBO":i==2?"TWIN TURBO":"SUPERCHARGER");
 text(u,0x218,here?"INSTALLED":i==0?"150,000":i==1?"290,000":i==2?"400,000":"340,000");
 text(u,0x240,s==1?"CONFIRM PURCHASE?":s==2?"INSTALLED":s==3?"INSUFFICIENT FUNDS":s==4?"ALREADY INSTALLED":s==5?"UNAVAILABLE":here?"ALREADY INSTALLED":"PURCHASE");
 text(u,0x298,i==0?"1":i==1?"2":i==2?"3":"4");text(u,0x2a0,"4");
 active(P(u,0x290),i>0);active(P(u,0x288),i<3);
}
__declspec(dllexport) int purchase(Obj b){
 int i=I(b,0x4c),v=induction(i),cost=price(i);
 Obj d=data(b),host=P(b,0x18),car=P(b,0x20);
 if(v<0||!d||!host||!P(d,0x78))return 5;
 if(I(d,0xd4)==v)return 4;

 if(v==1 && !superchargerReady(d))return 5;
 Obj god=FN(0x848ac0,Obj(*)(Obj))(0);
 if(!god||!P(god,0x508))return 5;
 if(!hostBool(host,24,cost))return 3;

 init(0x2c14250);init(0x2c135e0);
 Obj id=FN(0x15da7c0,Obj(*)(Obj,Obj))(car+0x48,0);
 Obj key=FN(0x1439e60,Obj(*)(Obj,Obj,Obj))(P(AT(0x2c14250),0),id,0);
 if(!key)return 5;
 if(!hostBool(host,25,cost))return 3;
 FN(0x9896b0,void(*)(Obj,int,Obj,Obj))(key,v,P(god,0x508),P(AT(0x2c135e0),0));
 I(d,0xd4)=v;

 FN(0x403770,void(*)(Obj,int,int,Obj,Obj))(car,0,1,0,0);

 FN(0x2f9a90,void(*)(Obj,Obj))(d,0);
 action(host,47);action(host,60);
 return 2;
}
__declspec(dllexport) void enter(Obj b){
 I(b,0x44)=2;I(b,0x6c)=0;
 Obj d=data(b);int v=d?I(d,0xd4):0;
 I(b,0x4c)=v==2?1:v==3?2:v==1?3:0;
 I(b,0x50)=0;I(b,0x54)=0;I(b,0x58)=0;
 call(0x77a8c0,b);refresh(b);
}
__declspec(dllexport) unsigned char beginHub(Obj b,Obj host,Obj car,Obj orbit,int start,Obj back,Obj exit,Obj mi,Obj hub){
 Obj slot=FN(0x781a10,Obj(*)(Obj,Obj))(hub,0);
 int forced=slot && I(slot,0x28)==5;
 unsigned char ok=FN(0x77fc60,unsigned char(*)(Obj,Obj,Obj,Obj,int,Obj,Obj,Obj))(b,host,car,orbit,forced?0:start,back,exit,mi);
 if(ok&&forced){I(b,0x48)=1;enter(b);}return ok;
}
__declspec(dllexport) void tick(Obj b,Obj mi){
 if(I(b,0x44)!=2){FN(0x77f630,Action)(b,mi);return;}
 if(FN(0x683210,unsigned char(*)(int,Obj))(0xcf,0)){
   if(I(b,0x6c)){I(b,0x6c)=0;refresh(b);call(0x77a8c0,b);}
   else {I(b,0x6c)=0;call(P(b,0x80)?0x77e940:0x77e890,b);}return;
 }
 int step=0;
 if(I(b,0x6c)!=1 && FN(0x7740b0,unsigned char(*)(Obj,int,int,int*,Obj))(b+0x50,0xca,0xcb,&step,0)){
   int i=I(b,0x4c)+step;if(i>=0&&i<4){I(b,0x4c)=i;I(b,0x6c)=0;refresh(b);action(P(b,0x18),58);}return;
 }
 if(!FN(0x683210,unsigned char(*)(int,Obj))(0xce,0))return;
 int i=I(b,0x4c);Obj d=data(b);

 if(I(b,0x6c)==1){
   I(b,0x6c)=purchase(b);

   if(I(b,0x6c)==2){I(b,0x6c)=0;call(P(b,0x80)?0x77e940:0x77e890,b);return;}
 }
 else if(d&&I(d,0xd4)==induction(i))I(b,0x6c)=4;
 else if(I(b,0x6c))I(b,0x6c)=0;
 else I(b,0x6c)=1;
 refresh(b);call(0x77a8c0,b);
}

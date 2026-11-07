typedef unsigned char *Obj;
typedef struct {float x,y,z;} Vec;
extern char __ImageBase;
#define AT(r) ((Obj)&__ImageBase-WHEEL_RVA+(r))
#define FN(r,t) ((t)AT(r))
#define P(o,n) (*(Obj*)((o)+(n)))
#define I(o,n) (*(int*)((o)+(n)))
#define F(o,n) (*(float*)((o)+(n)))
typedef Obj (*Getter)(Obj,Obj);
typedef void (*Setter)(Obj,const Vec*,Obj);
typedef Vec* (*ReadVec)(Vec*,Obj,Obj);
typedef struct {Obj car,ext,anchor[2];float last[2],original[2];int moved[2],frame,on;} Record;

#define slots ((Record*)AT(CACHE_RVA))
static int exact(Obj p,const char* text){
 if(!p||!FN(0x21872a0,int(*)(Obj,Obj))(p,0))return 0;
 Obj s=FN(0x2187190,Getter)(p,0);if(!s)return 0;
 int i=0;while(text[i]){if(i>=I(s,16)||((unsigned short*)(s+20))[i]!=text[i])return 0;i++;}
 return i==I(s,16)||((unsigned short*)(s+20))[i]=='(';
}
static int fortune(Obj p){
 if(!p||!FN(0x21872a0,int(*)(Obj,Obj))(p,0))return 0;
 int type=I(p,0x40);
 if(type==34)return exact(p,"VEILSIDE FORTUNE BODYKIT");
 if(type==8)return exact(p,"VS FORTUNE STOCK REAR FENDER");
 if(type==15)return exact(p,"VS FORTUNE STOCK DOORS");
 return 0;
}

static int villain(Obj p){
 if(!p||!FN(0x21872a0,int(*)(Obj,Obj))(p,0))return 0;
 int type=I(p,0x40);
 if(type==34)return exact(p,"VILLAIN");
 if(type==8)return exact(p,"DLV STOCK REAR FENDER");
 return 0;
}

static float offset(Record*rec,int front){
 if(!rec)return 0;
 if(rec->on==1)return front?0:0.05f;
 if(rec->on==2)return 0.03f;
 return 0;
}
static Record* record(Obj car){
 Obj origin=P(car,0x50);if(!origin)return 0;
 int model=I(origin,0x74);if(model!=54&&model!=41)return 0;
 int(*kit)(Obj)=model==54?fortune:villain;int on=model==54?1:2;
 Obj ext=P(car,0x1c0);
 int frame=FN(0x2190ba0,int(*)(Obj))(0);
 Record *rec=0;
 for(int i=0;i<6;i++){if(slots[i].car==car){rec=slots+i;break;}if(!rec||slots[i].frame<rec->frame)rec=slots+i;}
 if(rec->car==car && rec->ext==ext && (unsigned)(frame-rec->frame)<8)return rec;
 if(rec->car!=car||rec->ext!=ext){rec->moved[0]=rec->moved[1]=0;rec->car=car;rec->ext=ext;}
 rec->frame=frame;rec->on=(kit(P(car,0x2a0))||kit(P(car,0x138)))?on:0;
 if(!rec->on && ext){

  FN(0x1c0e50,void(*)(Obj))(AT(0x2bdf768));
  Obj go=FN(0x21745b0,Getter)(ext,0);
  Obj a=go?FN(0xa194e0,Obj(*)(Obj,int,Obj))(go,0,*(Obj*)AT(0x2bdf768)):0;
  if(a)for(int i=0;i<I(a,24);i++)if(kit(P(a,32+i*8))){rec->on=on;break;}
 }
 return rec;
}

__declspec(dllexport) void collider(Obj tr,const Vec*stock,Obj car,int side){
 Vec v=*stock;float d=offset(record(car),side>=2);
 if(d)v.x+=(side&1)?d:-d;
 FN(0x2198240,Setter)(tr,&v,0);
}
__declspec(dllexport) void model(Obj part,const Vec*stock,Obj car,int index){

 FN(0x2198240,Setter)(part,stock,0);

 if(index<0||index>3)return;
 float d=offset(record(car),index<2);if(!d)return;
 Obj body=FN(0x2174720,Getter)(car,0);if(!body)return;
 Vec right,pos;
 FN(0x2197aa0,ReadVec)(&right,body,0);
 float length2=right.x*right.x+right.y*right.y+right.z*right.z;
 if(!(length2>=0.999f && length2<=1.001f))return;
 FN(0x2197a30,ReadVec)(&pos,part,0);
 float distance=(index&1)?d:-d;
 pos.x+=right.x*distance;pos.y+=right.y*distance;pos.z+=right.z*distance;
 FN(0x2198550,Setter)(part,&pos,0);
}
int _fltused=0;

static const char kitNames[][2][28]={
 {"VEILSIDE FORTUNE BODYKIT","VEILSIDE FORTUNE"},{"SDF BODYKIT","SDF"},{"SUPERGREDDY3 BODYKIT","SUPERGREDDY3"},
 {"GENKI7 BODYKIT","GENKI7"},{"AC987 BODYKIT","AC987"},{"SB7 BODYKIT","SB7"},{"SCOOT RACING BODYKIT","SCOOT RACING"},
 {"GREDDY8 BODYKIT","GREDDY8"},{"VILLAIN","VILLAIN"}};
__declspec(dllexport) Obj kitLabel(Obj part){
 if(!part||!FN(0x21872a0,int(*)(Obj,Obj))(part,0)||I(part,0x40)!=34)return 0;
 for(int i=0;i<(int)(sizeof kitNames/sizeof kitNames[0]);i++)
  if(exact(part,kitNames[i][0]))return FN(0x20b2b0,Obj(*)(const char*))(kitNames[i][1]);
 return 0;
}

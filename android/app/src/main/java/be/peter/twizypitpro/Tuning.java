package be.peter.twizypitpro;
import org.json.*;
import java.util.*;

/** Register targets, adapted from M. Balzer's OVMS (2017, MIT).
 * See reference/rt_sevcon_tuning.cpp and the included OVMS license.
 * This compiler does not transmit and does not qualify hardware. */
final class Tuning {
    private static final long[] C80={80,7250,900,400,800,1250,89,8050,550,55000,57000,0,450000,450,540,12182,13000,4608};
    private static final long[] C45={45,5814,1307,686,1386,2686,56,7200,900,32500,33000,500,270000,290,330,7050,7650,2688};
    private static long scale(long d,long base,long v,long min,long max){return v==base?d:Math.max(min,Math.min(max,d*v/base));}
    private static void add(JSONArray rows,int index,int sub,Long raw,String keys,int width,boolean signed) {
        if(raw!=null&&(raw<(signed?-(1L<<(width*8-1)):0)||raw>=(1L<<(width*8-(signed?1:0)))))throw new IllegalArgumentException("Registerwaarde buiten datatype");
        JSONObject r=new JSONObject();Model.put(r,"index",index);Model.put(r,"sub",sub);Model.put(r,"address",String.format(Locale.ROOT,"%04X:%02X",index,sub));Model.put(r,"width",width);Model.put(r,"signed",signed);Model.put(r,"raw",raw==null?JSONObject.NULL:raw);Model.put(r,"keys",new JSONArray(Arrays.asList(keys.split(","))));Model.put(r,"key",keys.replace(","," / "));rows.put(r);
    }
    private static void add(JSONArray rows,int index,int sub,long raw,String keys){add(rows,index,sub,raw,keys,2,false);}
    static JSONArray targets(Model model,JSONObject v,String type,Long flags) {
        if(!type.equals("80")&&!type.equals("45"))throw new IllegalArgumentException("Onbekende aandrijflijn");
        model.validate(v,type);boolean t45=type.equals("45");long[] c=t45?C45:C80;JSONArray rows=new JSONArray();
        String[] simple={"drive","neutral","brake","ramp_start","ramp_accel","ramp_decel","ramp_neutral","ramp_brake","rampl_accel","rampl_decel","smooth"};
        int[] indices={0x2920,0x2920,0x2920,0x291c,0x2920,0x2920,0x2920,0x2920,0x2920,0x2920,0x290a},subs={1,3,4,2,7,11,13,14,15,16,3};
        long[] def={1000,t45?209:182,t45?209:182,t45?300:400,t45?2083:2500,2000,4000,4000,6000,6000,800},base={100,t45?21:18,t45?21:18,t45?30:40,t45?21:25,20,40,40,30,30,70},min={0,0,0,10,10,10,10,10,0,0,0},max={1000,1000,1000,10000,10000,10000,10000,10000,20000,20000,1000};
        for(int i=0;i<simple.length;i++)add(rows,indices[i],subs[i],scale(def[i],base[i],v.optLong(simple[i]),min[i],max[i]),simple[i],2,i==10);
        add(rows,0x290a,1,1+v.optLong("smooth")/10,"smooth",1,false);
        long rpm=scale(c[1],c[0],v.optLong("speed"),400,65535),warning=scale(c[7],c[6],v.optLong("warn"),400,65535);
        if(warning<c[8])throw new IllegalArgumentException("Waarschuwingssnelheid te laag voor hysterese");
        add(rows,0x3813,0x34,warning,"warn");add(rows,0x3813,0x3c,warning-c[8],"warn");
        add(rows,0x2920,5,rpm,"speed");add(rows,0x2920,6,Math.min(rpm,c[2]),"speed");
        int[] speedSubs={0x33,0x35,0x3b,0x2d};long[] offsets={c[3],c[4],c[5],c[5]+1500};
        for(int i=0;i<4;i++)add(rows,0x3813,speedSubs[i],rpm+offsets[i],"speed");
        add(rows,0x4624,0,rpm+c[5]+2500,"speed");
        add(rows,0x4641,2,scale(c[13],100,v.optLong("current"),0,c[14]),"current");
        add(rows,0x6075,0,scale(c[12],100,v.optLong("current"),0,c[14]*1000),"current",4,false);
        long torque=scale(c[9],100,v.optLong("torque"),10000,200000),low=scale(c[15],100,v.optLong("power_low"),500,200000),high=scale(c[16],100,v.optLong("power_high"),500,200000);
        add(rows,0x6076,0,torque+c[11],"torque",4,false);add(rows,0x2916,1,v.optInt("torque")==100?c[10]:torque+c[11],"torque",4,false);
        add(rows,0x3813,0x23,v.optInt("power_low")==100&&v.optInt("power_high")==100?c[17]:(long)(Math.max(low,high)*.353),"power_low,power_high",2,true);
        long[] fmap=t45?new long[]{480,8192,576,8960}:new long[]{964,9728,1122,9984};
        long[] pmap;
        if(rpm==c[1]&&torque==c[9]&&low==c[15]&&high==c[16])pmap=t45?new long[]{520,0,520,2050,437,2500,363,3000,314,3500,279,4000,247,4500,226,5000,195,6000}:new long[]{880,0,880,2115,659,2700,608,3000,516,3500,421,4500,360,5500,307,6500,273,7250};
        else {
            long rpm2=Math.min(low*9549/torque,rpm),trq=(torque*16+500)/1000;
            if(1000/9.549*10000*10000*(v.optDouble("current")/100)/high<rpm||rpm2<=0)throw new IllegalArgumentException("Niet ondersteunde breakdown-configuratie");
            if(trq>fmap[2])fmap=t45?new long[]{656,9600,1328,11901}:new long[]{1122,10089,2240,11901};
            pmap=new long[18];pmap[0]=trq;long drpm=(rpm-rpm2)/21,dpwr=(high-low)/21;int[] fib={0,1,2,3,5,8,13,21};
            for(int i=0;i<8;i++){long pr=rpm2+fib[i]*drpm,pp=low+fib[i]*dpwr;pmap[2+i*2]=(((pp*9549+(pr>>1))/pr)*16+500)/1000;pmap[3+i*2]=pr;}
        }
        String powerkeys="speed,torque,power_low,power_high,current";
        for(int i=0;i<18;i++)add(rows,0x4611,i+1,pmap[i],powerkeys);
        for(int i=0;i<4;i++)add(rows,0x4610,15+i,fmap[i],powerkeys);
        long[] mapspeed=t45?new long[]{4357,5083,6535,8714}:new long[]{3000,3500,4500,6000};int[] speeds={33,39,50,66},bases={0x24,0x1b,7};String[] letters={"D","N","B"};
        for(int m=0;m<3;m++){long previous=-1;for(int i=0;i<4;i++){
            String levelkey=letters[m]+"_level"+(i+1),speedkey=letters[m]+"_speed"+(i+1);
            add(rows,0x3813,bases[m]+i*2,scale(32767,100,v.optLong(levelkey),0,32767),levelkey);
            long point=scale(mapspeed[i],speeds[i],v.optLong(speedkey),0,65535);
            if(point<=previous)throw new IllegalArgumentException("Omgerekende kaartpunten lopen niet op");previous=point;
            add(rows,0x3813,bases[m]+i*2+1,point,speedkey);
        }}
        add(rows,0x3813,5,scale(1024,100,v.optLong("brakelight_off"),64,1024),"brakelight_off");add(rows,0x3813,6,scale(1024,100,v.optLong("brakelight_on"),64,1024),"brakelight_on");
        if(flags!=null&&(flags<0||flags>65535))throw new IllegalArgumentException("Ongeldige control flags");
        boolean enabled=v.optInt("brakelight_on")!=100||v.optInt("brakelight_off")!=100;
        add(rows,0x2910,1,flags==null?null:(enabled?flags|0x2000:flags&~0x2000),"brakelight_on,brakelight_off",2,false);
        return rows;
    }
    static JSONArray compare(Model model,JSONObject values,String type,JSONObject scan){
        Map<String,JSONObject> previous=new HashMap<>();
        if(scan!=null&&scan.optString("mode").equals("live-usb")){
            JSONArray rs=scan.optJSONArray("registers");if(rs!=null)for(int i=0;i<rs.length();i++){JSONObject r=rs.optJSONObject(i);if(r!=null&&!r.isNull("raw")&&!r.has("error"))previous.put(r.optString("address"),r);}
        }
        JSONObject control=previous.get("2910:01");Long flags=control!=null&&control.optInt("width")==2?control.optLong("raw"):null;
        JSONArray rows=targets(model,values,type,flags);
        for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i),old=previous.get(r.optString("address"));boolean known=old!=null&&old.optInt("width")==r.optInt("width");Model.put(r,"before",known?old.optLong("raw"):JSONObject.NULL);Model.put(r,"verified_width",known);Model.put(r,"changed",!known||r.isNull("raw")||r.optLong("raw")!=old.optLong("raw"));}
        return rows;
    }
}

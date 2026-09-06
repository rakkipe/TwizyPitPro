package be.peter.twizypitpro;
import org.json.*;
import java.util.*;

/** Passive Twizy frame decoding. OVMS/M. Balzer MIT reference: rt_can.cpp. */
final class CanTelemetry {
    static Map<Integer,byte[]> parse(String text){
        Map<Integer,byte[]> frames=new LinkedHashMap<>();
        for(String line:text.replace('\r','\n').replace(">","").split("\n")){
            line=line.trim();if(line.startsWith("FRAME "))line=line.substring(6);
            if(!line.matches("[0-9a-fA-F ]+"))continue;String compact=line.replace(" ","");if(compact.length()<5)continue;
            int id=Integer.parseInt(compact.substring(0,3),16);String data=compact.substring(3);
            if(data.length()%2==1){int size=Character.digit(data.charAt(0),16);data=data.substring(1);if(size!=8||data.length()!=16)continue;}
            if(id>0x7ff||data.length()!=16)continue;byte[] frame=new byte[8];for(int i=0;i<8;i++)frame[i]=(byte)Integer.parseInt(data.substring(i*2,i*2+2),16);frames.put(id,frame);
        }return frames;
    }
    static JSONObject decode(Map<Integer,byte[]> frames){
        JSONObject o=new JSONObject();Model.put(o,"frame_count",frames.size());
        for(Map.Entry<Integer,byte[]> e:frames.entrySet()){
            byte[] data=e.getValue();if(data.length!=8)continue;int[] b=new int[8];for(int i=0;i<8;i++)b[i]=data[i]&255;
            switch(e.getKey()){
                case 0x155:if(b[3]==0x54){int soc=b[4]*256+b[5],current=(b[1]&15)*256+b[2];if(soc>0&&soc<=40000)Model.put(o,"soc",(soc>>2)/100.0);if(current>0&&current<0xf00)Model.put(o,"current",(2000-current)/4.0);}break;
                case 0x599:int speed=b[6]*256+b[7];if(speed!=65535)Model.put(o,"speed",speed/100.0);break;
                case 0x55f:if(b[5]!=255){int v1=(b[5]<<4)|(b[6]>>4),v2=((b[6]&15)<<8)|b[7];if(v1>0&&v1<4095&&v2>0&&v2<4095)Model.put(o,"voltage",((v1+v2+1)>>1)/64.0);}break;
                case 0x597:Model.put(o,"key_on",(b[1]&16)!=0);Model.put(o,"charging",(b[1]&32)!=0);Model.put(o,"transition",(b[1]&64)!=0);break;
                case 0x59b:Model.put(o,"gear",b[0]==0?"N":b[0]==0x80?"D":b[0]==8?"R":"unknown");Model.put(o,"go",(b[1]&8)!=0);Model.put(o,"footbrake",(b[1]&1)!=0);Model.put(o,"throttle_raw",b[3]);break;
                case 0x554:int hottest=-1000;for(int v:b)if(v>0&&v<240)hottest=Math.max(hottest,v-40);if(hottest>-1000)Model.put(o,"battery_temp",hottest);break;
                default:break;
            }
        }
        if(o.has("voltage")&&o.has("current"))Model.put(o,"power",o.optDouble("voltage")*o.optDouble("current")/1000);
        return o;
    }
}

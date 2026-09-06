package be.peter.twizypitpro;

import com.hoho.android.usbserial.driver.UsbSerialPort;
import android.os.SystemClock;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.function.Predicate;

/** Bounded CANopen upload only. No download, fault-clear or NMT API. */
final class CanReader implements Closeable {
    interface Transport { byte[] exchange(byte[] request,Predicate<byte[]> match) throws IOException; }
    private final UsbSerialPort port;
    private final boolean m5;
    private final Transport transport;
    CanReader(UsbSerialPort port,boolean m5){this.port=port;this.m5=m5;this.transport=this::serialExchange;}
    CanReader(Transport transport){this.port=null;this.m5=false;this.transport=transport;}
    void initialize() throws IOException {
        if(m5) {
            SystemClock.sleep(1500);
            if(!command("HELLO",3500).contains("PITBRIDGE 1 READONLY"))throw new IOException("PitBridge READONLY niet herkend. Gebruik de meegeleverde M5-firmware.");
        } else {
            command("ATZ",3500);
            for(String cmd:new String[]{"ATE0","ATL0","ATS1","ATH1","ATSP6","ATCAF0","ATCFC0","ATD0","ATV1","ATSH601","ATCRA581"})
                if(!command(cmd,1800).contains("OK"))throw new IOException("Adapter ondersteunt "+cmd+" niet.");
            String id=command("ATI",1800).toUpperCase(Locale.ROOT);
            if(!(id.contains("ELM")||id.contains("STN")||id.contains("VLINKER")||id.contains("OBDLINK")))throw new IOException("Onbekende adapter.");
            String protocol=command("ATDPN",1800).replace(">","").trim();
            if(!protocol.equals("6")&&!protocol.equals("A6"))throw new IOException("CAN-protocol is geen 11-bit / 500 kbit/s.");
        }
    }
    private String command(String command,int timeout) throws IOException {
        byte[] buffer=new byte[512];
        try {port.purgeHwBuffers(false,true);}catch(UnsupportedOperationException ignored){}
        port.write((command+(m5?"\n":"\r")).getBytes(StandardCharsets.US_ASCII),1000);
        long end=System.nanoTime()+timeout*1000000L;
        ByteArrayOutputStream out=new ByteArrayOutputStream();
        while(System.nanoTime()<end) {
            int n=port.read(buffer,100);
            if(n>0)out.write(buffer,0,n);
            if(out.size()>32768)throw new IOException("Adapterantwoord te groot.");
            String text=out.toString("US-ASCII");
            if(!m5&&text.contains(">"))return text;
            if(m5&&(text.contains("PITBRIDGE 1 READONLY")||text.contains("RX ")||text.contains("ERR"))&&text.contains("\n"))return text;
        }
        throw new IOException("Geen passend adapterantwoord; controleer USB en CAN.");
    }
    static boolean allowed(byte[] payload){return payload.length==8&&(payload[0]==0x40||payload[0]==0x60||payload[0]==0x70);}
    private byte[] exchange(byte[] payload,Predicate<byte[]> match) throws IOException {
        if(!allowed(payload))throw new IOException("Uitsluitend SDO-upload toegestaan.");
        return transport.exchange(payload,match);
    }
    private byte[] serialExchange(byte[] payload,Predicate<byte[]> match) throws IOException {
        if(!allowed(payload))throw new IOException("Schrijfcommando geblokkeerd.");
        StringBuilder hex=new StringBuilder();for(byte b:payload)hex.append(String.format(Locale.ROOT,"%02X",b&255));
        String text=command((m5?"READ ":"")+hex,1800);
        for(String line:text.replace('\r','\n').replace(">","").split("\n")) {
            line=line.trim();if(m5&&line.startsWith("RX "))line=line.substring(3);
            if(!line.matches("[0-9a-fA-F ]+"))continue;
            String compact=line.replace(" ","");if(compact.length()<5)continue;
            int id=Integer.parseInt(compact.substring(0,3),16);String data=compact.substring(3);
            if(data.length()%2==1){int size=Character.digit(data.charAt(0),16);data=data.substring(1);if(size>8||data.length()!=size*2)continue;}
            if(id!=0x581||data.length()!=16)continue;
            byte[] frame=new byte[8];for(int i=0;i<8;i++)frame[i]=(byte)Integer.parseInt(data.substring(i*2,i*2+2),16);
            if(match.test(frame))return frame;
        }
        throw new IOException("Geen SDO-antwoord voor deze aanvraag.");
    }
    byte[] upload(int index,int sub) throws IOException {
        byte[] header={(byte)index,(byte)(index>>8),(byte)sub};
        byte[] request={0x40,header[0],header[1],header[2],0,0,0,0};
        Predicate<byte[]> same=b->b.length==8&&b[1]==header[0]&&b[2]==header[1]&&b[3]==header[2];
        byte[] response=exchange(request,b->same.test(b)&&((b[0]&255)==0x80||(b[0]&0xe0)==0x40));
        abort(response);int cmd=response[0]&255;
        if((cmd&2)!=0)return Arrays.copyOfRange(response,4,4+((cmd&1)!=0?4-((cmd>>2)&3):4));
        long expected=(cmd&1)!=0?unsigned(Arrays.copyOfRange(response,4,8)):-1;
        if(expected>256)throw new IOException("SDO-object te lang.");
        ByteArrayOutputStream out=new ByteArrayOutputStream();int toggle=0;
        for(int n=0;n<39;n++) {
            byte[] segment=exchange(new byte[]{(byte)(0x60|(toggle<<4)),0,0,0,0,0,0,0},b->b.length==8&&(((b[0]&255)==0x80&&same.test(b))||(b[0]&0xe0)==0));
            abort(segment);int c=segment[0]&255;
            if(((c>>4)&1)!=toggle)throw new IOException("SDO segment-toggle fout.");
            boolean last=(c&1)!=0;int unused=(c>>1)&7;
            if(!last&&unused!=0)throw new IOException("Ongeldige segmentlengte.");
            out.write(segment,1,last?7-unused:7);
            if(out.size()>256)throw new IOException("SDO-leeslimiet overschreden.");
            if(last){if(expected>=0&&expected!=out.size())throw new IOException("SDO-lengte klopt niet.");return out.toByteArray();}
            toggle^=1;
        }
        throw new IOException("SDO-segmenten niet afgerond.");
    }
    static long unsigned(byte[] bytes){long v=0;for(int i=0;i<bytes.length;i++)v|=(bytes[i]&255L)<<(8*i);return v;}
    private static void abort(byte[] response) throws IOException {if((response[0]&255)==0x80)throw new IOException(String.format(Locale.ROOT,"SDO geweigerd: 0x%08X",unsigned(Arrays.copyOfRange(response,4,8))));}
    long number(int index,int sub,int width,boolean signed) throws IOException {
        byte[] bytes=upload(index,sub);if(bytes.length!=width)throw new IOException(String.format(Locale.ROOT,"%04X:%02X: verkeerde registerbreedte",index,sub));
        long result=unsigned(bytes);if(signed&&(bytes[width-1]&0x80)!=0)result-=1L<<(width*8);return result;
    }
    JSONObject identity() throws IOException {
        JSONObject result=new JSONObject();JSONArray errors=new JSONArray();String[] names={"name","hardware","software"};
        for(int i=0;i<3;i++)try {
            byte[] bytes=upload(0x1008+i,0);boolean printable=true;for(byte b:bytes)if(b!=0&&(b<32||b>126))printable=false;
            String value;
            if(printable)value=new String(bytes,StandardCharsets.US_ASCII).replace("\0","");
            else {StringBuilder hex=new StringBuilder("0x");for(int n=bytes.length-1;n>=0;n--)hex.append(String.format(Locale.ROOT,"%02X",bytes[n]&255));value=hex.toString();}
            Model.put(result,names[i],value);
        }catch(IOException e){errors.put(e.getMessage());}
        names=new String[]{"vendor","product","revision","serial"};
        for(int i=0;i<4;i++)try {Model.put(result,names[i],number(0x1018,i+1,4,false));}catch(IOException e){errors.put(e.getMessage());}
        if(result.length()==0)throw new IOException("Geen controlleridentiteit uitgelezen.");
        Model.put(result,"source","live-usb");Model.put(result,"errors",errors);return result;
    }
    JSONObject diagnose() throws IOException {
        JSONObject report=new JSONObject();Model.put(report,"identity",identity());Model.put(report,"at",Model.now());Model.put(report,"mode","live-usb");
        JSONArray rows=new JSONArray(),errors=new JSONArray();
        int[][] registers={{0x1001,0,1},{0x6041,0,2},{0x1003,0,1}};
        for(int[] reg:registers)try {
            long value=number(reg[0],reg[1],reg[2],false);row(rows,reg[0],reg[1],reg[2],value);
            if(reg[0]==0x1003)for(int i=1;i<=Math.min(value,16);i++)try{row(rows,0x1003,i,4,number(0x1003,i,4,false));}catch(IOException e){errors.put(e.getMessage());}
        }catch(IOException e){errors.put(e.getMessage());}
        JSONObject id=report.optJSONObject("identity");String model=Model.modelOf(id);
        if(Model.known(model,id.optString("software"),id.optLong("revision"))) {
            int[][] typed={{0x2920,1,2},{0x2920,3,2},{0x2920,4,2},{0x291c,2,2},{0x2920,7,2},{0x2920,11,2},{0x2920,13,2},{0x2920,14,2},{0x2920,15,2},{0x2920,16,2},{0x290a,3,2},{0x290a,1,1}};
            for(int[] reg:typed)try{row(rows,reg[0],reg[1],reg[2],number(reg[0],reg[1],reg[2],false));}catch(IOException e){errors.put(e.getMessage());}
        }
        Model.put(report,"registers",rows);Model.put(report,"errors",errors);Model.put(report,"complete",errors.length()==0&&id.optJSONArray("errors").length()==0);
        Model.put(report,"scope","SEVCON CANopen. Geen volledige Renault ECU/BMS/airbagscan. Fouthistorie is niet automatisch een actuele storing.");return report;
    }
    private static void row(JSONArray rows,int index,int sub,int width,long value){JSONObject row=new JSONObject();Model.put(row,"address",String.format(Locale.ROOT,"%04X:%02X",index,sub));Model.put(row,"width",width);Model.put(row,"raw",value);rows.put(row);}
    JSONObject sample() throws IOException {
        JSONObject sample=new JSONObject();JSONArray errors=new JSONArray();
        int[][] regs={{0x606c,0,4},{0x4600,3,2},{0x5100,4,1}};String[] names={"rpm","motor_temp","controller_temp"};
        for(int i=0;i<3;i++)try{Model.put(sample,names[i],number(regs[i][0],regs[i][1],regs[i][2],true));}catch(IOException e){errors.put(e.getMessage());}
        if(sample.length()==0)throw new IOException("Geen actuele telemetrie; uitlezing gestopt.");
        if(!m5)try{java.util.regex.Matcher match=java.util.regex.Pattern.compile("(\\d{1,2}\\.\\d{1,2})V",2).matcher(command("ATRV",1800));if(match.find())Model.put(sample,"aux",Double.parseDouble(match.group(1)));}catch(IOException e){errors.put(e.getMessage());}
        Model.put(sample,"source","live-usb");Model.put(sample,"at",Model.now());Model.put(sample,"errors",errors);return sample;
    }
    @Override public void close() throws IOException {if(port!=null)port.close();}
}

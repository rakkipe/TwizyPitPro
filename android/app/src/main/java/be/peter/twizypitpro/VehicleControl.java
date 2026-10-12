package be.peter.twizypitpro;

import org.json.*;
import java.io.*;
import java.util.*;
import java.util.function.BooleanSupplier;

/** Narrow vLinker control port. No arbitrary command is exposed to the UI. */
final class VehicleControl implements VehicleWriter.Port {
    interface Bus {
        boolean writable();
        String command(String value,int timeout) throws IOException;
        JSONObject identity() throws IOException;
        long number(int index,int sub,int width,boolean signed) throws IOException;
        List<Frame> capture() throws IOException;
        long clock();
    }
    static final class Frame {
        final int id; final byte[] data; final long at;
        Frame(int id,byte[] data,long at){this.id=id;this.data=data.clone();this.at=at;}
    }
    static final class WriteAbort extends IOException {
        final long code; Long detail;
        WriteAbort(long code){super(String.format(Locale.ROOT,"SDO-write geweigerd: %08X",code));this.code=code;}
    }
    private final Bus bus;
    private final BooleanSupplier active;
    private JSONObject expected;
    private long deadline=-1;
    VehicleControl(Bus bus,BooleanSupplier active) throws IOException {
        if(!bus.writable())throw new IOException("Schrijven vereist vLinker USB; M5 blijft alleen uitlezen.");
        this.bus=bus;this.active=active;
    }
    private void check() throws IOException {if(!active.getAsBoolean())throw new IOException("Actie onderbroken; bekijk het hersteljournaal na opnieuw verbinden.");}
    private String command(String value) throws IOException {check();return bus.command(value,1800);}
    private void ok(String value) throws IOException {if(!command(value).toUpperCase(Locale.ROOT).contains("OK"))throw new IOException("Adapterinstelling geweigerd: "+value);}
    public JSONObject identity() throws IOException {check();return bus.identity();}
    public void bind(JSONObject identity){expected=Model.copy(identity);}
    public long read(JSONObject row) throws IOException {check();return bus.number(row.optInt("index"),row.optInt("sub"),row.optInt("width"),row.optBoolean("signed"));}
    private long number(int index,int sub,int width,boolean signed) throws IOException {check();return bus.number(index,sub,width,signed);}
    public int level() throws IOException {return (int)number(0x5000,1,1,false);}
    public int state() throws IOException {return (int)number(0x5110,0,1,false);}
    public void guard(boolean preop,boolean accessOnly) throws IOException {
        check();
        if(expected!=null&&!VehicleWriter.fingerprint(identity()).equals(VehicleWriter.fingerprint(expected)))throw new IOException("Controller gewisseld.");
        if(state()!=(preop?127:5))throw new IOException("Controllerstand gewijzigd.");
        if(number(0x1001,0,1,false)!=0||number(0x606c,0,4,true)!=0)throw new IOException("Foutregister actief of motor draait.");
        java.util.regex.Matcher voltage=java.util.regex.Pattern.compile("\\b(\\d{1,2}\\.\\d{1,2})V\\b",2).matcher(command("ATRV"));
        if(!voltage.find())throw new IOException("12V-voeding niet bevestigd.");
        double v=Double.parseDouble(voltage.group(1));if(v<12||v>15)throw new IOException("Stabiele voeding van 12–15 V vereist.");
        List<Frame> frames=bus.capture();long now=bus.clock();Map<Integer,Integer> counts=new HashMap<>();
        for(Frame frame:frames){
            byte[] b=frame.data;
            if(frame.id==0x81&&b.length==8&&((b[0]&255)|(b[1]&255))!=0)throw new IOException("SEVCON EMCY actief.");
            if(frame.id!=0x597&&frame.id!=0x599&&frame.id!=0x59b)continue;
            if(b.length!=8||now-frame.at<0||now-frame.at>750)throw new IOException("Ongeldig of verouderd veiligheidsframe.");
            boolean safe=frame.id==0x597?(b[0]&0x20)==0&&(b[1]&0x70)==0x10:
                frame.id==0x599?b[6]==0&&b[7]==0:
                (b[0]==0||b[0]==0x20)&&(b[1]&8)==0&&(accessOnly||(b[1]&1)!=0)&&b[3]==0;
            if(!safe)throw new IOException("N, GO uit, gas los, stilstand en ingedrukte rem vereist.");
            counts.put(frame.id,counts.getOrDefault(frame.id,0)+1);
        }
        for(int id:new int[]{0x597,0x599,0x59b})if(counts.getOrDefault(id,0)<2)throw new IOException("Te weinig verse veiligheidsframes.");
        check();deadline=bus.clock()+750;
    }
    private void fresh() throws IOException {check();if(bus.clock()>deadline)throw new IOException("Veiligheidscontrole verlopen; niets verstuurd.");}
    private void download(int index,int sub,long value,int width,boolean signed) throws IOException {
        fresh();long min=signed?-(1L<<(width*8-1)):0,max=1L<<(width*8-(signed?1:0));
        if((width!=1&&width!=2&&width!=4)||value<min||value>=max)throw new IOException("Ongeldig schrijfdatatype.");
        byte[] request=new byte[8];request[0]=(byte)(width==1?0x2f:width==2?0x2b:0x23);
        request[1]=(byte)index;request[2]=(byte)(index>>8);request[3]=(byte)sub;
        for(int i=0;i<width;i++)request[4+i]=(byte)(value>>(8*i));
        for(Frame frame:parse(command(hex(request)),bus.clock())){
            byte[] r=frame.data;if(frame.id!=0x581||r.length!=8||r[1]!=request[1]||r[2]!=request[2]||r[3]!=request[3])continue;
            if((r[0]&255)==0x80){WriteAbort error=new WriteAbort(CanReader.unsigned(Arrays.copyOfRange(r,4,8)));
                if(error.code==0x08000000L)try{error.detail=number(0x5310,0,2,false);}catch(IOException ignored){}
                throw error;
            }
            if(r[0]==0x60&&r[4]==0&&r[5]==0&&r[6]==0&&r[7]==0)return;
        }
        throw new IOException("Schrijfbevestiging ontbreekt; uitkomst onbekend, geen automatische herhaling.");
    }
    public void login() throws IOException {
        if(level()!=4){guard(state()==127,true);download(0x5000,3,0,2,false);download(0x5000,2,0x4bdf,2,false);}
        if(level()!=4)throw new IOException("Level 4 niet bevestigd.");
    }
    public void logout() throws IOException {
        guard(state()==127,true);download(0x5000,3,0,2,false);
        try{download(0x5000,2,0,2,false);}catch(WriteAbort e){if(e.code!=0x08000000L||e.detail==null||e.detail!=9)throw e;}
        if(level()!=0)throw new IOException("Uitloggen niet bevestigd.");
    }
    public void mode(boolean preop) throws IOException {
        fresh();try{ok("ATSH000");fresh();String answer=command(preop?"8001":"0101").toUpperCase(Locale.ROOT);
            for(String error:new String[]{"ERROR","BUS OFF","STOPPED","?"})if(answer.contains(error))throw new IOException("NMT geweigerd.");
        }finally{if(!bus.command("ATSH601",1800).toUpperCase(Locale.ROOT).contains("OK"))throw new IOException("SDO-header herstellen mislukt; verbind opnieuw.");}
        try{Thread.sleep(50);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("Controllerstandcontrole onderbroken.",e);}
        if(state()!=(preop?127:5))throw new IOException("Controllerstand niet bevestigd.");
    }
    public void write(JSONObject row) throws IOException {download(row.optInt("index"),row.optInt("sub"),row.optLong("raw"),row.optInt("width"),row.optBoolean("signed"));}
    public void commit() throws IOException {download(0x4641,1,1,1,false);}
    public void faults() throws IOException {
        try{
            for(String value:new String[]{"ATCSM0","ATSH743","ATCRA763","ATST64"})ok(value);
            diagnostic(new byte[]{0x10,(byte)0xc0});diagnostic(new byte[]{0x21,(byte)0x80});
            byte[] data=diagnostic(new byte[]{0x21,0x13});if(data.length!=112)throw new IOException("Renault-foutgeheugen onvolledig.");
            for(int i=2;i<112;i+=11)if((data[i]!=0||data[i+1]!=0)&&(data[i+2]&4)!=0)throw new IOException("Actieve Renault-storing: "+(data[i]&255)+"/"+(data[i+1]&255));
        }finally{for(String value:new String[]{"ATSH601","ATCRA581","ATST32"})if(!bus.command(value,1800).toUpperCase(Locale.ROOT).contains("OK"))throw new IOException("SDO-instellingen herstellen mislukt.");}
    }
    private byte[] diagnostic(byte[] request) throws IOException {
        // Only the three fixed reads in faults() call this method.
        byte[] tx=new byte[8];tx[0]=(byte)request.length;System.arraycopy(request,0,tx,1,request.length);
        List<Frame> initial=new ArrayList<>();for(Frame f:parse(command(hex(tx)),bus.clock()))if(f.id==0x763)initial.add(f);
        if(initial.size()!=1)throw new IOException("Renault-antwoord ontbreekt of is dubbel.");
        byte[] b=initial.get(0).data,payload;int kind=(b[0]&255)>>4;
        if(kind==0){int size=b[0]&15;if(size<=0||size>Math.min(7,b.length-1))throw new IOException("Ongeldig Renault-frame.");payload=Arrays.copyOfRange(b,1,1+size);}
        else if(kind==1){
            if(b.length!=8)throw new IOException("Ongeldig Renault-startframe.");int size=((b[0]&15)<<8)|(b[1]&255);
            if(size<=7||size>256)throw new IOException("Renault-antwoord buiten leeslimiet.");
            ByteArrayOutputStream out=new ByteArrayOutputStream();out.write(b,2,6);int seq=1;
            for(Frame f:parse(command("3000000000000000"),bus.clock())){if(f.id!=0x763)continue;b=f.data;int remaining=size-out.size();
                if(remaining<=0||b.length<1+Math.min(7,remaining)||(b[0]&255)!=(0x20|seq))throw new IOException("Renault-segmentvolgorde of lengte ongeldig.");
                out.write(b,1,Math.min(7,remaining));seq=(seq+1)&15;
            }
            if(out.size()!=size)throw new IOException("Renault-antwoord afgebroken.");payload=out.toByteArray();
        }else throw new IOException("Onbekend Renault-frametype.");
        if(payload.length<2||(payload[0]&255)!=(request[0]&255)+0x40||payload[1]!=request[1])throw new IOException("Renault-aanvraag geweigerd of verkeerd antwoord.");
        return payload;
    }
    static String hex(byte[] bytes){StringBuilder out=new StringBuilder();for(byte b:bytes)out.append(String.format(Locale.ROOT,"%02X",b&255));return out.toString();}
    static List<Frame> parse(String text,long at){
        List<Frame> result=new ArrayList<>();
        for(String line:text.replace('\r','\n').replace(">","").split("\n")){
            line=line.trim();if(!line.matches("[0-9A-Fa-f ]+"))continue;String compact=line.replace(" ","");if(compact.length()<5)continue;
            int id=Integer.parseInt(compact.substring(0,3),16);String data=compact.substring(3);
            if(data.length()%2==1){int length=Character.digit(data.charAt(0),16);data=data.substring(1);if(length>8||data.length()!=length*2)continue;}
            if(id>0x7ff||data.length()==0||data.length()>16)continue;byte[] raw=new byte[data.length()/2];
            for(int i=0;i<raw.length;i++)raw[i]=(byte)Integer.parseInt(data.substring(i*2,i*2+2),16);
            result.add(new Frame(id,raw,at));
        }return result;
    }
}

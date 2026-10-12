package be.peter.twizypitpro;

import org.json.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.*;

/** Byte-protocol bench only. No USB device or vehicle is ever opened. */
public final class VehicleWriteTests {
    interface Case {void run() throws Exception;}
    static int passed;
    static void check(boolean ok){if(!ok)throw new AssertionError();}
    static void rejects(Case body) throws Exception {try{body.run();throw new AssertionError("Expected rejection");}catch(IOException|IllegalArgumentException expected){}}
    static void test(String name,Case body) throws Exception {body.run();passed++;System.out.println("PASS "+name);}
    static Set<String> keys(String... values){return new HashSet<>(Arrays.asList(values));}
    static class MemoryStore implements VehicleWriter.Store {
        final Map<String,JSONObject> files=new HashMap<>();boolean fail;
        public JSONObject load(String name){JSONObject v=files.get(name);return v==null?null:Model.copy(v);}
        public void save(String name,JSONObject value) throws IOException {if(fail)throw new IOException("Disk full");files.put(name,Model.copy(value));}
        public void remove(String name){files.remove(name);}
    }
    static class Bench implements VehicleControl.Bus {
        final Model model;final MemoryStore store;final String type;
        JSONObject identity;Map<String,Long> objects=new HashMap<>();Set<String> protectedRows=new HashSet<>();
        List<String> sent=new ArrayList<>(),tuning=new ArrayList<>();List<Integer> widths=new ArrayList<>();
        long now=1000;int header=0x601;boolean writable=true,activeFault,loginTimeout,abortLogout,keepLevel;
        String guardFault="",lostAck,mismatch,failAfter;
        Bench(Model model,MemoryStore store,String type,String firmware) throws Exception {
            this.model=model;this.store=store;this.type=type;
            identity=VehicleWriter.object("vendor",30,"product",type.equals("45")?0x0712301b:0x0712302d,"revision",Model.revision(firmware),"serial",1234,"hardware","BENCH","software",firmware,"errors",new JSONArray());
            JSONArray rows=Tuning.targets(model,model.defaults(type),type,0x20cL);
            for(int i=0;i<rows.length();i++){JSONObject r=rows.getJSONObject(i);objects.put(r.getString("address"),r.getLong("raw"));protectedRows.add(r.getString("address"));}
            objects.put("5000:01",0L);objects.put("5110:00",5L);objects.put("1001:00",0L);objects.put("606C:00",0L);objects.put("5310:00",9L);
        }
        public boolean writable(){return writable;}
        public JSONObject identity(){return Model.copy(identity);}
        public long clock(){return now;}
        public long number(int index,int sub,int width,boolean signed) throws IOException {
            String address=String.format(Locale.ROOT,"%04X:%02X",index,sub);
            if(protectedRows.contains(address)&&objects.get("5000:01")!=4)throw new IOException("Protected read without level 4");
            if(address.equals("1001:00")&&guardFault.equals("error"))return 1;
            if(address.equals("606C:00")&&guardFault.equals("rpm"))return 1;
            Long value=objects.get(address);if(value==null)throw new IOException("No object: "+address);
            if(address.equals(mismatch)&&tuning.contains(address)){mismatch=null;return value+1;}return value;
        }
        public List<VehicleControl.Frame> capture(){
            byte[] key={0,0x10,0,0,0,0,0,0},speed=new byte[8],gear={0,1,0,0,0,0,0,0};long at=now;
            if(guardFault.equals("stale"))at-=1000;
            if(guardFault.equals("key"))key[1]=0;
            if(guardFault.equals("gear"))gear[0]=(byte)0x80;
            if(guardFault.equals("brake"))gear[1]=0;
            if(guardFault.equals("go"))gear[1]|=8;
            if(guardFault.equals("throttle"))gear[3]=1;
            if(guardFault.equals("moving"))speed[7]=1;
            List<VehicleControl.Frame> frames=new ArrayList<>();
            for(int i=0;i<2;i++){frames.add(new VehicleControl.Frame(0x597,key,at));frames.add(new VehicleControl.Frame(0x599,speed,at));if(!guardFault.equals("missing"))frames.add(new VehicleControl.Frame(0x59b,gear,at));}
            if(guardFault.equals("emcy"))frames.add(new VehicleControl.Frame(0x81,new byte[]{0,0x10,0,0,0,0,0,0},at));return frames;
        }
        private String reply(byte[] payload){return "763 "+VehicleControl.hex(payload)+"\r>";}
        public String command(String command,int timeout) throws IOException {
            sent.add(command);
            if(command.equals("ATRV"))return guardFault.equals("voltage")?"11.0V\r>":"13.2V\r>";
            if(command.startsWith("ATSH")){header=Integer.parseInt(command.substring(4),16);return "OK\r>";}
            if(command.startsWith("AT"))return "OK\r>";
            if(header==0){check(store.files.containsKey("pending-vehicle.json"));check(store.files.keySet().stream().anyMatch(s->s.startsWith("backup-")));check(command.equals("8001")||command.equals("0101"));objects.put("5110:00",command.equals("8001")?127L:5L);return "NO DATA\r>";}
            if(header==0x743){
                if(command.startsWith("0210C0"))return reply(new byte[]{2,0x50,(byte)0xc0,0,0,0,0,0});
                if(command.startsWith("022180"))return reply(new byte[]{2,0x61,(byte)0x80,0,0,0,0,0});
                if(command.startsWith("022113"))return reply(new byte[]{0x10,0x70,0x61,0x13,(byte)(activeFault?2:0),(byte)(activeFault?83:0),(byte)(activeFault?4:0),0});
                if(command.equals("3000000000000000")){StringBuilder out=new StringBuilder();for(int n=0;n<16;n++)out.append("763 ").append(String.format(Locale.ROOT,"%02X",0x20|((n+1)&15))).append("00000000000000\r");return out+">";}
                throw new IOException("Unexpected cluster command");
            }
            check(header==0x601&&command.length()==16);byte[] data=new byte[8];for(int i=0;i<8;i++)data[i]=(byte)Integer.parseInt(command.substring(i*2,i*2+2),16);
            int cs=data[0]&255,width=cs==0x2f?1:cs==0x2b?2:cs==0x23?4:0;check(width!=0);
            int index=(data[1]&255)|((data[2]&255)<<8),sub=data[3]&255;String address=String.format(Locale.ROOT,"%04X:%02X",index,sub);
            check(store.files.containsKey(index==0x5000?"pending-access.json":"pending-vehicle.json"));
            long value=CanReader.unsigned(Arrays.copyOfRange(data,4,4+width));
            if(index==0x5000){check(width==2&&(sub==2||sub==3));if(sub==2)objects.put("5000:01",value==0?(keepLevel?4L:0L):4L);}
            else if(address.equals("4641:01")){check(width==1&&value==1);tuning.add(address);widths.add(width);}
            else {check(objects.containsKey(address)&&objects.get("5000:01")==4&&objects.get("5110:00")==127);objects.put(address,value);tuning.add(address);widths.add(width);}
            if(loginTimeout&&address.equals("5000:03"))now+=1000;
            if(address.equals(failAfter))guardFault="moving";
            if(address.equals(lostAck)){lostAck=null;return "NO DATA\r>";}
            if(abortLogout&&address.equals("5000:02")&&value==0)return "581 8000500200000008\r>";
            return "581 60"+command.substring(2,8)+"00000000\r>";
        }
    }
    static class Rig {
        final Model model;final MemoryStore store=new MemoryStore();final Bench bus;final AtomicBoolean active=new AtomicBoolean(true);final AtomicLong clock=new AtomicLong(1000);
        VehicleWriter writer;VehicleControl control;
        Rig(Model model,String type,String firmware) throws Exception {this.model=model;bus=new Bench(model,store,type,firmware);writer=new VehicleWriter(model,store,clock::get);control=new VehicleControl(bus,active::get);}
        JSONObject values(Object... changes){JSONObject v=model.defaults(bus.type);for(int i=0;i<changes.length;i+=2)Model.put(v,(String)changes[i],changes[i+1]);return v;}
        JSONObject plan(JSONObject values,Set<String> keys) throws Exception {return writer.prepare(control,values,keys,true,true,true);}
        void apply(JSONObject p) throws Exception {writer.apply(control,p.getString("id"),p.getString("review_hash"));}
        void restore(JSONObject p) throws Exception {JSONObject review=writer.reviewRestore(control,p.getString("id"));writer.restore(control,p.getString("id"),review.getString("review_hash"));}
        void off() throws Exception {writer.observeOff(Collections.singletonList(new VehicleControl.Frame(0x597,new byte[8],1000)),1000);}
        void finish(JSONObject p) throws Exception {off();writer.verifyCycle(control,p.getString("id"));}
    }
    static class ByteSerial implements com.hoho.android.usbserial.driver.UsbSerialPort {
        byte[] reply=new byte[0];int offset;List<String> sent=new ArrayList<>();
        public void purgeHwBuffers(boolean write,boolean read){if(read){reply=new byte[0];offset=0;}}
        public void write(byte[] bytes,int timeout) throws IOException {
            String command=new String(bytes,java.nio.charset.StandardCharsets.US_ASCII).trim();sent.add(command);
            if(!command.startsWith("AT"))throw new IOException("Unexpected SDO during contact-OFF observation");
            String text=command.equals("ATMA")?"597 0000000000000000\r599 0000000000000000\r59B 0001000000000000\r597 0000000000000000\r599 0000000000000000\r59B 0001000000000000\r>":"OK\r>";
            reply=text.getBytes(java.nio.charset.StandardCharsets.US_ASCII);offset=0;
        }
        public int read(byte[] bytes,int timeout){if(offset==reply.length)return 0;bytes[0]=reply[offset++];return 1;}
        public void close(){}
    }
    public static void main(String[] args) throws Exception {
        Model model=new Model(new JSONObject(Files.readString(Path.of(args[0]))));
        test("Android writes and verifies all supported model/firmware combinations",()->{
            for(String type:new String[]{"45","80"})for(String firmware:new String[]{"0712.0001","0712.0002"}){
                Rig r=new Rig(model,type,firmware);JSONObject p=r.plan(r.values("drive",70),keys("drive"));check(p.getJSONArray("rows").length()==75&&p.getJSONArray("changes").length()==1);check(r.bus.tuning.isEmpty());
                r.apply(p);check(r.bus.objects.get("2920:01")==700&&r.control.level()==0&&r.control.state()==5);r.finish(p);check(r.writer.pending==null&&r.writer.access==null);
            }
        });
        test("Typed power maps commit and restore in safe point order",()->{
            for(String type:new String[]{"45","80"}){Rig r=new Rig(model,type,"0712.0002");JSONObject v=r.values("speed",90,"warn",100,"torque",120,"current",120,"power_low",120,"power_high",115,"D_speed1",34);
                Set<String> selected=keys();v.keys().forEachRemaining(selected::add);JSONObject p=r.plan(v,selected);r.apply(p);check(r.bus.tuning.contains("4641:01")&&r.bus.widths.contains(4)&&r.bus.widths.contains(1));r.restore(p);check(r.bus.objects.get("2920:05")== (type.equals("45")?5814:7250));r.finish(p);}
        });
        test("Partial warning selection cannot bypass preserved maximum speed",()->{
            for(String type:new String[]{"45","80"}){Rig r=new Rig(model,type,"0712.0002");rejects(()->r.plan(r.values("speed",6,"warn",10),keys("warn")));check(r.bus.tuning.isEmpty()&&r.control.level()==0);}
        });
        test("Partial speed selection cannot bypass preserved warning",()->{
            Rig r=new Rig(model,"80","0712.0002");Set<String> power=VehicleWriter.selectionGroup("speed");rejects(()->r.plan(r.values("speed",100,"warn",110),power));power.add("warn");JSONObject p=r.plan(r.values("speed",100,"warn",110),power);check(p.getJSONArray("changes").length()>1);
        });
        test("Unselected custom vehicle registers survive a valid warning change",()->{
            Rig r=new Rig(model,"80","0712.0002");r.bus.objects.put("6075:00",520000L);JSONObject p=r.plan(r.values("speed",6,"warn",100),keys("warn"));r.apply(p);check(r.bus.objects.get("6075:00")==520000&&r.bus.objects.get("2920:05")==7250);
        });
        test("Partial coupled power and brake-light selections reject before login",()->{
            for(Set<String> selected:Arrays.asList(keys(),keys("speed"),keys("brakelight_on"),keys("unknown"))){Rig r=new Rig(model,"80","0712.0002");rejects(()->r.plan(r.values(),selected));check(r.bus.sent.isEmpty());}
        });
        test("All unsafe CAN states and stale or missing frames reject before writes",()->{
            for(String fault:new String[]{"rpm","error","voltage","stale","key","gear","brake","go","throttle","moving","missing","emcy"}){Rig r=new Rig(model,"80","0712.0002");r.bus.guardFault=fault;rejects(()->r.plan(r.values("drive",70),keys("drive")));check(r.bus.tuning.isEmpty()&&r.control.level()==0);}
        });
        test("Active Renault cluster fault blocks preparation and apply",()->{
            Rig r=new Rig(model,"80","0712.0002");r.bus.activeFault=true;rejects(()->r.plan(r.values("drive",70),keys("drive")));check(r.control.level()==0);r.bus.activeFault=false;JSONObject p=r.plan(r.values("drive",70),keys("drive"));r.bus.activeFault=true;rejects(()->r.apply(p));check(r.bus.tuning.isEmpty());
        });
        test("Unknown firmware and M5 never gain a write route",()->{
            Rig r=new Rig(model,"80","0712.0003");rejects(()->r.plan(r.values("drive",70),keys("drive")));r.bus.writable=false;rejects(()->new VehicleControl(r.bus,()->true));check(r.bus.sent.isEmpty());
        });
        test("Durable access intent is required even before login",()->{
            Rig r=new Rig(model,"80","0712.0002");r.store.fail=true;rejects(()->r.writer.snapshot(r.control));check(r.bus.sent.isEmpty()&&r.control.level()==0);
        });
        test("Lost write acknowledgement stops once and restores after restart",()->{
            Rig r=new Rig(model,"80","0712.0002");JSONObject p=r.plan(r.values("drive",70),keys("drive"));r.bus.lostAck="2920:01";rejects(()->r.apply(p));check(r.bus.tuning.size()==1&&r.writer.pending.optString("phase").equals("recovery-required"));
            r.writer=new VehicleWriter(model,r.store,r.clock::get);check(r.writer.pending.optBoolean("interrupted"));r.restore(p);check(r.bus.objects.get("2920:01")==1000);r.finish(p);
        });
        test("Read-back mismatch and changed safety stop subsequent registers",()->{
            for(boolean mismatch:new boolean[]{true,false}){Rig r=new Rig(model,"80","0712.0002");JSONObject p=r.plan(r.values("drive",70,"neutral",15),keys("drive","neutral"));if(mismatch)r.bus.mismatch="2920:01";else r.bus.failAfter="2920:01";rejects(()->r.apply(p));check(r.bus.tuning.size()==1&&r.writer.pending.optString("phase").equals("recovery-required"));}
        });
        test("Restoration cannot add an unreviewed register",()->{
            Rig r=new Rig(model,"80","0712.0002");JSONObject p=r.plan(r.values("drive",70,"neutral",15),keys("drive","neutral"));r.bus.lostAck="2920:01";rejects(()->r.apply(p));JSONObject review=r.writer.reviewRestore(r.control,p.getString("id"));check(review.getJSONArray("changes").length()==1);
            r.bus.objects.put("2920:03",151L);int before=r.bus.tuning.size();rejects(()->r.writer.restore(r.control,p.getString("id"),review.getString("review_hash")));check(r.bus.tuning.size()==before);r.restore(p);check(r.bus.objects.get("2920:03")==182);
        });
        test("Restore plans are immutable single-use and expire",()->{
            Rig r=new Rig(model,"80","0712.0002");JSONObject p=r.plan(r.values("drive",70),keys("drive"));r.apply(p);
            rejects(()->r.writer.restore(r.control,p.getString("id"),""));JSONObject review=r.writer.reviewRestore(r.control,p.getString("id"));r.clock.addAndGet(120001);rejects(()->r.writer.restore(r.control,p.getString("id"),review.getString("review_hash")));
            JSONObject fresh=r.writer.reviewRestore(r.control,p.getString("id"));Model.put(fresh.getJSONArray("changes").getJSONObject(0),"raw",999);r.writer.restore(r.control,p.getString("id"),fresh.getString("review_hash"));check(r.bus.objects.get("2920:01")==1000);rejects(()->r.writer.restore(r.control,p.getString("id"),fresh.getString("review_hash")));
        });
        test("Controller swap and changed before-values prevent configuration writes",()->{
            for(boolean swap:new boolean[]{true,false}){Rig r=new Rig(model,"80","0712.0002");JSONObject p=r.plan(r.values("drive",70),keys("drive"));if(swap)Model.put(r.bus.identity,"serial",999);else r.bus.objects.put("2920:01",900L);rejects(()->r.apply(p));check(r.bus.tuning.isEmpty()&&r.control.state()==5);}
        });
        test("Contact cycle requires positive fresh OFF evidence and successful readback",()->{
            Rig r=new Rig(model,"80","0712.0002");JSONObject p=r.plan(r.values("drive",70),keys("drive"));r.apply(p);rejects(()->r.writer.verifyCycle(r.control,p.getString("id")));r.writer.observeOff(Collections.singletonList(new VehicleControl.Frame(0x597,new byte[8],0)),1000);check(!r.writer.pending.optBoolean("cycle_off_seen"));r.finish(p);check(r.writer.pending==null);
        });
        test("Tampered backup or interrupted contact-cycle evidence blocks completion",()->{
            Rig r=new Rig(model,"80","0712.0002");JSONObject p=r.plan(r.values("drive",70),keys("drive"));r.apply(p);r.off();r.writer=new VehicleWriter(model,r.store,r.clock::get);check(!r.writer.pending.optBoolean("cycle_off_seen"));
            Model.put(r.store.files.get("backup-"+p.getString("id")+".json"),"id","changed");r.writer=new VehicleWriter(model,r.store,r.clock::get);check(r.writer.pending.optString("phase").equals("corrupt"));rejects(()->r.restore(p));
        });
        test("Cancelled activity and expired login safety never send another write",()->{
            Rig r=new Rig(model,"80","0712.0002");JSONObject p=r.plan(r.values("drive",70),keys("drive"));r.active.set(false);rejects(()->r.apply(p));check(r.bus.tuning.isEmpty());
            Rig login=new Rig(model,"80","0712.0002");login.bus.loginTimeout=true;rejects(()->login.writer.snapshot(login.control));check(login.control.level()==0&&login.writer.access!=null);
        });
        test("Firmware logout error nine is accepted only with confirmed level zero",()->{
            Rig r=new Rig(model,"45","0712.0001");r.bus.abortLogout=true;check(r.writer.snapshot(r.control).optBoolean("logged_out"));
            Rig failure=new Rig(model,"45","0712.0001");failure.bus.abortLogout=true;failure.bus.keepLevel=true;rejects(()->failure.writer.snapshot(failure.control));check(failure.writer.access!=null&&failure.control.level()==4);
        });
        test("Fragmented real-reader capture observes contact OFF without SDO timeouts",()->{
            Rig r=new Rig(model,"80","0712.0002");JSONObject p=r.plan(r.values("drive",70),keys("drive"));r.apply(p);
            ByteSerial serial=new ByteSerial();CanReader reader=new CanReader(serial,false,model);JSONObject sample=reader.pendingSample(r.writer);
            check(r.writer.pending.optBoolean("cycle_off_seen")&&!sample.optBoolean("key_on"));check(serial.sent.contains("ATCM000")&&serial.sent.get(serial.sent.size()-1).equals("ATCRA581"));
        });
        System.out.println("ANDROID VEHICLE: "+passed+" tests passed");
    }
}

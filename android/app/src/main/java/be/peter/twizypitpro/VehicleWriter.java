package be.peter.twizypitpro;

import org.json.*;
import java.io.*;
import java.util.*;
import java.util.function.LongSupplier;

/** Durable, reviewed transactions. Construction never touches the CAN bus. */
final class VehicleWriter {
    interface Port {
        JSONObject identity() throws IOException;
        void bind(JSONObject identity);
        long read(JSONObject row) throws IOException;
        int state() throws IOException;
        int level() throws IOException;
        void guard(boolean preop,boolean accessOnly) throws IOException;
        void faults() throws IOException;
        void login() throws IOException;
        void logout() throws IOException;
        void mode(boolean preop) throws IOException;
        void write(JSONObject row) throws IOException;
        void commit() throws IOException;
    }
    interface Store {
        JSONObject load(String name) throws Exception;
        void save(String name,JSONObject value) throws Exception;
        void remove(String name) throws Exception;
    }
    private interface Action<T> {T run() throws Exception;}
    private final Store store;
    private final Model model;
    private final LongSupplier clock;
    private JSONObject plan,restorePlan;
    JSONObject pending,access;
    VehicleWriter(Model model,Store store){this(model,store,()->System.nanoTime()/1000000);}
    VehicleWriter(Model model,Store store,LongSupplier clock){
        this.model=model;this.store=store;this.clock=clock;
        try{access=store.load("pending-access.json");if(access!=null){id(access.optString("id"));if(access.optJSONObject("identity")==null)throw new IOException("Identiteit ontbreekt.");}}
        catch(Exception e){access=object("phase","corrupt","error","Toegangjournaal beschadigd; handmatige inspectie vereist.");}
        try{
            pending=store.load("pending-vehicle.json");
            if(pending!=null){String key=id(pending.optString("id"));JSONObject backup=store.load("backup-"+key+".json");
                if(backup==null||!hash(backup).equals(pending.optString("backup_sha256")))throw new IOException("Backup beschadigd.");
                Model.put(pending,"identity",copy(backup.optJSONObject("identity")));Model.put(pending,"rows",array(backup.optJSONArray("rows")));
                Model.put(pending,"interrupted",true);Model.put(pending,"cycle_off_seen",false);
            }
        }catch(Exception e){pending=object("phase","corrupt","error","Voertuigjournaal of backup beschadigd; handmatige inspectie vereist.");}
    }
    static JSONObject object(Object... values){JSONObject o=new JSONObject();for(int i=0;i<values.length;i+=2)Model.put(o,(String)values[i],values[i+1]);return o;}
    private static JSONObject copy(JSONObject value){if(value==null)throw new IllegalArgumentException("Object ontbreekt.");return Model.copy(value);}
    private static JSONArray array(JSONArray value){if(value==null)throw new IllegalArgumentException("Registerlijst ontbreekt.");try{return new JSONArray(value.toString());}catch(JSONException e){throw new IllegalArgumentException(e);}}
    private static String id(String value) throws IOException {if(!value.matches("[0-9a-f]{32}"))throw new IOException("Ongeldig transactie-ID.");return value;}
    private static String uuid(){return UUID.randomUUID().toString().replace("-","");}
    private static String canonical(Object value){
        if(value instanceof JSONObject){JSONObject o=(JSONObject)value;List<String> keys=new ArrayList<>();o.keys().forEachRemaining(keys::add);Collections.sort(keys);StringJoiner s=new StringJoiner(",","{","}");for(String k:keys)s.add(JSONObject.quote(k)+":"+canonical(o.opt(k)));return s.toString();}
        if(value instanceof JSONArray){JSONArray a=(JSONArray)value;StringJoiner s=new StringJoiner(",","[","]");for(int i=0;i<a.length();i++)s.add(canonical(a.opt(i)));return s.toString();}
        return value==null||value==JSONObject.NULL?"null":value instanceof String?JSONObject.quote((String)value):value.toString();
    }
    static String hash(JSONObject value){return Model.sha(canonical(value));}
    static String fingerprint(JSONObject value){JSONObject o=new JSONObject();for(String k:new String[]{"vendor","product","revision","serial","software","hardware"})Model.put(o,k,value.opt(k));return hash(o);}
    void invalidate(){plan=null;restorePlan=null;}
    JSONObject status(){return pending==null?null:copy(pending);}
    JSONObject accessStatus(){return access==null?null:copy(access);}
    private void persist() throws Exception {store.save("pending-vehicle.json",pending);}
    private void saveAccess() throws Exception {store.save("pending-access.json",access);}
    private JSONObject identity(Port port,JSONObject expected) throws Exception {
        JSONObject actual=port.identity();String type=Model.modelOf(actual);JSONArray errors=actual.optJSONArray("errors");
        if(errors==null||errors.length()!=0||actual.optLong("vendor")!=30||actual.optLong("serial")==0||!Model.known(type,actual.optString("software"),actual.optLong("revision")))throw new IOException("Geen volledige, exact ondersteunde controlleridentiteit.");
        if(expected!=null&&!fingerprint(expected).equals(fingerprint(actual)))throw new IOException("Controlleridentiteit wijkt af; niets verder schrijven.");
        port.bind(actual);return actual;
    }
    private void close(Port port) throws Exception {
        identity(port,access.optJSONObject("identity"));
        if(port.level()!=0){Model.put(access,"phase","logging-out");saveAccess();port.logout();}
        Model.put(access,"phase","closed");saveAccess();store.save("access-"+id(access.optString("id"))+".json",access);store.remove("pending-access.json");access=null;
    }
    void closeAccess(Port port) throws Exception {
        if(pending!=null||access==null||access.optString("phase").equals("corrupt"))throw new IOException("Geen afzonderlijk herstelbare toegangssessie; herstel eerst een open tuningtransactie.");
        identity(port,access.optJSONObject("identity"));port.guard(false,true);close(port);
    }
    private <T>T authenticated(Port port,JSONObject identity,String purpose,boolean resume,Action<T> action) throws Exception {
        identity(port,identity);
        if(access!=null){if(!resume||access.optString("phase").equals("corrupt")||!fingerprint(access.optJSONObject("identity")).equals(fingerprint(identity)))throw new IOException("Sluit eerst de onderbroken toegangssessie af.");}
        else{
            if(port.level()!=0)throw new IOException("Controller al ingelogd buiten deze app; sluit die sessie eerst af.");
            access=object("id",uuid(),"identity",copy(identity),"purpose",purpose,"phase","login-intent","configuration_changed",false);saveAccess();
        }
        boolean known=false;T result;
        try{
            port.guard(port.state()==127,true);port.login();known=true;Model.put(access,"phase","authenticated");saveAccess();result=action.run();
        }catch(Exception e){
            Model.put(access,"phase","recovery-required");Model.put(access,"error",e.toString());saveAccess();
            if(known&&pending==null)try{if(port.level()==4)close(port);}catch(Exception ignored){}
            throw e;
        }
        try{close(port);}catch(Exception e){
            if(access!=null){Model.put(access,"phase","recovery-required");Model.put(access,"error",e.toString());saveAccess();}
            if(pending!=null){Model.put(pending,"phase","recovery-required");Model.put(pending,"error",e.toString());Model.put(pending,"cycle_off_seen",false);persist();}
            throw e;
        }
        return result;
    }
    JSONObject snapshot(Port port) throws Exception {
        if(pending!=null||access!=null)throw new IOException("Rond eerst de open voertuig- of toegangssessie af.");
        JSONObject identity=identity(port,null);String type=Model.modelOf(identity);
        JSONObject result=authenticated(port,identity,"snapshot",false,()->{
            JSONArray rows=Tuning.targets(model,model.defaults(type),type,null);
            for(int i=0;i<rows.length();i++){JSONObject r=rows.getJSONObject(i);Model.put(r,"raw",port.read(r));Model.put(r,"source","live");}
            identity(port,identity);port.guard(false,true);
            JSONObject saved=object("id",uuid(),"identity",copy(identity),"model",type,"registers",rows,"complete",true,"tuning_changed",false,"mode","live-usb","at",Model.now());
            store.save("snapshot-"+saved.optString("id")+".json",saved);return saved;
        });
        Model.put(result,"logged_out",true);return result;
    }
    private static final Set<String> POWER=new HashSet<>(Arrays.asList("speed","torque","current","power_low","power_high"));
    private static final Set<String> LIGHT=new HashSet<>(Arrays.asList("brakelight_on","brakelight_off"));
    static Set<String> selectionGroup(String key){return POWER.contains(key)?new HashSet<>(POWER):LIGHT.contains(key)?new HashSet<>(LIGHT):new HashSet<>(Collections.singleton(key));}
    JSONObject prepare(Port port,JSONObject values,Set<String> selected,boolean drivetrain,boolean brakeHardware,boolean faultsResolved) throws Exception {
        plan=null;
        if(pending!=null||access!=null)throw new IOException("Rond eerst de openstaande transactie of toegangssessie af.");
        if(!drivetrain||!faultsResolved)throw new IOException("Bevestig de originele motor/reductiekast en opgeloste voertuigstoringen (ook SERV).");
        JSONObject identity=identity(port,null);String type=Model.modelOf(identity);model.validate(values,type);values=copy(values);
        Set<String> keys=new HashSet<>();values.keys().forEachRemaining(keys::add);
        if(selected==null||selected.isEmpty()||!keys.containsAll(selected))throw new IOException("Selecteer geldige instellingen.");
        if(!Collections.disjoint(selected,POWER)&&!selected.containsAll(POWER))throw new IOException("Snelheid, koppel, stroom en beide vermogensdoelen horen samen.");
        if(!Collections.disjoint(selected,LIGHT)&&!selected.containsAll(LIGHT))throw new IOException("Selecteer beide remlichtdrempels samen.");
        if(!Collections.disjoint(selected,LIGHT)&&(values.optInt("brakelight_on")!=100||values.optInt("brakelight_off")!=100)&&!brakeHardware)throw new IOException("Aangepaste remlichthardware niet bevestigd.");
        port.faults();port.guard(false,false);JSONObject scan=snapshot(port);identity(port,identity);
        JSONArray rows=Tuning.compare(model,values,type,scan);
        Map<String,JSONObject> byAddress=new HashMap<>();
        for(int i=0;i<rows.length();i++){
            JSONObject r=rows.getJSONObject(i);if(r.isNull("before")||r.isNull("raw")||!r.optBoolean("verified_width"))throw new IOException("Volledige getypeerde beginsnapshot ontbreekt.");
            JSONArray fields=r.getJSONArray("keys");boolean chosen=false;for(int n=0;n<fields.length();n++)chosen|=selected.contains(fields.getString(n));
            if(!chosen){Model.put(r,"raw",r.opt("before"));Model.put(r,"changed",false);}byAddress.put(r.getString("address"),r);
        }
        if((selected.contains("speed")||selected.contains("warn"))&&byAddress.get("3813:34").getLong("raw")<=byAddress.get("2920:05").getLong("raw"))throw new IOException("Waarschuwing moet boven de uiteindelijke maximumsnelheid liggen; controleer ook behouden voertuigwaarden.");
        JSONArray changes=ordered(rows);if(changes.length()==0)throw new IOException("Alle geselecteerde doelen zijn al gelijk aan de voertuigwaarden.");port.guard(false,false);
        plan=object("id",uuid(),"identity",copy(identity),"model",type,"values",values,"selected_keys",new JSONArray(new TreeSet<>(selected)),"rows",rows,"changes",changes,"expires_in",120,"deadline",clock.getAsLong()+120000);
        Model.put(plan,"review_hash",reviewHash(plan));return publicPlan(plan);
    }
    private static String reviewHash(JSONObject p){return hash(object("id",p.opt("id"),"review_id",p.opt("review_id"),"identity",p.opt("identity"),"rows",p.opt("rows"),"values",p.opt("values")));}
    private static JSONObject publicPlan(JSONObject p){JSONObject result=copy(p);result.remove("deadline");return result;}
    JSONObject apply(Port port,String planId,String token) throws Exception {
        JSONObject reviewed=plan;plan=null;
        if(pending!=null||reviewed==null||!reviewed.optString("id").equals(planId)||!reviewed.optString("review_hash").equals(token)||clock.getAsLong()>reviewed.optLong("deadline"))throw new IOException("Schrijfplan ontbreekt, wijkt af of is verlopen.");
        JSONObject identity=reviewed.getJSONObject("identity");identity(port,identity);port.faults();port.guard(false,false);
        authenticated(port,identity,"apply",false,()->{
            if(port.state()!=5)throw new IOException("Controllerstand gewijzigd.");checkRows(port,reviewed.getJSONArray("rows"),"before");identity(port,identity);port.guard(false,false);
            if(clock.getAsLong()>reviewed.optLong("deadline"))throw new IOException("Plan verlopen tijdens controle.");
            JSONObject backup=object("id",planId,"identity",copy(identity),"rows",array(reviewed.getJSONArray("rows")),"values",copy(reviewed.getJSONObject("values")));
            store.save("backup-"+id(planId)+".json",backup);
            pending=copy(backup);Model.put(pending,"backup_sha256",hash(backup));Model.put(pending,"phase","prepared");Model.put(pending,"attempts",new JSONArray());Model.put(pending,"cycle_off_seen",false);persist();
            execute(port,reviewed.getJSONArray("changes"),false);return null;
        });return status();
    }
    private void execute(Port port,JSONArray changes,boolean restore) throws Exception {
        try{
            Model.put(pending,"phase","entering-configuration");persist();Model.put(access,"configuration_changed",true);saveAccess();
            if(port.level()!=4)throw new IOException("Level 4 ontbreekt.");port.guard(port.state()==127,false);port.mode(true);
            for(int i=0;i<changes.length();i++){
                JSONObject row=changes.getJSONObject(i);
                if(port.level()!=4||port.state()!=127||port.read(row)!=row.getLong("before"))throw new IOException("Schrijfrechten, controllerstand of beginwaarde gewijzigd: "+row.optString("address"));
                JSONObject attempt=object("address",row.optString("address"),"before",row.opt("before"),"after",row.opt("raw"),"verified",false);
                Model.put(pending,"phase",restore?"restoring":"writing");Model.put(pending,"current",row.optString("address"));pending.getJSONArray("attempts").put(attempt);persist();
                port.guard(true,false);port.write(row);if(port.read(row)!=row.getLong("raw"))throw new IOException("Read-back wijkt af: "+row.optString("address"));Model.put(attempt,"verified",true);persist();
            }
            JSONArray originals=pending.getJSONArray("rows");boolean mapChanged=false;
            for(int i=0;i<originals.length();i++){JSONObject r=originals.getJSONObject(i);if((r.optInt("index")==0x4610||r.optInt("index")==0x4611)&&r.getLong("before")!=r.getLong("raw"))mapChanged=true;}
            if(mapChanged){Model.put(pending,"phase","committing-map");persist();port.guard(true,false);port.commit();}
            checkRows(port,originals,restore?"before":"raw");port.guard(true,false);port.mode(false);
            Model.put(pending,"phase","awaiting-contact-cycle");Model.put(pending,"restored",restore);Model.put(pending,"cycle_off_seen",false);pending.remove("error");persist();
        }catch(Exception e){Model.put(pending,"phase","recovery-required");Model.put(pending,"error",e.toString());Model.put(pending,"cycle_off_seen",false);persist();throw e;}
    }
    private static void checkRows(Port port,JSONArray rows,String field) throws Exception {for(int i=0;i<rows.length();i++){JSONObject r=rows.getJSONObject(i);if(port.read(r)!=r.getLong(field))throw new IOException("Begin-/eindwaarde gewijzigd bij "+r.optString("address")+"; bekijk een nieuw plan.");}}
    private void recoverable(String transactionId) throws Exception {if(pending==null||pending.optString("phase").equals("corrupt")||!pending.optString("id").equals(transactionId))throw new IOException("Geen passende hersteltransactie.");}
    JSONObject reviewRestore(Port port,String transactionId) throws Exception {
        restorePlan=null;recoverable(transactionId);JSONObject identity=pending.getJSONObject("identity");identity(port,identity);
        int state=port.state();if(state!=5&&state!=127)throw new IOException("Onbekende controllerstand.");port.guard(state==127,false);
        JSONObject reviewed=authenticated(port,identity,"restore-review",true,()->{
            JSONArray rows=new JSONArray(),originals=pending.getJSONArray("rows");
            for(int i=0;i<originals.length();i++){JSONObject original=originals.getJSONObject(i);long actual=port.read(original);
                if(actual!=original.getLong("before")&&actual!=original.getLong("raw"))throw new IOException("Onverwachte waarde bij herstel: "+original.optString("address"));
                JSONObject r=copy(original);Model.put(r,"before",actual);Model.put(r,"raw",original.opt("before"));rows.put(r);
            }
            return object("id",transactionId,"identity",copy(identity),"rows",rows,"changes",ordered(rows));
        });
        Model.put(reviewed,"review_id",uuid());Model.put(reviewed,"expires_in",120);Model.put(reviewed,"deadline",clock.getAsLong()+120000);Model.put(reviewed,"review_hash",reviewHash(reviewed));restorePlan=copy(reviewed);return publicPlan(reviewed);
    }
    JSONObject restore(Port port,String transactionId,String token) throws Exception {
        JSONObject reviewed=restorePlan;restorePlan=null;recoverable(transactionId);
        if(reviewed==null||!reviewed.optString("id").equals(transactionId)||!reviewed.optString("review_hash").equals(token)||clock.getAsLong()>reviewed.optLong("deadline"))throw new IOException("Herstelplan ontbreekt, wijkt af of is verlopen; bekijk een nieuw plan.");
        JSONObject identity=reviewed.getJSONObject("identity");identity(port,identity);port.guard(port.state()==127,false);
        authenticated(port,identity,"restore",true,()->{
            checkRows(port,reviewed.getJSONArray("rows"),"before");identity(port,identity);port.guard(port.state()==127,false);
            if(clock.getAsLong()>reviewed.optLong("deadline"))throw new IOException("Herstelplan verlopen tijdens controle.");
            Model.put(pending,"cycle_off_seen",false);persist();execute(port,reviewed.getJSONArray("changes"),true);return null;
        });return status();
    }
    void observeOff(List<VehicleControl.Frame> frames,long now) throws Exception {
        if(pending==null||!pending.optString("phase").equals("awaiting-contact-cycle"))return;
        for(VehicleControl.Frame f:frames)if(f.id==0x597&&f.data.length==8&&now-f.at>=0&&now-f.at<=750&&(f.data[1]&0x10)==0){Model.put(pending,"cycle_off_seen",true);persist();return;}
    }
    JSONObject verifyCycle(Port port,String transactionId) throws Exception {
        recoverable(transactionId);if(!pending.optString("phase").equals("awaiting-contact-cycle")||!pending.optBoolean("cycle_off_seen"))throw new IOException("Contact UIT nog niet via verse CAN-frames waargenomen.");
        JSONObject identity=pending.getJSONObject("identity");identity(port,identity);port.guard(false,false);
        if(port.state()!=5||port.level()!=0)throw new IOException("Operational/uitgelogde toestand niet bevestigd.");
        authenticated(port,identity,"verify-cycle",false,()->{checkRows(port,pending.getJSONArray("rows"),pending.optBoolean("restored")?"before":"raw");identity(port,identity);port.guard(false,false);return null;});
        Model.put(pending,"phase","verified-after-contact-cycle");persist();store.save("transaction-"+id(transactionId)+".json",pending);JSONObject result=status();store.remove("pending-vehicle.json");pending=null;restorePlan=null;return result;
    }
    static JSONArray ordered(JSONArray rows) throws Exception {
        JSONArray result=new JSONArray();Map<String,List<JSONObject>> maps=new HashMap<>();
        for(String letter:new String[]{"D","N","B"})maps.put(letter,new ArrayList<>());
        for(int i=0;i<rows.length();i++){JSONObject r=rows.getJSONObject(i);String key=r.getJSONArray("keys").getString(0);
            if(key.matches("[DNB]_speed[1-4]"))maps.get(key.substring(0,1)).add(r);
            else if(!key.matches("[DNB]_level[1-4]")&&r.getLong("before")!=r.getLong("raw"))result.put(copy(r));
        }
        for(String letter:new String[]{"D","N","B"}){
            List<JSONObject> speeds=maps.get(letter);speeds.sort(Comparator.comparing(r->r.optJSONArray("keys").optString(0)));
            if(speeds.size()!=4)throw new IOException("Onvolledige koppelkaart.");long[] current=new long[4],target=new long[4];boolean[] todo=new boolean[4];int left=0;
            for(int i=0;i<4;i++){current[i]=speeds.get(i).getLong("before");target[i]=speeds.get(i).getLong("raw");todo[i]=current[i]!=target[i];if(todo[i])left++;}
            for(int i=1;i<4;i++)if(current[i]<=current[i-1]||target[i]<=target[i-1])throw new IOException("Ongeldige koppelkaart; geen veilige updatevolgorde.");
            while(left>0){boolean progress=false;for(int i=0;i<4;i++)if(todo[i]&&(i==0||current[i-1]<target[i])&&(i==3||target[i]<current[i+1])){result.put(copy(speeds.get(i)));current[i]=target[i];todo[i]=false;left--;progress=true;break;}if(!progress)throw new IOException("Geen veilige kaartupdatevolgorde.");}
            for(int i=0;i<rows.length();i++){JSONObject r=rows.getJSONObject(i);String key=r.getJSONArray("keys").getString(0);if(key.matches(letter+"_level[1-4]")&&r.getLong("before")!=r.getLong("raw"))result.put(copy(r));}
        }return result;
    }
}

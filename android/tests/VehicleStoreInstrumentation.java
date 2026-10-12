package be.peter.twizypitpro;

import android.app.Instrumentation;
import android.os.Bundle;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import android.content.Intent;
import android.os.Handler;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import com.hoho.android.usbserial.driver.UsbSerialPort;
import java.lang.reflect.*;

/** Installed only in the separate signed test APK, never in the release APK. */
public final class VehicleStoreInstrumentation extends Instrumentation {
    private int passed;
    private interface Case {void run() throws Exception;}
    private void check(boolean value){if(!value)throw new AssertionError();}
    private void test(String name,Case body) throws Exception {body.run();passed++;Bundle status=new Bundle();status.putString("stream","PASS "+name+"\n");sendStatus(0,status);}
    private void rejects(Case body) throws Exception {try{body.run();throw new AssertionError("Expected rejection");}catch(Exception expected){}}
    private byte[] bytes(File file) throws Exception {try(InputStream in=new FileInputStream(file)){ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1)out.write(b,0,n);return out.toByteArray();}}
    private void write(File file,byte[] value) throws Exception {try(FileOutputStream out=new FileOutputStream(file)){out.write(value);out.getFD().sync();}}
    @Override public void onCreate(Bundle arguments){super.onCreate(arguments);start();}
    @Override public void onStart(){
        Bundle result=new Bundle();
        try{
            Vault vault=new Vault(getTargetContext());
            File root=new File(getTargetContext().getFilesDir(),"qa-storage-"+UUID.randomUUID());
            if(!root.mkdirs())throw new IOException("Test directory unavailable");
            VehicleStore store=new VehicleStore(root,vault);File directory=new File(root,"vehicle");
            test("AES-GCM roundtrip and unique ciphertext",()->{
                JSONObject secret=new JSONObject("{\"marker\":\"ANDROID-VEHICLE-ENCRYPTION-TEST\",\"number\":75}");store.save("record.json",secret);byte[] first=bytes(new File(directory,"record.json"));
                check(!new String(first,StandardCharsets.ISO_8859_1).contains(secret.optString("marker")));check(store.load("record.json").optInt("number")==75);
                store.save("record.json",secret);check(!java.util.Arrays.equals(first,bytes(new File(directory,"record.json"))));
            });
            test("Ciphertext tampering and name substitution rejected",()->{
                byte[] encrypted=bytes(new File(directory,"record.json"));write(new File(directory,"other.json"),encrypted);rejects(()->store.load("other.json"));
                encrypted[encrypted.length-1]^=1;write(new File(directory,"record.json"),encrypted);rejects(()->store.load("record.json"));rejects(()->store.load("../record.json"));
            });
            test("Interrupted AtomicFile update preserves original encrypted record",()->{
                store.save("atomic.json",new JSONObject("{\"sequence\":1}"));AtomicFile file=new AtomicFile(new File(directory,"atomic.json"));FileOutputStream unfinished=file.startWrite();unfinished.write(new byte[]{1,2,3});unfinished.getFD().sync();unfinished.close();
                check(store.load("atomic.json").optInt("sequence")==1);store.remove("atomic.json");check(store.load("atomic.json")==null);
            });
            test("Restart journal verified against encrypted backup; tampering blocks recovery",()->{
                String key="0123456789abcdef0123456789abcdef";JSONObject backup=new JSONObject();backup.put("id",key);backup.put("identity",new JSONObject("{\"serial\":123}"));backup.put("rows",new JSONArray());backup.put("values",new JSONObject());
                store.save("backup-"+key+".json",backup);JSONObject journal=new JSONObject();journal.put("id",key);journal.put("phase","awaiting-contact-cycle");journal.put("backup_sha256",VehicleWriter.hash(backup));journal.put("cycle_off_seen",true);store.save("pending-vehicle.json",journal);
                Model model=new Model(getTargetContext());VehicleWriter restarted=new VehicleWriter(model,store);check(restarted.pending.optBoolean("interrupted")&&!restarted.pending.optBoolean("cycle_off_seen"));
                byte[] encrypted=bytes(new File(directory,"pending-vehicle.json"));encrypted[encrypted.length-1]^=1;write(new File(directory,"pending-vehicle.json"),encrypted);restarted=new VehicleWriter(model,store);check(restarted.pending.optString("phase").equals("corrupt"));
            });
            test("Editing a USB goal updates selection and enables plan preparation",()->{
                MainActivity activity=(MainActivity)startActivitySync(new Intent(getTargetContext(),MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                runOnMainSync(()->{
                    try{
                        Handler handler=(Handler)field(activity,"ui");handler.removeCallbacks((Runnable)field(activity,"heartbeat"));
                        Model model=(Model)field(activity,"model");
                        UsbSerialPort fake=(UsbSerialPort)Proxy.newProxyInstance(UsbSerialPort.class.getClassLoader(),new Class<?>[]{UsbSerialPort.class},(proxy,method,arguments)->method.getReturnType()==int.class?0:method.getReturnType()==boolean.class?false:null);
                        set(activity,"reader",new CanReader(fake,false,model));set(activity,"mode","usb");set(activity,"identity",new JSONObject("{\"product\":118632493,\"software\":\"0712.0002\",\"revision\":65569}"));set(activity,"draft",model.defaults("80"));
                        Method show=MainActivity.class.getDeclaredMethod("showPage",int.class);show.setAccessible(true);show.invoke(activity,2);
                        Button prepare=(Button)field(activity,"prepareVehicleButton");check(!prepare.isEnabled());View viewRoot=(View)field(activity,"root");
                        ((EditText)viewRoot.findViewWithTag("parameter-drive")).setText("70");check(prepare.isEnabled());check(((TextView)field(activity,"vehicleSelectionText")).getText().toString().startsWith("1 van"));
                        ((EditText)viewRoot.findViewWithTag("parameter-speed")).setText("90");check(((TextView)field(activity,"vehicleSelectionText")).getText().toString().startsWith("6 van"));
                        Method disconnect=MainActivity.class.getDeclaredMethod("disconnect");disconnect.setAccessible(true);disconnect.invoke(activity);set(activity,"mode","demo");set(activity,"draft",model.defaults("80"));show.invoke(activity,0);
                    }catch(Exception e){throw new RuntimeException(e);}
                });
            });
            result.putString("passed",Integer.toString(passed));result.putString("stream","ANDROID STORAGE: "+passed+" tests passed\n");finish(-1,result);
        }catch(Throwable error){result.putString("failure",error.toString());result.putString("stream","ANDROID STORAGE FAILURE: "+error+"\n");finish(0,result);}
    }
    private Object field(Object target,String name) throws Exception {Field f=MainActivity.class.getDeclaredField(name);f.setAccessible(true);return f.get(target);}
    private void set(Object target,String name,Object value) throws Exception {Field f=MainActivity.class.getDeclaredField(name);f.setAccessible(true);f.set(target,value);}
}

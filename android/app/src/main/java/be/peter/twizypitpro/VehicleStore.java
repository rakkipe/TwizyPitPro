package be.peter.twizypitpro;

import android.util.AtomicFile;
import org.json.JSONObject;
import java.io.*;

/** Private encrypted storage. Every intent is flushed before its CAN mutation. */
final class VehicleStore implements VehicleWriter.Store {
    private final File directory;
    private final Vault vault;
    VehicleStore(File files,Vault vault) throws IOException {
        directory=new File(files,"vehicle");this.vault=vault;
        if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("Voertuigopslag kon niet worden aangemaakt.");
    }
    private AtomicFile file(String name) throws IOException {
        if(!name.matches("[a-z0-9-]{1,80}\\.json"))throw new IOException("Ongeldige opslagnaam.");return new AtomicFile(new File(directory,name));
    }
    public JSONObject load(String name) throws Exception {
        AtomicFile file=file(name);
        if(!file.getBaseFile().exists()&&!new File(file.getBaseFile().getPath()+".bak").exists())return null;
        if(file.getBaseFile().length()>2000000||new File(file.getBaseFile().getPath()+".bak").length()>2000000)throw new IOException("Voertuigjournaal te groot.");
        return vault.decryptVehicle(name,file.readFully());
    }
    public void save(String name,JSONObject value) throws Exception {
        byte[] encrypted=vault.encryptVehicle(name,value);AtomicFile file=file(name);FileOutputStream out=null;
        if(encrypted.length>2000000)throw new IOException("Voertuigjournaal te groot.");
        try{
            out=file.startWrite();out.write(encrypted);out.getFD().sync();file.finishWrite(out);
            // AtomicFile can log a rename failure without throwing. Confirm the
            // committed bytes before the writer is allowed to mutate the bus.
            if(!java.util.Arrays.equals(encrypted,file.readFully()))throw new IOException("Opslagcommit niet bevestigd; niets verder schrijven.");
        }
        catch(Exception e){if(out!=null)file.failWrite(out);throw e;}
    }
    public void remove(String name) throws Exception {
        AtomicFile file=file(name);file.delete();
        if(file.getBaseFile().exists()||new File(file.getBaseFile().getPath()+".bak").exists()||new File(file.getBaseFile().getPath()+".new").exists())throw new IOException("Voertuigjournaal kon niet worden afgesloten.");
    }
}

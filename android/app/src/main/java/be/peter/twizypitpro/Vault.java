package be.peter.twizypitpro;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.AtomicFile;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.spec.ECGenParameterSpec;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;

/** Encrypted app storage. Commits require a per-use Android-authenticated signature. */
final class Vault {
    private static final String DATA_KEY="pit.v2.data", OWNER_KEY="pit.v2.owner";
    private final AtomicFile file;
    private final KeyStore keys;
    Vault(Context context) throws Exception {
        file=new AtomicFile(new File(context.getFilesDir(),"owner-vault.aes"));
        keys=KeyStore.getInstance("AndroidKeyStore");keys.load(null);
        if(!keys.containsAlias(DATA_KEY)) {
            if(file.getBaseFile().exists()) throw new SecurityException("De gegevenssleutel ontbreekt. Bestaande kluis wordt niet overschreven.");
            KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(DATA_KEY,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).build());
            generator.generateKey();
        }
    }
    JSONObject load() throws Exception {
        if(!file.getBaseFile().exists()) return null;
        byte[] bytes=file.readFully();
        if(bytes.length<29 || bytes[0]!=1) throw new SecurityException("Kluisindeling ongeldig.");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,keys.getKey(DATA_KEY,null),new GCMParameterSpec(128,bytes,1,12));
        cipher.updateAAD("TwizyPitPro-owner-v2".getBytes(StandardCharsets.UTF_8));
        return new JSONObject(new String(cipher.doFinal(bytes,13,bytes.length-13),StandardCharsets.UTF_8));
    }
    Signature challenge() throws Exception {
        if(!keys.containsAlias(OWNER_KEY)) {
            KeyPairGenerator generator=KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC,"AndroidKeyStore");
            generator.initialize(new KeyGenParameterSpec.Builder(OWNER_KEY,KeyProperties.PURPOSE_SIGN|KeyProperties.PURPOSE_VERIFY)
                .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1")).setDigests(KeyProperties.DIGEST_SHA256)
                .setUserAuthenticationRequired(true)
                .setUserAuthenticationParameters(0,KeyProperties.AUTH_BIOMETRIC_STRONG|KeyProperties.AUTH_DEVICE_CREDENTIAL).build());
            generator.generateKeyPair();
        }
        Signature signature=Signature.getInstance("SHA256withECDSA");
        signature.initSign((PrivateKey)keys.getKey(OWNER_KEY,null));
        return signature;
    }
    void commit(String payload, byte[] approval, byte[] nonce) throws Exception {
        Signature verify=Signature.getInstance("SHA256withECDSA");
        verify.initVerify(keys.getCertificate(OWNER_KEY).getPublicKey());
        verify.update(nonce); verify.update(payload.getBytes(StandardCharsets.UTF_8));
        if(!verify.verify(approval)) throw new SecurityException("Eigenaarsgoedkeuring ongeldig.");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE,keys.getKey(DATA_KEY,null));
        cipher.updateAAD("TwizyPitPro-owner-v2".getBytes(StandardCharsets.UTF_8));
        byte[] encrypted=cipher.doFinal(payload.getBytes(StandardCharsets.UTF_8));
        FileOutputStream out=null;
        try {
            out=file.startWrite();out.write(1);out.write(cipher.getIV());out.write(encrypted);file.finishWrite(out);
        } catch(Exception e) {if(out!=null)file.failWrite(out);throw e;}
    }
}

package be.peter.twizypitpro;

import android.content.Context;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Shared reference schemas; nothing in this class can write to a vehicle. */
final class Model {
    final JSONObject catalog;
    Model(JSONObject catalog){this.catalog=catalog;}
    Model(Context context) throws Exception {
        try(InputStream in=context.getAssets().open("catalog.json")) {
            ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] bytes=new byte[4096];int n;while((n=in.read(bytes))!=-1)out.write(bytes,0,n);
            catalog=new JSONObject(out.toString("UTF-8"));
        }
    }
    JSONArray parameters(String model) {return catalog.optJSONArray(model.equals("45")?"45":"80");}
    JSONObject defaults(String model) {
        JSONObject result=new JSONObject();JSONArray params=parameters(model);
        for(int i=0;i<params.length();i++){JSONObject p=params.optJSONObject(i);put(result,p.optString("key"),p.optInt("default"));}
        return result;
    }
    JSONObject fresh() {
        JSONObject obj=new JSONObject();
        put(obj,"format","TwizyPitPro-android-v2");put(obj,"model","80");put(obj,"software","0712.0002");
        put(obj,"values",defaults("80"));put(obj,"profiles",new JSONArray());put(obj,"sessions",new JSONArray());
        put(obj,"audit",new JSONArray());put(obj,"keep_awake",true);put(obj,"haptics",true);put(obj,"fault","none");
        return obj;
    }
    void validate(JSONObject values,String model) {
        if(values==null || values.length()!=parameters(model).length())throw new IllegalArgumentException("Onvolledig profiel of onbekende instellingen.");
        JSONArray params=parameters(model);
        for(int i=0;i<params.length();i++) {
            JSONObject p=params.optJSONObject(i);Object raw=values.opt(p.optString("key"));
            if(!(raw instanceof Number))throw new IllegalArgumentException(p.optString("name")+": gebruik een geheel getal.");
            double v=((Number)raw).doubleValue();
            if(!Double.isFinite(v)||v!=Math.rint(v)||v<p.optInt("min")||v>p.optInt("max"))throw new IllegalArgumentException(p.optString("name")+": buiten het editorbereik.");
        }
        if(values.optInt("warn")<=values.optInt("speed"))throw new IllegalArgumentException("Overspeedwaarschuwing moet hoger zijn dan maximumsnelheid.");
        if(values.optInt("brakelight_on")<values.optInt("brakelight_off"))throw new IllegalArgumentException("Remlicht-aan moet minstens gelijk zijn aan remlicht-uit.");
        for(String map:new String[]{"D","N","B"})for(int i=1;i<4;i++)if(values.optInt(map+"_speed"+i)>=values.optInt(map+"_speed"+(i+1)))throw new IllegalArgumentException("Koppelkaart "+map+": snelheden moeten oplopen.");
    }
    static boolean known(String model,String firmware,long revision) {
        return (model.equals("45")||model.equals("80"))&&((firmware.equals("0712.0001")&&revision==0x10019)||(firmware.equals("0712.0002")&&revision==0x10021));
    }
    static String modelOf(JSONObject identity) {
        long product=identity.optLong("product",-1);return product==0x0712302dL?"80":product==0x0712301bL?"45":"?";
    }
    static long revision(String firmware){return firmware.equals("0712.0001")?0x10019:firmware.equals("0712.0002")?0x10021:-1;}
    static JSONObject copy(JSONObject obj){try{return new JSONObject(obj.toString());}catch(JSONException e){throw new IllegalArgumentException(e);}}
    static void put(JSONObject obj,String key,Object value){try{obj.put(key,value);}catch(JSONException e){throw new IllegalArgumentException(e);}}
    static String now(){return java.time.Instant.now().toString();}
    static String csv(String value){return "\""+value.replace("\"","\"\"")+"\"";}
    static String sha(String text){try {byte[] hash=java.security.MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));StringBuilder s=new StringBuilder();for(byte b:hash)s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}catch(Exception e){throw new IllegalStateException(e);}}
}

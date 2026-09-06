package be.peter.twizypitpro;
import org.json.*;
import java.nio.file.*;
import java.util.*;
import java.io.*;

public final class TuningTests {
    static void check(boolean c){if(!c)throw new AssertionError();}
    static JSONObject row(JSONArray rows,String address){for(int i=0;i<rows.length();i++)if(rows.optJSONObject(i).optString("address").equals(address))return rows.optJSONObject(i);throw new AssertionError(address);}
    public static void main(String[] args)throws Exception{
        Model model=new Model(new JSONObject(Files.readString(Path.of(args[0]))));
        CoreTests.test("75 distinct targets cover all 43 settings",()->{
            for(String car:new String[]{"45","80"}){JSONArray rs=Tuning.targets(model,model.defaults(car),car,null);Set<String> addresses=new HashSet<>(),keys=new HashSet<>();for(int i=0;i<rs.length();i++){JSONObject r=rs.optJSONObject(i);addresses.add(r.optString("address"));JSONArray k=r.optJSONArray("keys");for(int n=0;n<k.length();n++)keys.add(k.optString(n));}check(addresses.size()==75&&keys.size()==43);check(row(rs,"2910:01").isNull("raw"));}
        });
        CoreTests.test("independent documented default register values",()->{
            JSONArray rs=Tuning.targets(model,model.defaults("80"),"80",0x20cL);check(row(rs,"6075:00").optLong("raw")==450000);check(row(rs,"6076:00").optLong("raw")==55000);check(row(rs,"2916:01").optInt("width")==4);check(row(rs,"4611:12").optLong("raw")==7250);check(row(rs,"3813:24").optLong("raw")==32767);check(row(rs,"3813:0B").optLong("raw")==16383);
        });
        CoreTests.test("Python and Java targets agree for 14 complete profiles",()->{
            JSONArray vectors=new JSONArray(Files.readString(Path.of(args[1])));
            for(int n=0;n<vectors.length();n++){JSONObject v=vectors.optJSONObject(n);JSONArray actual=Tuning.targets(model,v.optJSONObject("values"),v.optString("model"),v.optLong("flags")),expected=v.optJSONArray("expected");check(actual.length()==expected.length());for(int i=0;i<actual.length();i++){JSONObject a=actual.optJSONObject(i),e=expected.optJSONObject(i);for(String key:new String[]{"address","width","signed","raw"})if(!a.opt(key).toString().equals(e.opt(key).toString()))throw new AssertionError(n+" "+a.optString("address")+" "+key);}}
        });
        CoreTests.test("CAN telemetry from protocol bytes",()->{
            JSONObject s=CanTelemetry.decode(CanTelemetry.parse("155 0006405480C80000\r599 0000000000001388\r55F 0000000000D80D80\r"));check(s.optDouble("speed")==50);check(s.optDouble("soc")==82.42);check(s.optDouble("current")==100);check(s.optDouble("voltage")==54);check(s.optDouble("power")==5.4);
        });
        CoreTests.test("invalid latest frame cannot leave stale speed",()->{
            JSONObject s=CanTelemetry.decode(CanTelemetry.parse("599 0000000000001388\n599 000000000000FFFF\n155 0006409480C80000\n"));check(!s.has("speed")&&!s.has("soc"));
        });
        CoreTests.test("no baseline from demo report",()->{
            JSONObject scan=new JSONObject("{\"mode\":\"demo\",\"registers\":[{\"address\":\"2920:01\",\"width\":2,\"raw\":700}]}");JSONArray rs=Tuning.compare(model,model.defaults("80"),"80",scan);check(row(rs,"2920:01").isNull("before"));
        });
        CoreTests.test("mismatched and truncated SDO replies rejected",()->{
            CanReader r=new CanReader((req,match)->new byte[]{0x4b,0x21,0x29,1,0,0,0,0});CoreTests.rejects(()->r.number(0x2920,1,2,false));CanReader shortReply=new CanReader((req,match)->new byte[]{0x4b});CoreTests.rejects(()->shortReply.number(0x2920,1,2,false));
        });
        System.out.println("ANDROID EXTENSIONS: 7 tests passed");
    }
}

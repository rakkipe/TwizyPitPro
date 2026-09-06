package be.peter.twizypitpro;
import org.json.*;
import java.nio.file.*;
import java.util.*;
import java.io.*;

public final class CoreTests {
    interface Case {void run() throws Exception;}
    private static int passed;
    static void check(boolean condition){if(!condition)throw new AssertionError();}
    static void rejects(Case test)throws Exception{try{test.run();throw new AssertionError("Expected rejection");}catch(IllegalArgumentException|IOException expected){}}
    static void test(String name,Case body)throws Exception{body.run();passed++;System.out.println("PASS "+name);}
    public static void main(String[] args)throws Exception{
        Model model=new Model(new JSONObject(Files.readString(Path.of(args[0]))));
        test("43 parameters for both models",()->{check(model.parameters("45").length()==43);check(model.parameters("80").length()==43);model.validate(model.defaults("45"),"45");model.validate(model.defaults("80"),"80");});
        test("unknown fields rejected",()->{JSONObject v=model.defaults("80");Model.put(v,"unlock",1);rejects(()->model.validate(v,"80"));});
        test("missing fields rejected",()->{JSONObject v=model.defaults("80");v.remove("speed");rejects(()->model.validate(v,"80"));});
        test("boolean number rejected",()->{JSONObject v=model.defaults("80");Model.put(v,"speed",true);rejects(()->model.validate(v,"80"));});
        test("fraction and out of range rejected",()->{JSONObject v=model.defaults("80");Model.put(v,"speed",80.5);rejects(()->model.validate(v,"80"));Model.put(v,"speed",121);rejects(()->model.validate(v,"80"));});
        test("dependent overspeed guard",()->{JSONObject v=model.defaults("80");Model.put(v,"warn",80);rejects(()->model.validate(v,"80"));});
        test("map order guard",()->{JSONObject v=model.defaults("80");Model.put(v,"D_speed2",33);rejects(()->model.validate(v,"80"));});
        test("brake light hysteresis guard",()->{JSONObject v=model.defaults("80");Model.put(v,"brakelight_on",10);rejects(()->model.validate(v,"80"));});
        test("exact revision required",()->{check(Model.known("80","0712.0002",0x10021));check(!Model.known("80","0712.0002",0x10019));check(!Model.known("80","0712.0003",0x10021));check(!Model.known("?","0712.0002",0x10021));});
        test("controller model identification",()->{JSONObject id=new JSONObject();Model.put(id,"product",0x0712302d);check(Model.modelOf(id).equals("80"));Model.put(id,"product",0x0712301b);check(Model.modelOf(id).equals("45"));Model.put(id,"product",22);check(Model.modelOf(id).equals("?"));});
        test("upload-only request whitelist",()->{for(int i=0;i<256;i++){byte[] b=new byte[8];b[0]=(byte)i;check(CanReader.allowed(b)==(i==0x40||i==0x60||i==0x70));}check(!CanReader.allowed(new byte[]{0x40}));});
        test("expedited SDO width",()->{CanReader c=new CanReader((req,match)->{check(req[0]==0x40);byte[] r={0x4b,0x20,0x29,1,(byte)0xe8,3,0,0};check(match.test(r));return r;});check(c.number(0x2920,1,2,false)==1000);rejects(()->c.number(0x2920,1,4,false));});
        test("signed SDO",()->{CanReader c=new CanReader((req,match)->new byte[]{0x4b,0,0x46,3,(byte)0xf6,(byte)0xff,0,0});check(c.number(0x4600,3,2,true)==-10);});
        test("SDO abort detected",()->{CanReader c=new CanReader((req,match)->new byte[]{(byte)0x80,0,0x46,3,0,0,2,6});rejects(()->c.upload(0x4600,3));});
        test("segmented identity upload",()->{int[] n={0};CanReader c=new CanReader((req,match)->{byte[] r=n[0]++==0?new byte[]{0x41,0x0a,0x10,0,9,0,0,0}:n[0]==2?new byte[]{0,'0','7','1','2','.','0','0'}:new byte[]{0x1b,'0','2',0,0,0,0,0};check(match.test(r));return r;});check(new String(c.upload(0x100a,0)).equals("0712.0002"));});
        test("bad segment toggle rejected",()->{int[] n={0};CanReader c=new CanReader((req,match)->n[0]++==0?new byte[]{0x41,0x0a,0x10,0,9,0,0,0}:new byte[]{0x10,1,2,3,4,5,6,7});rejects(()->c.upload(0x100a,0));});
        test("oversize object rejected",()->{CanReader c=new CanReader((req,match)->new byte[]{0x41,0x0a,0x10,0,0,2,0,0});rejects(()->c.upload(0x100a,0));});
        test("public network and URL credentials blocked",()->{rejects(()->new LaptopLink("http://8.8.8.8:8765/?viewer=abcdefghijklmnopqrstuvwxyz123456"));rejects(()->new LaptopLink("http://a:b@192.168.1.5:8765/?viewer=abcdefghijklmnopqrstuvwxyz123456"));rejects(()->new LaptopLink("http://example.org/?viewer=abcdefghijklmnopqrstuvwxyz123456"));});
        test("local viewer URL only",()->{LaptopLink l=new LaptopLink("http://192.168.1.5:8765/?viewer=abcdefghijklmnopqrstuvwxyz123456");check(l.base.equals("http://192.168.1.5:8765"));rejects(()->new LaptopLink("http://192.168.1.5:8765/"));});
        System.out.println("ANDROID CORE: "+passed+" tests passed");
    }
}

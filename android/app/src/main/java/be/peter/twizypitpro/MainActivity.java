package be.peter.twizypitpro;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.hardware.biometrics.*;
import android.hardware.usb.*;
import android.location.*;
import android.net.Uri;
import android.os.*;
import android.text.*;
import android.view.*;
import android.widget.*;
import com.hoho.android.usbserial.driver.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;
import static be.peter.twizypitpro.Model.put;

/** Native Android UI and owner approval coordinator. No WebView and no live writer. */
public final class MainActivity extends Activity implements LocationListener {
    private static final int BG=0xff101412,CARD=0xff1b221e,LIME=0xffd2fa69,TEXT=0xfff1f5ef,MUTED=0xff9aac9f,RED=0xffff9c87;
    private static final String USB_PERMISSION="be.peter.twizypitpro.USB_PERMISSION";
    private final Handler ui=new Handler(Looper.getMainLooper());
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private Model model; private Vault vault; private JSONObject config,draft,sample=new JSONObject(),identity=new JSONObject(),scan;
    private LinearLayout root,content,nav;private ScrollView pageScroll;private TextView statusText,speedText,modeText,gpsText,sessionText;
    private final HashMap<String,TextView> metrics=new HashMap<>();private TelemetryView chart;
    private int page=0,generation=0,linkEpoch=0;private boolean visible,authBusy,ioBusy,demoRunning,gpsOn,recording;
    private CancellationSignal authCancel;private String mode="demo",connectionNote="Zelfstandige simulator",pendingExport,pendingExportType;
    private CanReader reader;private LaptopLink laptop;private UsbSerialDriver pendingUsb;private boolean pendingM5;
    private JSONArray samples=new JSONArray(),laps=new JSONArray();private long started=SystemClock.elapsedRealtime(),recordStart,lastLap,lastSampleAt,liveSampleAt;
    private String recordName="",recordMode="";private Location gps;private LocationManager locations;
    private final Runnable heartbeat=new Runnable(){public void run(){if(!visible)return;tick();ui.postDelayed(this,1000);}};

    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        try{
            model=new Model(this);vault=new Vault(this);config=vault.load();if(config==null)config=model.fresh();
            validateConfig(config);draft=Model.copy(config.optJSONObject("values"));
            locations=getSystemService(LocationManager.class);buildShell();showPage(0);setupUsbReceiver();
        }catch(Exception e){LinearLayout fatal=column();fatal.setPadding(dp(24),dp(60),dp(24),dp(24));fatal.setBackgroundColor(BG);fatal.addView(text("Kluis vergrendeld",28,TEXT,true));fatal.addView(text("Bestaande gegevens zijn niet gewijzigd.\n"+safeError(e),16,RED,false));setContentView(fatal);}
    }
    private void validateConfig(JSONObject c){
        if(!"TwizyPitPro-android-v2".equals(c.optString("format")))throw new SecurityException("Onbekende kluisversie.");
        if(!c.optString("model").matches("45|80"))throw new SecurityException("Ongeldig model in kluis.");
        model.validate(c.optJSONObject("values"),c.optString("model"));
        if(c.optJSONArray("profiles")==null||c.optJSONArray("sessions")==null||c.optJSONArray("audit")==null)throw new SecurityException("Kluisstructuur onvolledig.");
    }
    private void buildShell(){
        root=column();root.setBackgroundColor(BG);root.setFitsSystemWindows(true);
        root.setOnApplyWindowInsetsListener((v,insets)->{android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());v.setPadding(bars.left,bars.top,bars.right,bars.bottom);return insets;});
        LinearLayout top=row();top.setGravity(Gravity.CENTER_VERTICAL);top.setPadding(dp(20),dp(14),dp(16),dp(12));
        ImageView icon=new ImageView(this);icon.setImageResource(R.drawable.pit_icon);top.addView(icon,new LinearLayout.LayoutParams(dp(42),dp(42)));
        LinearLayout brand=column();brand.setPadding(dp(10),0,0,0);brand.addView(text("TWIZY PIT PRO",17,TEXT,true));brand.addView(text("PETERS CIRCUITWERKPLAATS",9,MUTED,true));top.addView(brand,new LinearLayout.LayoutParams(0,-2,1));
        Button link=button("Verbind",false,()->showConnection());link.setTextSize(11);top.addView(link,new LinearLayout.LayoutParams(dp(87),dp(46)));root.addView(top);
        statusText=text("● DEMO    /    EIGENAARSGOEDKEURING ACTIEF",10,LIME,true);statusText.setPadding(dp(24),0,dp(20),dp(10));root.addView(statusText);
        ScrollView scroll=new ScrollView(this);pageScroll=scroll;scroll.setFillViewport(true);content=column();content.setPadding(dp(20),dp(8),dp(20),dp(24));scroll.addView(content);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        nav=row();nav.setPadding(dp(5),dp(4),dp(5),dp(7));nav.setBackgroundColor(CARD);root.addView(nav);
        String[] names={"Pit","Diagnose","Tuning","Sessies","Profielen","Garage"};String[] symbols={"◉","⌁","≋","◷","▤","⚙"};
        for(int i=0;i<names.length;i++){final int index=i;Button b=button(symbols[i]+"\n"+names[i],false,()->showPage(index));b.setTextSize(10);b.setPadding(0,0,0,0);b.setMinWidth(0);b.setMinimumWidth(0);nav.addView(b,new LinearLayout.LayoutParams(0,dp(58),1));}
        setContentView(root);awake();
    }
    private int dp(float v){return (int)(v*getResources().getDisplayMetrics().density+.5f);}
    private LinearLayout column(){LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.VERTICAL);return l;}
    private LinearLayout row(){LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.HORIZONTAL);return l;}
    private GradientDrawable background(int color,float radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;}
    private TextView text(String value,int size,int color,boolean bold){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(color);t.setFontFeatureSettings("tnum");t.setTypeface(Typeface.create("sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));t.setLineSpacing(dp(3),1);return t;}
    private Button button(String title,boolean primary,Runnable action){Button b=new Button(this);b.setText(title);b.setTextSize(13);b.setAllCaps(false);b.setTextColor(primary?BG:TEXT);b.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));b.setBackground(background(primary?LIME:0xff29352c,12));b.setPadding(dp(10),dp(8),dp(10),dp(8));b.setMinHeight(dp(48));b.setFilterTouchesWhenObscured(true);b.setOnClickListener(v->{try{action.run();}catch(Exception e){error(e);}});return b;}
    private void addButton(LinearLayout parent,String title,boolean primary,Runnable action){Button b=button(title,primary,action);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(50));p.topMargin=dp(10);parent.addView(b,p);}
    private LinearLayout card(String title,String caption){LinearLayout c=column();c.setPadding(dp(18),dp(18),dp(18),dp(18));c.setBackground(background(CARD,20));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.bottomMargin=dp(14);content.addView(c,p);if(title!=null)c.addView(text(title,18,TEXT,true));if(caption!=null){TextView t=text(caption,12,MUTED,false);t.setPadding(0,dp(7),0,dp(10));c.addView(t);}return c;}
    private void title(String label,String heading,String sub){TextView tag=text(label,10,LIME,true);tag.setLetterSpacing(.14f);content.addView(tag);TextView h=text(heading,30,TEXT,true);h.setPadding(0,dp(8),0,dp(5));content.addView(h);TextView s=text(sub,13,MUTED,false);s.setPadding(0,0,0,dp(20));content.addView(s);}
    private void kv(LinearLayout parent,String key,String value){LinearLayout r=row();r.setPadding(0,dp(8),0,dp(8));r.addView(text(key,12,MUTED,false),new LinearLayout.LayoutParams(0,-2,1));TextView v=text(value,12,TEXT,true);v.setGravity(Gravity.END);r.addView(v,new LinearLayout.LayoutParams(0,-2,1));parent.addView(r);}
    private EditText input(String hint,String value){EditText e=new EditText(this);e.setHint(hint);e.setText(value);e.setTextColor(TEXT);e.setHintTextColor(MUTED);e.setSingleLine(true);e.setTextSize(14);e.setPadding(dp(10),dp(12),dp(10),dp(12));e.setBackground(background(0xff111813,8));e.setFilters(new InputFilter[]{new InputFilter.LengthFilter(160)});return e;}
    private void showPage(int index){if(content==null||config==null)return;page=index;content.removeAllViews();metrics.clear();speedText=null;gpsText=null;sessionText=null;chart=null;
        for(int i=0;i<nav.getChildCount();i++){Button b=(Button)nav.getChildAt(i);b.setTextColor(i==page?LIME:MUTED);b.setBackground(background(i==page?0xff31402a:CARD,10));}
        switch(page){case 0:dashboard();break;case 1:diagnostics();break;case 2:tuning();break;case 3:sessions();break;case 4:profiles();break;default:garage();}
        updateMetrics();pageScroll.post(()->pageScroll.scrollTo(0,0));
    }
    private void dashboard(){
        title("RACE WEEKEND / PIT WALL","Klaar voor je volgende stint.","Diagnose, afstelling en sessiedata op één plek.");
        LinearLayout hero=card(null,null);GradientDrawable heroBackground=new GradientDrawable(GradientDrawable.Orientation.TL_BR,new int[]{0xff35472a,0xff1c2a20});heroBackground.setCornerRadius(dp(20));hero.setBackground(heroBackground);hero.setPadding(dp(20),dp(20),dp(20),dp(20));
        modeText=text(sourceLabel(),10,LIME,true);hero.addView(modeText);TextView car=text("TWIZY "+displayModel(),42,TEXT,true);car.setLetterSpacing(-.04f);hero.addView(car);
        kv(hero,"Controllerfirmware",displayFirmware());kv(hero,"Verbinding",connectionNote);kv(hero,"Live schrijftoegang","Geblokkeerd");
        LinearLayout speed=row();speed.setGravity(Gravity.BOTTOM);speedText=text("0",64,TEXT,true);speed.addView(speedText);TextView unit=text(" km/u",17,MUTED,false);unit.setPadding(0,0,0,dp(13));speed.addView(unit);hero.addView(speed);
        hero.addView(text(mode.equals("demo")?"Synthetische snelheid · geen prestatievoorspelling":"Snelheid onbekend zonder gekwalificeerde decoder",11,MUTED,false));
        if(mode.equals("demo"))addButton(hero,demoRunning?"Terug naar de pit ↙":"Start demoronde ↗",true,()->approve("Demoronde "+(demoRunning?"stoppen":"starten"),Model.copy(config),()->{demoRunning=!demoRunning;showPage(0);}));
        LinearLayout grid=row();content.addView(grid);metricCard(grid,"Accu","soc","%",0);metricCard(grid,"Motor","motor_temp","°C",1);
        grid=row();content.addView(grid);metricCard(grid,"Vermogen","power","kW",1);metricCard(grid,"12 V voeding","aux","V",1);
        LinearLayout graph=card("Telemetrie","Snelheid (demo/laptop); USB toont toerental. Laatste 90 metingen.");chart=new TelemetryView(this);graph.addView(chart,new LinearLayout.LayoutParams(-1,dp(155)));
        LinearLayout gpsCard=card("GPS van deze telefoon","GPS wordt apart van voertuigtelemetrie geregistreerd.");gpsText=text("GPS uit",15,TEXT,true);gpsCard.addView(gpsText);addButton(gpsCard,gpsOn?"GPS uitschakelen":"GPS inschakelen",false,()->toggleGps());
        if(config.has("pending")){LinearLayout pending=card("Demo-contactcyclus wacht","Een eerder toegepaste simulatie moet nog worden gecontroleerd.");addButton(pending,"Demo-contactcyclus afronden",true,()->finishCycle(false));addButton(pending,"Demo-snapshot herstellen",false,()->finishCycle(true));}
    }
    private void metricCard(LinearLayout parent,String title,String key,String unit,int digits){LinearLayout box=column();box.setBackground(background(CARD,16));box.setPadding(dp(16),dp(15),dp(12),dp(15));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(106),1);lp.bottomMargin=dp(12);if(parent.getChildCount()==0)lp.rightMargin=dp(10);parent.addView(box,lp);box.addView(text(title,12,MUTED,false));TextView value=text("— "+unit,25,TEXT,true);value.setTag(new String[]{unit,""+digits});box.addView(value);metrics.put(key,value);}
    private String sourceLabel(){return mode.equals("demo")?"● DEMO / GEEN VOERTUIGDATA":mode.equals("usb")?"● USB / ALLEEN UITLEZEN":mode.equals("laptop")?(sample.optString("source").equals("laptop-demo")?"● LAPTOP / DEMOGEGEVENS":"● LAPTOP / KIJKTOEGANG"):"● OFFLINE / HISTORISCHE SCAN";}
    private String displayModel(){return mode.equals("demo")?config.optString("model"):Model.modelOf(identity);}
    private String displayFirmware(){return mode.equals("demo")?config.optString("software"):identity.optString("software","Onbekend");}
    private void updateMetrics(){if(statusText==null)return;showValue(statusText,sourceLabel()+"    /    WIJZIGINGEN BEVEILIGD");
        boolean valid=mode.equals("demo")||(liveSampleAt>0&&SystemClock.elapsedRealtime()-liveSampleAt<6000);
        if(speedText!=null)showValue(speedText,valid?number(sample,"speed",0):"—");
        for(Map.Entry<String,TextView> entry:metrics.entrySet()){String[] tag=(String[])entry.getValue().getTag();showValue(entry.getValue(),(valid?number(sample,entry.getKey(),Integer.parseInt(tag[1])):"—")+" "+tag[0]);}
        if(gpsText!=null){boolean fresh=gps!=null&&SystemClock.elapsedRealtimeNanos()-gps.getElapsedRealtimeNanos()<8000000000L;gpsText.setText(!gpsOn?"GPS uit":!fresh?"Wachten op actuele GPS-fix…":String.format(Locale.ROOT,"%.1f km/u   ·   ±%.0f m",gps.hasSpeed()?gps.getSpeed()*3.6:0,gps.getAccuracy()));}
        if(sessionText!=null)sessionText.setText(recording?"OPNAME ●  "+duration(SystemClock.elapsedRealtime()-recordStart)+"  /  "+samples.length()+" metingen":samples.length()>0?"Opname gepauzeerd · "+samples.length()+" metingen nog opslaan":"Geen actieve opname");
    }
    private void showValue(TextView view,String value){if(!view.getText().toString().equals(value))view.setText(value);}
    private String number(JSONObject obj,String key,int digits){Object raw=obj.opt(key);if(!(raw instanceof Number)||!Double.isFinite(((Number)raw).doubleValue()))return "—";return String.format(Locale.forLanguageTag("nl-BE"),"%."+digits+"f",((Number)raw).doubleValue());}
    private void diagnostics(){
        title("DIAGNOSE / IDENTITEIT","Ken je machine.","Automatische herkenning na een echte controlleruitlezing.");
        LinearLayout id=card("Voertuigpaspoort",mode.equals("demo")?"Deze identiteit is gesimuleerd.":"Alleen daadwerkelijk gelezen velden worden ingevuld.");
        kv(id,"Model", "Twizy "+displayModel());kv(id,"Software",displayFirmware());kv(id,"Hardware",mode.equals("demo")?"DEMO-HW":identity.optString("hardware","Onbekend"));kv(id,"Serienummer",mode.equals("demo")?"DEMO":identity.optString("serial","Onbekend"));kv(id,"Dictionaryrevisie",mode.equals("demo")?String.format("0x%X",Model.revision(displayFirmware())):identity.has("revision")?String.format("0x%X",identity.optLong("revision")):"Onbekend");
        boolean known=Model.known(displayModel(),displayFirmware(),mode.equals("demo")?Model.revision(displayFirmware()):identity.optLong("revision",-1));
        kv(id,"Referentieschema",known?"Exacte combinatie herkend":"Onbekend / geblokkeerd");kv(id,"Voertuigschrijven","Niet beschikbaar");
        addButton(id,"Diagnose uitvoeren",true,()->runScan());
        LinearLayout report=card("Diagnoserapport",scan==null?"Nog geen scan in deze verbinding.":scan.optString("scope","Controlleruitlezing"));
        if(scan!=null){kv(report,"Tijdstip",scan.optString("at"));kv(report,"Herkomst",scan.optString("mode"));kv(report,"Volledig binnen scope",scan.optBoolean("complete")?"Ja":"Nee, leesfouten aanwezig");
            JSONArray rows=scan.optJSONArray("registers");if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);kv(report,r.optString("address"),r.optString("raw","Onbekend")+" · "+r.optInt("width")+" bytes");}
            JSONArray errors=scan.optJSONArray("errors");if(errors!=null)for(int i=0;i<errors.length();i++)report.addView(text(errors.optString(i),12,RED,false));
            addButton(report,"Rapport opslaan als JSON",false,()->export(scan.toString(),"twizy-diagnose.json","application/json"));}
        LinearLayout note=card("Storingen eerst begrijpen","SERV, temperatuur- of voedingsproblemen eerst onderzoeken. Er is geen knop om storingen te wissen of beveiligingen te omzeilen.");
        kv(note,"ECU / BMS / airbags","Geen volledige DTC-scan");
    }
    private void tuning(){
        title("SETUP STUDIO / ONTWERP","Elke instelling telt.","43 ontwerpvelden · Twizy "+config.optString("model")+" / "+config.optString("software"));
        LinearLayout info=card("Je afstelling blijft van jou","Bewerk eerst een ontwerp. Opslaan en toepassen vereisen een nieuwe eigenaarsbevestiging. Editorbereiken zijn geen bewezen veilige racegrenzen.");
        EditText search=input("Zoek instelling of groep…","");info.addView(search);
        LinearLayout buttons=row();Button compare=button("Vergelijk",true,()->compareDraft());Button save=button("Profiel opslaan",false,()->saveProfile());buttons.addView(compare,new LinearLayout.LayoutParams(0,dp(48),1));LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams(0,dp(48),1);bp.leftMargin=dp(8);buttons.addView(save,bp);info.addView(buttons);
        LinearLayout groups=column();content.addView(groups);
        renderParameters(groups,"");search.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int a,int b,int c){renderParameters(groups,s.toString());}public void afterTextChanged(Editable e){}});
    }
    private void renderParameters(LinearLayout groups,String query){groups.removeAllViews();JSONArray params=model.parameters(config.optString("model"));String last="";query=query.toLowerCase(Locale.ROOT);
        for(int i=0;i<params.length();i++){JSONObject p=params.optJSONObject(i);String key=p.optString("key"),group=p.optString("group");if(!(p.optString("name")+group).toLowerCase(Locale.ROOT).contains(query))continue;
            if(!group.equals(last)){TextView label=text(group.toUpperCase(Locale.ROOT),11,LIME,true);label.setPadding(0,dp(12),0,dp(10));groups.addView(label);last=group;}
            LinearLayout box=column();box.setPadding(dp(16),dp(14),dp(16),dp(12));box.setBackground(background(CARD,15));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.bottomMargin=dp(8);groups.addView(box,lp);
            TextView label=text(p.optString("name"),14,TEXT,true);box.addView(label);
            LinearLayout r=row();r.setGravity(Gravity.CENTER_VERTICAL);SeekBar slider=new SeekBar(this);slider.setMin(p.optInt("min"));slider.setMax(p.optInt("max"));slider.setProgress(draft.optInt(key));r.addView(slider,new LinearLayout.LayoutParams(0,dp(44),1));
            EditText value=input("",Integer.toString(draft.optInt(key)));value.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);value.setTextSize(15);value.setGravity(Gravity.CENTER);r.addView(value,new LinearLayout.LayoutParams(dp(66),dp(48)));r.addView(text(" "+p.optString("unit"),11,MUTED,false));box.addView(r);
            box.addView(text(p.optInt("min")+"–"+p.optInt("max")+" "+p.optString("unit")+"  ·  "+(p.optString("mapping").equals("sdo")?"SDO-referentie":"Ontwerpveld"),10,MUTED,false));
            label.setOnClickListener(v->message(p.optString("name"),p.optString("note")));
            slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onProgressChanged(SeekBar s,int v,boolean fromUser){if(fromUser){put(draft,key,v);value.setText(Integer.toString(v));}}public void onStartTrackingTouch(SeekBar s){}public void onStopTrackingTouch(SeekBar s){}});
            value.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int a,int c,int f){}public void onTextChanged(CharSequence s,int a,int b,int c){try{int n=Integer.parseInt(s.toString());put(draft,key,n);if(n>=p.optInt("min")&&n<=p.optInt("max")){slider.setProgress(n);value.setTextColor(TEXT);}else value.setTextColor(RED);}catch(NumberFormatException e){put(draft,key,JSONObject.NULL);value.setTextColor(RED);}}public void afterTextChanged(Editable e){}});
        }
    }
    private void compareDraft(){
        model.validate(draft,config.optString("model"));JSONObject proposed=Model.copy(draft);JSONObject before=config.optJSONObject("values");StringBuilder diff=new StringBuilder();JSONArray params=model.parameters(config.optString("model"));int count=0;
        for(int i=0;i<params.length();i++){JSONObject p=params.optJSONObject(i);String k=p.optString("key");if(before.optInt(k)!=proposed.optInt(k)){count++;diff.append(p.optString("name")).append(": ").append(before.optInt(k)).append(" → ").append(proposed.optInt(k)).append(" ").append(p.optString("unit")).append("\n");}}
        if(count==0){message("Geen wijzigingen","Het ontwerp is gelijk aan de actieve demo-afstelling.");return;}
        String blocker=demoBlocker();AlertDialog.Builder dialog=new AlertDialog.Builder(this).setTitle(count+" wijzigingen").setMessage(diff+"\n"+(blocker.isEmpty()?"Alleen de simulator wordt gewijzigd. Daarna volgt een demo-contactcyclus.":blocker)).setNegativeButton("Terug",null);
        if(blocker.isEmpty())dialog.setPositiveButton("Goedkeuren…",(d,w)->{
            String recheck=demoBlocker();if(!recheck.isEmpty()){message("Geblokkeerd",recheck);return;}
            JSONObject next=Model.copy(config);JSONObject pending=new JSONObject();put(pending,"before",Model.copy(before));put(pending,"after",proposed);put(pending,"at",Model.now());
            if(config.optString("fault").equals("writefail")){approve("Demo read-back-fout testen; oorspronkelijke waarden behouden",next,()->message("Demo-rollback uitgevoerd","Gesimuleerde read-back mislukt. Oorspronkelijke waarden behouden."));return;}
            put(next,"values",proposed);put(next,"pending",pending);approve("Demo-afstelling toepassen · "+countChanges(before,proposed)+" wijzigingen",next,()->{draft=Model.copy(config.optJSONObject("values"));showPage(0);});
        });dialog.show();
    }
    private int countChanges(JSONObject a,JSONObject b){int n=0;Iterator<String> keys=a.keys();while(keys.hasNext()){String k=keys.next();if(a.optInt(k)!=b.optInt(k))n++;}return n;}
    private String demoBlocker(){if(!mode.equals("demo"))return "Live schrijftoegang ontbreekt. Alleen een demo-afstelling kan worden toegepast.";if(demoRunning||recording)return "Stop de demoronde en opname vóór toepassing.";if(config.has("pending"))return "Rond eerst de vorige demo-contactcyclus af.";if(!Model.known(config.optString("model"),config.optString("software"),Model.revision(config.optString("software"))))return "Onbekende of vergrendelde firmwarecombinatie.";if(!config.optString("fault").matches("none|writefail"))return "Los het gesimuleerde foutscenario eerst op.";return "";}
    private void finishCycle(boolean restore){if(!mode.equals("demo")||demoRunning||recording)throw new IllegalStateException("Alleen in een stilstaande demo zonder opname.");JSONObject next=Model.copy(config),p=next.optJSONObject("pending");if(p==null)return;
        if(restore)put(next,"values",p.optJSONObject("before"));else if(!next.optJSONObject("values").toString().equals(p.optJSONObject("after").toString()))throw new IllegalStateException("Demo-read-back wijkt af. Herstel de snapshot.");next.remove("pending");
        approve(restore?"Demo-snapshot herstellen":"Demo-contactcyclus bevestigen",next,()->{draft=Model.copy(config.optJSONObject("values"));showPage(0);});
    }
    private void saveProfile(){model.validate(draft,config.optString("model"));JSONObject values=Model.copy(draft);EditText name=input("Naam","Circuit · setup "+(config.optJSONArray("profiles").length()+1));new AlertDialog.Builder(this).setTitle("Profiel bewaren").setView(name).setNegativeButton("Annuleer",null).setPositiveButton("Goedkeuren…",(d,w)->{
        try{String label=name.getText().toString().trim();if(label.isEmpty()||label.length()>80)throw new IllegalArgumentException("Gebruik een profielnaam van 1–80 tekens.");JSONObject p=new JSONObject();put(p,"format","TwizyPitPro-profile-v1");put(p,"name",label);put(p,"model",config.optString("model"));put(p,"software",config.optString("software"));put(p,"revision",Model.revision(config.optString("software")));put(p,"values",values);put(p,"at",Model.now());JSONObject next=Model.copy(config);JSONArray profiles=next.optJSONArray("profiles");if(profiles.length()>=100)throw new IllegalArgumentException("Maximaal 100 profielen. Exporteer en verwijder eerst een oud profiel.");profiles.put(p);approve("Profiel opslaan: "+label,next,()->showPage(4));}catch(Exception e){error(e);}
    }).show();}
    private void profiles(){
        title("SETUP BIBLIOTHEEK","Een plan voor elke stint.","Versiegebonden ontwerpen, versleuteld op deze telefoon.");
        LinearLayout actions=card("Profielen uitwisselen","Import controleert model, firmware, revisie en alle waarden.");addButton(actions,"Ontwerp importeren uit JSON",false,()->{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("application/json").addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(i,42);});addButton(actions,"Huidig ontwerp exporteren",false,()->{model.validate(draft,config.optString("model"));JSONObject p=new JSONObject();put(p,"format","TwizyPitPro-profile-v1");put(p,"name","Android-ontwerp");put(p,"model",config.optString("model"));put(p,"software",config.optString("software"));put(p,"revision",Model.revision(config.optString("software")));put(p,"values",Model.copy(draft));export(p.toString(),"twizy-ontwerp.json","application/json");});
        JSONArray list=config.optJSONArray("profiles");if(list.length()==0)card("Je eerste setup","Bewerk instellingen onder Tuning en kies Profiel opslaan.");
        for(int i=list.length()-1;i>=0;i--){final int index=i;JSONObject p=list.optJSONObject(i);LinearLayout c=card(p.optString("name"),"Twizy "+p.optString("model")+" · "+p.optString("software")+" · "+p.optJSONObject("values").length()+" velden");
            addButton(c,"Open in ontwerpstudio",true,()->{checkProfile(p);draft=Model.copy(p.optJSONObject("values"));showPage(2);});addButton(c,"Exporteer profiel",false,()->export(p.toString(),"twizy-profiel.json","application/json"));addButton(c,"Verwijder profiel…",false,()->confirmDelete("Profiel verwijderen",()->{JSONObject next=Model.copy(config);next.optJSONArray("profiles").remove(index);approve("Profiel verwijderen: "+p.optString("name"),next,()->showPage(4));}));}
        LinearLayout bundles=card("Model- en firmwarepakketten","Twizy 45 en 80 × 0712.0001 / 0712.0002. Dit zijn referentieschema's, geen flashbestanden.");addButton(bundles,"Versieschema's exporteren",false,()->export(model.catalog.optJSONArray("variants").toString(),"twizy-versieschemas.json","application/json"));
    }
    private void checkProfile(JSONObject p){if(!p.optString("format").equals("TwizyPitPro-profile-v1")||!p.optString("model").equals(config.optString("model"))||!p.optString("software").equals(config.optString("software"))||p.optLong("revision",-2)!=Model.revision(config.optString("software")))throw new IllegalArgumentException("Model, firmware of dictionaryrevisie wijkt af van het gekozen ontwerpmodel.");model.validate(p.optJSONObject("values"),config.optString("model"));}
    private void sessions(){
        title("DATA ACQUISITION","Maak je stint inzichtelijk.","Telemetrie, GPS en handmatig gemarkeerde rondetijden.");
        LinearLayout c=card("Sessieopname","Opname alleen terwijl de app vooraan staat. Maximaal 1 uur / 3600 metingen. Bewaar de opname vóór je de app sluit.");sessionText=text("",14,LIME,true);c.addView(sessionText);
        addButton(c,"Nieuwe opname starten",true,()->startRecording());addButton(c,"Ronde markeren",false,()->markLap());addButton(c,"Opname stoppen & bewaren",false,()->stopRecording());
        if(laps.length()>0){LinearLayout lc=card("Huidige rondes","Handmatige markeringen, geen transpondertijden.");for(int i=0;i<laps.length();i++)kv(lc,"Ronde "+(i+1),duration(laps.optJSONObject(i).optLong("duration_ms")));}
        JSONArray sessions=config.optJSONArray("sessions");for(int i=sessions.length()-1;i>=0;i--){final int index=i;JSONObject s=sessions.optJSONObject(i);LinearLayout sc=card(s.optString("name"),s.optString("mode")+" · "+s.optString("at"));kv(sc,"Metingen",Integer.toString(s.optJSONArray("samples").length()));JSONArray ls=s.optJSONArray("laps");for(int j=0;j<ls.length();j++)kv(sc,"Ronde "+(j+1),duration(ls.optJSONObject(j).optLong("duration_ms")));addButton(sc,"Telemetrie als CSV",false,()->export(sessionCsv(s),"twizy-sessie.csv","text/csv"));addButton(sc,"Volledig sessierapport",false,()->export(s.toString(),"twizy-sessie.json","application/json"));addButton(sc,"Verwijder sessie…",false,()->confirmDelete("Sessie verwijderen",()->{JSONObject next=Model.copy(config);next.optJSONArray("sessions").remove(index);approve("Sessie verwijderen",next,()->showPage(3));}));}
    }
    private void startRecording(){if(recording||samples.length()>0)throw new IllegalStateException("Bewaar eerst de huidige opname.");if(mode.equals("offline"))throw new IllegalStateException("Geen actuele gegevensbron.");if(config.optJSONArray("sessions").length()>=12)throw new IllegalStateException("Maximaal 12 sessies. Exporteer en verwijder eerst een oude sessie.");EditText name=input("Sessienaam","Circuit · stint "+(config.optJSONArray("sessions").length()+1));new AlertDialog.Builder(this).setTitle("Sessie starten").setView(name).setNegativeButton("Annuleer",null).setPositiveButton("Goedkeuren…",(d,w)->approve("Sessieopname toestaan",Model.copy(config),()->{recording=true;recordName=name.getText().toString();recordMode=mode;recordStart=lastLap=SystemClock.elapsedRealtime();samples=new JSONArray();laps=new JSONArray();showPage(3);})).show();}
    private void markLap(){if(!recording)throw new IllegalStateException("Start eerst een opname.");long now=SystemClock.elapsedRealtime();JSONObject lap=new JSONObject();put(lap,"duration_ms",now-lastLap);put(lap,"elapsed_ms",now-recordStart);put(lap,"at",Model.now());put(lap,"source","manual");laps.put(lap);lastLap=now;haptic();showPage(3);}
    private void stopRecording(){if(samples.length()==0)throw new IllegalStateException("Nog geen metingen om te bewaren.");recording=false;JSONObject session=new JSONObject();put(session,"name",recordName);put(session,"mode",recordMode);put(session,"at",Model.now());put(session,"samples",samples);put(session,"laps",laps);put(session,"identity",Model.copy(identity));put(session,"model",config.optString("model"));put(session,"software",config.optString("software"));put(session,"values",Model.copy(config.optJSONObject("values")));JSONObject next=Model.copy(config);next.optJSONArray("sessions").put(session);approve("Sessie bewaren: "+recordName,next,()->{samples=new JSONArray();laps=new JSONArray();showPage(3);});}
    private String sessionCsv(JSONObject session){String[] keys={"at","source","speed","rpm","power","soc","voltage","current","motor_temp","controller_temp","aux","gps_lat","gps_lon","gps_speed","gps_accuracy"};StringBuilder out=new StringBuilder(String.join(",",keys)+"\r\n");JSONArray rows=session.optJSONArray("samples");for(int i=0;i<rows.length();i++){JSONObject s=rows.optJSONObject(i);for(int j=0;j<keys.length;j++){if(j>0)out.append(',');String v=s.isNull(keys[j])?"":s.optString(keys[j],"");if(v.matches("^[=+@-].*")&&!v.matches("-?\\d+(\\.\\d+)?"))v="'"+v;out.append(Model.csv(v));}out.append("\r\n");}return out.toString();}
    private static String duration(long ms){return String.format(Locale.ROOT,"%02d:%02d.%03d",ms/60000,(ms/1000)%60,ms%1000);}
    private void garage(){
        title("GARAGE / EIGENAAR","Jouw pit. Jouw toestemming.","Android 0.2.0 · lokaal, ondertekend en zonder automatische updates.");
        LinearLayout secure=card("Eigenaarsbeveiliging","Iedere opgeslagen wijziging vraagt Android-biometrie of je toestelcode. Iedere nieuwe handeling krijgt een eigen, eenmalige cryptografische goedkeuring.");
        kv(secure,"Toestelvergrendeling",getSystemService(KeyguardManager.class).isDeviceSecure()?"Actief":"Niet ingesteld · wijzigingen geblokkeerd");kv(secure,"Opslag","AES-256-GCM / Android Keystore");kv(secure,"Schermopname","Geblokkeerd");kv(secure,"Cloudback-up","Uitgeschakeld");kv(secure,"Voertuigschrijven","Ontbreekt in deze release");
        addButton(secure,"Controleer eigenaarsbevestiging",true,()->approve("Eigenaarsbeveiliging gecontroleerd",Model.copy(config),()->message("Bevestigd","Je toestemming is met een Android Keystore-sleutel gecontroleerd en in het logboek vastgelegd.")));
        LinearLayout hardware=card("Hardware","vLinker FS of M5 PitBridge via USB-C/OTG; laptop via lokale wifi. USB-drivers zijn ingebouwd. Hardwarevalidatie is nog nodig.");addButton(hardware,"Verbinding kiezen",true,()->showConnection());
        LinearLayout simulation=card("Simulator","Model- en firmwarewissels passen alleen de lokale demo aan.");addButton(simulation,"Model: Twizy "+config.optString("model"),false,()->choose("Demomodel",new String[]{"Twizy 45","Twizy 80"},n->changeScenario(n==0?"45":"80",config.optString("software"))));addButton(simulation,"Firmware: "+config.optString("software"),false,()->choose("Firmware",new String[]{"0712.0001","0712.0002","0712.0003","9999.9999"},n->changeScenario(config.optString("model"),new String[]{"0712.0001","0712.0002","0712.0003","9999.9999"}[n])));
        addButton(simulation,"Foutscenario: "+config.optString("fault"),false,()->choose("Gesimuleerde storing",new String[]{"Geen storing","SERV","12 V te laag","Motor te warm","Read-back-fout"},n->{if(!mode.equals("demo")||recording)throw new IllegalStateException("Alleen wijzigen in demo zonder opname.");JSONObject next=Model.copy(config);put(next,"fault",new String[]{"none","serv","12v","thermal","writefail"}[n]);approve("Demo-foutscenario wijzigen",next,()->showPage(5));}));
        LinearLayout pref=card("Pitinstellingen",null);addButton(pref,"Scherm aanhouden: "+(config.optBoolean("keep_awake")?"aan":"uit"),false,()->togglePreference("keep_awake","Scherminstelling wijzigen"));addButton(pref,"Trilsignalen: "+(config.optBoolean("haptics")?"aan":"uit"),false,()->togglePreference("haptics","Trilsignalen wijzigen"));addButton(pref,"GPS: "+(gpsOn?"aan":"uit"),false,()->toggleGps());
        LinearLayout audit=card("Goedkeuringslogboek","Laatste 200 bevestigde handelingen in de versleutelde kluis.");JSONArray log=config.optJSONArray("audit");for(int i=log.length()-1;i>=Math.max(0,log.length()-8);i--){JSONObject a=log.optJSONObject(i);kv(audit,a.optString("action"),a.optString("at"));}addButton(audit,"Logboek exporteren",false,()->export(config.optJSONArray("audit").toString(),"twizy-goedkeuringen.json","application/json"));
        LinearLayout about=card("Over deze release","Een native Android-app met eigen opslag en USB-uitleesstack. Geen live tuning, firmwareflash of automatische GPS-rondedetectie. Een gewijzigde motor/reductiekast kan niet alleen uit een controller-ID worden afgeleid.");
        addButton(about,"Beveiliging en bronnen",false,()->message("Beveiliging & bronnen","Eigen toestelcode = eigenaarsbewijs. Iedereen met een geregistreerde vingerafdruk of jouw toestelcode kan bevestigen. Een rooted toestel of beheerder valt buiten deze bescherming.\n\nExports zijn gewone leesbare bestanden op een door jou gekozen locatie.\n\nAndroid Keystore / BiometricPrompt: developer.android.com\nUSB Serial 3.10.0 (MIT): github.com/mik3y/usb-serial-for-android\nTwizy-referenties (MIT): github.com/openvehicles/Open-Vehicle-Monitoring-System-3\n\nDe laptopviewer gebruikt HTTP: kies je eigen hotspot of vertrouwd wifi-netwerk. De APK stuurt geen bedieningsacties naar de laptop."));
    }
    private void togglePreference(String key,String action){JSONObject next=Model.copy(config);put(next,key,!next.optBoolean(key));approve(action,next,()->{awake();showPage(5);});}
    private void changeScenario(String car,String firmware){if(recording||samples.length()>0||config.has("pending"))throw new IllegalStateException("Bewaar de opname en rond de demo-contactcyclus eerst af.");JSONObject next=Model.copy(config);put(next,"model",car);put(next,"software",firmware);put(next,"values",model.defaults(car));put(next,"fault","none");approve("Demo wijzigen naar Twizy "+car+" / "+firmware,next,()->{disconnect();mode="demo";connectionNote="Zelfstandige simulator";demoRunning=false;draft=Model.copy(config.optJSONObject("values"));scan=null;showPage(5);});}
    private interface Choice {void accept(int n);}
    private void choose(String title,String[] options,Choice action){new AlertDialog.Builder(this).setTitle(title).setItems(options,(d,n)->{try{action.accept(n);}catch(Exception e){error(e);}}).setNegativeButton("Annuleer",null).show();}
    private void confirmDelete(String title,Runnable action){new AlertDialog.Builder(this).setTitle(title).setMessage("Deze lokale kopie verwijderen? Exporteer eerst als je die wilt bewaren.").setNegativeButton("Annuleer",null).setPositiveButton("Goedkeuren…",(d,n)->action.run()).show();}

    private void approve(String action,JSONObject proposed,Runnable success){
        if(authBusy)throw new IllegalStateException("Er wacht al een eigenaarsbevestiging.");
        if(!getSystemService(KeyguardManager.class).isDeviceSecure()){message("Toestelvergrendeling vereist","Stel eerst een privé-pincode, wachtwoord of biometrie in via Android-instellingen. Zonder vergrendeling blijven wijzigingen geblokkeerd.");return;}
        try{
            validateConfig(proposed);JSONArray log=proposed.optJSONArray("audit");JSONObject event=new JSONObject();put(event,"at",Model.now());put(event,"action",action);put(event,"previous",log.length()==0?"":Model.sha(log.optJSONObject(log.length()-1).toString()));put(event,"config_sha256",Model.sha(proposed.optJSONObject("values").toString()));log.put(event);if(log.length()>200)log.remove(0);
            final String payload=proposed.toString();final byte[] nonce=new byte[32];new SecureRandom().nextBytes(nonce);final int version=generation;final long expires=SystemClock.elapsedRealtime()+120000;
            Signature signature=vault.challenge();authBusy=true;authCancel=new CancellationSignal();
            BiometricPrompt prompt=new BiometricPrompt.Builder(this).setTitle("Jouw toestemming").setSubtitle(action).setDescription("Bevestig deze ene handeling voor Twizy Pit Pro.").setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG|BiometricManager.Authenticators.DEVICE_CREDENTIAL).setConfirmationRequired(true).build();
            prompt.authenticate(new BiometricPrompt.CryptoObject(signature),authCancel,getMainExecutor(),new BiometricPrompt.AuthenticationCallback(){
                @Override public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result){
                    try{
                        if(!authBusy||version!=generation||SystemClock.elapsedRealtime()>expires||!visible)throw new SecurityException("Goedkeuring verlopen. Probeer opnieuw.");
                        Signature signed=result.getCryptoObject()==null?null:result.getCryptoObject().getSignature();if(signed==null)throw new SecurityException("Cryptografische goedkeuring ontbreekt.");
                        signed.update(nonce);signed.update(payload.getBytes(StandardCharsets.UTF_8));vault.commit(payload,signed.sign(),nonce);config=new JSONObject(payload);generation++;authBusy=false;authCancel=null;haptic();success.run();
                    }catch(Exception e){authBusy=false;authCancel=null;error(e);}
                }
                @Override public void onAuthenticationError(int code,CharSequence message){authBusy=false;authCancel=null;toast("Niet gewijzigd: "+message);}
            });
        }catch(Exception e){authBusy=false;authCancel=null;error(e);}
    }
    private void runScan(){if(ioBusy)throw new IllegalStateException("Een uitlezing is nog bezig.");
        if(mode.equals("demo")){JSONObject r=new JSONObject();put(r,"at",Model.now());put(r,"mode","demo");put(r,"identity",demoIdentity());put(r,"complete",true);put(r,"scope","Gesimuleerde diagnose. Geen voertuiggegevens.");JSONArray rows=new JSONArray();JSONObject row=new JSONObject();put(row,"address","1001:00");put(row,"width",1);put(row,"raw",config.optString("fault").equals("none")?0:1);rows.put(row);put(r,"registers",rows);put(r,"errors",new JSONArray());scan=r;showPage(1);return;}
        if(mode.equals("laptop")){message("Diagnose vanaf laptop","Voer de scan uit in de laptop-app. Het laatste rapport verschijnt daarna hier.");return;}
        if(reader==null)throw new IllegalStateException("Sluit eerst de USB-adapter aan.");CanReader active=reader;int version=generation;ioBusy=true;toast("Controller uitlezen…");worker.execute(()->{try{JSONObject result=active.diagnose();ui.post(()->{if(reader==active&&visible){scan=result;identity=result.optJSONObject("identity");showPage(1);}});}catch(Exception e){ui.post(()->error(e));}finally{ui.post(()->ioBusy=false);}});
    }
    private JSONObject demoIdentity(){JSONObject id=new JSONObject();put(id,"product",config.optString("model").equals("80")?0x0712302d:0x0712301b);put(id,"vendor",30);put(id,"revision",Model.revision(config.optString("software")));put(id,"software",config.optString("software"));put(id,"hardware","DEMO-HW");put(id,"source","simulation");return id;}
    private void tick(){
        if(config==null||content==null||authBusy)return;long now=SystemClock.elapsedRealtime();
        if(mode.equals("demo")){double t=(now-started)/1000.0;JSONObject values=config.optJSONObject("values");double speed=demoRunning?Math.max(0,Math.min(values.optInt("speed"),48+23*Math.sin(t/7)+8*Math.sin(t/2.7))):0;double power=demoRunning?(4.2+9*Math.sin(t/7+.7))*values.optInt("drive")/100.0:0;
            sample=new JSONObject();put(sample,"at",Model.now());put(sample,"source","simulation");put(sample,"speed",speed);put(sample,"power",power);put(sample,"rpm",speed*(config.optString("model").equals("45")?5814.0/45:7250.0/80));put(sample,"soc",82.4-(t%1200)/150);put(sample,"voltage",54.5-Math.max(0,power)*.12);put(sample,"current",power*1000/sample.optDouble("voltage"));put(sample,"aux",config.optString("fault").equals("12v")?10.8:12.7);put(sample,"motor_temp",config.optString("fault").equals("thermal")?125:43+(demoRunning?6*Math.sin(t/40):0));put(sample,"controller_temp",35);identity=demoIdentity();
        }else if(!ioBusy&&(reader!=null||laptop!=null)){
            ioBusy=true;final CanReader activeReader=reader;final LaptopLink activeLaptop=laptop;
            worker.execute(()->{try{
                JSONObject result=activeReader!=null?activeReader.sample():activeLaptop.state();
                ui.post(()->{if(!visible||reader!=activeReader||laptop!=activeLaptop)return;
                    if(activeReader!=null)sample=result;else {String previousIdentity=identity.toString(),previousNote=connectionNote,previousScan=scan==null?"":scan.optString("at");sample=result.optJSONObject("sample");put(sample,"source",result.optString("mode").equals("demo")?"laptop-demo":"laptop-live");identity=result.optJSONObject("identity");JSONObject report=result.optJSONObject("scan");if(report!=null)scan=report;connectionNote="Laptop: "+(result.optString("mode").equals("demo")?"DEMO":"LIVE UITLEZEN");if((page==0&&(!identity.toString().equals(previousIdentity)||!connectionNote.equals(previousNote)))||(page==1&&scan!=null&&!scan.optString("at").equals(previousScan)))showPage(page);}
                    liveSampleAt=SystemClock.elapsedRealtime();if(activeLaptop!=null&&sample.optDouble("age",0)>=6)liveSampleAt=0;updateMetrics();
                });
            }catch(Exception e){ui.post(()->{if(reader==activeReader&&laptop==activeLaptop){connectionNote="Verbinding verloren";disconnect();mode="offline";liveSampleAt=0;sample=new JSONObject();recording=false;showPage(page);toast(safeError(e));}});}finally{ui.post(()->ioBusy=false);}});
        }
        boolean valid=mode.equals("demo")||liveSampleAt>0&&now-liveSampleAt<6000;
        if(chart!=null)chart.add(valid?sample.optDouble(mode.equals("usb")?"rpm":"speed",Double.NaN):Double.NaN);
        if(recording&&valid&&now-lastSampleAt>=1000){JSONObject record=Model.copy(sample);put(record,"captured_at",Model.now());if(gpsOn&&gps!=null&&SystemClock.elapsedRealtimeNanos()-gps.getElapsedRealtimeNanos()<8000000000L){put(record,"gps_lat",gps.getLatitude());put(record,"gps_lon",gps.getLongitude());put(record,"gps_speed",gps.hasSpeed()?gps.getSpeed()*3.6:JSONObject.NULL);put(record,"gps_accuracy",gps.getAccuracy());}samples.put(record);lastSampleAt=now;if(samples.length()>=3600){recording=false;toast("Opnamelimiet bereikt. Bewaar je sessie.");}}
        updateMetrics();
    }
    private void showConnection(){if(recording||samples.length()>0)throw new IllegalStateException("Bewaar eerst de opname vóór je de gegevensbron wijzigt.");choose("Jouw pitverbinding",new String[]{"Zelfstandige demo","vLinker FS · USB-C/OTG","M5 PitBridge · USB-C/OTG","Laptop · wifi-kijktoegang","Verbinding sluiten"},n->{if(n==0){approve("Overschakelen naar demo",Model.copy(config),()->{disconnect();mode="demo";connectionNote="Zelfstandige simulator";scan=null;showPage(0);});}else if(n==1||n==2)chooseUsb(n==2);else if(n==3)connectLaptop();else approve("Verbinding sluiten",Model.copy(config),()->{disconnect();mode="offline";connectionNote="Niet verbonden";showPage(0);});});}
    private void chooseUsb(boolean m5){UsbManager manager=getSystemService(UsbManager.class);List<UsbSerialDriver> devices=UsbSerialProber.getDefaultProber().findAllDrivers(manager);if(devices.isEmpty()){message("Geen USB-adapter gevonden","Sluit de adapter aan via een USB-C/OTG-datakabel. vLinker FS is USB, geen Bluetooth-adapter. Kies voor M5 de PitBridge-firmware uit dit project.");return;}
        String[] labels=new String[devices.size()];for(int i=0;i<labels.length;i++){UsbDevice d=devices.get(i).getDevice();labels[i]=String.format(Locale.ROOT,"%s · %04X:%04X",d.getProductName()==null?"USB-serieel":d.getProductName(),d.getVendorId(),d.getProductId());}
        choose("Kies USB-adapter",labels,n->approve("USB-controller alleen uitlezen",Model.copy(config),()->{pendingUsb=devices.get(n);pendingM5=m5;if(manager.hasPermission(pendingUsb.getDevice()))openUsb();else {Intent intent=new Intent(USB_PERMISSION).setPackage(getPackageName());PendingIntent permission=PendingIntent.getBroadcast(this,0,intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_MUTABLE);manager.requestPermission(pendingUsb.getDevice(),permission);}}));
    }
    private final BroadcastReceiver usbReceiver=new BroadcastReceiver(){@Override public void onReceive(Context context,Intent intent){if(!USB_PERMISSION.equals(intent.getAction())||pendingUsb==null)return;UsbDevice device=intent.getParcelableExtra(UsbManager.EXTRA_DEVICE);if(device==null||!device.equals(pendingUsb.getDevice()))return;if(intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED,false)&&getSystemService(UsbManager.class).hasPermission(device))openUsb();else {pendingUsb=null;toast("USB-toestemming niet gegeven.");}}};
    private boolean receiverRegistered;
    private void setupUsbReceiver(){if(Build.VERSION.SDK_INT>=33)registerReceiver(usbReceiver,new IntentFilter(USB_PERMISSION),Context.RECEIVER_NOT_EXPORTED);else registerReceiver(usbReceiver,new IntentFilter(USB_PERMISSION));receiverRegistered=true;}
    private void openUsb(){UsbSerialDriver driver=pendingUsb;boolean m5=pendingM5;pendingUsb=null;if(driver==null||!visible)return;disconnect();final int epoch=linkEpoch;ioBusy=true;connectionNote="USB verbinden…";toast(connectionNote);
        worker.execute(()->{CanReader opened=null;try{UsbDeviceConnection connection=getSystemService(UsbManager.class).openDevice(driver.getDevice());if(connection==null)throw new IOException("USB openen mislukt.");UsbSerialPort port=driver.getPorts().get(0);try{port.open(connection);port.setParameters(115200,8,UsbSerialPort.STOPBITS_1,UsbSerialPort.PARITY_NONE);}catch(Exception e){try{port.close();}catch(Exception ignored){}connection.close();throw e;}opened=new CanReader(port,m5);opened.initialize();JSONObject id=opened.identity();final CanReader ready=opened;ui.post(()->{if(!visible||linkEpoch!=epoch){try{ready.close();}catch(Exception ignored){}return;}reader=ready;identity=id;mode="usb";connectionNote=m5?"M5 PitBridge · READONLY":"vLinker FS · READONLY";sample=new JSONObject();liveSampleAt=0;scan=null;showPage(1);});}catch(Exception e){if(opened!=null)try{opened.close();}catch(Exception ignored){}ui.post(()->{if(linkEpoch==epoch&&visible){mode="offline";connectionNote="USB niet verbonden";error(e);showPage(0);}});}finally{ui.post(()->{if(linkEpoch==epoch)ioBusy=false;});}});
    }
    private void connectLaptop(){EditText url=input("http://192.168.…:8765/?viewer=…","");url.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);new AlertDialog.Builder(this).setTitle("Koppel de laptop").setMessage("Plak de telefoonviewerlink uit Hardware in de laptop-app. Gebruik je eigen hotspot of vertrouwd wifi: deze verbinding gebruikt HTTP en krijgt alleen kijktoegang.").setView(url).setNegativeButton("Annuleer",null).setPositiveButton("Goedkeuren…",(d,w)->{try{LaptopLink candidate=new LaptopLink(url.getText().toString());approve("Laptopviewer verbinden",Model.copy(config),()->{disconnect();laptop=candidate;mode="laptop";connectionNote="Laptop verbinden…";scan=null;showPage(0);});}catch(Exception e){error(e);}}).show();}
    private void disconnect(){linkEpoch++;CanReader old=reader;reader=null;laptop=null;liveSampleAt=0;sample=new JSONObject();demoRunning=false;ioBusy=false;if(old!=null)worker.execute(()->{try{old.close();}catch(Exception ignored){}});}
    private void toggleGps(){approve(gpsOn?"GPS uitschakelen":"GPS tijdens gebruik toestaan",Model.copy(config),()->{if(gpsOn){gpsOn=false;locations.removeUpdates(this);gps=null;showPage(page);}else if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION},44);else enableGps();});}
    private void enableGps(){try{if(!locations.isProviderEnabled(LocationManager.GPS_PROVIDER)){message("GPS staat uit","Schakel locatie in via Android-instellingen.");return;}locations.requestLocationUpdates(LocationManager.GPS_PROVIDER,1000,0,this);gpsOn=true;showPage(page);}catch(SecurityException e){error(e);}}
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);if(request==44&&results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)enableGps();else if(request==44)toast("Nauwkeurige GPS-toestemming ontbreekt.");}
    @Override public void onLocationChanged(Location location){gps=location;updateMetrics();}
    @Override public void onProviderDisabled(String provider){gps=null;updateMetrics();}
    @Override public void onProviderEnabled(String provider){}
    @Override public void onStatusChanged(String provider,int status,Bundle extras){}
    private void export(String data,String name,String mime){approve("Export toestaan: "+name,Model.copy(config),()->{pendingExport=data;pendingExportType=mime;Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(mime).putExtra(Intent.EXTRA_TITLE,name);startActivityForResult(intent,41);});}
    @Override protected void onActivityResult(int request,int result,Intent intent){super.onActivityResult(request,result,intent);if(result!=RESULT_OK||intent==null||intent.getData()==null){if(request==41)pendingExport=null;return;}Uri uri=intent.getData();
        try{if(request==41&&pendingExport!=null){try(OutputStream out=getContentResolver().openOutputStream(uri,"wt")){if(out==null)throw new IOException("Bestand kan niet worden geopend.");out.write(pendingExport.getBytes(StandardCharsets.UTF_8));}pendingExport=null;toast("Bestand opgeslagen.");}
            if(request==42){JSONObject imported;try(InputStream in=getContentResolver().openInputStream(uri)){if(in==null)throw new IOException("Bestand ontbreekt.");ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1){out.write(b,0,n);if(out.size()>100000)throw new IOException("Profiel groter dan 100 kB.");}imported=new JSONObject(out.toString("UTF-8"));}checkProfile(imported);JSONObject p=imported;ui.post(()->{draft=Model.copy(p.optJSONObject("values"));showPage(2);toast("Gecontroleerd ontwerp geladen. Opslaan vraagt jouw toestemming.");});}
        }catch(Exception e){pendingExport=null;error(e);}
    }
    private void awake(){if(config.optBoolean("keep_awake",true))getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);}
    private void haptic(){if(config!=null&&config.optBoolean("haptics",true)&&root!=null)root.performHapticFeedback(HapticFeedbackConstants.CONFIRM);}
    private void message(String title,String message){new AlertDialog.Builder(this).setTitle(title).setMessage(message).setPositiveButton("Begrepen",null).show();}
    private void toast(String text){Toast.makeText(this,text,Toast.LENGTH_LONG).show();}
    private static String safeError(Exception e){String s=e.getMessage();return s==null?e.getClass().getSimpleName():s.length()>350?s.substring(0,350):s;}
    private void error(Exception e){message("Actie niet uitgevoerd",safeError(e));}
    @Override protected void onResume(){super.onResume();visible=true;ui.removeCallbacks(heartbeat);ui.post(heartbeat);}
    @Override protected void onStop(){super.onStop();visible=false;ui.removeCallbacks(heartbeat);if(authCancel!=null)authCancel.cancel();authBusy=false;generation++;linkEpoch++;recording=false;pendingUsb=null;if(locations!=null)locations.removeUpdates(this);gpsOn=false;gps=null;if(reader!=null||laptop!=null){disconnect();mode="offline";connectionNote="Gepauzeerd · opnieuw verbinden";}}
    @Override protected void onDestroy(){if(receiverRegistered)unregisterReceiver(usbReceiver);disconnect();worker.shutdown();super.onDestroy();}
    @Override public void onBackPressed(){if(page!=0){showPage(0);return;}if(samples.length()>0){message("Sessie nog niet bewaard","Ga naar Sessies en kies Opname stoppen & bewaren voordat je sluit.");return;}super.onBackPressed();}
}

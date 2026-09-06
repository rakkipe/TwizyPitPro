package be.peter.twizypitpro;

import android.content.Context;
import android.graphics.*;
import android.view.View;
import org.json.*;
import java.util.*;

final class TelemetryView extends View {
    private final Paint paint=new Paint(3);
    private final ArrayList<Double> values=new ArrayList<>();
    private final float density;
    TelemetryView(Context c){super(c);density=c.getResources().getDisplayMetrics().density;setContentDescription("Telemetriegrafiek: laatste 90 metingen");}
    void add(double value){values.add(value);if(values.size()>90)values.remove(0);invalidate();}
    void reset(){values.clear();invalidate();}
    @Override protected void onDraw(Canvas c){
        super.onDraw(c);float w=getWidth(),h=getHeight(),bottom=h-24*density;
        paint.setStrokeWidth(density);paint.setColor(Color.rgb(48,60,51));
        for(int i=0;i<4;i++)c.drawLine(0,12*density+(bottom-12*density)*i/3,w,12*density+(bottom-12*density)*i/3,paint);
        paint.setTextSize(10*density);paint.setTypeface(Typeface.create("sans-serif",Typeface.NORMAL));paint.setColor(Color.rgb(136,151,141));
        c.drawText("−90 s",0,h-3*density,paint);c.drawText("NU",w-20*density,h-3*density,paint);
        double max=10;for(double v:values)if(Double.isFinite(v))max=Math.max(max,v);
        if(values.size()<2)return;
        Path line=new Path();boolean pen=false;
        for(int i=0;i<values.size();i++){double v=values.get(i);if(!Double.isFinite(v)){pen=false;continue;}float x=w*i/(values.size()-1),y=(float)(bottom-8*density-(bottom-24*density)*v/(max*1.12));if(!pen)line.moveTo(x,y);else line.lineTo(x,y);pen=true;}
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(2.5f*density);paint.setColor(Color.rgb(210,250,105));paint.setStrokeJoin(Paint.Join.ROUND);c.drawPath(line,paint);paint.setStyle(Paint.Style.FILL);
    }
}

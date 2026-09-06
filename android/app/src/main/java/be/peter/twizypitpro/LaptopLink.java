package be.peter.twizypitpro;

import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

/** Local-network viewer. Never sends POST or a laptop command. */
final class LaptopLink {
    final String base,token;
    LaptopLink(String viewerUrl) throws Exception {
        URI uri=new URI(viewerUrl.trim());String host=uri.getHost();
        if(!"http".equals(uri.getScheme())||uri.getUserInfo()!=null||host==null||!host.matches("\\d{1,3}(\\.\\d{1,3}){3}"))throw new IOException("Gebruik de volledige lokale IPv4-viewerlink van de laptop.");
        InetAddress address=InetAddress.getByName(host);
        if(!(address.isSiteLocalAddress()||address.isLoopbackAddress()||address.isLinkLocalAddress()))throw new IOException("Alleen een lokaal netwerkadres is toegestaan.");
        String found="";for(String part:(uri.getRawQuery()==null?"":uri.getRawQuery()).split("&"))if(part.startsWith("viewer="))found=URLDecoder.decode(part.substring(7),"UTF-8");
        if(!found.matches("[A-Za-z0-9_-]{24,128}"))throw new IOException("De viewerlink mist een geldige sleutel.");
        token=found;base="http://"+host+":"+(uri.getPort()<0?8765:uri.getPort());
    }
    JSONObject state() throws Exception {
        HttpURLConnection connection=(HttpURLConnection)new URL(base+"/api/state").openConnection();
        connection.setConnectTimeout(3000);connection.setReadTimeout(3500);connection.setInstanceFollowRedirects(false);
        connection.setRequestProperty("X-Pit-Viewer",token);connection.setRequestProperty("Accept","application/json");
        try {
            if(connection.getResponseCode()!=200)throw new IOException("Laptop niet bereikbaar of viewersleutel verlopen.");
            ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[8192];
            try(InputStream in=connection.getInputStream()){int n;while((n=in.read(buffer))!=-1){out.write(buffer,0,n);if(out.size()>2000000)throw new IOException("Laptopantwoord te groot.");}}
            JSONObject state=new JSONObject(out.toString("UTF-8"));
            if(state.optJSONObject("sample")==null||state.optJSONObject("identity")==null||!state.optString("mode").matches("demo|live"))throw new IOException("Geen geldig Twizy Pit Pro-antwoord.");return state;
        }finally{connection.disconnect();}
    }
}

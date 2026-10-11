package android.content;

/** Host-JVM fixture: platform access must never silently succeed. */
public class Context {
    public android.content.res.AssetManager getAssets() {
        throw new UnsupportedOperationException("Android Context unavailable in JVM core tests");
    }
}

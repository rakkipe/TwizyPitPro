package android.os;

public class SystemClock {
    public static void sleep(long ms) {
        throw new UnsupportedOperationException("Android SystemClock unavailable in JVM core tests");
    }
}

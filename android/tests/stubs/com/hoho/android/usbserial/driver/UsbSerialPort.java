package com.hoho.android.usbserial.driver;

/** Compile-time signature; core tests use CanReader.Transport instead. */
public interface UsbSerialPort {
    void purgeHwBuffers(boolean purgeWriteBuffers, boolean purgeReadBuffers) throws java.io.IOException;
    void write(byte[] data, int timeout) throws java.io.IOException;
    int read(byte[] data, int timeout) throws java.io.IOException;
    void close() throws java.io.IOException;
}

import sys
import os
import struct
from cStringIO import StringIO

class WAVEError(Exception):
    pass

class WAVE(object):
    def __init__(self, file, count):
        self.file  = file
        self.count = count

        try:
            self.size = os.path.getsize(self.file)
        except OSError:
            raise WAVEError("Cannot read file metadata")

        self.riff_head = None
        self.riff_size = None
        self.wave_head = None

        self.fmt_size             = None
        self.codecid              = None
        self.channels             = None
        self.sample_rate          = None
        self.avg_bytes_per_second = None
        self.block_alignment      = None
        self.bps                  = None
        self.extra_fmt_length     = None
        self.extra_fmt            = None

        self.data_size = None
        self.data      = None

        try:
            with open(self.file, "rb") as f:
                self._rbuffer = StringIO(f.read())
        except (OSError, IOError):
            raise WAVEError("Cannot open file")

        self._wbuffer = StringIO()

    def __read(self, size):
        return self._rbuffer.read(size)

    def __write(self, data):
        self._wbuffer.write(data)

    def _read_uchar(self, size=None):
        if size is None:
            return struct.unpack("<B", self.__read(1))[0]
        else:
            return self.__read(size)

    def _read_uint16(self):
        return struct.unpack("<H", self.__read(2))[0]

    def _read_uint32(self):
        return struct.unpack("<I", self.__read(4))[0]

    def _write_uchar(self, data):
        if type(data) in (int, long):
            self.__write(struct.pack("<B", data))
        else:
            self.__write(data)

    def _write_uint16(self, data):
        self.__write(struct.pack("<H", data))

    def _write_uint32(self, data):
        self.__write(struct.pack("<I", data))

    def read(self):
        try:
            self.riff_head = self._read_uchar(4)

            if self.riff_head != "RIFF":
                raise WAVEError("No RIFF head found")

            self.riff_size = self._read_uint32()

            if self.riff_size != (self.size - 8):
                raise WAVEError("Truncated RIFF")

            self.wave_head = self._read_uchar(4)

            if self.wave_head != "WAVE":
                raise WAVEError("No WAVE head found")

            chunk_type = self._read_uchar(4)

            while chunk_type:
                if chunk_type == "fmt ":
                    if self.fmt_size is not None:
                        raise WAVEError("Repeated fmt chunk")

                    self.fmt_size = self._read_uint32()
                    self.codecid = self._read_uint16()

                    if self.codecid != 1:
                        raise WAVEError("Compressed WAVE is not supported")

                    self.channels = self._read_uint16()
                    self.sample_rate = self._read_uint32()
                    self.avg_bytes_per_second = self._read_uint32()
                    self.block_alignment = self._read_uint16()
                    self.bps = self._read_uint16()

                    if self.fmt_size > 0x10:
                        self.extra_fmt_length = self._read_uint16()

                        if self.extra_fmt_length > 0:
                            self.extra_fmt = self._read_uchar(self.extra_fmt_length)
                elif chunk_type == "data":
                    if self.data_size is not None:
                        raise WAVEError("Repeated data chunk")

                    self.data_size = self._read_uint32()
                    self.data = self._read_uchar(self.data_size)

                    if len(self.data) != self.data_size:
                        raise WAVEError("Bad data")
                else:
                    if len(chunk_type) != 4:
                        raise WAVEError("Truncated chunk header")

                    chunk_size = self._read_uint32()

                    self._rbuffer.seek(chunk_size, 1) # Skip to the next chunk.

                chunk_type = self._read_uchar(4)

            if self.fmt_size is None or self.data_size is None:
                WAVEError("Bad WAVE file")
        except struct.error:
            raise WAVEError("Bad WAVE file")
        finally:
            self._rbuffer.close()

    def write(self):
        self.riff_size = 0

        self._write_uchar(self.riff_head)
        self._write_uint32(self.riff_size)
        self._write_uchar(self.wave_head)

        self._write_uchar("fmt ")
        self._write_uint32(self.fmt_size)
        self._write_uint16(self.codecid)
        self._write_uint16(self.channels)
        self._write_uint32(self.sample_rate)
        self._write_uint32(self.avg_bytes_per_second)
        self._write_uint16(self.block_alignment)
        self._write_uint16(self.bps)

        if self.extra_fmt_length is not None:
            self._write_uint16(self.extra_fmt_length)

            if self.extra_fmt is not None:
                self._write_uchar(self.extra_fmt)

        self._write_uchar("cue ")
        self._write_uint32(0x0000001C) # cue chunk size
        self._write_uint32(1) # cue count
        self._write_uint32(1) # cue id 
        self._write_uint32(0) # cue position
        self._write_uchar("data") # chunk id
        self._write_uint32(0) # chunk start
        self._write_uint32(0) # block start
        self._write_uint32(0) # sample offset

        label = "preparedM\0"
        llen  = len(label)

        self._write_uchar("LIST")
        self._write_uint32(16 + llen) # list chunk size
        self._write_uchar("adtl") # list type
        self._write_uchar("labl") # list label
        self._write_uint32(4 + llen) # label chunk size
        self._write_uint32(1) # label id
        self._write_uchar(label) # label name

        self._write_uchar("data")
        self._write_uint32(self.data_size + (self.data_size * self.count))
        self._write_uchar(self.data)

        for i in xrange(self.count):
            self._write_uchar(self.data)

        self.riff_size = self._wbuffer.tell() - 8

        self._wbuffer.seek(4) # RIFF size parameter.
        self._write_uint32(self.riff_size)

        try:
            with open(self.file + ".cued", "wb") as f:
                f.write(self._wbuffer.getvalue())
        except (OSError, IOError):
            raise WAVEError("Couldn't flush merged file")
        finally:
            self._wbuffer.close()

def main(argc, argv):
    if argc not in (2, 3):
        print "Usage: %s <FILE> [COUNT]" % (os.path.basename(argv[0]))
        sys.exit(1)

    file = argv[1].strip()

    if not file:
        raise SyntaxError("Invalid file")

    try:
        count = max(int(argv[2]), 0)
    except IndexError:
        count = 0
    except ValueError:
        raise SyntaxError("Invalid repeat count")

    wavfile = WAVE(file, count)

    sys.stdout.write("[*] Reading WAVE...")
    wavfile.read()
    sys.stdout.write(" Done!\n")

    sys.stdout.write("[*] Writing WAVE...")
    wavfile.write()
    sys.stdout.write(" Done!\n")

    sys.exit(0)

if __name__ == "__main__":
    main(len(sys.argv), sys.argv)

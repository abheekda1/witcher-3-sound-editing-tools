import sys
import os
import struct

class CacheError(Exception):
    pass

class Cache(object):
    BIT_LENGTH_32 = 1
    BIT_LENGTH_64 = 2
 
    def __init__(self, file):
        try:
            self.file = open(file, "rb")
        except IOError, OSError:
            raise CacheError("Cannot read cache file")

        self.id = None
        self.bitlength = None
        self.unk_field32_1 = None # Possibly NOP
        self.unk_field32_2 = None # Possibly NOP
        self.info_offset = None
        self.info = None
        self.info_found = 0
        self.names_offset = None
        self.names_size = None
        self.names = None
        self.null_bytes_in_names = None
        self.names_found = 0
        self.files = None
        self.unk_field32_3 = None # Only used in BIT_LENGTH_64
        self.bufsize = None
        self.checksum = None
        self.data_offset = None
        self.data = None

    def __del__(self):
        try:
            self.file.close()
        except Exception:
            pass

    def _read_uchar(self, size=None):
        if size is None:
            return struct.unpack("<B", self.file.read(1))[0]
        else:
            if size > 0x7FFFFFFF:
                data = ""
                dv = divmod(size, 0x7FFFFFFF)
                count = dv[0]

                for i in xrange(count):
                    data += self.file.read(0x7FFFFFFF)

                if dv[1] > 0:
                    data += self.file.read(dv[1])

                return data
            else:
                return self.file.read(size)

    def _read_uint16(self):
        return struct.unpack("<H", self.file.read(2))[0]

    def _read_uint32(self):
        return struct.unpack("<I", self.file.read(4))[0]

    def _read_uint64(self):
        return struct.unpack("<Q", self.file.read(8))[0]

    def read(self):
        self.id = self._read_uchar(4)
        self.bitlength = self._read_uint32()
        self.unk_field32_1 = self._read_uint32()
        self.unk_field32_2 = self._read_uint32()

        if self.bitlength == Cache.BIT_LENGTH_32:
            self.info_offset = self._read_uint32()
            self.files = self._read_uint32()
            self.names_offset = self._read_uint32()
        elif self.bitlength == Cache.BIT_LENGTH_64:
            self.info_offset = self._read_uint64()
            self.files = self._read_uint64()
            self.names_offset = self._read_uint64()

        self.names_size = self._read_uint32()

        if self.bitlength == Cache.BIT_LENGTH_64: # This field only appears in the 64 bits version.
            self.unk_field32_3 = self._read_uint32()

        self.bufsize = self._read_uint64()
        self.checksum = self._read_uint64()
        self.data_offset = self.file.tell()
        self.data = self._read_uchar(self.names_offset - self.data_offset)
        self.names = self._read_uchar(self.names_size)
        self.info = self.file.read()

        self.null_bytes_in_names = self.names.count("\0")
        self.names_found = len(self.names.split("\0")) - 1

        if self.bitlength == Cache.BIT_LENGTH_32:
            self.info_found = divmod(len(self.info), 12)
        elif self.bitlength == Cache.BIT_LENGTH_64:
            self.info_found = divmod(len(self.info), 24)

    def display(self):
        print "ID: " + self.id
        print "BIT LENGTH: %i" % (32 if self.bitlength == Cache.BIT_LENGTH_32 else 64)
        print "UNK FIELD32 1: 0x%X" % (self.unk_field32_1)
        print "UNK FIELD32 2: 0x%X" % (self.unk_field32_2)
        print "INFO OFFSET: %i" % (self.info_offset)
        print "FILES: %i" % (self.files)
        print "NAMES OFFSET: %i" % (self.names_offset)
        print "NAMES SIZE: %i" % (self.names_size)

        if self.unk_field32_3 is not None:
            print "UNK FIELD32 3 (POSSIBLY BUFFER COUNT): %i" % (self.unk_field32_3)

        print "BUFFER SIZE: %i" % (self.bufsize)
        print "CHECKSUM: 0x%X" % (self.checksum)
        print "DATA OFFSET: %i" % (self.data_offset)
        print "DATA SIZE: %i" % (len(self.data))
        print "INFO SIZE: %i" % (len(self.info))
        print "NULL BYTES IN NAMES: %i" % (self.null_bytes_in_names)
        print "NAMES FOUND: %i" % (self.names_found)
        print("INFOS FOUND: BROKEN" if self.info_found[1] != 0 else "INFO FOUND: %i" % (self.info_found[0]))

def main(argc, argv):
    if argc != 2:
        print "Usage: %s <INPUT>" % (os.path.basename(argv[0]))
        sys.exit(1)

    input = argv[1].strip()

    if not input:
        raise SyntaxError("Invalid input")

    sys.stdout.write("Decoding sounds cache...")
    soundscache = Cache(input)
    soundscache.read()
    sys.stdout.write("Done!\n")

    print
    soundscache.display()
    print

    del soundscache

    sys.exit(0)

if __name__ == "__main__":
    main(len(sys.argv), sys.argv)
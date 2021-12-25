import sys
import os
import struct
from cStringIO import StringIO
from hashlib import sha1

class FileError(Exception):
    pass

class CacheError(Exception):
    pass

class FNV1a64(object):
    """ Adapted from: https://pypi.python.org/pypi/fnvhash """

    FNV_64_PRIME = 0x100000001b3
    FNV1_64_INIT = 0xcbf29ce484222325

    def __init__(self, data):
        assert isinstance(data, bytes)

        self.hval = FNV1a64.FNV1_64_INIT

        for byte in data:
            self.hval = self.hval ^ ord(byte)
            self.hval = (self.hval * FNV1a64.FNV_64_PRIME) % 0x10000000000000000

    def __int__(self):
        return self.hval

    def __long__(self):
        return self.hval

    def __str__(self):
        return "0x%X" % (self.hval)

class FileRead(object):
    def __init__(self, file):
        self.path = file

        try:
            self.file = open(self.path, "rb")
        except (IOError, OSError):
            raise FileError("Can't open %s" % (self.path))

        self.name = os.path.basename(file)
        self.size = os.path.getsize(file)

    def __del__(self):
        try:
            self.file.close()
        except Exception:
            pass

    def read_uchar(self, size=None):
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

    def read_uint16(self):
        return struct.unpack("<H", self.file.read(2))[0]

    def read_uint32(self):
        return struct.unpack("<I", self.file.read(4))[0]

    def read_data(self):
        try:
            return self.file.read()
        except IOError:
            raise FileError("Failed to read data from %s" % (self.path))

class Data(object):
    def __init__(self, parent, data):
        self.parent = parent
        self.data = data
        self.hash = sha1(data).digest()
        self.offset = None

    def __len__(self):
        return len(self.data)

    def __getitem__(self, key):
        if not isinstance(key, FileRead):
            raise FileError("%s is not a File object" % repr(key))

        return (True if key is self.parent else False)

class Cache(object):
    BIT_LENGTH_32 = 1
    BIT_LENGTH_64 = 2
    CACHE_BUFFER_SIZE = 4096

    def __init__(self, folder):
        try:
            self.file = open("soundspc.cache", "wb")
        except IOError:
            raise CacheError("Couldn't create cache")

        self.folder = folder
        self.id = "CS3W"
        self.bitlength = Cache.BIT_LENGTH_32
        self.unk_field32_1 = 0x00000000 # Possibly NOP
        self.unk_field32_2 = 0x00000000 # Possibly NOP
        self.unk_field32_3 = 1 # Only used for 64-bits.
        self.bufsize = None
        self.checksum = None
        self.data = None
        self.data_offset = 0x30
        self.names = None
        self.info = None
        self.buffer = StringIO()
        self.to_cache = None

    def __del__(self):
        try:
            self.file.close()
        except Exception:
            pass

        try:
            self.buffer.close()
        except Exception:
            pass

        try:
            del self.to_cache[:]
        except Exception:
            pass

    def _write_uchar(self, data, output=None):
        if output is None:
            output = self.file

        if type(data) == int or type(data) == long:
            output.write(struct.pack("<B", data))
        else:
            if len(data) > 0x7FFFFFFF:
                dv = divmod(len(data), 0x7FFFFFFF)
                count = dv[0]

                for i in xrange(count):
                    output.write(data[0:0x7FFFFFFF])
                    data = data[0x7FFFFFFF:]

                if dv[1] > 0:
                    output.write(data[:dv[1]])
            else:
                output.write(data)

    def _write_uint16(self, data, output=None):
        if output is None:
            output = self.file

        output.write(struct.pack("<H", data))

    def _write_uint32(self, data, output=None):
        if output is None:
            output = self.file

        output.write(struct.pack("<I", data))

    def _write_uint64(self, data, output=None):
        if output is None:
            output = self.file

        output.write(struct.pack("<Q", data))

    def get_files_to_cache(self):
        temp = []

        for file in os.listdir(self.folder):
            file = self.folder + os.sep + file

            if not os.path.isfile(file) or (not file.endswith(".wem") and not file.endswith(".bnk")):
                raise FileError("%s is not a valid file" % (file))

            file = FileRead(file)
            temp.append(file)

        if not temp:
            raise CacheError("No files to cache")

        bnks = [file for file in temp if file.name.endswith(".bnk")]
        wems = [file for file in temp if file.name.endswith(".wem")]

        bnks.sort(key=lambda bnk: bnk.name.lower())
        wems.sort(key=lambda wem: wem.name.lower())

        self.to_cache = bnks + wems

    def get_total_data_size(self):
        return sum(len(data) for data in self.data if data.offset is not None)

    def _build_names(self):
        self.names = "\0".join(file.name for file in self.to_cache)
        self.names += "\0"

    def _build_info(self):
        buf = StringIO()
        noffset = 0
        offset = self.data_offset

        if self.bitlength == Cache.BIT_LENGTH_32:
            write_info_field = self._write_uint32
        elif self.bitlength == Cache.BIT_LENGTH_64:
            write_info_field = self._write_uint64

        for (i, file) in enumerate(self.to_cache):
            repeated = False
            write_info_field(noffset, buf)
            data = self.data[i]

            if not data[file]:
                raise FileError("Mismatched file and data")

            for _data in self.data:
                if data is not _data:
                    if _data.offset is not None and len(data) == len(_data) and data.hash == _data.hash:
                        data.offset = None
                        repeated = True
                        roffset = _data.offset
                        break

            if repeated:
                write_info_field(roffset, buf)
            else:
                data.offset = offset
                write_info_field(data.offset, buf)
                offset += len(data)

            write_info_field(len(data), buf)

            noffset += len(file.name) + 1

        self.info = buf.getvalue()
        buf.close()

    def _build_data(self):
        self.data = [Data(file, file.read_data()) for file in self.to_cache]

    def _calculate_checksum(self):
        self.checksum = FNV1a64(self.names + self.info)

    def generate_cache(self):
        self._build_data()
        self._build_info()
        self._build_names()

        if self.data_offset + self.get_total_data_size() + len(self.names) + len(self.info) > 0xFFFFFFFF: # Switch to 64-bits mode.
            self.bitlength = Cache.BIT_LENGTH_64
            self.data_offset += 0x10

            for data in self.data:
                data.offset = None

            self._build_info()

        self._calculate_checksum()

        self.bufsize = max(file.size for file in self.to_cache)

        if self.bufsize <= Cache.CACHE_BUFFER_SIZE:
            self.bufsize = Cache.CACHE_BUFFER_SIZE
        else:
            fremainder = self.bufsize % Cache.CACHE_BUFFER_SIZE
            self.bufsize += (Cache.CACHE_BUFFER_SIZE - fremainder)

        self._write_uchar(self.id)
        self._write_uint32(self.bitlength)
        self._write_uint32(self.unk_field32_1)
        self._write_uint32(self.unk_field32_2)

        if self.bitlength == Cache.BIT_LENGTH_32:
            self._write_uint32(self.data_offset + self.get_total_data_size() + len(self.names))
            self._write_uint32(len(self.to_cache))
            self._write_uint32(self.data_offset + self.get_total_data_size())
        elif self.bitlength == Cache.BIT_LENGTH_64:
            self._write_uint64(self.data_offset + self.get_total_data_size() + len(self.names))
            self._write_uint64(len(self.to_cache))
            self._write_uint64(self.data_offset + self.get_total_data_size())

        self._write_uint32(len(self.names))

        if self.bitlength == Cache.BIT_LENGTH_64: # This field only appears in the 64 bits version.
            self._write_uint32(self.unk_field32_3)

        self._write_uint64(self.bufsize)
        self._write_uint64(long(self.checksum))

        for data in self.data:
            print "[PACKING] %s" % (data.parent.name)

            if data.offset is not None:
                self._write_uchar(data.data)

        self._write_uchar(self.names)
        self._write_uchar(self.info)

def main(argc, argv):
    if argc != 2:
        print "Usage: %s <FOLDER>" % (os.path.basename(argv[0]))
        sys.exit(1)

    folder = argv[1].strip()

    if not folder:
        raise SyntaxError("Invalid folder")

    print "Creating sounds cache..."
    print

    soundscache = Cache(folder)
    soundscache.get_files_to_cache()
    soundscache.generate_cache()

    del soundscache

    print
    print "Finished!"

    sys.exit(0)

if __name__ == "__main__":
    main(len(sys.argv), sys.argv)

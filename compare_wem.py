import sys
import os
import struct
from cStringIO import StringIO

class WEMError(Exception):
    pass

class WEMTypes(object):
    SEEK_BEGIN = 0
    SEEK_CURRENT = 1
    SEEK_END = 2

def yes_or_no(message):
    while True:
        answer = raw_input("%s? [Y]es/[N]o: " % (message)).strip().lower()

        if answer in ("yes", "ye", "y"):
            return True
        elif answer in ("no", "n"):
            return False

class Table(object):
    def __init__(self, headers, content):
        self.headers = headers
        self.content = content

    def show(self):
        # Get table sizes.
        tabsizes = tuple(max(len(_header), max(len(elements[i]) for elements in iter(self.content)))
                         for (i, _header) in enumerate(self.headers))

        # Make table header.
        header = " ".join(_header.ljust(tabsizes[i]) for (i, _header) in enumerate(self.headers))
        head = tail = ("-" * len(header))

        # Make table elements.
        table = "\n".join(" ".join(element.ljust(tabsizes[i]) for (i, element) in enumerate(elements))
                          for elements in iter(self.content))

        # Print crafted table.
        print "\n".join((head, header, table, tail))

class Packet(object):
    def __init__(self, wem, offset, no_granule):
        self.offset = offset
        self.absolute_granule = 0
        self.no_granule = no_granule
        self.size = wem._read_uint16()

        if not self.no_granule:
            self.absolute_granule = wem._read_uint32()

    def __len__(self):
        return self.size

    def get_header_size(self):
        return 2 if self.no_granule else 6

    def get_offset(self):
        return self.offset + self.get_header_size()

    def get_next_offset(self):
        return self.get_offset() + self.size

class WEM(object):
    def __init__(self, file):
        try:
            self.fsize = os.path.getsize(file)
            self.file = open(file, "rb")
        except (OSError, IOError):
            raise WEMError("Cannot open file")

        self._file = file
        self.buffer = StringIO()
        self.riff_head = None
        self.riff_size = None
        self.wave_head = None
        self.fmt_offset = None
        self.fmt_size = None
        self.cue_offset = None
        self.cue_size = None
        self.LIST_offset = None
        self.LIST_size = None
        self.smpl_offset = None
        self.smpl_size = None
        self.vorb_offset = None
        self.vorb_size = None
        self.data_offset = None
        self.data_size = None
        self.codecid = None
        self.channels = 0
        self.sample_rate = 0
        self.avg_bytes_per_second = 0
        self.block_alignment = None
        self.bps = None
        self.extra_fmt_length = None
        self.ext_unk = 0
        self.subtype = 0
        self.sample_count = 0
        self.no_granule = False
        self.mod_signal = None
        self.mod_packets = False
        self.fmt_unk_field32_1 = None
        self.fmt_unk_field32_2 = None
        self.setup_packet_offset = 0
        self.first_audio_packet_offset = 0
        self.fmt_unk_field32_3 = None
        self.fmt_unk_field32_4 = None
        self.fmt_unk_field32_5 = None
        self.header_triad_present = False
        self.old_packet_headers = False
        self.uid = 0
        self.blocksize_0_pow = 0
        self.blocksize_1_pow = 0
        self.cue_count = 0
        self.cue_id = None
        self.cue_position = None
        self.cue_datachunkid = None
        self.cue_chunkstart = None
        self.cue_blockstart = None
        self.cue_sampleoffset = None
        self.adtlbuf = None
        self.LIST_remain = None
        self.loop_count = 0
        self.loop_start = 0
        self.loop_end = 0
        self.fake_vorb = False
        self.pre_data = None
        self.data_setup = None
        self.data = None

    def __del__(self):
        try:
            self.file.close()
        except Exception:
            pass

        try:
            self.buffer.close()
        except Exception:
            pass

    def _read_uchar(self, size=None):
        if size is None:
            return struct.unpack("<B", self.file.read(1))[0]
        else:
            return self.file.read(size)

    def _read_uint16(self):
        return struct.unpack("<H", self.file.read(2))[0]

    def _read_uint32(self):
        return struct.unpack("<I", self.file.read(4))[0]

    def _write_uchar(self, data):
        if type(data) == int or type(data) == long:
            self.buffer.write(struct.pack("<B", data))
        else:
            self.buffer.write(data)

    def _write_uint16(self, data):
        self.buffer.write(struct.pack("<H", data))

    def _write_uint32(self, data):
        self.buffer.write(struct.pack("<I", data))

    def read(self):
        try:
            self.riff_head = self._read_uchar(4)

            if self.riff_head != "RIFF":
                raise WEMError("No RIFF head found")

            self.riff_size = self._read_uint32() + 8

            if self.riff_size > self.fsize:
                raise WEMError("Truncated RIFF")

            self.wave_head = self._read_uchar(4)

            if self.wave_head != "WAVE":
                raise WEMError("No WAVE head found")

            chunk_offset = 12

            while chunk_offset < self.riff_size:
                self.file.seek(chunk_offset, WEMTypes.SEEK_BEGIN)

                if chunk_offset + 8 > self.riff_size:
                    raise WEMError("Truncated chunk header")

                chunk_type = self._read_uchar(4)
                chunk_size = self._read_uint32()

                if chunk_type == "fmt ":
                    self.fmt_offset = chunk_offset + 8
                    self.fmt_size = chunk_size
                elif chunk_type == "cue ":
                    self.cue_offset = chunk_offset + 8
                    self.cue_size = chunk_size
                elif chunk_type == "LIST":
                    self.LIST_offset = chunk_offset + 8
                    self.LIST_size = chunk_size
                elif chunk_type == "smpl":
                    self.smpl_offset = chunk_offset + 8
                    self.smpl_size = chunk_size
                elif chunk_type == "vorb":
                    self.vorb_offset = chunk_offset + 8
                    self.vorb_size = chunk_size
                elif chunk_type == "data":
                    self.data_offset = chunk_offset + 8
                    self.data_size = chunk_size

                chunk_offset += (8 + chunk_size)

            if chunk_offset > self.riff_size:
                    raise WEMError("Truncated chunk")

            if self.fmt_offset is None and self.data_offset is None:
                raise WEMError("No fmt and data chunks found")

            if self.vorb_size not in (None, 0x28, 0x2A, 0x2C, 0x32, 0x34):
                raise WEMError("Bad vorb size")

            if self.vorb_offset is None:
                if self.fmt_size != 0x42:
                    raise WEMError("fmt size must be 0x42 if no vorb")
                else:
                    self.vorb_offset = self.fmt_offset + 0x18 # Fake
                    self.fake_vorb = True
            else:
                raise WEMError("Not Supported")

                if self.fmt_size not in (0x28, 0x18, 0x12):
                    raise WEMError("Bad fmt size")

            self.file.seek(self.fmt_offset, WEMTypes.SEEK_BEGIN)

            self.codecid = self._read_uint16()

            if self.codecid != 0xFFFF:
                raise WEMError("Bad codec id")

            self.channels = self._read_uint16()
            self.sample_rate = self._read_uint32()
            self.avg_bytes_per_second = self._read_uint32()
            self.block_alignment = self._read_uint16()

            if self.block_alignment != 0:
                raise WEMError("Bad block alignment")

            self.bps = self._read_uint16()

            if self.bps != 0:
                raise WEMError("BPS is not 0")

            self.extra_fmt_length = self._read_uint16()

            if self.extra_fmt_length != (self.fmt_size - 0x12):
                raise WEMError("Bad extra fmt length")

            if (self.fmt_size - 0x12) >= 2:
                self.ext_unk = self._read_uint16()

                if (self.fmt_size - 0x12) >= 6:
                    self.subtype = self._read_uint32()

            if self.cue_offset is not None:
                #if self.cue_size != 0x1c:
                    #raise WEMError("Bad cue size")

                self.file.seek(self.cue_offset, WEMTypes.SEEK_BEGIN)
                self.cue_count = self._read_uint32()
                self.cue_id = self._read_uint32()
                self.cue_position = self._read_uint32()
                self.cue_datachunkid = self._read_uint32()
                self.cue_chunkstart = self._read_uint32()
                self.cue_blockstart = self._read_uint32()
                self.cue_sampleoffset = self._read_uint32()

            if self.LIST_offset is not None:
                self.file.seek(self.LIST_offset, WEMTypes.SEEK_BEGIN)
                self.adtlbuf = self._read_uchar(4)

                if self.adtlbuf != "adtl":
                    raise WEMError("LIST is not adtl")

                self.LIST_remain = self._read_uchar(self.LIST_size - 4)

            if self.smpl_offset is not None:
                self.file.seek(self.smpl_offset + 0x1C, WEMTypes.SEEK_BEGIN)
                self.loop_count = self._read_uint32()

                if self.loop_count != 1:
                    raise WEMError("Not an one loop")

                self.file.seek(self.smpl_offset + 0x2c, WEMTypes.SEEK_BEGIN)
                self.loop_start = self._read_uint32()
                self.loop_end = self._read_uint32()

            self.file.seek(self.vorb_offset, WEMTypes.SEEK_BEGIN)
            self.sample_count = self._read_uint32()

            if self.vorb_size in (None, 0x2A):
                self.no_granule = True
                self.file.seek(self.vorb_offset + 0x4, WEMTypes.SEEK_BEGIN)
                self.mod_signal = self._read_uint32()

                if self.mod_signal not in (0x4A, 0x4B, 0x69, 0x70):
                    self.mod_packets = True

                self.fmt_unk_field32_1 = self._read_uint32()
                self.fmt_unk_field32_2 = self._read_uint32()

                self.file.seek(self.vorb_offset + 0x10, WEMTypes.SEEK_BEGIN)
            else:
                self.file.seek(self.vorb_offset + 0x18, WEMTypes.SEEK_BEGIN)

            self.setup_packet_offset = self._read_uint32()
            self.first_audio_packet_offset = self._read_uint32()
            self.fmt_unk_field32_3 = self._read_uint32()
            self.fmt_unk_field32_4 = self._read_uint32()
            self.fmt_unk_field32_5 = self._read_uint32()

            if self.vorb_size in (None, 0x2A):
                self.file.seek(self.vorb_offset + 0x24, WEMTypes.SEEK_BEGIN)
            elif self.vorb_size in (0x32, 0x34):
                self.file.seek(self.vorb_offset + 0x2C, WEMTypes.SEEK_BEGIN)

            if self.vorb_size in (0x28, 0x2C):
                self.header_triad_present = True
                self.old_packet_headers = True
            elif self.vorb_size in (None, 0x2A, 0x32, 0x34):
                self.uid = self._read_uint32()
                self.blocksize_0_pow = self._read_uchar()
                self.blocksize_1_pow = self._read_uchar()

            if self.loop_count != 0:
                if self.loop_end == 0:
                    self.loop_end = self.sample_count
                else:
                    self.loop_end += 1

                if self.loop_start >= self.sample_count or self.loop_end > self.sample_count or self.loop_start > self.loop_end:
                    raise WMError("Loops out of range")

            if self.subtype in (4, 3, 0x33, 0x37, 0x3b, 0x3f):
                pass

            self.setup_packet()

            self.file.seek(self.data_offset, WEMTypes.SEEK_BEGIN)
            self.pre_data = self._read_uchar(self.setup_packet_offset)
            self.data_setup = self._read_uchar(self.first_audio_packet_offset)
            self.data = self.file.read()

            if len(self.pre_data) + len(self.data_setup) + len(self.data) != self.data_size:
                raise WEMError("Bad data")
                    
        except (IOError, struct.error):
            raise WMError("Bad WEM file")

    def setup_packet(self):
        self.packet = Packet(self, self.data_offset + self.setup_packet_offset, self.no_granule)

        if self.packet.absolute_granule != 0:
            raise WEMError("Setup packet granule is not 0")

    def merge_headers(self, ww):
        if not self.fake_vorb:
            raise WEMError("Not supported")

        self.riff_size = 0
        #self.LIST_size = ww.LIST_size
        #self.adtlbuf = ww.adtlbuf
        #self.LIST_remain = ww.LIST_remain
        #self.unk_field32_1 = ww.unk_field32_1
        #self.unk_field32_2 = ww.unk_field32_2
        #self.unk_field32_3 = ww.unk_field32_3
        #self.unk_field32_4 = ww.unk_field32_4
        #self.unk_field32_5 = ww.unk_field32_5
        #self.uid = ww.uid
        self.subtype = ww.subtype
        #self.mod_signal = ww.mod_signal
        #self.setup_packet_offset = ww.setup_packet_offset
        #self.first_audio_packet_offset = ww.first_audio_packet_offset
        #self.pre_data = ww.pre_data
        #self.data_setup = ww.data_setup

        self.file.close()

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
        self._write_uint16(self.extra_fmt_length)
        self._write_uint16(self.ext_unk)
        self._write_uint32(self.subtype)
        self._write_uint32(self.sample_count)
        self._write_uint32(self.mod_signal)
        self._write_uint32(self.fmt_unk_field32_1)
        self._write_uint32(self.fmt_unk_field32_2)
        self._write_uint32(len(self.pre_data))
        self._write_uint32(len(self.pre_data) + (self.first_audio_packet_offset - self.setup_packet_offset))
        self._write_uint32(self.fmt_unk_field32_3)
        self._write_uint32(self.fmt_unk_field32_4)
        self._write_uint32(self.fmt_unk_field32_5)
        self._write_uint32(self.uid)
        self._write_uchar(self.blocksize_0_pow)
        self._write_uchar(self.blocksize_1_pow)

        if self.cue_offset is not None:
            self._write_uchar("cue ")
            self._write_uint32(self.cue_size)
            self._write_uint32(self.cue_count)
            self._write_uint32(self.cue_id)
            self._write_uint32(self.cue_position)
            self._write_uint32(self.cue_datachunkid)
            self._write_uint32(self.cue_chunkstart)
            self._write_uint32(self.cue_blockstart)
            self._write_uint32(self.cue_sampleoffset)

        #self._write_uchar("LIST")
        #self._write_uint32(self.LIST_size)
        #self._write_uchar(self.adtlbuf)
        #self._write_uchar(self.LIST_remain)

    def merge_datas(self, ww):
        databuf = StringIO()
        databuf.write(self.pre_data)
        databuf.write(self.data_setup)
        databuf.write(self.data)

        self.data_size = databuf.tell()

        self._write_uchar("data")
        self._write_uint32(self.data_size)
        self._write_uchar(databuf.getvalue())

        databuf.close()

    def calculate_riff_size(self):
        fsize = self.buffer.tell()
        self.buffer.seek(4, WEMTypes.SEEK_BEGIN)
        self._write_uint32(fsize - 8)
        self.buffer.seek(0, WEMTypes.SEEK_END)

    def get_elements_for_table(self):
        return (
                "RIFF SIZE: %i" % (self.riff_size),
                "CUE: " + ("No" if self.cue_offset is None else "Yes"),
                "LIST: " + ("No" if self.LIST_offset is None else "Yes"),
                "SMP1: " + ("No" if self.smpl_offset is None else "Yes"),
                "VORB: " + ("No" if self.vorb_offset is None or self.fake_vorb else "Yes"),
                "LIST SIZE: %i" % (self.LIST_size) if self.LIST_offset is not None else "",
                "FMT SIZE: %i" % (self.fmt_size),
                "DATA SIZE: %i" % (self.data_size),
                "CODEC ID: %i" % (self.codecid),
                "CHANNELS: %i" % (self.channels),
                "SAMPLE RATE: %i" % (self.sample_rate),
                "AVG BYTES PER SECOND: %i" % (self.avg_bytes_per_second),
                "BPS: %i" % (self.bps),
                "EXTRA FMT LENGTH: %i" % (self.extra_fmt_length),
                "EXT UNKNOWN: %i" % (self.ext_unk),
                "SUBTYPE: %i" % (self.subtype),
                "SAMPLE COUNT: %i" % (self.sample_count),
                "NO GRANULE: " + ("Yes" if self.no_granule else "No"),
                "MOD SIGNAL: %i" % (self.mod_signal),
                "MOD PACKETS: " + ("Yes" if self.mod_packets else "No"),
                "SETUP PACKET OFFSET: %i" % (self.setup_packet_offset),
                "FIRST AUDIO PACKET OFFSET: %i" % (self.first_audio_packet_offset),
                "HEADER TRIAD PRESENT: " + ("Yes" if self.header_triad_present else "No"),
                "OLD PACKET HEADERS: " + ("Yes" if self.old_packet_headers else "No"),
                "UID: %i" % (self.uid),
                "BLOCKSIZE 0: %i" % (self.blocksize_0_pow),
                "BLOCKSIZE 1: %i" % (self.blocksize_1_pow),
                "UNK FMT FIELDS 32: %i, %i, %i, %i, %i" % (self.fmt_unk_field32_1, self.fmt_unk_field32_2, self.fmt_unk_field32_3, self.fmt_unk_field32_4, self.fmt_unk_field32_5),
                "CUE COUNT: %i" % (self.cue_count),
                "CUE SIZE: %i" % (self.cue_size) if self.cue_offset is not None else "",
                "CUE ID: %i" % (self.cue_id) if self.cue_offset is not None else "",
                "CUE POSITION: %i" % (self.cue_position) if self.cue_offset is not None else "",
                "CUE DATACHUNKID: %i" % (self.cue_datachunkid) if self.cue_offset is not None else "",
                "CUE CHUNKSTART: %i" % (self.cue_chunkstart) if self.cue_offset is not None else "",
                "CUE BLOCKSTART: %i" % (self.cue_blockstart) if self.cue_offset is not None else "",
                "CUE SAMPLEOFFSET: %i" % (self.cue_sampleoffset) if self.cue_offset is not None else "",
                "LOOP COUNT: %i" % (self.loop_count)
               )

    def create(self):
        try:
            self.file = open(self._file + ".merged", "wb")
            self.file.write(self.buffer.getvalue())
        except IOError:
            raise WEMError("Couldn't flush merged file")

def main(argc, argv):
    if argc != 3:
        print "Usage: %s <INPUT> <OUTPUT>" % (os.path.basename(argv[0]))
        sys.exit(1)

    input = argv[1].strip()

    if not input:
        raise SyntaxError("Invalid input")

    output = argv[2].strip()

    if not output:
        raise SyntaxError("Invalid output")

    sys.stdout.write("Analyzing...")

    wwinput = WEM(input)
    wwinput.read()

    wwoutput = WEM(output)
    wwoutput.read()

    sys.stdout.write("Done!\n")

    tabheaders = ("INPUT", "OUTPUT")
    tabcontent1 = wwinput.get_elements_for_table()
    tabcontent2 = wwoutput.get_elements_for_table()

    tabcontent = [(tabcontent1[i], tabcontent2[i]) for (i, element) in enumerate(tabcontent1)]

    table = Table(tabheaders, tabcontent)

    print
    table.show()

    print
    answer = yes_or_no("Merge headers")

    if answer:
        wwoutput.merge_headers(wwinput)
        wwoutput.merge_datas(wwinput)
        wwoutput.calculate_riff_size()
        wwoutput.create()

    del wwinput
    del wwoutput

    sys.exit(0)

if __name__ == "__main__":
    main(len(sys.argv), sys.argv)
import sys
import os
import struct
from cStringIO import StringIO
from copy import deepcopy
from binascii import hexlify
from hashlib import sha1
from ConfigParser import SafeConfigParser
import compare_wem

class SoundbankError(Exception):
    pass

class SBHeaderError(SoundbankError):
    pass

class SBDataIndexError(SoundbankError):
    pass

class SBDataError(SoundbankError):
    pass

class SBObjectsError(SoundbankError):
    pass

class SBObjectError(SBObjectsError):
    pass

class SBSoundTypeIDError(SoundbankError):
    pass

class SBManagerError(SoundbankError):
    pass

class SBEnvironmentsError(SoundbankError):
    pass

class SoundbankChunk(object):
    pass

class Random(object):
    seed = os.urandom

    @classmethod
    def int8(cls):
        return struct.unpack("<b", cls.seed(1))[0]

    @classmethod
    def uint8(cls):
        return struct.unpack("<B", cls.seed(1))[0]

    @classmethod
    def int16(cls, positive=False):
        if not positive:
            return struct.unpack("<h", cls.seed(2))[0]
        else:
            r = cls.seed(1)
            c = 0xFF

            while c > 0x7F:
                c = Random.uint8()

            r += struct.pack("<B", c)

            return struct.unpack("<h", r)[0]

    @classmethod
    def uint16(cls):
        return struct.unpack("<H", cls.seed(2))[0]

    @classmethod
    def int32(cls, positive=False):
        if not positive:
            return struct.unpack("<i", cls.seed(4))[0]
        else:
            r = cls.seed(3)
            c = 0xFF

            while c > 0x7F:
                c = Random.uint8()

            r += struct.pack("<B", c)

            return struct.unpack("<i", r)[0]

    @classmethod
    def uint32(cls):
        return struct.unpack("<I", cls.seed(4))[0]

    @classmethod
    def float(cls):
        return struct.unpack("<f", cls.seed(4))[0]

    @classmethod
    def int64(cls, positive=False):
        if not positive:
            return struct.unpack("<q", cls.seed(8))[0]
        else:
            r = cls.seed(7)
            c = 0xFF

            while c > 0x7F:
                c = Random.uint8()

            r += struct.pack("<B", c)

            return struct.unpack("<q", r)[0]

    @classmethod
    def uint64(cls):
        return struct.unpack("<Q", cls.seed(8))[0]

    @classmethod
    def double(cls):
        return struct.unpack("<d", cls.seed(8))[0]

class SBHeader(SoundbankChunk):
    HEAD = "BKHD"
    #LENGTH = (0x10, 0x14, 0x18, 0x1C)
    VERSION = 0x58

    def __init__(self, data=None):
        if data is not None:
            self.head = data.read_header()

            if self.head != SBHeader.HEAD:
                raise SBHeaderError("Invalid head")

            self.length = data.read_uint32()
            curPos = data.where()

            #if self.length not in SBHeader.LENGTH:
                #raise SBHeaderError("Invalid length")

            self.version = data.read_uint32()

            if self.version != SBHeader.VERSION:
                raise SBHeaderError("Invalid version")

            self.id = data.read_uint32()
            self.unk_field32_1 = data.read_uint32()
            self.unk_field32_2 = data.read_uint32()

            remaining = self.length - (data.where() - curPos)

            if remaining > 0:
                self.unk_data = data.read_uchar(remaining)
            else:
                self.unk_data = None
            
        else:
            self.head = SBHeader.HEAD
            self.length = None
            self.version = SBHeader.VERSION
            self.id = None
            self.unk_field32_1 = 0
            self.unk_field32_2 = 0
            self.unk_data = None

class SBDataIndex(SoundbankChunk):
    HEAD = "DIDX"

    def __init__(self, data=None):
        if data is not None:
            self.head = data.read_header()

            if self.head != SBDataIndex.HEAD:
                self.head = None
                data.goto(-4, 1)
                return

            self.length = data.read_uint32()

            if (self.length % 12) != 0:
                raise SBDataIndexError("Invalid length")

            self.data_info = [WEM(data) for i in xrange(0, self.length, 12)]
        else:
            self.head = SBDataIndex.HEAD
            self.length = None
            self.data_info = []

    def __nonzero__(self):
        return self.head is not None

    def get_total_size(self):
        return sum(data.size for data in self.data_info)

    def get_offset(self, id):
        for data in self.data_info:
            if data.id == id:
                return data.offset

    def get_size(self, id):
        for data in self.data_info:
            if data.id == id:
                return data.size

    def calculate_offsets(self):
        offset = 0

        for data_info in self.data_info:
            data_info.offset = offset
            offset += data_info.size

class SBData(SoundbankChunk):
    HEAD = "DATA"

    def __init__(self, data=None):
        if data is not None:
            self.head = data.read_header()

            if self.head != SBData.HEAD:
                self.head = None
                data.goto(-4, 1)
                return

            self.length = data.read_uint32()

            #if self.length != data_index.get_total_size():
                #raise SBDataError("Invalid length")

            self.offset = data.where()
        else:
            self.head = SBData.HEAD
            self.length = None
            self.offset = None

        self.data = []

    def __nonzero__(self):
        return self.head is not None

    def read_data(self, data, data_index):
        for data_info in data_index.data_info:
            data.goto(self.offset + data_info.offset)
            data_info.data = data.read_uchar(data_info.size)

        data.goto(self.offset + self.length)

        self.data = data_index.data_info

class SoundStructureField(object):
    pass

class SoundStructure_Effect(SoundStructureField):
    def __init__(self, data=None):
        if data is not None:
            self.index = data.read_uchar()
            self.id = data.read_uint32()
            self.unk_field16_1 = data.read_uint16()
        else:
            self.index = None
            self.id = None
            self.unk_field16_1 = 0

class SoundStructure_Additional(SoundStructureField):
    def __init__(self, data=None):
        if data is not None:
            self.type = data.read_uchar()
            self.value = None
        else:
            self.type = None
            self.value = None

class SoundStructure_StateGroup(SoundStructureField):
    def __init__(self, data=None):
        if data is not None:
            self.id = data.read_uint32()
            self.change_occurs = data.read_uchar()
            self.different = data.read_uint16()
            self.ids = []
            self.ids_object_contain = []

            for i in xrange(self.different):
                self.ids.append(data.read_uint32)
                self.ids_object_contain.append(data.read_uint32)
        else:
            self.id = None
            self.change_occurs = None
            self.different = None
            self.ids = []
            self.ids_object_contain = []

class SoundStructure_RTPC(SoundStructureField):
    def __init__(self, data=None):
        if data is not None:
            self.x_axis_id = data.read_uint32()
            self.y_axis_type = data.read_uint32()
            self.unk_field32_1 = data.read_uint32()
            self.unk_field8_1 = data.read_uchar()
            self.points_count = data.read_uchar()
            self.unk_field8_2 = data.read_uchar()
            self.x_coordinates = []
            self.y_coordinates = []
            self.curve_shape = []

            for i in xrange(self.points_count):
                self.x_coordinates.append(data.read_float())
                self.y_coordinates.append(data.read_float())
                self.curve_shape.append(data.read_uint32())
        else:
            self.x_axis_id = None
            self.y_axis_type = None
            self.unk_field32_1 = None
            self.unk_field8_1 = None
            self.points_count = None
            self.unk_field8_2 = None
            self.x_coordinates = []
            self.y_coordinates = []
            self.curve_shape = []

class SoundStructure(object):
    def __init__(self, data=None):
        if data is not None:
            self.effects_override = data.read_bool()
            self.effects_count = data.read_uchar()
            self.effects = []

            if self.effects_count > 0:
                self.effects_bitmask = data.read_uchar()
                self.effects = [SoundStructure_Effect(data) for i in xrange(self.effects_count)]

            self.output_bus_id = data.read_uint32()
            self.parent_id = data.read_uint32()
            self.override_playback_priority = data.read_bool()
            self.offset_priority = data.read_bool()
            self.additional_parameters_count = data.read_uchar()
            self.additional_parameters = []

            if self.additional_parameters_count > 0:
                self.additional_parameters = [SoundStructure_Additional(data) for i in xrange(self.additional_parameters_count)]

                for additional_parameter in self.additional_parameters:
                    additional_parameter.value = data.read_uint32() if additional_parameter.type == 0x07 else data.read_float()

            self.unk_field8_1 = data.read_uchar()
            self.has_positioning = data.read_bool()

            if self.has_positioning:
                self.positioning_type = data.read_uchar()

                if self.positioning_type == 0x2D:
                    self.enable_panner = data.read_bool()
                elif self.positioning_type == 0x3D:
                    self.position_source = data.read_uint32()
                    self.attenuation_id = data.read_uint32()
                    self.enable_spatialization = data.read_bool()

                    if self.position_source == 0x02:
                        self.play_type = data.read_uint32()
                        self.do_loop = data.read_bool()
                        self.transition_time = data.read_uint32()
                        self.follow_listener_orientation = data.read_bool()
                    elif self.position_source == 0x03:
                        self.update_at_each_frame = data.read_bool()
                elif self.positioning_type == 0x01:
                    self.unk_field16_1 = data.read_uint16()
                else:
                    self.unk_field32_1 = data.read_uint32()
                    self.unk_field32_2 = data.read_uint32()

            self.override_game_auxiliary_sends = data.read_bool()
            self.use_game_auxiliary_sends = data.read_bool()
            self.override_user_auxiliary_sends = data.read_bool()
            self.user_auxiliary_sends_exists = data.read_bool()

            if self.user_auxiliary_sends_exists:
                self.auxiliary_bus_id0 = data.read_uint32()
                self.auxiliary_bus_id1 = data.read_uint32()
                self.auxiliary_bus_id2 = data.read_uint32()
                self.auxiliary_bus_id3 = data.read_uint32()

            self.unk_field8_2 = data.read_bool()

            if self.unk_field8_2:
                self.priority_equal = data.read_uchar()
                self.limit_reached = data.read_uchar()
                self.limit_sound_instances = data.read_uint16()

            self.how_to_limit_sound_instances = data.read_uchar()
            self.virtual_voice_behavior = data.read_uchar()
            self.override_playback_limit = data.read_bool()
            self.override_virtual_voice = data.read_bool()
            self.state_groups_count = data.read_uint32()
            self.state_groups = []

            if self.state_groups_count > 0:
                self.state_groups = [SoundStructure_StateGroup(data) for i in xrange(self.state_groups_count)]

            self.rtpc_count = data.read_uint16()
            self.rtpcs = []

            if self.rtpc_count > 0:
                self.rtpcs = [SoundStructure_RTPC(data) for i in xrange(self.rtpc_count)]

            self.unk_field32_3 = data.read_uint32()

            if self.unk_field32_3 > 0:
                self.unk_data = data.read_uchar(0x3F)
            else:
                self.unk_data = None
        else:
            self.effects_override = None
            self.effects_count = None
            self.effects = []
            self.effects_bitmask = None
            self.output_bus_id = None
            self.parent_id = None
            self.override_playback_priority = None
            self.offset_priority = None
            self.additional_parameters_count = None
            self.additional_parameters = []
            self.unk_field8_1 = 0
            self.has_positioning = None
            self.positioning_type = None
            self.enable_panner = None
            self.position_source = None
            self.attenuation_id = None
            self.enable_spatialization = None
            self.play_type = None
            self.do_loop = None
            self.transition_time = None
            self.follow_listener_orientation = None
            self.update_at_each_frame = None
            self.unk_field32_1 = None
            self.unk_field32_2 = None
            self.override_game_auxiliary_sends = None
            self.use_game_auxiliary_sends = None
            self.override_user_auxiliary_sends = None
            self.user_auxiliary_sends_exists = None
            self.auxiliary_bus_id0 = None
            self.auxiliary_bus_id1 = None
            self.auxiliary_bus_id2 = None
            self.auxiliary_bus_id3 = None
            self.unk_field8_2 = None
            self.priority_equal = None
            self.limit_reached = None
            self.limit_sound_instances = None
            self.how_to_limit_sound_instances = None
            self.virtual_voice_behavior = None
            self.override_playback_limit = None
            self.override_virtual_voice = None
            self.state_groups_count = None
            self.state_groups = []
            self.rtpc_count =  None
            self.rtpcs = []
            self.unk_field32_3 = None
            self.unk_data = None

    def __str__(self):
        buffer = StringIO()
        data = FileWrite(buffer, True)

        data.write_bool(self.effects_override)
        data.write_uchar(self.effects_count)

        if self.effects_count > 0:
            data.write_uchar(self.effects_bitmask)

            for effect in self.effects:
                data.write_uchar(effect.index)
                data.write_uint32(effect.id)
                data.write_uint16(effect.unk_field16_1)

        data.write_uint32(self.output_bus_id)
        data.write_uint32(self.parent_id)
        data.write_bool(self.override_playback_priority)
        data.write_bool(self.offset_priority)
        data.write_uchar(self.additional_parameters_count)

        if self.additional_parameters_count > 0:
            for additional_parameter in self.additional_parameters:
                data.write_uchar(additional_parameter.type)

            for additional_parameter in self.additional_parameters:
                if additional_parameter.type == 0x07:
                    data.write_uint32(additional_parameter.value)
                else:
                    data.write_float(additional_parameter.value)

        data.write_uchar(self.unk_field8_1)
        data.write_bool(self.has_positioning)

        if self.has_positioning:
            data.write_uchar(self.positioning_type)

            if self.positioning_type == 0x2D:
                data.write_bool(self.enable_panner)
            elif self.positioning_type == 0x3D:
                data.write_uint32(self.position_source)
                data.write_uint32(self.attenuation_id)
                data.write_bool(self.enable_spatialization)

                if self.position_source == 0x02:
                    data.write_uint32(self.play_type)
                    data.write_bool(self.do_loop)
                    data.write_uint32(self.transition_time)
                    data.write_bool(self.follow_listener_orientation)
                elif self.position_source == 0x03:
                    data.write_bool(self.update_at_each_frame)
            elif self.positioning_type == 0x01:
                data.write_uint16(self.unk_field16_1)
            else:
                data.write_uint32(self.unk_field32_1)
                data.write_uint32(self.unk_field32_2)

        data.write_bool(self.override_game_auxiliary_sends)
        data.write_bool(self.use_game_auxiliary_sends)
        data.write_bool(self.override_user_auxiliary_sends)
        data.write_bool(self.user_auxiliary_sends_exists)

        if self.user_auxiliary_sends_exists:
            data.write_uint32(self.auxiliary_bus_id0)
            data.write_uint32(self.auxiliary_bus_id1)
            data.write_uint32(self.auxiliary_bus_id2)
            data.write_uint32(self.auxiliary_bus_id3)

        data.write_bool(self.unk_field8_2)

        if self.unk_field8_2:
            data.write_uchar(self.priority_equal)
            data.write_uchar(self.limit_reached)
            data.write_uint16(self.limit_sound_instances)

        data.write_uchar(self.how_to_limit_sound_instances)
        data.write_uchar(self.virtual_voice_behavior)
        data.write_bool(self.override_playback_limit)
        data.write_bool(self.override_virtual_voice)
        data.write_uint32(self.state_groups_count)

        if self.state_groups_count > 0:
            for state_group in self.state_groups:
                data.write_uint32(state_group.id)
                data.write_uchar(state_group.change_occurs)
                data.write_uint16(state_group.different)

                for i in xrange(state_group.different):
                    data.write_uint32(state_group.ids[i])
                    data.write_uint32(state_group.ids_object_contain[i])

        data.write_uint16(self.rtpc_count)

        if self.rtpc_count > 0:
            for rtpc in self.rtpcs:
                data.write_uint32(rtpc.x_axis_id)
                data.write_uint32(rtpc.y_axis_type)
                data.write_uint32(rtpc.unk_field32_1)
                data.write_uchar(rtpc.unk_field8_1)
                data.write_uchar(rtpc.points_count)
                data.write_uchar(rtpc.unk_field8_2)

                for i in xrange(rtpc.points_count):
                    data.write_float(rtpc.x_coordinates[i])
                    data.write_float(rtpc.y_coordinates[i])
                    data.write_uint32(rtpc.curve_shape[i])

        data.write_uint32(self.unk_field32_3)

        if self.unk_data is not None:
            data.write_uchar(self.unk_data)

        return buffer.getvalue()

    def __len__(self):
        return len(str(self))

class SBObjectType(object):
    def __str__(self):
        return ""
    def __len__(self):
        return len(str(self))

class SBSoundObject(SBObjectType):
    SOUND_EMBEDDED   = 0x00
    SOUND_STREAMED   = 0x01
    SOUND_PREFETCHED = 0x02
    SOUND_TYPE_SFX   = 0x00
    SOUND_TYPE_VOICE = 0x01

    def __init__(self, data=None, curPos=None, length=None):
        if data is not None:
            self.unk_field32_1 = data.read_uint32()
            self.include_type = data.read_uint32()

            if self.include_type not in (SBSoundObject.SOUND_EMBEDDED, SBSoundObject.SOUND_STREAMED, SBSoundObject.SOUND_PREFETCHED):
                raise SBObjectError("Invalid include type")

            self.audio_id = data.read_uint32()
            self.source_id = data.read_uint32()

            if self.include_type == SBSoundObject.SOUND_EMBEDDED:
                self.offset = data.read_uint32()
                self.size = data.read_uint32()

            self.sound_type = data.read_uchar()

            if self.sound_type not in (SBSoundObject.SOUND_TYPE_SFX, SBSoundObject.SOUND_TYPE_VOICE):
                raise SBObjectError("Invalid sound type")

            self.sound_structure = data.read_uchar((length - (data.where() - curPos)))
        else:
            self.unk_field32_1 = None
            self.include_type = None
            self.audio_id = None
            self.source_id = None
            self.offset = None
            self.size = None
            self.sound_type = None
            self.sound_structure = None

    def __str__(self):
        buffer = StringIO()
        data = FileWrite(buffer, True)

        data.write_uint32(self.unk_field32_1)
        data.write_uint32(self.include_type)
        data.write_uint32(self.audio_id)
        data.write_uint32(self.source_id)

        if self.include_type == SBSoundObject.SOUND_EMBEDDED:
            data.write_uint32(self.offset)
            data.write_uint32(self.size)

        data.write_uchar(self.sound_type)
        data.write_uchar(str(self.sound_structure))

        return buffer.getvalue()

class EventActionField(object):
    pass

class EventAction_Additional(EventActionField):
    def __init__(self, data=None):
        if data is not None:
            self.type = data.read_uchar()
            self.value = None
        else:
            self.type = None
            self.value = None

class SBEventActionObject(SBObjectType):
    ACTION_TYPE_SET_STATE  = 0x12
    ACTION_TYPE_SET_SWITCH = 0x19

    def __init__(self, data=None, curPos=None, length=None):
        if data is not None:
            self.scope = data.read_uchar()
            self.type = data.read_uchar()
            self.game_object_id = data.read_uint32()
            self.unk_field8_1 = data.read_uchar()
            self.additional_parameters_count = data.read_uchar()
            self.additional_parameters = []

            if self.additional_parameters_count > 0:
                self.additional_parameters = [EventAction_Additional(data) for i in xrange(self.additional_parameters_count)]

                for additional_parameter in self.additional_parameters:
                    additional_parameter.value = data.read_float() if additional_parameter.type == 0x10 else data.read_uint32()

            self.unk_field8_2 = data.read_uchar()

            if self.type == SBEventActionObject.ACTION_TYPE_SET_STATE:
                self.state_group_id = data.read_uint32()
                self.state_id = data.read_uint32()
            elif self.type == SBEventActionObject.ACTION_TYPE_SET_SWITCH:
                self.switch_group_id = data.read_uint32()
                self.switch_id = data.read_uint32()
            #elif self.type == 0x01:
                #self.unk_field32_1 = data.read_uint32()
                #self.unk_field16_1 = data.read_uint16()
                #self.unk_field32_2 = data.read_uint32()
            #elif self.type == 0x04:
                #self.unk_field32_1 = data.read_uint32()
                #self.unk_field8_3 = data.read_uchar()

            remaining = (length - (data.where() - curPos))

            if remaining > 0:
                self.unk_data = data.read_uchar(remaining)
            else:
                self.unk_data = None
        else:
            self.scope = None
            self.type = None
            self.game_object_id = None
            self.unk_field8_1 = 0
            self.additional_parameters_count = None
            self.additional_parameters = []
            self.unk_field8_2 = 0
            self.state_group_id = None
            self.state_id = None
            self.switch_group_id = None
            self.switch_id = None
            #self.unk_field32_1 = None
            #self.unk_field16_1 = None
            #self.unk_field32_2 = None
            #self.unk_field8_3 = None
            self.unk_data = None

    def __str__(self):
        buffer = StringIO()
        data = FileWrite(buffer, True)

        data.write_uchar(self.scope)
        data.write_uchar(self.type)
        data.write_uint32(self.game_object_id)
        data.write_uchar(self.unk_field8_1)
        data.write_uchar(self.additional_parameters_count)

        for additional_parameter in self.additional_parameters:
            data.write_uchar(additional_parameter.type)

        for additional_parameter in self.additional_parameters:
            if additional_parameter.type == 0x10:
                data.write_float(additional_parameter.value)
            else:
                data.write_uint32(additional_parameter.value)

        data.write_uchar(self.unk_field8_2)

        if self.type == SBEventActionObject.ACTION_TYPE_SET_STATE:
            data.write_uint32(self.state_group_id)
            data.write_uint32(self.state_id)
        elif self.type == SBEventActionObject.ACTION_TYPE_SET_SWITCH:
            data.write_uint32(self.switch_group_id)
            data.write_uint32(self.switch_id)
        #elif self.type == 0x01:
            #data.write_uint32(self.unk_field32_1)
            #data.write_uint16(self.unk_field16_1)
            #data.write_uint32(self.unk_field32_2)
        #elif self.type == 0x04:
            #data.write_uint32(self.unk_field32_1)
            #data.write_uchar(self.unk_field8_3)

        if self.unk_data is not None:
            data.write_uchar(self.unk_data)

        return buffer.getvalue()

class SBEventObject(SBObjectType):
    def __init__(self, data=None):
        if data is not None:
            self.event_actions = data.read_uint32()
            self.event_action_ids = []

            for i in xrange(self.event_actions):
                self.event_action_ids.append(data.read_uint32())
        else:
            self.event_actions = None
            self.event_action_ids = []

    def __str__(self):
        buffer = StringIO()
        data = FileWrite(buffer, True)

        data.write_uint32(self.event_actions)

        for action_id in self.event_action_ids:
            data.write_uint32(action_id)

        return buffer.getvalue()

class SBMusicSegmentObject(SBObjectType):
    def __init__(self, data=None, curPos=None, length=None):
        if data is not None:
            self.sound_structure = SoundStructure(data)
            self.children = data.read_uint32()
            self.child_ids = []

            for i in xrange(self.children):
                self.child_ids.append(data.read_uint32())

            self.unk_double_1 = data.read_double()
            self.unk_field64_1 = data.read_uint64()
            self.tempo = data.read_float()
            self.time_sig1 = data.read_uchar()
            self.time_sig2 = data.read_uchar()
            self.unk_field32_1 = data.read_uint32()
            self.unk_field8_1 = data.read_uchar()
            self.time_length = data.read_double()
            self.unk_field32_2 = data.read_uint32()
            self.unk_field32_3 = data.read_uint32()
            self.unk_field64_2 = data.read_uint64()
            self.unk_field32_4 = data.read_uint32()
            self.unk_field32_5 = data.read_uint32()
            self.time_length_next = data.read_double()
            self.unk_field32_6 = data.read_uint32()

            remaining = (length - (data.where() - curPos))

            if remaining > 0:
                self.unk_data = data.read_uchar(remaining)
            else:
                self.unk_data = None
        else:
            self.sound_structure = None
            self.children = None
            self.child_ids = []
            self.unk_double_1 = None
            self.unk_field64_1 = None
            self.tempo = None
            self.time_sig1 = None
            self.time_sig2 = None
            self.unk_field32_1 = None
            self.unk_field8_1 = None
            self.time_length = None
            self.unk_field32_2 = None
            self.unk_field32_3 = None
            self.unk_field64_2 = None
            self.unk_field32_4 = None
            self.unk_field32_5 = None
            self.time_length_next = None
            self.unk_field32_6 = None

    def __str__(self):
        buffer = StringIO()
        data = FileWrite(buffer, True)

        data.write_uchar(str(self.sound_structure))
        data.write_uint32(self.children)

        for child in self.child_ids:
            data.write_uint32(child)

        data.write_double(self.unk_double_1)
        data.write_uint64(self.unk_field64_1)
        data.write_float(self.tempo)
        data.write_uchar(self.time_sig1)
        data.write_uchar(self.time_sig2)
        data.write_uint32(self.unk_field32_1)
        data.write_uchar(self.unk_field8_1)
        data.write_double(self.time_length)
        data.write_uint32(self.unk_field32_2)
        data.write_uint32(self.unk_field32_3)
        data.write_uint64(self.unk_field64_2)
        data.write_uint32(self.unk_field32_4)
        data.write_uint32(self.unk_field32_5)
        data.write_double(self.time_length_next)
        data.write_uint32(self.unk_field32_6)

        if self.unk_data is not None:
            data.write_uchar(self.unk_data)

        return buffer.getvalue()

class SBMusicTrackObject(SBObjectType):
    def __init__(self, data=None, curPos=None, length=None):
        if data is not None:
            self.unk_field32_1 = data.read_uint32()
            self.unk_field32_2 = data.read_uint32()
            self.unk_field32_3 = data.read_uint32()
            self.id1 = data.read_uint32()

            if self.id1 > 0:
                self.id2 = data.read_uint32()
                self.unk_field32_4 = data.read_uint32()
                self.unk_field32_5 = data.read_uint32()
                self.unk_field8_1 = data.read_uchar()
                self.id3 = data.read_uint32()
                self.unk_field64_1 = data.read_uint64()
                self.unk_field64_2 = data.read_uint64()
                self.unk_field64_3 = data.read_uint64()
                self.time_length = data.read_double()

            remaining = (length - (data.where() - curPos))

            self.unk_data = data.read_uchar(remaining)
        else:
            self.unk_field32_1 = None
            self.unk_field32_2 = None
            self.unk_field32_3 = None
            self.id1 = None
            self.id2 = None
            self.unk_field32_4 = None
            self.unk_field32_5 = None
            self.unk_field8_1 = None
            self.id3 = None
            self.unk_field64_1 = None
            self.unk_field64_2 = None
            self.unk_field64_3 = None
            self.time_length = None
            self.unk_data = None

    def __str__(self):
        buffer = StringIO()
        data = FileWrite(buffer, True)

        data.write_uint32(self.unk_field32_1)
        data.write_uint32(self.unk_field32_2)
        data.write_uint32(self.unk_field32_3)
        data.write_uint32(self.id1)

        if self.id1 > 0:
            data.write_uint32(self.id2)
            data.write_uint32(self.unk_field32_4)
            data.write_uint32(self.unk_field32_5)
            data.write_uchar(self.unk_field8_1)
            data.write_uint32(self.id3)
            data.write_uint64(self.unk_field64_1)
            data.write_uint64(self.unk_field64_2)
            data.write_uint64(self.unk_field64_3)
            data.write_double(self.time_length)

        data.write_uchar(self.unk_data)

        return buffer.getvalue()

class SBMusicTrackCustomObject(SBMusicTrackObject):
    def __init__(self, mid, new_time, parent):
        self.unk_field32_1 = 1
        self.unk_field32_2 = 0x00040001
        self.unk_field32_3 = 1
        self.id1 = mid
        self.id2 = mid
        self.unk_field32_4 = 0x00000100
        self.unk_field32_5 = 0
        self.unk_field8_1 = 0
        self.id3 = mid
        self.unk_field64_1 = 0
        self.unk_field64_2 = 0
        self.unk_field64_3 = 0x8000000000000000
        self.time_length = new_time
        self.unk_field32_6 = 1
        self.unk_field64_4 = 0
        self.unk_field16_1 = 0
        self.parent = parent
        self.unk_field64_5 = 0
        self.unk_field8_2 = 0
        self.unk_field32_7 = 1
        self.unk_field64_6 = 0
        self.unk_field64_7 = 0
        self.unk_field16_2 = 0
        self.unk_field8_3 = 0
        self.unk_field32_8 = 0x00000064

    def __str__(self):
        buffer = StringIO()
        data = FileWrite(buffer, True)

        data.write_uint32(self.unk_field32_1)
        data.write_uint32(self.unk_field32_2)
        data.write_uint32(self.unk_field32_3)
        data.write_uint32(self.id1)
        data.write_uint32(self.id2)
        data.write_uint32(self.unk_field32_4)
        data.write_uint32(self.unk_field32_5)
        data.write_uchar(self.unk_field8_1)
        data.write_uint32(self.id3)
        data.write_uint64(self.unk_field64_1)
        data.write_uint64(self.unk_field64_2)
        data.write_uint64(self.unk_field64_3)
        data.write_double(self.time_length)
        data.write_uint32(self.unk_field32_6)
        data.write_uint64(self.unk_field64_4)
        data.write_uint16(self.unk_field16_1)
        data.write_uint32(self.parent)
        data.write_uint64(self.unk_field64_5)
        data.write_uchar(self.unk_field8_2)
        data.write_uint32(self.unk_field32_7)
        data.write_uint64(self.unk_field64_6)
        data.write_uint64(self.unk_field64_7)
        data.write_uint16(self.unk_field16_2)
        data.write_uchar(self.unk_field8_3)
        data.write_uint32(self.unk_field32_8)

        return buffer.getvalue()

class MusicSwitchObject(object):
    pass

class MusicSwitchObject_Transition(MusicSwitchObject):
    def __init__(self, data=None):
        if data is not None:
            self.source_id = data.read_uint32()
            self.dest_id = data.read_uint32()
            self.source_fadeout = data.read_int32()
            self.source_shape_curve_fadeout = data.read_uint32()
            self.source_fadeout_offset = data.read_int32()
            self.exit_source = data.read_uint32()
            self.unk_field32_1 = data.read_uint32()
            self.unk_field32_2 = data.read_uint32()
            self.src_type = data.read_uchar()
            self.dest_fadein = data.read_int32()
            self.dest_shape_curve_fadein = data.read_uint32()
            self.dest_fadein_offset = data.read_int32()
            self.match_custom_cue_id = data.read_uint32()
            self.playlist_id = data.read_uint32()
            self.sync_to = data.read_uint16()
            self.dest_type = data.read_uchar()
            self.unk_field8_1 = data.read_uchar()
            self.has_transition = data.read_bool()
            self.trans_id = data.read_uint32()
            self.trans_fadein = data.read_int32()
            self.trans_shape_curve_fadein = data.read_uint32()
            self.trans_fadein_offset = data.read_int32()
            self.trans_fadeout = data.read_int32()
            self.trans_shape_curve_fadeout = data.read_uint32()
            self.trans_fadeout_offset = data.read_int32()
            self.trans_fadein_type = data.read_uchar()
            self.trans_fadeout_type = data.read_uchar()

        else:
            self.source_id = None
            self.dest_id = None
            self.source_fadeout = None
            self.source_shape_curve_fadeout = None
            self.source_fadeout_offset = None
            self.exit_source = None
            self.unk_field32_1 = None
            self.unk_field32_2 = None
            self.src_type = None
            self.dest_fadein = None
            self.dest_shape_curve_fadein = None
            self.dest_fadein_offset = None
            self.match_custom_cue_id = None
            self.playlist_id = None
            self.sync_to = None
            self.dest_type = None
            self.unk_field8_1 = None
            self.has_transition = None
            self.trans_id = None
            self.trans_fadein = None
            self.trans_shape_curve_fadein = None
            self.trans_fadein_offset = None
            self.trans_fadeout = None
            self.trans_shape_curve_fadeout = None
            self.trans_fadeout_offset = None
            self.trans_fadein_type = None
            self.trans_fadeout_type = None

class MusicSwitchObject_SwitchState(MusicSwitchObject):
    def __init__(self, data=None):
        if data is not None:
            self.id = data.read_uint32()
            self.music_id = data.read_uint32()
        else:
            self.id = None
            self.music_id = None

class SBMusicSwitchObject(SBObjectType):
    def __init__(self, data=None, curPos=None, length=None):
        if data is not None:
            self.sound_structure = SoundStructure(data)
            self.children = data.read_uint32()
            self.child_ids = []

            for i in xrange(self.children):
                self.child_ids.append(data.read_uint32())

            self.unk_double_1 = data.read_double()
            self.unk_field64_1 = data.read_uint64()
            self.tempo = data.read_float()
            self.time_sig1 = data.read_uchar()
            self.time_sig2 = data.read_uchar()
            self.unk_field8_1 = data.read_uchar()
            self.unk_field32_3 = data.read_uint32()
            self.transition_count = data.read_uint32()
            self.transitions = []

            #if self.transition_count > 0:
                #self.transitions = [MusicSwitchObject_Transition(data) for i in xrange(self.transition_count)]

            #self.switch_type = data.read_uint32()
            #self.switch_state_group_id = data.read_uint32()
            #self.switch_state_default_id = data.read_uint32()
            #self.continue_to_play = data.read_bool()
            #self.switch_state_count = data.read_uint32()
            #self.switch_state = []

            #if switch_state_count > 0:
                #self.switch_state = [MusicSwitchObject_SwitchState(data) for i in xrange(switch_state_count)]

            self.unk_data = data.read_uchar(length - (data.where() - curPos))

class MusicPlaylistObject(object):
    pass

class MusicPlaylistObject_Transition(MusicPlaylistObject):
    def __init__(self, data=None):
        if data is not None:
            self.source_id = data.read_uint32()
            self.dest_id = data.read_uint32()
            self.source_fadeout = data.read_int32()
            self.source_shape_curve_fadeout = data.read_uint32()
            self.source_fadeout_offset = data.read_int32()
            self.unk_field32_1 = data.read_uint32()
            self.unk_field32_2 = data.read_uint32()
            self.unk_field32_3 = data.read_uint32()
            self.src_type = data.read_uchar()
            self.dest_fadein = data.read_int32()
            self.dest_shape_curve_fadein = data.read_uint32()
            self.dest_fadein_offset = data.read_int32()
            self.unk_field32_4 = data.read_uint32()
            self.unk_field32_5 = data.read_uint32()
            self.unk_field16_1 = data.read_uint16()
            self.dest_type = data.read_uchar()
            self.unk_field8_1 = data.read_uchar()
            self.has_segment = data.read_bool()
            self.trans_segment_id = data.read_uint32()
            self.trans_fadein = data.read_int32()
            self.trans_shape_curve_fadein = data.read_uint32()
            self.trans_fadein_offset = data.read_int32()
            self.trans_fadeout = data.read_int32()
            self.trans_shape_curve_fadeout = data.read_uint32()
            self.trans_fadeout_offset = data.read_int32()
            self.trans_fadein_type = data.read_uchar()
            self.trans_fadeout_type = data.read_uchar()
        else:
            self.source_id = None
            self.dest_id = None
            self.source_fadeout = None
            self.source_shape_curve_fadeout = None
            self.source_fadeout_offset = None
            self.unk_field32_1 = None
            self.unk_field32_2 = None
            self.unk_field32_3 = 7
            self.src_type = None
            self.dest_fadein = None
            self.dest_shape_curve_fadein = None
            self.dest_fadein_offset = None
            self.unk_field32_4 = None
            self.unk_field32_5 = None
            self.unk_field16_1 = None
            self.dest_type = None
            self.unk_field8_1 = 0
            self.has_segment = None
            self.trans_segment_id = None
            self.trans_fadein = None
            self.trans_shape_curve_fadein = None
            self.trans_fadein_offset = None
            self.trans_fadeout = None
            self.trans_shape_curve_fadeout = None
            self.trans_fadeout_offset = None
            self.trans_fadein_type = None
            self.trans_fadeout_type = None

class MusicPlaylistObject_PlaylistElement(MusicPlaylistObject):
    SIZE = 0x1A

    def __init__(self, data=None):
        if data is not None:
            self.music_segment_id = data.read_uint32()
            self.id = data.read_uint32()
            self.child_elements = data.read_uint32()
            self.playlist_type = data.read_int32()
            self.loop_count = data.read_uint16()
            self.weight = data.read_uint32()
            self.times_in_row = data.read_uint16()
            self.unk_field8_1 = data.read_uchar()
            self.random_type = data.read_uchar()
        else:
            self.music_segment_id = None
            self.id = None
            self.child_elements = None
            self.playlist_type = None
            self.loop_count = None
            self.weight = None
            self.times_in_row = None
            self.unk_field8_1 = 1
            self.random_type = None

class SBMusicPlaylistObject(SBObjectType):
    def __init__(self, data=None, curPos=None, length=None):
        if data is not None:
            self.sound_structure = SoundStructure(data)
            self.segments = data.read_uint32()
            self.segment_ids = []

            for i in xrange(self.segments):
                self.segment_ids.append(data.read_uint32())

            self.unk_double_1 = data.read_double()
            self.unk_field64_1 = data.read_uint64()
            self.tempo = data.read_float()
            self.time_sig1 = data.read_uchar()
            self.time_sig2 = data.read_uchar()
            self.unk_field8_1 = data.read_uchar()
            self.unk_field32_1 = data.read_uint32()
            self.transition_count = data.read_uint32()
            self.transitions = []

            if self.transition_count > 0:
                self.transitions = [MusicPlaylistObject_Transition(data) for i in xrange(self.transition_count)]

            self.playlist_elements_count = data.read_uint32() # This one doesn't make sense.
            self.playlist_elements = []

            elements_count = (length - (data.where() - curPos)) / MusicPlaylistObject_PlaylistElement.SIZE

            if elements_count > 0:
                self.playlist_elements = [MusicPlaylistObject_PlaylistElement(data) for i in xrange(elements_count)]
        else:
            self.sound_structure = None
            self.segments = None
            self.segment_ids = []
            self.unk_double_1 = None
            self.unk_field64_1 = None
            self.tempo = None
            self.time_sig1 = None
            self.time_sig2 = None
            self.unk_field8_1 = None
            self.unk_field32_1 = None
            self.transition_count = None
            self.transitions = []
            self.playlist_elements_count = None
            self.playlist_elements = []

    def __str__(self):
        buffer = StringIO()
        data = FileWrite(buffer, True)

        data.write_uchar(str(self.sound_structure))
        data.write_uint32(self.segments)

        for segment in self.segment_ids:
            data.write_uint32(segment)

        data.write_double(self.unk_double_1)
        data.write_uint64(self.unk_field64_1)
        data.write_float(self.tempo)
        data.write_uchar(self.time_sig1)
        data.write_uchar(self.time_sig2)
        data.write_uchar(self.unk_field8_1)
        data.write_uint32(self.unk_field32_1)
        data.write_uint32(self.transition_count)

        for transition in self.transitions:
            data.write_uint32(transition.source_id)
            data.write_uint32(transition.dest_id)
            data.write_int32(transition.source_fadeout)
            data.write_uint32(transition.source_shape_curve_fadeout)
            data.write_int32(transition.source_fadeout_offset)
            data.write_uint32(transition.unk_field32_1)
            data.write_uint32(transition.unk_field32_2)
            data.write_uint32(transition.unk_field32_3)
            data.write_uchar(transition.src_type)
            data.write_int32(transition.dest_fadein)
            data.write_uint32(transition.dest_shape_curve_fadein)
            data.write_int32(transition.dest_fadein_offset)
            data.write_uint32(transition.unk_field32_4)
            data.write_uint32(transition.unk_field32_5)
            data.write_uint16(transition.unk_field16_1)
            data.write_uchar(transition.dest_type)
            data.write_uchar(transition.unk_field8_1)
            data.write_bool(transition.has_segment)
            data.write_uint32(transition.trans_segment_id)
            data.write_int32(transition.trans_fadein)
            data.write_uint32(transition.trans_shape_curve_fadein)
            data.write_int32(transition.trans_fadein_offset)
            data.write_int32(transition.trans_fadeout)
            data.write_uint32(transition.trans_shape_curve_fadeout)
            data.write_int32(transition.trans_fadeout_offset)
            data.write_uchar(transition.trans_fadein_type)
            data.write_uchar(transition.trans_fadeout_type)

        data.write_uint32(self.playlist_elements_count)

        for playlist_element in self.playlist_elements:
            data.write_uint32(playlist_element.music_segment_id)
            data.write_uint32(playlist_element.id)
            data.write_uint32(playlist_element.child_elements)
            data.write_int32(playlist_element.playlist_type)
            data.write_uint16(playlist_element.loop_count)
            data.write_uint32(playlist_element.weight)
            data.write_uint16(playlist_element.times_in_row)
            data.write_uchar(playlist_element.unk_field8_1)
            data.write_uchar(playlist_element.random_type)

        return buffer.getvalue()

    def _get_new_element_id(self):
        nid = -1

        while nid == -1:
            nid = Random.uint32()

            for playlist_element in self.playlist_elements:
                if playlist_element.id == nid:
                    nid = -1
                    break

        return nid

    def export(self, objects):
        ini = SafeConfigParser()

        if self.segment_ids:
            ini.add_section("SEGMENTS")

            for (i, segid) in enumerate(self.segment_ids, 1):
                ini.set("SEGMENTS", "segment%i" % (i), str(segid))

        for (i, transition) in enumerate(self.transitions, 1):
            ini.add_section("TRANSITION %i" % (i))
            ini.set("TRANSITION %i" % (i), "source_id", str(transition.source_id))
            ini.set("TRANSITION %i" % (i), "dest_id", str(transition.dest_id))
            ini.set("TRANSITION %i" % (i), "source_fadeout", str(transition.source_fadeout))
            ini.set("TRANSITION %i" % (i), "source_shape_curve_fadeout", str(transition.source_shape_curve_fadeout))
            ini.set("TRANSITION %i" % (i), "source_fadeout_offset", str(transition.source_fadeout_offset))
            ini.set("TRANSITION %i" % (i), "unk_field32_1", str(transition.unk_field32_1))
            ini.set("TRANSITION %i" % (i), "unk_field32_2", str(transition.unk_field32_2))
            ini.set("TRANSITION %i" % (i), "unk_field32_3", str(transition.unk_field32_3))
            ini.set("TRANSITION %i" % (i), "src_type", str(transition.src_type))
            ini.set("TRANSITION %i" % (i), "dest_fadein", str(transition.dest_fadein))
            ini.set("TRANSITION %i" % (i), "dest_shape_curve_fadein", str(transition.dest_shape_curve_fadein))
            ini.set("TRANSITION %i" % (i), "dest_fadein_offset", str(transition.dest_fadein_offset))
            ini.set("TRANSITION %i" % (i), "unk_field32_4", str(transition.unk_field32_4))
            ini.set("TRANSITION %i" % (i), "unk_field32_5", str(transition.unk_field32_5))
            ini.set("TRANSITION %i" % (i), "unk_field16_1", str(transition.unk_field16_1))
            ini.set("TRANSITION %i" % (i), "dest_type", str(transition.dest_type))
            ini.set("TRANSITION %i" % (i), "unk_field8_1", str(transition.unk_field8_1))
            ini.set("TRANSITION %i" % (i), "has_segment", str(transition.has_segment))
            ini.set("TRANSITION %i" % (i), "trans_segment_id", str(transition.trans_segment_id))
            ini.set("TRANSITION %i" % (i), "trans_fadein", str(transition.trans_fadein))
            ini.set("TRANSITION %i" % (i), "trans_shape_curve_fadein", str(transition.trans_shape_curve_fadein))
            ini.set("TRANSITION %i" % (i), "trans_fadein_offset", str(transition.trans_fadein_offset))
            ini.set("TRANSITION %i" % (i), "trans_fadeout", str(transition.trans_fadeout))
            ini.set("TRANSITION %i" % (i), "trans_shape_curve_fadeout", str(transition.trans_shape_curve_fadeout))
            ini.set("TRANSITION %i" % (i), "trans_fadeout_offset", str(transition.trans_fadeout_offset))
            ini.set("TRANSITION %i" % (i), "trans_fadein_type", str(transition.trans_fadein_type))
            ini.set("TRANSITION %i" % (i), "trans_fadeout_type", str(transition.trans_fadeout_type))

        for (i, playlist_element) in enumerate(self.playlist_elements, 1):
            ini.add_section("PLAYLIST ELEMENT %i" % (i))

            tracks = []

            for obj in objects:
                if obj.type == SBObject.TYPE_MUSIC_SEGMENT and obj.id == playlist_element.music_segment_id:
                    tracks = [str(child.obj.id1) for child in objects if child.id in obj.obj.child_ids]
                    break

            if tracks:
                ini.set("PLAYLIST ELEMENT %i" % (i), "tracks", ", ".join(tracks))

            ini.set("PLAYLIST ELEMENT %i" % (i), "music_segment_id", str(playlist_element.music_segment_id))
            ini.set("PLAYLIST ELEMENT %i" % (i), "id", str(playlist_element.id))
            ini.set("PLAYLIST ELEMENT %i" % (i), "child_elements", str(playlist_element.child_elements))
            ini.set("PLAYLIST ELEMENT %i" % (i), "playlist_type", str(playlist_element.playlist_type))
            ini.set("PLAYLIST ELEMENT %i" % (i), "loop_count", str(playlist_element.loop_count))
            ini.set("PLAYLIST ELEMENT %i" % (i), "weight", str(playlist_element.weight))
            ini.set("PLAYLIST ELEMENT %i" % (i), "times_in_row", str(playlist_element.times_in_row))
            ini.set("PLAYLIST ELEMENT %i" % (i), "unk_field8_1", str(playlist_element.unk_field8_1))
            ini.set("PLAYLIST ELEMENT %i" % (i), "random_type", str(playlist_element.random_type))

        return ini

    def reimport(self, file):
        ini = SafeConfigParser()

        with open(file, "rt") as f:
            ini.readfp(f)

        segments = ()
        moveSegments = ()
        transitions = []
        playlist_elements = []

        for section in ini.sections():                
            if section == "SEGMENTS":
                segments = (name for (name, value) in ini.items("SEGMENTS"))
            elif section == "MOVE SEGMENTS":
                moveSegments = (name for (name, value) in ini.items("MOVE SEGMENTS"))
            elif section.startswith("TRANSITION "):
                transitions.append(int(section[11:]))
            elif section.startswith("PLAYLIST ELEMENT "):
                playlist_elements.append(int(section[17:]))

        new_segment_ids = [ini.getint("SEGMENTS", name) for name in segments]
        moveSegments = [ini.getint("MOVE SEGMENTS", name) for name in moveSegments]

        transitions.sort()
        new_transitions = []

        for transition in transitions:
            transition = "TRANSITION %i" % (transition)

            new_transition = MusicPlaylistObject_Transition()

            new_transition.source_id = ini.getint(transition, "source_id")
            new_transition.dest_id = ini.getint(transition, "dest_id")
            new_transition.source_fadeout = ini.getint(transition, "source_fadeout")
            new_transition.source_shape_curve_fadeout = ini.getint(transition, "source_shape_curve_fadeout")
            new_transition.source_fadeout_offset = ini.getint(transition, "source_fadeout_offset")
            new_transition.unk_field32_1 = ini.getint(transition, "unk_field32_1")
            new_transition.unk_field32_2 = ini.getint(transition, "unk_field32_2")
            new_transition.unk_field32_3 = ini.getint(transition, "unk_field32_3")
            new_transition.src_type = ini.getint(transition, "src_type")
            new_transition.dest_fadein = ini.getint(transition, "dest_fadein")
            new_transition.dest_shape_curve_fadein = ini.getint(transition, "dest_shape_curve_fadein")
            new_transition.dest_fadein_offset = ini.getint(transition, "dest_fadein_offset")
            new_transition.unk_field32_4 = ini.getint(transition, "unk_field32_4")
            new_transition.unk_field32_5 = ini.getint(transition, "unk_field32_5")
            new_transition.unk_field16_1 = ini.getint(transition, "unk_field16_1")
            new_transition.dest_type = ini.getint(transition, "dest_type")
            new_transition.unk_field8_1 = ini.getint(transition, "unk_field8_1")
            new_transition.has_segment = ini.getboolean(transition, "has_segment")
            new_transition.trans_segment_id = ini.getint(transition, "trans_segment_id")
            new_transition.trans_fadein = ini.getint(transition, "trans_fadein")
            new_transition.trans_shape_curve_fadein = ini.getint(transition, "trans_shape_curve_fadein")
            new_transition.trans_fadein_offset = ini.getint(transition, "trans_fadein_offset")
            new_transition.trans_fadeout = ini.getint(transition, "trans_fadeout")
            new_transition.trans_shape_curve_fadeout = ini.getint(transition, "trans_shape_curve_fadeout")
            new_transition.trans_fadeout_offset = ini.getint(transition, "trans_fadeout_offset")
            new_transition.trans_fadein_type = ini.getint(transition, "trans_fadein_type")
            new_transition.trans_fadeout_type = ini.getint(transition, "trans_fadeout_type")

            new_transitions.append(new_transition)

        playlist_elements.sort()
        new_playlist_elements = []

        for playlist_element in playlist_elements:
            playlist_element = "PLAYLIST ELEMENT %i" % (playlist_element)

            new_playlist_element = MusicPlaylistObject_PlaylistElement()

            new_playlist_element.music_segment_id = ini.getint(playlist_element, "music_segment_id")

            if ini.get(playlist_element, "id", True) == "<NEW ID>":
                new_playlist_element.id = self._get_new_element_id()
            else:
                new_playlist_element.id = ini.getint(playlist_element, "id")

            new_playlist_element.child_elements = ini.getint(playlist_element, "child_elements")
            new_playlist_element.playlist_type = ini.getint(playlist_element, "playlist_type")
            new_playlist_element.loop_count = ini.getint(playlist_element, "loop_count")
            new_playlist_element.weight = ini.getint(playlist_element, "weight")
            new_playlist_element.times_in_row = ini.getint(playlist_element, "times_in_row")
            new_playlist_element.unk_field8_1 = ini.getint(playlist_element, "unk_field8_1")
            new_playlist_element.random_type = ini.getint(playlist_element, "random_type")

            new_playlist_elements.append(new_playlist_element)

        if new_segment_ids:
            self.segment_ids = new_segment_ids
            self.segments = len(self.segment_ids)

        if new_transitions:
            self.transitions = new_transitions
            self.transition_count = len(self.transitions)

        if new_playlist_elements:
            self.playlist_elements = new_playlist_elements

        return moveSegments

class SBObject(object):
    TYPE_SOUND          = 0x02
    TYPE_EVENT_ACTION   = 0x03
    TYPE_EVENT          = 0x04
    TYPE_MUSIC_SEGMENT  = 0x0A
    TYPE_MUSIC_TRACK    = 0x0B
    TYPE_MUSIC_SWITCH   = 0x0C
    TYPE_MUSIC_PLAYLIST = 0x0D

    def __init__(self, data=None):
        if data is not None:
            self.type = data.read_uchar()
            self.length = data.read_uint32()
            curPos = data.where()
            self.id = data.read_uint32()

            if self.type == SBObject.TYPE_SOUND:
                self.obj = SBSoundObject(data, curPos, self.length)
            elif self.type == SBObject.TYPE_EVENT_ACTION:
                self.obj = SBEventActionObject(data, curPos, self.length)
            elif self.type == SBObject.TYPE_EVENT:
                self.obj = SBEventObject(data)
            elif self.type == SBObject.TYPE_MUSIC_SEGMENT:
                self.obj = SBMusicSegmentObject(data, curPos, self.length)
            elif self.type == SBObject.TYPE_MUSIC_TRACK:
                self.obj = SBMusicTrackObject(data, curPos, self.length)
            #elif self.type == SBObject.TYPE_MUSIC_SWITCH:
                #self.obj = SBMusicSwitchObject(data, curPos, self.length)
            elif self.type == SBObject.TYPE_MUSIC_PLAYLIST:
                self.obj = SBMusicPlaylistObject(data, curPos, self.length)
            else:
                self.obj = data.read_uchar(self.length - 4)

            if (data.where() - curPos) != self.length:
                raise SBObjectError("Invalid object")
        else:
            self.type = None
            self.length = None
            self.id = None
            self.obj = None

    def calculate_length(self):
        self.length = 4 + len(self.obj)

class SBObjects(SoundbankChunk):
    HEAD = "HIRC"

    def __init__(self, data=None):
        if data is not None:
            self.head = data.read_header()

            if self.head != SBObjects.HEAD:
                raise SBObjectsError("Invalid head")

            self.length = data.read_uint32()
            self.quantity = data.read_uint32()
            self.objects = [SBObject(data) for i in xrange(self.quantity)]
            self._ids = None
        else:
            self.head = SBObjects.HEAD
            self.length = None
            self.quantity = 0
            self.objects = []
            self._ids = None

    def calculate_length(self):
        self.quantity = len(self.objects)
        self.length = 4
        self.length += sum((5 + obj.length) for obj in self.objects)

    def _read_ids(self):
        db = FileRead("objectids.db")

        hash = db.read_uchar(sha1().digestsize)
        data = db.read_data()

        del db

        if sha1(data).digest() != hash:
            raise SBObjectsError("Invalid object ids database")

        self._ids = [struct.unpack("<I", data[i:i+4])[0] for i in xrange(0, len(data), 4)]

    def get_new_id(self):
        if self._ids is None:
            self._read_ids()

        nid = -1

        while nid == -1:
            nid = Random.uint32()

            if nid in self._ids:
                nid = -1
                continue

            for obj in self.objects:
                if obj.id == nid:
                    nid = -1
                    break

        return nid

class SBSoundTypeID(SoundbankChunk):
    HEAD = "STID"

    def __init__(self, data=None):
        if data is not None:
            self.head = data.read_header()

            if not self.head:
                self.head = None
                return
            elif self.head != SBSoundTypeID.HEAD:
                raise SBSoundTypeIDError("Invalid head")

            self.length = data.read_uint32()
            self.unk_field32_1 = data.read_uint32()
            self.quantity = data.read_uint32()
            self.remaining = data.read_uchar(self.length - 8)
        else:
            self.length = None
            self.unk_field32_1 = 1
            self.quantity = 0
            self.remaining = None

    def __nonzero__(self):
        return self.head is not None

class ManagerObject(object):
    pass

class ManagerObject_StateGroup(ManagerObject):
    def __init__(self, data=None):
        if data is not None:
            self.id = data.read_uint32()
            self.default_trans = data.read_uint32()
            self.custom_trans_count = data.read_uint32()
            self.custom_trans = []

            if self.custom_trans_count > 0:
                self.custom_trans = [ManagerObject_StateGroup_CustomTransition(data) for i in xrange(self.custom_trans_count)]

        else:
            self.id = None
            self.default_trans = None
            self.custom_trans_count = None
            self.custom_trans = []

class ManagerObject_StateGroup_CustomTransition(ManagerObject_StateGroup):
    def __init__(self, data=None):
        if data is not None:
            self.from_id = data.read_uint32()
            self.to_id = data.read_uint32()
            self.trans_time = data.read_uint32()
        else:
            self.from_id = None
            self.to_id = None
            self.trans_time = None

class ManagerObject_SwitchGroup(ManagerObject):
    def __init__(self, data=None):
        if data is not None:
            self.id = data.read_uint32()
            self.game_parameter_id = data.read_uint32()
            self.points_count = data.read_uint32()
            self.points = []

            if self.points_count > 0:
                self.points = [ManagerObject_SwitchGroup_Point(data) for i in xrange(self.points_count)]

        else:
            self.id = None
            self.game_parameter_id = None
            self.points_count = None
            self.points = []

class ManagerObject_SwitchGroup_Point(ManagerObject_SwitchGroup):
    def __init__(self, data=None):
        if data is not None:
            self.value = data.read_float()
            self.switch_id = data.read_uint32()
            self.shape_curve = data.read_uint32()
        else:
            self.value = None
            self.switch_id = None
            self.shape_curve = 0x09

class ManagerObject_GameParameter(ManagerObject):
    def __init__(self, data=None):
        if data is not None:
            self.id = data.read_uint32()
            self.default_value = data.read_float()
        else:
            self.id = None
            self.default_value = None

class SBManager(SoundbankChunk):
    HEAD = "STMG"

    def __init__(self, data=None):
        if data is not None:
            self.head = data.read_header()

            if self.head != SBManager.HEAD:
                raise SBManagerError("Invalid head")

            self.length = data.read_uint32()
            self.volume = data.read_float()
            self.max_voice_instances = data.read_uint16()
            self.state_groups_count = data.read_uint32()
            self.state_groups = []

            if self.state_groups_count > 0:
                self.state_groups = [ManagerObject_StateGroup(data) for i in xrange(self.state_groups_count)]

            self.switch_groups_count = data.read_uint32()
            self.switch_groups = []

            if self.state_groups_count > 0:
                self.switch_groups = [ManagerObject_SwitchGroup(data) for i in xrange(self.switch_groups_count)]

            self.game_parameters_count = data.read_uint32()
            self.game_parameters = []

            if self.game_parameters_count > 0:
                self.game_parameters = [ManagerObject_GameParameter(data) for i in xrange(self.game_parameters_count)]

        else:
            self.head = SBManager.HEAD
            self.length = None
            self.volume = None
            self.max_voice_instances = None
            self.state_groups_count = None
            self.state_groups = []
            self.switch_groups_count = None
            self.switch_groups = []
            self.game_parameters_count = None
            self.game_parameters = []

class SBEnvironments(SoundbankChunk):
    HEAD = "ENVS"

    def __init__(self, data=None):
        if data is not None:
            self.head = data.read_header()

            if self.head != SBEnvironments.HEAD:
                raise SBEnvironmentsError("Invalid head")

            self.length = data.read_uint32()
            self.unk_data = data.read_uchar(self.length)

        else:
            self.head = SBEnvironments.HEAD
            self.length = None
            self.unk_data = None

class WEM(object):
    def __init__(self, data=None):
        if data is not None:
            self.id = data.read_uint32()
            self.offset = data.read_uint32()
            self.size = data.read_uint32()
            self.data = None
        else:
            self.id = None
            self.offset = None
            self.size = None
            self.data = None

class FileRead(object):
    def __init__(self, file):
        self.path = file
        self.file = open(self.path, "rb")
        self.name = os.path.basename(file)
        self.size = os.path.getsize(file)

    def __del__(self):
        try:
            self.file.close()
        except Exception:
            pass

    def read_bool(self):
        c = self.read_uchar()

        if c not in (0, 1):
            raise ValueError("Not a boolean")

        return bool(c)

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

    def read_int16(self):
        return struct.unpack("<h", self.file.read(2))[0]

    def read_uint32(self):
        return struct.unpack("<I", self.file.read(4))[0]

    def read_int32(self):
        return struct.unpack("<i", self.file.read(4))[0]

    def read_float(self):
        return struct.unpack("<f", self.file.read(4))[0]

    def read_uint64(self):
        return struct.unpack("<Q", self.file.read(8))[0]

    def read_int64(self):
        return struct.unpack("<q", self.file.read(8))[0]

    def read_double(self):
        return struct.unpack("<d", self.file.read(8))[0]

    def read_header(self):
        return self.read_uchar(4)

    def read_until(self, end):
        pos = self.where()
        data = ""

        while not data.endswith(end):
            c = self.read_uchar(1)

            if not c:
                self.goto(pos)
                raise LookupError("%s was not found --EOF" % end)

            data += c

        self.goto(-len(end), 1)

        return data[:-len(end)]

    def read_data(self):
        return self.file.read()

    def where(self):
        return self.file.tell()

    def goto(self, offset, whence=0):
        self.file.seek(offset, whence)

class FileWrite(object):
    def __init__(self, file, isBuffer=False, mode="wb"):
        if not isBuffer:
            self.path = file
            self.file = open(self.path, mode)
            self.name = os.path.basename(file)
        else:
            self.path = None
            self.file = file
            self.name = None

    def __del__(self):
        try:
            self.file.close()
        except Exception:
            pass

    def write_bool(self, data):
        self.file.write(struct.pack("<?", data))

    def write_uchar(self, data):
        if type(data) == int or type(data) == long:
            self.file.write(struct.pack("<B", data))
        else:
            if len(data) > 0x7FFFFFFF:
                dv = divmod(len(data), 0x7FFFFFFF)
                count = dv[0]

                for i in xrange(count):
                    self.file.write(data[0:0x7FFFFFFF])
                    data = data[0x7FFFFFFF:]

                if dv[1] > 0:
                    self.file.write(data[:dv[1]])
            else:
                self.file.write(data)

    def write_uint16(self, data):
        self.file.write(struct.pack("<H", data))

    def write_int16(self, data):
        self.file.write(struct.pack("<h", data))

    def write_uint32(self, data):
        self.file.write(struct.pack("<I", data))

    def write_int32(self, data):
        self.file.write(struct.pack("<i", data))

    def write_float(self, data):
        self.file.write(struct.pack("<f", data))

    def write_uint64(self, data):
        self.file.write(struct.pack("<Q", data))

    def write_int64(self, data):
        self.file.write(struct.pack("<q", data))

    def write_double(self, data):
        self.file.write(struct.pack("<d", data))

    def where(self):
        return self.file.tell()

    def goto(self, offset, whence=0):
        self.file.seek(offset, whence)

class Soundbank(object):
    MODE_BUILD             = 0
    MODE_BUILD_MUSIC       = 1
    MODE_ADD_NEW_MUSIC     = 2
    MODE_PLAYLIST_ID       = 3
    MODE_EXPORT_PLAYLIST   = 4
    MODE_REIMPORT_PLAYLIST = 5
    MODE_DUMP_SOUNDS       = 6
    MODE_DEBUG             = 7
    MODE_DEBUG_EVENT       = 8
    MODE_DEBUG_SOUND       = 9
    MODE_DEBUG_OBJECT      = 10
    MODE_DEBUG_OWNER       = 11

    def __init__(self, file):
        try:
            self.file = FileRead(file)
        except (OSError, IOError):
            raise SoundbankError("Could not open soundbank")

        self._file = file
        self.header = None
        self.data_index = None
        self.data = None
        self.objects = None
        self.stid = None
        self.stmg = None
        self.envs = None
        self.to_add = []

    def __del__(self):
        try:
            del self.file
        except Exception:
            pass

    def read(self):
        self.header = SBHeader(self.file)
        self.isInit = self.file.name == "Init.bnk"

        if not self.isInit:
            #try:
                #self.unk_chunk = self.file.read_until(SBDataIndex.HEAD)
            #except LookupError:
                #try:
                    #self.unk_chunk = self.file.read_until(SBData.HEAD)
                #except LookupError:
                    #try:
                        #self.unk_chunk = self.file.read_until(SBObjects.HEAD)
                    #except LookupError:
                        #raise SoundbankError("Invalid file")

            self.data_index = SBDataIndex(self.file)
            self.data = SBData(self.file)

            if self.data:
                self.data.read_data(self.file, self.data_index)

        else:
            #try:
                #self.unk_chunk = self.file.read_until(SBManager.HEAD)
            #except LookupError:
                #raise SoundbankError("Invalid file")

            self.stmg = SBManager(self.file)

        self.objects = SBObjects(self.file)

        if not self.isInit:
            self.stid = SBSoundTypeID(self.file)
        else:
            self.envs = SBEnvironments(self.file)

        del self.file

    def debug(self):
        print "--- HEADER ---"
        print "HEAD : " + self.header.head
        print "LENGTH: %i" % (self.header.length)
        print "VERSION: %i" % (self.header.version)
        print "ID: %i" % (self.header.id)
        print "UNK FIELD32 1: %i" % (self.header.unk_field32_1)
        print "UNK FIELD32 2: %i" % (self.header.unk_field32_2)

        if self.header.unk_data is not None:
            print "UNK DATA LENGTH: %i" % (len(self.header.unk_data))

        print "--- HEADER ---"
        print

        if not self.isInit:
            if self.data_index:
                print "--- DATA INDEX ---"
                print "HEAD: " + self.data_index.head
                print "LENGTH: %i" % (self.data_index.length)

                for (i, data_info) in enumerate(self.data_index.data_info):
                    print "DATA INFO %i: (ID: %i), (OFFSET: %i), (SIZE: %i)" % (i+1, data_info.id, data_info.offset, data_info.size)

                print "--- DATA INDEX ---"
                print

            if self.data:
                print "--- DATA ---"
                print "HEAD: " + self.data.head
                print "LENGTH (NON PADDED): %i" % (self.data_index.get_total_size())
                print "LENGTH: %i" % (self.data.length)
                print "OFFSET: %i" % (self.data.offset)
                print "--- DATA ---"
                print

        else:
            print "--- MANAGER ---"
            print "HEAD: " + self.stmg.head
            print "LENGTH: %i" % (self.stmg.length)
            print "VOLUME: %f" % (self.stmg.volume)
            print "MAX VOICE INSTANCES: %i" % (self.stmg.max_voice_instances)
            print "STATE GROUPS: %i" % (self.stmg.state_groups_count)
            print "SWITCH GROUPS: %i" % (self.stmg.switch_groups_count)
            print "GAME PARAMETERS: %i" % (self.stmg.game_parameters_count)
            print "--- MANAGER ---"
            print

        print "--- OBJECTS ---"
        print "HEAD: " + self.objects.head
        print "LENGTH: %i" % (self.objects.length)
        print "QUANTITY: %i" % (self.objects.quantity)

        objTypes = {}

        for obj in self.objects.objects:
            try:
                objTypes[obj.type] += 1
            except KeyError:
                objTypes[obj.type] = 1

        for (key, value) in objTypes.iteritems():
            print "TYPE %i: %i" % (key, value)

        print "--- OBJECTS ---"
        print

        if not self.isInit:
            if self.stid:
                print "--- SOUND TYPE ID ---"
                print "HEAD: " + self.stid.head
                print "LENGTH: %i" % (self.stid.length)
                print "UNK FIELD32 1: %i" % (self.stid.unk_field32_1)
                print "QUANTITY: %i" % (self.stid.quantity)
                print "REMAINING SIZE: %i" % (len(self.stid.remaining))
                print "--- SOUND TYPE ID ---"
                print

        else:
                print "--- ENVIRONMENTS ---"
                print "HEAD: " + self.envs.head
                print "LENGTH: %i" % (self.envs.length)
                print "UNK DATA LENGTH: %i" % (len(self.envs.unk_data))
                print "--- ENVIRONMENTS ---"
                print

    def debug_event(self, event_id):
        for event in self.objects.objects:
            if event.id == event_id:
                if event.type == SBObject.TYPE_EVENT:
                    print "Event Object ID: %i" % (event.id)
                    print "Event Actions: %i" % (event.obj.event_actions)
                    print

                    for (i, action_id) in enumerate(event.obj.event_action_ids, 1):
                        print "*** EVENT ACTION %03i ***" % (i)
                        self.debug_event(action_id)
                        print

                    return
                elif event.type == SBObject.TYPE_EVENT_ACTION:
                    print "Event Action Object ID: %i" % (event.id)
                    print "Event Action Scope: %i" % (event.obj.scope)
                    print "Event Action Type: %i" % (event.obj.type)
                    print "Event Action Game Object ID: %i" % (event.obj.game_object_id)
                    print "UNK FIELD 8 1: %i" % (event.obj.unk_field8_1)
                    print "Event Action Additional Parameters Count: %i" % (event.obj.additional_parameters_count)
                    print ("Event Action Additional Parameters: %s" %
                        (", ".join(
                            "(%i: %.3f)" % (additional_parameter.type, additional_parameter.value)
                            if additional_parameter.type == 0x10 else
                            "(%i: %i)" % (additional_parameter.type, additional_parameter.value)
                            for additional_parameter in event.obj.additional_parameters
                        ))
                    )
                    print "UNK FIELD 8 2: %i" % (event.obj.unk_field8_2)

                    if event.obj.type == SBEventActionObject.ACTION_TYPE_SET_STATE:
                        print "Event Action State Group ID: %i" % (event.obj.state_group_id)
                        print "Event Action State ID: %i" % (event.obj.state_id)
                    elif event.obj.type == SBEventActionObject.ACTION_TYPE_SET_SWITCH:
                        print "Event Action Switch Group ID: %i" % (event.obj.switch_group_id)
                        print "Event Action Switch ID: %i" % (event.obj.switch_id)
                    #elif event.obj.type == 0x01:
                        #print "UNK FIELD 32 1: %i" % (event.obj.unk_field32_1)
                        #print "UNK FIELD 16 1: %i" % (event.obj.unk_field16_1)
                        #print "UNK FIELD 32 2: %i" % (event.obj.unk_field32_2)
                    #elif event.obj.type == 0x04:
                        #print "UNK FIELD 32 1: %i" % (event.obj.unk_field32_1)
                        #print "UNK FIELD 8 3: %i" % (event.obj.unk_field8_3)

                    if event.obj.unk_data is not None:
                        print "UNK DATA: %s" % (hexlify(event.obj.unk_data).upper())

                    print "---------- SOUND ----------"
                    self.debug_sound(event.obj.game_object_id)
                    print "---------- SOUND ----------"

                    return
                else:
                    break

        print "No event object by ID %i." % (event_id)

    def debug_sound(self, sound_id):
        for sound in self.objects.objects:
            if sound.id == sound_id:
                if sound.type == SBObject.TYPE_SOUND:
                    print "Sound Object ID: %i" % (sound.id)
                    print "UNK FIELD 32 1: %i" % (sound.obj.unk_field32_1)
                    print "Sound Include Type: %i" % (sound.obj.include_type)
                    print "Sound Audio ID: %i" % (sound.obj.audio_id)
                    print "Sound Source ID: %i" % (sound.obj.source_id)

                    if sound.obj.include_type == SBSoundObject.SOUND_EMBEDDED:
                        print "Sound Offset: %i" % (sound.obj.offset)
                        print "Sound Size: %i" % (sound.obj.size)

                    print "Sound Type: %i" % (sound.obj.sound_type)
                    print "Sound Structure: %s" % (hexlify(sound.obj.sound_structure).upper())

                    return
                else:
                    break

        print "No sound object by ID %i." % (sound_id)

    def debug_object(self, object_id):
        for object in self.objects.objects:
            if object.id == object_id:
                print "Object ID: %i" % (object.id)
                print "Object Type: %i" % (object.type)
                print "Object Size: %i" % (len(str(object.obj)))
                print "Object Data: %s" % (hexlify(str(object.obj)).upper())

                return

        print "No object by ID %i." % (object_id)

    def debug_owner(self, audio_id):
        for owner in self.objects.objects:
            if owner.type == SBObject.TYPE_SOUND:
                if owner.obj.audio_id == audio_id:
                    print "Object Owner ID: %i" % (owner.id)
                    print "Object Owner Type: SOUND"

                    return
            elif owner.type == SBObject.TYPE_MUSIC_TRACK:
                if owner.obj.id1 == audio_id:
                    print "Object Owner ID: %i" % (owner.id)
                    print "Object Owner Type: MUSIC"

                    return

        print "No object owner found for audio ID %i." % (audio_id)

    def read_wems(self, folder):
        try:
            for file in os.listdir(folder):
                if not os.path.isfile(folder + os.sep + file) or not file.endswith(".wem"):
                    raise SoundbankError("%s is not a WEM file" % (file))

                path = folder + os.sep + file

                wem = WEM()
                wem.id = int(file[:-4])
                wem.size = os.path.getsize(path)

                with open(path, "rb") as f:
                    wem.data = f.read()

                self.to_add.append(wem)

        except (OSError, IOError, ValueError):
            raise SoundbankError("Failed to load new WEMs")

    def rebuild_data(self):
        for data_info in self.data_index.data_info:
            for wem in self.to_add:
                if data_info.id == wem.id:
                    data_info.size = wem.size
                    data_info.data = wem.data
                    break

    def rebuild_music(self, wem):
        mid = int(os.path.basename(wem)[:-4])

        if mid < 1 or mid > 0xFFFFFFFF:
            raise SoundbankError("Invalid WEM ID")

        _wem = compare_wem.WEM(wem)
        _wem.read()

        new_time = (_wem.sample_count / float(_wem.sample_rate)) * 1000

        del _wem

        trackids = {}

        for (i, obj) in enumerate(self.objects.objects):
            if obj.type == SBObject.TYPE_MUSIC_TRACK:
                if obj.obj.id1 == mid:
                    trackids[obj.id] = [i, None]

        if not trackids:
            raise SoundbankError("Could not find ID %i within soundbank" % (mid))

        for obj in self.objects.objects:
            if obj.type == SBObject.TYPE_MUSIC_SEGMENT:
                if len(obj.obj.child_ids) == 1:
                    if obj.obj.child_ids[0] in trackids:
                        obj.obj.unk_double_1 = 1000.0
                        obj.obj.unk_field64_1 = 0
                        obj.obj.unk_field64_2 = 0
                        obj.obj.time_length = new_time
                        obj.obj.time_length_next = new_time
                        trackids[obj.obj.child_ids[0]][1] = obj.id
                else:
                    hasTrack = [trackid for trackid in trackids if trackid in obj.obj.child_ids]

                    if hasTrack:
                        trackid = hasTrack[0]

                        obj.obj.children = 1
                        obj.obj.child_ids = [trackid]
                        obj.obj.unk_double_1 = 1000.0
                        obj.obj.unk_field64_1 = 0
                        obj.obj.unk_field64_2 = 0
                        obj.obj.time_length = new_time
                        obj.obj.time_length_next = new_time
                        obj.calculate_length()
                        trackids[trackid][1] = obj.id

        for (trackidx, segid) in trackids.itervalues():
            if segid is not None:
                self.objects.objects[trackidx].obj = SBMusicTrackCustomObject(mid, new_time, segid)
                self.objects.objects[trackidx].calculate_length()

        self.objects.calculate_length()

    def add_music(self, wem):
        mid = int(os.path.basename(wem)[:-4])

        if mid < 1 or mid > 0xFFFFFFFF:
            raise SoundbankError("Invalid WEM ID")

        _wem = compare_wem.WEM(wem)
        _wem.read()

        new_time = (_wem.sample_count / float(_wem.sample_rate)) * 1000

        del _wem

        segment = None

        for obj in self.objects.objects:
            if obj.type == SBObject.TYPE_MUSIC_TRACK:
                if obj.obj.id1 == mid:
                    raise SoundbankError("ID %i already used" % (mid))
            elif obj.type == SBObject.TYPE_MUSIC_SEGMENT:
                if segment is None:
                    segment = obj

        if segment is None:
            raise SoundbankError("No music segments within the soundbank")

        musicTrackID = self.objects.get_new_id()
        musicTrackObject = SBObject()
        musicTrackObject.type = SBObject.TYPE_MUSIC_TRACK
        musicTrackObject.id = musicTrackID
        musicTrackObject.obj = SBMusicTrackCustomObject(mid, new_time, 0)
        musicTrackObject.calculate_length()

        self.objects.objects.append(musicTrackObject)

        musicSegmentID = self.objects.get_new_id()
        musicTrackObject.obj.parent = musicSegmentID

        musicSegmentObject = deepcopy(segment)
        musicSegmentObject.id = musicSegmentID
        musicSegmentObject.obj.children = 1
        musicSegmentObject.obj.child_ids = [musicTrackID]
        musicSegmentObject.obj.unk_double_1 = 1000.0
        musicSegmentObject.obj.unk_field64_1 = 0
        musicSegmentObject.obj.unk_field64_2 = 0
        musicSegmentObject.obj.time_length = new_time
        musicSegmentObject.obj.time_length_next = new_time
        musicSegmentObject.obj.sound_structure.parent_id = 0
        musicSegmentObject.calculate_length()

        self.objects.objects.append(musicSegmentObject)

        self.objects.calculate_length()

        return musicSegmentID

    def get_playlist_ids(self, wid):
        if wid < 1 or wid > 0xFFFFFFFF:
            raise SoundbankError("Invalid music ID")

        trackids = []

        for obj in self.objects.objects:
            if obj.type == SBObject.TYPE_MUSIC_TRACK:
                if obj.obj.id1 == wid:
                    trackids.append(obj.id)

        if not trackids:
            raise SoundbankError("Could not find ID %i within soundbank" % (wid))

        segids = []

        for obj in self.objects.objects:
            if obj.type == SBObject.TYPE_MUSIC_SEGMENT:
                hasTrack = [trackid for trackid in trackids if trackid in obj.obj.child_ids]

                if hasTrack:
                    segids.append(obj.id)

        if not segids:
            raise SoundbankError("%i has no music segments" % (wid))

        playlist_ids = []

        for obj in self.objects.objects:
            if obj.type == SBObject.TYPE_MUSIC_PLAYLIST:
                hasSegment = [segid for segid in segids if segid in obj.obj.segment_ids]

                if hasSegment:
                    playlist_ids.append(("'%i'" % (obj.id)))

        if not playlist_ids:
            raise SoundbankError("%i has no music playlists" % (wid))

        print "[*] Playlists found: %i" % len(playlist_ids)
        print "[*] Playlists IDs: %s" % (", ".join(playlist_ids))
        print

    def export_playlist(self, playlist_id):
        if playlist_id < 1 or playlist_id > 0xFFFFFFFF:
            raise SoundbankError("Invalid playlist ID")

        playlist = None

        for obj in self.objects.objects:
            if obj.type == SBObject.TYPE_MUSIC_PLAYLIST:
                if obj.id == playlist_id:
                    playlist = obj
                    break

        if playlist is None:
            raise SoundbankError("Playlist %i not found within soundbank" % (playlist_id))

        playlist_file = "%i_playlist.ini" % (playlist_id)

        with open(playlist_file, "wt") as f:
            playlist.obj.export(self.objects.objects).write(f)

    def reimport_playlist(self, playlist_id):
        if playlist_id < 1 or playlist_id > 0xFFFFFFFF:
            raise SoundbankError("Invalid playlist ID")

        playlist = None
        playlistIdx = None
        playlistSegids = None

        for (i, obj) in enumerate(self.objects.objects):
            if obj.type == SBObject.TYPE_MUSIC_PLAYLIST:
                if obj.id == playlist_id:
                    playlist = obj
                    playlistIdx = i
                    playlistSegids = tuple(playlist.obj.segment_ids)
                    break

        if playlist is None:
            raise SoundbankError("Playlist %i not found within soundbank" % (playlist_id))

        playlist_file = "%i_playlist.ini" % (playlist_id)

        moveSegments = playlist.obj.reimport(playlist_file)
        playlist.calculate_length()

        if moveSegments:
            baseSegment = None

            for obj in self.objects.objects:
                if obj.type == SBObject.TYPE_MUSIC_SEGMENT:
                    if obj.id in playlistSegids and obj.id not in moveSegments:
                        baseSegment = obj
                        break

            if baseSegment is None:
                raise SoundbankError("No base segment within playlist")

            for segid in moveSegments:
                segment = None

                for (i, obj) in enumerate(self.objects.objects):
                    if obj.type == SBObject.TYPE_MUSIC_SEGMENT:
                        if obj.id == segid:
                            segment = obj
                            segmentIdx = i
                            break

                if segment is None:
                    raise SoundbankError("Failed to find playlist's music segment within soundbank")

                if segmentIdx < playlistIdx:
                    continue

                _segment = deepcopy(baseSegment)
                _segment.id = segment.id
                _segment.obj.children = segment.obj.children
                _segment.obj.child_ids = segment.obj.child_ids
                _segment.obj.unk_double_1 = segment.obj.unk_double_1
                _segment.obj.unk_field64_1 = segment.obj.unk_field64_1
                _segment.obj.unk_field64_2 = segment.obj.unk_field64_2
                _segment.obj.time_length = segment.obj.time_length
                _segment.obj.time_length_next = segment.obj.time_length_next
                _segment.calculate_length()
                segment = _segment

                tracks = [i for (i, obj) in enumerate(self.objects.objects) if obj.type == SBObject.TYPE_MUSIC_TRACK and obj.id in segment.child_ids]

                if not tracks:
                    raise SoundbankError("Failed to find tracks for playlist's music segment within soundbank")

                for trackIdx in tracks:
                    track = self.objects.objects[trackIdx]
                    del self.objects.objects[trackIdx]
                    self.objects.objects.insert(playlistIdx, track)

                    playlistIdx += 1

                del self.objects.objects[segmentIdx]

                self.objects.objects.insert(playlistIdx, segment)

                playlistIdx += 1

        self.objects.calculate_length()

    def dump_sounds(self, folder):
        try:
            os.makedirs(folder)
        except OSError:
            pass

        for data_info in self.data_index.data_info:
            with open(folder + "\\" + str(data_info.id) + ".wem", "wb") as dump:
                dump.write(data_info.data)

    def build_bnk(self):
        if self.isInit:
            raise SoundbankError("Rebuilding Init.bnk is not yet supported")

        try:
            self.file = FileWrite(self._file + ".rebuilt")
        except (OSError, IOError):
            raise SoundbankError("Could not create new soundbank")

        self.file.write_uchar(self.header.head)
        self.file.write_uint32(self.header.length)
        self.file.write_uint32(self.header.version)
        self.file.write_uint32(self.header.id)
        self.file.write_uint32(self.header.unk_field32_1)
        self.file.write_uint32(self.header.unk_field32_2)

        if self.header.unk_data is not None:
            self.file.write_uchar(self.header.unk_data)

        #if self.unk_chunk:
            #self.file.write_uchar(self.unk_chunk)

        if self.data_index:
            self.data_index.calculate_offsets()

            self.file.write_uchar(self.data_index.head)
            self.file.write_uint32(self.data_index.length)

            for data_info in self.data_index.data_info:
                self.file.write_uint32(data_info.id)
                self.file.write_uint32(data_info.offset)
                self.file.write_uint32(data_info.size)

        if self.data:
            self.file.write_uchar(self.data.head)
            self.file.write_uint32(self.data_index.get_total_size())

            self.data.offset = self.file.where()

            for data_info in self.data_index.data_info:
                self.file.write_uchar(data_info.data)

        self.file.write_uchar(self.objects.head)
        self.file.write_uint32(self.objects.length)
        self.file.write_uint32(self.objects.quantity)

        for obj in self.objects.objects:
            self.file.write_uchar(obj.type)
            self.file.write_uint32(obj.length)
            self.file.write_uint32(obj.id)

            if obj.type == SBObject.TYPE_SOUND:
                if obj.obj.include_type == SBSoundObject.SOUND_EMBEDDED and self.data_index:
                    try:
                        offset = self.data.offset + self.data_index.get_offset(obj.obj.audio_id)
                        size = self.data_index.get_size(obj.obj.audio_id)
                    except TypeError:
                        pass
                    else:
                        obj.obj.offset = offset
                        obj.obj.size = size

            self.file.write_uchar(str(obj.obj))

        if self.stid:
            self.file.write_uchar(self.stid.head)
            self.file.write_uint32(self.stid.length)
            self.file.write_uint32(self.stid.unk_field32_1)
            self.file.write_uint32(self.stid.quantity)
            self.file.write_uchar(self.stid.remaining)

        del self.file

def show_usage(path):
    path = os.path.basename(path)

    print "Usage: %s <BNK> <FOLDER>" % (path)
    print "Usage: %s --music <BNK> <WEM>" % (path)
    print "Usage: %s --add-new-music <BNK> <WEM>" % (path)
    print "Usage: %s --playlist-id-from-track <BNK> <TRACK ID>" % (path)
    print "Usage: %s --export-playlist <BNK> <PLAYLIST ID>" % (path)
    print "Usage: %s --reimport-playlist <BNK> <PLAYLIST ID>" % (path)
    print "Usage: %s --dump-sounds <BNK> <FOLDER>" % (path)
    print "Usage: %s --debug <BNK>" % (path)
    print "Usage: %s --debug-event <BNK> <EVENT ID>" % (path)
    print "Usage: %s --debug-sound <BNK> <SOUND ID>" % (path)
    print "Usage: %s --debug-object <BNK> <OBJECT ID>" % (path)
    print "Usage: %s --debug-owner <BNK> <AUDIO ID>" % (path)

    sys.exit(1)

def main(argc, argv):
    if argc < 2:
        show_usage(argv[0])

    mode = None
    bnk = None
    wem = None
    wid = None
    folder = None
    playlist_id = None
    debug_id = None

    argv = [arg.strip() for arg in argv]

    if argv[1] == "--music":
        if argc != 4:
            show_usage(argv[0])

        mode = Soundbank.MODE_BUILD_MUSIC
        bnk = argv[2]
        wem = argv[3]
    elif argv[1] == "--add-new-music":
        if argc != 4:
            show_usage(argv[0])
        
        mode = Soundbank.MODE_ADD_NEW_MUSIC
        bnk = argv[2]
        wem = argv[3]
    elif argv[1] == "--playlist-id-from-track":
        if argc != 4:
            show_usage(argv[0])

        mode = Soundbank.MODE_PLAYLIST_ID
        bnk = argv[2]
        wid = argv[3]
    elif argv[1] == "--export-playlist":
        if argc != 4:
            show_usage(argv[0])

        mode = Soundbank.MODE_EXPORT_PLAYLIST
        bnk = argv[2]
        playlist_id = argv[3]
    elif argv[1] == "--reimport-playlist":
        if argc != 4:
            show_usage(argv[0])
        
        mode = Soundbank.MODE_REIMPORT_PLAYLIST
        bnk = argv[2]
        playlist_id = argv[3]
    elif argv[1] == "--dump-sounds":
        if argc != 4:
            show_usage(argv[0])

        mode = Soundbank.MODE_DUMP_SOUNDS
        bnk = argv[2]
        folder = argv[3]
    elif argv[1] == "--debug":
        if argc != 3:
            show_usage(argv[0])

        mode = Soundbank.MODE_DEBUG
        bnk = argv[2]
    elif argv[1] == "--debug-event":
        if argc != 4:
            show_usage(argv[0])

        mode = Soundbank.MODE_DEBUG_EVENT
        bnk = argv[2]
        debug_id = argv[3]
    elif argv[1] == "--debug-sound":
        if argc != 4:
            show_usage(argv[0])

        mode = Soundbank.MODE_DEBUG_SOUND
        bnk = argv[2]
        debug_id = argv[3]
    elif argv[1] == "--debug-object":
        if argc != 4:
            show_usage(argv[0])

        mode = Soundbank.MODE_DEBUG_OBJECT
        bnk = argv[2]
        debug_id = argv[3]
    elif argv[1] == "--debug-owner":
        if argc != 4:
            show_usage(argv[0])

        mode = Soundbank.MODE_DEBUG_OWNER
        bnk = argv[2]
        debug_id = argv[3]
    else:
        if argc != 3:
            show_usage(argv[0])

        mode = Soundbank.MODE_BUILD
        bnk = argv[1]
        folder = argv[2]

    if not bnk:
        raise SyntaxError("Invalid bnk file")

    if not wem and wem is not None:
        raise SyntaxError("Invalid wem file")

    if wid is not None:
        try:
            wid = int(wid)
        except ValueError:
            raise SyntaxError("ID is not an integer")

    if not folder and folder is not None:
        raise SyntaxError("Invalid folder")

    if playlist_id is not None:
        try:
            playlist_id = int(playlist_id)
        except ValueError:
            raise SyntaxError("Playlist ID is not an integer")

    if debug_id is not None:
        try:
            debug_id = int(debug_id)
        except ValueError:
            raise SyntaxError("Debug ID is not an integer")

    sys.stdout.write("Reading soundbank...")
    soundbank = Soundbank(bnk)
    soundbank.read()
    sys.stdout.write("Done!\n")

    if mode == Soundbank.MODE_DEBUG:
        print
        soundbank.debug()
    elif mode == Soundbank.MODE_DEBUG_EVENT:
        print
        soundbank.debug_event(debug_id)
    elif mode == Soundbank.MODE_DEBUG_SOUND:
        print
        soundbank.debug_sound(debug_id)
    elif mode == Soundbank.MODE_DEBUG_OBJECT:
        print
        soundbank.debug_object(debug_id)
    elif mode == Soundbank.MODE_DEBUG_OWNER:
        print
        soundbank.debug_owner(debug_id)
    elif mode == Soundbank.MODE_BUILD_MUSIC:
        sys.stdout.write("Rebuilding music...")
        soundbank.rebuild_music(wem)
        soundbank.build_bnk()
        sys.stdout.write("Done!\n")
    elif mode == Soundbank.MODE_ADD_NEW_MUSIC:
        sys.stdout.write("Adding new music...")
        objID = soundbank.add_music(wem)
        soundbank.build_bnk()
        sys.stdout.write("Done!\n")
        print "[*] Music segment object ID: '%i'" % (objID)
    elif mode == Soundbank.MODE_PLAYLIST_ID:
        print
        soundbank.get_playlist_ids(wid)
    elif mode == Soundbank.MODE_EXPORT_PLAYLIST:
        sys.stdout.write("Exporting playlist...")
        soundbank.export_playlist(playlist_id)
        sys.stdout.write("Done!\n")
    elif mode == Soundbank.MODE_REIMPORT_PLAYLIST:
        sys.stdout.write("Reimporting playlist...")
        soundbank.reimport_playlist(playlist_id)
        soundbank.build_bnk()
        sys.stdout.write("Done!\n")
    elif mode == Soundbank.MODE_DUMP_SOUNDS:
        sys.stdout.write("Dumping sounds...")
        soundbank.dump_sounds(folder)
        sys.stdout.write("Done!\n")
    else:
        if not soundbank.data_index:
            raise SoundbankError("Soundbank does not contains embedded files")

        sys.stdout.write("Rebuilding sounds...")
        soundbank.read_wems(folder)
        soundbank.rebuild_data()
        soundbank.build_bnk()
        sys.stdout.write("Done!\n")

    del soundbank

    sys.exit(0)

if __name__ == "__main__":
    main(len(sys.argv), sys.argv)

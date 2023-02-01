import collections
import operator
import time
from ..base.message_parser_base import MessageParserBase
from ...framework.utils import helper
from ...framework.context import APP_CONTEXT
from .rtk330l_packet_parser import (
    match_command_handler, common_continuous_parser, other_output_parser)

MSG_HEADER = [0x55, 0x55]
PACKET_TYPE_INDEX = 2

INPUT_PACKETS = ['pG', 'uC', 'uP', 'uA', 'uB',
                 'sC', 'rD',
                 'gC', 'gA', 'gB', 'gP', 'gV', 'cA'
                 '\x15\x15', '\x00\x00',
                 'JI', 'JA', 'WA', 'CS', 'JS', 'JG'
                 'RE', 'WE', 'UE', 'LE', 'SR',
                 'SF', 'RF', 'WF', 'GF', 'RC', 'WC', 'PK', 'CH']
OTHER_OUTPUT_PACKETS = ['s1', 's2', 'iN', 'd1', 'gN', 'd2', 'sT', 'o1']


class ANALYSIS_STATUS:
    INIT = 0
    FOUND_HEADER = 1
    FOUND_PAYLOAD_LENGTH = 2
    FOUND_PACKET_TYPE = 3
    CRC_PASSED = 4


class OpenDevicePacket:
    _payload_length = 0
    _raw_data_bytes = []
    _payload_bytes = []
    _packet_type = None

    def __init__(self):
        self._payload_length = 0
        self._raw_data_bytes = []
        self._payload_bytes = []
        self._packet_type = None

    @property
    def payload_length(self):
        return self._payload_length

    @property
    def packet_type(self):
        return self._packet_type

    @property
    def payload(self):
        return self._raw_data_bytes[5: self._payload_length]

    @property
    def raw(self):
        return self._raw_data_bytes

    def accept_to_header(self, bytes_data):
        self._raw_data_bytes.extend(bytes_data)

    def accept_to_length(self, byte_data):
        self._payload_length = byte_data+5
        self._raw_data_bytes.append(byte_data)

    def accept_to_packet_type(self, bytes_data):
        self._packet_type = bytes(bytes_data).decode()
        self._raw_data_bytes.extend(bytes_data)

    def accept_to_payload(self, byte_data):
        self._raw_data_bytes.append(byte_data)

    def check_crc(self):
        crc_calculate_value = helper.calc_crc(self._raw_data_bytes[2:-2])
        crc_value = self._raw_data_bytes[-2:]
        return crc_calculate_value == crc_value

class UartMessageParser(MessageParserBase):
    def __init__(self, configuration):
        super(UartMessageParser, self).__init__(configuration)
        self.frame = []
        self.payload_len_idx = 5
        self.sync_pattern = collections.deque(2*[0], 4)
        self.find_header = False
        self.payload_len = 0
        self.userPacketsTypeList = configuration['userPacketsTypeList']
        # command,continuous_message
        self.sync_state = 0
    def set_run_command(self, command):
        pass

    def analyse(self, data):
        for data_block in data:
            if self.find_header:
                self.frame.append(data_block)
                if self.payload_len_idx == len(self.frame):
                    self.payload_len = data_block

                elif 5 + self.payload_len + 2 == len(self.frame):
                    packet_type = ''.join(
                        ["%c" % x for x in self.frame[PACKET_TYPE_INDEX:4]])
                    # self.find_header = False
                    #print('len = ',self.payload_len,packet_type)
                    result = helper.calc_crc(self.frame[2:-2])
                    if result[0] == self.frame[-2] and result[1] == self.frame[-1]:
                        # if packet_type == 'gB':
                        #     print('parsed')
                        # find a whole frame
                        # self._parse_frame(self.frame, self.payload_len)
                        self._parse_message(
                            packet_type, self.payload_len, self.frame)
                    else:
                        APP_CONTEXT.get_logger().logger.info(
                            "crc check error! packet_type:{0}".format(packet_type))
                        # print('crc',packet_type,'calc',result,'expect',self.frame[-2:])
                        #print(self.frame)
                        self.emit('crc_failure', packet_type=packet_type,
                                event_time=time.time())
                        input_packet_config = next(
                            (x for x in self.properties['userMessages']['inputPackets']
                            if x['name'] == packet_type), None)
                        if input_packet_config:
                            self.emit('command',
                                    packet_type=packet_type,
                                    data=[],
                                    error=True,
                                    raw=self.frame)

                    self.find_header = False
                    self.payload_len = 0
                    self.sync_pattern = collections.deque(2*[0], 4)
                    self.frame=[]
            else:
                self.sync_pattern.append(data_block)
                packet_type = None
                if len(self.sync_pattern) == 4:
                    packet_type = ''.join(
                        ["%c" % x for x in list(self.sync_pattern)[2:4]])
                if operator.eq(list(self.sync_pattern)[0:2], MSG_HEADER) and packet_type in self.userPacketsTypeList:
                    self.frame = list(self.sync_pattern)[:]  # header_tp.copy()
                    self.find_header = True
                    #print(packet_type)

    def _parse_message(self, packet_type, payload_len, frame):
        payload = frame[5:payload_len+5]
        # parse interactive commands
        is_interactive_cmd = INPUT_PACKETS.__contains__(packet_type)
        if is_interactive_cmd:
            self._parse_input_packet(packet_type, payload, frame)
        else:
            # consider as output packet, parse output Messages
            self._parse_output_packet(packet_type, payload)

    def _parse_input_packet(self, packet_type, payload, frame):
        payload_parser = match_command_handler(packet_type)
        if payload_parser:
            data, error = payload_parser(
                payload, self.properties['userConfiguration'])

            self.emit('command',
                      packet_type=packet_type,
                      data=data,
                      error=error,
                      raw=frame)
        else:
            print('[Warning] Unsupported command {0}'.format(
                packet_type.encode()))

    def _parse_output_packet(self, packet_type, payload):
        # check if it is the valid out packet
        payload_parser = None
        is_other_output_packet = OTHER_OUTPUT_PACKETS.__contains__(packet_type)
        if is_other_output_packet:
            payload_parser = other_output_parser
            data = payload_parser(payload)
            return

        payload_parser = common_continuous_parser

        output_packet_config = next(
            (x for x in self.properties['userMessages']['outputPackets']
                if x['name'] == packet_type), None)
        data = payload_parser(payload, output_packet_config)

        if not data:
            # APP_CONTEXT.get_logger().logger.info(
            #     'Cannot parse packet type {0}. It may caused by firmware upgrade'.format(packet_type))
            #pass
            return

        self.emit('continuous_message',
                  packet_type=packet_type,
                  data=data,
                  event_time=time.time())

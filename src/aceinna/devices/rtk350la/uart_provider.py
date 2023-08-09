import time
import serial
import struct
from ..decorator import with_device_message
from ..base.rtk_provider_base import RTKProviderBase
from ..upgrade_workers import (
    FirmwareUpgradeWorker,
    SDK9100UpgradeWorker,
    UPGRADE_EVENT,
    UPGRADE_GROUP
)
from ...framework.utils import (
    helper
)
from ...framework.utils.print import print_red
from ..parsers.rtk330l_field_parser import encode_value, get_value_len

class Provider(RTKProviderBase):
    '''
    RTK350LA UART provider
    '''

    def __init__(self, communicator, *args):
        super(Provider, self).__init__(communicator)
        self.type = 'RTK350LA'
        self.bootloader_baudrate = 460800
        self.config_file_name = 'RTK350LA.json'
        self.device_category = 'RTK350LA'
        self.port_index_define = {
            'user': 0,
            'rtcm': -2,
            'debug': 1,
        }


    @with_device_message
    def get_params(self, *args):  # pylint: disable=unused-argument
        '''
        Get all parameters
        '''
        has_error = False
        parameter_values = []

        if self.app_info['app_name'] == 'RTK_INS':
            conf_parameters = self.properties['userConfiguration']
            conf_parameters_len = len(conf_parameters)-1
            step = 10

            for i in range(2, conf_parameters_len, step):
                start_byte = i
                end_byte = i+step-1 if i+step < conf_parameters_len else conf_parameters_len
                time.sleep(0.2)

                para_num = end_byte - start_byte + 1
                message_bytes = []
                message_bytes.append(para_num)
                for i in range(start_byte, end_byte+1):
                    message_bytes.append(i)
                command_line = helper.build_packet(
                    'gB', message_bytes)
                result = yield self._message_center.build(command=command_line, timeout=20)
                if result['error']:
                    has_error = True
                    break

                parameter_values.extend(result['data'])
        else:
            command_line = helper.build_input_packet('gA')
            result = yield self._message_center.build(command=command_line, timeout=5)
            if result['error']:
                has_error = True

            parameter_values = result['data']

        if not has_error:
            self.parameters = parameter_values
            yield {
                'packetType': 'inputParams',
                'data': parameter_values
            }

        yield {
            'packetType': 'error',
            'data': 'No Response'
        }


    @with_device_message
    def set_params(self, params, *args):  # pylint: disable=unused-argument
        '''
        Update paramters value
        '''
        input_parameters = self.properties['userConfiguration']
        grouped_parameters = {}

        for parameter in params:
            exist_parameter = next(
                (x for x in input_parameters if x['paramId'] == parameter['paramId']), None)

            if exist_parameter:
                has_group = grouped_parameters.__contains__(
                    exist_parameter['category'])
                if not has_group:
                    grouped_parameters[exist_parameter['category']] = []

                current_group = grouped_parameters[exist_parameter['category']]

                current_group.append(
                    {'paramId': parameter['paramId'], 'value': parameter['value'], 'type': exist_parameter['type']})

        for group in grouped_parameters.values():
            message_bytes = []
            for parameter in group:
                message_bytes.extend(
                    encode_value('int8', parameter['paramId'])
                )
                
                message_bytes.extend(
                    encode_value('uint8', get_value_len(parameter['type']))
                )

                message_bytes.extend(
                    encode_value(parameter['type'], parameter['value'])
                )
                # print('parameter type {0}, value {1}'.format(
                #     parameter['type'], parameter['value']))
            # result = self.set_param(parameter)
            command_line = helper.build_packet(
                'uB', message_bytes)

            result = yield self._message_center.build(command=command_line)

            packet_type = result['packet_type']
            data = result['data']

            if packet_type == 'error':
                yield {
                    'packetType': 'error',
                    'data': {
                        'error': data
                    }
                }
                break

            if data > 0:
                yield {
                    'packetType': 'error',
                    'data': {
                        'error': data
                    }
                }
                break

        yield {
            'packetType': 'success',
            'data': {
                'error': 0
            }
        }

    def thread_debug_port_receiver(self, *args, **kwargs):
        if self.debug_logf is None:
            return

        # log data
        while True:
            if self.is_upgrading:
                time.sleep(0.1)
                continue
            try:
                data = bytearray(self.debug_serial_port.read_all())
            except Exception as e:
                print_red('DEBUG PORT Thread error: {0}'.format(e))
                return  # exit thread receiver
            if data and len(data) > 0:
                self.debug_logf.write(data)
            else:
                time.sleep(0.001)

    def thread_rtcm_port_receiver(self, *args, **kwargs):
        if self.rtcm_logf is None:
            return
        while True:
            if self.is_upgrading:
                time.sleep(0.1)
                continue
            try:
                data = bytearray(self.rtcm_serial_port.read_all())
            except Exception as e:
                print_red('RTCM PORT Thread error: {0}'.format(e))
                return  # exit thread receiver
            if len(data):
                self.rtcm_logf.write(data)
            else:
                time.sleep(0.001)

    def before_write_content(self, core, content_len):
        self.communicator.serial_port.baudrate = self.bootloader_baudrate
        self.communicator.serial_port.reset_input_buffer()

        message_bytes = [ord('C'), ord(core)]
        message_bytes.extend(struct.pack('>I', content_len))
        command_line = helper.build_packet('CS', message_bytes)
        for i in range(5):
            self.communicator.write(command_line, True)
            time.sleep(1)
            result = helper.read_untils_have_data(
                self.communicator, 'CS', 200, 100)
            if result:
                break

        if not result:
            raise Exception('Cannot run set core command')

    def firmware_write_command_generator(self, data_len, current, data):
        command_WA = 'WA'
        message_bytes = []
        message_bytes.extend(struct.pack('>I', current))
        message_bytes.extend(struct.pack('B', data_len))
        message_bytes.extend(data)
        return helper.build_packet(command_WA, message_bytes)

    # override
    def build_worker(self, rule, content):
        pass

    # command list
    # use base methods

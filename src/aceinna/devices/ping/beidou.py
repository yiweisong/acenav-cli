import sys
import time
import struct
from ...framework.utils import (helper, resource)
from ...framework.context import APP_CONTEXT

pG = 'pG'
gV = 'gV'


def _run_command(communicator, command, size, retry):
    command_line = helper.build_input_packet(command)
    communicator.write(command_line)
    time.sleep(0.1)

    data_buffer = helper.read_untils_have_data(
        communicator, command, size, retry)

    return data_buffer


def _format_string(data_buffer):
    parsed = bytearray(data_buffer) if data_buffer and len(
        data_buffer) > 0 else None

    formatted = ''
    if parsed is not None:
        try:
            if sys.version_info < (3, 0):
                formatted = str(struct.pack(
                    '{0}B'.format(len(parsed)), *parsed))
            else:
                formatted = str(struct.pack(
                    '{0}B'.format(len(parsed)), *parsed), 'utf-8')
        except UnicodeDecodeError:
            APP_CONTEXT.get_logger().logger.error('Parse data as string failed')
            formatted = ''

    return formatted


def _need_check(limit_type, device_type):
    if limit_type is None:
        return True

    return limit_type == device_type


def run_command_as_string(communicator, command, size=1000, retry=10):
    ''' Run command and parse result as string
    '''
    data_buffer = _run_command(communicator, command, size, retry)      #TODO: step6
    result = _format_string(data_buffer)

    return result


def ping(communicator, *args):
    '''beidou Ping
    '''
    filter_device_type = args[0]

    cmd_device_info_text = run_command_as_string(communicator, pG)
    if cmd_device_info_text.find(',') > -1:
        device_info_text = cmd_device_info_text.replace(',', ' ')
    else:
        device_info_text = cmd_device_info_text

    cmd_app_info_text = run_command_as_string(communicator, gV)
    if cmd_app_info_text.find(',') > -1:
        app_info_text = cmd_app_info_text.replace(',', ' ')
    else:
        app_info_text = cmd_app_info_text

    # Prevent action. Get app info again,
    # if cannot retrieve any info at the first time of ping. Should find the root cause.
    if app_info_text == '':
        app_info_text = run_command_as_string(communicator, gV)


    # a bad check, to distinguish beidou
    if _need_check(filter_device_type, 'beidou') and device_info_text.find('beidou') > -1  and device_info_text.find('OpenRTK') == -1 :
        return {
            'device_type': 'beidou',
            'device_info': device_info_text,
            'app_info': app_info_text
        }

    if _need_check(filter_device_type, 'INS') and device_info_text.find('INS401') > -1:
        return {
            'device_type': 'INS401',
            'device_info': device_info_text,
            'app_info': app_info_text
        }

    return None

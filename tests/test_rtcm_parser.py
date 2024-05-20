from io import BufferedWriter
import sys
from typing import List

try:
    from aceinna.core.gnss import RTCMParser
except:
    sys.path.append('./src')
    from aceinna.core.gnss import RTCMParser

rtcm_base_file_path = '/Users/songyiwei/Desktop/debug/20240424/ins502_log_2302500001_20240423_145009/rtcm_base_2024_04_23_14_50_44.bin'

rtcm_base_file_filtered_path = '/Users/songyiwei/Desktop/debug/20240424/ins502_log_2302500001_20240423_145009/rtcm_base_2024_04_23_14_50_44_filtered.bin'

def handle_parsed(file_writer: BufferedWriter, packets: List[int]):
    for packet in packets:
        file_writer.write(bytes(packet))

def test_rtcm_parser():
    file_writer = open(rtcm_base_file_filtered_path, 'wb')
    file_reader = open(rtcm_base_file_path, 'rb')

    parser = RTCMParser()
    parser.set_ignore_packets([1124])
    parser.on('parsed', lambda data:handle_parsed(file_writer, data))

    while True:
        data = file_reader.read(1024)
        if not data:
            break

        parser.receive(data)

    print('Conveted!')

if __name__ == '__main__':
    test_rtcm_parser()
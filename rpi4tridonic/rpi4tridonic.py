import signal
import time
import sys
import socket
import threading
import logging
import pigpio

logging.basicConfig(level=logging.DEBUG)

VERSION = 2.1
#GPIO line used
GPIO_TX_LINE=4
GPIO_RX_LINE=5

#TCP server
DEFAULT_NET_ADDRESS = "192.168.0.254"	# Standard loopback interface address (localhost)
DEFAULT_NET_PORT = 1234		# Port to listen on (non-privileged ports are > 1023)

arg = sys.argv
if len(arg) >= 2:
    DEFAULT_NET_ADDRESS = arg[1]
if len(arg) == 3:
    DEFAULT_NET_PORT = int(arg[2])

#DALI Timings
BIT_TIMING_MIN = 749990 / 1000 # 749.99 uS
BIT_TIMING_NOR = 416    # 416.00 uS
BIT_TIMING_MAX = 916660 / 1000 # 916.66 uS

TIME_OUT_IDLE = int((2 * BIT_TIMING_MIN)/1000) # mS

TRANSMITTING = False
DALI_ANSWER_DELAY = 0.05 # in sec
DALI_BUFFER_IN = []

# lgpio variables
previous_edge_tick = 0
previous_edge_level = 0
delta_edge_tick = 0
count_edge = 0
out = ''

def tridonic_crc(dali_frame):
    crc = 0x00
    if not isinstance(dali_frame, bytes):
        return(False)
    data_len = len(dali_frame)
    if 4 <= data_len <=5:
        for i in range(4):
            crc = crc ^ dali_frame[i]
    else:
        return(False)
    if data_len == 4:
        return(crc)
    if dali_frame[4] == crc:
        return(True)
    return(False)

def tx_to_tcp(buffer,status):
    global conn
    buffer_to_tcp = []
    if status == 'Error':
	    buffer_to_tcp = [0x67,0x00,0x00,0x03] # 03-DALI recive error; 02-Bus shot circuit
	    status = '\x1b[31;20m Error'
    elif status == 'Answer Test':
	    buffer_to_tcp = [0x60,0x00,0x12,0x03] # ANSWER_TEST_CONNECTION
    elif status == 'No Data':
	    buffer_to_tcp = [0x61,0x00,0x00,0x00] # ANSWER_NO_DATA
    elif status == 'OK TCP':
	    buffer_to_tcp = [0x60,0x00,0x00,0x00] # ANSWER_OK
    elif status == 'Patch':
	    buffer_to_tcp = [0x62,0x00,0x00,0xFF] # Answer 0xFF Patch for LTECH
    elif status == 'Answer' or status == 'Broadcast':
	    if len(buffer) == 1:
		    buffer_to_tcp.append(0x62)
		    buffer_to_tcp.append(0x00)
		    buffer_to_tcp.append(0x00)
		    buffer_to_tcp.append(buffer[0])
	    elif len(buffer) == 2:
		    buffer_to_tcp.append(0x63)
		    buffer_to_tcp.append(0x00)
		    buffer_to_tcp.append(buffer[0])
		    buffer_to_tcp.append(buffer[1])
	    elif len(buffer) == 3:
		    buffer_to_tcp.append(0x64)
		    buffer_to_tcp.append(buffer[0])
		    buffer_to_tcp.append(buffer[1])
		    buffer_to_tcp.append(buffer[2])
    buffer_to_tcp.append(tridonic_crc(bytes(buffer_to_tcp)))
    logging.info('\x1b[32;20m'+'tcp->client: '+str(status)+' - '+str(bytes(buffer_to_tcp).hex(' '))+'\x1b[0m')
    try:
	    conn.sendall(bytes(buffer_to_tcp))
    except:
	    return

def answer_delay():
    tx_to_tcp([],'No Data')

def timeout_dali(f):
    global tt
    if f == 'Start':
	    tt = threading.Timer(DALI_ANSWER_DELAY, answer_delay)
	    tt.start()
    elif f == 'Stop':
	    try:
		    tt.cancel()
	    except:
		    pass

def rx_from_tcp(data_frame):
    logging.info('\x1b[32;20m'+'client->TCP: '+str(data_frame.hex(' '))+'\x1b[0m')
    frame_to_dali = []
    if len(data_frame) != 5:
	    if len(data_frame) / 2 == 5:
		    logging.info('\x1b[31;20m double \x1b[0m')
	    else:
		    logging.info('\x1b[31;20m small \x1b[0m')
		    return
    if not tridonic_crc(data_frame):
	    logging.info('\x1b[31;20mcrc error \x1b[0m')
	    return
    if data_frame[0] == 0xC0:		#REQUEST_TEST_CONNECTION:
	    tx_to_tcp([],'Answer Test')
	    return
    if data_frame[0] == 0x83:
	    frame_to_dali.append(data_frame[2])
	    frame_to_dali.append(data_frame[3])
    if data_frame[0] == 0x84:
	    frame_to_dali.append(data_frame[1])
	    frame_to_dali.append(data_frame[2])
	    frame_to_dali.append(data_frame[3])
    tx_to_dali_pigpio(frame_to_dali)


def dali_tx_wave(bytes_tx):
    pulses = []
    pulses.append(pigpio.pulse(0, 1<<GPIO_TX_LINE, BIT_TIMING_NOR))	# Start
    pulses.append(pigpio.pulse(1<<GPIO_TX_LINE, 0, BIT_TIMING_NOR))	# bit = 1
    for d in bytes_tx:
	    for i in list('{0:08b}'.format(d)):
		    if int(i) == 1:
			    pulses.append(pigpio.pulse(0, 1<<GPIO_TX_LINE, BIT_TIMING_NOR))
			    pulses.append(pigpio.pulse(1<<GPIO_TX_LINE, 0, BIT_TIMING_NOR))
		    else:
			    pulses.append(pigpio.pulse(1<<GPIO_TX_LINE, 0, BIT_TIMING_NOR))
			    pulses.append(pigpio.pulse(0, 1<<GPIO_TX_LINE, BIT_TIMING_NOR))
    pulses.append(pigpio.pulse(1<<GPIO_TX_LINE, 0, BIT_TIMING_NOR*2))	# Stop IDLE
    return pulses

def tx_to_dali_pigpio(data_dali):
    global TRANSMITTING
    logging.debug('\x1b[33;20m'+'server->DALI: '+bytes(data_dali).hex(' ')+'\x1b[0m')
    if len(data_dali) > 0:
	    pi.wave_clear()
	    pi.wave_add_generic(dali_tx_wave(data_dali))
	    wid = pi.wave_create()
	    pi.wave_send_once(wid)
	    pi.wave_clear()
	    TRANSMITTING = True	# Start transmitting

def cbf_pigpio(gpio, level, current_edge_tick):
    global previous_edge_tick
    global previous_edge_level
    global count_edge
    global out
    global TRANSMITTING
    global DALI_BUFFER_IN

    if gpio != GPIO_RX_LINE:
	    return

    if count_edge == 0:
	    pi.set_watchdog(GPIO_RX_LINE, 1) # Start WatchDog

    if pi.wave_tx_busy(): # echo drop transmitting
	    return

    delta_edge_tick = current_edge_tick - previous_edge_tick
    current_edge_level = (0 if level==1 else 1)

    if level == 2:
	    pi.set_watchdog(GPIO_RX_LINE, 0) # Stop WatchDog
	    buff_len = len(DALI_BUFFER_IN)
	    logging.debug('\x1b[33;20m'+'DALI->server: '+bytes(DALI_BUFFER_IN).hex(' ')+' /'+str(count_edge)+'\x1b[0m')

	    if TRANSMITTING and buff_len == 0:	# start timeout for answer
		    timeout_dali('Start')

	    if buff_len != 0:
		    if TRANSMITTING:
			    status = "Answer"
		    else:
			    status = "Broadcast"
		    TRANSMITTING = False
		    tx_to_tcp(DALI_BUFFER_IN,status)

	    previous_edge_tick = current_edge_tick
	    delta_edge_tick = 0
	    count_edge = 0
	    out = ''
	    DALI_BUFFER_IN = []
	    return

    if BIT_TIMING_MIN <= delta_edge_tick <= BIT_TIMING_MAX:
	    count_edge += 2	# if bit 1->0 or 0->1
    else:
	    count_edge += 1	# if bit 1->1 or 0->0

    if TRANSMITTING and count_edge >= 4:	#stop timeout for answer
	    timeout_dali('Stop')

    if count_edge > 2 and (count_edge % 2) == 0:
	    if previous_edge_level < current_edge_level:
		    out += '1'
	    else:
		    out += '0'
	    if (count_edge - 2) % 16 == 0:
		    DALI_BUFFER_IN.append(int(out,2))
		    out = ''
    previous_edge_tick = current_edge_tick
    previous_edge_level = current_edge_level

def client_thread(conn, addr):
    with conn:
	    logging.debug(f"[CONNECTION] Connected from {addr}")
	    while True:
		    data = conn.recv(5)
		    if not data:
			    break
		    rx_from_tcp(data)
    logging.debug(f"[CONNECTION] Disconnected from {addr}")

def request_shutdown(*args):
    logging.debug('Request to shutdown received, stopping')
    cb1.cancel()
    pi.stop()

    try:
	    conn.close()
    except:
	    pass
    try:
	    s.close()
    except:
	    pass
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    pi = pigpio.pi()
    pi.set_mode(GPIO_RX_LINE,pigpio.INPUT)
    pi.set_pull_up_down(GPIO_RX_LINE, pigpio.PUD_OFF)
    cb1 = pi.callback(GPIO_RX_LINE, pigpio.EITHER_EDGE, cbf_pigpio)
    pi.set_mode(GPIO_TX_LINE,pigpio.OUTPUT)
    pi.write(GPIO_TX_LINE,1)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
	    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	    s.bind((DEFAULT_NET_ADDRESS, DEFAULT_NET_PORT))
	    s.listen(0)
	    logging.info(f"[INFO] Ver: {VERSION}  Listening on {DEFAULT_NET_ADDRESS}:{DEFAULT_NET_PORT}")
	    while True:
		    conn, addr =  s.accept()
		    cc = False
		    for tr in threading.enumerate():
			    if tr.name == 'tcp_in':
				    cc = True
		    if cc:
			    conn.close()
			    continue
		    logging.debug(f"[INFO] Starting thread for connection {addr}")
		    thread = threading.Thread(target=client_thread, args=(conn, addr), daemon=True)
		    thread.name = 'tcp_in'
		    thread.start()

# Ver: 2.1_1no_thread
import signal
import sys
import socket
import threading
import logging
import pigpio

logging.basicConfig(level=logging.DEBUG)

#GPIO line used
GPIO_TX_LINE=4
GPIO_RX_LINE=5

#TCP server
DEFAULT_NET_ADDRESS = "127.0.0.1"	# Standard loopback interface address (localhost)
DEFAULT_NET_PORT = 55825		# Port to listen on (non-privileged ports are > 1023)

arg = sys.argv
if len(arg) >= 2:
    DEFAULT_NET_ADDRESS = arg[1]
if len(arg) == 3:
    DEFAULT_NET_PORT = int(arg[2])

#DALI Timings
BIT_TIMING_MIN = 749990 / 1000 # 749.99 uS
BIT_TIMING_NOR = 416    # 416.00 uS
BIT_TIMING_MAX = 916660 / 1000 # 916.66 uS

TIME_OUT_IDLE = 2 # mS
EDGES_FOR_STOP = 4
DALI_ANSWER_DELAY = 0.025 # in sec

TRANSMITTING = False
DALI_ANSWER_DELAY = 0.02 # in sec
DALI_BUFFER_IN = []

# lgpio variables
previous_edge_tick = 0
previous_edge_level = 0
delta_edge_tick = 0
count_edge = 0
out = ''

# onitake/daliserver emulation
DEFAULT_NET_FRAMESIZE = 4	# Network frame size
DEFAULT_NET_PROTOCOL = 2	# Network protocol number


# NetStatus
NET_STATUS_SUCCESS = 0x00	# Transfer successful, no response
NET_STATUS_RESPONSE = 0x01	# Transfer successful, response received
NET_STATUS_BROADCAST = 0x02	# Broadcast message received
NET_STATUS_ERROR = 0xFF		# Transfer error
NET_TYPE_SEND = 0x00		# type must be 0, denoting a "Send DALI command" request


def tx_to_tcp(buffer,status):
    global conn
    buffer_to_tcp = [DEFAULT_NET_PROTOCOL]

    if status == 'No Data':
	    buffer_to_tcp.append(NET_STATUS_SUCCESS)	# ANSWER_NO_DATA
	    buffer_to_tcp.append(0x00)
	    buffer_to_tcp.append(0x00)
    elif status == 'Answer':
	    buffer_to_tcp.append(NET_STATUS_RESPONSE)
	    buffer_to_tcp.append(buffer[0])
	    buffer_to_tcp.append(0x00)
    elif status == 'Broadcast':
		    buffer_to_tcp.append(NET_STATUS_BROADCAST)
		    buffer_to_tcp.extend(buffer)
    logging.debug('\x1b[32;20m'+'tcp->client: '+str(status)+' - '+str(bytes(buffer_to_tcp).hex(' '))+'\x1b[0m')
    try:
	    conn.sendall(bytes(buffer_to_tcp))
    except:
	    logging.debug('\x1b[32;20m No connection\x1b[0m')
	    return
    else:
	    logging.debug(f"[CONNECTION] Disconnected from {addr}")
	    conn.close()


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
    logging.debug('\x1b[32;20m'+'client->TCP: '+str(data_frame.hex(' '))+'\x1b[0m')
    frame_to_dali = []
    if len(data_frame) != DEFAULT_NET_FRAMESIZE:
	    logging.debug('\x1b[31;20m Error frame from TCP \x1b[0m')
	    return
    if data_frame[0] != DEFAULT_NET_PROTOCOL:
	    logging.debug('\x1b[31;20m Error protocol version \x1b[0m')
	    return
    if data_frame[1] == NET_TYPE_SEND:
	    frame_to_dali.append(data_frame[2])
	    frame_to_dali.append(data_frame[3])
	    tx_to_dali_pigpio(frame_to_dali)
    else:
	    logging.debug('\x1b[31;20m Frame with unsupported command received:'+str(hex(data_frame[1]))+'\x1b[0m')

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
	    count_edge += 1	# if bit 1->0 or 0->1
    count_edge += 1		# if bit 1->1 or 0->0

    if TRANSMITTING and count_edge >= EDGES_FOR_STOP:	#stop timeout for answer
	    timeout_dali('Stop')

    if count_edge > 2 and (count_edge % 2) == 0:
	    if previous_edge_level < current_edge_level:
		    out += '1'
	    else:
		    out += '0'
	    if len(out) == 8:
		    DALI_BUFFER_IN.append(int(out,2))
		    out = ''
    previous_edge_tick = current_edge_tick
    previous_edge_level = current_edge_level

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
	    logging.info(f"[INFO] Listening on {DEFAULT_NET_ADDRESS}:{DEFAULT_NET_PORT}")
	    while True:
		    conn, addr =  s.accept()
		    logging.debug(f"[CONNECTION] Connected from {addr}")
		    try:
			    data = conn.recv(4)
			    if not data:
				    break
			    rx_from_tcp(data)
		    except:
			    logging.debug('\x1b[32;20m No connection to client\x1b[0m')
			    pass

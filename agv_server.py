import serial.tools.list_ports
import minimalmodbus as mm
import socketio
import logging
import sys

from typing import Optional, List

log = logging.getLogger("agv_server")

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
stdout_handler.setFormatter(formatter)
log.addHandler(stdout_handler)

def find_serial_port() -> List[str]:
    """Return a list of serial ports that may have a sensor attached.
    
    The USB to UART converter on the interface board is a 
    CP2102 with no serial number programmed, attached to the RS232
    port of the sensor.
    
    That means whichever CP2102 that is recognized by the computer first
    gets the lowest COM port number.

    To fix the COM port number for each interface board, program a serial
    number to the CP2102 with "CP21xxCustomizationUtility".
    """
    ports = serial.tools.list_ports.comports()
    ports = [p[0] for p in ports if ' CP210' in p[1]]
    ports = sorted(ports)
    return ports

class AGVGuideSensor:
    def __init__(self, port: str, modbus_id: Optional[int]=None, baudrate: Optional[int]=None):
        if modbus_id is None:
            # Default Modbus ID is 1
            # The interface board talks to the sensor over RS232
            # So multiple modbus id's are redundant
            modbus_id = 1
        if baudrate is None:
            # Default baudrate is 115200
            baudrate = 115200
        # Modbus handle for the sensor. Not thread safe so make sure
        # no other process is using the serial port.
        log.info("Sensor port {} modbus_id {}".format(port, modbus_id))
        self.inst = mm.Instrument(port, modbus_id)
        self.inst.serial.baudrate = baudrate
    def value(self) -> int:
        """Return digital output of the sensor as bits packed as uint16"""
        return self.inst.read_register(0x28)
    def __del__(self):
        try:
            self.inst.serial.close()
        except Exception:
            pass

class AGVServer:
    def __init__(self, socketio_server_url: str, socketio_request_event_name: str, serial_port: str):
        self.sensor = AGVGuideSensor(serial_port)
        self.sio_client = socketio.Client()
        self.sio_client.connect(socketio_server_url)
        self.sio_client.on(socketio_request_event_name, self.sio_handler)
        self.socketio_request_event_name = socketio_request_event_name
    def sio_handler(self):
        """SocketIO handler for sensor read request.
        
        Runs in a separate thread so no problem if this crashed.
        """
        ret = {"value": self.sensor.value()}
        event_name = self.socketio_request_event_name + "Response"
        self.sio_client.emit(event_name, ret)

# Configs
socketio_server_url = "http://localhost:8080"
socketio_request_event_name = "AGVGuideSensor"

def main():
    try:
        port = find_serial_port()[0]
    except IndexError:
        log.fatal("No serial ports detected. Exiting.")
        exit(-1)
    server = AGVServer(socketio_server_url, socketio_request_event_name, port)
    log.info("AGVServer init finished")
    server.sio_client.wait()

if __name__ == "__main__":
    main()
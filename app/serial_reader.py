import serial


class SerialReader:
    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.connection = None

    def connect(self):
        self.connection = serial.Serial(self.port, self.baudrate, timeout=1)

    def read_line(self) -> str:
        if self.connection and self.connection.in_waiting:
            return self.connection.readline().decode("utf-8").strip()
        return ""

    def close(self):
        if self.connection:
            self.connection.close()

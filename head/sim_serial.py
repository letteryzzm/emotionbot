"""调试台的内存串口；不导入 pyserial，也不打开设备。"""
from head.actuators import ACTUATORS


class SimSerial:
    def __init__(self, board):
        self.board = board
        self.angles = {a.name: 90.0 for a in ACTUATORS if a.board == board}
        self.reply = ""

    def write(self, data):
        parts = data.decode().strip().split()
        op = parts[0]
        self.reply = "OK"
        if op == "?":
            self.reply = f"ROLE {self.board}"
        elif op == "G":
            self.reply = "A " + " ".join(f"{n}={v:g}" for n, v in self.angles.items())
        elif op == "S":
            for pair in parts[1:]:
                n, value = pair.split("=")
                self.angles[n] = float(value)
        elif op == "O":
            for n in parts[1:]:
                self.angles[n] = 90.0

    def readline(self):
        return (self.reply + "\n").encode()

    def close(self):
        pass

"""给视觉、T5 桥接等程序用：向统一控制进程提交意图，不碰串口。

    hub = HubClient()
    hub.intent("vision", {"LR": 0.6, "UD": 0.5}, ttl=0.5)
    hub.pose("dialog", "happy", intensity=0.7, ttl=3)
    hub.clear("dialog")

控制进程没开时返回 False，不抛异常，调用方继续跑就行。
"""
import http.client
import json


class HubClient:
    def __init__(self, host="127.0.0.1", port=8780, timeout=0.5):
        self.host, self.port, self.timeout = host, port, timeout
        self.conn = None
        self.error = ""

    def _post(self, body):
        data = json.dumps(body).encode()
        try:
            if self.conn is None:
                self.conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
            self.conn.request("POST", "/api", data, {"Content-Type": "application/json", "X-Head": "1"})
            r = self.conn.getresponse()
            reply = json.loads(r.read() or b"{}")
        except (OSError, http.client.HTTPException, ValueError) as e:
            self.close()
            self.error = str(e)
            return False
        self.error = reply.get("error", "")
        return r.status == 200

    def intent(self, source, values, ttl=1.0, merge=False):
        return self._post({"op": "intent", "source": source, "values": values, "ttl": ttl, "merge": merge})

    def pose(self, source, name, intensity=1.0, ttl=1.0):
        return self._post({"op": "intent", "source": source, "pose": name, "intensity": intensity, "ttl": ttl})

    def clear(self, source):
        return self._post({"op": "clear", "source": source})

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

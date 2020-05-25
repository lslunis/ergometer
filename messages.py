import base64
import copy
import json

TYPE_MAP = {}


class Registrar(type):
    def __new__(cls, name, bases, dct):
        new_class = super().__new__(cls, name, bases, dct)
        TYPE_MAP[dct["TYPE"]] = new_class
        return new_class


class Message(metaclass=Registrar):
    FIELDS = None
    TYPE = None

    def __init__(self, error, **fields):
        assert hasattr(self, "FIELDS")
        self.error = error
        self.fields = {}
        for k, v in fields.items():
            if k not in self.FIELDS:
                raise Exception(
                    f"Invalid field for {self.TYPE}: {k}. Allowed values are: {self.FIELDS}"
                )
            self.fields[k] = v
            setattr(self, k, v)
        missing = set(fields.keys()) - set(self.FIELDS)
        if missing:
            raise Exception(f"Missing fields for {self.TYPE}: {missing}")

    @property
    def type(self):
        return self.TYPE

    def encode(self):
        encoded = copy.copy(self.fields)
        encoded["type"] = self.TYPE
        encoded["error"] = self.error
        if "data" in encoded:
            encoded["data"] = base64.b64encode(encoded["data"]).decode("ascii")
        return json.dumps(encoded)

    @classmethod
    def decode(cls, blob):
        msg = json.loads(blob)
        msg_type = msg["type"]
        if "data" in msg:
            msg["data"] = base64.b64decode(msg["data"])
        if "type" not in msg:
            raise Exception(f"Unknown type for message: {blob}")
        msg_type = msg["type"]
        del msg["type"]
        error = msg["error"]
        del msg["error"]
        return TYPE_MAP[msg_type](error, **msg)


class WriteRequest(Message):
    FIELDS = ["host", "data", "pos"]
    TYPE = "write_req"


class WriteResponse(Message):
    FIELDS = ["pos"]
    TYPE = "write_resp"


class ReadRequest(Message):
    FIELDS = ["positions", "exclude"]
    TYPE = "read_req"


class ReadResponse(Message):
    FIELDS = ["host", "data", "pos"]
    TYPE = "read_resp"


class HostPositionRequest(Message):
    FIELDS = ["host"]
    TYPE = "host_position_req"


class HostPositionResponse(Message):
    FIELDS = ["host", "pos"]
    TYPE = "host_position_resp"

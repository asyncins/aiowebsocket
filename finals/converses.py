from freams import Frames


class Converse:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def send(self, message: bytes):
        fin = True
        code = 0x02
        frame = Frames(fin, code, message)
        frame.write(self.writer)

    def receive(self):
        message = yield from Frames().read(self.reader.readexactly)
        print(message)


import json
import hashlib
import os
import struct


def create_file(socket):
    filename, filesize = json.loads(socket.receive_msg())
    print "Creating:", filename
    print "Filesize: {} bytes".format(filesize)
    hash_func = hashlib.sha512()
    with open(filename, "wb") as writer:
        data_received = 0
        while data_received < filesize:
            data = socket.receive_msg()
            data_received += len(data)
            hash_func.update(data)
            writer.write(data)

    return hash_func.hexdigest()


def send_file(socket, filename):
    """
    send a file through sockets by reading and sending its binary contents
    calculate SHA 512 checksum and send that for validation

    :param socket: socket that will perform sending and receiving of msgs
                   socket must already be connected with client/server
                   socket must implement or use send_msg() and receive_msg()
                     in remote_server / remote_client
    :param filename: must be full filename including path
    """

    filesize = int(os.path.getsize(filename))
    print "Sending :", os.path.split(filename)[1]
    print "Filesize: {} bytes\n".format(filesize)
    socket.send_msg(json.dumps((os.path.split(filename)[1], filesize)))

    hash_func = hashlib.sha512()
    data_sent = 0
    with open(filename, "rb") as reader:
        while data_sent < filesize:
            data = reader.read(socket.data_rate)
            data_sent += len(data)
            hash_func.update(data)
            socket.send_msg(data)

    checksum = hash_func.hexdigest()
    socket.send_msg(checksum)


class CliserSocketCommunication(object):

    # modified https://stackoverflow.com/questions/17667903/17668009#17668009
    def send_msg(self, msg):
        msg = struct.pack(self.struct_fmt, len(msg)) + msg
        self.msg_handler.sendall(msg)

    def receive_msg(self):
        raw_msglen = self.recvall(self.struct_size)
        if not raw_msglen:
            raise ValueError("Message has no length")
        msglen = struct.unpack(self.struct_fmt, raw_msglen)[0]
        return self.recvall(msglen)

    def recvall(self, n):
        data = ""
        while len(data) < n:
            packet = self.msg_handler.recv(n - len(data))
            if not packet:
                data = None
                break
            data += packet
        return data

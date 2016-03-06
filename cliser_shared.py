import json
import hashlib
import os
import struct
import sys


def get_filesize_str(filesize_):
    """
    Constructs upload speed string
    Converts the given filesize_ argument to the largest possible
    metric (bytes, kilobytes, megabytes, ...) rounded to two decimal places

    arguments:
        :param filesize_: filesize of file in bytes

    return filesize string
    """

    metrics = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]

    metric_limit = 1024.0
    metric_count = 0
    while filesize_ >= metric_limit:
        filesize_ /= metric_limit
        metric_count += 1

    filesize = round(filesize_, 2)

    return str(filesize) + " " + metrics[metric_count]


def update_progress_stdin(prev, prog):
    if prog != prev:
        sys.stdout.write(len(prog) * "\b")
        sys.stdout.write(len(prog) * " ")
        sys.stdout.write(len(prog) * "\b")
        sys.stdout.write(prog)


def create_file(socket):
    filename, filesize = json.loads(socket.receive_msg())
    print "Creating:", filename
    print "Filesize: {} ".format(get_filesize_str(filesize))
    hash_func = hashlib.sha512()

    # create file in location that remote_server.py was started in
    #     to avoid possibly overwriting files in self.curr_dir
    # moving file to a different folder needs to be done explicitly
    with open(filename, "wb") as writer:
        data_received = 0.0

        progress_msg = ""
        while data_received < filesize:
            prev_progress_msg = progress_msg
            progress_msg = str(round((data_received/filesize) * 100)) + "%"

            update_progress_stdin(prev_progress_msg, progress_msg)

            data = socket.receive_msg()
            data_received += len(data)
            hash_func.update(data)
            writer.write(data)

        sys.stdout.write("\n")

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

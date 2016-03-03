import json
import hashlib
import os


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

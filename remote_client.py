import hashlib
import socket
import sys
import os
import pickle
import json
from time import time, sleep
import struct


"""
def changeRemoteDirectory(mainSock, switches):
    mainSock.send("changeDir" + "\n")
    currDir, dirList = pickle.loads(mainSock.recv(DATA_RATE))
    print "Current directory: ", currDir

    print "Available directories: "

    if 'cm' in switches:
        chosenDir = []
        chosenDir.append(raw_input("Enter directory name: "))
    else:
        chosenDir = getFilesToReceive(dirList, switches)

    mainSock.send(chosenDir[0].encode("utf-8") + "\n")
    print mainSock.recv(DATA_RATE)


def sendFile(mainSock, switches, file):
    print "Sending ", file
    mainSock.send("sendFile" + "\n")
    mainSock.send(sys.argv[1] + "\n")

    fileSize = os.path.getsize(sys.argv[1])
    print str(fileSize / 1048576) + " MB"
    mainSock.send(str(fileSize) + "\n")

    f = open(file, 'rb')
    data = f.read(DATA_RATE)
    dataSent = len(data)
    mainSock.send(data)

    prevPct = 0
    while(dataSent < fileSize):
        data = f.read(DATA_RATE)
        dataSent = dataSent + len(data)

        currPct = int((round(dataSent / (fileSize * 1.0), 2)) * 100)
        if currPct != prevPct:
            drawLoadingBar(str(currPct) + "%")
            prevPct = currPct

        mainSock.send(data)

    f.close()
    print "File sent"
"""


class MaxTriesExceededError(Exception):
    pass


class RemoteClient:

    def __init__(self):
        self.target_host = socket.gethostbyname("localhost")
        self.port = 9988
        self.socket = self.init_socket_connection()

        self.max_get_files_tries = 3
        self.data_rate = 32768
        self.struct_size = 8 # >Q
        self.struct_fmt = ">Q"
        self.timeout = 10 # seconds
        self.socket.settimeout(self.timeout)

        self.password = "abcdef"
        self.authenticate()

    def init_socket_connection(self):

        main_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print "Connecting to: {} on PORT: {}".format(self.target_host,
                                                     self.port)
        main_sock.connect((self.target_host, self.port))
        return main_sock

    def authenticate(self):
        self.send_msg(self.password)

    # modified https://stackoverflow.com/questions/17667903/17668009#17668009
    def send_msg(self, msg):
        msg = struct.pack(self.struct_fmt, len(msg)) + msg
        self.socket.sendall(msg)

    def receive_msg(self):
        raw_msglen = self.recvall(self.struct_size)
        if not raw_msglen:
            raise ValueError("Message has no length")
        msglen = struct.unpack(self.struct_fmt, raw_msglen)[0]
        return self.recvall(msglen)

    def recvall(self, n):
        data = ""
        while len(data) < n:
            packet = self.socket.recv(n - len(data))
            if not packet:
                data = None
                break
            data += packet
        return data

    def close_connection(self):
        self.socket.close()


def print_list(item_list):
    number = 1
    symbols = ["!", "@", "#"]

    for item in item_list:
        symbol = symbols[number % 3]
        print "[{s}  {n}  {s}] {i} [{s}  {n}  {s}]".format(
            s=symbol, n=number, i=item)
        number += 1


def run_command(client):
    operation = "run_command"
    command = sys.argv[2]
    command_args = " ".join(sys.argv[3:])

    client.send_msg(operation)
    client.send_msg(command)
    client.send_msg(command_args)


def create_file(client):
    filename, filesize = json.loads(client.receive_msg())
    print "Creating:", filename
    print "Filesize: {} bytes".format(filesize)
    hash_func = hashlib.sha512()
    with open(filename, "wb") as writer:
        data_received = 0
        while data_received < filesize:
            data = client.receive_msg()
            data_received += len(data)
            hash_func.update(data)
            writer.write(data)

    return hash_func.hexdigest()


def get_files(client, filename_choices=[], tries=0):
    operation = "get_files"
    client.send_msg(operation)

    f_list = json.loads(client.receive_msg())

    if len(filename_choices) == 0:
        print_list(f_list)
        choices = raw_input(
            "Enter number of file(s) separated by commas\n").split(',')
        filename_choices = map(lambda n: f_list[int(n)-1], choices)

    client.send_msg(json.dumps(filename_choices))

    for f in filename_choices:
        calculated_checksum = create_file(client)
        expected_checksum = client.receive_msg()
        # print "Expected checksum  :", expected_checksum
        # print "Calculated checksum:", calculated_checksum
        if expected_checksum != calculated_checksum:
            if tries > client.max_get_files_tries:
                raise MaxTriesExceededError(
                    "Tried to download {} and failed {} times.".format(
                        f, client.max_get_files_tries))
            else:
                print "Checksums do not match retrying."
                tries += 1
                get_files(RemoteClient(), [f], tries)


def create_new_user(client):
    operation = "create_new_user"
    new_user = sys.argv[2]
    new_password = " ".join(sys.argv[3:])
    msg = new_user + " " + new_password

    client.send_msg(operation)
    client.send_msg(msg)


def main():

    rc = RemoteClient()

    switches = map(lambda x: x.replace("-", ""), sys.argv[1:])

    if "rc" in switches:
        run_command(rc)

    elif "gf" in switches:
        get_files(rc)

    elif "nu" in switches:
        create_new_user(rc)

    elif "shutdown" in switches:
        operation = "shutdown"
        rc.send_msg(operation)

    else:
        rc.send_msg("")

    print rc.receive_msg()
    rc.close_connection()


if __name__ == "__main__":
    main()

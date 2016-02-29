import socket
import sys
import os
import pickle
import json
from time import time, sleep
import struct


"""
def sendReq(sock, fileToRetrieve):

    try:

        # Connect to server and send data
        sock.connect((TARGET_HOST, PORT))
        sock.send("getFile" + "\n")
        sock.send(fileToRetrieve .encode('utf-8') + "\n")

        name = (sock.recv(DATA_RATE)).decode('utf-8')
        print encodeUniEscape(name)

        fileSize = int(sock.recv(DATA_RATE))
        print str(fileSize / 1048576) + " MB"

        f = open(name, 'wb')
        data = sock.recv(DATA_RATE)

        dataRecv = len(data)
        f.write(data)

        prevPct = 0
        while(dataRecv < fileSize):

            data = sock.recv(DATA_RATE)
            dataRecv = dataRecv + len(data)
            currPct = int((round(dataRecv / (fileSize * 1.0), 2)) * 100)
            if currPct != prevPct:
                drawLoadingBar(str(currPct) + "%")
                prevPct = currPct

            f.write(data)

        print "\n"

        f.close()

    finally:
        sock.close()

    return (fileSize / 1048576.0)


def createSockets(n):
    socketList = []

    for i in range(0, n):
        exec("socket_" + str(i) + "=" +
             "socket.socket(socket.AF_INET, socket.SOCK_STREAM)")
        exec("socketList.append(" + "socket_" + str(i) + ")")

    return socketList


def encodeUniEscape(targ):
    return targ.encode('unicode_escape')


def createPrintableList(targList):
    return map(encodeUniEscape, targList)


def getChoices(fileList):

    printNumberedList(createPrintableList(fileList))
    choices = raw_input(
        "Select the number of the file. Separate with commas: \n")
    return choices.split(',')


def getFilesToReceive(choiceList, switches):
    if len(choiceList) > 0:
        chosenFiles = []
        if ('a' in switches):
            chosenFiles = choiceList

        elif ('g' in switches or 'c' in switches):
            for i in getChoices(choiceList):
                chosenFiles.append(choiceList[int(i) - 1])

    else:
        print "ERROR: Empty file list. No files in current directory."
        exit(1)

    return chosenFiles


def pullFiles(chosenFiles):
    startTime = time()
    totalFileSize = 0

    socketList = createSockets(len(chosenFiles))
    for i in range(0, len(socketList)):
        totalFileSize = totalFileSize + sendReq(socketList[i], chosenFiles[i])
        sleep(1)

    print totalFileSize, " MB"
    totalTime = time() - startTime
    print totalTime, " seconds", "( ", totalTime / 60.0, " minutes ) "
    print (totalFileSize / 1.0) / (time() - startTime), " MB/s"


def getFiles(mainSock, switches):
    mainSock.send("retrieveFileList" + "\n")

    choiceList = json.loads(mainSock.recv(DATA_RATE))
    chosenFiles = getFilesToReceive(choiceList, switches)
    pullFiles(chosenFiles)


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


class RemoteClient:

    def __init__(self):
        self.target_host = socket.gethostbyname("localhost")
        self.port = 9988
        self.socket = self.init_socket_connection()

        # self.data_rate = 32768
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


def main():

    rc = RemoteClient()

    switches = map(lambda x: x.replace("-", ""), sys.argv[1:])

    if "rc" in switches:
        operation = "run_command"
        command = sys.argv[2]
        command_args = " ".join(sys.argv[3:])

        rc.send_msg(operation)
        rc.send_msg(command)
        rc.send_msg(command_args)

    elif "gf" in switches:
        operation = "get_files"
        rc.send_msg(operation)

        f_list = json.loads(rc.receive_msg())
        print_list(f_list)
        choices = raw_input(
            "Enter number of file(s) separated by commas\n").split(',')

        rc.send_msg(json.dumps(choices))
        print len(choices)
        for c in range(0, len(choices)):
            filename, filesize = json.loads(rc.receive_msg())
            filename = os.path.split(filename)[1]
            print "Creating:", filename
            print "Filesize:", filesize
            with open(filename, "wb") as writer:
                data_received = 0
                while data_received < filesize:
                    data = rc.receive_msg()
                    data_received += len(data)
                    writer.write(data)

    elif "nu" in switches:
        operation = "create_new_user"
        new_user = sys.argv[2]
        new_password = " ".join(sys.argv[3:])
        msg = new_user + " " + new_password

        rc.send_msg(operation)
        rc.send_msg(msg)

    elif "shutdown" in switches:
        operation = "shutdown"
        rc.send_msg(operation)

    else:
        rc.send_msg("")

    print rc.receive_msg()
    rc.close_connection()


if __name__ == "__main__":
    main()

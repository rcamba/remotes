import socket
import threading
import SocketServer
import os
import pickle
import json
import time
import shutil
import subprocess
from root import drawLoadingBar

currDir = "C:\\Users\\Kevin\\Downloads\\uT_Downloads"
DEFAULT_CURR_DIR = "C:\\Users\\Kevin\\Downloads\\uT_Downloads"

HOST = socket.gethostname()
PORT = 9988

DATA_RATE = 32768
VALID_IPS = [socket.gethostbyname("MainDesktop")]


def validateIP(ipaddr):
    if(ipaddr not in VALID_IPS):
        print "Invalid IP ", ipaddr
        exit(1)
    else:
        print "Valid IP"


class ThreadedTCPRequestHandler(SocketServer.StreamRequestHandler):

    def handle(self):

        operation = self.rfile.readline().replace("\n", "")

        if operation == "retrieveFileList":
            self.__retrieveFileList__()

        elif operation == "getFile":
            self.__getFile__()

        elif operation == "sendFile":
            self.__receiveFile__()

        elif operation == "changeDir":
            self.__changeDir__()

        elif operation == "runComm":
            self.__runCommand__()

        elif operation == "sysCall":
            self.__directSysCall__()
        else:
            self.wfile.write("Invalid operation")

    def __retrieveFileList__(self):
        fList = getList("file")

        print "Sending file list"

        self.wfile.write(json.dumps(fList))

    def __getFile__(self):
        fileToRetrieve = self.rfile.readline().replace("\n", "")
        fileToRetrieve = fileToRetrieve.decode('utf-8')

        print "Sending file: ",
        self.__sendFile__(fileToRetrieve)

    def __changeDir__(self):
        global currDir
        dirList = getList("dir")

        print "Sending available directories "
        self.wfile.write(pickle.dumps((currDir, dirList)))

        targDir = self.rfile.readline().replace("\n", "").decode('utf-8')

        if targDir == '.':
            currDir = currDir
        elif targDir == "..":
            currDir = currDir[:currDir.rindex("\\")]
        else:
            if os.path.isdir(targDir):
                currDir = targDir
            else:
                print "Invalid directory: ", targDir

        print "Current directory: ", currDir.encode('unicode_escape'), "\n"

    def __sendFile__(self, file):
        fileStr = file.encode('unicode_escape').replace("\u", "")
        print fileStr
        self.wfile.write((os.path.split(file)[1]).encode('utf-8'))

        # file size
        fileSize = os.path.getsize(file)
        print "File size:", str(fileSize / 1048576.0), " MB"
        self.wfile.write(fileSize)

        time.sleep(1)

        # open file and read data
        f = open(file, 'rb')
        data = f.read(DATA_RATE)
        dataSent = len(data)
        self.wfile.write(data)

        while(dataSent < fileSize):
            data = f.read(DATA_RATE)
            dataSent = dataSent + len(data)
            self.wfile.write(data)

        f.close()

        print "Deleting ", fileStr
        os.remove(file)
        cur_thread = threading.current_thread()
        print cur_thread.name
        print "Done\n\n"

    def __receiveFile__(self):
        locked_currDir = currDir  # "locked"

        fileName = self.rfile.readline().replace("\n", "")
        print fileName

        fileSize = int(self.rfile.readline())
        print str(fileSize / 1048576) + " MB"

        f = open(fileName, 'wb')
        data = self.rfile.readline()

        dataRecv = len(data)
        f.write(data)

        prevPct = 0
        while(dataRecv < fileSize):

            data = self.rfile.readline()
            dataRecv = dataRecv + len(data)
            currPct = int((round(dataRecv / (fileSize * 1.0), 2)) * 100)
            if currPct != prevPct:
                drawLoadingBar(str(currPct) + "%")
                prevPct = currPct

            f.write(data)

        print "\n"

        f.close()

    def __runCommand__(self):
        print "Running command"

        command = self.rfile.readline().replace("\n", "")
        print "Command: ", command

        commandArgs = self.rfile.readline().replace("\n", "")
        print "Command arguments: ", commandArgs
        # os.system(command)

        if len(commandArgs) == 0:
            proc = subprocess.Popen(
                [command], stdout=subprocess.PIPE, shell=True)
            (out, err) = proc.communicate()
        else:
            proc = subprocess.Popen(
                [command, commandArgs], stdout=subprocess.PIPE, shell=True)
            (out, err) = proc.communicate()

        # send result of command

        self.wfile.write(out.encode('utf-8'))
        print "Finished running command"
        # print "out ", out
        # print "err" , err

    def __directSysCall__(self):
        print "Syscall"
        command = self.rfile.readline().replace("\n", "")
        print "Command: ", command
        os.system(command)


class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass


def getList(targ):

    fList = os.listdir(unicode(currDir))
    for i in range(len(fList) - 1, -1, -1):

        unicodeFileName = unicode(fList[i])
        fList[i] = currDir + "\\" + unicodeFileName

        if targ == "file":
            if(os.path.isfile(fList[i]) is False):
                fList.remove(fList[i])

        elif targ == "dir":
            if(os.path.isdir(fList[i]) is False):
                fList.remove(fList[i])

    if targ == "dir":
        fList.insert(0, "..")
        fList.insert(0, ".")

    fList.sort()

    return fList


if __name__ == "__main__":

    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    print "Server running on:  " + socket.gethostbyname(HOST)
    print "V: 03"
    # Start a thread with the server -- that thread will then start one
    # more thread for each request
    server_thread = threading.Thread(target=server.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.daemon = True
    server_thread.start()
    print "Server loop running in thread:", server_thread.name

    server.serve_forever()
    # add reset server command ? server.shutdown() and then server.start() ?

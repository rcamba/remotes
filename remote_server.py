import socket
import threading
import SocketServer
import os
import pickle
import json
import time
import shutil
import subprocess
import thread
import errno
import select
import ConfigParser
import hashlib
import uuid
import string

currDir = "C:\\Users\\Kevin\\Downloads\\uT_Downloads"
DEFAULT_CURR_DIR = "C:\\Users\\Kevin\\Downloads\\uT_Downloads"

HOST = socket.gethostbyname("localhost")  # socket.gethostname()
PORT = 9988


class InvalidCredentialsError(Exception):
    pass


class DuplicateUserError(Exception):
    pass


class ThreadedTCPRequestHandler(SocketServer.StreamRequestHandler):
    def __init__(self, request, client_address, server_):
        self.conf_parser = ConfigParser.RawConfigParser()
        self.config_file = "server_data"
        self.conf_parser.read(self.config_file)
        self.timeout = 10  # overrides parent
        self.data_rate = 32768
        SocketServer.StreamRequestHandler.__init__(self, request,
                                                   client_address, server_)

    def authenticate(self):
        print "Authenticating client:", (self.client_address)
        msg = self.receive_message()
        user = socket.gethostbyaddr(self.client_address[0])[0]

        try:
            hash_ = self.conf_parser.get(user, "hash")
            salt = self.conf_parser.get(user, "salt")
        except ConfigParser.NoSectionError:
            raise InvalidCredentialsError(
                "Unable to find credentials")

        if hashlib.sha512(msg + salt).hexdigest() != hash_:
            raise InvalidCredentialsError(
                "Invalid credentials")

        print "Authenticated:        ", self.client_address

    def receive_message(self):
        return self.rfile.readline().replace("\n", "")

    def send_msg(self, msg):
        self.wfile.write(msg.encode('utf-8').strip())

    def handle(self):

        self.authenticate()
        operation = self.receive_message()

        if operation == "shutdown":
            msg = "Shutting down server"
            self.send_msg(msg)
            print msg
            thread.start_new_thread(server.shutdown, ())

        elif operation == "create_new_user":
            self.create_new_user()

        elif operation == "retrieveFileList":
            self.__retrieveFileList__()

        elif operation == "getFile":
            self.__getFile__()

        elif operation == "sendFile":
            self.__receiveFile__()

        elif operation == "changeDir":
            self.__changeDir__()

        elif operation == "run_command":
            self.run_command()

        else:
            self.request.send("Invalid operation")

        self.finish()

    def create_new_user(self):
        try:
            new_user, new_password = self.receive_message().split(' ', 1)
        except ValueError:
            raise

        if any(c for c in new_user
               if c not in string.ascii_letters and
                c not in string.digits):
            msg = ("Invalid user: {}. " +
                   "Only letters and numbers are allowed.").format(new_user)
            self.send_msg(msg)
            raise InvalidCredentialsError(msg)

        if any(c for c in new_password
               if c in string.whitespace):
            msg = "Invalid password: {}. No whitespace allowed.".format(
                new_password)
            self.send_msg(msg)
            raise InvalidCredentialsError(msg)

        try:
            self.conf_parser.add_section(new_user)

        except ConfigParser.DuplicateSectionError:
            msg = "User {} already exists".format(new_user)
            self.send_msg(msg)
            raise DuplicateUserError(msg)

        new_salt = uuid.uuid4().hex
        new_hash = hashlib.sha512(new_password + new_salt).hexdigest()

        self.conf_parser.set(new_user, "hash", new_hash)
        self.conf_parser.set(new_user, "salt", new_salt)

        with open(self.config_file, 'wb') as cff:
            self.conf_parser.write(cff)

        self.send_msg("Created new user: " + new_user)

    """
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
    """

    def run_command(self):
        command = self.receive_message()
        print "Running command:", command

        command_args = self.receive_message()
        print "Command arguments:", command_args

        if len(command_args) == 0:
            proc = subprocess.Popen(
                [command], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, shell=True)
            out, err = proc.communicate()
        else:
            proc = subprocess.Popen(
                [command, command_args], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, shell=True)
            out, err = proc.communicate()

        if err is not None and len(err) > 0:
            self.send_msg(err)
        else:
            self.send_msg(out)

        print "Finished running command"


class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass


"""
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
"""

if __name__ == "__main__":
    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)

    print "Server running on:" + socket.gethostbyname(HOST)
    server.serve_forever()
    server.server_close()

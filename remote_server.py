import socket
import SocketServer
import os
import json
import subprocess
import thread
import ConfigParser
import hashlib
import uuid
import string
import struct
import cliser_shared


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

        self.struct_size = 8  # >Q
        self.struct_fmt = ">Q"

        self.data_rate = 32768
        self.default_dir = self.conf_parser.get("Settings", "default_dir")
        SocketServer.StreamRequestHandler.__init__(self, request,
                                                   client_address, server_)

    def authenticate(self):
        print "Authenticating client:", (self.client_address)

        msg = self.receive_msg()
        user = socket.gethostbyaddr(self.client_address[0])[0]

        # if there are no others users make first user connecting as admin...
        if (len(self.conf_parser.sections()) == 1 and
                self.conf_parser.sections()[0] == "Settings"):
            self.create_new_user(user, msg)

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

    def update_settings(self, targ_setting, new_value):
        print "Updating Settings"
        # self.conf_parser.add_section("Settings")
        self.conf_parser.set("Settings", targ_setting, new_value)
        with open(self.config_file, 'wb') as cff:
            self.conf_parser.write(cff)

    # modified https://stackoverflow.com/questions/17667903/17668009#17668009
    def send_msg(self, msg):
        msg = struct.pack(self.struct_fmt, len(msg)) + msg
        self.request.sendall(msg)

    def receive_msg(self):
        raw_msglen = self.recvall(self.struct_size)
        if not raw_msglen:
            raise ValueError("Message has no length")
        msglen = struct.unpack(self.struct_fmt, raw_msglen)[0]
        return self.recvall(msglen)

    def recvall(self, n):
        data = ""
        while len(data) < n:
            packet = self.request.recv(n - len(data))
            if not packet:
                data = None
                break
            data += packet
        return data

    def handle(self):

        self.authenticate()
        operation = self.receive_msg()

        if operation == "shutdown":
            msg = "Shutting down server"
            self.send_msg(msg)
            print msg
            thread.start_new_thread(server.shutdown, ())

        elif operation == "create_new_user":
            self.create_new_user()

        elif operation == "get_files":
            self.get_files()

        elif operation == "send_files":
            self.send_files()

        elif operation == "updating_settings":
            target_option, new_value = json.loads(self.receive_msg())
            self.update_settings(target_option, new_value)
            self.send_msg("Successfully updated settings")

        elif operation == "changeDir":
            self.__changeDir__()

        elif operation == "run_command":
            self.run_command()

        else:
            self.request.send("Invalid operation")

        self.finish()

    def create_new_user(self, new_user=None, new_password=None):

        if all([new_user is None, new_password is None]):
            try:
                new_user, new_password = self.receive_msg().split(' ', 1)
            except ValueError:
                raise

        elif any([new_user is None, new_password is None]):
            raise ValueError("Must provide both username and password")

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

        if all([new_user is None, new_password is None]):
            self.send_msg("Created new user: " + new_user)

    def get_files_list(self):
        f_list = os.listdir(unicode(self.default_dir))
        f_list = map(lambda f: os.path.join(self.default_dir, f), f_list)
        f_list = [os.path.split(f)[1] for f in f_list if os.path.isfile(f)]
        f_list.sort()
        return f_list

    def get_files(self):
        print "Sending file list"
        f_list = self.get_files_list()

        self.send_msg(json.dumps(f_list))

        filename_choices = json.loads(self.receive_msg())

        f_list = map(lambda f: os.path.join(self.default_dir, f),
                     filename_choices)

        for f in f_list:
            cliser_shared.send_file(self, f)

        self.send_msg("Finished operation get_files")

    def send_files(self):
        print "Receiving files"

        calculated_checksum = cliser_shared.create_file(self)
        expected_checksum = self.receive_msg()
        if calculated_checksum != expected_checksum:  # ask to resend
            self.send_msg("receive_failure")
            # TODO alternative to recursion

        else:
            print "Checksums match!"
            self.send_msg("receive_success")

        self.send_msg("Finished operation send_files")

    """
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

    """

    def run_command(self):
        command = self.receive_msg()
        print "Running command:", command

        command_args = self.receive_msg()
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


def check_for_config_file():
    """
    Checks if config file exists
        if not then create one

        defaults:
            [Section] - [Option] - [Value]
            Settings - "default_dir" - server current dir

        First user to connect will have them as admin
    """

    config_file = "server_data"
    if not os.path.isfile(config_file):
        print "Config file {c} not found. Creating new file {c}.".format(
            c=config_file)
        with open(config_file, "wb"):
            pass

    conf_parser = ConfigParser.RawConfigParser()
    conf_parser.add_section("Settings")
    conf_parser.set("Settings", "default_dir", os.getcwd())
    with open(config_file, 'wb') as cff:
        conf_parser.write(cff)


if __name__ == "__main__":
    host = socket.gethostbyname("localhost")  # socket.gethostname()
    port = 9988

    check_for_config_file()
    server = ThreadedTCPServer((host, port), ThreadedTCPRequestHandler)

    print "Server running on:" + socket.gethostbyname(host)

    server.serve_forever()
    server.server_close()

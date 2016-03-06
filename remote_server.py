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
import threading
import cliser_shared


class InvalidCredentialsError(Exception):
    pass


class DuplicateUserError(Exception):
    pass


class ThreadedTCPRequestHandler(SocketServer.StreamRequestHandler,
                                cliser_shared.CliserSocketCommunication):

    def __init__(self, request, client_address, server_):
        self.conf_parser = ConfigParser.RawConfigParser()
        self.config_file = "server_data"
        self.conf_parser.read(self.config_file)

        self.timeout = 20  # overrides parent

        self.struct_size = 8  # >Q
        self.struct_fmt = ">Q"

        self.data_rate = 32768
        self.default_dir = self.conf_parser.get("Settings", "default_dir")

        # values set when client connects in self.handle()
        self.user = ""
        self.curr_dir = ""
        self.msg_handler = ""

        SocketServer.StreamRequestHandler.__init__(self, request,
                                                   client_address, server_)

    def authenticate(self):
        msg = self.receive_msg()
        user = socket.gethostbyaddr(self.client_address[0])[0]
        print "Authenticating client:", (user)

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

        print "Authenticated:        ", user

    def update_settings(self, targ_opt, new_value):
        print "Updating Settings"
        # self.conf_parser.add_section("Settings")
        success = False
        if self.conf_parser.has_option("Settings", targ_opt):
            self.conf_parser.set("Settings", targ_opt, new_value)
            with open(self.config_file, 'wb') as cff:
                self.conf_parser.write(cff)
            success = True

        return success

    def update_user_settings(self, targ_opt, new_value):
        print "Updating user settings"

        success = False
        if self.conf_parser.has_option(self.user, targ_opt):
            self.conf_parser.set(self.user, targ_opt, new_value)
            with open(self.config_file, 'wb') as cff:
                self.conf_parser.write(cff)
            success = True

        return success

    # message handling (send/recv) inherited from CliserSocketCommunication

    def handle(self):

        self.msg_handler = self.request
        self.authenticate()

        self.user = socket.gethostbyaddr(self.client_address[0])[0]
        self.curr_dir = self.conf_parser.get(self.user, "curr_dir")

        operation = self.receive_msg()

        if operation == "shutdown":
            msg = "Shutting down server"
            self.send_msg(msg)
            print msg
            thread.start_new_thread(server.shutdown, ())

        elif operation == "restart":
            msg = "Restarting"
            self.send_msg(msg)
            print msg
            t = threading.Thread(target=server.shutdown())
            while t.is_alive():
                t.join(1)

            detached_process = 0x00000008
            subprocess.Popen(["python", "remote_server.py"], shell=True,
                             stdin=None, stdout=None, stderr=None,
                             creationflags=detached_process)

        elif operation == "update_server":
            msg = "Updating server"
            self.send_msg(msg)
            print msg
            t = threading.Thread(target=server.shutdown())
            while t.is_alive():
                t.join(1)

            detached_process = 0x00000008
            subprocess.Popen(["python", "updater.py"], shell=True,
                             stdin=None, stdout=None, stderr=None,
                             creationflags=detached_process)

        elif operation == "create_new_user":
            self.create_new_user()

        elif operation == "get_files":
            self.get_files()

        elif operation == "send_files":
            self.send_files()

        elif operation == "updating_settings":
            target_option, new_value = json.loads(self.receive_msg())
            success = self.update_settings(target_option, new_value)
            if success:
                self.send_msg("Successfully updated settings")
            else:
                self.send_msg(
                    "Failed to update settings. "
                    "{} is not a valid option.".format(target_option))

        elif operation == "list_items_in_dir":
            self.list_items_in_dir()

        elif operation == "change_dir":
            self.change_dir()

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

        self.conf_parser.set(new_user, "curr_dir", self.default_dir)

        with open(self.config_file, 'wb') as cff:
            self.conf_parser.write(cff)

        if all([new_user is None, new_password is None]):
            self.send_msg("Created new user: " + new_user)

    def get_files_list(self):
        f_list = os.listdir(unicode(self.curr_dir))
        f_list = map(lambda f_:
                     os.path.normpath(os.path.join(self.curr_dir, f_).encode(
                         "unicode_escape")), f_list)
        f_list = [os.path.split(f)[1] for f in f_list if os.path.isfile(f)]
        f_list.sort()
        return f_list

    def get_dir_list(self):
        dir_list = os.listdir(unicode(self.curr_dir))
        dir_list = map(lambda d_:
                       os.path.normpath(os.path.join(self.curr_dir, d_).encode(
                           "unicode_escape")), dir_list)
        dir_list = [d for d in dir_list if os.path.isdir(d)]
        dir_list.sort()
        return dir_list

    def list_items_in_dir(self):
        items_list = self.get_dir_list()
        items_list.extend(self.get_files_list())
        items_list.sort()
        self.send_msg(json.dumps(items_list))
        self.send_msg("Finished operation display_dir")

    def change_dir(self):

        instr = "Enter full directory name or navigate using numbers.\n" \
                "Enter 'q' when finished.\n" \
                "Enter 'd' to quit and discard changes in directory.\n" \
                "Enter 'r' to reset directory to default.\n"

        dir_list = self.get_dir_list()
        dir_list.insert(0, os.path.abspath(
            os.path.join(self.curr_dir, os.pardir)))

        self.send_msg(instr)
        self.send_msg(json.dumps(dir_list))

        choice = self.receive_msg()
        while choice != "q" and choice != "d":

            err = None
            if not os.path.isdir(choice):
                err = "{} is not a valid directory.".format(choice)
            else:
                self.curr_dir = choice
                dir_list = self.get_dir_list()
                dir_list.insert(0, os.path.abspath(
                    os.path.join(self.curr_dir, os.pardir)))
            self.send_msg(json.dumps((dir_list, err)))
            choice = self.receive_msg()

        if choice == "d":
            self.send_msg("No changes have been made")

        elif choice == "q":
            self.update_user_settings("curr_dir", self.curr_dir)
            msg = "Changed current directory to: {}".format(self.curr_dir)
            print msg
            self.send_msg(msg)

        elif choice == "r":
            self.update_user_settings("curr_dir", self.default_dir)

    def get_files(self):
        print "Sending file list"
        f_list = self.get_files_list()

        self.send_msg(json.dumps(f_list))

        filename_choices = json.loads(self.receive_msg())

        f_list = map(lambda f_: os.path.join(self.curr_dir, f_),
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
        with open(config_file, 'a') as cff:
            conf_parser.write(cff)


if __name__ == "__main__":
    host = socket.gethostbyname("localhost")  # socket.gethostname()
    port = 9988

    check_for_config_file()

    server = ThreadedTCPServer((host, port), ThreadedTCPRequestHandler)

    print "Server running on:", socket.gethostbyname(host)

    server.serve_forever()
    server.server_close()

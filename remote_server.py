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
import time
import sys
import ast
import logging


class DuplicateUserError(Exception):
    pass


def create_batch_file(command_loc, command_args):
    extension = None

    if sys.platform.startswith("win32"):
        extension = "bat"
    elif sys.platform.startswith("linux"):
        extension = "sh"

    command_args = map(lambda a: "\"" + a + "\"", command_args)

    batch_name = "{time}.{ext}".format(time=str(time.time()),
                                       ext=extension)
    arg_str = " ".join(command_args)
    with open(batch_name, 'w') as writer:
        batch_contents = "\"{cl}\" {arg}".format(cl=command_loc, arg=arg_str)
        writer.write(batch_contents)
        writer.write("\n")

    log_and_print("Batch contents: " + batch_contents)
    log_and_print("Creating " + batch_name)
    return batch_name


def log_and_print(msg, level="info"):
    print msg
    if level == "info":
        logging.info(msg)
    elif level == "debug":
        logging.debug(msg)
    else:
        logging.error(msg)


class ThreadedTCPRequestHandler(SocketServer.StreamRequestHandler,
                                cliser_shared.CliserSocketCommunication):

    def __init__(self, request, client_address, server_):
        self.conf_parser = ConfigParser.RawConfigParser()
        self.config_file = check_for_config_file()
        self.conf_parser.read(self.config_file)

        # self.timeout = 90  # overrides parent
        self.command_timeout = 180

        self.struct_size = 8  # >Q
        self.struct_fmt = ">Q"

        self.data_rate = 32768
        self.default_dir = self.conf_parser.get("Settings", "default_dir")

        # values set when client connects in self.handle()
        self.user = ""
        self.curr_dir = ""
        self.msg_handler = ""

        self.operation_function_mapping = {
            "run_command": self.run_command,
            "add_custom_operation": self.add_custom_operation,
            "firefox_open": self.firefox_open,
            "change_dir": self.change_dir,
            "list_items_in_dir": self.list_items_in_dir,
            "get_files": self.get_files,
            "send_files": self.send_files,
            "create_new_user": self.create_new_user,
            "update_settings": self.update_settings,
            "update_server": self.update_server,
            "restart": self.restart_server,
            "shutdown": self.shutdown_server
        }
        self.custom_ops = {}

        self.ffo_proc = None
        self.rc_proc = None

        SocketServer.StreamRequestHandler.__init__(self, request,
                                                   client_address, server_)

    def authenticate(self):
        valid = False

        msg = self.receive_msg()
        user = socket.gethostbyaddr(self.client_address[0])[0]
        user = user.lower()
        log_and_print("Authenticating client: " + user)

        # if there are no others users make first user connecting as admin...
        if (len(self.conf_parser.sections()) == 1 and
                self.conf_parser.sections()[0] == "Settings"):
            self.create_new_user(user, msg)

        try:
            hash_ = self.conf_parser.get(user, "hash")
            salt = self.conf_parser.get(user, "salt")
        except ConfigParser.NoSectionError:
            hash_ = ""
            salt = ""

        if hashlib.sha512(msg + salt).hexdigest() == hash_:
            valid = True
            self.user = user

        return valid

    def update_settings(self):
        log_and_print("Updating server settings")

        target_option, new_value = json.loads(self.receive_msg())
        success = False
        if self.conf_parser.has_option("Settings", target_option):
            self.conf_parser.set("Settings", target_option, new_value)
            with open(self.config_file, 'wb') as cff:
                self.conf_parser.write(cff)
            success = True

        if success:
            log_and_print("Successfully updated server settings")
            self.send_msg("Successfully updated settings")
        else:
            fail_msg = "Failed to update settings. " \
                       "{} is not a valid option.".format(target_option)
            log_and_print(fail_msg, level="debug")
            self.send_msg(fail_msg)

    def update_user_settings(self, targ_opt, new_value):
        log_and_print("Updating {opt} in {u}'s settings".format(
            u=self.user, opt=targ_opt))

        success = False
        if self.conf_parser.has_option(self.user, targ_opt):
            self.conf_parser.set(self.user, targ_opt, new_value)
            with open(self.config_file, 'wb') as cff:
                self.conf_parser.write(cff)
            success = True

        log_and_print("Successfully updated {u}'s settings")

        return success

    def update_server(self):
        msg = "Updating server"
        self.send_msg(msg)
        log_and_print(msg)
        t = threading.Thread(target=server.shutdown())
        while t.is_alive():
            t.join(1)

        detached_process = 0x00000008
        subprocess.Popen(["python", "updater.py"],
                         stdin=None, stdout=None, stderr=None,
                         creationflags=detached_process)

    def restart_server(self):
        msg = "Restarting server"
        self.send_msg(msg)
        log_and_print(msg)
        t = threading.Thread(target=server.shutdown())
        while t.is_alive():
            t.join(1)

        detached_process = 0x00000008
        subprocess.Popen(["python", "remote_server.py"],
                         stdin=None, stdout=None, stderr=None,
                         creationflags=detached_process)

    def shutdown_server(self):
        msg = "Shutting down server"
        self.send_msg(msg)
        log_and_print(msg)
        thread.start_new_thread(server.shutdown, ())

    # message handling (send/recv) inherited from CliserSocketCommunication
    def handle(self):

        self.msg_handler = self.request
        valid = self.authenticate()
        if valid:
            log_and_print("Authenticated:         " + self.user)
            self.send_msg("Valid credentials")

            self.curr_dir = self.conf_parser.get(self.user, "curr_dir")
            self.custom_ops = ast.literal_eval(
                self.conf_parser.get(self.user, "custom_ops"))

            operation = self.receive_msg()

        else:
            log_and_print("Authentication failed:" +
                          socket.gethostbyaddr(self.client_address[0])[0],
                          level="debug")
            self.send_msg("Invalid credentials")
            return

        if operation in self.operation_function_mapping:
            log_and_print("Running regular op: " + operation)
            self.operation_function_mapping[operation]()
        elif operation in self.custom_ops:
            log_and_print("Running custom_op: " + operation)
            self.run_command(self.custom_ops[operation][0],
                             [self.custom_ops[operation][1]])
        else:
            log_and_print("Invalid operation {}".format(operation),
                          level="debug")
            self.request.send("Invalid operation {}".format(operation))

        self.finish()

    def run_command(self, command=None, command_args=None):
        if command is None:
            command = self.receive_msg()
        log_and_print("Running command:" + command)

        if command_args is None:
            command_args = self.receive_msg().split()
        log_and_print("Command arguments:" + " ".join(command_args))

        # Workaround for running commands that have spaces and args that
        #   use characters that don't get escaped (e.g &, =) even with '^'
        # e.g "Program Files (x86)\\Mozilla Firefox\\firefox.exe" ... "a=1&b=1"
        command = os.path.normpath(command)
        command_name = create_batch_file(command, command_args)
        batch_command_name = [command_name]

        communicate_container = []

        def run_cmd_t():
            self.rc_proc = subprocess.Popen(
                batch_command_name, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, shell=True)
            communicate_container.append(self.rc_proc.communicate())

        t = threading.Thread(target=run_cmd_t)
        t.start()
        t.join(timeout=self.command_timeout)
        if t.is_alive():
            self.rc_proc.terminate()
            t.join()

        os.remove(command_name)

        out = communicate_container[0][0]
        err = communicate_container[0][1]
        if err is not None and len(err) > 0:
            self.send_msg(err)
            log_and_print(err, level="debug")
        else:
            self.send_msg(out)
            log_and_print(out, level="debug")

        log_and_print("Finished running command")

    def add_custom_operation(self):
        new_op, new_cmd, new_cmd_args = json.loads(self.receive_msg())
        log_and_print("Adding custom operation:" + new_op)

        result_msg = ""
        args_valid = True

        if any([len(new_cmd) == 0, len(new_op) == 0]):
            result_msg += "Missing argument"
            args_valid = False

        if new_op in self.operation_function_mapping:
            result_msg += "Can't replace default operation {}".format(new_op)
            args_valid = False

        if new_op in self.custom_ops:
            result_msg += "Operation: {o} already exists.\n  " \
                         "Replacing command: {c1} with {c2}".format(
                          o=new_op,
                          c1=self.custom_ops[new_op], c2=new_cmd)

        if args_valid:
            if not os.path.isabs(new_cmd):
                new_cmd = os.path.join(self.curr_dir, new_cmd)
            if os.path.isfile(new_cmd):
                self.custom_ops[new_op] = (new_cmd, new_cmd_args)
                print new_op, "mapped to", (new_cmd, new_cmd_args)

                self.conf_parser.set(self.user, "custom_ops", self.custom_ops)
                with open(self.config_file, 'ab') as cff:
                    self.conf_parser.write(cff)

                self.send_msg("success")

            else:
                result_msg += "Command {} doesn't exist.\n  " \
                              "Enter full command path otherwise your " \
                              "current directory will be used to " \
                              "create it.".format(new_cmd)

                self.send_msg("failed")

            log_and_print(result_msg)
            self.send_msg(result_msg)

    def firefox_open(self):
        link = self.receive_msg()
        log_and_print("Opening: " + link)

        if sys.platform.startswith("win32"):
            ff_exe = os.path.join("C:", os.sep,
                                  "Program Files (x86)",
                                  "Mozilla Firefox", "firefox.exe")
            if not os.path.isfile(ff_exe):
                ff_exe = os.path.join("C:", os.sep,
                                      "Program Files",
                                      "Mozilla Firefox", "firefox.exe")

        elif sys.platform.startswith("linux"):
            ff_exe = os.path.join("usr", "bin", "firefox")

        else:
            raise OSError("Unsupported OS")

        self.run_command(command=ff_exe, command_args=["-new-tab", link])

        self.send_msg("Finished firefox_open")

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
            log_and_print(msg)
            self.send_msg(msg)

        elif choice == "r":
            self.update_user_settings("curr_dir", self.default_dir)

    def list_items_in_dir(self):
        items_list = self.get_dir_list()
        items_list.extend(self.get_files_list())
        items_list.sort()
        self.send_msg(json.dumps(items_list))
        self.send_msg("Finished operation display_dir")

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

    def get_files(self):
        log_and_print("Sending file list")
        f_list = self.get_files_list()

        self.send_msg(json.dumps(f_list))

        filename_choices = json.loads(self.receive_msg())

        f_list = map(lambda f_: os.path.join(self.curr_dir, f_),
                     filename_choices)

        for f in f_list:
            cliser_shared.send_file(self, f)

        finished_msg = "Finished operation get_files"
        log_and_print(finished_msg)
        self.send_msg(finished_msg)

    def send_files(self):
        log_and_print("Receiving files")

        calculated_checksum = cliser_shared.create_file(self)
        expected_checksum = self.receive_msg()
        if calculated_checksum != expected_checksum:  # ask to resend
            self.send_msg("receive_failure")
            log_and_print("Checksums do not match. Got {} "
                          "but expected {}".format(calculated_checksum,
                                                   expected_checksum))
            # TODO alternative to recursion

        else:
            log_and_print("Checksums match!")
            self.send_msg("receive_success")

        finished_msg = "Finished operation send_files"
        log_and_print(finished_msg)
        self.send_msg(finished_msg)

    def create_new_user(self, new_user=None, new_password=None):
        log_and_print("Creating new user:" + new_user)
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

        if any(c for c in new_password
               if c in string.whitespace):
            msg = "Invalid password: {}. No whitespace allowed.".format(
                new_password)
            self.send_msg(msg)

        try:
            new_user = new_user.lower()
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
        self.conf_parser.set(new_user, "custom_ops", "{}")

        with open(self.config_file, 'wb') as cff:
            self.conf_parser.write(cff)

        if all([new_user is None, new_password is None]):
            self.send_msg("Created new user: " + new_user)
            log_and_print("Created new user: " + new_user)


class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass


def get_config_storage_dir():
    if sys.platform.startswith("win32"):
        config_storage = os.getenv("APPDATA")
    elif sys.platform.startswith("linux"):
        config_storage = os.path.expanduser('~')
    else:
        raise OSError("Unsupported OS")

    return os.path.join(config_storage, ".remotes-data")


def check_for_config_file():
    """
    Checks if config file exists
        if not then create one

        defaults:
            [Section] - [Option] - [Value]
            Settings - "default_dir" - server current dir

        First user to connect will have them as admin
    """

    config_storage_dir_ = get_config_storage_dir()
    if not os.path.isdir(config_storage_dir_):
        os.mkdir(config_storage_dir_)

    config_file_ = os.path.join(config_storage_dir_, "server_data")

    if not os.path.isfile(config_file_):
        log_and_print(
            "Config file {c} not found.\n  Creating new file {c}.".format(
                c=config_file_))
        with open(config_file_, "wb"):
            pass

        conf_parser = ConfigParser.RawConfigParser()
        conf_parser.add_section("Settings")
        conf_parser.set("Settings", "default_dir", os.getcwd())
        with open(config_file_, 'a') as cff:
            conf_parser.write(cff)

    return config_file_


if __name__ == "__main__":
    host = socket.gethostname()
    port = 9988

    check_for_config_file()
    rev = subprocess.Popen(["git", "show", "--pretty=oneline",
                            "--abbrev-commit", "--quiet", "--max-count", "1",
                            "remote_server.py"],
                           stdout=subprocess.PIPE).communicate()[0].split()

    config_storage_dir = get_config_storage_dir()
    log_file = os.path.join(config_storage_dir, "remotes_server.log")
    logging.basicConfig(filename=log_file, level=logging.DEBUG,
                        format="%(asctime)s %(message)s",
                        datefmt="%d/%m/%Y %I:%M:%S %p")

    line_limit = 79
    char_count = 0

    for i in range(0, len(rev)):
        word = rev[i]
        char_count += len(word)
        if char_count >= line_limit:
            rev[i - 1] += "\n"
            char_count = len(word)

    log_and_print(" ".join(rev))

    server = ThreadedTCPServer((host, port), ThreadedTCPRequestHandler)
    log_and_print("Running on {} ({}) at port: {}".format(
        host, socket.gethostbyname(host), port))

    server.serve_forever()
    server.server_close()
    logging.shutdown()

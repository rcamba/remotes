import socket
import sys
import os
import json
import cliser_shared
import ConfigParser
import ast


class MaxTriesExceededError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class RemoteClient(cliser_shared.CliserSocketCommunication):

    def __init__(self, target_host=None):
        # prevent autocall when get_target_host() is set as default argument
        if target_host is None:
            target_host = get_target_host()

        self.target_host = target_host
        self.port = 9988
        self.socket = self.init_socket_connection()

        self.max_get_files_tries = 3
        self.data_rate = 32768

        self.struct_size = 8  # >Q
        self.struct_fmt = ">Q"

        self.timeout = 300  # seconds
        self.socket.settimeout(self.timeout)

        self.msg_handler = self.socket

        self.password = get_config_password()
        self.authenticate()

    def init_socket_connection(self):

        main_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print "Connecting to: {} on PORT: {}".format(self.target_host,
                                                     self.port)
        main_sock.connect((self.target_host, self.port))
        return main_sock

    def authenticate(self):
        self.send_msg(self.password)
        result = self.receive_msg()
        if "Invalid credentials" in result:
            raise InvalidCredentialsError(result)

    # message handling (send/recv) inherited from CliserSocketCommunication

    def close_connection(self):
        self.socket.close()


def run_command(client):
    operation = "run_command"
    command = sys.argv[2]
    command_args = " ".join(sys.argv[3:])

    client.send_msg(operation)
    client.send_msg(command)
    client.send_msg(command_args)


def set_custom_ops(custom_ops):
    conf_parser = ConfigParser.RawConfigParser()
    conf_parser.read(config_file)
    conf_parser.set("client", "custom_ops", custom_ops)
    with open(config_file, 'wb') as cff:
            conf_parser.write(cff)


def add_custom_operation(client):
    operation = "add_custom_operation"

    custom_operation = sys.argv[2]
    if " " in custom_operation:
        raise ValueError(
            "Operation can't contain spaces: {}".format(custom_operation))

    custom_command = sys.argv[3]
    custom_command_args = ""
    if len(sys.argv) > 4:
        custom_command_args = " ".join(sys.argv[4:])

    client.send_msg(operation)
    client.send_msg(json.dumps((custom_operation,
                                custom_command, custom_command_args)))
    result = client.receive_msg()

    if result == "success":
        custom_ops = get_custom_ops()
        custom_ops.update({custom_operation:
                          (custom_command, custom_command_args)})
        set_custom_ops(custom_ops)
    else:
        print result


def open_in_firefox(client):
    operation = "firefox_open"
    # command_and_args = map(lambda c: "\"" + c + "\"", sys.argv[2:])
    command_and_args = " ".join(sys.argv[2:])

    print command_and_args

    client.send_msg(operation)
    client.send_msg(command_and_args)


def change_dir(client):
    operation = "change_dir"
    client.send_msg(operation)
    instructions = client.receive_msg()

    dir_list = json.loads(client.receive_msg())
    print instructions
    print_list(dir_list)
    choice = raw_input()
    if choice.isdigit():
        client.send_msg(dir_list[(int(choice)-1)])
    else:
        client.send_msg(choice.lower())

    while choice != "q" and choice != "d":
        dir_list, err = json.loads(client.receive_msg())
        print_list(dir_list)
        if err is not None:
            print err
        choice = raw_input()

        if choice.isdigit():
            client.send_msg(dir_list[(int(choice)-1)])
        else:
            client.send_msg(choice.lower())


def list_dir(client):
    operation = "list_items_in_dir"
    client.send_msg(operation)
    print_list(json.loads(client.receive_msg()))


def print_list(item_list):
    number = 1
    symbols = ["!", "+", "#"]

    for item in item_list:
        symbol = symbols[number % 3]
        print "[{s}  {n}  {s}] {i} [{s}  {n}  {s}]".format(
            s=symbol, n=number, i=item)
        number += 1


def get_files(client, filename_choices=None, tries=0):
    operation = "get_files"
    client.send_msg(operation)

    f_list = json.loads(client.receive_msg())

    if filename_choices is None:
        print_list(f_list)
        choices = raw_input(
            "Enter number of file(s) separated by commas\n").split(',')
        filename_choices = map(lambda n: f_list[int(n)-1], choices)

    client.send_msg(json.dumps(filename_choices))

    for f in filename_choices:
        calculated_checksum = cliser_shared.create_file(client)
        expected_checksum = client.receive_msg()

        if expected_checksum == calculated_checksum:
            print "Checksums match!"

        else:
            if tries > client.max_get_files_tries:
                raise MaxTriesExceededError(
                    "Tried to download {} and failed {} times.".format(
                        f, client.max_get_files_tries))
            else:
                # TODO shared way to handle checksum and retry
                print "Expected checksum  :", expected_checksum
                print "Calculated checksum:", calculated_checksum
                print "Checksums do not match retrying."
                tries += 1
                get_files(RemoteClient(), [f], tries)


def send_files(client, interactive=False):
    operation = "send_files"
    client.send_msg(operation)

    pruned_f_list = []
    if interactive:
        # Cli[p]board ?
        prompt = "Get files to send from:\n" \
                 "[C]urrent directory\n" \
                 "[O]ther directory\n" \
                 "[T]yping filenames"
        choice = raw_input(prompt)

        if choice.lower() == "c":
            f_list = os.listdir(os.getcwd())
            print_list(f_list)
            file_indexes = raw_input(
                "Enter number(s) separated by comma").split(',')
            pruned_f_list = [f_list[int(fi)-1] for fi in file_indexes]

    else:
        filename = sys.argv[2]
        pruned_f_list = [filename]

    for f in pruned_f_list:
        if not os.path.isabs(f):
            filename = os.path.join(os.getcwd(), f)

        if not os.path.isfile(filename):
            raise IOError("{} is not a valid file".format(filename))

        cliser_shared.send_file(client, filename)

        send_status = client.receive_msg()
        # TODO shared way to handle checksum and retry
        if send_status == "receive_failure":
            raise IOError("{} was not received properly. " +
                          "Retry".format(filename))
            # TODO alternative to recursion


def create_new_user(client):
    operation = "create_new_user"
    new_user = sys.argv[2]
    new_password = " ".join(sys.argv[3:])
    msg = new_user + " " + new_password

    client.send_msg(operation)
    client.send_msg(msg)


def get_target_host():
    conf_parser = ConfigParser.RawConfigParser()
    conf_parser.read(config_file)
    target_host = conf_parser.get("client", "target_host")
    return target_host


def set_target_host(new_target_host):
    conf_parser = ConfigParser.RawConfigParser()
    conf_parser.read(config_file)

    conf_parser.set("client", "target_host", new_target_host)
    with open(config_file, 'wb') as cff:
            conf_parser.write(cff)


def get_custom_ops():
    conf_parser = ConfigParser.RawConfigParser()
    conf_parser.read(config_file)
    custom_ops = ast.literal_eval(conf_parser.get("client", "custom_ops"))
    return custom_ops


def get_config_password():
    conf_parser = ConfigParser.RawConfigParser()
    conf_parser.read(config_file)
    return conf_parser.get("client", "password")


def set_config_password(new_password):
    conf_parser = ConfigParser.RawConfigParser()
    conf_parser.read(config_file)

    if " " in new_password:
        raise InvalidCredentialsError("Password can't contain spaces")

    conf_parser.set("client", "password", new_password)
    with open(config_file, 'wb') as cff:
            conf_parser.write(cff)


def main():

    # TODO Deal with switches and argv - possibly use argparse
    switch = sys.argv[1].replace("-", "")

    custom_ops = get_custom_ops()

    if "setpass" in switch:
        set_config_password(sys.argv[2])

    elif "sethost" in switch:
        set_target_host(sys.argv[2])

    else:
        rc = RemoteClient()

        operation_function_mapping = {
            "rc": {"function": run_command, "args": (rc,)},
            "aco": {"function": add_custom_operation, "args": (rc,)},
            "ffo": {"function": open_in_firefox, "args": (rc,)},
            "cd": {"function": change_dir, "args": (rc,)},
            "ls": {"function": list_dir, "args": (rc,)},
            "gf": {"function": get_files, "args": (rc,)},
            "sf": {"function": send_files, "args": (rc,)},
            "sfi": {"function": send_files, "args": (rc, True)},
            "nu": {"function": create_new_user, "args": (rc,)}
        }

        if switch in operation_function_mapping:
            func = operation_function_mapping[switch]["function"]
            func_args = operation_function_mapping[switch]["args"]
            # noinspection PyCallingNonCallable
            func(*func_args)

        elif switch in custom_ops:
            operation = switch
            rc.send_msg(operation)

        elif "usettings" in switch:
            operation = "update_settings"
            rc.send_msg(operation)
            rc.send_msg(json.dumps((sys.argv[2], sys.argv[3])))

        elif "userver" in switch:
            operation = "update_server"
            rc.send_msg(operation)

        elif "restart" in switch:
            operation = "restart"
            rc.send_msg(operation)

        elif "shutdown" in switch:
            operation = "shutdown"
            rc.send_msg(operation)

        else:
            rc.send_msg("")

        print rc.receive_msg()
        rc.close_connection()


def check_for_config_file():
    """
    Checks if config file exists
        if not then create one

        defaults:
            Section - Option - Value

            user - password - abcdef
            user - custom_ops - {}
            user - target_host - current machine address
    """

    if sys.platform.startswith("win32"):
        config_storage = os.getenv("APPDATA")
    elif sys.platform.startswith("linux"):
        config_storage = os.path.expanduser('~')
    else:
        raise OSError("Unsupported OS")

    config_storage_dir = os.path.join(config_storage, ".remotes-data")
    if not os.path.isdir(config_storage_dir):
        os.mkdir(config_storage_dir)

    config_file_ = os.path.join(config_storage_dir, "client_data")

    if not os.path.isfile(config_file_):
        print "Config file {c} not found.\n  Creating new file {c}.".format(
            c=config_file_)
        with open(config_file_, "wb"):
            pass

        conf_parser = ConfigParser.RawConfigParser()
        section = "client"
        conf_parser.add_section(section)
        default_options = {
            "password": "abcdef",
            "custom_ops": "{}",
            "target_host": socket.gethostbyname(socket.gethostname())
        }

        for key in default_options.keys():
            conf_parser.set(section, key, default_options[key])
        with open(config_file_, 'a') as cff:
            conf_parser.write(cff)

    return config_file_


if __name__ == "__main__":
    config_file = check_for_config_file()
    main()

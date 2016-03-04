import socket
import sys
import os
import json
import struct
import cliser_shared


class MaxTriesExceededError(Exception):
    pass


class RemoteClient:

    def __init__(self, target_host=socket.gethostbyname("localhost")):
        self.target_host = target_host
        self.port = 9988
        self.socket = self.init_socket_connection()

        self.max_get_files_tries = 3
        self.data_rate = 32768
        self.struct_size = 8  # >Q
        self.struct_fmt = ">Q"
        self.timeout = 10  # seconds
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
            f_list = os.getcwd()
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


def main():

    rc = RemoteClient()
    # TODO Deal with switches and argv - possibly use argparse
    switches = map(lambda x: x.replace("-", ""), sys.argv[1:])

    if "rc" in switches:
        run_command(rc)

    elif "cd" in switches:
        operation = "change_dir"
        rc.send_msg(operation)
        instructions = rc.receive_msg()

        dir_list = json.loads(rc.receive_msg())
        print instructions
        print_list(dir_list)
        choice = raw_input()
        if choice.isdigit():
            rc.send_msg(dir_list[(int(choice)-1)])
        else:
            rc.send_msg(choice.lower())

        while choice != "q" and choice != "d":
            dir_list, err = json.loads(rc.receive_msg())
            print_list(dir_list)
            if err is not None:
                print err
            choice = raw_input()

            if choice.isdigit():
                rc.send_msg(dir_list[(int(choice)-1)])
            else:
                rc.send_msg(choice.lower())

    elif "ls" in switches:
        operation = "list_items_in_dir"
        rc.send_msg(operation)
        print_list(json.loads(rc.receive_msg()))

    elif "gf" in switches:
        get_files(rc)

    elif "sf" in switches:
        send_files(rc)

    elif "sfi" in switches:
        send_files(rc, interactive=True)

    elif "nu" in switches:
        create_new_user(rc)

    elif "us" in switches:
        operation = "updating_settings"
        rc.send_msg(operation)
        rc.send_msg(json.dumps((sys.argv[2], sys.argv[3])))

    elif "shutdown" in switches:
        operation = "shutdown"
        rc.send_msg(operation)

    else:
        rc.send_msg("")

    print rc.receive_msg()
    rc.close_connection()


if __name__ == "__main__":
    main()

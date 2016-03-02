import json
import hashlib


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
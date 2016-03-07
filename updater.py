import subprocess
import socket

if __name__ == "__main__":
    host = socket.gethostname()
    port = 9988
    server_not_running_code = 10061

    main_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    err_code = main_sock.connect_ex((host, port))
    main_sock.close()

    if err_code == server_not_running_code:  # server is not running
        update_command = ["git", "pull", "origin", "master"]
        p = subprocess.Popen(update_command)
        p.communicate()

        remote_server_command = ["python", "remote_server.py"]
        subprocess.Popen(remote_server_command)

    elif err_code == 0:
        raise ValueError("Can't update while server is currently running.")

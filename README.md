Remotes
=======
Native Python sockets for running commands remotely from one machine to another.  
Practicing sockets and trying out how no `from` imports feels 


## Installation ##

No installation required.   
Run **remote_server.py** in remote machine and then it's ready to receive commands from **remote_client.py**.

### Set host name ###

`remote_client.py -sethost hostname`  

### Run commands ###

`remote_client.py -rc calc`  
`remote_client.py -rc taskkill /f /im calc.exe`  
SUCCESS: The process "calc.exe" with PID 37360 has been terminated.

The output of the command will be returned to the client

### Change user directory in remote machine ###
`remote_client.py -cd`

### Display items in current user directory in remote machine ###
`remote_client.py -ls`

### Send file to remote machine in current server user directory ###
`remote_client.py -sf full_path_to_file`

### Retrieve file from remote machine in current server user directory ###
`remote_client.py -gf` will print a a list of files and prompt for file to retrieve

### Restart server ###
`remote_client.py -restart`

### Shutdown server ###
`remote_client.py -shutdown`
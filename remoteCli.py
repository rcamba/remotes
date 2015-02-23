"""
	remoteClient:
	send and receive data
	change directory
	run commands remotely -verify client
	
	
"""


import socket
from sys import argv
import os
import pickle
import json
from root import switchBoard, printNumberedList, chooseFromNumberedList, errorAlert, drawLoadingBar
from time import time, sleep



TARGET_HOST=socket.gethostbyname("SMLaptop")

PORT=9988
AVAILABLE_SWITCHES= ['a','s','c','r','g','gat','cm','ffo','o']
DATA_RATE=32768

def sendReq(sock, fileToRetrieve):
	
	try:
		
		# Connect to server and send data
		sock.connect((TARGET_HOST, PORT))
		sock.send( "getFile" +"\n" )
		sock.send( fileToRetrieve .encode('utf-8')+"\n")
		
		name = (sock.recv(DATA_RATE)).decode('utf-8')
		print encodeUniEscape(name)
		
		fileSize= int( sock.recv(DATA_RATE) ) 
		print str( fileSize/ 1048576) +" MB"
		
		
		f=open(name,'wb')
		data = sock.recv(DATA_RATE)
		
		dataRecv = len(data)
		f.write(data)
		
		prevPct=0
		while(dataRecv < fileSize):
			
			data = sock.recv(DATA_RATE)
			dataRecv = dataRecv + len(data)
			currPct=int((round( dataRecv/(fileSize*1.0) , 2))*100)
			if currPct!=prevPct:
				drawLoadingBar(str(currPct)+"%")
				prevPct=currPct
				
			f.write(data)
			
		print "\n"
		
		f.close()
			
	finally:
		sock.close()
		
	return (fileSize/ 1048576.0)


	
def createSockets( n ):
	socketList=[]
	
	for i in range(0,n):
		exec("socket_"+ str(i) +"=" + "socket.socket(socket.AF_INET, socket.SOCK_STREAM)" )
		exec("socketList.append(" + "socket_"+ str(i)  + ")" )
		
	return socketList
	


def initSocketConnection():
	mainSock= socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	print "Connecting to: ", TARGET_HOST, "on PORT: ", PORT
	mainSock.connect((TARGET_HOST, PORT))
	return mainSock

def encodeUniEscape(targ):
		return targ.encode('unicode_escape')
	
def createPrintableList(targList):	
	return map(encodeUniEscape, targList)

def getChoices(fileList):
	
	
	printNumberedList( createPrintableList(fileList) )
	choices=raw_input("Select the number of the file. Separate with commas: \n")	
	return choices.split(',')	
	
def getFilesToReceive(choiceList, switches):
	if len(choiceList)>0:
		chosenFiles=[]
		if ('a' in switches):
			chosenFiles=choiceList
			
			
		elif ('g' in switches or 'c' in switches):
			for i in getChoices(choiceList):
				chosenFiles.append( choiceList[int(i)-1])
			
	
	else:
		print "ERROR: Empty file list. No files in current directory."
		exit(1)
		
	return chosenFiles

def pullFiles(chosenFiles):
	startTime=time()			
	totalFileSize=0
	
	socketList= createSockets (len(chosenFiles))
	for i in range(0,len(socketList)):
		totalFileSize=totalFileSize+sendReq(socketList[i],chosenFiles[i])
		sleep(1)
		
	
	print totalFileSize, " MB"
	totalTime=time()-startTime
	print totalTime, " seconds", "( ", totalTime/60.0 , " minutes ) "
	print (totalFileSize/1.0)/(time()-startTime), " MB/s"

def getFiles(mainSock, switches):
	mainSock.send("retrieveFileList"+"\n")
	
	choiceList= json.loads(mainSock.recv(DATA_RATE))
	chosenFiles=getFilesToReceive(choiceList, switches)
	pullFiles(chosenFiles)
			
def changeRemoteDirectory(mainSock, switches):
	mainSock.send("changeDir"+"\n")
	currDir, dirList=pickle.loads(mainSock.recv( DATA_RATE))
	print "Current directory: ", currDir
	
	print "Available directories: "
	
	if 'cm' in switches:
		chosenDir=[]
		chosenDir.append(raw_input("Enter directory name: "))
	else:
		chosenDir=getFilesToReceive(dirList, switches)
	
	mainSock.send( chosenDir[0].encode("utf-8")+"\n")
	print mainSock.recv(DATA_RATE)

def sendFile(mainSock, switches, file):
	print "Sending ", file 
	mainSock.send("sendFile"+"\n")
	mainSock.send( argv[1] +"\n" )
	
	fileSize=os.path.getsize(argv[1])
	print str( fileSize/ 1048576) +" MB"
	mainSock.send(str(fileSize) +"\n")
	
	f=open(file,'rb')
	data= f.read(DATA_RATE)
	dataSent= len(data)
	mainSock.send( data )
	
	prevPct=0
	while(dataSent< fileSize):
		data= f.read(DATA_RATE)
		dataSent= dataSent+len(data)
		
		currPct=int((round( dataSent/(fileSize*1.0) , 2))*100)
		if currPct!=prevPct:
			drawLoadingBar(str(currPct)+"%")
			prevPct=currPct
		
		mainSock.send( data)
	
	f.close()
	print "File sent"
	
if __name__ == "__main__":
	
	mainSock=initSocketConnection()
	switches=switchBoard(argv)
	
	if(len(switches) >0):
		
		if( 'a' in switches or 'g' in switches): 
			"""
			a: retrieve all files
			g: select file(s) to retrieve
			"""
			getFiles(mainSock, switches)
			
		elif ( 'c' in switches or 'cm' in switches):
			changeRemoteDirectory(mainSock, switches)
			
			
		elif('s' in switches):
			try:
				file=argv[1]
			except IndexError:
				print "ERROR: Missing filename to send. Exiting program."
				exit(1)
			
			sendFile(mainSock, switches, file)
		
		elif ('gat' in switches):
			print "Running getAnimeTorrents.py"
			mainSock.send("runComm"+"\n")
			mainSock.send("C:\\Users\\Kevin\\Util\\resources\\getAnimeTorrents.py"+"\n")
			mainSock.send(""+"\n")
			print "Operation output:\n", mainSock.recv(DATA_RATE)
			
			
		elif('ffo' in switches):
			
			argv[1]=argv[1][ argv[1].index("www") : ]
			print "Opening link in firefox:", argv[1]
			mainSock.send("sysCall" + "\n")
			mainSock.send("firefox -new-tab " + "\"" + argv[1] + "\"" + "\n")
			
		
		elif('o' in switches):
			command=" ".join(map(str,argv[1:]))
			print argv
			print "Running command " + command
			mainSock.send("sysCall"+"\n")
			
			
			
			
			mainSock.send(command+"\n")
			#mainSock.send("firefox"+"\n")
			#argv[1]=argv[1][ argv[1].index("www") : ]
			#mainSock.send("firefox -new-tab "+ "\""+argv[1] +"\"" +"\n")
			
			
			
			
			
			print mainSock.recv(DATA_RATE)
	
	mainSock.close()
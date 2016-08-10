#!/usr/bin/python2
# encoding: utf-8

from threading import Thread
from multiprocessing import Queue
import sys, os, datetime, readline

from modules import bot, client, config

def init():
	global thread, log, userinput_queue
	
	#init log file
	if not os.path.exists(os.path.abspath("logs")):
	  os.makedirs('logs')
	log = open(datetime.datetime.now().strftime("logs/log_%Y-%m-%d-%H:%M"),'w')
	
	userinput_queue = Queue()
	
	#init user console
	thread = Thread(target = userinput, name = "Userinput")
	thread.daemon = True
	thread.start()
		
def userinput():
	readline.parse_and_bind("tab: complete")
	while 1:
		inputcmd=input()
		userinput_queue.put(inputcmd)

def run():
	try:
		cmd = userinput_queue.get(False)
		display(">"+cmd)
		try:
			exec(cmd)
		except Exception as e:
			display(str(e))
	except:
		pass
			
def display(text):
	text=datetime.datetime.now().strftime("(%H:%M:%S)")+str(text) # add date and time
	sys.stdout.write('\r'+' '*(len(readline.get_line_buffer())+2)+'\r')
	sys.stdout.write(text+'\r\n> ' + readline.get_line_buffer())
	sys.stdout.flush()
	log.write(str(text)+'\r\n')

def terminate():
	bot.terminate()
	log.close()
	client.terminate()
	print("QUIT NOW.")
	os._exit(0)

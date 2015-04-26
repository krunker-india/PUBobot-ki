#!/usr/bin/python2
# encoding: utf-8

import socket, fcntl, os, errno, time, traceback

import console, bot
from config import cfg

# SOCKET AND SYSTEM FUNCTIONS #

def init():
	global readbuffer, send_queue, disconnect_time, silent, lastsend, lastconnect, connected, ops
	
	silent = False
	readbuffer = ""
	send_queue = [] # Queue for sending messages
	connected = False
	disconnect_time = False
	lastsend = 0
	lastconnect = 0
	ops = []
		
def connect():
	global Socket, connected
	try:
		console.display("Connecting to {0}...".format(cfg['HOST']))
		Socket = socket.socket()
		Socket.connect((cfg['HOST'], cfg['PORT']))
		fcntl.fcntl(Socket, fcntl.F_SETFL, os.O_NONBLOCK)
		connected = True
		#Socket.send("NICK {0}\r\n".format(cfg['NICK']))
		#Socket.send("USER {0} {1} {2} :{3}\r\n".format(cfg['IDENT'], cfg['HOST'], cfg['SERVERNAME'], cfg['REALNAME']))
	except Exception,e:
		console.display(str(e)+", reconnect in 5 seconds...")
		Socket.close()
				
def reconnect():
	global disconnect_time
	disconnect_time = time.time()-15
	Socket.close()
	connect()
	
def recive():
	try:
		data = Socket.recv(2048)
		return data
	except Exception,e:
		if not e.args[0] in [errno.EAGAIN, errno.EWOULDBLOCK]:
			console.display("Socket excetion:"+str(e)+", reconnecting...")
			connected = False
		return False

def send(frametime):
	global lastsend
	if len(send_queue) > 0 and frametime - lastsend > 2:
		data = send_queue.pop(0)
		console.display(('>/'+data))
		#only display messages in silent mode
		if not silent or data[0:5] in ["NAMES", "PONG ", "JOIN ", "QUIT ", "AUTH "]:
			Socket.send(data)
			
		lastsend = frametime
				
def run(frametime):
	global readbuffer, connected, lastconnect, disconnect_time
	
	if not connected:
		if frametime - lastconnect > 5:
			lastconnect = frametime
			connect()
			
	else:
		data = recive()
		
		if data:
			readbuffer=readbuffer+data
			console.display(readbuffer)
			temp=readbuffer.split('\r\n')
			readbuffer=''
	
			#process recived messages
			for line in temp:
				l=line.rstrip().split(" ")
				
				if line == "NOTICE AUTH :*** Checking Ident":
					send_queue.append("NICK {0}\r\n".format(cfg['NICK']))
					send_queue.append("USER {0} {1} {2} :{3}\r\n".format(cfg['IDENT'], cfg['HOST'], cfg['SERVERNAME'], cfg['REALNAME']))
			
				elif(l[0]=="PING"):
					send_queue.append("PONG %s\r\n" % l[1].lstrip(":"))
				
				elif len(l)>2:

					if l[1]=="353":
						if l[4]==cfg['HOME']:
							parse_names(l[5:len(l)])
							
					elif(l[1]=="221"): #just connected, need to auth and join channels
						if cfg['PASSWORD']:
							send_queue.append("PRIVMSG Q@CServe.quakenet.org :AUTH {0} {1}\r\n".format(cfg['USERNAME'],cfg['PASSWORD']))
						for channel in cfg['SPAMCHANS'] + cfg['SECRETSHANS']:
							send_queue.append("JOIN {0}\r\n".format(channel))
						if disconnect_time: #warn players if we had a disconnect
							dtime=time.time()-disconnect_time
							notice("Having net problems. Was disconnected for ~{0} minutes.".format(str(int(dtime/60))))
							bot.reset_players()
							
					elif l[1]=="433": #nick is already in use, need to send another
						newnick = cfg['NICK'] + "_"
						send_queue.append("NICK {0}\r\n".format(newnick))
						cfg['NICK'] = newnick
					
					elif l[1]=="NICK": #someone changed nick, need to update added players
						nick = l[0].lstrip(":").split("!")[0].lower()
						newnick = l[2].lstrip(':').lower()
						console.display("NICK: {0} | NEWNICK: {1}".format(nick, newnick))
						bot.remove_player(nick, [], newnick)
						update_op_nick(nick, newnick)

					elif l[1]=="PART" and l[2]==cfg['HOME'] or l[1]=="QUIT": #someone left, need to update added players
						nick = l[0].lstrip(":").split("!")[0].lower()
						bot.remove_player(nick, [], False, True)
						remove_op(nick)

					elif l[1]=="/": #someone left or kicked us from a channel
						if l[2]==cfg['HOME']:
							if l[3]==cfg['NICK']:
								send_queue.append("JOIN {0}\r\n".format(cfg['HOME']))
							else:
								nick = l[3].lower()
								bot.remove_player(nick, [], False, True)
								remove_op(nick)
						elif l[3]==cfg['NICK']:
							remove_spam_channel([l[2]])
				
					elif l[1]=="MODE": #someone changed usermod, update names, update channel topic if we got +o
						if len(l)>4:
							if l[2] == cfg['HOME']:
								update_op_mode(l[3], l[4].lower())
								
							 	if l[3] == "+o" and l[4] == cfg['NICK']:
									bot.update_topic()
								
					elif l[1]=="PRIVMSG" and (l[2]==cfg['HOME'] or l[2] in cfg['SECRETSHANS']): #process user message on HOME channel with crash handling
						bot.processmsg(l)
						#pass
						
def terminate():
	console.display("Closing connection")
	try:
		Socket.send(":QUIT Quit\r\n")
	except: pass
		

# OP AND VOICE USERS TRACKING #

def parse_names(nameslist):
	nameslist = [i.lower() for i in nameslist]
	nameslist[0] = nameslist[0].lstrip(":")
	
	for i in nameslist:
		if i[0] in ['+', '@']:
			usermod = i[0]
			nick = i.lstrip(usermod)
		else:
			usermod = ''
			nick = i

		change = False
		for op in ops:
			if op[0] == nick:
				op[1] == usermod
				change = True
	
		if not change:
			ops.append([nick, usermod])

def update_op_mode(mode, nick):
	if mode[0] == "-":
		mode = ""
	else: #mode[0] = "+"
		if mode[1] == "v":
			mode = "+"
		elif mode[1] == "o":
			mode = "@"
		else:
			mode = ""
			
	for i in ops:
		if i[0] == nick:
			i[1] = mode
			return
	
	ops.append([nick, mode])
	
def update_op_nick(oldnick, newnick):
	for i in ops:
		if i[0] == oldnick:
			i[0] = newnick
			
def remove_op(nick):
	for i in ops:
		if i[0] == nick:
			ops.remove(i)
			return
	
def refresh_ops():
	global ops
	ops = []
	send_queue.append("NAMES {0}\r\n".format(cfg['HOME']))

# IRC HELPER FUNCTIONS #

def get_ip(nick):
	global readbuffer
	for i in ("WHOIS","WHOWAS"):
		data = "{0} {1}\r\n".format(i,nick)
		console.display(('>/'+data))
		Socket.send(data)
		
		#oldtime=time.time()
		time.sleep(0.5)
		try:
			data = recive()
			if data:
				readbuffer=readbuffer+data
				for line in readbuffer.split('\r\n'):
					line = line.lower()
					print(">>>" + line)
					if line.find("311 "+cfg['NICK'].lower())>0 or line.find("314 "+cfg['NICK'].lower())>0:
						return line.split(' ')[5]
		except:
			pass
	return False
	
def get_usermod(nick):
	for i in ops:
		if i[0] == nick:
			return i[1]
	return ""

def get_real_usermod(nick):
	global readbuffer
	send_queue.put("NAMES {0}\r\n".format(cfg['HOME']))
	oldtime=time.time()
	while 1:
		readbuffer=readbuffer+recive()
		for line in readbuffer.split("\n"):
			if line.find(nick)>0 and line.find("quakenet.org")>0:
				return line[line.find(nick)-1] #return usermod symbol
		if time.time()-oldtime>10:
			return False
		time.sleep(1)
			
def reply(nick, msg):
	send_queue.append('PRIVMSG {0} :{1}: {2}\r\n'.format(cfg['HOME'],nick,msg))
		
def notice(msg):
	send_queue.append('PRIVMSG {0} :{1}\r\n'.format(cfg['HOME'],msg))
	
def highlight(blacklist):
	nicks = [i[0] for i in ops if i[0] not in blacklist]
	if nicks != []:
		send_queue.append('PRIVMSG {0} :{1}\r\n'.format(cfg['HOME'], ' '.join(nicks)))
	send_queue.append('PRIVMSG {0} :Please !add to pickups!\r\n'.format(cfg['HOME']))
		
def promote(msg):
	for i in cfg['SPAMCHANS']:
		send_queue.append('PRIVMSG {0} :{1}\r\n'.format(i,msg))
			
def private_reply(nick, msg):
	send_queue.append('NOTICE {0} :{1}\r\n'.format(nick,msg))
	
def set_topic(topic):
	send_queue.append('TOPIC {0} :{1}\r\n'.format(cfg['HOME'],topic))

def add_spam_channel(nick, c):
	if c in cfg['SPAMCHANS']:
		private_reply(nick, '{0} channel is already in spam list.'.format(c))
	else:
		cfg['SPAMCHANS'].append(c)
		send_queue.append('JOIN {0}\r\n'.format(c))
		private_reply(nick, 'Added {0} channel to the spam list.'.format(c))
			
def remove_spam_channel(c, nick=False):
	if c in cfg['SPAMCHANS'] and c != cfg['HOME']:
		send_queue.append('PART {0}\r\n'.format(c))
		cfg['SPAMCHANS'].remove(c)
		if nick:
			private_reply(nick, 'Removed {0} channel from spam list.'.format(c))
	elif nick:
		private_reply(nick, 'Channel {0} is not in spam list.'.format(c))

def chanban(ip, duratation, reason):
	send_queue.append("PRIVMSG Q@CServe.quakenet.org :TEMPBAN {0} *!*@{1} {2}h {3}".format(cfg['HOME'],ip,duratation,reason))

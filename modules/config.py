#!/usr/bin/python2
# encoding: utf-8

import shutil, os
from modules import console, bot

def init(dirname=""):
	global cfg, channels
	
	#load config
	cfg = dict()
	f = open(dirname + 'config.cfg', 'r')
	for line in f.readlines():
		try:
			if line[0] != '#':
				a = line.split('=')
				var = a[0].strip();
				val = a[1].strip()
				cfg[var] = eval(val)
		except Exception as e:
			console.display("ERROR IN CONFIG FILE @ \"{0}\". Exception: {1}".format(line, str(e)))
			console.terminate()
	
	#search for channels
	for i in os.listdir('channels'):
		if i != 'default':
			bot.channels_list.append(i)

def new_channel(channel, admin):
	path = "channels/"+channel.id
	shutil.copytree("channels/default", path)
	c = bot.Channel(channel)
	c.cfg["ADMINID"] = admin.id
	bot.channels.append(c)

def delete_channel(channel):
	for i in bot.channels:
		if i.id == channel.id:
			bot.channels.remove(i)
			i.stats.close()
			oldpath = "channels/"+channel.id
			newpath = "trash/"+channel.id
			if os.path.exists(newpath):
				shutil.rmtree(newpath)
			shutil.move(oldpath, newpath)
			return True
	return False
			

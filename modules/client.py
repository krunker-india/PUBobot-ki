#!/usr/bin/python2
# encoding: utf-8
import discord
from modules import console, config, bot, stats3

def init(c):
	global silent, lastsend, send_queue, Client, ready
	
	silent = False
	send_queue = [] # Queue for sending messages
	lastsend = 0
	Client = c
	ready = False
	
def process_connection():
	global username, ready

	console.display('SYSTEM| Logged in as: {0}, ID: {1}'.format(Client.user.name, Client.user.id))

	channels = stats3.get_channels()
	for cfg in channels:
		discord_channel = Client.get_channel(cfg['channel_id'])
		if  discord_channel == None:
			console.display("SYSTEM| Could not find channel '{0}>{1}#' with CHANNELID '{2}'! Scipping...".format(cfg['server_name'], cfg['channel_name'], cfg['channel_id']))
			#todo: delete channel
		else:
			c = bot.Channel(discord_channel, cfg)
			bot.channels.append(c)
			console.display("SYSTEM| '{0}>{1}#' channel init successfull".format(c.cfg['server_name'], c.cfg['channel_name']))
	ready = True

def send(frametime):
	global lastsend, connected
	if len(send_queue) > 0 and frametime - lastsend > 1:
		destination, data = send_queue.pop(0)
		console.display('SEND| /{0}: {1}'.format(destination, data))
		#only display messages in silent mode
		if not silent:
			Client.send_message(destination, data)
			
		lastsend = frametime

def get_empty_servers():
	for serv in Client.servers:
		n=0
		for chan in serv.channels:
			if chan.id in [i.cfg['channel_id'] for i in bot.channels]:
				n=1
				break
		if not n:
			console.display("server name: {0}, id: {1}".format(serv.name, serv.id))

### api for bot.py ###
def find_role_by_name(channel, name):
	name = name.lower()
	for role in channel.server.roles:
		if name == role.name.lower():
			return role
	return None

def notice(channel, msg):
	send_queue.append(['msg', channel, msg])

def reply(channel, member, msg):
	send_queue.append(['msg', channel, "<@{0}>, {1}".format(member.id, msg)])
	
def private_reply(channel, member, msg):
	send_queue.append(['msg', member, msg])

def set_topic(channel, newtopic):
	send_queue.append(['topic', newtopic])
	
def get_member_by_nick(channel, nick):
	return discord.utils.find(lambda m: m.name == nick, channel.server.members)

def get_member_by_id(channel, highlight):
	memberid = highlight.lstrip('<@!').rstrip('>')
	return discord.utils.find(lambda m: m.id == memberid, channel.server.members)

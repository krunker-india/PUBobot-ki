#!/usr/bin/python2
# encoding: utf-8
import discord
from modules import console, config, bot

def init(c):
	global silent, lastsend, send_queue, Client
	
	silent = False
	send_queue = [] # Queue for sending messages
	lastsend = 0
	Client = c
	
def process_connection():
	global username, state

	console.display('SYSTEM| Logged in as:')
	console.display('SYSTEM| Name: '+Client.user.name)
	console.display('SYSTEM| Id: '+Client.user.id)
	console.display('------')

	for channelid in bot.channels_list:
		channel = Client.get_channel(channelid)
		if channel == None:
			console.display('SYSTEM| Could not found channel {0} with given CHANNELID...'.format(channel.name))
		else:
			c = bot.Channel(channel)
			bot.channels.append(c)
			console.display("SYSTEM| \"{0}\" channel init successfull".format(c.name))

def send(frametime):
	global lastsend, connected
	if len(send_queue) > 0 and frametime - lastsend > 2:
		destination, data = send_queue.pop(0)
		console.display('SEND| /{0}: {1}'.format(destination, data))
		#only display messages in silent mode
		if not silent:
			Client.send_message(destination, data)
			
		lastsend = frametime
						
def terminate():
	console.display("SYSTEM| Closing connection")
	yield from Client.logout()

### api for bot.py ###

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

def get_member_by_id(channel, memberid):
	memberid = memberid.lstrip('<@').rstrip('>')
	return discord.utils.find(lambda m: m.id == memberid, channel.server.members)

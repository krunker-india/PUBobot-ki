#!/usr/bin/python3
# encoding: utf-8
import os, time, sys, traceback
try:
	import discord, asyncio
except:
	print("Discord api not found, please install discord.py: https://github.com/Rapptz/discord.py")
	sys.exit(1)

#my modules
from modules import console, config, bot, client, scheduler, stats3

console.init()
scheduler.init()
bot.init()
stats3.init()
config.init()

#start discord api
c = discord.Client()
client.init(c)

@asyncio.coroutine
def bot_run():
	while not c.is_closed and console.alive:
		frametime = time.time()
		bot.run(frametime)
		scheduler.run(frametime)
		console.run()
		if not c.is_closed:
			if len(client.send_queue) > 0:
				data = client.send_queue.pop(0)
				if data[0] == 'msg':
					destination, content = data[1], data[2]
					console.display('SEND| /{0}: {1}'.format(destination, content))
					if not client.silent:
						try:
							yield from c.send_message(destination, content)
						except:
							console.display("ERROR| Could not send the message. "+str(sys.exc_info()))
				elif data[0] == 'topic':
					content = data[1]
					if not client.silent:
						try:
							yield from c.edit_channel(client.channel, topic=content)
						except:
							console.display("ERROR| Could not change topic."+str(sys.exc_info()))
				elif data[0] == 'leave_server':
					for serv in c.servers:
						if serv.id == data[1]:
							console.display("Leaving {0}...".format(serv.name))
							yield from c.leave_server(serv)
							break
		else:
			console.display("ERROR| Connection to server has been closed unexpectedly.")
			console.terminate()
		yield from asyncio.sleep(0.5) # task runs every 0.5 seconds
	#quit gracefully
	try:
		yield from Client.logout()
	except:
		pass
	console.log.close()
	print("QUIT NOW.")
	os._exit(0)

@c.event
@asyncio.coroutine
def on_ready():
	if not client.ready:
		client.process_connection()
		console.display("SYSTEM| Setting status message...")
		yield from c.change_presence(game=discord.Game(name='pm !help'))
		console.display("SYSTEM| Initialization complete!")
		loop.create_task(bot_run())
	else:
		console.display("DEBUG| Unexpected on_ready event!")
		yield from c.change_presence(game=discord.Game(name='pm !help'))
@c.event
@asyncio.coroutine
def on_message(message):
	if message.channel.is_private and message.author.id != c.user.id:
		console.display("PRIVATE| {0}>{1}>{2}: {3}".format(message.server, message.channel, message.author.display_name, message.content))
		client.send_queue.append(['msg', message.channel, config.cfg.HELPINFO])
	if message.content == '!enable_pickups':
		if message.channel.permissions_for(message.author).manage_channels:
			if message.channel.id not in [x.id for x in bot.channels]:
				newcfg = stats3.new_channel(message.server.id, message.server.name, message.channel.id, message.channel.name, message.author.id)
				bot.channels.append(bot.Channel(message.channel, newcfg))
				client.reply(message.channel, message.author, config.cfg.FIRST_INIT_MESSAGE)
			else:
				client.reply(message.channel, message.author, "this channel allready have pickups configured!")
		else:
			client.reply(message.channel, message.author, "You must have permission to manage channels to enable pickups.")
	elif message.content == '!disable_pickups':
		if message.channel.permissions_for(message.author).manage_channels:
			for chan in bot.channels:
				if chan.id == message.channel.id:
					stats3.delete_channel(message.channel.id)
					bot.channels.remove(chan)
					client.reply(message.channel, message.author, "pickups on this channel have been disabled.")
					return
			client.reply(message.channel, message.author, "pickups on this channel has not been set up yet!") 
		else:
			client.reply(message.channel, message.author, "You must have permission to manage channels to disable pickups.") 
	else:
		for channel in bot.channels:
			if message.channel.id == channel.id:
				console.display("CHAT| {0}>{1}>{2}: {3}".format(message.server, message.channel, message.author.display_name, message.content))
				try:
					channel.processmsg(message.content, message.author)
				except:
					console.display("ERROR| Error processing message: {0}".format(traceback.format_exc()))
					
	
@c.event
@asyncio.coroutine
def on_member_update(before, after):
	#console.display("DEBUG| {0} changed status from {1}  to -{2}-".format(after.name, before.status, after.status))
	if str(after.status) in ['idle', 'offline']:
		bot.update_member(after)

loop = asyncio.get_event_loop()

try:
	if config.cfg.DISCORD_TOKEN != "":
		console.display("SYSTEM| logging in with token...")
		loop.run_until_complete(c.login(config.cfg.DISCORD_TOKEN))
	else:
		console.display("SYSTEM| logging in with username and password...")
		loop.run_until_complete(c.login(config.cfg.USERNAME, config.cfg.PASSWORD))
	loop.run_until_complete(c.connect())
except Exception as e:
	console.display("ERROR| Disconnected from the server: "+str(e))
	loop.run_until_complete(c.close())
finally:
	loop.close()
	console.terminate()
	print("QUIT NOW.")
	os._exit(0)

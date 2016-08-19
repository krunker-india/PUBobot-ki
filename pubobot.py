#!/usr/bin/python3
# encoding: utf-8
import os, time, sys
try:
	import discord, asyncio
except:
	print("Discord api not found, please install discord.py: https://github.com/Rapptz/discord.py")
	sys.exit(1)

#my modules
from modules import console, config, bot, client, scheduler

console.init()
scheduler.init()
bot.init()
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
		else:
			console.display("ERROR| Connection to server has been closed unexpectedly.")
			console.terminate()
		yield from asyncio.sleep(0.5) # task runs every 0.5 seconds
	#quit gracefully
	try:
		yield from Client.logout()
	except:
		pass
	print("QUIT NOW.")
	os._exit(0)

@c.event
@asyncio.coroutine
def on_ready():
	client.process_connection()
	console.display("SYSTEM| Setting status message...")
	yield from c.change_status(game=discord.Game(name='pm !help'))
	console.display("SYSTEM| Initialization complete!")
	loop.create_task(bot_run())
@c.event
@asyncio.coroutine
def on_message(message):
	console.display("CHAT| {0}>{1}>{2}: {3}".format(message.server, message.channel, message.author.display_name, message.content))
	if message.channel.is_private and message.author.id != c.user.id:
		client.send_queue.append(['msg', message.channel, config.cfg.HELPINFO])
	elif message.content == '!enable_pickups':
		if message.channel.permissions_for(message.author).manage_channels:
			if message.channel.id not in [x.id for x in bot.channels]:
				config.new_channel(message.channel, message.author)
			else:
				client.reply(message.channel, message.author, "this channel allready have pickups configured!")
		else:
			client.reply(message.channel, message.author, "You must have permission to manage channels to enable pickups.")
	elif message.content == '!disable_pickups':
		if message.channel.permissions_for(message.author).manage_channels:
			if config.delete_channel(message.channel):
				client.reply(message.channel, message.author, "pickups on this channel have been disabled.") 
			else:
				client.reply(message.channel, message.author, "pickups on this channel has not been set up yet!") 
		else:
			client.reply(message.channel, message.author, "You must have permission to manage channels to disable pickups.") 
	else:
		for channel in bot.channels:
			if message.channel.id == channel.id:
				try:
					channel.processmsg(message.content, message.author)
				except:
					console.display("ERROR| Error processing message: "+str(sys.exc_info()))
	
@c.event
@asyncio.coroutine
def on_member_update(before, after):
	console.display("DEBUG| {0} changed status to -{1}-".format(after.name, after.status))
	if after.status.name in ['idle', 'offline']:
		for channel in bot.channels:
			channel.update_member(after)

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

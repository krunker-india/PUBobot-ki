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
bot.init()
config.init()

#start discord api
c = discord.Client()

@asyncio.coroutine
def bot_run():
	yield from c.wait_until_ready()
	console.display("Setting status message...")
	yield from c.change_status(game=discord.Game(name='pm !help'))
	client.init(c)
	while not c.is_closed:
		frametime = time.time()
		bot.run(frametime)
		console.run()
		if len(client.send_queue) > 0:
			data = client.send_queue.pop(0)
			if data[0] == 'msg':
				destination, content = data[1], data[2]
				console.display('>/{0}: {1}'.format(destination, content))
				try:
					yield from c.send_message(destination, content)
				except:
					print("ERROR: Could not send the message.")
					print(sys.exc_info())
			elif data[0] == 'topic':
				content = data[1]
				if not client.silent:
					try:
						yield from c.edit_channel(client.channel, topic=content)
					except:
						print("ERROR: Could not change topic.")
						print(sys.exc_info())
						
		yield from asyncio.sleep(0.5) # task runs every 0.5 seconds
	console.terminate()

@c.event
@asyncio.coroutine
def on_ready():
	client.process_connection()

@c.event
@asyncio.coroutine
def on_message(message):
	console.display("{0}>{1}>{2}: {3}".format(message.server, message.channel, message.author.display_name, message.content))
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
					print(sys.exc_info())
	
@c.event
@asyncio.coroutine
def on_member_update(before, after):
	print("-{0}-".format(after.status))
	print(type(after.status.name))
	if after.status.name in ['afk', 'offline']:
		for channel in bot.channels:
			channel.remove_player(after,[],after.status.name)

loop = asyncio.get_event_loop()

try:
	loop.create_task(bot_run())
	if config.cfg.DISCORD_TOKEN != "":
		console.display("logging in with token...")
		loop.run_until_complete(c.login(config.cfg.DISCORD_TOKEN))
	else:
		console.display("logging in with username and password...")
		loop.run_until_complete(c.login(config.cfg.USERNAME, config.cfg.PASSWORD))
	loop.run_until_complete(c.connect())
except Exception:
	console.display("ERROR: Disconnected from the server")
	loop.run_until_complete(c.close())
finally:
	loop.close()
	console.terminate()

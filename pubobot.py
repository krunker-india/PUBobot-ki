#!/usr/bin/python2
# encoding: utf-8
import os
import time

#my modules
from modules import console, config, bot, irc, scheduler

#start the bot
config.init()
scheduler.init()
irc.init()
bot.init()
console.init()

os.environ['TZ'] = config.cfg['TIMEZONE']
time.tzset()

while 1:
	frametime = time.time()
	
	irc.run(frametime)
	irc.send(frametime)
	scheduler.run(frametime)
	console.run()
	time.sleep(0.5)

#!/usr/bin/python2
# encoding: utf-8

import console, bot

def init():
	global pickups
	
	#load config
	f = open('config.cfg', 'r')
	for line in f.readlines():
		try:
			a = line.split('=')
			var = a[0].strip();
			if var in cfg:
				val = a[1].strip()
				cfg[var] = eval(val)
		except Exception,e:
			console.display("ERROR IN CONFIG FILE @ \"{0}\". Exception: {1}".format(line, str(e)))
	
	#load games list
	try:
		f = open('pickuplist','r')
		pickups = eval(f.read())
		f.close
	except:
		console.display("Pickups list import failed!")
		pickups = []

def save():
	global pickups
	# write gameslist
	console.display('Writing pickuplist file.')
	pickups=[]
	for i in bot.pickups:
		pickups.append((i.name,i.maxplayers,i.ip,i.default))
	f = open('pickuplist', 'w')
	syntax="# syntax: ('name','number_of_players,'ip','show_in_topic')\n"
	f.write(syntax + str(pickups).replace("), (", "),\n("))
	f.close()
	#write config file
	console.display('Writing config file.')
	cfgfile = open("config.cfg", "r")
	cfglines = cfgfile.readlines()
	for i in cfg:
		for line in cfglines:
			if line.find(i) == 0:
				if type(cfg[i]) == str:
					cfglines[cfglines.index(line)] =  i + " = \"" + str(cfg[i]) + "\"\n"
				else:
					cfglines[cfglines.index(line)] =  i + " = " + str(cfg[i]) + "\n"
  	cfgfile.close()
  	cfgfile = open("config.cfg", "w")
  	cfgfile.write("".join(cfglines))
  	cfgfile.close()

# DEFAULT SETTINGS #
cfg = {
	'HOST': "irc.quakenet.org",
	'PORT': 6667,
	'NICK': "^PUbossbot^",
	'IDENT': "pickup",
	'SERVERNAME': "irc.quakenet.org",
	'REALNAME': "Leshka's bot",
	'HOME': "#warsow.pickup",
	'SPAMCHANS': eval('[\'#warsow.pickup\', \'#warsow\']'),
	'SECRETSHANS': eval('[\'#warsow.admin\']'),
	'USERNAME': "wswpickup",
	'PASSWORD': "",
	'DEFAULTIP': "77.72.150.21:44400;password pickupftw",
	'MOTD': "do !help or !games | HOROSH duel cup 18.01 http://wswhorosh.tourney.cc/sign-ups/",
	'BANTIME': 2,
	'PICKUPS_IN_TOPIC': 6,
	'BACKUP_TIME': 6,
	'AUTOREMOVE_TIME': 180
}
gameslist = [('bomb', 10, '77.72.150.21:44400;password pickupftw', True)]

#!/usr/bin/python2
# encoding: utf-8

import console, bot, datetime, shutil, os

def init(dirname=""):
	global pickups
	
	#load config
	f = open(dirname + 'config.cfg', 'r')
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
		f = open(dirname + 'pickuplist','r')
		pickups = eval(f.read())
		f.close
	except:
		console.display("Pickups list import failed!")
		pickups = []
		
	if not os.path.exists("backups"):
		os.makedirs("backups")

def save(directory=""):
	global pickups
	# write gameslist
	console.display('Writing pickuplist file.')
	pickups=[]
	for i in bot.pickups:
		pickups.append((i.name,i.maxplayers,i.ip,i.default))
	f = open(directory + 'pickuplist', 'w')
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
  	cfgfile = open(directory + "config.cfg", "w")
  	cfgfile.write("".join(cfglines))
  	cfgfile.close()
  	
def backup(dirname):
	os.makedirs("backups/" + dirname)
	shutil.copyfile("stats.sql", "backups/{0}/stats.sql".format(dirname))
	save("backups/{0}/".format(dirname))
	console.display("Backup saved.")
	
	#delete old backups
	dirs = [i for i in os.listdir("backups") if i[0].isdigit()]
	delete_num = len(dirs) - cfg['KEEP_BACKUPS']
	if delete_num > 0:
		to_delete = sorted(dirs)[0:delete_num]
		for i in to_delete:
			shutil.rmtree('backups/{0}'.format(i))
	
def backup_load(dirname=False):
	if not dirname:
		try:
			dirs = [i for i in os.listdir("backups") if i[0].isdigit()]
			dirname = sorted(dirs, reverse=True)[0]
		except:
			return "No backups found"
	if os.path.exists("backups/" + dirname):
		bot.reset_players()
		bot.stats2.close()
		bot.stats2.init("backups/{0}/stats.sql".format(dirname))
		init("backups/{0}/".format(dirname))
		bot.init_pickups()
		return("Loaded backup {0}".format(dirname))
	else:
		return "Backup '{0}' not found!".format(dirname)
	

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
	'KEEP_BACKUPS': 10,
	'AUTOREMOVE_TIME': 180
}
gameslist = [('bomb', 10, '77.72.150.21:44400;password pickupftw', True)]

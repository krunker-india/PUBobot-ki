#!/usr/bin/python2
# encoding: utf-8

import time, datetime, re, traceback, random
from modules import client, config, console, stats2, scheduler

def init():
	global channels, channels_list
	channels = []
	channels_list = []

class Pickup():

	def __init__(self, name, maxplayers, ip):
		self.players = [] #[id, nick]
		self.maxplayers = int(maxplayers)
		self.name = str(name)
		self.ip = str(ip)

class Channel():

	def __init__(self, channel):
		self.channel = channel
		self.id = channel.id
		self.name = "{0}>{1}".format(channel.server.name,channel.name)
		self.cfg = dict()
		self.stats = stats2.Stats(self)
		self.cfg['CHANNEL_NAME'] = channel.name
		self.oldtime = 0
		self.pickups = []
		self.init_pickups()
		self.lastgame_cache = self.stats.lastgame()
		self.oldtopic = '[**no pickups**]'

		if self.cfg['FIRST_INIT'] == 'True':
			client.notice(self.channel, self.cfg['FIRST_INIT_MESSAGE'])
			self.cfg['FIRST_INIT'] = 'False'
		#scheduler.add_task(self.id+"#backup#", config.cfg['BACKUP_TIME'])
		
	def init_pickups(self):
		for i in eval(self.cfg["PICKUP_LIST"]):
			try:
				self.pickups.append(Pickup(i[0],i[1],i[2]))
			except:
				console.display("ERROR| Failed to parse a pickup of channel {0} @ {1}.".format(self.id, str(i)))
			
	def start_pickup(self, pickup):
		players=tuple(pickup.players) #just to save the value
		if pickup.maxplayers > 2:
			caps=random.sample(players, 2)
			capsstr=" Captains will be: {0}.".format('<@'+'> and <@'.join([i.id for i in caps])+'>')
		else:
			caps=False
			capsstr=''

		ipstr = self.cfg['IP_FORMAT'].replace("%ip%", pickup.ip).replace("%password%", self.cfg['PICKUP_PASSWORD'])
		noticestr="{0}, {1}.{2}".format('<@'+'>, <@'.join([i.id for i in players])+'>', ipstr, capsstr)
		client.notice(self.channel, pickup.name+' pickup has been started!\r\n'+noticestr)

		for i in players:
			if self.id+i.id in scheduler.tasks.keys():
				scheduler.cancel_task(self.id+i.id)
			client.private_reply(self, i,"**{0}** pickup has been started, {1}.{2}".format(pickup.name, ipstr, capsstr))
			for pu in ( pu for pu in self.pickups if i.id in [x.id for x in pu.players]):
				pu.players.remove(i)

		self.stats.register_pickup(pickup.name, players, caps)
		self.lastgame_cache = self.stats.lastgame()
		self.update_topic()

	def processmsg(self, content, member): #parse PRIVMSG event
		msgtup = content.split(" ")
		lower = [i.lower() for i in msgtup]
		msglen = len(lower)
		if self.cfg['ADMINROLE'] in [i.name for i in member.roles] or member.id == self.cfg['ADMINID']:
			isadmin = True
		else:
			isadmin = False

		if lower[0]=="!add":
			self.add_player(member, lower[1:msglen])

		elif re.match("^\+..", lower[0]):
			lower[0]=lower[0].lstrip(":+")
			self.add_player(member, lower[0:msglen])

		elif lower[0]=="++":
			self.add_player(member, [])

		elif lower[0]=="!remove":
			self.remove_player(member, lower[1:msglen])

		elif re.match("^-..",lower[0]):
			lower[0]=lower[0].lstrip(":-")
			self.remove_player(member,lower[0:msglen])

		elif lower[0]=="--":
			self.remove_player(member,[])

		elif lower[0]=="!expire":
			self.expire(member,lower[1:msglen])

		elif lower[0]=="!remove_player" and msglen == 2:
			self.remove_players(member, lower[1], isadmin)

		elif lower[0]=="!who":
			self.who(member,lower[1:msglen])

		elif lower[0] in ["!games", "!pickups"]:
			self.replypickups(member)

		elif lower[0]=="!promote":
			self.promote_pickup(member,lower[1:2])
		
		elif lower[0]=="!lastgame":
			self.lastgame(member,msgtup[1:msglen])

		elif lower[0]=="!sub":
			self.sub_request(member)

		elif lower[0]=="!stats":
			self.getstats(member,msgtup[1:2])

		elif lower[0]=="!top":
			self.gettop(member, lower[1:msglen])

		elif lower[0]=="!add_pickups":
			self.add_games(member, msgtup[1:msglen], isadmin)

		elif lower[0]=="!remove_pickups":
			self.remove_games(member, lower[1:msglen], isadmin)

		elif lower[0]=="!set_ip" and msglen>2:
			self.setip(member, msgtup[1:msglen], isadmin)

		elif msgtup[0]=="!ip":
			self.getip(member,lower[1:2])

		elif lower[0]=="!noadd" and msglen>1:
			self.noadd(member, msgtup[1:msglen], isadmin)

		elif lower[0]=="!forgive" and msglen==2:
			self.forgive(member,msgtup[1], isadmin)

		elif lower[0]=="!noadds":
			self.getnoadds(member, msgtup[1:2])

		elif lower[0]=="!reset":
			self.reset_players(member, lower[1:msglen], isadmin)

		elif lower[0]=="!backup_save":
			self.backup_save(member, isadmin)

		elif lower[0]=="!backup_load" and msglen==2:
			self.backup_load(member, msgtup[1], isadmin)

		elif lower[0]=="!phrase":
			self.set_phrase(member, msgtup[1:msglen], isadmin)
		
		elif lower[0]=="!help":
			client.private_reply(self.channel, member, config.cfg.HELPINFO)
	
		elif lower[0]=="!commands":
			client.reply(self.channel, member, config.cfg.COMMANDS_LINK)

		elif lower[0]=="!set" and msglen>2:
			self.configure(member, lower[1], ' '.join(msgtup[2:msglen]), isadmin)
			
	### COMMANDS ###

	def add_player(self, member, target_pickups):
	#check delay between last pickup
		if self.lastgame_cache:
			if time.time() - self.lastgame_cache[1] < 60 and member.name in self.lastgame_cache[4]:
				client.reply(self.channel, member, "Get off me! Your pickup already started!")
	
		#check noadds and phrases
		l = self.stats.check_memberid(member.id)
		if l[0] == True: # if banned
			client.reply(self.channel, member, l[1])
			return

		changes = False
		#ADD GUY TO TEH GAMES
		for pickup in ( pickup for pickup in self.pickups if ((target_pickups == [] and len(pickup.players)>0) or pickup.name.lower() in target_pickups)):
			if not member.id in [i.id for i in pickup.players]:
				changes = True
				pickup.players.append(member)
				if len(pickup.players)==pickup.maxplayers:
					self.start_pickup(pickup)
					return
				elif len(pickup.players)==pickup.maxplayers-1 and pickup.maxplayers>2:
					client.notice(self.channel, "Only 1 player left for {0} pickup. Hurry up!".format(pickup.name))

		#update scheduler, reply a phrase and update topic
		if changes:
			if self.id+member.id in scheduler.tasks.keys():
					scheduler.cancel_task(self.id+member.id)
			if l[1] != False: # if have phrase
				client.reply(self.channel, member, l[1])
			self.update_topic()
			
	def remove_player(self, member,args,status='online'):
		changes = []
		allpickups = True

		#remove player from games
		for pickup in self.pickups:
			for player in pickup.players:
				if player.id == member.id:
					if args == [] or pickup.name.lower() in args:
						changes.append(pickup.name)
						pickup.players.remove(player)
					elif allpickups:
						allpickups = False

		#update topic and warn player
		if changes != []:
			self.update_topic()
			if status == 'scheduler':
				client.private_reply(self.channel, member, "You have been removed from all pickups as your !expire time ran off...")
			elif status == 'idle':
				client.private_reply(self.channel, member, "You have been removed from all pickups as your status went AFK...")
			elif status == 'offline':
				client.private_reply(self.channel, member, "You have been removed from all pickups as you went offline...")
			elif status == 'banned':
				client.private_reply(self.channel, member, "You have been removed from all pickups as you've been banned...")
			elif status == 'reset':
				if allpickups:
					client.private_reply(self.channel, member, "You have been removed from all pickups, pickups has been reset.")
				else:
					client.private_reply(self.channel, member, "You have been removed from {0} - pickups has been reset.".format(", ".join(changes)))
			elif status == 'admin':
				if allpickups:
					client.private_reply(self.channel, member, "You have been removed from all pickups by an admin.")
				else:
					client.private_reply(self.channel, member, "You have been removed from {0} by an admin.".format(", ".join(changes)))
			#if status == 'online':
			#if allpickups:
			#	client.private_reply(self.channel, member, "You have been removed from all pickups")
			#else:
			#	client.private_reply(self.channel, member, "You have been removed from {0}.".format(", ".join(changes)))

			#REMOVE !expire AUTOREMOVE IF HE IS REMOVED FROM ALL GAMES
			if allpickups and self.id+member.id in scheduler.tasks.keys():
				scheduler.cancel_task(self.id+member.id)

	def scheduler_remove(self, member):
		self.remove_player(member, [], 'scheduler')

	def remove_players(self, member, arg, isadmin):
		if isadmin:
			if re.match("^<@[0-9]+>$", arg):
				target = client.get_member_by_id(self.channel, arg)
				if target:
					self.remove_player(target, [], 'admin')
				else:
					client.reply(self.channel, member, "Could not found specified Member on the server, is the highlight valid?")
			else:
				client.reply(self.channel, member, "Argument must be a Member highlight.")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def who(self, member, args):
		templist=[]
		for pickup in ( pickup for pickup in self.pickups if pickup.players != [] and (pickup.name.lower() in args or args == [])):
			templist.append('[**{0}**] {1}'.format(pickup.name, '/'.join([i.name for i in pickup.players])))
		if templist != []:
			client.notice(self.channel, ' '.join(templist))
		else:
			client.notice(self.channel, 'no one added...ZzZz')

	def lastgame(self, member, args):
		if args != []:
			l = self.stats.lastgame(args[0]) # number, ago, gametype, players, caps
		else:
			l = self.lastgame_cache
		if l:
			n = l[0]
			ago = datetime.timedelta(seconds=int(time.time() - int(l[1])))
			gt = l[2]
			caps = ", ".join(l[3])
			players = ", ".join(l[4])
			client.notice(self.channel, "Pickup #{0}, {1} ago [{2}]: {3}. Caps: {4}".format(n, ago, gt, players, caps))
		else:
			client.notice(self.channel, "No pickups found.")

	def sub_request(self, member):
		ip = self.cfg['DEFAULT_IP']

		if self.lastgame_cache:
			self.newtime=time.time()
			if self.newtime-self.oldtime>60:
				for i in ( i for i in self.pickups if i.name == self.lastgame_cache[2]):
					ip = i.ip
					client.notice(self.channel, "SUB NEEDED for {0} pickup! Please connect {1} !".format(self.lastgame_cache[2],ip))
				self.oldtime=self.newtime
			else:
				client.reply(self.channel, member,"Only one promote per minute! You have to wait {0} secs.".format(int(60-(self.newtime-self.oldtime))))
		else:
			client.reply(self.channel, member, "No pickups played yet.")

	def update_topic(self):
		newtopic=''

		sort=sorted(self.pickups,key=lambda x: len(x.players), reverse=True)
		strlist = []
		for i in ( i for i in sort if i.players):
			strlist.append("**{0}** ({1}/{2})".format(i.name,len(i.players),i.maxplayers))
		newtopic="[{0}]".format(" | ".join(strlist))

		if newtopic == "[]":
			newtopic="[**no pickups**]"
		if newtopic != self.oldtopic:
			client.notice(self.channel, newtopic)
			self.oldtopic=newtopic

	def replypickups(self, member):
		if self.pickups != []:
			s=[]
			for i in self.pickups:
				s.append("**{0}** ({1}/{2})".format(i.name,len(i.players),i.maxplayers))
			s = ' | '.join(s)

			client.notice(self.channel, s)
		else:
			client.notice(self.channel, "No pickups configured on this channel")

	def promote_pickup(self, member,arg):
		self.newtime=time.time()
		if self.newtime-self.oldtime>60:
			if arg != []:
				for pickup in ( pickup for pickup in self.pickups if [pickup.name] == arg ):
					client.notice(self.channel, "Please !add {0}, {1} players to go!".format(pickup.name,pickup.maxplayers-len(pickup.players)))
			else:
				client.notice(self.channel, "Please !add to pickups!")
			self.oldtime=self.newtime
		else:
			client.reply(self.channel, member,"Only one promote per minute! You have to wait {0} secs.".format(int(60-(self.newtime-self.oldtime))))

	def expire(self, member,timelist):
		added = False
		for players in [i.players for i in self.pickups]:
			if member.id in [i.id for i in players]:
				added = True;
				break
		if not added:
			client.reply(self.channel, member, "You must be added first!")
			return
			
		#set expire if time is specified
		if timelist != []:
			#calculate the time
			timeint=0
			for i in timelist: #convert given time to float
				try:
					num=float(i[:-1]) #the number part
					if i[-1]=='h':
						timeint+=num*3600
					elif i[-1]=='m':
						timeint+=num*60
					elif i[-1]=='s':
						timeint+=num
					else:
						raise Exception("doh!")
				except:
					client.reply(self.channel, member, "Bad argument @ \"{0}\", format is: !expire 1h 2m 3s".format(i))
					return

			#apply given time
			if timeint>0 and timeint<115200: #restart the scheduler task, no afk check task for this guy
				if self.id+member.id in scheduler.tasks.keys():
					scheduler.cancel_task(self.id+member.id)
				scheduler.add_task(self.id+member.id, timeint, self.scheduler_remove, (member, ))
				client.reply(self.channel, member, "You will be removed in {0}".format(str(datetime.timedelta(seconds=int(timeint)))))
			else:
				client.reply(self.channel, member, "Invalid time amount")

		#return expire time	if no time specified
		else:
			if not self.id+member.id in scheduler.tasks.keys():
				client.reply(self.channel, member, "No !expire time is set. You will be removed on your AFK status.")
				return

			timeint=scheduler.tasks[self.id+member.id][0]
			
			client.reply(self.channel, member, "You will be removed in {0}".format(str(datetime.timedelta(seconds=int(timeint-time.time()))),))

	def getstats(self, member,target):
		if target == []:
			s = self.stats.stats()
		else:
			s = self.stats.stats(target[0])
		client.notice(self.channel, s)

	def gettop(self, member, arg):
		if arg == []:
			top10=self.stats.top()
			client.notice(self.channel, "Top 10 of all time: "+top10)

		elif arg[0] == "weekly":
			timegap = int(time.time()) - 604800
			top10=self.stats.top(timegap)
			client.notice(self.channel, "Top 10 of the week: "+top10)

		elif arg[0] == "monthly":
			timegap = int(time.time()) - 2629744
			top10=self.stats.top(timegap)
			client.notice(self.channel, "Top 10 of the month: "+top10)

		elif arg[0] == "yearly":
			timegap = int(time.time()) - 31556926
			top10=self.stats.top(timegap)
			client.notice(self.channel, "Top 10 of the year: "+top10)

		else:
			client.reply(self.channel, member, "Bad argument.")

	def getnoadds(self, member, args):
		if args == []:
			l = self.stats.noadds()
		elif args[0][0] == '#':
			l = self.stats.noadds(False, args[0].lstrip('#'))
		else:
			target = client.get_member_by_nick(self.channel, args[0])
			if target:
				l = self.stats.noadds(target.id, False)
			else:
				client.reply(self.channel, member, "Member '{0}' not found".format(args[0]))
				return
		for i in l:
			client.notice(self.channel, i)

	def add_games(self, member, targs, isadmin):
		if isadmin:
			newpickups = []
			for i in range(0,len(targs)):
				try:
					name,players = targs[i].split(":")
					if int(players) > 1:
						if name not in [i.name for i in self.pickups]:
							newpickups.append([name, int(players)])
						else:
							client.reply(self.channel, member, "Pickup with name '{0}' allready exists!".format(name))
					else:
						client.reply(self.channel, member, "Players number must be more than 1, dickhead")
				except:
					client.reply(self.channel, member, "Bad argument @ {0}".format(i))
			if newpickups != []:
				for i in newpickups:
					self.pickups.append(Pickup(i[0], i[1], self.cfg['DEFAULT_IP']))
				self.replypickups(member)
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def remove_games(self, member, args, isadmin):
		if isadmin:
			toremove = [ pickup for pickup in self.pickups if pickup.name.lower() in args ]
			for i in toremove:
				self.pickups.remove(i)
			self.replypickups(member)
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def setip(self, member, args, isadmin):
		if isadmin:
			try:
				pickupnames,gameip=' '.join(args).split(' : ',1)
				pickupnames = pickupnames.split(" ")
			except:
				client.reply(self.channel, member, "Bad arguments")
				return

			affected_pickups = []
			for pickup in ( pickup for pickup in self.pickups if ( 'default' in pickupnames and pickup.ip == self.cfg['DEFAULT_IP']) or pickup.name in pickupnames):
				if gameip=='default':
					gameip=self.cfg['DEFAULT_IP']
				pickup.ip=gameip
				affected_pickups.append(pickup.name)

			if "default" in pickupnames:
				self.cfg['DEFAULT_IP']=gameip
				if affected_pickups != []:
					client.notice(self.channel, "Changed ip to '{0}' for {1}, and set it for default.".format(gameip, ' '.join(affected_pickups)))
				else:
					client.notice(self.channel, "Changed default ip to '{0}'.".format(gameip))
			elif affected_pickups != []:
				client.notice(self.channel, "Changed ip to '{0}' for {1}.".format(gameip, ' '.join(affected_pickups)))
			else:
				client.reply(self.channel, member, "No such pickups were found.")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def getip(self, member, args): #GET IP FOR GAME
		# find desired parameter
		if args != []:
			pickup_or_ip = args[0]
		else:
			l = self.lastgame_cache
			if l:
				pickup_or_ip = l[2]
			else:
				client.notice(self.channel, "No pickups played yet.")
				return

		# find desired info
		if pickup_or_ip  == 'default':
			client.notice(self.channel, 'Default ip is {0} and it is currently set for {1} pickups'.format(self.cfg['DEFAULT_IP'], str([x.name for x in self.pickups if x.ip == self.cfg['DEFAULT_IP']])))
			return

		n=0
		for pickup in self.pickups:
			if pickup.name == pickup_or_ip:
				client.notice(self.channel, 'Ip for {0} is {1}'.format(pickup.name, pickup.ip))
				n=1

		if not n:
			client.reply(self.channel, member, 'No such game or ip')

	def set_phrase(self, member, args, isadmin):
		if isadmin:
			if len(args) >= 2:
				targetid = args[0]
				if re.match("^<@[0-9]+>$", targetid):
					target = client.get_member_by_id(self.channel, targetid)
					if target:
						phrase = ' '.join(args[1:len(args)])
						self.stats.set_phrase(target, phrase)
						client.reply(self.channel, member, "Phrase has been set.")
					else:
						client.reply(self.channel, member, "Could not found specified Member on the server, is the highlight valid?")
				else:
					client.reply(self.channel, member, "Target must be a Member highlight.")
			else:
				client.reply(self.channel, member, "This command needs more arguments.")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def noadd(self, member, args, isadmin):
		if isadmin:
			reason = ''
			duratation = int(self.cfg['BANTIME'])

			targetid = args.pop(0)
			if re.match("^<@[0-9]+>$", targetid):
				target = client.get_member_by_id(self.channel, targetid)
				i=0
				while len(args):
					i += 1
					arg = args.pop(0)
				
					if i == 1 and arg.isdigit() == True:
						duratation = int(arg)
					
					elif arg in ["-t", "--time"]:
						try:
							duratation = int(args.pop(0))
						except:
							client.reply(self.channel, member,"Bad duratation argument.")
							return
					
					elif arg in ["-r", "--reason"]:
						l=[]
						while len(args):
							if args[0][0:1] != '-':
								l.append(args.pop(0))
							else:
								break
						reason = " ".join(l)

					else:
						client.reply(self.channel, member, "Bad argument @ '{0}'. Usage !noadd $nick [$time] [--time|-t $time] [--reason|-r $reason]".format(arg))
						return
					
			else:
				client.reply(self.channel, member, "Target must be a Member highlight.")
				return

			if abs(duratation) > 10000:
				client.reply(self.channel, member,"Max ban duratation is 10000 hours.")
				return

			if target:
				self.remove_player(target,[],'banned')
				s = self.stats.noadd(target, duratation, member.name, reason)
				client.notice(self.channel, s)
			else:
				client.reply(self.channel, member, "Could not found specified Member on the server, is the highlight valid?")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def forgive(self, member, arg, isadmin):
		if isadmin:
			if re.match("^<@[0-9]+>$", arg):
				target = client.get_member_by_id(self.channel, arg)
				if target:
					s = self.stats.forgive(target, member.name)
					client.reply(self.channel, member, s)
				else:
					client.reply(self.channel, member, "Could not found specified Member on the server, is the highlight valid?")
			else:
				client.reply(self.channel, member, "Target must be a Member highlight.")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def reset_players(self, member=False, args=[], isadmin=False):
		if member == False or isadmin:
			removed = []
			for pickup in self.pickups:
				if pickup.name in args or args == []:
					for player in pickup.players:
						if not player in removed:
							removed.append(player)
					pickup.players = []
			if removed != []:
				for player in removed:
					allpickups = True
					for pickup in self.pickups:
						if player in pickup.players:
							allpickups = False
					if allpickups and self.id+player.id in scheduler.tasks.keys():
						scheduler.cancel_task(self.id+player.id)
				if args == []:
					client.notice(self.channel, "{0} was removed from all pickups!".format('<@'+', <@'.join([i.id+'>' for i in removed])))
				elif len(args) == 1:
					client.notice(self.channel, "{0} was removed from {1} pickup!".format('<@'+', <@'.join([i.id+'>' for i in removed]), args[0]))
				else:
					client.notice(self.channel, "{0} was removed from {1} pickups!".format('<@'+', <@'.join([i.id+'>' for i in removed]), ', '.join(args)))
				self.update_topic()
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def backup_save(self, member, isadmin):
		if isadmin:
			name = member.name + datetime.datetime.now().strftime("%Y-%m-%d-%H:%M")
			config.backup_channel(self, name)
			client.reply(self.channel, member, "Backup saved to backups/{0}. Use !backup_load {0} to restore.".format(name))
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def backup_load(self, member, name, isadmin):
		if isadmin:
			if config.load_backup_channel(self, name):
				client.reply(self.channel, member, "Backup successfully loaded! All pickups has been reset!")
			else:
				client.reply(self.channel, member, "specified backup not found!")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def scheduler_backup(self):
		dirname = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M")
		config.backup(self.channel, dirname)
		scheduler.add_task(self.id+"#backup#", int(self.cfg['BACKUP_TIME']) * 60 * 60, self.scheduler_backup, ())
			
	def update_member(self, member):
		if member.status.name == 'offline':
			self.remove_player(member,[],'offline')
		elif member.status.name == 'idle' and not self.id+member.id in scheduler.tasks.keys():
			self.remove_player(member,[],'idle')

	def configure(self, member, var, value, isadmin):
		if isadmin:
			if var == "adminrole":
				self.cfg["ADMINROLE"] = value
				client.reply(self.channel, member, "done.")

			elif var == "pickup_password":
				self.cfg["PICKUP_PASSWORD"] = value
				client.reply(self.channel, member, "done.")

			elif var == "ip_format":
				self.cfg["IP_FORMAT"] = value
				client.reply(self.channel, member, "done, now message will look like: **example** pickup has been started, {0}".format(self.cfg['IP_FORMAT'].replace("%ip%", self.cfg['DEFAULT_IP']).replace("%password%", self.cfg['PICKUP_PASSWORD'])))

			elif var == "change_topic":
				if value in ['0', '1']:
					self.cfg["CHANGE_TOPIC"] = value
					client.reply(self.channel, member, "done.")
				else:
					client.reply(self.channel, member, "value for CHANGE_TOPIC should be 0 or 1.")

			elif var == "bantime":
				try:
					x = int(value)
					if x > 0:
						if x <= 10000:
							self.cfg["BANTIME"] = value
							client.reply(self.channel, member, "done.")
						else:
							client.reply(self.channel, member, "maximum BANTIME value is 10000.")
					else:
						client.reply(self.channel, member, "BANTIME value should be higher than 0.")
				except:
					client.reply(self.channel, member, "BANTIME value should be an integrer.")

			else:
				client.reply(self.channel, member, "variable \'{0}\' is not configurable.".format(var))
					
		else:
			client.reply(self.channel, member, "You have no right for this!")

def run(frametime):
	pass

def terminate():
	for channel in channels:
		console.display("SYSTEM| Saving channel \"{0}\"...".format(channel.name))
		channel.stats.save_config(channel.cfg, channel.pickups)
		channel.stats.close()

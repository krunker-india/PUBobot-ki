#!/usr/bin/python2
# encoding: utf-8

import time, datetime, re, traceback, random
from modules import client, config, console, stats2, scheduler, utils

def init():
	global channels, channels_list
	channels = []
	channels_list = []

class Pickup():

	def __init__(self, name, maxplayers, ip, promotion_role, whitelist_role, blacklist_role):
		self.players = [] #[id, nick]
		self.maxplayers = maxplayers
		self.name = name
		self.ip = ip
		self.promotion_role = promotion_role
		self.whitelist_role = whitelist_role
		self.blacklist_role = blacklist_role

class Channel():

	def __init__(self, channel):
		self.channel = channel
		self.id = channel.id
		self.name = "{0}>{1}".format(channel.server.name,channel.name)
		self.cfg = dict()
		self.stats = stats2.Stats(self)
		self.update_config('CHANNEL_NAME', channel.name)
		self.oldtime = 0
		self.pickups = []
		self.init_pickups()
		self.lastgame_cache = self.stats.lastgame()
		self.oldtopic = '[**no pickups**]'

		if self.cfg['FIRST_INIT'] == 'True':
			client.notice(self.channel, config.cfg.FIRST_INIT_MESSAGE)
			self.update_config('FIRST_INIT', 'False')
		#scheduler.add_task(self.id+"#backup#", config.cfg['BACKUP_TIME'])
		
	def init_pickups(self):
		for i in self.stats.pickup_table:
			try:
				self.pickups.append(Pickup(*i))
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
		if len(players) > 4:
			client.notice(self.channel, pickup.name+' pickup has been started!\r\n'+noticestr)
		else:
			client.notice(self.channel, pickup.name+' pickup has been started! '+noticestr)

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

		if re.match("^\+..", lower[0]):
			lower[0]=lower[0].lstrip(":+")
			self.add_player(member, lower[0:msglen])

		elif lower[0]=="++":
			self.add_player(member, [])

		elif re.match("^-..",lower[0]):
			lower[0]=lower[0].lstrip(":-")
			self.remove_player(member,lower[0:msglen])

		elif lower[0]=="--":
			self.remove_player(member,[])

		prefix, lower[0] = lower[0][0], lower[0][1:]
		if prefix == self.cfg["PREFIX"]:
			if lower[0]=="add":
				self.add_player(member, lower[1:msglen])

			elif lower[0]=="remove":
				self.remove_player(member, lower[1:msglen])

			elif lower[0]=="expire":
				self.expire(member,lower[1:msglen])

			elif lower[0]=="default_expire":
				self.default_expire(member,lower[1:msglen])

			elif lower[0]=="remove_player" and msglen == 2:
				self.remove_players(member, lower[1], isadmin)

			elif lower[0]=="who":
				self.who(member,lower[1:msglen])

			elif lower[0] in ["games", "pickups"]:
				self.replypickups(member)

			elif lower[0]=="pickups_list":
				self.replypickups_list(member)

			elif lower[0]=="promote":
				self.promote_pickup(member,lower[1:2])
		
			elif lower[0]=="lastgame":
				self.lastgame(member,msgtup[1:msglen])

			elif lower[0]=="sub":
				self.sub_request(member)

			elif lower[0]=="stats":
				self.getstats(member,msgtup[1:2])

			elif lower[0]=="top":
				self.gettop(member, lower[1:msglen])

			elif lower[0]=="add_pickups":
				self.add_games(member, msgtup[1:msglen], isadmin)

			elif lower[0]=="remove_pickups":
				self.remove_games(member, lower[1:msglen], isadmin)

			elif lower[0]=="set_ip" and msglen>2:
				self.setip(member, msgtup[1:msglen], isadmin)

			elif lower[0]=="promotion_role" and msglen>2:
				self.set_promotion_role(member, msgtup[1:msglen], isadmin)

			elif lower[0]=="whitelist_role" and msglen>2:
				self.set_whitelist_role(member, msgtup[1:msglen], isadmin)

			elif lower[0]=="blacklist_role" and msglen>2:
				self.set_blacklist_role(member, msgtup[1:msglen], isadmin)

			elif msgtup[0]=="ip":
				self.getip(member,lower[1:2])

			elif lower[0]=="noadd" and msglen>1:
				self.noadd(member, msgtup[1:msglen], isadmin)

			elif lower[0]=="forgive" and msglen==2:
				self.forgive(member,msgtup[1], isadmin)

			elif lower[0]=="noadds":
				self.getnoadds(member, msgtup[1:2])

			elif lower[0]=="reset":
				self.reset_players(member, lower[1:msglen], isadmin)

			elif lower[0]=="backup_save":
				self.backup_save(member, isadmin)

			elif lower[0]=="backup_load" and msglen==2:
				self.backup_load(member, msgtup[1], isadmin)

			elif lower[0]=="phrase":
				self.set_phrase(member, msgtup[1:msglen], isadmin)
	#		
	#		elif lower[0]=="help":
	#			client.private_reply(self.channel, member, config.cfg.HELPINFO)
	
			elif lower[0]=="commands":
				client.reply(self.channel, member, config.cfg.COMMANDS_LINK)

			elif lower[0]=="set" and msglen>2:
				self.configure(member, lower[1], ' '.join(msgtup[2:msglen]), isadmin)

			elif lower[0]=="show_config":
				self.show_config(member)
			
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
		for pickup in ( pickup for pickup in self.pickups if ((target_pickups == [] and len(pickup.players)>0 and int(self.cfg["++_REQ_PLAYERS"])<=pickup.maxplayers) or pickup.name.lower() in target_pickups)):
			if not member.id in [i.id for i in pickup.players]:
				#check if pickup have blacklist or whitelist
				if pickup.blacklist_role in [r.name for r in member.roles]:
					client.reply(self.channel, member, "You are not allowed to play {0} (blacklisted).".format(pickup.name))
				elif pickup.whitelist_role == 'none' or pickup.whitelist_role in [r.name for r in member.roles]:
					changes = True
					pickup.players.append(member)
					if len(pickup.players)==pickup.maxplayers:
						self.start_pickup(pickup)
						return
					elif len(pickup.players)==pickup.maxplayers-1 and pickup.maxplayers>2:
						client.notice(self.channel, "Only 1 player left for {0} pickup. Hurry up!".format(pickup.name))
				else:
					client.reply(self.channel, member, "You are not allowed to play {0} (not in whitelist).".format(pickup.name))

		#update scheduler, reply a phrase and update topic
		if changes:
			seconds = self.stats.get_expire(member.id)
			if seconds != 0:
				if self.id+member.id in scheduler.tasks.keys():
					scheduler.cancel_task(self.id+member.id)
				scheduler.add_task(self.id+member.id, seconds, self.scheduler_remove, (member, ))
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
				client.reply(self.channel, member, "you have been removed from all pickups as your !expire time ran off...")
			elif status == 'idle':
				client.notice(self.channel, "<@{0}> went AFK and was removed from all pickups...".format(member.id))
			elif status == 'offline':
				client.notice(self.channel, "{0} went offline and was removed from all pickups...".format(member.name))
			elif status == 'banned':
				client.notice(self.channel, "{0} have been removed from all pickups...".format(member.name))
			#elif status == 'reset':
			#	if allpickups:
			#		client.reply(self.channel, member, "You have been removed from all pickups, pickups has been reset.")
			#	else:
			#		client.reply(self.channel, member, "You have been removed from {0} - pickups has been reset.".format(", ".join(changes)))
			elif status == 'admin':
				if allpickups:
					client.reply(self.channel, member, "You have been removed from all pickups by an admin.")
				else:
					client.reply(self.channel, member, "You have been removed from {0} by an admin.".format(", ".join(changes)))
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
			if self.newtime-self.oldtime>int(self.cfg['PROMOTION_DELAY']):
				for i in ( i for i in self.pickups if i.name == self.lastgame_cache[2]):
					if i.promotion_role != 'none':
						client.notice(self.channel, "{0} SUB NEEDED for {1} pickup! Please connect {2} !".format(i.promotion_role,i.name,i.ip))
					else:
						client.notice(self.channel, "SUB NEEDED for {0} pickup! Please connect {1} !".format(i.name,i.ip))
				self.oldtime=self.newtime
			else:
				client.reply(self.channel, member,"You can't promote too often! You have to wait {0}.".format(str(datetime.timedelta(seconds=int(int(self.cfg['PROMOTION_DELAY'])-self.newtime+self.oldtime)))))
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

	def replypickups_list(self, member):
		str="name | players | ip | promotion role | blacklist role | whitelist role"
		for i in self.pickups:
			str+="\n{0} | {1} | {2} | {3} | {4} | {5}".format(i.name, i.maxplayers, i.ip, i.promotion_role, i.blacklist_role, i.whitelist_role)
		messages = utils.split_large_message(str)
		for i in messages:
			client.private_reply(self.channel, member, i)

	def promote_pickup(self, member,arg):
		self.newtime=time.time()
		if self.newtime-self.oldtime>int(self.cfg['PROMOTION_DELAY']):
			if arg != []:
				for pickup in ( pickup for pickup in self.pickups if [pickup.name.lower()] == arg ):
					if pickup.promotion_role != "none":
						client.notice(self.channel, "{0} please !add {1}, {2} players to go!".format(pickup.promotion_role,pickup.name,pickup.maxplayers-len(pickup.players)))
					else:
						client.notice(self.channel, "Please !add {0}, {1} players to go!".format(pickup.name,pickup.maxplayers-len(pickup.players)))
			else:
				if self.cfg['PROMOTION_ROLE'] != "none":
					client.notice(self.channel, "{0} please !add to pickups!".format(self.cfg['PROMOTION_ROLE']))
				else:
					client.notice(self.channel, "Please !add to pickups!")
			self.oldtime=self.newtime
		else:
			client.reply(self.channel, member,"You can't promote too often! You have to wait {0}.".format(str(datetime.timedelta(seconds=int(int(self.cfg['PROMOTION_DELAY'])-self.newtime+self.oldtime)))))

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
			try:
				timeint = utils.format_timestring(timelist)
			except Exception as e:
				client.reply(self.channel, member, str(e))
				return

			#apply given time
			if timeint>0 and timeint<=int(self.cfg['MAX_EXPIRE_TIME']): #restart the scheduler task, no afk check task for this guy
				if self.id+member.id in scheduler.tasks.keys():
					scheduler.cancel_task(self.id+member.id)
				scheduler.add_task(self.id+member.id, timeint, self.scheduler_remove, (member, ))
				client.reply(self.channel, member, "You will be removed in {0}".format(str(datetime.timedelta(seconds=int(timeint)))))
			else:
				client.reply(self.channel, member, "Invalid time amount. Maximum expire time on this channel is {0}".format(str(datetime.timedelta(seconds=int(int(self.cfg['MAX_EXPIRE_TIME'])))),))

		#return expire time	if no time specified
		else:
			if not self.id+member.id in scheduler.tasks.keys():
				client.reply(self.channel, member, "No !expire time is set. You will be removed on your AFK status.")
				return

			timeint=scheduler.tasks[self.id+member.id][0]
			
			client.reply(self.channel, member, "You will be removed in {0}".format(str(datetime.timedelta(seconds=int(timeint-time.time()))),))

	def default_expire(self, member, timelist):
		#print user default expire time
		if timelist == []:
			timeint = self.stats.get_expire(member.id)
			if timeint != 0:
				client.reply(self.channel, member, "Your default expire time is {0}".format(str(datetime.timedelta(seconds=int(timeint))),))
			else:
				client.reply(self.channel, member, "You will be removed on AFK status by default.")

		#set expire time to afk
		elif timelist[0] == 'afk':
			self.stats.set_expire(member.name, member.id, 0)
			client.reply(self.channel, member, "You will be removed on AFK status by default.")

		#format time string and set new time amount
		else:
			try:
				timeint = utils.format_timestring(timelist)
			except Exception as e:
				client.reply(self.channel, member, str(e))
				return
			if timeint>0 and timeint<=int(self.cfg['MAX_EXPIRE_TIME']):
				self.stats.set_expire(member.name, member.id, timeint)
				client.reply(self.channel, member, "set your default expire time to {0}".format(str(datetime.timedelta(seconds=int(timeint))),))
			else:
				client.reply(self.channel, member, "Invalid time amount. Maximum expire time on this channel is {0}".format(str(datetime.timedelta(seconds=int(int(self.cfg['MAX_EXPIRE_TIME'])))),))
				
			
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
					self.pickups.append(Pickup(i[0], i[1], self.cfg['DEFAULT_IP'], self.cfg['PROMOTION_ROLE'], 'none', 'none'))
				self.stats.update_pickups(self.pickups)
				self.replypickups(member)
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def remove_games(self, member, args, isadmin):
		if isadmin:
			toremove = [ pickup for pickup in self.pickups if pickup.name.lower() in args ]
			if len(toremove) > 0:
				for i in toremove:
					self.pickups.remove(i)
				self.stats.update_pickups(self.pickups)
				self.replypickups(member)
			else:
				client.reply(self.channel, member, "No such pickups found.")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def setip(self, member, args, isadmin):
		if isadmin:
			try:
				pickupnames,gameip=' '.join(args).split(' : ',1)
				pickupnames = pickupnames.lower().split(" ")
			except:
				client.reply(self.channel, member, "Bad arguments")
				return

			affected_pickups = []
			for pickup in ( pickup for pickup in self.pickups if ( 'default' in pickupnames and pickup.ip == self.cfg['DEFAULT_IP']) or pickup.name.lower() in pickupnames):
				if gameip=='default':
					gameip=self.cfg['DEFAULT_IP']
				pickup.ip=gameip
				affected_pickups.append(pickup.name)

			if "default" in pickupnames:
				self.update_config('DEFAULT_IP', gameip)
				if affected_pickups != []:
					self.stats.update_pickups(self.pickups)
					client.notice(self.channel, "Changed ip to '{0}' for {1}, and set it for default.".format(gameip, ' '.join(affected_pickups)))
				else:
					client.notice(self.channel, "Changed default ip to '{0}'.".format(gameip))
			elif affected_pickups != []:
				self.stats.update_pickups(self.pickups)
				client.notice(self.channel, "Changed ip to '{0}' for {1}.".format(gameip, ' '.join(affected_pickups)))
			else:
				client.reply(self.channel, member, "No such pickups were found.")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def set_promotion_role(self, member, args, isadmin):
		if isadmin:
			try:
				pickupnames,newrole=' '.join(args).split(' : ',1)
				pickupnames = pickupnames.lower().split(" ")
			except:
				client.reply(self.channel, member, "Bad arguments")
				return

			roleid = False
			if newrole == 'none':
				roleid = 'none'
			else:
				for i in self.channel.server.roles:
					if newrole == i.name:
						roleid = "<@&{0}>".format(i.id)

			if roleid != False:
				affected_pickups = []
				for pickup in ( pickup for pickup in self.pickups if ( 'default' in pickupnames and pickup.promotion_role == self.cfg['PROMOTION_ROLE']) or pickup.name.lower() in pickupnames):
					pickup.promotion_role=roleid
					affected_pickups.append(pickup.name)

				if "default" in pickupnames:
					self.update_config('PROMOTION_ROLE', roleid)
					if affected_pickups != []:
						self.stats.update_pickups(self.pickups)
						client.notice(self.channel, "Changed promotion role to '{0}' for {1}, and set it for default.".format(newrole, ' '.join(affected_pickups)))
					else:
						client.notice(self.channel, "Changed default promotion role to '{0}'.".format(newrole))
				elif affected_pickups != []:
					self.stats.update_pickups(self.pickups)
					client.notice(self.channel, "Changed promotion role to '{0}' for {1}.".format(newrole, ' '.join(affected_pickups)))
				else:
					client.reply(self.channel, member, "No such pickups were found.")
			else:
				client.reply(self.channel, member, "role '{0}' not found on this server.".format(newrole))
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def set_whitelist_role(self, member, args, isadmin):
		if isadmin:
			try:
				pickupnames,newrole=' '.join(args).split(' : ',1)
				pickupnames = pickupnames.lower().split(" ")
			except:
				client.reply(self.channel, member, "Bad arguments")
				return


			affected_pickups = []
			for pickup in ( pickup for pickup in self.pickups if pickup.name.lower() in pickupnames):
				pickup.whitelist_role=newrole
				affected_pickups.append(pickup.name)

			if affected_pickups != []:
				self.stats.update_pickups(self.pickups)
				client.notice(self.channel, "Changed whitelist role to '{0}' for {1}.".format(newrole, ' '.join(affected_pickups)))
			else:
				client.reply(self.channel, member, "No such pickups were found.")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def set_blacklist_role(self, member, args, isadmin):
		if isadmin:
			try:
				pickupnames,newrole=' '.join(args).split(' : ',1)
				pickupnames = pickupnames.lower().split(" ")
			except:
				client.reply(self.channel, member, "Bad arguments")
				return

			affected_pickups = []
			for pickup in ( pickup for pickup in self.pickups if pickup.name.lower() in pickupnames):
				pickup.blacklist_role=newrole
				affected_pickups.append(pickup.name)

			if affected_pickups != []:
				self.stats.update_pickups(self.pickups)
				client.notice(self.channel, "Changed blacklist role to '{0}' for {1}.".format(newrole, ' '.join(affected_pickups)))
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
			if pickup.name.lower() == pickup_or_ip:
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

	def reset_players(self, member=False, args=[], isadmin=False, comment=False):
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
				if comment:
					client.notice(self.channel, comment)
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
		if str(member.status) == 'offline':
			self.remove_player(member,[],'offline')
		elif str(member.status) == 'idle':
			#dont remove if user have expire time set!
			if self.id+member.id not in scheduler.tasks.keys():
				self.remove_player(member,[],'idle')

	def update_config(self, variable, value):
		self.cfg[variable] = value
		self.stats.update_config(variable, value)

	def show_config(self, member):
		s=""
		for i in self.cfg:
			s += "{0} = \"{1}\"\n".format(i, self.cfg[i])
		messages = utils.split_large_message(s)
		for i in messages: 
			client.private_reply(self.channel, member, i)

	def configure(self, member, var, value, isadmin):
		if isadmin:
			if var == "adminrole":
				self.update_config("ADMINROLE", value)
				client.reply(self.channel, member, "done.")

			elif var == "pickup_password":
				self.update_config("PICKUP_PASSWORD", value)
				client.reply(self.channel, member, "done.")

			elif var == "ip_format":
				self.update_config("IP_FORMAT", value)
				client.reply(self.channel, member, "done, now message will look like: **example** pickup has been started, {0}".format(self.cfg['IP_FORMAT'].replace("%ip%", self.cfg['DEFAULT_IP']).replace("%password%", self.cfg['PICKUP_PASSWORD'])))

			elif var == "promotion_delay":
				try:
					self.update_config("PROMOTION_DELAY", str(int(value)*60))
					client.reply(self.channel, member, "done.")
				except:
					client.reply(self.channel, member, "value for promotion_delay must be a number of minutes.")

			elif var == "++_req_players":
				try:
					if int(value) >= 0:
						self.update_config("++_REQ_PLAYERS", value)
						client.reply(self.channel, member, "done.")
					else:
						raise("must be a positive number")
				except:
					client.reply(self.channel, member, "value must be a positive number or 0.")

			elif var == "bantime":
				try:
					x = int(value)
					if x > 0:
						if x <= 10000:
							self.update_config("BANTIME", value)
							client.reply(self.channel, member, "done.")
						else:
							client.reply(self.channel, member, "maximum BANTIME value is 10000.")
					else:
						client.reply(self.channel, member, "BANTIME value should be higher than 0.")
				except:
					client.reply(self.channel, member, "BANTIME value should be an integrer.")

			elif var == "max_expire_time":
				try:
					seconds = utils.format_timestring(value.split(" "))
				except Exception as e:
					client.reply(self.channel, member, e)
					return
				if seconds > 0:
					if seconds < 86401:
						self.cfg["MAX_EXPIRE_TIME"] = str(seconds)
						self.stats.update_max_expire_time(seconds)
						client.reply(self.channel, member, "done.")
					else:
						client.reply(self.channel, member, "max expire time cant be more than 24 hours!")
				else:
					client.reply(self.channel, member, "max expire time cant be in past!.")

			elif var == "prefix":
				if len(value) == 1:
					self.update_config("PREFIX", value)
					client.reply(self.channel, member, "done.".format(self.cfg["PREFIX"]))
				else:
					client.reply(self.channel, member, "PREFIX value must be one character.")

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

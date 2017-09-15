#!/usr/bin/python2
# encoding: utf-8

import time, datetime, re, traceback, random
from modules import client, config, console, stats3, scheduler, utils

max_expire_time = 6*60*60 #6 hours
max_bantime = 30*24*60*60 #30 days

def init():
	global channels, channels_list, active_pickups, allowoffline
	channels = []
	channels_list = []
	active_pickups = []
	allowoffline = [] #users with !allowoffline

class Pickup():

	def __init__(self, channel, cfg):
		self.players = [] #[discord member objects]
		self.name = cfg['pickup_name']
		self.channel = channel
		self.cfg = cfg

class Channel():

	def __init__(self, channel, cfg):
		self.channel = channel
		self.id = channel.id
		self.name = "{0}>{1}".format(channel.server.name,channel.name)
		self.cfg = cfg
		self.update_channel_config('channel_name', channel.name)
		self.update_channel_config('server_name', channel.server.name)
		if not self.cfg['startmsg']:
			self.update_channel_config('startmsg', "please connect to steam://connect/%ip%/%password%")
			self.update_channel_config('submsg', "%promotion_role% SUB NEEDED @ **%pickup_name%**. Please connect to steam://connect/%ip%/%password%")
		self.oldtime = 0
		self.pickups = []
		self.init_pickups()
		self.lastgame_cache = stats3.lastgame(self.id)
		self.lastgame_pickup = None
		self.lastgame_players = []
		self.lastgame_teams = [[], []] #first player in each team is a captain
		self.oldtopic = '[**no pickups**]'
		
	def init_pickups(self):
		pickups = stats3.get_pickups(self.id)
		for i in pickups:
			try:
				self.pickups.append(Pickup(self, i))
			except Exception as e:
				console.display("ERROR| Failed to init a pickup of channel {0}({1}) @ {2}.".format(self.name, self.id, str(e)))
			
	def start_pickup(self, pickup):
		if not len(pickup.players):
			client.notice("No players added to this pickup...")
			return

		self.lastgame_pickup = pickup
		players=list(pickup.players) #just to save the value

		#if len(pickup.players) > 2
		if self.cfg['teams_pick_system'] == 'just_captains' and len(pickup.players) > 3:
			caps=random.sample(players, 2)
			capsstr="\r\nSuggested captains: <@{0}> and <@{1}>.".format(caps[0].id, caps[1].id)
			self.lastgame_teams = [[],[]]
			self.lastgame_players = []
				
		elif self.cfg['teams_pick_system'] == 'captains_pick' and len(pickup.players) > 3:
			caps=random.sample(players, 2)
			capsstr="\r\nSuggested captains: <@{0}> and <@{1}>.".format(caps[0].id, caps[1].id)
			self.lastgame_players = list(pickup.players)
			self.lastgame_players.remove(caps[0])
			self.lastgame_players.remove(caps[1])
			self.lastgame_teams = [[caps[0]],[caps[1]]]

		elif self.cfg['teams_pick_system'] == 'manual_pick' and len(pickup.players) > 3:
			caps=False
			capsstr=""
			self.lastgame_players = list(pickup.players)
			self.lastgame_teams = [[],[]]
				
		elif self.cfg['teams_pick_system'] == 'random_teams' and len(pickup.players) > 3:
			self.lastgame_players = list(pickup.players)
			self.lastgame_teams = [[], []]
			while len(self.lastgame_players) > 1:
				self.lastgame_teams[0].append(self.lastgame_players.pop(random.randint(0, len(self.lastgame_players)-1)))
				self.lastgame_teams[1].append(self.lastgame_players.pop(random.randint(0, len(self.lastgame_players)-1)))
			red_str = '<@'+'>, <@'.join([i.id for i in self.lastgame_teams[0]])+'>'
			blue_str = '<@'+'>, <@'.join([i.id for i in self.lastgame_teams[1]])+'>'
			caps=False
			capsstr="\r\n[{0}]\r\n  **VS**\r\n[{1}]".format(red_str, blue_str)

		else:
			caps=False
			capsstr=''
			self.lastgame_teams = [[],[]]
			self.lastgame_players = []

		last_player = players.pop(len(players)-1)
		players_highlight = '<@'+'>, <@'.join([i.id for i in players])+'>'
		players_highlight += " and <@{0}>".format(last_player.id)

		ip = self.get_value('ip', pickup)
		password = self.get_value('password', pickup)
		startmsg = self.get_value("startmsg", pickup)
		startmsg = startmsg.replace("%ip%", ip or "")
		startmsg = startmsg.replace("%password%", password or "")

		noticestr = "{1} {2}{3}".format(pickup.name, players_highlight, startmsg, capsstr)
		maps = self.get_value("maps", pickup)
		if maps:
			noticestr += "\r\nSuggested map: **{0}**.".format(random.choice(maps.split(',')).strip())

		if len(pickup.players) > 4:
			client.notice(self.channel, '**{0}** pickup has been started!\r\n{1}'.format(pickup.name, noticestr))
		else:
			client.notice(self.channel, '**{0}** pickup has been started! {1}'.format(pickup.name, noticestr))

		stats3.register_pickup(self.id, pickup.name, pickup.players)
		for i in [i for i in pickup.players]:
			print(i)
			if i in allowoffline:
				allowoffline.remove(i)
			if i.id in scheduler.tasks.keys():
				scheduler.cancel_task(i.id)
			client.private_reply(self, i,"**{0}** pickup has been started @ <#{1}>.".format(pickup.name, self.id))
			for pu in ( pu for pu in active_pickups if i.id in [x.id for x in pu.players]):
				pu.players.remove(i)
				if not len(pu.players):
					active_pickups.remove(pu)

		self.lastgame_cache = stats3.lastgame(self.id)
		print("active_pickups: {0}".format(str([i.name for i in active_pickups])))
		print("allowoffline: {0}".format(str([i.name for i in allowoffline])))
		self.update_topic()

	def processmsg(self, content, member): #parse PRIVMSG event
		msgtup = content.split(" ")
		lower = [i.lower() for i in msgtup]
		msglen = len(lower)
		if self.cfg['admin_role'] in [i.id for i in member.roles] or member.id == self.cfg['admin_id']:
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
		if prefix == self.cfg["prefix"]:
			if lower[0]=="add":
				self.add_player(member, lower[1:msglen])

			elif lower[0]=="remove":
				self.remove_player(member, lower[1:msglen])

			elif lower[0]=="expire":
				self.expire(member,lower[1:msglen])

			elif lower[0]=="default_expire":
				self.default_expire(member,lower[1:msglen])

			elif lower[0]=="allowoffline":
				self.switch_allowoffline(member)

			elif lower[0]=="remove_player" and msglen == 2:
				self.remove_players(member, lower[1], isadmin)

			elif lower[0]=="who":
				self.who(member,lower[1:msglen])

			elif lower[0]=="start":
				self.user_start_pickup(member, lower[1:msglen], isadmin)

			elif lower[0]=="pickups":
				self.replypickups(member)

			elif lower[0]=="promote":
				self.promote_pickup(member,lower[1:2])
		
			elif lower[0]=="lastgame":
				self.lastgame(member,msgtup[1:msglen])

			elif lower[0]=="sub":
				self.sub_request(member)

			elif lower[0] in ["cointoss", "ct"]:
				self.cointoss(member, lower[1:2])

			elif lower[0]=="pick":
				self.pick_player(member, lower[1:2])

			elif lower[0]=="capfor":
				self.capfor(member, lower[1:2])

			elif lower[0]=="subfor":
				self.subfor(member, lower[1:2])

			elif lower[0]=="teams":
				self.print_teams()

			elif lower[0]=="stats":
				self.getstats(member,msgtup[1:2])

			elif lower[0]=="top":
				self.gettop(member, lower[1:msglen])

			elif lower[0]=="add_pickups":
				self.add_pickups(member, msgtup[1:msglen], isadmin)

			elif lower[0]=="remove_pickups":
				self.remove_pickups(member, lower[1:msglen], isadmin)

			elif lower[0]=="maps":
				self.show_maps(member, lower[1:msglen], False)
			
			elif lower[0]=="map":
				self.show_maps(member, lower[1:msglen], True)

			elif lower[0]=="ip":
				self.getip(member,lower[1:2])

			elif lower[0]=="noadd" and msglen>1:
				self.noadd(member, msgtup[1:msglen], isadmin)

			elif lower[0]=="forgive" and msglen==2:
				self.forgive(member,msgtup[1], isadmin)

			elif lower[0]=="noadds":
				self.getnoadds(member, msgtup[1:2])

			elif lower[0]=="reset":
				self.reset_players(member, lower[1:msglen], isadmin)

			elif lower[0]=="phrase":
				self.set_phrase(member, msgtup[1:msglen], isadmin)
	#		
	#		elif lower[0]=="help":
	#			client.private_reply(self.channel, member, config.cfg.HELPINFO)
	
			elif lower[0]=="commands":
				client.reply(self.channel, member, config.cfg.COMMANDS_LINK)

			elif lower[0]=="show_config":
				self.show_config(member, msgtup[1:2])

			elif lower[0]=="show_pickup_config":
				self.show_pickup_config(member, msgtup[1:3])

			elif lower[0]=="set_default" and msglen > 2:
				self.configure_default(member, msgtup[1:msglen], isadmin)

			elif lower[0]=="set_pickups" and msglen > 3:
				self.configure_pickups(member, msgtup[1:msglen], isadmin)
			
	### COMMANDS ###

	def add_player(self, member, target_pickups):
	#check delay between last pickup
		if self.lastgame_cache:
			if time.time() - self.lastgame_cache[1] < 60 and member.name in self.lastgame_cache[3].strip().split(" "):
				client.reply(self.channel, member, "Get off me! Your pickup already started!")
	
		#check noadds and phrases
		l = stats3.check_memberid(self.id, member.id)
		if l[0] == True: # if banned
			client.reply(self.channel, member, l[1])
			return

		changes = False
		#ADD GUY TO TEH GAMES
		if target_pickups == [] and len(self.pickups) < 2: #make !add always work if only one pickup is configured on the channel
			filtered_pickups = self.pickups
		else:
			filtered_pickups = [pickup for pickup in ( pickup for pickup in self.pickups if ((target_pickups == [] and len(pickup.players)>0 and int(self.cfg["++_req_players"])<=pickup.maxplayers) or pickup.name.lower() in target_pickups))]
		for pickup in filtered_pickups:
			if not member.id in [i.id for i in pickup.players]:
				#check if pickup have blacklist or whitelist
				whitelist_role = self.get_value("whitelist_role", pickup)
				blacklist_role = self.get_value("whitelist_role", pickup)
				member_roles = [r.id for r in member.roles]
				if blacklist_role in member_roles:
					client.reply(self.channel, member, "You are not allowed to play {0} (blacklisted).".format(pickup.name))
				
				elif not whitelist_role or whitelist_role in member_roles:
					changes = True
					pickup.players.append(member)
					if len(pickup.players)==pickup.cfg['maxplayers']:
						self.start_pickup(pickup)
						return
					elif len(pickup.players)==pickup.cfg['maxplayers']-1 and pickup.cfg['maxplayers']>2:
						client.notice(self.channel, "Only 1 player left for {0} pickup. Hurry up!".format(pickup.name))

					if pickup not in active_pickups:
						active_pickups.append(pickup)
				else:
					client.reply(self.channel, member, "You are not allowed to play {0} (not in whitelist).".format(pickup.name))

		#update scheduler, reply a phrase and update topic
		if changes:
			if l[2]: # if have default_expire
				if member.id in scheduler.tasks.keys():
					scheduler.cancel_task(member.id)
				scheduler.add_task(member.id, l[2], global_remove, (member, 'scheduler'))
			if l[1]: # if have phrase
				client.reply(self.channel, member, l[1])
			self.update_topic()

	def remove_player(self, member, args, reason='online'):
		changes = []
		allpickups = True

		#remove player from games
		l = active_pickups
		for pickup in l:
			if member.id in [i.id for i in pickup.players]:
				if pickup.channel.id == self.id and (args == [] or pickup.name.lower() in args):
					changes.append(pickup.name)
					pickup.players.remove(member)
					if len(pickup.players) == 0:
						active_pickups.remove(pickup)
				elif allpickups:
					allpickups = False

		#update topic and warn player
		if changes != []:
			self.update_topic()
			if reason == 'banned':
				client.notice(self.channel, "{0} have been removed from all pickups...".format(member.name))
			#elif reason == 'reset':
			#	if allpickups:
			#		client.reply(self.channel, member, "You have been removed from all pickups, pickups has been reset.")
			#	else:
			#		client.reply(self.channel, member, "You have been removed from {0} - pickups has been reset.".format(", ".join(changes)))
			elif reason == 'admin':
				if allpickups:
					client.reply(self.channel, member, "You have been removed from all pickups by an admin.")
				else:
					client.reply(self.channel, member, "You have been removed from {0} by an admin.".format(", ".join(changes)))
			#if reason == 'online':
			#if allpickups:
			#	client.private_reply(self.channel, member, "You have been removed from all pickups")
			#else:
			#	client.private_reply(self.channel, member, "You have been removed from {0}.".format(", ".join(changes)))

			#REMOVE !expire AUTOREMOVE IF HE IS REMOVED FROM ALL GAMES
			if allpickups and member.id in scheduler.tasks.keys():
				scheduler.cancel_task(member.id)

	def remove_players(self, member, arg, isadmin):
		if isadmin:
			if re.match("^<@(!|)[0-9]+>$", arg):
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
			templist.append('[**{0}** ({1}/{2})] {3}'.format(pickup.name, len(pickup.players), pickup.cfg['maxplayers'], '/'.join([i.name for i in pickup.players])))
		if templist != []:
			client.notice(self.channel, ' '.join(templist))
		else:
			client.notice(self.channel, 'no one added...ZzZz')

	def user_start_pickup(self, member, args, isadmin):
		if isadmin:
			if len(args):
				for pickup in self.pickups:
					if pickup.name.lower() == args[0]:
						self.start_pickup(pickup)
			elif len(self.pickups) == 1:
				self.start_pickup(self.pickups[0])
			else:
				client.reply(self.channel, member, "You must specify a pickup to start!")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def lastgame(self, member, args):
		if args != []:
			l = stats3.lastgame(self.id, args[0]) #id, ago, gametype, players, alpha_players, beta_players
		else:
			l = self.lastgame_cache
		if l:
			n = l[0]
			ago = datetime.timedelta(seconds=int(time.time() - int(l[1])))
			gt = l[2]
			if l[4] and l[5]:
				players = "[{0}] vs [{1}]".format(l[4], l[5])
			else:
				players = ", ".join(l[3].strip().split(" "))
			client.notice(self.channel, "Pickup #{0}, {1} ago [{2}]: {3}".format(n, ago, gt, players))
		else:
			client.notice(self.channel, "No pickups found.")

	def sub_request(self, member):
		if not self.lastgame_pickup:
			client.reply(self.channel, member, "No pickups played yet.")
			return

		self.newtime=time.time()
		if self.newtime-self.oldtime>int(self.cfg['promotion_delay']):
			promotion_role = self.get_value('promotion_role', self.lastgame_pickup)
			if promotion_role:
				promotion_role = "<@&{0}>".format(promotion_role)
			ip = self.get_value('ip', self.lastgame_pickup)
			password = self.get_value('password', self.lastgame_pickup)
			submsg = self.get_value('submsg', self.lastgame_pickup)
					
			submsg = submsg.replace("%pickup_name%", self.lastgame_pickup.name)
			submsg = submsg.replace("%ip%", ip or "")
			submsg = submsg.replace("%password%", password or "") 
			submsg = submsg.replace("%promotion_role%", promotion_role or "")
			client.notice(self.channel, submsg)

			self.oldtime=self.newtime
		else:
			client.reply(self.channel, member,"You can't promote too often! You have to wait {0}.".format(str(datetime.timedelta(seconds=int(int(self.cfg['promotion_delay'])-self.newtime+self.oldtime)))))

	def cointoss(self, member, args):
		if len(args):
			if args[0] in ['heads', 'tails']:
				pick = args[0]
			else:
				client.reply(self.channel, member, "Its best to pick between **heads** or **tails**. But who knows...")
				#return
				pick = args[0]
		else:
			pick = 'heads'

		result = random.choice(['heads', 'tails'])
		if result == pick:
			client.reply(self.channel, member, "You win, it's **{0}**!".format(result))
		else:
			client.reply(self.channel, member, "You loose, it's **{0}**!".format(result))
#next
	def pick_player(self, member, args):
		if not self.lastgame_pickup:
			client.reply(self.channel, member, "No pickups played yet.")
			return
			
		if self.get_value('teams_pick_system', self.lastgame_pickup) not in ['captains_pick', 'manual_pick']:
			client.reply(self.channel, member, "This pickup channel is not configured for this command!")
			return
		#if len(self.lastgame_teams[0]) == 0 or len(self.lastgame_teams[1]) == 0:
		#	client.reply(self.channel, member, "Captains are not set!")
		#	return
		teamidx = -1
		if len(self.lastgame_teams[0]):
			if self.lastgame_teams[0][0].id == member.id:
				teamidx=0
		if len(self.lastgame_teams[1]):
			if self.lastgame_teams[1][0].id == member.id:
				teamidx=1
		if teamidx == -1:
			client.reply(self.channel, member, "You are not a captain!")
			return

		if len(args):
			targetid = args[0].lstrip("<@!").rstrip(">")
			for i in self.lastgame_players:
				if i.id == targetid:
					self.lastgame_teams[teamidx].append(i)
					self.lastgame_players.remove(i)
					self.print_teams()
					return
			for i in self.lastgame_teams[abs(teamidx-1)]:
				if i.id == targetid:
					self.lastgame_teams[teamidx].append(i)
					self.lastgame_teams[abs(teamidx-1)].remove(i)
					self.print_teams()
					return
			client.reply(self.channel, member, "Specified player are not added or already in your team!")
		else:
			client.reply(self.channel, member, "You must specify a player to pick!")

	def subfor(self, member, args):
		if not self.lastgame_pickup:
			client.reply(self.channel, member, "No pickups played yet.")
			return

		if self.get_value('teams_pick_system', self.lastgame_pickup) not in ['captains_pick', 'random_teams', 'manual_pick']:
			client.reply(self.channel, member, "This pickup channel is not configured for this command!")
			return

		if member in self.lastgame_players+self.lastgame_teams[0]+self.lastgame_teams[1]:
			client.reply(self.channel, member, "You are allready in the players list!")
			return

		if len(args):
			targetid = args[0].lstrip("<@!").rstrip(">")
			for x in [self.lastgame_players, self.lastgame_teams[0], self.lastgame_teams[1]]:
				for i in x:
					if i.id == targetid:
						idx = x.index(i)
						x[idx] = member
						self.print_teams()
						return
			client.reply(self.channel, member, "Specified player not found!")
		else:
			client.reply(self.channel, member, "You must specify a player to substitute!")

	def capfor(self, member, args):
		if not self.lastgame_pickup:
			client.reply(self.channel, member, "No pickups played yet.")
			return

		if self.get_value('teams_pick_system', self.lastgame_pickup) not in ['captains_pick', 'manual_pick']:
			client.reply(self.channel, member, "This pickup channel is not configured for this command!")
			return

		if len(args):
			if args[0] not in ['alpha', 'beta']:
				client.reply(self.channel, member, "Specified team must be **alpha** or **beta**!")
				return

			for x in [self.lastgame_players, self.lastgame_teams[0], self.lastgame_teams[1]]:
				for i in x:
					if i.id == member.id:
						memberidx = x.index(i)
						if args[0] == 'alpha':
							if len(self.lastgame_teams[0]): #swap current captain possition
								if self.lastgame_teams[0][0].id == member.id:
									client.reply(self.channel, member, "You are allready the captain of this team!")
									return
								x[memberidx] = self.lastgame_teams[0][0]
								self.lastgame_teams[0][0] = member
							else:
								x.pop(memberidx)
								self.lastgame_teams[0].insert(0, member)
						elif args[0] == 'beta':
							if len(self.lastgame_teams[1]): #swap current captain possition
								if self.lastgame_teams[1][0].id == member.id:
									client.reply(self.channel, member, "You are allready the captain of this team!")
									return
								x[memberidx] = self.lastgame_teams[1][0]
								self.lastgame_teams[1][0] = member
							else:
								x.pop(memberidx)
								self.lastgame_teams[1].insert(0, member)
						self.print_teams()
						return

			client.reply(self.channel, member, "You must be in players list to become a captain!")

	def print_teams(self):
		red_team = ", ".join([i.nick or i.name for i in self.lastgame_teams[0]])
		blue_team = ", ".join([i.nick or i.name for i in self.lastgame_teams[1]])
		noticestr = "[{0}] **VS** [{1}]".format(red_team, blue_team)
		if len(self.lastgame_players):
			unpicked  = ", ".join([i.nick or i.name for i in self.lastgame_players])
			noticestr += "\r\nUnpicked: [{0}]".format(unpicked)
		client.notice(self.channel, noticestr)

	def update_topic(self):
		newtopic=''

		sort=sorted(self.pickups,key=lambda x: len(x.players), reverse=True)
		strlist = []
		for i in ( i for i in sort if i.players):
			strlist.append("**{0}** ({1}/{2})".format(i.name,len(i.players), i.cfg['maxplayers']))
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
				s.append("**{0}** ({1}/{2})".format(i.name,len(i.players),i.cfg['maxplayers']))
			s = ' | '.join(s)

			client.notice(self.channel, s)
		else:
			client.notice(self.channel, "No pickups configured on this channel.")

#next also fix !sub
	def promote_pickup(self, member, args):
		if not len(self.pickups):
			client.reply(self.channel, member, "This channel does not have any pickups configured.")
			return

		self.newtime=time.time()
		if self.newtime-self.oldtime>int(self.cfg['promotion_delay']):
			#get pickup to promote
			pickup = False
			if args != []:
				for i in self.pickups:
					if i.name.lower() == args[0]:
						pickup = i
						break
				if not pickup:
					client.reply(self.channel, "Pickup '{0}' not found on this channel.".format(args[0]))
					return

			else:
				pickups = sorted(self.pickups, key=lambda x: len(x.players))
				if len(pickups[0].players):
					pickup = pickups[0]

			if pickup:
				promotion_role = self.get_value('promotion_role', pickup)
				players_left = pickup.cfg['maxplayers']-len(pickup.players)
				if promotion_role:
					client.notice(self.channel, "<@&{0}> please !add {1}, {2} players to go!".format(promotion_role, pickup.name, players_left))
				else:
					client.notice(self.channel, "Please !add {0}, {1} players to go!".format(pickup.name, players_left))
			else:
				if self.cfg['promotion_role']:
					client.notice(self.channel, "<@&{0}> please !add to pickups!".format(self.cfg['promotion_role']))
				else:
					client.notice(self.channel, "Please !add to pickups!")

			self.oldtime=self.newtime

		else:
			client.reply(self.channel, member,"You can't promote too often! You have to wait {0}.".format(str(datetime.timedelta(seconds=int(int(self.cfg['promotion_delay'])-self.newtime+self.oldtime)))))

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
			if timeint>0 and timeint<=max_expire_time: #restart the scheduler task, no afk check task for this guy
				if member.id in scheduler.tasks.keys():
					scheduler.cancel_task(member.id)
				scheduler.add_task(member.id, timeint, global_remove, (member, 'scheduler'))
				client.reply(self.channel, member, "You will be removed in {0}".format(str(datetime.timedelta(seconds=int(timeint)))))
			else:
				client.reply(self.channel, member, "Invalid time amount. Maximum expire time is {0}".format(str(datetime.timedelta(seconds=max_expire_time))))

		#return expire time	if no time specified
		else:
			if not member.id in scheduler.tasks.keys():
				client.reply(self.channel, member, "No !expire time is set. You will be removed on your AFK status.")
				return

			timeint=scheduler.tasks[member.id][0]
			
			client.reply(self.channel, member, "You will be removed in {0}".format(str(datetime.timedelta(seconds=int(timeint-time.time()))),))
#next
	def default_expire(self, member, timelist):
		#print user default expire time
		if timelist == []:
			timeint = stats3.get_expire(member.id)
			if timeint:
				client.reply(self.channel, member, "Your default expire time is {0}".format(str(datetime.timedelta(seconds=int(timeint))),))
			else:
				client.reply(self.channel, member, "You will be removed on AFK status by default.")

		#set expire time to afk
		elif timelist[0] == 'afk':
			stats3.set_expire(member.id, None)
			client.reply(self.channel, member, "You will be removed on AFK status by default.")

		#format time string and set new time amount
		else:
			try:
				timeint = utils.format_timestring(timelist)
			except Exception as e:
				client.reply(self.channel, member, str(e))
				return
			if timeint>0 and timeint<=max_expire_time:
				stats3.set_expire(member.id, timeint)
				client.reply(self.channel, member, "set your default expire time to {0}".format(str(datetime.timedelta(seconds=int(timeint))),))
			else:
				client.reply(self.channel, member, "Invalid time amount. Maximum expire time on this channel is {0}".format(str(datetime.timedelta(seconds=max_expire_time))))

	def switch_allowoffline(self, member):
		if member in allowoffline:
			allowoffline.remove(member)
			client.reply(self.channel, member, "Your offline/afk immune is gone.")
		else:
			allowoffline.append(member)
			client.reply(self.channel, member, "You will have offline/afk immune until your next pickup.")
			
	def getstats(self, member, target):
		if target == []:
			s = stats3.stats(self.id)
		else:
			s = stats3.stats(self.id, target[0])
		client.notice(self.channel, s)

	def gettop(self, member, arg):
		if arg == []:
			top10=stats3.top(self.id)
			client.notice(self.channel, "Top 10 of all time: "+top10)

		elif arg[0] == "weekly":
			timegap = int(time.time()) - 604800
			top10=stats3.top(self.id, timegap)
			client.notice(self.channel, "Top 10 of the week: "+top10)

		elif arg[0] == "monthly":
			timegap = int(time.time()) - 2629744
			top10=stats3.top(self.id, timegap)
			client.notice(self.channel, "Top 10 of the month: "+top10)

		elif arg[0] == "yearly":
			timegap = int(time.time()) - 31556926
			top10=stats3.top(self.id, timegap)
			client.notice(self.channel, "Top 10 of the year: "+top10)

		else:
			client.reply(self.channel, member, "Bad argument.")

	def getnoadds(self, member, args):
		if args == []:
			l = stats3.noadds(self.id)
		else:
			try:
				index = int(args[0])
			except:
				index = -1
			if index < 0:
				client.reply(self.channel, member, "Index argument must be a positive number.")
				return
			l = stats3.noadds(self.id, index)
		if l != []:
			client.notice(self.channel, "\r\n".join(l))
		else:
			client.reply(self.channel, member, "No noadds found.")
#next
	def add_pickups(self, member, targs, isadmin):
		if isadmin:
			newpickups = []
			for i in range(0,len(targs)):
				try:
					name,players = targs[i].split(":")
					if int(players) > 1:
						if name.lower() not in [i.name.lower() for i in self.pickups]:
							newpickups.append([name, int(players)])
						else:
							client.reply(self.channel, member, "Pickup with name '{0}' allready exists!".format(name))
							return
					else:
						client.reply(self.channel, member, "Players number must be more than 1, dickhead.")
						return
				except:
					client.reply(self.channel, member, "Bad argument @ {0}".format(targs[i]))
					return
			if newpickups != []:
				for i in newpickups:
					cfg = stats3.new_pickup(self.id, i[0], i[1])
					self.pickups.append(Pickup(self, cfg))
				self.replypickups(member)
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def remove_pickups(self, member, args, isadmin):
		if isadmin:
			toremove = [ pickup for pickup in self.pickups if pickup.name.lower() in args ]
			if len(toremove) > 0:
				for i in toremove:
					self.pickups.remove(i)
					stats3.delete_pickup(self.id, i.name)
				self.replypickups(member)
			else:
				client.reply(self.channel, member, "No such pickups found.")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def show_maps(self, member, args, pick):
		if len(args):
			pickupname = args[0].lower()
			for pickup in self.pickups:
				if pickup.name.lower() == pickupname:
					maps = self.get_value('maps', pickup)
					if not maps:
						client.reply(self.channel, member, "No maps set for **{0}** pickup".format(pickup.name))
					else:
						if pick:
							client.notice(self.channel, "**{0}**".format(random.choice(maps.split(',')).strip()))
						else:
							client.notice(self.channel, "Maps for [**{0}**]: {1}.".format(pickup.name, maps))
					return
			client.reply(self.channel, member, "Pickup '{0}' not found!".format(args[0]))
		elif self.cfg['maps']:
			if pick:
				client.notice(self.channel, "**{0}**".format(random.choice(self.cfg['maps'].split(',')).strip()))
			else:
				client.reply(self.channel, member, "Default maps: {0}".format(self.cfg['maps']))
		else:
			client.reply(self.channel, member, "No default maps are set")

	def getip(self, member, args): #GET IP FOR GAME
		# find desired parameter
		if args != []:
			pickup = False
			for i in self.pickups:
				if i.name.lower() == args[0]:
					pickup = i
					break
			if not pickup:
				client.reply(self.channel, member, "Pickup '{0}' not found on this channel.".format(args[0]))
				return
		else:
			if self.lastgame_pickup:
				pickup = self.lastgame_pickup
			else:
				client.reply(self.channel, member, "No pickups played yet.")

		ip = self.get_value('ip', pickup)
		password = self.get_value('password', pickup)
		if ip:
			reply = "Ip for {0}: {1}".format(pickup.name, ip)
			if password:
				reply += "\r\nPassword: '{0}'.".format(password)
		else:
			reply = "No ip is set for {0} pickup.".format(pickup.name)
		client.notice(self.channel, reply)
#next
	def set_phrase(self, member, args, isadmin):
		if isadmin:
			if len(args) >= 2:
				targetid = args[0]
				if re.match("^<@(!|)[0-9]+>$", targetid):
					target = client.get_member_by_id(self.channel, targetid)
					if target:
						phrase = ' '.join(args[1:len(args)])
						stats3.set_phrase(self.id, target.id, phrase)
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
			duratation = self.cfg['default_bantime']

			targetid = args.pop(0)
			if re.match("^<@(!|)[0-9]+>$", targetid):
				target = client.get_member_by_id(self.channel, targetid)
				i=0
				timelist = []
				while len(args):
					if re.match("[0-9]+(d|h|m|s)", args[0].lower()):
						timelist.append(args.pop(0).lower())
					else:
						break

				if len(timelist):
					duratation = utils.format_timestring(timelist)

				if len(args):
					reason = " ".join(args)
					
			else:
				client.reply(self.channel, member, "Target must be a Member highlight.")
				return

			if abs(duratation) > max_bantime:
				client.reply(self.channel, member,"Max ban duratation is {0}.".format(str(datetime.timedelta(seconds=max_bantime))))
				return

			if target:
				self.remove_player(target,[],'banned')
				s = stats3.noadd(self.id, target.id, target.name, duratation, member.name, reason)
				client.notice(self.channel, s)
			else:
				client.reply(self.channel, member, "Could not found specified Member on the server, is the highlight valid?")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def forgive(self, member, arg, isadmin):
		if isadmin:
			if re.match("^<@(!|)[0-9]+>$", arg):
				target = client.get_member_by_id(self.channel, arg)
				if target:
					s = stats3.forgive(self.id, target.id, target.name, member.name)
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
				if len(pickup.players) and (pickup.name in args or args == []):
					for player in pickup.players:
						if not player in removed:
							removed.append(player)
					pickup.players = []
					active_pickups.remove(pickup)
			if removed != []:
				for player in removed:
					allpickups = True
					for pickup in active_pickups:
						if player in pickup.players:
							allpickups = False
							break
					if allpickups and player.id in scheduler.tasks.keys():
						scheduler.cancel_task(player.id)
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

	def get_value(self, variable, pickup):
		if pickup.cfg[variable] != None:
			return pickup.cfg[variable]
		else:
			return self.cfg[variable]

	def update_channel_config(self, variable, value):
		self.cfg[variable] = value
		stats3.update_channel_config(self.id, variable, value)

	def update_pickup_config(self, pickup, variable, value):
		pickup.cfg[variable] = value
		stats3.update_pickup_config(self.id, pickup.name, variable, value)

	def show_config(self, member, args):
		if len(args):
			if args[0] in self.cfg.keys():
				client.private_reply(self.channel, member, "{0}: '{1}'".format(args[0], str(self.cfg[args[0]])))
			else:
				client.reply(self.channel, member, "No such variable '{0}'.".format(args[0]))
		else:
			client.private_reply(self.channel, member, '\r\n'.join(["{0}: '{1}'".format(key, str(value)) for (key, value) in self.cfg.items()]))

	def show_pickup_config(self, member, args):
		if len(args):
			for pickup in self.pickups:
				if pickup.name.lower() == args[0]:
					if len(args) > 1:
						if args[1] in pickup.cfg.keys():
							client.private_reply(self.channel, member, "[{0}] {1}: '{2}'".format(pickup.name, args[1], str(pickup.cfg[args[1]])))
							return
						else:
							client.reply(self.channel, member, "No such variable '{0}'.".format(args[1]))
							return
					else:
						client.private_reply(self.channel, member, '\r\n'.join(["[{0}] {1}: '{2}'".format(pickup.name, key, str(value)) for (key, value) in pickup.cfg.items()]))
						return
			client.reply(self.channel, member, "Pickup '{0}' not found.".format(args[0]))
		else:
			client.reply(self.channel, member, "You must specify a pickup")

	def configure_default(self, member, args, isadmin):
		print("step1")
		if not isadmin:
			client.reply(self.channel, member, "You have no right for this!")
			return

		print("step2")
		variable = args.pop(0).lower()
		value = " ".join(args)
		print("step3: {0}: {1}".format(variable, value))

		if variable == "admin_role":
			if value.lower() == "none":
				client.reply(self.channel, member, "Cant unset {0} value.".format(variable))
			else:
				role = client.find_role_by_name(self.channel, value)
				if role:
					self.update_channel_config('admin_role', role.id)
					client.reply(self.channel, member, "Set '{0}' {1} as default value".format(role.name, variable))
				else:
					client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))

		elif variable == "moderator_role":
			if value.lower() == "none":
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
			else:
				role = client.find_role_by_name(self.channel, value)
				if role:
					self.update_channel_config(variable, role.id)
					client.reply(self.channel, member, "Set '{0}' {1} as default value".format(role.name, variable))
				else:
					client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))
			
		elif variable == "captain_role":
			if value.lower() == "none":
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
			else:
				role = client.find_role_by_name(self.channel, value)
				if role:
					self.update_channel_config(variable, role.id)
					client.reply(self.channel, member, "Set '{0}' {1} as default value".format(role.name, variable))
				else:
					client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))

		elif variable == "noadd_role":
			if value.lower() == "none":
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
			else:
				role = client.find_role_by_name(self.channel, value)
				if role:
					self.update_channel_config(variable, role.id)
					client.reply(self.channel, member, "Set '{0}' {1} as default value".format(role.name, variable))
				else:
					client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))

		elif variable == "default_bantime":
			print("step4")
			if value.lower() == "none":
				client.reply(self.channel, member, "Cant unset {0} value.".format(variable))
			else:
				try:
					seconds = utils.format_timestring(value.split(" "))
				except Exception as e:
					client.reply(self.channel, member, str(e))
					return
				if seconds <= max_bantime:
					self.update_channel_config(variable, seconds)
					client.reply(self.channel, member, "Set '{0}' {1} as default value".format(seconds, variable))
				else:
					client.reply(self.channel, member, "Maximum bantime is 30 days.")

		elif variable == "++_req_players":
			if value.lower() == "none":
				client.reply(self.channel, member, "Cant unset {0} value.".format(variable))
			else:
				try:
					number = int(value)
				except:
					client.reply("Value must be a number")
				if 0 <= number < 50:
					self.update_channel_config(variable, number)
					client.reply(self.channel, member, "Done.")
				else:
					client.reply(self.channel, member, "++_req_players number must be a positive number less than 50.")

		elif variable == "startmsg":
			if value.lower() == "none":
				client.reply(self.channel, member, "Cant unset {0} value.".format(variable))
			else:
				self.update_channel_config(variable, value)
				startmsg = self.cfg['startmsg']
				startmsg = startmsg.replace("%ip%", self.cfg['ip'] or "")
				startmsg = startmsg.replace("%password%", self.cfg['password'] or "")
				if self.cfg['teams_pick_system'] in ["random_captains", "captains_pick"]:
					startmsg += "\r\nSuggested captains: @player1 and @player2."
				if self.cfg['maps']:
					startmsg += "\r\nSuggested map: **{0}**.".format(random.choice(self.cfg['maps'].split(",")).strip())
				client.reply(self.channel, member, "Start message of pickup with default settings will now look like this:\r\n**example** pickup has been started!\r\n@player1, @player2 {0}".format(startmsg))

		elif variable == "submsg":
			if value.lower() == "none":
				client.reply(self.channel, member, "Cant unset {0} value.".format(variable))
			else:
				self.update_channel_config(variable, value)
				submsg = self.cfg['submsg']
				submsg = submsg.replace("%pickup_name%", "example")
				submsg = submsg.replace("%ip%", self.cfg['ip'] or "")
				submsg = submsg.replace("%password%", self.cfg['password'] or "")
				promotion_role = self.cfg['promotion_role']
				if promotion_role:
					promotion_role = "<@&{0}>".format(promotion_role)
				submsg = submsg.replace("%promotion_role%", promotion_role  or "")
				client.reply(self.channel, member, "Sub request message for default pickup will now look like this:\r\n{0}".format(submsg))

		elif variable == "ip":
			if value.lower() == "none":
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
			else:
				self.update_channel_config(variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(value, variable))

		elif variable == "password":
			if value.lower() == "none":
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
			else:
				self.update_channel_config(variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(value, variable))

		elif variable == "maps":
			if value.lower() == "none":
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
			else:
				self.update_channel_config(variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(value, variable))

		elif variable == "teams_pick_system":
			if value.lower() in ["no_teams", "just_captains", "captains_pick", "manual_pick", "random_teams"]:
				self.update_channel_config(variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(value, variable))
			else:
				client.reply(self.channel, member, "teams_pick_system value must be no_teams, just_captains, captains_pick, manual_pick or random_teams.")
				
		elif variable == "promotion_role":
			if value.lower() == "none":
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
			else:
				role = client.find_role_by_name(self.channel, value)
				if role:
					self.update_channel_config(variable, role.id)
					client.reply(self.channel, member, "Set '{0}' {1} as default value".format(role.name, variable))
				else:
					client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))

		elif variable == "promotion_delay":
			if value.lower() == "none":
				client.reply(self.channel, member, "Cant unset {0} value.".format(variable))
			else:
				try:
					seconds = utils.format_timestring(value.split(" "))
				except Exception as e:
					client.reply(self.channel, member, str(e))
					return
				self.update_channel_config(variable, seconds)
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(seconds, variable))

		elif variable == "blacklist_role":
			if value.lower() == "none":
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
			else:
				role = client.find_role_by_name(self.channel, value)
				if role:
					self.update_channel_config(variable, role.id)
					client.reply(self.channel, member, "Set '{0}' {1} as default value".format(role.name, variable))
				else:
					client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))

		elif variable == "whitelist_role":
			if value.lower() == "none":
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
			else:
				role = client.find_role_by_name(self.channel, value)
				if role:
					self.update_channel_config(variable, role.id)
					client.reply(self.channel, member, "Set '{0}' {1} as default value".format(role.name, variable))
				else:
					client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))

		elif variable == "require_ready":
			if value.lower() == "none":
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
			elif value in ['0', '1']:
				self.update_channel_config(variable, int(value))
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(value, variable))
			else:
				client.reply(self.channel, member, "Value for {0} must be 0 or 1".format(variable))
				
		elif variable == "ready_timeout":
			if value.lower() == 'none':
				client.reply(self.channel, member, "Cant unset {0} value.".format(variable))
			else:
				try:
					seconds = utils.format_timestring(value.split(" "))
				except Exception as e:
					client.reply(self.channel, member, str(e))
					return
				self.update_channel_config(variable, seconds)
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(seconds, variable))

		else:
			client.reply(self.channel, member, "Variable '{0}' is not configurable.".format(variable))

	def configure_pickups(self, member, args, isadmin):
		if not isadmin:
			client.reply(self.channel, member, "You have no right for this!")
			return

		#determine pickup names, variable name, and value
		pickup_names = " ".join(args).split(",")
		last_pickup, rest = pickup_names[len(pickup_names)-1].lstrip().split(" ", 1)
		pickup_names[len(pickup_names)-1] = last_pickup
		pickup_names = [i.strip().lower() for i in pickup_names]
		variable, value = rest.lstrip().split(" ", 1)
		variable = variable.lower()

		#get pickups by pickup names
		pickups = []
		for i in self.pickups:
			if i.name.lower() in pickup_names:
				pickups.append(i)
				pickup_names.remove(i.name.lower())
		if len(pickup_names):
			client.reply(self.channel, member, "Pickups '{0}' not found".format(", ".join(pickup_names)))
			return

		#configure!
		if variable == "maxplayers":
			if value.lower() == "none":
				client.reply(self.channel, member, "Cant unset {0} value.".format(variable))
			else:
				try:
					value = int(value)
				except:
					client.reply(self.channel, member, "Maxplayers value must be a number.")
					return
				if  1 < value < 101:
					for i in pickups:
						self.update_pickup_config(i, variable, value)
					client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(value, variable, ", ".join(i.name for i in pickups)))
				else:
					client.reply(self.channel, member, "maxplayers value must be between 2 and 100")

		elif variable == "minplayers":
			pass

		elif variable == "startmsg":
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				for i in pickups:
					self.update_pickup_config(i, variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(value, variable, ", ".join(i.name for i in pickups)))

		elif variable == "submsg":
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				for i in pickups:
					self.update_pickup_config(i, variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(value, variable, ", ".join(i.name for i in pickups)))

		elif variable == "ip":
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				for i in pickups:
					self.update_pickup_config(i, variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(value, variable, ", ".join(i.name for i in pickups)))

		elif variable == "password":
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				for i in pickups:
					self.update_pickup_config(i, variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(value, variable, ", ".join(i.name for i in pickups)))

		elif variable == "maps":
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				for i in pickups:
					self.update_pickup_config(i, variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(value, variable, ", ".join(i.name for i in pickups)))

		elif variable == "teams_pick_system":
			value = value.lower()
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			elif value in ["no_teams", "just_captains", "captains_pick", "manual_pick", "random_teams"]:
				for i in pickups:
					self.update_pickup_config(i, variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(value, variable, ", ".join(i.name for i in pickups)))
			else:
				client.reply(self.channel, member, "teams_pick_system value must be no_teams, just_captains, captains_pick, manual_pick or random_teams.")

		elif variable == "pick_order":
			pass

		elif variable == "promotion_role":
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				role = client.find_role_by_name(self.channel, value)
				if role:
					for i in pickups:
						self.update_pickup_config(i, variable, role.id)
					client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(role.name, variable, ", ".join(i.name for i in pickups)))
				else:
					client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))

		elif variable == "blacklist_role":
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				role = client.find_role_by_name(self.channel, value)
				if role:
					for i in pickups:
						self.update_pickup_config(i, variable, role.id)
					client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(role.name, variable, ", ".join(i.name for i in pickups)))
				else:
					client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))

		elif variable == "whitelist_role":
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				role = client.find_role_by_name(self.channel, value)
				if role:
					for i in pickups:
						self.update_pickup_config(i, variable, role.id)
					client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(role.name, variable, ", ".join(i.name for i in pickups)))
				else:
					client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))

		elif variable == "captain_role":
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				role = client.find_role_by_name(self.channel, value)
				if role:
					for i in pickups:
						self.update_pickup_config(i, variable, role.id)
					client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(role.name, variable, ", ".join(i.name for i in pickups)))
				else:
					client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))

		elif variable == "require_ready":
			pass

		elif variable == "ready_timeout":
			pass	

		else:
			client.reply(self.channel, member, "Variable '{0}' is not configurable.".format(variable))			

def update_member(member): #on status change
	if member not in allowoffline:
		if str(member.status) == 'offline':
			global_remove(member, 'offline')
		elif str(member.status) == 'idle':
			#dont remove if user have expire time set!
			if member.id not in scheduler.tasks.keys():
				global_remove(member, 'idle')

def global_remove(member, reason):
	#removes player from pickups on all channels
	affected_channels = []
	l = active_pickups
	for p in l:
		if member.id in [i.id for i in p.players]:
			p.players.remove(member)
			if len(p.players) == 0:
				active_pickups.remove(p)
			if p.channel not in affected_channels:
				affected_channels.append(p.channel)

	for i in affected_channels:
		i.update_topic()
		if reason == 'scheduler':
			client.reply(i.channel, member, "you have been removed from all pickups as your !expire time ran off...")
		elif reason == 'idle':
			client.notice(i.channel, "<@{0}> went AFK and was removed from all pickups...".format(member.id))
		elif reason == 'offline':
			client.notice(i.channel, "{0} went offline and was removed from all pickups...".format(member.name))

def run(frametime):
	pass

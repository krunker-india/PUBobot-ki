#!/usr/bin/python2
# encoding: utf-8

import time, datetime, re, traceback, random
from modules import client, config, console, stats3, scheduler, utils

max_expire_time = 6*60*60 #6 hours
max_bantime = 30*24*60*60*12*3 #30 days * 12 * 3
max_match_alive_time = 4*60*60 #4 hours
team_smileys = [":fox:", ":wolf:", ":dog:", ":bear:", ":panda_face:", ":tiger:", ":lion:", ":pig:", ":octopus:", ":boar:", ":spider:", ":scorpion:", ":crab:", ":eagle:", ":shark:", ":bat:", ":gorilla:", ":rhino:", ":dragon_face:", ":deer:"]

def init():
	global channels, channels_list, active_pickups, active_matches, matches_step, allowoffline
	channels = []
	channels_list = []
	active_pickups = []
	active_matches = []
	matches_step = 0
	allowoffline = [] #users with !allowoffline

class Match():

	def __init__(self, pickup, players):
		global matches_step
		active_matches.append(self)
		#set the temporary id
		matches_step += 1
		self.id = matches_step
		#these values cannot be changed until match end, so we need to save them
		self.maxplayers = pickup.cfg['maxplayers']
		self.pick_teams = pickup.channel.get_value('pick_teams', pickup)
		self.require_ready = pickup.channel.get_value('require_ready', pickup)
		self.pick_order = pickup.cfg['pick_order']
		self.ranked = pickup.channel.get_value('ranked', pickup)
		self.captains_role = pickup.channel.get_value('captains_role', pickup)
		maps = pickup.channel.get_value('maps', pickup)
		if maps:
			self.map = random.choice(maps.split(',')).strip()
		else:
			self.map = None
		#prepare working variables
		self.state = "none" #none, waiting_ready, teams_picking or waiting_report
		self.pickup = pickup
		self.channel = pickup.channel.channel
		self.players = list(players)
		self.winner = None
		self.lastpick = None #fatkid

		if self.pickup.channel.get_value('pick_captains', pickup) and len(players) > 2:
			if self.captains_role:
				self.captains = []
				candidates = list(filter(lambda x: self.captains_role in [role.id for role in x.roles], self.players))
				while len(self.captains) < 2:
					if len(candidates):
						p = random.choice(candidates)
						self.captains.append(p)
						candidates.remove(p)
					else:
						p = random.choice(self.players)
						self.captains.append(p)
			else:
				self.captains = random.sample(self.players, 2)
		else:
			self.captains = None

		if self.require_ready:
			self.players_ready = [False for i in players]

		self.alpha_icon, self.beta_icon = random.sample(team_smileys, 2)
		print(str(self.pick_teams))
		if len(players) > 2:
			if self.pick_teams == 'no_teams' or self.pick_teams == None:
				self.alpha_team = None
				self.beta_team = None
			
			elif self.pick_teams == 'manual':
				self.pick_step = 0
				self.unpicked = list(players)
				self.alpha_team = []
				self.beta_team = []
				if self.captains:
					self.alpha_team.append(self.captains[0])
					self.beta_team.append(self.captains[1])
					self.unpicked.remove(self.captains[0])
					self.unpicked.remove(self.captains[1])
					
			elif self.pick_teams == 'auto':
				unpicked = list(self.players) #todo: sort by rank
				self.lastpick = unpicked[len(unpicked)-1]
				self.alpha_team = []
				self.beta_team = []
				while len(unpicked) > 1:
					self.alpha_team.append(unpicked.pop(random.randint(0,len(unpicked)-1)))
					self.beta_team.append(unpicked.pop(random.randint(0,len(unpicked)-1)))
				if len(unpicked):
					self.alpha_team.append(unpicked.pop(0))
		else: #for 1v1 pickups
			self.pick_teams = 'auto'
			self.alpha_team = [self.players[0]]
			self.beta_team = [self.players[1]]

		#set state and start time
		self.start_time = time.time()
		self.next_state()

	def think(self, frametime):
		alive_time = frametime - self.start_time
		if self.state == "waiting_ready":
			if alive_time > self.require_ready:
				not_ready = list(filter(lambda x: not self.players_ready[self.players.index(x)], self.players))
				self.players = list(filter(lambda x: x not in not_ready, self.players))
				not_ready = ["<@{0}>".format(i.id) for i in not_ready]
				client.notice(self.channel, "{0} was not ready in time!\r\nReverting **{1}** to gathering state...".format(", ".join(not_ready), self.pickup.name))
				self.ready_fallback()
		elif alive_time > max_match_alive_time:
			client.notice(self.channel, "Match [*{0}*] has timed out.".format(str(self.id)))
			self.cancel_match()

	def _teams_to_str(self):
		alpha_str = " ".join(["<@{0}>".format(i.id) for i in self.alpha_team])
		beta_str = " ".join(["<@{0}>".format(i.id) for i in self.beta_team])
		if len(self.players) > 4:
			return "{0} [{1}] {0}\r\n          :fire: **VERSUS** :fire:\r\n{2} [{3}] {2}".format(self.alpha_icon, alpha_str, self.beta_icon, beta_str)
		elif len(self.players) == 2:
			return "{0} :fire:**VERSUS**:fire: {1}".format(alpha_str, beta_str)
		else:
			return "{0} [{1}] :fire:**VERSUS**:fire: [{3}] {2}".format(self.alpha_icon, alpha_str, self.beta_icon, beta_str)
			
	def _teams_picking_to_str(self):
		if len(self.alpha_team):
			alpha_str = "[{0}]".format(" + ".join(["**{0}**".format(i.nick or i.name) for i in self.alpha_team]))
		else:
			alpha_str = "[alpha]"
		if len(self.beta_team):
			beta_str = "[{0}]".format(" + ".join(["**{0}**".format(i.nick or i.name) for i in self.beta_team]))
		else:
			beta_str = "[beta]"
		unpicked_str = ", ".join(["**{0}**".format(i.nick or i.name) for i in self.unpicked])
		return "{0} {1} :vs: {2} {3}\r\nUnpicked: {4}.".format(self.alpha_icon, alpha_str, beta_str, self.beta_icon, unpicked_str)

	def _startmsg_to_str(self):
		ipstr = self.pickup.channel.get_value("startmsg", self.pickup)
		ip = self.pickup.channel.get_value("ip", self.pickup)
		password = self.pickup.channel.get_value("password", self.pickup)
		ipstr = ipstr.replace("%ip%", ip or "").replace("%password%", password or "")
		return ipstr

	def _players_to_str(self):
		players = list(self.players)
		last_player = players.pop(len(players)-1)
		players_highlight = '<@'+'>, <@'.join([i.id for i in players])+'>'
		players_highlight += " and <@{0}> ".format(last_player.id)
		return players_highlight

	def print_startmsg_instant(self):
		if self.ranked:
			startmsg = "*({0})* **{1}** pickup has been started! ".format(str(self.id), self.pickup.name)
		else:
			startmsg = "**{0}** pickup has been started! ".format(self.pickup.name)
		
		if self.beta_team and self.alpha_team and len(self.players) > 1:
			startmsg += "\r\n"+self._teams_to_str()+"\r\n"
		else:
			startmsg += "\r\n"+self._players_to_str()
			if len(self.players) > 4:
				startmsg += "\r\n"

		startmsg += self._startmsg_to_str()

		if self.captains and self.pick_teams != 'auto' and len(self.players) > 1:
			startmsg += "\r\nSuggested captains: <@{0}> and <@{1}>.".format(self.captains[0].id, self.captains[1].id)
		if self.map:
			startmsg += "\r\nSuggested map: **{0}**.".format(self.map)

		client.notice(self.channel, startmsg)

	def print_startmsg_teams_picking_start(self):
		startmsg = "*({0})* **{1}** pickup has been started! ".format(str(self.id), self.pickup.name)
		if self.captains:
			startmsg += "<@{0}> and <@{1}> please start picking teams.\r\n".format(self.captains[0].id, self.captains[1].id)
		else:
			if len(self.players) > 4:
				startmsg += "\r\n"
			startmsg += self._players_to_str() + "please use '!capfor alpha|beta' and start picking teams.\r\n"
		startmsg += self._teams_picking_to_str()

		if self.pick_order:
			if self.pick_order[0] == 'a':
				if self.captains:
					first = "<@{0}>".format(self.captains[0].id)
				else:
					first = "Alpha"
			else:
				if self.captains:
					first = "<@{0}>".format(self.captains[1].id)
				else:
					first = "Beta"
			startmsg += "\r\n{0} picks first!".format(first)

		client.notice(self.channel, startmsg)

	def print_startmsg_teams_picking_finish(self):
		startmsg = "**TEAMS READY:**\r\n"
		startmsg += self._teams_to_str()
		startmsg += "\r\n" + self._startmsg_to_str()
		if self.map:
			startmsg += "\r\nSuggested map: **{0}**.".format(self.map)
		client.notice(self.channel, startmsg)

	def print_startmsg_report_finish(self):
		client.notice(self.channel, "Match *({0})* has been finished.".format(self.id))
		
	def next_state(self):
		if self.state == 'none':
			if self.require_ready:
				self.state = 'waiting_ready'
				client.notice(self.channel, "*({0})* **{1}** pickup is now on waiting ready state!\r\n{2} please type **!ready** or **!notready**.".format(str(self.id), self.pickup.name, ", ".join(["<@{0}>".format(i.id) for i in self.players])))
			elif self.pick_teams == 'manual':
				self.print_startmsg_teams_picking_start()
				self.state = 'teams_picking'
			elif self.ranked:
				self.print_startmsg_instant()
				self.state = 'waiting_report'
			else:
				self.print_startmsg_instant()
				self.finish_match()

		elif self.state == 'waiting_ready':
			if self.pick_teams == 'manual':
				self.print_startmsg_teams_picking_start()
				self.state = 'teams_picking'
			elif self.ranked:
				self.print_startmsg_instant()
				self.state = 'waiting_report'
			else:
				self.print_startmsg_instant()
				self.finish_match()

		elif self.state == 'teams_picking':
			if self.ranked:
				self.print_startmsg_teams_picking_finish()
				self.state = 'waiting_report'
			else:
				self.print_startmsg_teams_picking_finish()
				self.finish_match()

		elif state == 'waiting_report':
			self.print_startmsg_report_finish()
			self.finish_match()

	def finish_match(self):
		stats3.register_pickup(self.pickup.channel.id, self.pickup.name, self.players, self.lastpick, self.beta_team, self.alpha_team, self.winner)
		self.pickup.channel.lastgame_cache = stats3.lastgame(self.pickup.channel.id)
		active_matches.remove(self)

	def cancel_match(self):
		active_matches.remove(self)

	def ready_ready(self, player): #on !ready commands
		idx = self.players.index(player)
		if self.players_ready[idx]:
			client.reply(self.channel, player, "You are already ready.")
		else:
			self.players_ready[idx] = True
			if False in self.players_ready:
				self.ready_show()
			else:
				self.ready_end()

	def ready_notready(self, player): #on !notready command
		client.notice(self.channel, "**{0}** is not ready!\r\nReverting **{1}** to gathering state...".format(player.nick or player.name, self.pickup.name))
		self.players.remove(player)
		self.ready_fallback()

	def ready_show(self):
		l = []
		print(self.players)
		for idx in range(0, len(self.players)):
			print(self.players[idx].name)
			if self.players_ready[idx]:
				status = ":ok:"
			else:
				status = ":zzz:"
			l.append("{0} {1}".format(self.players[idx].nick or self.players[idx].name, status))

		print(l)
		client.notice(self.channel, " | ".join(l))

	def	ready_fallback(self): #if ready event failed
		active_matches.remove(self)
		newplayers = list(self.pickup.players)
		self.pickup.players = list(self.players)
		while len(self.pickup.players) < self.pickup.cfg['maxplayers'] and len(newplayers):
			self.pickup.players.append(newplayers.pop(0))
		if len(self.pickup.players) == self.pickup.cfg['maxplayers']:
			self.pickup.channel.start_pickup(self.pickup)
			self.pickup.players = newplayers
		if len(self.pickup.players):
			active_pickups.append(self.pickup)
		self.pickup.channel.update_topic()

	def ready_end(self):
		#client.notice(self.channel, "All players ready @ **{0}** pickup!".format(self.pickup.name))
		self.next_state()

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
		self.server = channel.server
		self.cfg = cfg
		self.update_channel_config('channel_name', channel.name)
		self.update_channel_config('server_name', channel.server.name)
		if not self.cfg['startmsg']:
			self.update_channel_config('startmsg', "please connect to steam://connect/%ip%/%password%")
			self.update_channel_config('submsg', "%promotion_role% SUB NEEDED @ **%pickup_name%**. Please connect to steam://connect/%ip%/%password%")
		self.oldtime = 0
		self.pickups = []
		self.init_pickups()
		self.pickup_groups = stats3.get_pickup_groups(self.id)
		self.lastgame_cache = stats3.lastgame(self.id)
		self.lastgame_pickup = None
		self.oldtopic = '[**no pickups**]'
		self.to_remove = [] #players
		
	def init_pickups(self):
		pickups = stats3.get_pickups(self.id)
		for i in pickups:
			try:
				self.pickups.append(Pickup(self, i))
			except Exception as e:
				console.display("ERROR| Failed to init a pickup of channel {0}({1}) @ {2}.".format(self.name, self.id, str(e)))
			
	def start_pickup(self, pickup):
		if len(pickup.players) < 2:
			client.notice(self.channel, "Pickup must have atleast 2 players added to start...")
			return

		players = list(pickup.players)
		affected_channels = list()

		pmsg = self.get_value('start_pm_msg', pickup)
		if pmsg:
			pmsg = pmsg.replace("%channel%", "<#{0}>".format(self.id))
			pmsg = pmsg.replace("%pickup_name%", pickup.name)
			pmsg = pmsg.replace("%ip%", self.get_value('ip', pickup) or "")
			pmsg = pmsg.replace("%password%", self.get_value('password', pickup) or "")

		for i in players:
			if i in allowoffline:
				allowoffline.remove(i)
			if i.id in scheduler.tasks.keys():
				scheduler.cancel_task(i.id)
			if pmsg:
				client.private_reply(self, i, pmsg)
			for pu in ( pu for pu in list(active_pickups) if i.id in [x.id for x in pu.players]):
				pu.players.remove(i)
				if not len(pu.players):
					active_pickups.remove(pu)
				if pu.channel != self:
					if i not in pu.channel.to_remove:
						pu.channel.to_remove.append(i)
					if pu.channel not in affected_channels:
						affected_channels.append(pu.channel)

		for i in affected_channels:
			client.notice(i.channel, "{0} was removed from all pickups! (pickup started on another channel)".format(", ".join(["**{0}**".format(i.nick or i.name) for i in i.to_remove])))
			i.to_remove = []
			i.update_topic()

		console.display("DEBUG| active_pickups: {0}".format(str([i.name for i in active_pickups])))
		console.display("DEBUG| allowoffline: {0}".format(str([i.name for i in allowoffline])))
		pickup.players = []
		self.update_topic()
		Match(pickup, players)
		self.lastgame_pickup = pickup

	def processmsg(self, content, member): #parse PRIVMSG event
		msgtup = content.split(" ")
		lower = [i.lower() for i in msgtup]
		msglen = len(lower)
		role_ids = [i.id for i in member.roles]
		if self.cfg['admin_role'] in role_ids or member.id == self.cfg['admin_id']:
			access_level = 2
		elif self.cfg['moderator_role'] in role_ids:
			access_level = 1
		else:
			access_level = 0

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

			elif lower[0]=="allowoffline" or lower[0]=="ao":
				self.switch_allowoffline(member)

			elif lower[0]=="remove_player" and msglen == 2:
				self.remove_players(member, lower[1], access_level)

			elif lower[0]=="who":
				self.who(member,lower[1:msglen])

			elif lower[0]=="start":
				self.user_start_pickup(member, lower[1:msglen], access_level)

			elif lower[0]=="pickups":
				self.replypickups(member)

			elif lower[0]=="promote":
				self.promote_pickup(member,lower[1:2])

			elif lower[0]=="subscribe":
				self.subscribe(member,lower[1:msglen],False)

			elif lower[0]=="unsubscribe":
				self.subscribe(member,lower[1:msglen],True)

			elif lower[0]=="lastgame":
				self.lastgame(member,msgtup[1:msglen])

			elif lower[0]=="sub":
				self.sub_request(member)

			elif lower[0] in ["cointoss", "ct"]:
				self.cointoss(member, lower[1:2])

			elif lower[0]=="pick":
				self.pick_player(member, lower[1:2])

			elif lower[0]=="put":
				self.put_player(member, lower[1:3], access_level)

			elif lower[0]=="capfor":
				self.capfor(member, lower[1:2])

			elif lower[0]=="subfor":
				self.subfor(member, lower[1:2])

			elif lower[0]=="teams":
				self.print_teams(member)

			elif lower[0]=="cancel_match":
				self.cancel_match(member, lower[1:2], access_level)

			elif lower[0] in ["ready", "r"]:
				self.set_ready(member, True)

			elif lower[0] in ["notready", "nr"]:
				self.set_ready(member, False)

			elif lower[0]=="stats":
				self.getstats(member,msgtup[1:2])

			elif lower[0]=="top":
				self.gettop(member, msgtup[1:msglen])

			elif lower[0]=="add_pickups":
				self.add_pickups(member, msgtup[1:msglen], access_level)

			elif lower[0]=="remove_pickups":
				self.remove_pickups(member, lower[1:msglen], access_level)

			elif lower[0]=="add_pickup_group":
				self.add_pickup_group(member, lower[1:msglen], access_level)

			elif lower[0]=="remove_pickup_group":
				self.remove_pickup_group(member, lower[1:msglen], access_level)

			elif lower[0]=="pickup_groups":
				self.show_pickup_groups()

			elif lower[0]=="maps":
				self.show_maps(member, lower[1:msglen], False)
			
			elif lower[0]=="map":
				self.show_maps(member, lower[1:msglen], True)

			elif lower[0]=="ip":
				self.getip(member,lower[1:2])

			elif lower[0]=="noadd" and msglen>1:
				self.noadd(member, msgtup[1:msglen], access_level)

			elif lower[0]=="forgive" and msglen==2:
				self.forgive(member,msgtup[1], access_level)

			elif lower[0]=="noadds":
				self.getnoadds(member, msgtup[1:2])

			elif lower[0]=="reset":
				self.reset_players(member, lower[1:msglen], access_level)

			elif lower[0]=="reset_stats":
				self.reset_stats(member, access_level)

			elif lower[0]=="phrase":
				self.set_phrase(member, msgtup[1:msglen], access_level)
	#		
	#		elif lower[0]=="help":
	#			client.private_reply(self.channel, member, config.cfg.HELPINFO)
	
			elif lower[0]=="commands":
				client.reply(self.channel, member, config.cfg.COMMANDS_LINK)

			elif lower[0]=="cfg":
				self.show_config(member, msgtup[1:2])

			elif lower[0]=="pickup_cfg":
				self.show_pickup_config(member, msgtup[1:3])

			elif lower[0]=="set_default" and msglen > 2:
				self.configure_default(member, msgtup[1:msglen], access_level)

			elif lower[0]=="set_pickups" and msglen > 3:
				self.configure_pickups(member, msgtup[1:msglen], access_level)

			elif lower[0]=="help":
				self.help_answer(member, lower[1:])
			
	### COMMANDS ###

	def add_player(self, member, target_pickups):
		match = self._match_by_player(member)
		if match:
			client.reply(self.channel, member, "You are already in an active match.")
			return
	
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
			if not len(target_pickups):
				filtered_pickups = list(filter(lambda p: len(p.players)>0 and int(self.cfg["++_req_players"])<=p.cfg["maxplayers"], self.pickups))
			else:
				for i in list(target_pickups):
					if i in self.pickup_groups.keys():
						target_pickups.remove(i)
						target_pickups += self.pickup_groups[i]
				filtered_pickups = list(filter(lambda p: p.name.lower() in target_pickups, self.pickups))
					
		for pickup in filtered_pickups:
			if not member.id in [i.id for i in pickup.players]:
				#check if pickup have blacklist or whitelist
				whitelist_role = self.get_value("whitelist_role", pickup)
				blacklist_role = self.get_value("blacklist_role", pickup)
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

		#add pickups from pickup_groups
		for i in list(args):
			if i in self.pickup_groups.keys():
				args.remove(i)
				args += self.pickup_groups[i]
		#remove player from games
		for pickup in list(active_pickups):
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

	def remove_players(self, member, arg, access_level):
		if access_level:
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
			templist.append('[**{0}** ({1}/{2})] {3}'.format(pickup.name, len(pickup.players), pickup.cfg['maxplayers'], '/'.join(["`"+(i.nick or i.name).replace("`","")+"`" for i in pickup.players])))
		if templist != []:
			client.notice(self.channel, ' '.join(templist))
		else:
			client.notice(self.channel, 'no one added...ZzZz')

	def user_start_pickup(self, member, args, access_level):
		if access_level:
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
			if not submsg:
				submsg = "%promotion_role% NEED SUB @ **%pickup_name%**, please connect to %ip%."
					
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
			client.reply(self.channel, member, "You lose, it's **{0}**!".format(result))
#next
	def _match_by_player(self, member):
		for i in active_matches:
			if member in i.players:
				return i
		return None

	def pick_player(self, member, args):
		match = self._match_by_player(member)
		if not match:
			client.reply(self.channel, member, "Could not find an active match.")
			return
			
		if match.state != "teams_picking":
			client.reply(self.channel, member, "The match is not on teams picking stage.")
			return

		if member in match.alpha_team[0:1]:
			team = match.alpha_team
			if match.pick_order:
				if match.pick_order[match.pick_step] == "b":
					client.reply(self.channel, member, "Not your turn to pick.")
		elif member in match.beta_team[0:1]:
			team = match.beta_team
			if match.pick_order:
				if match.pick_order[match.pick_step] == "a":
					client.reply(self.channel, member, "Not your turn to pick.")
		else:
			client.reply(self.channel, member, "You are not a captain.")
			return

		if len(args):
			targetid = args[0].lstrip("<@!").rstrip(">")
			for i in match.unpicked:
				if i.id == targetid:
					team.append(i)
					match.unpicked.remove(i)
					if len(match.unpicked) == 0:
						match.next_state()
					else:
						msg = match._teams_picking_to_str()
						if match.pick_order:
							match.pick_step += 1
							if match.pick_order[match.pick_step] == 'a':
								if len(match.alpha_team):
									who = "<@{0}>".format(match.alpha_team[0].id)
								else:
									who = "Alpha"
							else:
								if len(match.beta_team):
									who = "<@{0}>".format(match.beta_team[0].id)
								else:
									who = "Beta"
							msg += " {0}'s turn to pick.".format(who)
						client.notice(self.channel, msg)
					return
			client.reply(self.channel, member, "Specified player are not in unpicked players list.")
		else:
			client.reply(self.channel, member, "You must specify a player to pick!")

	def put_player(self, member, args, access_level):
		if not access_level:
			client.reply(self.channel, member, "You dont have right for this!")
			return

		if len(args) > 1:
			player = client.get_member_by_id(self.channel, args[0])
			if not player:
				client.reply(self.channel, member, "Specified user not found.")
				return

			match = self._match_by_player(player)
			if not match:
				client.reply(self.channel, member, "Specified user are not in a match.")
				return

			if match.pick_teams not in ['auto', 'manual']:
				client.reply(self.channel, member, "This match does not have teams.")
				return

			if args[1] == 'alpha':
				team = match.alpha_team
			elif args[1] == 'beta':
				team = match.beta_team
			else:
				client.reply(self.channel, member, "Team argument must be **alpha** or **beta**.")
				return

			if player in match.unpicked:
				match.unpicked.remove(player)
			elif player in match.beta_team:
				match.beta_team.remove(player)
			elif player in match.alpha_team:
				match.alpha_team.remove(player)
			team.append(player)
			if len(match.unpicked) == 0:
				match.next_state()
			else:
				client.notice(self.channel, match._teams_picking_to_str())

		else:
			client.reply(self.channel, member, "Not enough arguments.")

	def subfor(self, member, args):	
		if len(args):
			target = client.get_member_by_id(self.channel, args[0])
			if not target:
				client.reply(self.channel, member, "Could not find specified user.")
				return
			match = self._match_by_player(target)

			if not match:
				client.reply(self.channel, member, "Could not find an active match.")
				return

			if match.state not in ["teams_picking", "waiting_report"]:
				client.reply(self.channel, member, "The match is not on teams picking stage.")
				return

			if member in match.players:
				client.reply(self.channel, member, "You are already in the players list!")
				return

			for x in [match.unpicked, match.alpha_team, match.beta_team]:
				if target in x:
					idx = x.index(target)
					x[idx] = member
					idx = match.players.index(target)
					match.players[idx] = member
					client.notice(self.channel, match._teams_picking_to_str())
					return
			client.reply(self.channel, member, "Specified player not found in the match!")
		else:
			client.reply(self.channel, member, "You must specify a player to substitute!")

	def capfor(self, member, args):
		match = self._match_by_player(member)
		if not match:
			client.reply(self.channel, member, "Could not find an active match.")
			return
			
		if match.state != "teams_picking":
			client.reply(self.channel, member, "The match is not on the teams picking stage.")
			return

		if match.captains_role:
			if match.captains_role not in [role.id for role in member.roles]:
				client.reply(self.channel, member, "You dont possess the captain role for this pickup.")
				return

		if len(args):
			if args[0] == 'alpha':
				team = match.alpha_team
			elif args[0] == 'beta':
				team = match.beta_team
			else:
				client.reply(self.channel, member, "Specified team must be **alpha** or **beta**.")
				return
		else:
			client.reply(self.channel, member, "You must specify the team.")
			return

		for x in [match.unpicked, match.beta_team, match.alpha_team]:
			if member in x:
				idx = x.index(member)
				if len(team):
					x[idx] = team[0]
					team[0] = member
				else:
					x.remove(member)
					team.append(member)
				client.notice(self.channel, match._teams_picking_to_str())
				return

	def print_teams(self, member):
		match = self._match_by_player(member)
		if not match:
			client.reply(self.channel, member, "Could not find an active match.")
			return
		
		if match.pick_teams != "no_teams":
			client.notice(self.channel, match._teams_picking_to_str())
		else:
			client.reply(self.channel, member, "This match does not have teams.")

	def cancel_match(self, member, args, access_level):
		if not access_level:
			client.reply(self.channel, member, "You dont have right for this!")
			return

		if not len(args):
			client.reply(self.channel, member, "You must specify the match id.")
			return

		for i in active_matches:
			if str(i.id) == args[0]:
				i.cancel_match()
				client.reply(self.channel, member, "Match *({0})* has been canceled.".format(str(i.id)))
				return

		client.reply(self.channel, member, "Could not find an active match with id '{0}'".format(args[0]))

	def set_ready(self, member, isready):
		match = self._match_by_player(member)
		if not match:
			client.reply(self.channel, member, "Could not find an active match.")
			return

		if match.state != "waiting_ready":
			client.reply(self.channel, member, "This match is not on waiting_ready state.")
			return

		if isready:
			match.ready_ready(member)
		else:
			match.ready_notready(member)

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
				pickups = sorted(self.pickups, key=lambda x: len(x.players), reverse=True)
				if len(pickups[0].players):
					pickup = pickups[0]

			if pickup:
				promotion_role = self.get_value('promotion_role', pickup)
				players_left = pickup.cfg['maxplayers']-len(pickup.players)
				if promotion_role:
					roles = self.server.roles
					try:
						role_obj = next(x for x in roles if x.id==promotion_role)
					except StopIteration:
						client.notice(self.channel, "Role doesn't exist.")
						return
					role_mentionable=role_obj.mentionable
					if not role_mentionable:
						kwargs = {'server': self.server, 'role': role_obj, 'mentionable': True}
						client.edit_role(**kwargs)
						remove_role_players = []
						for player in [x for x in pickup.players if role_obj in x.roles]:
							remove_role_players.append(player)
							client.remove_roles(player,role_obj)
					client.notice(self.channel, "<@&{0}> please !add {1}, {2} players to go!".format(promotion_role, pickup.name, players_left))
					if not role_mentionable:
						for player in remove_role_players:
							client.add_roles(player, role_obj)
						kwargs = {'server': self.server, 'role': role_obj, 'mentionable': False}
						client.edit_role(**kwargs)
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

	def subscribe(self,member,args,unsub):
		print(args,type(args))
		if len(args)<1:
			client.notice(self.channel, "Specify pickup(s).")
			return
		for arg in args:
			pickup = False
			for i in self.pickups:
				if i.name.lower() == arg:
					pickup = i
					break
			if not pickup:
				client.notice(self.channel, "Pickup '{0}' not found on this channel.".format(arg))
				continue
			promotion_role = self.get_value('promotion_role', pickup)
			if promotion_role:
				roles = self.server.roles
				try:
					role_obj = next(x for x in roles if x.id == promotion_role)
				except StopIteration:
					client.notice(self.channel, "Role doesn't exist.")
					continue
				if not unsub:
					client.add_roles(member, role_obj)
				else:
					client.remove_roles(member, role_obj)
			else:
				client.notice(self.channel, "Promotion role for '{0}' not set.".format(arg))

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
		pickup = False
		if len(arg):
			if arg[0] not in ["daily", "weekly", "monthly", "yearly"]:
				pickup = arg[0]
				arg.pop(0)

		if arg == []:
			timegap = False
			reply = "Top 10 of all time"
		elif arg[0] == "daily":
			timegap = int(time.time()) - 86400
			reply = "Top 10 of the day"
		elif arg[0] == "weekly":
			timegap = int(time.time()) - 604800
			reply = "Top 10 of the week"
		elif arg[0] == "monthly":
			timegap = int(time.time()) - 2629744
			reply = "Top 10 of the month"
		elif arg[0] == "yearly":
			timegap = int(time.time()) - 31556926
			reply = "Top 10 of the year"
		else:
			client.reply(self.channel, member, "Bad argument.")
			return
		
		top10=stats3.top(self.id, timegap, pickup)
		if top10:
			if pickup:
				client.reply(self.channel, member, "{0} for {1}: {2}".format(reply, pickup, top10))
			else:
				client.reply(self.channel, member, "{0}: {1}".format(reply, top10))
		else:
			client.reply(self.channel, member, "Nothing found.")

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
	def add_pickups(self, member, targs, access_level):
		if access_level > 1:
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

	def remove_pickups(self, member, args, access_level):
		if access_level > 1:
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

	def add_pickup_group(self, member, args, access_level):
		if access_level > 1:
			if len(args) > 1:
				group_name = args[0]
				desired_pickup_names = args[1:len(args)]
				pickup_names = [i.name.lower() for i in self.pickups]
				for i in desired_pickup_names:
					if i not in pickup_names:
						client.reply(self.channel, member, "Pickup '{0}' not found.".format(i))
						return
				if group_name in pickup_names:
					client.reply(self.channel, member, "Group name can not match any of pickup names.")
					return
				if group_name in self.pickup_groups.keys():
					stats3.delete_pickup_group(self.id, group_name)
				self.pickup_groups[group_name] = desired_pickup_names
				stats3.new_pickup_group(self.id, group_name, desired_pickup_names)
				self.show_pickup_groups()
			else:
				client.reply(self.channel, member, "This command requires more arguments.")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def remove_pickup_group(self, member, args, access_level):
		if access_level > 1:
			if len(args) > 0:
				if args[0] in self.pickup_groups:
					stats3.delete_pickup_group(self.id, args[0])
					self.pickup_groups.pop(args[0])
					client.reply(self.channel, member, "Pickup group '{0}' deleted.".format(args[0]))
				else:
					client.reply(self.channel, member, "Pickup group '{0}' not found.".format(args[0]))
			else:
				client.reply(self.channel, member, "You must specify the pickup group name")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def show_pickup_groups(self):
		if not len(self.pickup_groups):
			client.notice(self.channel, "No pickup groups is configured on this channel.")
			return
		msg = "Pickup groups:"
		for i in self.pickup_groups.keys():
			msg += "\r\n**{0}**: [{1}]".format(i, ", ".join(self.pickup_groups[i]))
		client.notice(self.channel, msg)
			
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
	def set_phrase(self, member, args, access_level):
		if access_level:
			if len(args) >= 2:
				targetid = args[0]
				if re.match("^<@(!|)[0-9]+>$", targetid):
					target = client.get_member_by_id(self.channel, targetid)
					if target:
						phrase = ' '.join(args[1:len(args)])
						if phrase.lower() == "none":
							phrase = None
							client.reply(self.channel, member, "Phrase has been removed.")
						else:
							client.reply(self.channel, member, "Phrase has been set.")
						stats3.set_phrase(self.id, target.id, phrase)
					else:
						client.reply(self.channel, member, "Could not found specified Member on the server, is the highlight valid?")
				else:
					client.reply(self.channel, member, "Target must be a Member highlight.")
			else:
				client.reply(self.channel, member, "This command needs more arguments.")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def noadd(self, member, args, access_level):
		if access_level:
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

	def forgive(self, member, arg, access_level):
		if access_level:
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

	def reset_players(self, member=False, args=[], access_level=False, comment=False):
		if member == False or access_level:
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

	def reset_stats(self, member, access_level):
		if access_level > 1:
			stats3.reset_stats(self.id)
			client.reply(self.channel, member, "Done.")
		else:
			client.reply(self.channel, member, "You have no right for this!")

	def help_answer(self, member, args):
		if args != []:
			answer = None
			for p in self.pickups:
				if args[0] == p.name.lower():
					answer = self.get_value('help_answer', p)
		else:
			answer = self.cfg['help_answer']
		if answer:
			client.notice(self.channel, answer)

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
			args[0] = args[0].lower()
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

	def configure_default(self, member, args, access_level):
		if access_level < 2:
			client.reply(self.channel, member, "You have no right for this!")
			return

		variable = args.pop(0).lower()
		value = " ".join(args)

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
			
		elif variable == "captains_role":
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

		#elif variable == "noadd_role":
		#	if value.lower() == "none":
		#		self.update_channel_config(variable, None)
		#		client.reply(self.channel, member, "Removed {0} default value".format(variable))
		#	else:
		#		role = client.find_role_by_name(self.channel, value)
		#		if role:
		#			self.update_channel_config(variable, role.id)
		#			client.reply(self.channel, member, "Set '{0}' {1} as default value".format(role.name, variable))
		#		else:
		#			client.reply(self.channel, member, "Role '{0}' not found on this discord server".format(value))

		elif variable == "prefix":
			if value.lower() == "none":
				client.reply(self.channel, member, "Cant unset {0} value.".format(variable))
			else:
				if len(value) == 1:
					self.update_channel_config(variable, value)
					client.reply(self.channel, member, "Set '{0}' preffix for all commands on this channel.".format(value))
				else:
					client.reply(self.channel, member, "Prefix must be one symbol.")

		elif variable == "default_bantime":
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
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(value, variable))

		elif variable == "help_answer":
			if value.lower() == "none":
				client.reply(self.channel, member, "Cant unset {0} value.".format(variable))
			else:
				self.update_channel_config(variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(value, variable))

		elif variable == "start_pm_msg":
			if value.lower() == "none":
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
			else:
				self.update_channel_config(variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(value, variable))

		elif variable == "submsg":
			if value.lower() == "none":
				client.reply(self.channel, member, "Cant unset {0} value.".format(variable))
			else:
				self.update_channel_config(variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(value, variable))

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

		elif variable == "pick_teams":
			value = value.lower()
			if value in ["no_teams", "manual", "auto"]:
				self.update_channel_config(variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(value, variable))
			else:
				client.reply(self.channel, member, "teams_pick_system value must be no_teams, just_captains, captains_pick, manual_pick or random_teams.")

		elif variable == "pick_captains":
			if value in ["0", "1"]:
				self.update_channel_config(variable, bool(int(value)))
				client.reply(self.channel, member, "Set '{0}' {1} as default value".format(value, variable))
			else:
				client.reply(self.channel, member, "pick_captains value must be 0 or 1.")
				
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
			if value.lower() == 'none':
				self.update_channel_config(variable, None)
				client.reply(self.channel, member, "Removed {0} default value".format(variable))
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

	def configure_pickups(self, member, args, access_level):
		if access_level < 2:
			client.reply(self.channel, member, "You have no right for this!")
			return

		#determine pickup names, variable name, and value
		pickups = []
		variable = False
		for i in list(args):
			args.remove(i)
			if i != "":
				i = i.strip().lower()
				f = list(filter(lambda x: x.name.lower() == i, self.pickups))
				if len(f):
					pickups.append(f[0])
				else:
					variable = i.lower()
					break

		if not variable:
			client.reply(self.channel, member, "You must specify a variable.")
			return
		value = " ".join(args)

		if not len(pickups):
			client.reply(self.channel, member, "No specified pickups found")
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

		elif variable == "help_answer":
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				for i in pickups:
					self.update_pickup_config(i, variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(value, variable, ", ".join(i.name for i in pickups)))

		elif variable == "start_pm_msg":
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

		elif variable == "pick_teams":
			value = value.lower()
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			elif value in ["no_teams", "manual", "auto"]:
				for i in pickups:
					self.update_pickup_config(i, variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(value, variable, ", ".join(i.name for i in pickups)))
			else:
				client.reply(self.channel, member, "teams_pick_system value must be no_teams, just_captains, captains_pick, manual_pick or random_teams.")

		elif variable == "pick_captains":
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			elif value in ["0", "1"]:
				for i in pickups:
					self.update_pickup_config(i, variable, bool(int(value)))
				client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(value, variable, ", ".join(i.name for i in pickups)))
			else:
				client.reply(self.channel, member, "pick_captains value must be none, 0 or 1.")

		elif variable == "pick_order":
			value = value.lower()
			if value == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "Disabled {0} for {1} pickups.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				if len(pickups) > 1:
					client.reply(self.channel, member, "Only one pickup at time is supported for this variable configuration.")
					return
				if len(value) != pickups[0].cfg['maxplayers']-2:
					client.reply(self.channel, member, "pick_order letters count must equal required players number minus 2 (captains) for specified pickup.")
					return
				for i in value:
					if i not in ['a', 'b']:
						client.reply(self.channel, member, "pick_order letters must be 'a' (alpha) or 'b' (beta).")
						return
				self.update_pickup_config(pickups[0], variable, value)
				client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(value, variable, ", ".join(i.name for i in pickups)))

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

		elif variable == "captains_role":
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
			if value.lower() == "none":
				for i in pickups:
					self.update_pickup_config(i, variable, None)
				client.reply(self.channel, member, "{0} for {1} pickups will now fallback to the channel's default value.".format(variable, ", ".join(i.name for i in pickups)))
			else:
				try:
					seconds = utils.format_timestring(value.split(" "))
				except Exception as e:
					client.reply(self.channel, member, str(e))
					return
				for i in pickups:
					self.update_pickup_config(i, variable, seconds)
				client.reply(self.channel, member, "Set '{0}' {1} for {2} pickups.".format(seconds, variable, ", ".join(i.name for i in pickups)))

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
	for p in list(active_pickups):
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
	for match in active_matches:
		match.think(frametime)

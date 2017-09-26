#!/usr/bin/python3
# encoding: utf-8
import os, imp, sqlite3, operator, discord, asyncio

def get_role_id(channel, role_name):
	if role_name:
		for role in channel.server.roles:
			if role.name.lower() == role_name.lower():
				return role.id
	return None

def update_databases():
	known_pickup_ids = dict()
	id_step = 0
	newconn = sqlite3.connect("database.sqlite3")
	newc = newconn.cursor()
	for channel_id in os.listdir("channels"):
		if channel_id != 'default':
			channel = c.get_channel(channel_id)
			if not channel:
				print("Could not find channel with channel id '{0}', scipping...".format(channel_id))
			else:
				oldconn = sqlite3.connect("channels/{0}/stats.sql".format(channel_id))
				oldc = oldconn.cursor()
				oldc.execute("SELECT variable, value FROM config")
				l = list(oldc.fetchall())
				for i in l:
					i = list(i)
					if i[1].lower() == 'none':
						i[1] = None
					if i[0] == "ADMINROLE":
						admin_role = get_role_id(channel, i[1])
					elif i[0] == "DEFAULT_IP":
						if i[1] == "127.0.0.1":
							ip = None
						else:
							ip = i[1]
					elif i[0] == "PICKUP_PASSWORD":
						password = i[1]
					elif i[0] == "IP_FORMAT":
						startmsg = i[1]
					elif i[0] == "FIRST_INIT":
						first_init = i[1]
					elif i[0] == "BANTIME":
						default_bantime = int(i[1])*60*60
					elif i[0] == "CHANNEL_NAME":
						channel_name = i[1]
					elif i[0] == "ADMINID":
						admin_id = i[1]
					elif i[0] == "PROMOTION_DELAY":
						promotion_delay = int(i[1])*60
					elif i[0] == "PROMOTION_ROLE":
						promotion_role = get_role_id(channel, i[1])
					elif i[0] == "PREFIX":
						prefix = i[1]
					elif i[0] == "++_REQ_PLAYERS":
						req_players = int(i[1])
					elif i[0] == "FIRST_INIT":
						first_init = int(i[1])
					elif i[0] == "TEAMS_PICK_SYSTEM":
						if i[1] == "MANUAL_PICK":
							pick_captains = False
							pick_teams = "manual"
						elif i[1] == "CAPTAINS_PICK":
							pick_captains = True
							pick_teams = "manual"
						elif i[1] == "RANDOM_TEAMS":
							pick_captains = False
							pick_teams = "auto"
						else:
							pick_captains = True
							pick_teams = "no_teams"
				
				print("UPDATING CHANNEL '{0}' id '{1}'...".format(channel_name, channel_id))
						
				newc.execute("INSERT INTO channels (channel_id, channel_name, first_init, admin_id, admin_role, prefix, default_bantime, `++_req_players`, startmsg, ip, password, pick_captains, pick_teams, promotion_role, promotion_delay) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (channel_id, channel_name, first_init, admin_id, admin_role, prefix, default_bantime, req_players, startmsg, ip, password, pick_captains, pick_teams, promotion_role, promotion_delay))
			
				oldc.execute("SELECT name, maxplayers, ip, promotion_role, whitelist_role, blacklist_role, maps FROM pickups_config")
				l = list(oldc.fetchall())
				for i in l:
					i = list(i)
					if i[2] == "127.0.0.1":
						i[2] = None
					if i[3] == "none":
						i[3] = None
					if i[4] == "none":
						i[4] = None
					if i[5] == "none":
						i[5] = None
					newc.execute("INSERT INTO pickup_configs (channel_id, pickup_name, maxplayers, ip, promotion_role, whitelist_role, blacklist_role, maps) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (channel_id, i[0], i[1], i[2], i[3], i[4], i[5], i[6]))
			
				oldc.execute("SELECT memberid, phrase FROM players")
				l = list(oldc.fetchall())
				for i in l:
					i = list(i)
					if i[1].lower() == "false":
						i[1] = None
					newc.execute("INSERT INTO channel_players (channel_id, user_id, phrase) VALUES (?, ?, ?)", (channel_id, i[0], i[1]))

				oldc.execute("SELECT id, time, gametype, players FROM pickups")
				l = oldc.fetchall()
				for i in l:
					known_pickup_ids[i[0]] = id_step
					newc.execute("INSERT INTO pickups (channel_id, pickup_id, at, pickup_name, players) VALUES (?, ?, ?, ?, ?)", (channel_id, id_step, i[1], i[2], i[3]))
					id_step += 1

				oldc.execute("SELECT pickup_id, memberid, membername, time, gametype FROM player_games")
				l = oldc.fetchall()
				for i in l:
					newc.execute("INSERT INTO player_pickups (channel_id, pickup_id, user_id, user_name, at, pickup_name) VALUES (?, ?, ?, ?, ?, ?)", (channel_id, known_pickup_ids[i[0]], i[1], i[2], i[3], i[4]))
				oldconn.close()

	newconn.commit()
	newconn.close()


c = discord.Client()
loop = asyncio.get_event_loop()

@c.event
@asyncio.coroutine
def on_ready():
	update_databases()
	print("SUCCESSFULLY UPDATED")
	c.close()
	os.rename("channels", "channels_old")
	os._exit(0)
		
f = open('config.cfg', 'r')
cfg = imp.load_source('data', '', f)
f.close()

try:
	if cfg.DISCORD_TOKEN != "":
		print("SYSTEM| logging in with token...")
		loop.run_until_complete(c.login(cfg.DISCORD_TOKEN))
	else:
		print("SYSTEM| logging in with username and password...")
		loop.run_until_complete(c.login(cfg.USERNAME, cfg.PASSWORD))
	loop.run_until_complete(c.connect())
except:
	pass

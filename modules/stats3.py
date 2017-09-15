#!/usr/bin/python2
import sqlite3, operator
from datetime import timedelta
from time import time
import re

#INIT

def init():
	global conn, c
	conn = sqlite3.connect("database.sqlite3")
	c = conn.cursor()
	check_tables()

def get_channels():
	l = []
	c.execute("SELECT * from channels")
	chans = c.fetchall()
	l = []
	for chan in chans:
		d = _channelcfg_to_dict(chan)
		l.append(d)
	return l

def _channelcfg_to_dict(l):
	d = dict()
	d["server_id"] = l[0]
	d["server_name"] = l[1]
	d["channel_id"] = l[2]
	d["channel_name"] = l[3]
	d["premium"] = l[4]
	d["first_init"] = l[5]
	d["admin_id"] = l[6]
	d["admin_role"] = l[7]
	d["moderator_role"] = l[8]
	d["captain_role"] = l[9]
	d["noadd_role"] = l[10]
	d["prefix"] = l[11]
	d["default_bantime"] = l[12]
	d["++_req_players"] = l[13]
	d["startmsg"] = l[14]
	d["submsg"] = l[15]
	d["ip"] = l[16]
	d["password"] = l[17]
	d["maps"] = l[18]
	d["teams_pick_system"] = l[19]
	d["promotion_role"] = l[20]
	d["promotion_delay"] = l[21]
	d["blacklist_role"] = l[22]
	d["whitelist_role"] = l[23]
	d["require_ready"] = l[24]
	d["readd_treshold"] = l[25]
	return d

def _pickupcfg_to_dict(l):
	d = dict()
	d["channel_id"] = l[0]
	d["pickup_name"] = l[1]
	d["maxplayers"] = l[2]
	d["minplayers"] = l[3]
	d["startmsg"] = l[4]
	d["submsg"] = l[5]
	d["ip"] = l[6]
	d["password"] = l[7]
	d["maps"] = l[8]
	d["teams_pick_system"] = l[9]
	d["pick_order"] = l[10]
	d["promotion_role"] = l[11]
	d["blacklist_role"] = l[12]
	d["whitelist_role"] = l[13]
	d["captain_role"] = l[14]
	d["require_ready"] = l[15]
	d["ready_timeout"] = l[16]
	return d

def get_pickups(channel_id):
	c.execute("SELECT * from pickup_configs WHERE channel_id = ?", (channel_id, ))
	pickups = c.fetchall()
	l = []
	for pickup in pickups:
		d = _pickupcfg_to_dict(pickup)
		l.append(d)
	return l

def new_channel(server_id, server_name, channel_id, channel_name, admin_id):
	c.execute("INSERT OR REPLACE INTO channels (server_id, server_name, channel_id, channel_name, first_init, admin_id) VALUES (?, ?, ?, ?, ?, ?)", (server_id, server_name, channel_id, channel_name, str(int(time())), admin_id))
	conn.commit()
	c.execute("SELECT * from channels WHERE channel_id = ?", (channel_id, ))
	chan = c.fetchone()
	d = _channelcfg_to_dict(chan)
	return d

def new_pickup(channel_id, pickup_name, maxplayers):
	c.execute("INSERT INTO pickup_configs (channel_id, pickup_name, maxplayers) VALUES (?, ?, ?)", (channel_id, pickup_name, maxplayers))
	conn.commit()
	c.execute("SELECT * from pickup_configs WHERE channel_id = ? AND pickup_name = ?", (channel_id, pickup_name))
	result = c.fetchone()
	return _pickupcfg_to_dict(result)
	

def delete_pickup(channel_id, pickup_name):
	c.execute("DELETE FROM pickup_configs WHERE channel_id = ? AND pickup_name = ? COLLATE NOCASE", (channel_id, pickup_name))
	conn.commit()

def delete_channel(channel_id):
	c.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id, ))
	c.execute("DELETE FROM channel_players WHERE channel_id = ?", (channel_id, ))
	c.execute("DELETE FROM bans WHERE channel_id = ?", (channel_id, ))
	c.execute("DELETE FROM pickup_configs WHERE channel_id = ?", (channel_id, ))
	c.execute("DELETE FROM player_pickups WHERE channel_id = ?", (channel_id, ))
	c.execute("DELETE FROM pickups WHERE channel_id = ?", (channel_id, ))
	conn.commit()

def register_pickup(channel_id, pickup_name, players):
	at = int(time())
	playersstr = " " + " ".join([i.name for i in players]) + " "

	#insert pickup
	c.execute("INSERT INTO pickups (channel_id, pickup_name, at, players) VALUES (?, ?, ?, ?)", (channel_id, pickup_name, at, playersstr))
	#update player_games and players
	for player in players:
		c.execute("INSERT OR IGNORE INTO player_pickups (channel_id, user_id, user_name, pickup_name, at) VALUES (?, ?, ?, ?, ?)", (channel_id, player.id, player.name, pickup_name, at))
	conn.commit()

def lastgame(channel_id, text=False): #[id, gametype, ago, [players], [caps]]
	if not text: #return lastest game
		c.execute("SELECT pickup_id, at, pickup_name, players, alpha_players, beta_players FROM pickups WHERE channel_id = ? ORDER BY pickup_id DESC LIMIT 1", (channel_id, ))
		result = c.fetchone()
	else:
		#try to find last game by gametype
		c.execute("SELECT pickup_id, at, pickup_name, players, alpha_players, beta_players FROM pickups WHERE channel_id = ? and pickup_name = ? ORDER BY pickup_id DESC LIMIT 1 COLLATE NOCASE", (channel_id, text))
		result = c.fetchone()
		if result == None: #no results, try to find last game by player
			c.execute("SELECT pickup_id, at, pickup_name, players, alpha_players, beta_players FROM pickups WHERE channel_id = '{0}' and players LIKE '% {1} %' ORDER BY pickup_id DESC LIMIT 1".format(channel_id, text))
			result = c.fetchone()
	return result

def stats(channel_id, text=False):
	if not text: #return overall stats
		c.execute("SELECT pickup_name, count(pickup_name) FROM pickups WHERE channel_id = ? GROUP BY pickup_name", (channel_id, ))
		l = c.fetchall()
		if l != None:
			pickups = []
			total = 0
			for i in l:
				pickups.append("{0}: {1}".format(i[0], i[1])) 
				total += i[1]
			return "Total pickups: {0} | {1}".format(total, ", ".join(pickups))
		else:
			return "No pickups played yet." ###STOP###
	else:
		# get total pickups count
		c.execute("SELECT count(channel_id) FROM pickups WHERE channel_id = ? GROUP BY channel_id", (channel_id, ))
		l = c.fetchone()
		if l != None:
			total = l[0]
		else:
			return "No pickups played yet."

		# try to find by pickup_name
		c.execute("SELECT pickup_name, count(pickup_name) FROM pickups WHERE channel_id = ? AND pickup_name = ? COLLATE NOCASE GROUP BY pickup_name ", (channel_id, text))
		l = c.fetchone()
		if l != None:
			percent = int((float(l[1]) / total) * 100)
			return "Stats for **{0}**. Played: {1} ({2}%).".format(l[0], l[1], percent)
		else:
			# try to find by user_name
			c.execute("SELECT user_id, user_name FROM player_pickups WHERE channel_id = ? AND user_name = ? COLLATE NOCASE LIMIT 1", (channel_id, text))
			l = c.fetchone()
			if l != None:
				user_id = l[0]
				user_name = l[1]
			else:
				return "Nothing found."
			
			c.execute("SELECT pickup_name, count(pickup_name) FROM player_pickups WHERE channel_id = ? AND user_id = ? GROUP BY pickup_name", (channel_id, user_id))
			l = c.fetchall()
			pickups = []
			user_total = 0
			for i in l:
				pickups.append("{0}: {1}".format(i[0], i[1]))
				user_total += i[1]
			percent = int((float(user_total) / total) * 100)
			return "Stats for **{0}**. Played {1} ({2}%): {3}".format(user_name, user_total, percent, ", ".join(pickups))

def top(channel_id, timegap=False):
	if not timegap:
		c.execute("SELECT user_name, count(user_id) FROM player_pickups WHERE channel_id = ? GROUP BY user_id ORDER by count(user_id) DESC LIMIT 10", (channel_id, ))
	else:
		c.execute("SELECT user_name, count(user_id) FROM player_pickups WHERE channel_id = ? and at > ? GROUP BY user_id ORDER by count(user_id) DESC LIMIT 10", (channel_id, timegap))
	l = c.fetchall()
	top = ["{0}: {1}".format(i[0], i[1]) for i in l]
	return ', '.join(top)

def noadd(channel_id, user_id, user_name, duratation, author_name, reason=''):
	c.execute("SELECT * FROM bans WHERE user_id = ? AND channel_id = ? AND active = 1", (user_id, channel_id))
	ban = c.fetchone()
	if ban != None:
		c.execute("UPDATE bans SET at=?, duratation=?, author_name=?, reason=? WHERE user_id = ? AND channel_id = ? AND active = 1", (int(time()), duratation, author_name, reason, user_id, channel_id))
		conn.commit()
		return("Updated {0}'s noadd to {1} from now.".format(user_name, str(timedelta(seconds=duratation))))
	else:
		#add new ban
		c.execute("INSERT INTO bans (channel_id, user_id, user_name, active, at, duratation, reason, author_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (channel_id, user_id, user_name, 1, int(time()), duratation, reason, author_name))
		conn.commit()
		#Get a quote!
		c.execute("SELECT * FROM nukem_quotes ORDER BY RANDOM() LIMIT 1")
		quote = c.fetchone()
		return("Banned {0} for {1}. {2}".format(user_name, str(timedelta(seconds=duratation)), quote[0]))

def forgive(channel_id, user_id, user_name, unban_author_name):
	c.execute("SELECT * FROM bans WHERE user_id = ? AND channel_id = ? AND active = 1", (user_id, channel_id))
	ban = c.fetchone()
	if ban != None:
		c.execute("UPDATE bans SET active = 0, unban_author_name = ? WHERE user_id = ? AND channel_id = ? AND active = 1", (unban_author_name, user_id, channel_id))
		conn.commit()
		return("{0} forgiven.".format(user_name))
	return("Ban not found!")

def noadds(channel_id, index=None):
	if index == None:
		c.execute("SELECT user_name, active, at, duratation, reason, author_name, unban_author_name FROM bans WHERE channel_id = ? AND active = 1", (channel_id, ))
	else:
		c.execute("SELECT user_name, active, at, duratation, reason, author_name, unban_author_name FROM bans WHERE channel_id = ? ORDER BY at DESC LIMIT ?", (channel_id, index+10))
	bans = c.fetchall()
	bans_str = []
	for ban in bans[0:10]:
		if ban[1] == 1:
			timeleft = timedelta( seconds=int(ban[3]-(time()-ban[2])) )
			#user_name, timeleft, author: reason
			bans_str.append("{0}, {1} left, by {2}: {3}".format(ban[0], timeleft, ban[5], ban[4]))
		else:
			ago = timedelta( seconds=int(time()-ban[2]) )
			#user_name, ago, author (reason), unban_author
			bans_str.append("{0}, {1} ago, by {2} ({3}), unbanned by {4}".format(ban[0], ago, ban[5], ban[4], ban[6]))
	return bans_str

def check_memberid(channel_id, user_id): #check on bans and phrases
	#returns (bool is_banned, string phrase, int default_expire)

	#check if he is banned
	unbanned=False
	c.execute("SELECT at, duratation, reason FROM bans WHERE user_id = ? AND channel_id = ? AND active = 1", (user_id, channel_id))
	ban = c.fetchone()
	if ban:
		ban = list(ban)
		seconds_left = int(ban[1]-(time()-ban[0]))
		if seconds_left > 0:
			timeleft = timedelta(seconds=seconds_left)
			if ban[2] != '':
				ban[2] = " Reason : {0}".format(ban[2])
			return( (True, "You have been banned. {0} time left.{1}".format(timeleft, ban[2]), None) )
		else:
			c.execute("UPDATE bans SET active = 0, unban_author_name = ? WHERE user_id = ? AND channel_id = ? AND active = 1", ("time", user_id, channel_id))
			conn.commit()
			return( (False, "Be nice next time, please.", None) )

	#no bans, find phrases!
	c.execute("SELECT default_expire FROM players WHERE user_id = ?", (user_id, ))
	l = c.fetchone()
	if l:
		expire = l[0]
	else:
		expire = None
	c.execute("SELECT phrase FROM channel_players WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
	l = c.fetchone()
	if l:
		phrase = l[0]
	else:
		phrase = None
		
	return( (False, phrase, expire) )

#get default user !expire time
def get_expire(user_id):
	c.execute("SELECT default_expire FROM players WHERE user_id = ?", (user_id, ))
	l = c.fetchone()
	if l:
		return(l[0])
	else:
		return(None)

#set default user !expire time
def set_expire(user_id, seconds):
	#create user if not exists
	c.execute("INSERT OR IGNORE INTO players (user_id) VALUES (?)", (user_id, ))
	c.execute("UPDATE players SET default_expire = ? WHERE user_id = ?", (seconds, user_id))
	conn.commit()

def set_phrase(channel_id, user_id, phrase):
	#create user if not exists
	c.execute("INSERT OR IGNORE INTO channel_players (channel_id, user_id) VALUES (?, ?)", (channel_id, user_id))
	c.execute("UPDATE channel_players SET phrase = ? WHERE user_id = ? AND channel_id = ?", (phrase, user_id, channel_id ))
	conn.commit()
		
def save_config(channel_id, cfg, pickups):
	c.execute("INSERT OR REPLACE INTO channels VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (*cfg.values(), ))
	for i in pickups:
		c.execute("INSERT OR REPLACE INTO pickup_configs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (channel_id, i.name, i.maxplayers, i.minplayers, i.startmsg, i.maps, i.teams_pick_system, i.promotion_role, i.blacklist_role, i.whitelist_role))
	conn.commit()

def update_channel_config(channel_id, variable, value):
	c.execute("UPDATE OR IGNORE channels SET {0} = ? WHERE channel_id = ?".format(variable), (value, channel_id))
	conn.commit()

def update_pickup_config(channel_id, pickup_name, variable, value):
	c.execute("UPDATE OR IGNORE channels SET {0} = ? WHERE channel_id = ? and pickup_name = ?".format(variable), (value, channel_id, pickup_name))
	conn.commit()

def update_pickups(channel_id, pickups):
	for i in pickups:
		c.execute("INSERT OR REPLACE INTO pickup_configs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (channel_id, i.name, i.maxplayers, i.minplayers, i.startmsg, i.maps, i.teams_pick_system, i.promotion_role, i.blacklist_role, i.whitelist_role))
	conn.commit()

def check_tables():
	c.execute("CREATE TABLE IF NOT EXISTS `bans` ( `channel_id` TEXT, `user_id` TEXT, `user_name` TEXT, `active` BLOB, `at` INTEGER, `duratation` INTEGER, `reason` TEXT, `author_name` TEXT, `unban_author_name` TEXT )")

	c.execute("CREATE TABLE IF NOT EXISTS `channel_players` ( `channel_id` TEXT, `user_id` TEXT, `points` INTEGER, `lastpicked` INTEGER, `phrase` TEXT, PRIMARY KEY(`channel_id`, `user_id`) )")

	c.execute("CREATE TABLE IF NOT EXISTS `channels` ( `server_id` TEXT, `server_name` TEXT, `channel_id` TEXT, `channel_name` TEXT, `premium` BOOL, `first_init` INTEGER, `admin_id` TEXT, `admin_role` TEXT, `moderator_role` TEXT, `captain_role` TEXT, `noadd_role` TEXT, `prefix` TEXT DEFAULT '!', `default_bantime` INTEGER DEFAULT 7200, `++_req_players` INTEGER DEFAULT 4, `startmsg` TEXT, `submsg` TEXT, `ip` TEXT, `password` TEXT, `maps` TEXT, `teams_pick_system` TEXT, `promotion_role` TEXT, `promotion_delay` INTEGER DEFAULT 18000, `blacklist_role` TEXT, `whitelist_role` TEXT, `require_ready` INTEGER, `readd_treshold` INTEGER, PRIMARY KEY(`channel_id`) )")
	
	c.execute("CREATE TABLE IF NOT EXISTS `nukem_quotes` ( `quote` TEXT )")
	
	c.execute("CREATE TABLE IF NOT EXISTS `pickup_configs` ( `channel_id` TEXT, `pickup_name` TEXT, `maxplayers` INTEGER, `minplayers` INTEGER, `startmsg` TEXT, `start_pm_msg` TEXT, `submsg` TEXT, `ip` TEXT, `password` TEXT, `maps` TEXT, `teams_pick_system` TEXT, `pick_order` TEXT, `promotion_role` TEXT, `blacklist_role` TEXT, `whitelist_role` TEXT, `captain_role` TEXT, `require_ready` INTEGER, PRIMARY KEY(`channel_id`, `pickup_name`) )")
	
	c.execute("CREATE TABLE IF NOT EXISTS `pickups` ( `pickup_id` INTEGER PRIMARY KEY, `channel_id` TEXT, `pickup_name` TEXT, `at` INTEGER, `players` TEXT, `alpha_players` TEXT, `beta_players` TEXT )")
	
	c.execute("CREATE TABLE IF NOT EXISTS `player_pickups` ( `pickup_id` INTEGER, `channel_id` TEXT, `user_id` TEXT, `user_name` TEXT, `pickup_name` TEXT, `at` INTEGER, `team` TEXT )")
	
	c.execute("CREATE TABLE IF NOT EXISTS `players` ( `user_id` TEXT, `default_expire` INTEGER, `disable_pm` BLOB, PRIMARY KEY(`user_id`) )")

	conn.commit()

def close():
	conn.commit()
	conn.close()

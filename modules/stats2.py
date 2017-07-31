#!/usr/bin/python2
import sqlite3, operator
from datetime import timedelta
from time import time
import re

#INIT
class Stats():

	def __init__(self, channel):
		self.conn = sqlite3.connect("channels/{0}/stats.sql".format(channel.id))
		self.c = self.conn.cursor()

		#check if we have all tables we need, create if needed
		self.update_tables()

		self.c.execute("SELECT * from config")
		config_table = self.c.fetchall()
		for i in config_table:
			channel.cfg[i[0]] = i[1]

		self.c.execute("SELECT * from pickups_config")
		self.pickup_table = self.c.fetchall()

	def register_pickup(self, gametype, players, caps):
		playersstr = " " + " ".join([i.name for i in players]) + " "
		if caps:
			cap1, cap2 = [i.name for i in caps]
		else:
			cap1, cap2 = ['','']
		#update overall_stats
		self.c.execute("UPDATE overall_stats SET pickups = pickups+1")

		#insert pickup
		self.c.execute("INSERT INTO pickups (time, gametype, cap1, cap2, players) VALUES (?, ?, ?, ?, ?)", (int(time()), gametype, cap1, cap2, playersstr))
		self.c.execute("SELECT last_insert_rowid()")
		pickupid = self.c.fetchone()[0]

		#update gametype
		self.c.execute("INSERT OR IGNORE INTO gametypes VALUES (?, 0, 0)", (gametype, ))
		self.c.execute("UPDATE gametypes SET played = played+1, lastgame = ? WHERE gametype = ?", (pickupid, gametype))

		#update player_games and players
		for player in players:
			self.c.execute("INSERT OR IGNORE INTO players VALUES (?, ?, 0, 0, 0, 0, 'False', 0)", (player.name, player.id ))
			self.c.execute("UPDATE players SET played=played+1, lastgame = ?, membername = ? WHERE memberid = ?", (pickupid, player.name, player.id))
			self.c.execute("INSERT INTO player_games (pickup_id, memberid, membername, time, gametype) VALUES (?, ?, ?, ?, ?)", (pickupid, player.id, player.name, int(time()), gametype))
		if caps:
			for player in caps:
				self.c.execute("UPDATE players SET caps=caps+1 WHERE memberid = ?", (player.id, ))
		self.conn.commit()

	def lastgame(self, text=False): #[id, gametype, ago, [players], [caps]]
		if not text: #return lastest game
			self.c.execute("SELECT * FROM pickups ORDER BY id DESC LIMIT 1")
			result = self.c.fetchone()
		else:
			#try to find last game by gametype
			self.c.execute("SELECT lastgame FROM gametypes WHERE gametype = ? COLLATE NOCASE", (text,))
			tmp = self.c.fetchone()
			if tmp != None:
				pickupid = tmp[0]
				self.c.execute("SELECT * FROM pickups WHERE id = ?", (pickupid,))
				result = self.c.fetchone()
			else: #no results, try to find last game by player
				self.c.execute("SELECT * FROM pickups WHERE players LIKE '% {0} %' ORDER BY id DESC LIMIT 1".format(text))
				result = self.c.fetchone()

		#return result
		if result != None:
			#players = result[5].strip().replace(" ",", ")
			#caps = "{0}, {1}".format(result[3],result[4])
			#ago = timedelta(seconds=int(time() - int(result[1])))
		
			#return id, time, gametype, caps, players
			return result[0], result[1], result[2], [result[3],result[4]], result[5].strip().split()
		else:
			return False

	def stats(self, text=False):
		if not text: #return overall stats
			self.c.execute("SELECT * FROM overall_stats")
			l = self.c.fetchone()
			if l != None:
				pickups, bans = l[0], l[1]
				self.c.execute("SELECT * FROM gametypes ORDER BY played DESC")
				l=[]
				for i in self.c:
					l.append("{0}: {1}".format(i[0],i[1]))
				return "Total pickups: {0}, noadds: {1}. | {2}".format(pickups, bans, ", ".join(l))
			else:
				return "No pickups played yet."
		else:
			d=dict()
			self.c.execute("SELECT * FROM players WHERE membername = ?", (text, ))
			result = self.c.fetchone()
			#print(result)
			if result != None:
				memberid, played, wascap, bans = result[1], result[2], result[3], result[4]
				self.c.execute("SELECT pickups FROM overall_stats")
				if played != 0:
					percent = int((float(played) / self.c.fetchone()[0]) * 100)
				else:
					percent = 0
				self.c.execute("SELECT * FROM player_stats WHERE memberid = ?", (memberid, ))
				dstr = ""
				for i in self.c.fetchall():
					if i[1] in d:
						d[i[1]]+=1
					else:
						d[i[1]]=1
				dstr = ', '.join("{0}: {1}".format(key,val) for (key,val) in d.items())
				return "Stats for {0}. Played: {1} ({2}%), was cap: {3}, noadded: {4} | {5}.".format(text, played, percent, wascap, bans, dstr)
			self.c.execute("SELECT * FROM gametypes WHERE gametype = ?", (text, ))
			result = self.c.fetchone()
			if result != None:
				played = result[1]
				self.c.execute("SELECT pickups FROM overall_stats")
				percent = int((float(played) / self.c.fetchone()[0]) * 100)
				return "Stats for {0} pickups. Played {1}, {2}% of all games.".format(text, played, percent)
			return "No pickups found for " + text

	def top(self, timegap=False):
		if not timegap:
			self.c.execute("SELECT membername, played FROM players ORDER BY played DESC LIMIT 10")
			l = self.c.fetchall()
			s = ', '.join("{0}: {1}".format(i[0],i[1]) for i in [x for x in l])
			return s
		if timegap:
			d=dict()
			self.c.execute("SELECT membername FROM player_games WHERE time > ?", (timegap, ))
			l = self.c.fetchall()
			if l == []:
				return ""
			for player in l:
				if player[0] in d:
					d[player[0]] += 1
				else:
					d[player[0]] = 1
			top = sorted(list(d.items()), key=operator.itemgetter(1), reverse=True)
			s = ', '.join("{0}: {1}".format(i[0],i[1]) for i in [x for x in top[0:10]])
			return s
		#print [x for x in c]



	def noadd(self, member, duratation, admin, reason=''):
		self.c.execute("SELECT * FROM bans WHERE active = 1 AND memberid = ?", (member.id, ))
		ban = self.c.fetchone()
		if ban != None:
			self.c.execute("""UPDATE bans SET time=?, duratation=?, reason=?, admin=? WHERE active = 1 AND memberid = ?""", (int(time()), duratation*60*60, reason, admin, member.id))
			self.conn.commit()
			return("Updated {0}'s noadd to {1} hours from now.".format(member.name, duratation))
		else:
			#add new ban
			self.c.execute("UPDATE overall_stats SET bans = bans+1")
			self.c.execute("INSERT OR IGNORE INTO players VALUES (?, ?, 0, 0, 0, 0, 'False', 0)", (member.name, member.id ))
			self.c.execute("UPDATE players SET bans = bans+1 WHERE memberid = ?", (member.id, ))
			self.c.execute("INSERT INTO bans (memberid, membername, active, time, duratation, reason, admin) VALUES (?, ?, 1, ?, ?, ?, ?)", (member.id, member.name, int(time()), duratation*60*60, reason, admin))
			self.conn.commit()
			#return("Banned {0} for {1} hours".format(nick, duratation))
			#Get a quote!
			self.c.execute("SELECT * FROM nukem_quotes ORDER BY RANDOM() LIMIT 1")
			quote = self.c.fetchone()
			return(quote[0])

	def forgive(self, member, admin):
		self.c.execute("SELECT * FROM bans WHERE active = 1 and memberid = ?", (member.id, ))
		ban = self.c.fetchone()
		if ban != None:
			self.c.execute("UPDATE bans SET active = 0, unban_admin = ? WHERE active = 1 and memberid = ?", (admin, member.id))
			self.conn.commit()
			return("{0} forgiven.".format(member.name))
		return("Ban not found!")

	def noadds(self, memberid=False,number=False):
		if not memberid and not number:
			l,s,s1 = [],"", "Noadds: "
			self.c.execute("SELECT * FROM bans WHERE active = 1")
			bans = self.c.fetchall()
			for i in bans:
				#print(i)
				if i[4]+i[5] > time(): # if time didnt ran out
					number = i[0]
					name = i[2]
					timeleft=timedelta( seconds=int(i[5]-(time()-i[4])) )
					s='#{0} {1}, {2} time left | '.format(number,name,timeleft)
					print(len(s1+s))
					if len(s1+s) > 230:
						l.append(s1)
						s1 = s
					else:
						s1 = s1+s
			if s1 != "Noadds: ":
				l.append(s1)
				return l
		else:
			if number: #search by number
				self.c.execute("SELECT * FROM bans WHERE id = ?", (number, ))
			else: #search active ban by nick
				self.c.execute("SELECT * FROM bans WHERE active = 1 AND membername = ?", (memberid, ))
			ban = self.c.fetchone()
			if ban != None:
				number = ban[0]
				name = ban[2]
				if ban[6] == "False":
					reason = "\"\""
				else:
					reason = "\"{0}\"".format(ban[6])
				admin = ban[7]
				if ban[8] != None:
					unbanned_or_timeleft="unbanned by "+ban[8]
				else:
					#print("time", ban[5] - (time()-ban[4]))
					unbanned_or_timeleft=str(timedelta( seconds=int(ban[5]-(time()-ban[4])) ))+" time left"
				s='#{0} {1}, {2}, by {3}, {4}.'.format(number,name,reason, admin, unbanned_or_timeleft)
				return([s,])
		return(["Nothing found.", ])

	def check_memberid(self, memberid): #check on bans and phrases

		#check if he is banned
		unbanned=False
		self.c.execute("SELECT * FROM bans WHERE active = 1")
		bans = self.c.fetchall()
		for ban in bans:
			if ban[1] == memberid:
				if ban[4]+ban[5] > time():
					timeleft=timedelta( seconds=int(ban[5]-(time()-ban[4])) )
					if ban[6] != "":
						reason = " Reason: {0}.".format(ban[6])
					else:
						reason = ""
					return((True, "You have been banned. {0} time left.{1}".format(timeleft, reason)))
				else: #ban time ran out, disable ban
					self.c.execute("UPDATE bans SET active = 0, unban_admin = ? WHERE id = ? ", ("time", ban[0]))
					unbanned=True
			if unbanned:
				self.conn.commit()
				return((False, "Be nice next time, please."))

		#no bans, find phrases!
		self.c.execute("SELECT phrase FROM players WHERE memberid = ? AND phrase != 'False'", (memberid, ))
		phrase = self.c.fetchone()
		if phrase != None:
			return((False, phrase[0]))
		return((False, False))

	#get default user !expire time
	def get_expire(self, memberid):
		self.c.execute("SELECT expire FROM players WHERE memberid = ?", (memberid, ))
		l = self.c.fetchone()
		if l:
			return(l[0])
		else:
			return(0)

	#set default user !expire time
	def set_expire(self, membername, memberid, seconds):
		#create user if not exists
		self.c.execute("INSERT OR IGNORE INTO players VALUES (?, ?, 0, 0, 0, 0, 'False', 0)", (membername, memberid ))
		self.c.execute("UPDATE players SET expire = ? WHERE memberid = ?", (seconds, memberid ))

	def set_phrase(self, member, phrase):
		self.c.execute("SELECT phrase FROM players WHERE memberid = ?", (member.id, ))
		sel = self.c.fetchone()
		if sel != None:
			self.c.execute("""UPDATE players SET phrase = ? WHERE memberid = ?""", (phrase, member.id))
			self.conn.commit()
		else:
			self.c.execute("INSERT INTO players VALUES (?, ?, 0, 0, 0, 0, ?, 0)", (member.name, member.id, phrase))
			self.conn.commit()
	
	def show_help(self, command):
		self.c.execute("SELECT text FROM help WHERE command = ?", (command, ))
		result = self.c.fetchone()
		if result != None:
			return result[0]
		else:
			return "Command not found! See '!commands'."
	def show_commands(self):
		self.c.execute("SELECT command FROM help")
		result = self.c.fetchall()
		commands = [x[0] for x in result]
		return " ".join(commands)

	def update_max_expire_time(self, seconds):
		self.c.execute("UPDATE players SET expire = ? WHERE expire > ?", (seconds, seconds))
		
	def save_config(self, cfg, pickups):
		for var in cfg.keys():
			self.c.execute("UPDATE OR IGNORE config SET value = ? WHERE variable = ?", (cfg[var], var))
			pickup_list = []
			for i in pickups:
				self.c.execute("""INSERT OR REPLACE INTO pickups_config VALUES(?, ?, ?, ?, ?, ?, ?);""", (i.name, i.maxplayers, i.ip, i.promotion_role, i.whitelist_role, i.blacklist_role, ", ".join(i.maps)))
		self.conn.commit()

	def update_config(self, variable, value):
		self.c.execute("UPDATE OR IGNORE config SET value = ? WHERE variable = ?", (value, variable))
		self.conn.commit()

	def update_pickups(self, pickups):
		for i in pickups:
			self.c.execute("""INSERT OR REPLACE INTO pickups_config VALUES(?, ?, ?, ?, ?, ?, ?);""", (i.name, i.maxplayers, i.ip, i.promotion_role, i.whitelist_role, i.blacklist_role, ", ".join(i.maps)))
		self.conn.commit()

	def close(self):
		self.conn.commit()
		self.conn.close()

	def update_tables(self):
		self.c.execute("""SELECT value FROM config WHERE variable='PICKUP_LIST';""")
		old_pickups = self.c.fetchone()
		if old_pickups != None:
			self.c.execute("""CREATE TABLE IF NOT EXISTS pickups_config (name TEXT, maxplayers INTEGER, ip TEXT, promotion_role TEXT, whitelist_role TEXT, blacklist_role TEXT, PRIMARY KEY(name));""")
			for i in eval(old_pickups[0]):
				self.c.execute("""INSERT OR IGNORE INTO pickups_config VALUES(?, ?, ?, ?, ?, ?);""", (i[0], i[1], i[2], 'none', 'none', 'none'))
			self.c.execute("""DELETE FROM config WHERE variable = 'PICKUP_LIST';""")

		self.c.execute("""UPDATE OR IGNORE config SET value = ? WHERE variable = ? AND value = ?""", (str(int(time())), "FIRST_INIT", "False"))

		self.c.execute("PRAGMA table_info(players)")
		if 'expire' not in [i[1] for i in self.c.fetchall()]:
			self.c.execute("ALTER TABLE players ADD COLUMN expire INTEGER NOT NULL DEFAULT 0")

		self.c.execute("PRAGMA table_info(pickups_config)")
		if 'maps' not in [i[1] for i in self.c.fetchall()]:
			self.c.execute("ALTER TABLE pickups_config ADD COLUMN maps TEXT NOT NULL DEFAULT ''")

		self.c.execute("""DELETE FROM config WHERE variable = 'FIRST_INIT_MESSAGE';""")
		self.c.execute("""DELETE FROM config WHERE variable = 'CHANGE_TOPIC';""")
		self.c.execute("""DELETE FROM config WHERE variable = 'TOPIC';""")
		self.c.execute("""INSERT OR IGNORE INTO config VALUES('PROMOTION_DELAY', '10');""")
		self.c.execute("""INSERT OR IGNORE INTO config VALUES('PROMOTION_ROLE', 'none');""")
		self.c.execute("""INSERT OR IGNORE INTO config VALUES('PREFIX', '!');""")
		self.c.execute("""INSERT OR IGNORE INTO config VALUES('MAX_EXPIRE_TIME', '21600');""")
		self.c.execute("""INSERT OR IGNORE INTO config VALUES('++_REQ_PLAYERS', '5');""")
		self.c.execute("""INSERT OR IGNORE INTO config VALUES('TEAMS_PICK_SYSTEM', 'JUST_CAPTAINS');""")

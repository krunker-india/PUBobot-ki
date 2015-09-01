#!/usr/bin/python2
# encoding: utf-8

import time, datetime, re, traceback, random
import irc, config, console, stats2, scheduler

def init():
	global oldtopic, lastgame_cache, cfg, oldtime, highlight_time

	oldtime = 0
	highlight_time = 0

	stats2.init()

	init_pickups()

	cfg = config.cfg
	lastgame_cache = stats2.lastgame()
	oldtopic = ''
	
	scheduler.add_task("#backup#", cfg['BACKUP_TIME'] * 60 * 60, scheduler_backup, ())
	
def init_pickups():
	global pickups

	pickups = []
	for i in config.pickups:
		pickup = Pickup(i[0],i[1],i[2],i[3],False)

class Pickup():

	def __init__(self, name, maxplayers, ip, default=False, update=True):
		for i in ( i for i in pickups if i.name == name ):
			return False
		self.players = []
		self.maxplayers = maxplayers
		self.name = name
		self.ip = ip
		self.info = "http://www.warsow.net/wiki/Gametypes"
		self.default = default
		pickups.append(self)
		if update:
			update_topic()

	def start(self):
		global pickups, lastgame_cache, highlight_time
		#remove warnings
		for i in self.players:
			scheduler.cancel_task(i)
		players=tuple(self.players) #just to save the value
		caps=random.sample(players,2)
		noticestr="02{0} 04should03 connect {1} .04 Captains will be: 02{2}.".format(', '.join(players), self.ip, ' and '.join(caps))
		irc.notice('04'+self.name+' pickup has been started!')
		irc.notice(noticestr)
		for i in players:
			irc.private_reply(i,"04{0} pickup has been started, please03 connect {1} .".format(self.name,self.ip))
			for pickup in ( pickup for pickup in pickups if i in pickup.players):
				pickup.players.remove(i)
		stats2.register_pickup(self.name, players, caps)
		lastgame_cache = stats2.lastgame()
		highlight_time = 0
		update_topic()

def processmsg(msgtup): #parse PRIVMSG event
	lower=[i.lower() for i in msgtup]
	nick,ident = lower[0].lstrip(":").split("!")
	ip = ident.split('@')[1]
	msglen = len(lower)


	if lower[3]==":!add":
		add_player(nick.lower(), ip, lower[4:msglen])

	elif re.match("^:\+..", lower[3]):
		lower[3]=lower[3].lstrip(":+")
		add_player(nick.lower(), ip, lower[3:msglen])

	elif lower[3]==":++":
		add_player(nick.lower(), ip, [])

	elif lower[3]==":!remove":
		remove_player(nick.lower(),lower[4:msglen])

	elif re.match("^:-..",lower[3]):
		lower[3]=lower[3].lstrip(":-")
		remove_player(nick.lower(),lower[3:msglen])

	elif lower[3]==":--":
		remove_player(nick.lower(),[])

	elif lower[3]==":!expire":
		expire(nick.lower(),lower[4:msglen])

	elif lower[3]==":!remove_players":
		remove_players(nick, lower[4:msglen])

	elif lower[3]==":!who" or lower[3]==":??":
		who(nick,msgtup[4:msglen])

	elif lower[3] in [":!games", ":!pickups"]:
		replypickups(nick)

	elif lower[3]==":!promote":
		promote_pickup(nick,lower[4:5])

	elif lower[3]==":!highlight":
		highlight(nick)

	elif lower[3] in [":!stfu", ":!nohighlight"]:
		switch_highlight_blacklist(nick)

	elif lower[3]==":!highlight_blacklist":
		show_highlight_blacklist(nick)
		
	elif lower[3]==":!lastgame":
		lastgame(nick,lower[4:msglen])

	elif lower[3]==":!sub":
		sub_request(nick)

	elif lower[3]==":!stats":
		getstats(nick,lower[4:5])

	elif lower[3]==":!top":
		gettop(nick, lower[4:msglen])

	elif lower[3]==":!add_pickups":
		add_games(nick,lower[4:msglen])

	elif lower[3]==":!remove_pickups":
		remove_games(nick, lower[4:msglen])

	elif lower[3]==":!default_pickups":
		default_games(nick, lower[4:msglen])

	elif lower[3]==":!motd":
		set_motd(nick, msgtup[4:msglen])

	elif lower[3]==":!ip" and msglen>5:
		setip(nick, lower[4:msglen])

	elif msgtup[3]==":!ip":
		getip(nick,lower[4:5])

	elif lower[3]==":!noadd":
		noadd(nick, lower[4:msglen])

	elif lower[3]==":!chanban":
		chanban(nick,lower[4:msglen])

	elif lower[3]==":!forgive":
		forgive(nick,lower[4:5])

	elif lower[3]==":!noadds":
		getnoadds(nick, lower[4:5])

	elif lower[3]==":!spamchans":
		irc.private_reply(nick,str(cfg['SPAMCHANS']))

	elif lower[3]==":!spam" and msglen==5:
		add_spam_channel(nick, lower[4])

	elif lower[3]==":!nospam" and msglen==5:
		remove_spam_channel(nick, lower[4])

	elif lower[3]==":!reset":
		reset_players(nick, lower[4:msglen])

	elif lower[3]==":!backup_save":
		backup_save(nick)

	elif lower[3]==":!backup_load":
		backup_load(nick, lower[4:5])
		
	elif lower[3]==":!topiclimit" and msglen==5:
		set_topic_limit(nick, lower[4])

	elif lower[3]==":!silent":
		set_silent(nick, lower[4:msglen])

	elif lower[3]==":!puquit":
		quit(nick, lower[4:msglen])

	elif lower[3]==":!phrase":
		set_phrase(nick, lower[4:msglen])

	elif lower[3]==":!lock":
		lock_nick(ip, nick,lower[4:6])

	elif lower[3]==":!unlock":
		unlock_nick(ip, nick, lower[4:5])

	elif lower[3]==":!autoremove_time" and msglen==5:
		set_autoremove_time(nick, lower[4])

	elif lower[3]==":!refresh_ops":
		refresh_ops(nick)
		
	elif lower[3]==":!help":
		show_help(nick, lower[4:msglen])
	
	elif lower[3]==":!commands":
		irc.private_reply(nick, stats2.show_commands())

# COMMANDS #

def add_player(nick, ip, target_pickups):
	#check delay between last pickup
	if lastgame_cache:
		if time.time() - lastgame_cache[1] < cfg['NEXT_PU_ADD_DELAY'] * 60 and nick in lastgame_cache[4]:
			irc.reply(nick, "Get off me! Your pickup already started!")
	
	#check noadds and phrases
	l = stats2.check_ip(ip, nick)
	if l[0] == True: # if banned or faker
		irc.reply(nick, l[1])
		return

	update_autoremove = False
	changes = False

	#ADD GUY TO TEH GAMES
	for pickup in ( pickup for pickup in pickups if ((target_pickups == [] and pickup.default == True) or pickup.name in target_pickups)):
		update_autoremove=True
		if not nick in pickup.players:
			changes = True
			pickup.players.append(nick)
			if len(pickup.players)==pickup.maxplayers:
				pickup.start()
				return
			elif len(pickup.players)==pickup.maxplayers-1 and pickup.maxplayers>2:
				irc.promote("Only 1 player left for {0} pickup. Hurry up!".format(pickup.name))

	#ADD WARNING MESSAGE
	if update_autoremove:
		if nick in scheduler.tasks:
			scheduler.cancel_task(nick)
		delay = (cfg['AUTOREMOVE_TIME']*60)-(5*60)
		scheduler.add_task(nick, delay, scheduler_warning, (nick,))

	#reply a phrase and update topic
	if changes:
		if l[1] != False: # if have phrase
			irc.reply(nick, l[1])
		update_topic()

def remove_player(nick,args,newnick=False,quit=False,from_scheduler=False):
	changes = []
	allpickups = True

	#remove player from games
	for pickup in ( pickup for pickup in pickups if nick in pickup.players and (args == [] or pickup.name in args)):
		changes.append(pickup.name)
		pickup.players.remove(nick)
		if newnick:
			pickup.players.append(newnick)

	for pickup in ( pickup for pickup in pickups if nick in pickup.players):
		allpickups = False

	#update topic and warn player
	if changes != []:
		update_topic()
		if not quit and not newnick:
			if allpickups:
				irc.private_reply(nick, "You have been removed from all pickups")
			else:
				irc.private_reply(nick, "You have been removed from {0}.".format(", ".join(changes)))

		if not from_scheduler:
			#REMOVE AFK WARNING MESSAGE IF HE IS REMOVED FROM ALL GAMES
			if allpickups and not newnick:
				scheduler.cancel_task(nick)

			#UPDATE SCHEDULER IF PLAYER CHANGED HIS NICK
			if newnick:
				delay_left = scheduler.tasks[nick][0] - time.time()
				task_name = scheduler.tasks[nick][1].__name__
				if task_name == "scheduler_remove":
					scheduler.add_task(newnick, delay_left, scheduler_remove, (newnick, ))
				else:
					scheduler.add_task(newnick, delay_left, scheduler_warning, (newnick, ))
				scheduler.cancel_task(nick)
				
def scheduler_warning(nick): #SEND WARNING MESSAGE
	irc.private_reply(nick,'AFK check...Please use !add command...You have 5 minutes')
	scheduler.add_task(nick, 5*60, scheduler_remove, (nick, ))

def scheduler_remove(nick):
	remove_player(nick, [], False, False, True)

def remove_players(nick, players):
	if re.match("@|\+",irc.get_usermod(nick)):
		print players
		for player in players:
			remove_player(player, [])
	else:
		irc.reply(nick, "You have no right for this!")

def who(nick, args):
	templist,l,c=[],0,-1
	for pickup in ( pickup for pickup in pickups if pickup.players != [] and (pickup.name in args or args == [])):
		templist.append(u'[{0}] 03{1}'.format(pickup.name, '/03'.join(pickup.players)))
	if templist != []:
		for i in range(0,len(templist)):
			l+=len(templist[i].encode('utf-8'))+6
			c+=1
			if l>230 or i==len(templist)-1:
				irc.private_reply(nick,' '.join(templist[i-c:i+1]))
				c,l=0,-1
	else:
		irc.private_reply(nick,'sleepsow...06ZzZz')

def lastgame(nick, args):
	if args != []:
		l = stats2.lastgame(args[0]) # number, ago, gametype, players, caps
	else:
		l = lastgame_cache
	if l:
		n = l[0]
		ago = datetime.timedelta(seconds=int(time.time() - int(l[1])))
		gt = l[2]
		caps = ", ".join(l[3])
		players = ", ".join(l[4])
		irc.private_reply(nick, "Pickup #{0}, {1} ago [{2}]: {3}. Caps: {4}".format(n, ago, gt, players, caps))
	else:
		irc.private_reply(nick, "No pickups found.")
      

def sub_request(nick):
	global oldtime
	ip = cfg['DEFAULTIP']

	if lastgame_cache:
		newtime=time.time()
		if newtime-oldtime>60:
			for i in ( i for i in pickups if i.name == lastgame_cache[2]):
				ip = i.ip
				irc.promote("SUB NEEDED for {0} pickup! Please connect {1} !".format(lastgame_cache[2],ip))
			oldtime=newtime
		else:
			irc.private_reply(nick,"04Only one promote per minute! You have to wait 03{0} secs.".format(int(60-(newtime-oldtime))))
	else:
		irc.private_reply(nick, "No pickups played yet.")

def update_topic():
	global oldtopic
	newtopic=''

	sort=sorted(pickups,key=lambda x: len(x.players), reverse=True)
	for i in ( i for i in sort if i.players or i.default):
		newtopic="{0}{1} 03{2}/{3}04|".format(newtopic,i.name,len(i.players),i.maxplayers)
		if sort.index(i)==cfg['PICKUPS_IN_TOPIC']-1:
			break

	newtopic="04|{0} {1}".format(newtopic,cfg['MOTD'])
	if newtopic != oldtopic:
		irc.set_topic(newtopic)
		oldtopic=newtopic

def replypickups(nick):
	s=''
	for i in pickups:
		if i.default:
			status=' default'
		else:
			status = ''
		s="{0}{1} 03{2}/{3}{4}04|".format(s,i.name,len(i.players),i.maxplayers,status)

	for i in range(0, (len(s)/200)+1):
		irc.private_reply(nick,s[i*200:(i+1)*200])

def promote_pickup(nick,arg):
	global oldtime
	newtime=time.time()
	if newtime-oldtime>60:
		if arg != []:
			for pickup in ( pickup for pickup in pickups if [pickup.name] == arg ):
				irc.promote("Please !add in {0} {1}, {2} players to go!".format(cfg['HOME'],pickup.name,pickup.maxplayers-len(pickup.players)))
		else:
			irc.promote("Please !add in {0}!".format(cfg['HOME']))
		oldtime=newtime
	else:
		irc.private_reply(nick,"04Only one promote per minute! You have to wait 03{0} secs.".format(int(60-(newtime-oldtime))))

def highlight(nick):
	global highlight_time
	newtime = time.time()
	if newtime - highlight_time > 3600:
		blacklist = stats2.highlight_blacklist()
		blacklist.append(cfg['NICK'].lower())
		for pickup in pickups:
			for player in pickup.players:
				if player not in blacklist:
					blacklist.append(player)
					
		highlight_time = newtime
		irc.highlight(blacklist)
	else:
		irc.private_reply(nick, "04Only one highlight per hour or pickup! You have to wait 03{0} minutes.".format(int((3600-(newtime-highlight_time))/60)))

def switch_highlight_blacklist(nick):
	msg = stats2.highlight_blacklist(nick)
	irc.reply(nick, msg)
		
def show_highlight_blacklist(nick):
	l = stats2.highlight_blacklist()
	irc.private_reply(nick, "Nicks in blacklist: {0}".format(' '.join(l)))

def expire(nick,timelist):
	#set expire if time is specified
	if timelist != []:
		if not (nick in scheduler.tasks):
			irc.private_reply(nick, "You must be added first!")
			return

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
				irc.private_reply(nick, "Bad argument @ \"{0}\", format is: !expire 1h 2m 3s".format(i))
				return

		#apply given time
		if timeint>0 and timeint<115200: #restart the scheduler task, no afk check task for this guy
			scheduler.cancel_task(nick)
			scheduler.add_task(nick, timeint, scheduler_remove, (nick, ))
			irc.private_reply(nick, "You will be removed at {0} {1}".format(datetime.datetime.fromtimestamp(time.time()+timeint).strftime("%H:%M:%S"), time.tzname[0]))
		else:
			irc.private_reply(nick, "Invalid time amount")

	#return expire time	if no time specified
	else:
		if not (nick in scheduler.tasks):
			irc.private_reply(nick, "You are not added!")
			return

		if scheduler.tasks[nick][1].__name__ == "scheduler_remove": #+5m if its a warning
			timeint=scheduler.tasks[nick][0]
		else:
			timeint=scheduler.tasks[nick][0]+300

		dtime=datetime.datetime.fromtimestamp(timeint)
		irc.private_reply(nick, "You will be removed in {0}, at {1} {2}".format(str(datetime.timedelta(seconds=int(timeint-time.time()))),dtime.strftime("%H:%M:%S"), time.tzname[0]))

def getstats(nick,target):
	if target == []:
		s = stats2.stats()
	else:
		s = stats2.stats(target[0])
	irc.private_reply(nick, s)

def gettop(nick, arg):
	if arg == []:
		top10=stats2.top()
		irc.private_reply(nick, "Top 10 of all time: "+top10)

	elif arg[0] == "weekly":
		timegap = int(time.time()) - 604800
		top10=stats2.top(timegap)
		irc.private_reply(nick, "Top 10 of the week: "+top10)

	elif arg[0] == "monthly":
		timegap = int(time.time()) - 2629744
		top10=stats2.top(timegap)
		irc.private_reply(nick, "Top 10 of the month: "+top10)

	elif arg[0] == "yearly":
		timegap = int(time.time()) - 31556926
		top10=stats2.top(timegap)
		irc.private_reply(nick, "Top 10 of the year: "+top10)

	else:
		irc.private_reply(nick, "Bad argument.")

def getnoadds(nick, args):
  if args == []:
    l = stats2.noadds()
  else:
    l = stats2.noadds(args[0])
  for i in l:
    irc.private_reply(nick,i)

def add_games(nick,targs):
	if re.match("@|\+",irc.get_usermod(nick)):
		for i in range(0,len(targs)):
			console.display(targs[i]+"!")
			name,players = targs[i].split(":")
			if int(players) > 1:
				try:
					e=Pickup(name,int(players),cfg['DEFAULTIP'],0)
				except:
					irc.private_reply(nick,"Bad arguments")
			else:
				irc.private_reply(nick,"Players number must be more than 1, dickhead")
	else:
		irc.reply(nick, "You have no right for this!")

def remove_games(nick, args):
	if re.match("@|\+",irc.get_usermod(nick)):
		toremove = [ pickup for pickup in pickups if pickup.name in args ]
		for i in toremove:
			pickups.remove(i)
		update_topic()
	else:
		irc.reply(nick, "You have no right for this!")

def default_games(nick, args):
	if re.match("@|\+",irc.get_usermod(nick)):
		for pickup in pickups:
			if pickup.name in args:
				pickup.default = 1
			else:
				pickup.default = 0
		update_topic()
	else:
		irc.reply(nick, "You have no right for this!")

def set_autoremove_time(nick, arg):
	if re.match("@|\+",irc.get_usermod(nick)):
		try:
			minutes = int(arg)
		except:
			irc.reply(nick, "Argument must be number of minutes.")
			return

		if minutes>5:
			cfg['AUTOREMOVE_TIME'] = minutes
			irc.private_reply(nick, 'AUTOREMOVE_TIME is set to {0} minutes. Needs re!add to affect'.format(minutes))
		else:
			irc.private_reply(nick, 'AUTOREMOVE_TIME must be more than 5 minutes.')
	else:
		irc.reply(nick, "You have no right for this!")

def setip(nick, args):
	if re.match("@|\+",irc.get_usermod(nick)):
		try:
			pickupnames,gameip=' '.join(args).split(' : ',1)
		except:
			irc.private_reply(nick, "Bad arguments")
			return
		n=0
		for pickup in ( pickup for pickup in pickups if ( 'default' in pickupnames and pickup.ip == cfg['DEFAULTIP']) or pickup.name in pickupnames):
			if gameip=='default':
				gameip=cfg['DEFAULTIP']
			pickup.ip=gameip
			n=1

		if "default" in pickupnames:
			cfg['DEFAULTIP']=gameip
		if n:
			irc.private_reply(nick, "Changed ip to {0} for {1}".format(gameip,str(pickupnames)))
		else:
			irc.private_reply(nick, "No such pickup")
	else:
		irc.reply(nick, "You have no right for this!")

def getip(nick,args): #GET IP FOR GAME
	# find desired parameter
	if args != []:
		pickup_or_ip = args[0]
	else:
		l = lastgame_cache
		if l:
			pickup_or_ip = l[2]
		else:
			irc.reply(nick, "No pickups played yet.")
			return

	# find desired info
	if pickup_or_ip  == 'default':
		irc.private_reply(nick,'Default ip is {0} and it is currently set for {1} pickups'.format(cfg['DEFAULTIP'], str([x.name for x in pickups if x.ip == cfg['DEFAULTIP']])))
		return

	n=0
	for pickup in pickups:
		if pickup.name == pickup_or_ip:
			irc.private_reply(nick,'Ip for {0} is {1}'.format(pickup.name, pickup.ip))
			n=1

	if not n:
		irc.private_reply(nick,'No such game or ip')

def set_motd(nick, args):
	if re.match("@|\+",irc.get_usermod(nick)):
		cfg['MOTD']=' '.join(args)
		update_topic()
	else:
		irc.reply(nick, "You have no right for this!")

def set_topic_limit(nick, arg):
	if re.match("@|\+",irc.get_usermod(nick)):
		cfg['PICKUPS_IN_TOPIC']=int(arg)
		update_topic()
	else:
		irc.reply(nick, "You have no right for this!")

def set_phrase(nick, args):
	if re.match("@|\+",irc.get_usermod(nick)):
		if len(args) >= 2:
			targetnick = args[0]
			phrase = ' '.join(args[1:len(args)])
			stats2.set_phrase(targetnick, phrase)
			irc.reply(nick,"Phrase has been set.")
		else:
			irc.reply(nick, "This command needs more arguments.")
	else:
		irc.reply(nick, "You have no right for this!")

def lock_nick(ip, nick, args):
	if len(args) == 0:
		s = stats2.lock_nick(nick.lower(), ip, False)
	elif re.match("@|\+", irc.get_usermod(nick)):
		if len(args) == 2:
			ip = args[1]
		else:
			ip = irc.get_ip(nick)
		if ip != False:
			s = stats2.lock_nick(args[0].lower(), ip, True)
		else:
			s = "Couldnt find target ip. You can specify ip yourself, ex: '!lock nick ip'."
	else:
		s = "You must have +v to specify nick. Use '!lock' to lock your current nick."
	irc.private_reply(nick, s)

def unlock_nick(ip, nick, args):
	if len(args) == 0:
		s = stats2.unlock_nick(nick.lower(), ip, False)
	elif re.match("@|\+",irc.get_usermod(nick)):
		s = stats2.unlock_nick(args[0], False, True)
	else:
		s = "You must have +v to specify nick. Use '!unlock' to unlock your current nick."
	irc.private_reply(nick, s)

def noadd(nick, args):
	if re.match("@|\+",irc.get_usermod(nick)):
		reason = ''
		duratation = cfg['BANTIME']
		ip = False

		if args != []:
			targetnick = args.pop(0)
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
						irc.reply(nick,"Bad duratation argument.")
						return
					
				elif arg in ["-r", "--reason"]:
					l=[]
					while len(args):
						if args[0][0:1] != '-':
							l.append(args.pop(0))
						else:
							break
					reason = " ".join(l)
						
				elif arg in ["-m", "--ip-mask"]:
					try:
						ip = args.pop(0)
						re.compile("^{0}$".format(re.escape(ip).replace("\*",".*")))	
					except:
						irc.reply(nick,"Bad ip mask argument.")
						return
				else:
					irc.reply(nick, "Bad argument @ '{0}'. Usage !noadd $nick [$time] [--time|-t $time] [--reason|-r $reason] [--ip-mask|-m $ip_mask]".format(arg))
					return
					
		else:
			irc.reply(nick, "You must specify target nick!")
			return

		if abs(duratation) > 10000:
			irc.reply(nick,"Max ban duratation is 10000 hours.")
			return

		if not ip:
			ip = irc.get_ip(targetnick)
			
		remove_player(targetnick,[])
		s = stats2.noadd(ip, targetnick, duratation, nick, reason)
		irc.notice(s)
	else:
		irc.reply(nick, "You have no right for this!")

def forgive(nick,args):
	if re.match("@|\+",irc.get_usermod(nick)):
		if args != []:
			s = stats2.forgive(args[0],nick)
			irc.private_reply(nick, s)
		else:
			irc.reply(nick, "You must specify target nick!")
	else:
		irc.reply(nick, "You have no right for this!")

def chanban(nick,args):
	if re.match("@|\+",irc.get_usermod(nick)):
		reason = ''
		duratation = cfg['BANTIME']

		if args != []:
			targetnick = args[0]
			if len(args) > 1:
				duratation = args[1]
				if len(args) > 2:
					reason = args[2]
		else:
			irc.reply(nick, "You must specify target nick!")

		try:
			duratation = int(duratation)
		except:
			irc.reply(nick,"Bad duratation argument.")
			return

		if 0 < duratation > 12:
			irc.reply(nick,"Max ban duratation is 12 hours.")
			return

		ip = irc.get_ip(targetnick)
		if (ip==False):
			irc.reply(nick,"No such nick on server.")
		else:
			remove_player(targetnick,[])
			irc.chanban(ip, str(duratation), reason)
	else:
		irc.reply(nick, "You have no right for this!")

def add_spam_channel(nick, arg):
	if re.match("@|\+",irc.get_usermod(nick)):
		irc.add_spam_channel(nick, arg)
	else:
		irc.reply(nick, "You have no right for this!")

def remove_spam_channel(nick, arg):
	if re.match("@|\+",irc.get_usermod(nick)):
		irc.remove_spam_channel(arg, nick)
	else:
		irc.reply(nick, "You have no right for this!")

def reset_players(nick=False, args=[]):
	if nick == False or re.match("@|\+",irc.get_usermod(nick)):
		removed = []
		for pickup in pickups:
			if pickup.name in args or args == []:
				for player in pickup.players:
					if not player in removed:
						removed.append(player)
				pickup.players = []
		if removed != []:
			for player in removed:
				allpickups = True
				for pickup in pickups:
					if player in pickup.players:
						allpickups = False
				if allpickups:
					scheduler.cancel_task(player)
			if args == []:
				irc.notice("{0} was removed from all pickups!".format(', '.join(removed)))
			elif len(args) == 1:
				irc.notice("{0} was removed from {1} pickup!".format(', '.join(removed), args[0]))
			else:
				irc.notice("{0} was removed from {1} pickups!".format(','.join(removed), ', '.join(args)))
	else:
		irc.reply(nick, "You have no right for this!")

def backup_save(nick):
	if re.match("@|\+",irc.get_usermod(nick)):
		dirname = nick + datetime.datetime.now().strftime("%Y-%m-%d-%H:%M")
		config.backup(dirname)
		irc.reply(nick, "Backup saved to backups/{0}. Use !backup_load {0} to restore.".format(dirname))
	else:
		irc.reply(nick, "You have no right for this!")

def backup_load(nick, args):
	if re.match("@|\+", irc.get_usermod(nick)):
		if len(args) > 0:
			reply = config.backup_load(args[0])
		else:
			reply = config.backup_load()
		irc.reply(nick, reply)
	else:
		irc.reply(nick, "You have no right for this!")

def scheduler_backup():
	dirname = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M")
	config.backup(dirname)
	scheduler.add_task("#backup#", cfg['BACKUP_TIME'] * 60 * 60, scheduler_backup, ())

def set_silent(nick, args):
	if re.match("@|\+",irc.get_usermod(nick)):
		if (cfg['NICK'] in args) or (args == []):
			silent = not silent
	else:
		irc.reply(nick, "You have no right for this!")

def refresh_ops(nick):
	irc.refresh_ops()
	
def show_help(nick, args):
	if len(args) == 0:
		irc.private_reply(nick, cfg['HELPINFO'])
	else:
		reply = stats2.show_help(args[0].lstrip("!"))
		irc.private_reply(nick, reply)
	
def quit(nick, args):
	if re.match("@|\+",irc.get_usermod(nick)):
		console.terminate()
	else:
		irc.reply(nick, "You have no right for this!")
		
def terminate():
	stats2.close()

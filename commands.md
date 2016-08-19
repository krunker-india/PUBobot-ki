## Avaible commands:
### ACTONS:
'!add <u>pickup</u>[ <u>pickup</u> ..]]' or '+<u>pickup</u>[ <u>pickup</u> ..]]' - adds you to specified pickups.   
'!add' or '++' - adds you to all active pickups.    
'!remove <u>pickup</u>[ <u>pickup</u> ...]' or '-[<u>pickup</u>[ <u>pickup</u> ..]]' - removes you from specified pickups.  
'!remove' or '--' - removes you from all pickups.   
'!expire <u>time</u>' - Sets new time delay after you will be removed from all pickups, example: '!expire 1h 2m 3s'.     
'!sub' - request sub for last game.

### INFO:
'!who [<u>pickup</u>[ <u>pickup</u> ...]]' - list of users added to a pickups.    
'!pickups' - list of all pickups on the channel.    
'!expire' - shows you how much time left before you will be removed from all pickups.   
'!noadds' - show list of users who are disallowed to play pickups.  
'!lastgame [ <u>@nick</u> or <u>pickup</u> ]' - show last pickup, or last pickup by specified argument.     
'!top [weekly or monthly or yearly]' - shows you most active players.   
'!stats [<u>nick</u> or <u>pickup</u>]' - shows you overall stats or stats for specified argument.    
'!ip [<u>pickup</u> or default]' - shows you ip of last pickup or specified pickup.  

### ADMINISTRATION:
'!noadd <u>@nick</u> [<u>hours</u>] [-r <u>reason</u>]' - disallow user to play pickups.   
'!forgive <u>@nick</u>' - allow user from noadds list to play pickups.   
'!phrase <u>@nick</u> <u>text</u>' - set specified reply for specified user after !add command.   
'!remove_player <u>@nick</u>' - remove specified players from all pickups.   
'!reset' - removes all players from all pickups.    
'!add_pickups <u>name</u>:<u>players</u>[ <u>name</u>:<u>players</u> ...]' - create new pickups.    
'!remove_pickups <u>pickup</u>[ <u>pickup</u> ...]' - delete specified pickups.   
'!set_ip <u>pickup</u>[ <u>pickup</u> ...] : ip' - set server to be played for game. Use 'default' value for pickup to set server for games with default server value.  
'!backup_save' - save backup.   
'!backup_load <u>name</u>' - load specified backup.  
'!set adminrole <u>role</u>' - set channel role for pickup admins.   
'!set pickup_password <u>password</u>' - specify password of your pickup servers.    
'!set ip_format <u>format</u>' - set the format ip and password will be represented in. Default value: 'please connect to steam://connect/%ip%/%password%'.  
'!set bantime <u>hours</u> - set default !noadd time.
## Avaible commands:
### ACTONS:
'!add <i>pickup</i>[ <i>pickup</i> ..]]' or '+<u>pickup</u>[ <i>pickup</i> ..]]' - adds you to specified pickups.   
'!add' or '++' - adds you to all active pickups.    
'!remove <i>pickup</i>[ <i>pickup</i> ...]' or '-[<i>pickup</i>[ <i>pickup</i> ..]]' - removes you from specified pickups.  
'!remove' or '--' - removes you from all pickups.   
'!expire <i>time</i>' - Sets new time delay after you will be removed from all pickups, example: '!expire 1h 2m 3s'.     
'!sub' - request sub for last game.

### INFO:
'!who [<i>pickup</i>[ <i>pickup</i> ...]]' - list of users added to a pickups.    
'!pickups' - list of all pickups on the channel.    
'!expire' - shows you how much time left before you will be removed from all pickups.   
'!noadds' - show list of users who are disallowed to play pickups.  
'!lastgame [ <i>@nick</i> or <i>pickup</i> ]' - show last pickup, or last pickup by specified argument.     
'!top [weekly or monthly or yearly]' - shows you most active players.   
'!stats [<i>nick</i> or <i>pickup</i>]' - shows you overall stats or stats for specified argument.    
'!ip [<i>pickup</i> or default]' - shows you ip of last pickup or specified pickup.  

### PICKUP MANAGEMENT:
'!add_pickups <i>name</i>:<i>players</i>[ <i>name</i>:<i>players</i> ...]' - create new pickups.    
'!remove_pickups <i>pickup</i>[ <i>pickup</i> ...]' - delete specified pickups.   
'!set_ip <i>pickup</i>[ <i>pickup</i> ...] : <i>ip</i>' - set server to be played for game. Use 'default' value for <i>pickup</i> to set server for pickups with default server value.   
'!set_promotion_role <i>pickup</i>[ <i>pickup</i> ...] : <i>role_name</i> - set <i>role</i> to be highlighted on '!promote' command for specified pickups, set 'none' as <i>role</i> to disable. Use 'default' value for <i>pickup</i> to change the default setting.   
'!set_whitelist <i>pickup</i>[ <i>pickup</i> ...] : <i>role_name</i> - allow only specified <i>role</i> to play specified pickups, set 'none' as <i>role</i> to disable.   
'!set_blacklist <i>pickup</i>[ <i>pickup</i> ...] : <i>role_name</i> - disallow specified <i>role</i> to play specified pickups, set 'none' as <i>role</i> to disable.   
'!set promotion_delay <i>minutes<i>' - set how often '!promote' command can be used.   
'!set pickup_password <i>password</i>' - specify password of your pickup servers.    
'!set ip_format <i>format</i>' - set the format ip and password will be represented in. Default value: 'please connect to steam://connect/%ip%/%password%'.   
'!backup_save' - save backup.   
'!backup_load <i>name</i>' - load specified backup.  

### ADMINISTRATION:
'!noadd <i>@nick</i> [<i>hours</i>] [-r <i>reason</i>]' - disallow user to play pickups.   
'!forgive <i>@nick</i>' - allow user from noadds list to play pickups.   
'!phrase <i>@nick</i> <i>text</i>' - set specified reply for specified user after !add command.   
'!remove_player <i>@nick</i>' - remove specified players from all pickups.   
'!reset' - removes all players from all pickups.    
'!set adminrole <i>role_name</i>' - set channel role for pickup admins.   
'!set bantime <i>hours</i> - set default !noadd time.
## 
<b>Availible only for users with permission to manage channels:</b>     
'!enable_pickups' - setup pickups on the channel.   
'!disable_pickups' - remove pickups from the channel. <b>Warning, this action is irreversible!</b>

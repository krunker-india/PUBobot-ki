import sqlite3, operator, re
from os.path import isfile
dbexists = isfile("database.sqlite3")
conn = sqlite3.connect("database.sqlite3")
conn.row_factory = sqlite3.Row
c = conn.cursor()
if dbexists:
    c.execute("SELECT user_id, wins, loses FROM channel_players")
    l = c.fetchall()
    if len(l):
        for user_id, wins, loses in l:
            c.execute("UPDATE channel_players SET wins=?, loses=? WHERE user_id = ?", (loses, wins, user_id))
        conn.commit()
        print("success")

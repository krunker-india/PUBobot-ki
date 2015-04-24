import time

import bot, console

def init():
	global tasks, next_task
	
	tasks = dict()
	next_task = False

def run(frametime):
	if next_task:
		if frametime > tasks[next_task][0]:
			current_task = tasks.pop(next_task)
			exec current_task[1]
			define_next_task()

def add_task(name, delay, func):
	if name not in tasks:
		tasks[name] = [time.time()+delay, func] #time to run task, func
		define_next_task()
	else:
		console.display("SCHEDULER> Task with this name already exist!")

def cancel_task(name):
	if name in tasks:
		tasks.pop(name)
		if next_task == name:
			define_next_task()
	else:
		console.display("SCHEDULER> No such task")

def define_next_task():
	global next_task
	
	if len(tasks.keys()) > 0:
		sorted_tasks = sorted([(value,key) for (key,value) in tasks.items()])
		if next_task != sorted_tasks[0][1]:
			next_task = sorted_tasks[0][1]
	else:
		next_task = False

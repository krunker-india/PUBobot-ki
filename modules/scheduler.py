import time

from modules import bot, console

class Scheduler():

	def __init__(self):
		self.tasks = dict()
		self.next_task = False

	def run(self, frametime):
		if self.next_task:
			if frametime > self.tasks[self.next_task][0]:
				current_task = self.tasks.pop(self.next_task)
				try:
					current_task[1](*current_task[2])
				except Exception as e:
					console.display("SCHEDULER> Task function failed @ {0} {1}, Exception: {2}".format(current_task[1], current_task[2], e))
				self.define_next_task()

	def add_task(self, name, delay, func, args):
		if name not in self.tasks:
			self.tasks[name] = [time.time()+delay, func, args] #time to run task, func
			self.define_next_task()
		else:
			console.display("SCHEDULER> Task with this name already exist!")

	def cancel_task(self, name):
		if name in self.tasks:
			self.tasks.pop(name)
			if self.next_task == name:
				self.define_next_task()
		else:
			console.display("SCHEDULER> No such task")

	def define_next_task(self):
		if len(list(self.tasks.keys())) > 0:
			sorted_tasks = sorted([(value,key) for (key,value) in list(self.tasks.items())])
			if self.next_task != sorted_tasks[0][1]:
				self.next_task = sorted_tasks[0][1]
		else:
			self.next_task = False

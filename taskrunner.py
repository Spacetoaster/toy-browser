import threading

class Task:
    def __init__(self, task_code, *args):
        self.task_code = task_code
        self.args = args
        self.__name__ = "task"
    
    def run(self):
        self.task_code(*self.args)
        self.task_code = None
        self.args = None

class TaskRunner:
    def __init__(self):
        self.tasks = []
        self.condition = threading.Condition()
        self.main_thread = threading.Thread(target=self.run)
    
    def start(self):
        self.main_thread.start()

    def schedule_task(self, task):
        self.condition.acquire(blocking=True)
        self.tasks.append(task)
        self.condition.notify_all()
        self.condition.release()
    
    def run(self):
        while True:
            self.condition.acquire(blocking=True)
            task = None
            if len(self.tasks) > 0:
                task = self.tasks.pop(0)
            self.condition.release()
            if task:
                # print("running task")
                task.run()
            
            self.condition.acquire(blocking=True)
            if len(self.tasks) == 0:
                self.condition.wait()
            self.condition.release()
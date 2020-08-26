class Token:
    def __init__(self, handler, task_id):
        self.task_id = task_id
        self.handler = handler
        self.data = None

    def __call__(self):
        if self.data is None:
            return self.handler.recv(self.task_id)
        else:
            return self.data

class GroupToken:
    def __init__(self, group_handler, task_id, connect_number):
        self.task_id = task_id
        self.group_handler = group_handler
        self.connect_number = connect_number
        self.data = None

    def __call__(self):
        if self.data is None:
            return self.group_handler.recv(self.task_id, self.connect_number)
        else:
            return self.data

class MultipleGroupToken:
    def __init__(self, group_handler, task_id, connect_numbers, tasks, l):
        self.task_id = task_id
        self.tasks = tasks
        self.l = l
        self.group_handler = group_handler
        self.connect_numbers = connect_numbers
        self.data = {}
        self.sorted_data = None

    def __call__(self):
        if self.sorted_data is None:
            
            for connect_number in self.connect_numbers:
                self.group_handler.recv(self.task_id, connect_number)
            
            self.sorted_data = self.group_handler.sort_results(self.tasks, self.data, self.l)
        
        return self.sorted_data
import os, sys

from multiprocessing import Process, Pipe, Array
import multiprocessing

from setproctitle import setproctitle, getproctitle
import inspect

import time
import ctypes
import numpy as np
import copy
import re
import psutil

from .plasma_handler import plasma_info
from .tokens import Token, GroupToken, MultipleGroupToken

def mrange(M):
    a = np.zeros(M)
    a[:M//2] = np.arange(M//2) * 2 + 1
    if M % 2 == 0:
        a[M//2:] = np.arange(M//2) * 2
    else:
        a[M//2:] = np.arange(M//2 + 1) * 2
    return np.asarray(a, dtype='int64')


# This function will execute the task on the object self
def execute(self, task, plasma_client=None):
    try:
        atr = self
        # set args and kwargs
        if "args" in task:
            args = task["args"]
        else:
            args = []

        if "kwargs" in task:
            kwargs = task["kwargs"]
        else:
            kwargs = dict()
        
        if plasma_client is not None:
            args = list(args)
            for i, arg in enumerate(args):
                if type(arg) == plasma_info.plasma.ObjectID:
                    args[i] = plasma_client.get(arg)
            
            for key, value in kwargs.items():
                if type(value) == plasma_info.plasma.ObjectID:
                    kwargs[key] = plasma_client.get(value)


        if task['mode'] == 'eval':
            res = eval(task['code'])
            return res

        if task['mode'] == 'copy':
            self_copy = copy.deepcopy(self)
            if "code" in task:
                exec(task['code'])
            return self_copy

        elif task['mode'] == 'exec':
            exec(task['code'])
            return None

        else:
            # Enables to write something like foo.bar
            p = -1
            i = -1
            for x in re.finditer('\.', task['name']):
                i = x.start()
                name = task['name'][p + 1: x.start()]
                atr = getattr(atr, name)
                p = i
            name = task['name'][i + 1:]

            if task['mode'] == 'run':
                
                if task['name'] == "self" or task['name'] == "":
                    f = self
                else:
                    f = getattr(atr, name)

                res = f(*args, **kwargs)
                return res

            elif task['mode'] == 'get_attr':
                if task['name'] == "self" or task['name'] == "":
                    return self
                else:
                    res = getattr(atr, name)
                    return res

            elif task['mode'] == 'set_attr':
                setattr(atr, name, task['value'])
                return None

            else:
                raise Exception(f"No mode '{task['mode']}'")
    except BaseException as e:
        return e

def interpreter(conn, self, affinity=None, plasma_client_file_name=None, param=None):

    # change the cpu affinity of the process
    import psutil
    if affinity is not None:
        p = psutil.Process()
        p.cpu_affinity(affinity)
    
    # If param is not None then self is a class that needs to be initialized
    if param is not None:
        self = self(*param[0], **param[1])
    
    # Open a connection to plasma if initialized
    if plasma_client_file_name is not None:
        plasma_client = plasma_info.plasma.connect(plasma_client_file_name)
    else:
        plasma_client = None

     # Change procces name
    process_name = f"apalis: {self.__class__.__name__}; {getproctitle()}"
    setproctitle(process_name)
    
    while True:
        task = conn.recv()
        if type(task) == list:
            res = []
            for task_i in task:
                res += [execute(self, task_i, plasma_client=plasma_client)]
            
            if "task_id" in task[0]:
                conn.send((task[0]["task_id"], res))
            else:
                conn.send(res)
        
        elif type(task) == dict:
            res = execute(self, task, plasma_client=plasma_client)
            if "task_id" in task:
                conn.send((task["task_id"], res))
            else:
                conn.send(res)
        
        # If task is a str then end the function
        elif type(task) == str:
            break

    conn.close()

class DummyHandler:
    def __init__(self, handler, name=""):
        self._handler = handler
        self._name = name
    
    def __getattr__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        
        if self._name != "":
            long_name = f"{self._name}.{name}"
        else:
            long_name = name
        
        dh = DummyHandler(self._handler, long_name)
        self.__dict__[name] = dh
        return dh
    
    def get(self):
        task = {'name': self._name, "mode": "get_attr"}
        return self._handler.single_run(task)
    
    def __setattr__(self, name, value):
        """Setting a private attribute in the child process will not work.
        """
        if name[:1] == "_":
            self.__dict__[name] = value
        else:
            if self._name != "":
                name = f"{self._name}.{name}"
            
            task = {'name': name, 'value': value, "mode": "set_attr"}
            return self._handler.single_run(task)
    
    def __call__(self, *args, **kwargs):
        """Calls the desired function.

        Returns
        -------
        Token:
            A token is returned. If it is called the main process will wait until the child process has returned the outputs of the function.
        """
        task = {'name': self._name, 'args': args, "kwargs": kwargs, "mode": "run"}
        return self._handler.single_run(task)
    
    def remote(self, *args, **kwargs):
        """ Calls __call__() for compatibility with ray."""
        return self(*args, **kwargs)

class Handler(DummyHandler):
    """Saves the object into a forked process and provides an interface to interact with it.

    Parameters
    ----------
        obj : 
            Object to be saved in a forked process.
        affinity : int, optional
            cpu affinity of the process. This is usefull when the processed functions take between 1ms and 10ms to complete, by default None
    
    Examples
    --------
    >>> class A:
    >>>     def f(self, x):
    >>>         return x
    >>>
    >>> h = apalis.Handler(A())
    >>> token = h.f(5)
    >>> token()
    5
    """
    def __init__(self, obj, affinity=None, param=None):

        kwargs_options = {}
        if plasma_info.init:
            kwargs_options["plasma_client_file_name"] = plasma_info.plasma_client_file_name
        
        if affinity is not None:
            kwargs_options["affinity"] = [affinity]
        
        # If param is None then the obj needs to be called after the fork
        if param is not None:
            kwargs_options["param"] = param

        # Initialize the Pipe between the main process and the child process
        parent_conn, child_conn = Pipe()
        self._conn = parent_conn

        self._p = Process(target=interpreter, args=(child_conn, obj), kwargs=kwargs_options, daemon=True)
        self._p.start()
        
        # Task Cache
        self._task_cache = dict()
        self._running_task_id = 0

        # Initialize the DummyHandler class
        super().__init__(self)
    
    def single_run(self, task):
        """Executes a single task.

        Parameters
        ----------
        task : dict
            Dictionary contatining the required fields to execute a function, get an attribute, etc.

        Returns
        -------
        Token
            A token is returned. If it is called the main process will wait until the child process has returned the outputs of the function.
        
        Examples
        ---------
        >>> h.single_run([{'name': '<function_name>', 'args': args, 'kwargs': kwargs, 'mode': 'run'}])
        """
        task_id = self._running_task_id
        self._running_task_id += 1
        task["task_id"] = task_id

        self._conn.send(task)
        token = Token(self, task_id)
        self._task_cache[task_id] = token
        return token
    
    def recv(self, task_id):
        """Recieves the result of a task.

        Parameters
        ----------
        task_id : int
            Task indentifier.

        Returns
        -------
        output
            Output of the operation.

        Raises
        ------
            Exceptions that where caught in the child process.
        """
        while task_id in self._task_cache:
            recv_task_id, out = self._conn.recv()

            if isinstance(out, BaseException):
                    raise out
            if type(out) == list:
                for o in out:
                    if isinstance(o, BaseException):
                        raise o
            
            self._task_cache[recv_task_id].data = out
            del self._task_cache[recv_task_id]
        
        return out
    
    def clear(self):
        if self._task_cache:
            tokens = list(self._task_cache.values())
            get(tokens)

    
    def multiple_run(self, tasks):
        """Executes several tasks.

        Parameters
        ----------
        task : dict
            Dictionary contatining the required fields to execute a function, get an attribute, etc.
        

        Returns
        -------
        Token
            A token is returned. If it is called the main process will wait until the child process has returned the outputs of the function.
        
        Examples
        --------
        >>> tasks = []
        >>> tasks.append({'name': '<function_name>', 'args': args, 'kwargs': kwargs, 'mode': 'run'})
        >>> tasks.append({'name': '<attribute_name>', 'mode': 'get_attr'})
        >>> h.multiple_run(tasks)
        """
        task_id = self._running_task_id
        self._running_task_id += 1
        for task in tasks:
            task["task_id"] = task_id

        self._conn.send(tasks)
        token = Token(self, task_id)
        self._task_cache[task_id] = token
        return token
    
    def run_send(self, tasks):
        self._conn.send(tasks)
    
    def run_recv(self):
        self.clear()
        out = self._conn.recv()
        if isinstance(out, BaseException):
                raise out
        elif type(out) == list:
            for o in out:
                if isinstance(o, BaseException):
                    raise o
        return out

    def run(self, tasks):
        """Runs the tasks and directly returns the ouputs.
        It is faster than multiple_run since it does not need to deal with Tokens.

        Parameters
        ----------
        tasks : list(dict)
            List of tasks.

        Returns
        -------
        list
            List with the output of the tasks.
        
        Examples
        --------
        >>> tasks = [{name': '<function_name>', 'args': args, 'kwargs': kwargs, 'mode': 'run'}, 
        >>> taks += {name': '<attr_name>', 'value': 5, 'mode': 'setattr'}]
        >>> h.run(tasks)
        [result, attr]
        """
        self.run_send(tasks)
        return self.run_recv()

    def __del__(self):
        self._conn.send('kill')
        self._p.join()
        self._p.terminate()
    
    def __getstate__(self):
        return self._conn
    
    def __setstate__(self, conn):
        self._conn = conn

        # Task Cache
        self._task_cache = dict()
        self._running_task_id = 0

        # Initialize the DummyHandler class
        super().__init__(self)


class RemoteClass:
    """Objects of classes decorated with RemoteClass will be initialized in a seperate process.
    """
    def __init__(self, clas):
        self._cls = clas
    
    def __call__(self, *args, **kwargs):
        return Handler(self._cls, param=[args, kwargs])


def group_interpreter(conn, objs, mapping, affinity=None, plasma_client_file_name=None, params=None):
    import psutil

    if affinity is not None:
        p = psutil.Process()
        p.cpu_affinity(affinity)
    
    # Initialize obects if params are given
    if params is not None:
        for i, param in enumerate(params):
            if param is not None:
                objs[i] = objs[i](*param[0], **param[1])

    if plasma_client_file_name is not None:
        plasma_client = plasma_info.plasma.connect(plasma_client_file_name)
    else:
        plasma_client = None

    mapping = mapping.tolist()
    mapping_dict = dict()
    for i, m in enumerate(mapping):
        mapping_dict[m] = i
    
    # Set procces name
    process_name = "apalis: "
    for i, obj in enumerate(objs[:-1]):
        process_name += (f"{obj.__class__.__name__} {mapping[i]}, ")
    
    process_name += (f"{objs[-1].__class__.__name__} {mapping[-1]}")
    process_name += "; " + getproctitle()
    setproctitle(process_name)

    while True:
        tasks = conn.recv()
        if type(tasks) == str:
            break
        else:
            out = []

            for task in tasks:
                i = mapping_dict[task['i']]
                res = execute(objs[i], task, plasma_client=plasma_client)
                out.append(res)

            if "task_id" in tasks[0]:
                conn.send((tasks[0]["task_id"], out))
            else:
                conn.send(out)

class GroupHandler:
    """The GroupHandler class saves a list of objects into a forked processes and provides an interface to interact with them.
    Depending on how many CPU cores your machine has it will save several objects into one child process. This reduces overhead.

    Parameters
    ----------
        objs : list
            List of objects to be send to forked processes.
        threads : int, optional
            Number of child processes to be created, by default CPU cre number
        affinity : bool, optional
            If affinity is *True* it will set the affinity of the child processes to one core. This can lead to a faster execution time in some instances, by default False
        params : list, by default None
            If this argument is given the object will be called after the child process has been forked. A list of list with the structre
            [[args, kwargs], ...] should be given.
    
    Examples
    --------
    >>> gh = apalis.GroupHandler([A() for _ in range(2)])
    >>> tasks = [h.f(5) for h in gh]
    >>> token = gh.multiple_run(tasks)
    >>> token()
    [5, 5]
    """
    def __init__(self, objs, threads=None, affinity=False, params=None):

        self.length = len(objs)

        cores = multiprocessing.cpu_count()

        if threads is None:
            threads = cores

        if threads > self.length:
            threads = self.length

        self.threads = threads

        self.objs = np.array(objs, dtype=object)
        if params is not None:
            params = np.array(params, dtype=object)
        
        self.mapping = [0] * self.length

        l1 = int(np.ceil(self.length / threads))
        l2 = l1 - 1
        g2 = l1 * threads - self.length
        g1 = threads - g2

        cc = 0
        processes = []
        conns = []
        # There are to different kind of processes, one kind has l1 many objects the other one has l2 many
        # There are g1 many processes with l1 many objects.
        self.order = mrange(self.length)

        kwargs = dict()
        if plasma_info.init:
            kwargs["plasma_client_file_name"] = plasma_info.plasma_client_file_name
        
        affinity_core = 0
        for _ in range(g1):
            ob = self.objs[self.order[cc: cc + l1]]
            parent_conn, child_conn = Pipe()

            if affinity:
                kwargs["affinity"] = [affinity_core]
                affinity_core = (affinity_core + 1) % cores
            
            if params is not None:
                kwargs["params"] = params[self.order[cc: cc + l1]]
            
            p = Process(target=group_interpreter, args=(child_conn, ob, self.order[cc: cc + l1]), kwargs=kwargs, daemon=True)
            p.start()
            conns.append(parent_conn)

            connection_number = len(conns) - 1
            for i in range(cc, cc + l1):
                self.mapping[self.order[i]] = connection_number

            cc = cc + l1
        #affinity = False
        for _ in range(g2):
            ob = self.objs[self.order[cc: cc + l2]]
            parent_conn, child_conn = Pipe()

            if affinity:
                kwargs["affinity"] = [affinity_core]
                affinity_core = (affinity_core + 1) % cores

            p = Process(target=group_interpreter, args=(child_conn, ob, self.order[cc: cc + l1]), kwargs=kwargs, daemon=True)
            p.start()

            processes.append(p)
            conns.append(parent_conn)

            for i in range(cc, cc + l2):
                self.mapping[self.order[i]] = len(conns) - 1

            cc = cc + l2

        self.conns = conns
        self.processes = processes

        # Initiatlize empty task cache
        self.running_task_id = 0
        self.task_cache = [dict() for _ in self.conns]

        # Set affinity of main proces
        #if affinity:
        #    p = psutil.Process(os.getpid())
        #    p.cpu_affinity([affinity_core])

        self.make_dummy_list()

    def __del__(self):

        for conn in self.conns:
            conn.send('kill')

        for p in self.processes:
            p.join()
            p.terminate()

        del self
    
    def multiple_run(self, tasks):
        """Executes several tasks.

        Parameters
        ----------
        task : dict
            Dictionary contatining the required fields to execute a function, get an attribute, etc.
        

        Returns
        -------
        Token
            A token is returned. If it is called the main process will wait until the child process has returned the outputs of the function.
        
        Examples
        --------
        >>> tasks = [{'i': i, name': '<function_name>', 'args': args, 'kwargs': kwargs, 'mode': 'run'} for i in range(16)]
        >>> gh.multiple_run(tasks)
        """

        # Sort tasks into different connections
        task_id = self.running_task_id
        self.running_task_id += 1

        for task in tasks:
            task["task_id"] = task_id
        
        sorted_tasks = self.sort_tasks(tasks)

        for key, value in sorted_tasks.items():
            self.conns[key].send(value)
        
        connect_numbers = list(sorted_tasks.keys())
        token = MultipleGroupToken(self, task_id, connect_numbers, sorted_tasks, len(tasks))

        for connect_number in connect_numbers:
            self.task_cache[connect_number][task_id] = token
        return token


    # Only one task is dispatched and one gets a task_id back which can then be single_run_send
    # to retrieve the result the token object needs to be called

    def single_run(self, task):
        """Executes a single task.

        Parameters
        ----------
        task : dict
            Dictionary contatining the required fields to execute a function, get an attribute, etc.

        Returns
        -------
        Token
            A token is returned. If it is called the main process will wait until the child process has returned the outputs of the function.
        
        Examples
        ---------
        >>> gh.single_run([{'i': i, 'name': '<function_name>', 'args': args, 'kwargs': kwargs, 'mode': 'run'}])
        """
        task_id = self.running_task_id
        self.running_task_id += 1
        task["task_id"] = task_id
        connect_number = self.mapping[task['i']]

        self.conns[connect_number].send([task])
        token = GroupToken(self, task_id, connect_number)
        self.task_cache[connect_number][task_id] = token
        return token

    def run(self, tasks):
        """Runs the tasks and directly returns the ouputs.
        It is faster than multiple_run since it does not need to deal with Tokens.

        Parameters
        ----------
        tasks : list(dict)
            List of tasks.

        Returns
        -------
        list
            List with the output of the tasks.
        
        Examples
        --------
        >>> tasks = [{'i': i, name': '<function_name>', 'args': args, 'kwargs': kwargs, 'mode': 'run'} for i in range(16)]
        >>> gh.run(tasks)
        """
        tasks_sorted, l = self.run_send(tasks)
        return self.run_recv(tasks_sorted, l)
    
    def clear(self):
        """Clears all tokens from the cache.
        """
        # If there are any tokens in the cache. Get all tokens.
        for task_cache in self.task_cache:
            if task_cache:
                tokens = list(task_cache.values())
                get(tokens)
    
    def recv(self, task_id, connect_number):
        """Recieves the result of a task.

        Parameters
        ----------
        task_id : int
            Task indentifier.

        Returns
        -------
        output
            Output of the operation.

        Raises
        ------
            Exceptions that where caught in the child process.
        """

        while task_id in self.task_cache[connect_number]:
            recv_task_id, out = self.conns[connect_number].recv()

            if type(self.task_cache[connect_number][recv_task_id]) == MultipleGroupToken:
                for o in out:
                    if isinstance(o, BaseException):
                        raise o
                
                self.task_cache[connect_number][recv_task_id].data[connect_number] = out
            else:
                out = out[0] # A list with 1 element is returned
                if isinstance(out, BaseException):
                    raise out
                self.task_cache[connect_number][recv_task_id].data = out
            
            del self.task_cache[connect_number][recv_task_id]
        
        return out
    

    def run_send(self, tasks):
        """Sends tasks, to be run, to the the child processes.

        Parameters
        ----------
        tasks : list(dict)
            List of tasks.

        Returns
        -------
        tasks_sorted: dict(list(dict))
            Dictionary of sorted tasks by connection.
        l: int
            Number of tasks.
        """
        tasks_sorted = self.sort_tasks(tasks)

        for key, value in tasks_sorted.items():
            self.conns[key].send(value)
        
        return tasks_sorted, len(tasks)

    def run_recv(self, tasks_sorted, l):
        """Recieves the results to the tasks. To do this the recieved data from the child processes needs to be sorted
        to the original tasks dispatched by run_send.

        Parameters
        ----------
        tasks_sorted : dict(list(dict))
            Dictionary of sorted tasks by connection.
        l : [type]
            Number of tasks.

        Returns
        -------
        list
            Outputs to the tasks.

        Raises
        ------
        r
            Exceptions that where caught in the child processes.
        """

        # Clears any tokens that might be still pending to be recieved from the child processes
        self.clear()

        out = [None] * l

        for connect_number, task in tasks_sorted.items():
            try:
                res = self.conns[connect_number].recv()
            except EOFError:
                print(connect_number, task)
                raise

            assert len(res) == len(task)
            for r, v in zip(res, task):
                out[v['item_number']] = r
                if isinstance(r, BaseException):
                    print("item_number_excepted:", v['item_number'])
                    raise r

        return out
    
    def sort_results(self, tasks, results, l):
        """Sorts the results to the original task.

        Parameters
        ----------
        tasks : dict(list(dict))
            Dictionary of sorted tasks by connection.
        results: list(list)
            Data revieved from the child processes.
        l : [type]
            Number of tasks.

        Returns
        -------
        list
            Sorted outputs.
        """
        out = [None] * l

        for connect_number, task in tasks.items():
            res = results[connect_number]

            assert len(res) == len(task)
            for r, v in zip(res, task):
                out[v['item_number']] = r
        return out
    
    def sort_tasks(self, tasks):
        """Sort tasks into the right child processes.

        Parameters
        ----------
        tasks : [type]
            [description]

        Returns
        -------
        [type]
            [description]
        """
        # Sort task into connections
        tasks_sorted = dict()
        for i, d in enumerate(tasks):
            connect_number = self.mapping[d['i']]
            if not (connect_number in tasks_sorted.keys()):
                tasks_sorted[connect_number] = []

            d['item_number'] = i
            
            tasks_sorted[connect_number].append(d)

        return tasks_sorted

    def __len__(self):
        return self.length
    
    def make_dummy_list(self):
        self._dummy_list = [GroupDummyHandler(self, key) for key in range(self.length)]
    
    def __getitem__(self, key):
        return self._dummy_list[key]
    
    def __iter__(self):
        return iter(self._dummy_list)

class GroupDummyHandler:
    """Dummy class that is used as refrence to remember which item in the GroupHandler object needs to be called.
    It also enables to act on attributes of the obj saved in the GroupHandler like gh[0].foo.bar.moo().
    """
    def __init__(self, group_handler, key, name=""):
        """Initializes the GroupDummyHandler

        Args:
            group_handler (GroupHandler): GroupHandler wich stores the connections to the objects.
            key (int): Object number in the GroupHandler gh[key]
            name (str, optional): The attribute names that want to be acces are stored here for example name="foo.bar.moo".
        """
        self._key = key
        self._group_handler = group_handler
        self._name = name
    
    def __getattr__(self, name):
        """Returns new GroupDummyHandler with the update name."""
        if name in self.__dict__:
            return self.__dict__[name]
        
        if self._name != "":
            long_name = f"{self._name}.{name}"
        else:
            long_name = name
        
        gdh = GroupDummyHandler(self._group_handler, self._key, long_name)
        self.__dict__[name] = gdh
        return gdh
    
    def get(self):
        """Gets the attribute saved in self._name from the object stored in the group handler."""
        task = {'i': self._key, 'name': self._name, "mode": "get_attr"}
        return task
    
    def __setattr__(self, name, value):
        """ Sets the attribute in the object stored in the group handler."""
        if name[:1] == "_":
            self.__dict__[name] = value
        else:
            if self._name != "":
                name = f"{self._name}.{name}"
            
            return {'i': self._key, 'name': name, 'value': value, "mode": "set_attr"}
    
    def __call__(self, *args, **kwargs):
        """ Calls function in the object stored in the child process. """
        return {'i': self._key, 'name': self._name, "args": args, "kwargs": kwargs, "mode": "run"}



## General functions
def get(tokens):
    """Returns the result of tasks executed in parallel by apalis.

    Parameters
    ----------
    tokens : list
        List of objects of the type Token.

    Returns
    -------
    list
        List of results

    Examples
    --------
    >>> handler_list = [Handler(ClassName(i)) for i in range(10)]
    >>> apalis.get([g.f() for g in handler_list])
    """
    return [t() for t in tokens]

def patch_pickeling():
    """Exchanges the pickle protocol from multiprocessing to the one used by cloudpickle.
    
    From the cloudpickle README:  
    cloudpickle is especially useful for cluster computing where Python code is shipped over the network to execute on remote hosts, possibly close to the data.
    Among other things, cloudpickle supports pickling for lambda functions along with functions and classes defined interactively in the __main__ module (for instance in a script, a shell or a Jupyter notebook).
    """
    import cloudpickle, io
    @classmethod
    def dumps(cls, obj, protocol=None):
        buf = io.BytesIO()
        cloudpickle.dump(obj, buf)
        return buf.getbuffer()
    multiprocessing.reduction.ForkingPickler.dumps = dumps
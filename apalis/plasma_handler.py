import numpy as np
import sys

class PlasmaInfo:
    plasma_client_file_name = None
    plasma = None
    plasma_client = None
    init = False

plasma_info = PlasmaInfo()
# Will only work is plasma has been initialized
def put(obj):
    """Loads object into Plasma. Will only work if plasma has been initialized with init_plasma()

    Parameters
    ----------
    obj :
        Object that will be shared through Plasma.

    Returns
    -------
    ObjectId
        A ObjectId generated by Plasma that can be be passed to functions that are executed in a child process by apalis.

    Examples
    --------
    >>> apalis.put(1)
    ObjectID(bad02ba2c0f59e5f55033298520668cbf0ad1102)
    """
    return plasma_info.plasma_client.put(obj)

def plasma_get(oid):
    return plasma_info.plasma_client.get(oid)

def init_plasma(mem=1000):
    """Initializes a Plasma object store.

    Args:
        mem (int, optional): The argument specifies the size of the store in megabytes. Defaults to 1000.

    Returns:
        (PlasmaClient): Plasma client object
    """
    import subprocess
    global plasma_info

    if not plasma_info.init:
        import pyarrow.plasma as plasma
        plasma_info.plasma = plasma

        # get random string which will make it unlikely that two instances of plasma are trying to use the same file
        import string
        characters = string.ascii_uppercase + string.ascii_lowercase + string.digits
        characters = [c for c in characters]
        rstr = "".join(np.random.choice(characters, 10))

        plasma_info.plasma_client_file_name = "/tmp/plasma_" + rstr

        PLASMA_STORE_EXECUTABLE = sys.executable[:-6]+ "plasma_store"

        # Run Plasma
        system_run(f"{PLASMA_STORE_EXECUTABLE} -m {int(mem * 1000000)} -s {plasma_info.plasma_client_file_name}")
        plasma_info.plasma_client = plasma.connect(plasma_info.plasma_client_file_name)
        plasma_info.init = True
        return plasma_info.plasma_client
    else:
        print("Plasma has already been initialized before.")
        return plasma_info.plasma_client

def system_run(command):
    import signal
    import subprocess
    from ctypes import cdll
    print(command)
    libc = cdll.LoadLibrary('libc.so.6')
    subprocess.Popen(command.split(" "), preexec_fn=lambda *args: libc.prctl(1, signal.SIGTERM, 0, 0, 0))
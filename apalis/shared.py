import sys
import numpy as np

# Shared memory was added in python 3.8
try:
    if sys.version_info[0] == 3 and sys.version_info[1] > 7:
        from multiprocessing import shared_memory
    else:
        from apalis.multiprocessing import shared_memory
except ImportError:
    print("Shared memory could not be imported. SharedArray will not work.")

class SharedArray(np.ndarray):
    """Creates a new shared numpy array from an existing ndarray.
    SharedArrays can be used the same way as the usual numpy arrays. Note that when a SharedArray is send to another process through multiprocessing
    the array is not copied.

    Parameters
    ----------
    np : numpy.ndarray
        Numpy array to be saved into shared memory.
    
    Examples
    --------
    >>> a = apalis.SharedArray(np.zeros(10))
    SharedArray([0., 0., 0., 0., 0., 0., 0., 0., 0., 0.])
    >>> a.unlink()
    """
    _original = False
    def __new__(cls, x):
        shm = shared_memory.SharedMemory(create=True, size=x.nbytes)
        
        # Now create a NumPy array backed by shared memory
        x_shared = super().__new__(cls, x.shape, dtype=x.dtype, buffer=shm.buf)
        x_shared.set_shm(shm)
        
        np.copyto(x_shared, x)  # Copy the original data into shared memory
        # shm.buf[:] = memoryview(x).cast("B")
        return x_shared
    
    @classmethod
    def init_from_name(cls, name, dtype, shape):
        existing_shm = shared_memory.SharedMemory(name=name)
        x = super().__new__(cls, shape, dtype=dtype, buffer=existing_shm.buf)
        x.set_shm(existing_shm)
        return x
    
    def set_shm(self, shm):
        self._shm = shm
        self._original = True
    
    def unlink(self):
        """Deletes the object from shared memory.
        """
        self._shm.close()
        self._shm.unlink()
    
    def __reduce__(self):
        if self._original:
            return (self.__class__.init_from_name, (self._shm.name, self.dtype, self.shape))
        
        # If it the object was not initialized with __new__, the object should revert to a ndarray after pickeling.
        redu = super().__reduce__()
        redu2 = (redu[0], (np.ndarray,) + redu[1][1:]) + redu[2:]
        return redu2

        return (self.__class__.init_from_name, (self._shm.name, self.dtype, self.shape))
       
    def __del__(self):
        if self._original:
            self._shm.close()
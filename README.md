![Apalis Logo](https://danielalcalde.github.io/apalis/_static/apalislogo.svg)

[Documentation](https://danielalcalde.github.io/apalis)

# What is Apalis?

Apalis is a python library for parallel computing. It focuses on enabling parallel computing with little overhead. In :ref:`ray` we compare Apalis
to ray in speed.

# Getting started with Apalis

Apalis can be installed from PyPI:

.. code-block:: bash

   pip install apalis

Apalis can send an object into a child process and interact with it through a Handler.
To send an object into a parallel process just:

```
   import apalis
   import time

   class A:
    def expensive(self, x):
      time.sleep(1)
      return x
      
   a = A()
   obj = apalis.Handler(a) # Send object
   token = obj.expensive(5) # Sends the task to the object in the child process.
   token() # Calling the token yields the result of the operation.

```python

The same can be done with multiple Handlers at once.

```
    
   es = [apalis.Handler(A()) for _ in range(16)]
   tokens = [obj.expensive(5) for obj in objs]
   aplais.get(tokens) # Gets the results of the operations.

```python

More examples can be found in this (Jupyter Notebook)[link].
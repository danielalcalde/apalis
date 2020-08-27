<p align="center">
  <img src="https://danielalcalde.github.io/apalis/_static/apalislogo.svg" />
</p>

# What is Apalis?

Apalis is a python library for parallel computing. It focuses on enabling parallel computing with little overhead. To explore the apalis functionality see the [Documentation](https://danielalcalde.github.io/apalis).

# Getting started with Apalis

Apalis can be installed from PyPI:

```bash
   pip install apalis
```

Apalis can send an object into a child process and interact with it through a Handler.
To send an object into a parallel process just:

```python
   import apalis
   import time

   class A:
    def expensive(self, x):
      time.sleep(1)
      return x
      
   a = A()
   obj = apalis.Handler(a) # Sends the object to a child process.
   token = obj.expensive(5) # Sends the task to the object in the child process.
   token() # Calling the token yields the result of the operation.

```

The same can be done with multiple Handlers at once.

```python
   objs = [apalis.Handler(A()) for _ in range(16)]
   tokens = [obj.expensive(5) for obj in objs]
   aplais.get(tokens) # Gets the results of the operations.

```

More examples can be found in this [Jupyter Notebook](https://danielalcalde.github.io/apalis/examples.html).
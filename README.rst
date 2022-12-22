interactions.py
===============


What it is?
***********

This is experimental branch or most likely prototype, my vision of version 4.5.0 for interactions.py.
As you know v4.4.0 is the latest minor version of v4 major. Next versions will take v5 as major.
It's will be different library with NAFF codebase.
But i want to try improve v4 as i can.
This branch should not be used in the production. But if you want use it on your own risk. I wont help you or fix any bugs.

What will be changed?
---------------

Change minimal version of python to 3.10
Rewrite gateway with using ``anyio`` library.
Refactor event dispatching.
Use ``cattrs`` to [un]structure dataclasses.
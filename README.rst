interactions.py
===============


What is it?
***********

This is a experimental version of interactions.py named v4.5.0. It's just an attempt to improve codebase.
I don't garantie this version will work, so you should not use it in the production.

**This version wont be merged in official interactions.py**

Why?
v4.4.0 is the latest minor version of interactions.py because NAFF merges into i.py and next version will be v5.

To do
-----

- [ ] - Refactor event dispatching.
- [ ] - Solve issue with different cached objects. Like we could have channel in cache and in ``guild.channels`` but it will be different objects.
- [ ] - Rewrite gateway with using ``anyio`` library.
- [ ] - Use ``cattrs`` to [un]structure dataclasses.

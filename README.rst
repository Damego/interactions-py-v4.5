interactions.py
===============


What it is?
***********

This is experimental branch or most likely prototype, my vision of version 4.5.0 for interactions.py.
As you know v4.4.0 is the latest minor version of v4 major. Next versions will take v5 as major.
It's will be different library with NAFF codebase.
But i want to try improve v4 as i can.
This branch should not be used in the production.

To do
---------------

- [ ] - Refactor event dispatching.
- [ ] - Rewrite gateway with using ``anyio`` library.
- [ ] - Use ``cattrs`` to [un]structure dataclasses.
- [ ] - Solve issue with different cached objects. Like we could have channel in cache and in guild.channels but it's will be different objects.
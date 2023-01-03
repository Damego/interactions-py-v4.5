interactions.py
===============


What is it?
***********

This is a experimental version of interactions.py named v4.5.0. It's just an attempt to improve codebase.
I don't garantie this version will work, so you should not use it in the production.

**This version wont be merged in official interactions.py**

Why?
v4.4.0 is the latest minor version of interactions.py because NAFF merges into i.py and next version will be v5.

What changed?
-------------
- Refactored event dispatching. Removed cursed dynamic code and replaced with processors.
- Made ``channels``, ``members``, ``roles``, ``threads`` for ``Guild`` as property which will use cache.
- Made stickers and emojis store in the cache and made they as property of ``Guild``.
- Cleaned up code (partially). Removed duplicate code in http and in helper methods, removed guild modifying and more stuff.
- Removed ``GuildMember``.
- Renamed ``Tags`` to ``ForumTag``



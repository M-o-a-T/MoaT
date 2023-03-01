import sys
import anyio

# All Stacks builders return a (top,bot) tuple.
# The top is the Request object. You're expected to attach your Base
# (or a subclass) to it, then call `bot.run()`.

from moat.util.queue import Queue

from ..main import Request
from ..compat import TaskGroup, AnyioMoatStream
from ..proto.stream import MsgpackStream
from ..proto import Logger

import logging
logger = logging.getLogger(__name__)

async def unix_stack_iter(path="upy-moat", log=False, *, evt=None, request_factory=Request):
    # an iterator for Unix-domain connections / their stacks. Yields one t,b
    # pair for each successful connection.

    q=Queue(1)

    async with TaskGroup() as tg:
        listener = await anyio.create_unix_listener(path)
        if evt is not None:
            evt.set()

        await tg.spawn(listener.serve, q.put)
        n = 0
        async for sock in q:
            n += 1
            t = b = MsgpackStream(AnyioMoatStream(sock))
            await b.init()
            if log:
                t = t.stack(Logger, txt="U%d" % n)
            t = t.stack(request_factory)
            yield t,b




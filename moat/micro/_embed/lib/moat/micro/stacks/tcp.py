"""
Support code to connect to a TCP server.
"""
from __future__ import annotations

from ..compat import Event, TaskGroup, run_server
from ..proto.stream import SingleAIOBuf
from ..stacks.util import BaseConnIter

from typing import TYPE_CHECKING  # isort:skip

if TYPE_CHECKING:
    from typing import Never

class TcpIter(BaseConnIter):
    """
    A connection iterator for TCP sockets
    """

    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port

    async def accept(self) -> Never:  # noqa:D102
        async with TaskGroup() as tgx:
            evt = Event()

            async def rdy(evt):
                await evt.wait()
                self.set_ready()

            await tgx.spawn(rdy, evt)

            await run_server(self._handle, self.host, self.port, evt=evt)

    async def _handle(self, conn):
        await self.add_conn(SingleAIOBuf(conn))

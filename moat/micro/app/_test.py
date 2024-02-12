"""
Apps used for testing.
"""

from __future__ import annotations

from moat.micro._test import Loopback, MpyBuf
import anyio

from moat.micro.compat import AC_use
from moat.micro.proto.stream import MsgpackMsgBlk

from ._test_ import Cmd, Cons  # noqa:F401 pylint:disable=unused-import


def MpyCmd(*a, **k):
    """MoaT link to a local micropython process"""
    from moat.micro.cmd.stream.cmdmsg import BaseCmdMsg
    from moat.micro.stacks.console import console_stack

    class _MpyCmd(BaseCmdMsg):
        async def stream(self):
            mpy = MpyBuf(self.cfg)
            return await AC_use(self, console_stack(mpy, self.cfg))

    return _MpyCmd(*a, **k)


def MpyRaw(*a, **k):
    """stdio of a local micropython process"""
    from moat.micro.cmd.stream.cmdbbm import BaseCmdBBM

    class _MpyRaw(BaseCmdBBM):
        async def stream(self):
            return await AC_use(self, MpyBuf(self.cfg))

    return _MpyRaw(*a, **k)


def Loop(*a, **k):
    """Loopback. Unlike remote.Fwd this goes through msgpack."""
    from moat.micro.cmd.stream.cmdmsg import BaseCmdMsg
    from moat.micro.stacks.console import console_stack

    class _Loop(BaseCmdMsg):
        async def stream(self):
            s = Loopback(**self.cfg.get("loop", {}))
            s.link(s)
            if (li := self.cfg.get("link", None)) is not None:
                if "pack" in li and len(li) == 1:
                    s = MsgpackMsgBlk(s, li)
                    if (log := self.cfg.get("log", None)) is not None:
                        from ..proto.stack import LogMsg
                        s = LogMsg(s, log)
                    s = await AC_use(self, s)
                else:
                    s = await AC_use(self, console_stack(s, self.cfg))
            return s

    return _Loop(*a, **k)


def LoopMsg(*a, **k):
    """Test Loopback connection.

    This app uses the LoopBBM back-end, thus needs to connect to a LoopLink
    that uses queues for both directions.
    """
    from moat.micro.cmd.stream.cmdbbm import BaseCmdBBM
    from moat.micro._test import LoopBBM

    class _LoopMsg(BaseCmdBBM):
        async def stream(self):
            return await AC_use(self, LoopBBM(self.cfg))

    return _LoopMsg(*a, **k)


def LoopLink(*a, **k):
    """Bi- or even multidirectional loopback.

    The ``path`` config says where to read from.
    If not given, uses the local read buffer.
    Read relationships do NOT need to be symmetrical.
    Reading from self works.

    ``usage`` is a string that controls which buffers to create.

    * m – Messages
    * b – Byte blocks
    * s – serial data
    * c – Console stream

    Lower case are write buffers; upper case are read buffers.
    If the remote side is a LoopBBM, both are required.

    Requests use a queue if it exists. Otherwise the request is forwarded
    to the external end of the remote queue.
    """
    from moat.micro.cmd.base import BaseCmd
    from moat.micro._test import Loopback

    class _LoopLink(BaseCmd):
        q_wm,q_wmr = None,None
        q_wb,q_wbr = None,None
        q_ws,q_wse = None,None
        q_wc,q_wce = None,None
        q_rmw,q_rm = None,None
        q_rbw,q_rb = None,None
        q_rse,q_rs = None,None
        q_rce,q_rc = None,None

        async def setup(self):
            p = self.cfg.get("path",None)
            if isinstance(p,str):
                raise ValueError(f"Need a path, not {p !r}")
            self.remote = self.root.sub_at(*p) if p is not None else None

            u = self.cfg.get("usage","")
            if "m" in u:
                self.q_wm,self.q_wmr = anyio.create_memory_object_stream(self.cfg.get("qlen",99))
            if "b" in u:
                self.q_wb,self.q_wbr = anyio.create_memory_object_stream(self.cfg.get("qlen",99))
            if "s" in u:
                self.q_ws,self.q_wse = bytearray(),anyio.Event()
            if "c" in u:
                self.q_wc,self.q_wce = bytearray(),anyio.Event()

            if "M" in u:
                self.q_rmw,self.q_rm = anyio.create_memory_object_stream(self.cfg.get("qlen",99))
            if "B" in u:
                self.q_rbw,self.q_rb = anyio.create_memory_object_stream(self.cfg.get("qlen",99))
            if "S" in u:
                self.q_rse,self.q_rs = anyio.Event(),bytearray()
            if "C" in u:
                self.q_rce,self.q_rc = anyio.Event(),bytearray()

            await super().setup()

        # Messages

        def cmd_s(self, m) -> Awaitable:
            "write to the message queue"
            if self.q_wm:
                return self.q_wm.send(m)
            else:
                return self.remote.xs(m=m)

        def cmd_xs(self, m) -> Awaitable:
            "remotely write the message read queue"
            return self.q_rmw.send(m)

        def cmd_r(self):
            "read the message queue"
            if self.q_rm:
                return self.q_rm.receive()
            else:
                return self.remote.xr()

        def cmd_xr(self):
            "remotely read the message write queue"
            return self.q_wmr.receive()

        # Blocks

        def cmd_sb(self, m) -> Awaitable:
            "write to the block queue"
            if self.q_wb:
                return self.q_wb.send(m)
            else:
                return self.remote.xsb(m=m)

        def cmd_xsb(self, m) -> Awaitable:
            "remotely write the block read queue"
            return self.q_rbw.send(m)

        def cmd_rb(self):
            "read the byte queue"
            if self.q_rb:
                return self.q_rb.receive()
            else:
                return self.remote.xrb()

        def cmd_xrb(self):
            "remotely read the block write queue"
            return self.q_wbr.receive()

        # Bytes

        async def cmd_wr(self, b):
            "write to the byte queue"
            if self.q_wse is not None:
                self.q_ws.extend(b)
                self.q_wse.set()
                self.q_wse = anyio.Event()
            else:
                return await self.remote.xwr(b)

        async def cmd_xwr(self, b) -> Awaitable:
            "remotely write the byte read queue"
            self.q_rs.extend(b)
            self.q_rse.set()
            self.q_rse = anyio.Event()

        async def cmd_rd(self, n=64):
            "read the byte queue"
            if self.q_rse is None:
                return await self.remote.xrd(n=n)
            while not self.q_rs:
                await self.q_rse.wait()
            n = min(n,len(self.q_rs))
            res = self.q_rs[:n]
            self.q_rs[:n] = b''
            return res

        async def cmd_xrd(self, n=64):
            "remotely read the byte write queue"
            while not self.q_ws:
                await self.q_wse.wait()
            n = min(n,len(self.q_ws))
            res = self.q_ws[:n]
            self.q_ws[:n] = b''
            return res

        # Console

        async def cmd_cwr(self, b):
            "write to the console queue"
            if self.q_wce is not None:
                self.q_wc.extend(b)
                self.q_wce.set()
                self.q_wce = anyio.Event()
            else:
                return await self.remote.xcwr(b)

        async def cmd_xcwr(self, b) -> Awaitable:
            "remotely write the console read queue"
            self.q_rc.extend(b)
            self.q_rce.set()
            self.q_rce = anyio.Event()

        async def cmd_crd(self, n=64):
            "read the console queue"
            if self.q_rce is None:
                return await self.remote.xcrd(n=n)
            while not self.q_rc:
                await self.q_rce.wait()
            n = min(n,len(self.q_rc))
            res = self.q_rc[:n]
            self.q_rc[:n] = b''
            return res

        async def cmd_xcrd(self, n=64):
            "remotely read the console write queue"
            while not self.q_wc:
                await self.q_wce.wait()
            n = min(n,len(self.q_wc))
            res = self.q_wc[:n]
            self.q_wc[:n] = b''
            return res

    return _LoopLink(*a, **k)

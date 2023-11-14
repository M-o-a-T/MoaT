"""
Test runner
"""
from __future__ import annotations

import anyio
import logging
import os
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from pathlib import Path
from random import random

import moat.micro
from moat.util import attrdict, combine_dict, packer, yload
from moat.micro.cmd.tree.dir import Dispatch
from moat.micro.compat import TaskGroup, L

# from moat.micro.main import Request, get_link, get_link_serial
# from moat.micro.proto.multiplex import Multiplexer
from moat.micro.proto.stack import BaseBuf, BaseMsg
from moat.micro.proto.stream import ProcessBuf

logging.basicConfig(level=logging.DEBUG)


def _lbc(*a, **k):  # noqa: ARG001
    "block log configuration"
    raise RuntimeError("don't configure logging a second time")


logging.basicConfig = _lbc


temp_dir = ContextVar("temp_dir")

required = [
    "__future__",
    "copy",
    "errno",
    "pprint",
    "typing",
    "types",
    "functools",
    "contextlib",
    "ucontextlib",
    "collections",
    "collections-deque",
]


def rlink(s, d):
    "recursive linking"
    if s.is_file():
        with suppress(FileExistsError):
            d.symlink_to(s)
    else:
        with suppress(FileExistsError):
            d.mkdir()
        for f in s.iterdir():
            rlink(s / f.name, d / f.name)


class MpyBuf(ProcessBuf):
    """
    A stream that links to MicroPython.

    If the config option "mplex" is `True`, this starts a standard
    multiplexer. Otherwise you get a plain micropython interpreter;
    if `False` (instead of missing or `None`), your directory contains a
    "stdlib" folder and MICROPYPATH will point to it.

    Using this option requires either running as part of a MpyStack,
    or setting the ``cwd`` config to a suitable directory.

    If "mplex" is a string, it is interpreted as the "state" argument to
    ``main.go()``. The default for ``mplex=True`` is "once".
    """

    async def setup(self):
        mplex = self.cfg.get("mplex", None)
        if mplex is not None:
            try:
                os.stat("micro/lib")
            except OSError:
                pre = Path(__file__).parents[2]
            else:
                pre = "micro/"

            root = self.cfg.get("cwd", None)
            if root is None:  # noqa:SIM108
                root = temp_dir.get() / "root"
            else:
                root = Path(root).absolute()
            lib = root / "stdlib"
            lib2 = root / "lib"
            with suppress(FileExistsError):
                root.mkdir()
            with suppress(FileExistsError):
                lib.mkdir()
            with suppress(FileExistsError):
                lib2.mkdir()
            if mplex:
                with suppress(FileExistsError):
                    (root / "tests").symlink_to(Path("tests").absolute())

            std = Path("lib/micropython-lib/python-stdlib").absolute()
            ustd = Path("lib/micropython-lib/micropython").absolute()
            for req in required:
                if (std / req).exists():
                    rlink(std / req, lib)
                elif (ustd / req).exists():
                    rlink(ustd / req, lib)
                else:
                    raise FileNotFoundError(req)

            aio = Path("lib/micropython/extmod/asyncio").absolute()
            with suppress(FileExistsError):
                (lib / "asyncio").symlink_to(aio)

            libp = []
            for p in moat.micro.__path__:
                p = Path(p) / "_embed"  # noqa:PLW2901
                if p.exists():
                    libp.append(p)
                if (p / "lib").exists():
                    libp.append(p / "lib")

            self.env = {
                "MICROPYPATH": os.pathsep.join(str(x) for x in (lib, lib2, *libp)),
            }
            self.cwd = root

        if mplex:
            with (root / "moat.cfg").open("wb") as f:
                f.write(packer(self.cfg["cfg"]))

            self.argv = [
                # "strace","-s300","-o/tmp/bla",
                pre / "lib/micropython/ports/unix/build-standard/micropython",
                pre / "tests-mpy/mplex.py",
            ]
            if isinstance(mplex, str):
                self.argv.append(mplex)
        else:
            self.argv = [
                pre / "lib/micropython/ports/unix/build-standard/micropython",
                "-e",
            ]

        await super().setup()


@asynccontextmanager
async def mpy_stack(temp: Path, cfg: dict | str, cfg2: dict | None = None):
    """
    Creates a multiplexer.
    """
    if isinstance(cfg, str):
        if "\n" in cfg:
            cfg = yload(cfg, attr=True)
        else:
            with (Path("tests") / "cfg" / (cfg + ".cfg")).open("r") as cff:
                cfg = yload(cff, attr=True)

    if cfg2 is not None:
        cfg = combine_dict(cfg2, cfg)

    rst = temp_dir.set(temp)
    try:
        async with TaskGroup() as tg:
            stack = Dispatch(cfg)
            try:
                await tg.spawn(stack.run)
                if L:
                    await stack.wait_ready()
                yield stack
            finally:
                tg.cancel()
    finally:
        temp_dir.reset(rst)


class Loopback(BaseMsg, BaseBuf):
    """
    A simple loopback object.

    The write queue is created locally, the read queue is taken from the
    "other side".

    This object can be self-linked.
    """

    # pylint:disable=abstract-method

    _link = None
    _buf = None

    def __init__(self, qlen=0, loss=0):
        super().__init__({})
        assert 0 <= loss < 1
        self.q_wr, self.q_rd = anyio.create_memory_object_stream(qlen)
        self.loss = loss

    async def setup(self):
        if self._link is None:
            raise RuntimeError("Link before setup!")

    def link(self, other):
        """Tell this loopback to read from some other loopback."""
        self._link = other

    async def send(self, m, _loss=True):  # pylint:disable=arguments-differ
        """Send data."""
        if self._link is None:
            raise anyio.BrokenResourceError(self)
        if _loss and random() < self.loss:
            return
        try:
            await self.q_wr.send(m)
        except (anyio.ClosedResourceError, anyio.BrokenResourceError, anyio.EndOfStream) as exc:
            raise EOFError from exc

    snd = send

    async def recv(self):  # pylint:disable=arguments-differ
        if self._link is None:
            raise anyio.BrokenResourceError(self)
        try:
            return await self._link.q_rd.receive()
        except (anyio.ClosedResourceError, anyio.BrokenResourceError, anyio.EndOfStream):
            raise EOFError from None

    rcv = recv

    async def rd(self, buf) -> int:
        while True:
            if self._buf:
                n = min(len(self._buf), len(buf))
                buf[0:n] = self._buf[0:n]
                self._buf = self._buf[n:]
                return n
            self._buf = await self.recv()

    async def wr(self, buf) -> int:
        if self.loss:
            b = bytearray(buf)
            loss = 1 - (1 - self.loss) ** (1 / len(b) / 2)
            # '1-loss' is the chance of not killing each single byte
            # that's required to not kill a message of size len(b)
            # given two chances of mangling each byte

            n = 0
            while n < len(b):
                if random() < loss:
                    del b[n]
                else:
                    if random() < loss:
                        b[n] = b[n] ^ (1 << int(8 * random()))
                    n += 1
        else:
            b = bytes(buf)
        await self.send(bytes(buf), _loss=False)

    async def teardown(self):
        await self.q_wr.aclose()
        if self._link is not None and self._link is not self:
            await self._link.q_rd.aclose()
        await super().teardown()


class Root(Dispatch):
    "an empty root for testing"

    def __init__(self):
        super().__init__({})


# Fake "machine" module

machine = attrdict()


class FakeI2C:
    def __init__(self, c, d, **_):
        self._c = c
        self._d = d


class FakePin:
    def __init__(self, pin, **_):
        self._pin = pin


machine.Pin = FakePin
machine.I2C = FakeI2C
machine.SoftI2C = FakeI2C

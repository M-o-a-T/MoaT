"""
Basic infrastructure to run an RPC system via an unreliable,
possibly-reordering, and/or stream-based transport

We have a stack of classes. At the top there's the adapting App, a subclass
of StreamCmdMsg. Linked to it via a chain of *Msg…Buf modules there's a
*Buf adapter that affords an external interface.

Everything is fully asynchronous. Each class is an async context manager,
responsible for managing the contexts of its sub-app(s) / linked stream(s).

Incoming messages are handled by the child's "dispatch" method. They
are expected to be fully asynchronous, i.e. a "run" method that calls
"dispatch" must use a separate task to do so.

Outgoing messages are handled by the parent's "send" method. Send calls
return when the data has been sent, implying that sending on an
unreliable transport will wait for the message to be confirmed. Sending
may fail.
"""

from __future__ import annotations

import sys

from moat.micro.proto.stack import Base
from moat.micro.compat import TaskGroup, idle, Event, wait_for_ms, log, Lock, AC_use, TimeoutError
from moat.util import Path

from .util import run_no_exc, StoppedError, wait_complain

uPy = sys.implementation.name == "micropython"


class BaseCmd(Base):
    """
    Basic Request/response handler.

    This class does not accept subcommands.
    """
    _parent:BaseCmd = None
    _ts = None
    _rl_ok = None  # result of last reload
    p_task = None  # managed by parent. Do not touch.

    def __init__(self, cfg):
        super().__init__(cfg)
        # self.cfg = cfg
        self._init_events()

    def _init_events(self):
        self._starting = Event()
        self._ready = Event()
        self._stopped = Event()

    async def setup(self):
        """
        Start up this command.

        Call first when overriding.
        """
        await AC_use(self,self._is_stopped)
        if self._stopped is None:
            self._init_events()
        elif self._starting is None or self._starting.is_set():
            raise RuntimeError("DupStartA")

        self._starting.set()
        self._starting = None

    async def teardown(self):
        """
        Clean up this command.

        Call last when overriding.
        """
        pass

    def _is_stopped(self):
        """
        The command has ended.
        """
        if self._stopped is None:
            return
        self._stopped.set()
        self._stopped = None

        if self._starting is not None:
            self._starting.set()
            self._starting = None

        if self._ready is not None:
            self._ready.set()
            self._ready = None


    async def run(self):
        """
        Task handler to run this command.

        If you need a subtask, override `task`.
        """
        async with self:
            await self.task()

    async def task(self):
        """
        The app's task. Runs after `setup` has completed. By default does nothing.

        If you override this, you're responsible for eventually calling `set_ready`.
        Otherwise the MoaT system will stall!
        """
        self.set_ready()
        await idle()

    def set_ready(self):
        if self._starting is not None:
            raise RuntimeError("Ready w/o start")
            # self._starting.set()
            # self._starting = None
        if self._ready is not None:
            self._ready.set()
            self._ready = None

    async def stop(self):
        if self.p_task is None:
            return  # not running
        elif self.p_task is False:
            raise RuntimeError("Colliison")
        self.p_task.cancel()
        await wait_complain(f"Stop {self.path}", 250, self.wait_stopped)

    async def wait_started(self):
        if self._starting is None:
            return
        await self._starting.wait()

    async def wait_ready(self, wait=True) -> bool|None:
        """
        Check if the command is ready.

        Returns True if it is stopped, False if it is already running, and
        None if the command has (or would have, if @wait is False) waited
        for it to become ready.
        """
        if self._stopped is None:
            return True
        if self._ready is None:
            return False
        if wait:
            await wait_complain(f"Rdy {self.path}", 250, self._ready.wait)
        return None

    def cmd_rdy(self, w=True) -> Awaitable:
        return self.wait_ready(wait=w)

    async def wait_stopped(self):
        if self._stopped is not None:
            await self._stopped.wait()

    cmd_stp = wait_stopped

    @property
    def path(self):
        return self._parent.path / self._name

    def send(self, *action, _x_err=(), **kw) -> Awaitable:
        """
        Send a message, returns a reply.

        Delegates to the root dispatcher.

        Do not override this.
        """
        return self.root.dispatch(action, kw, x_err=_x_err)

    def send_iter(self, _rep, *action, **kw) -> AsyncContextManager:
        """
        Send a message, receive an iterated reply.

        The first argument is the delay between replies, in msec.

        Usage::

            async with self.iter(250, "foo","bar", baz=123) as it:
                async for msg in it:
                    ...

        Delegates to the root dispatcher.
         
        Do not override this.
        """
        return self.root.dispatch(action, kw, rep=_rep)

    def send_nr(self, *action, _x_err=(), **kw) -> Awaitable:
        """
        Send a possibly-lossy message, does not return a reply.

        Delegates to the root dispatcher

        Do not override this.
        """
        return self.root.dispatch(action, kw, wait=False, x_err=_x_err)
        # XXX run in a separate task


    async def dispatch(
            self, action: list[str], msg: dict, rep:int = None, wait:bool = True, x_err=()
    ):  # pylint:disable=arguments-differ
        """
        Process a message.

        @msg is either a dict (keyword+value for the destination handler)
        or not (single direct argument).

        @action is a list. This dispatcher requires it to have exactly one
        element: the command name.

        Returns whatever the called command returns/raises, or raises
        AttributeError if no command is found.

        Warning: All incoming commands wait for the subsystem to be ready.

        If @rep is >0, the requestor wants an iterator with (roughly) "@rep"
        milliseconds between values. You need to return an async context
        manager that implements one.
        """

        if not action:
            raise RuntimeError("noAction")
        elif len(action) > 1:
            raise ValueError("no chain here", action)
        else:
            p = getattr(self,"cmd_"+action[0])
            
        if not wait:
            if rep:
                raise ValueError("can't rep without wait")
            self.tg.spawn(run_no_exc, p,msg,x_err, _name=f"Call:{self.path}/{a or '-'}")
            return

        await self.wait_ready()
        r = p(**msg)
        if hasattr(r, "throw"):  # coroutine
            r = await r
        if rep:
            if not hasattr(r, "__aiter__"):
                # This is not already an iterator
                r = IterWrap(p,(),msg, r)
            if not isinstance(r,_DelayedIter):
                r = DelayedIter(it=r, t=rep)
        else:
            if hasattr(r, "__aiter__"):  # async iter
                raise ValueError("iterator")
        return r

    def send(self, *a, _x_err=(), **k):
        "Sending is forwarded to the root"
        return self.root.dispatch(a, k, x_err=_x_err)


    # globally-available commands

    def cmd_dir(self, h=False):
        """
        Rudimentary introspection. Returns a list of available commands @c and
        submodules @d. j=True if callable directly.
        """
        c = []
        res = dict(c=c)

        for k in dir(self):
            if k.startswith("cmd_") and h == (k[4] == '_'):
                c.append(k[4:])
            elif k == ("_cmd" if h else "cmd"):
                res['j'] = True
        return res


    def attached(self, parent:DirCmd, name:str):
        if self._parent is not None:
            raise RuntimeError(f"already {'.'.join(self.path)}")
        self._parent = parent
        self._name = name
        self.root = parent.root

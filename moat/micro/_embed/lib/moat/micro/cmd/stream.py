"""
Stream link-up support for MoaT commands
"""

from __future__ import annotations

import sys

from moat.util import ValueEvent, obj2name, NotGiven
from .util import ValueTask, SendIter, RecvIter
from moat.micro.compat import CancelledError, WouldBlock, log, Lock, ACM, AC_exit
from moat.micro.proto.stack import RemoteError, SilentRemoteError, BaseMsg

from .base import BaseCmd

class BaseBBMCmd(BaseCmd):
    """
    This is a command handler that connects MoaT's Cmd tree to a `BaseBuf`,
    `BaseBlk` or `BaseMsg` instance.

    Override `setup` to return that instance.
    """
    def __init__(self, cfg):
        super().__init__(cfg)
        self.w_lock = Lock()

    async def setup(self):
        raise NotImplementedError("setup", self.path)

    async def run(self):
        ACM(self)
        try:
            self.dev = await self.setup()
            await super().run()
        finally:
            del self.dev
            await AC_exit(self)
    
    async def cmd_rd(self, n=64):
        """read some data"""
        b = bytearray(n)
        r = await self.dev.rd(b)
        if r == n:
            return b
        elif r <= n>>2:
            return bytes(b[:r])
        else:
            b = memoryview(b)
            return b[:r]

    async def cmd_wr(self, b):
        """write some data"""
        async with self.w_lock:
            await self.dev.wr(b)

    async def cmd_crd(self, n=64):
        """read some console data"""
        b = bytearray(n)
        r = await self.dev.crd(b)
        if r == n:
            return b
        elif r <= n>>2:
            return bytes(b[:r])
        else:
            b = memoryview(b)
            return b[:r]

    async def cmd_cwr(self, b):
        """write some console data"""
        async with self.w_lock:
            await self.dev.cwr(b)

    async def cmd_s(self, m):
        """send a message"""
        return await self.dev.send(m)

    async def cmd_r(self):
        """receive a message"""
        return await self.dev.recv(m)



class StreamCmd(BaseCmd):
    """
    This is a command handler that relays messages between MoaT's Cmd tree
    and a `BaseMsg` stream.
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        self.reply = {}
        self.seq = 3
        # seqnum must be odd
        # we want it to not be zero when the low bit is flipped
        # TODO: CBOR: use negative seqnums for replies 

    async def stream(self):
        """
        Creates the actual data stream. Must be called with an active ACM.

        Must be overridden.
        """
        raise NotImplementedError("Create the stream: ",self.__class__.__name)

    async def run(self):
        """
        Start the stack.

        You typically override `stream`, not this method.
        """
        acm = ACM(self)
        err = None
        try:
            await acm(self._cleanup_open_commands)
            self.s = await self.stream()
            self.set_ready()
            while True:
                msg = await self.s.recv()
                await self._handle(msg)
        except Exception as exc:
            err = exc
            log("Run", err=err)
            raise
        except BaseException as exc:
            err = exc
            raise
        finally:
            self.s = None
            await AC_exit(self, type(err) if err is not None else err, err, None)
            if err is not None:
                raise err

    # stacked
    async def error(self, exc):
        print("ERROR: " + repr(error), file=sys.stderr)

    def _cleanup_open_commands(self):
        for e in self.reply.values():
            e.cancel()

    async def _handle_request(self, a, i, d, msg):
        """
        Handler for a single request.

        `_handle` starts this in a new task for each message.
        """
        res = {'i': i}
        try:
            r = await self.root.dispatch(a, d)
        except SilentRemoteError as exc:
            if i is None:
                return
            res["e"] = type(exc)
            res["d"] = exc.args
        except WouldBlock:
            raise
        except Exception as exc:  # pylint:disable=broad-exception-caught
            # TODO only when debugging
            log("ERROR handling %r %r %r %r", a, i, d, msg, err=exc)
            if i is None:
                return
            try:
                obj2name(type(exc))
            except KeyError:
                res["e"] = "E:" + repr(exc)
            else:
                res["e"] = type(exc)
                res["d"] = exc.args
        except BaseException as exc:  # pylint:disable=broad-exception-caught
            res["e"] = type(StoppedError)
            res["d"] = (repr(exc),)
        else:
            if i is None:
                return
            res["d"] = r

        try:
            await self.s.send(res)
        except TypeError as exc:
            log("ERROR returning %r", res, err=exc)
            res = {'e': "T:" + repr(exc), 'i': i}
            await self.s.send(res)

    async def reply_result(self, i, res):
        if i is None:
            return
        try:
            await self.s.send({'i':i, 'd':res})
        except Exception as e:
            await self.reply_error(i, e)
        except BaseException as e:
            await self.reply_error(i, e)
            raise

    async def reply_error(self, i, exc):
        try:
            if isinstance(exc, SilentRemoteError):
                pass
            else:
                log("ERROR handling %d", i, err=exc)
            if i is None:
                return
            res = {'i': i}
            if isinstance(exc,Exception):
                try:
                    obj2name(type(exc))
                except KeyError:
                    res["e"] = "E:" + repr(exc)
                else:
                    res["e"] = type(exc)
                    res["d"] = exc.args
            else:
                res["e"] = type(StoppedError)
                res["d"] = (repr(exc),)
            await self.s.send(res)
        except TypeError as e2:
            log("ERROR returning %r", res, err=e2)
            await self.s.send({'e': "T:" + repr(exc), 'i': i})

    async def _handle(self, msg):
        """
        Main handler for incoming messages
        """
        if not isinstance(msg, dict):
            print("?3", msg, file=sys.stderr)
            return
        a = msg.get("a", None)
        i = msg.get("i", None)
        d = msg.get("d", NotGiven)
        e = msg.get("e", None)
        r = msg.get("r", None)
        n = msg.get("n", None)

        if i is not None:
            i ^= 1

        for k in msg.keys():
            if k not in "aidren":
                log("Unknown %s: %r", k, msg)
                break

        if a is not None:
            # incoming request
            # runs in a separate task
            # XXX create a task pool?
            if d is NotGiven:
                d = None
            if r is None:
                t = ValueTask(self, i, self.root.dispatch, a, d)
            else:
                t = SendIter(self, i, r, a, d)

            if i is not None:
                if i in self.reply:
                    log("msgid known?!? %d", i)
                    tt = self.reply.pop(i)
                    tt.i = None
                    tt.error(RuntimeError("OldCmd"))
                self.reply[i] = t
            rm = await t.start()
            if r is not None:
                await self.s.send({'i':i, 'r':rm})

        else:
            # reply
            if i is None:
                log("?? %r", msg)
                return

            t = self.reply.get(i, None)
            if t is None:
                log("unknown %r", msg)
                return

            if e is not None:
                if isinstance(e,type):
                    if d is NotGiven:
                        d = ()
                    e = e(*d)
                elif isinstance(e,str):
                    e = RemoteError(e)
                elif isinstance(e,Exception):
                    pass
                else:
                    log("unknown err %r", msg)
                    e = StoppedError()
                t.set_error(e)

            elif r is not None:
                if r is False:
                    t.error(StopIter())
                    del self.reply[i]
                else:
                    t.set_r(r)

            elif d is not NotGiven:
                if isinstance(t, (SendIter,RecvIter)):
                    if n:
                        t.set(d,n=n)
                    else:
                        t.set(d)
                    return
                else:
                    t.set(d)
                    del self.reply[i]

            else: # just i
                t.cancel()
                del self.reply[i]


    async def dispatch(self, action, msg=None, rep:int=None, wait=True):  # pylint:disable=arguments-differ
        """
        Forward a request to the remote side, return the response.

        The message is either the second parameter, or a dict (use any
        number of keywords).

        If @wait is False, the message doesn't have a sequence number and
        thus no reply will be expected.

        @rep requests iterated replies.
        """

        if self.s is None:
            raise EOFError

        if not wait:
            msg = {"a": action, "d": msg}
            await self.s.send(msg)
            return
        
        # Find a small-ish but unique *ODD* seqnum
        # even seqnums are requests from the other side
        if self.seq > 10 * (len(self.reply) + 5):
            self.seq = 9
        while True:
            self.seq += 2
            seq = self.seq
            if seq not in self.reply:
                break
        msg = {"a": action, "d": msg, "i": seq}

        if rep:
            msg["r"] = rep
            self.reply[seq] = e = RecvIter(rep)
            await self.s.send(msg)
            res = await e.get()
            if res is not None:
                log("Spurious IterReply %r", res)
            return e
        else:
            self.reply[seq] = e = ValueEvent()
            try:
                await self.s.send(msg)
                return await e.get()
            finally:
                self.reply.pop(seq, None)


class SingleStreamCmd(StreamCmd):
    """A StreamCmd that disconnects on error, or when the connection ends."""
    async def run(self):
        try:
            await super().run()
        except Exception as exc:
            log("Err %s", self.path, err=exc)
        except BaseException:
            log("Err %s", self.path, err=exc)
            raise
        finally:
            await self._parent.detach(self._name)


"""
This module locally stores code that's been uploaded to DistKV 
so that it can be called easily.

"Code" consists of either Python modules or single procedures.

"""

import sys
import anyio
from collections import defaultdict, deque
from weakref import WeakValueDictionary
from time import time  # wall clock, intentionally
from functools import partial

from .util import PathLongener, make_module, make_proc, NotGiven
from .client import ClientRoot, ClientEntry

import logging

logger = logging.getLogger(__name__)


class EmptyCode(Exception):
    """
    There is no code here.
    """

    pass


class ModuleRoot(ClientRoot):
    """
    Modules are stored at ``(*PREFIX,*name)``.
    The prefix defaults to ``("code","module")``.

    The module code is stored textually. Content that is not UTF-8 is TODO.
    """

    CFG = "modules"

    err: "ErrorRoot" = None

    @classmethod
    def child_type(cls, name):
        return ModuleEntry

    async def run_starting(self):
        from .errors import ErrorRoot

        self.err = await ErrorRoot.as_handler(self.client)
        await super().run_starting()

    async def add(self, *path, code=None):
        """
        Add or replace this code at this location.
        """
        # test-compile the code for validity
        if code is None:
            return await self.remove(*path)

        make_module(code, *path)

        r = await self.client.set(*self._path, *path, value=dict(code=code), nchain=2)
        await self.wait_chain(r.chain)


class ModuleEntry(ClientEntry):
    @property
    def name(self):
        return ".".join(self.subpath)

    async def set_value(self, value):
        await super().set_value(value)
        if value is NotGiven:
            self._module = None
            try:
                del sys.modules[self.name]
            except KeyError:
                pass
            return

        try:
            c = self.value.code
            if not isinstance(c, str):
                raise RuntimeError("Not a string, cannot compile")
            m = make_module(c, *self.subpath)
        except Exception as exc:
            self._module = None
            logger.warn("Could not compile @%r", self.subpath)
            await self.root.err.record_exc(
                "compile",
                *self.subpath,
                exc=exc,
                reason="compilation",
                message="compiler error"
            )
        else:
            await self.root.err.record_working("compile", *self.subpath)
            self._module = m


class CodeRoot(ClientRoot):
    """
    This class represents the root of a code storage hierarchy. Ideally
    there should only be one, but you can configure more.

    You typically don't create this class directly; instead, call
    :meth:`CodeRoot.as_handler`::

        errs = await CodeRoot.as_handler(client, your_config.get("error-handler",{})                        

    The prefix defaults to ``("code","proc")``.

    Configuration:

    Arguments:
      prefix (list): Where to store the code in DtsiKV.
        The default is ``('.distkv','code','proc')``. 

    The code is stored as a dict.

    Arguments:
      code: the actual code to run. It is parsed as a function body; be
        aware that multi-line strings will be indented more than you'd like.
      async: flag whether the code should run asynchronously.
        True: yes, None (default): no, False: run in a separate thread.
      vars: array of names to be used as named arguments.

    All arguments are mandatory and should be named.
    Extra arguments will be available in the "kw" dict.

    """

    CFG = "codes"

    err = None

    @classmethod
    def child_type(cls, name):
        return CodeEntry

    async def run_starting(self):
        from .errors import ErrorRoot

        self.err = await ErrorRoot.as_handler(self.client)
        await super().run_starting()

    async def add(self, *path, code=None, is_async=None, vars=()):
        """
        Add or replace this code at this location.
        """
        if code is NotGiven:
            return await self.remove(*path)

        # test-compile the code for validity
        make_proc(code, vars, *path, use_async=is_async)

        r = await self.client.set(
            *(self._path + path),
            value=dict(code=code, is_async=is_async, vars=vars),
            nchain=2
        )
        await self.wait_chain(r.chain)

    async def remove(self, *path):
        """Drop this code"""
        r = await self.client.set(*self._path, *path, value=None, nchain=2)
        await self.wait_chain(r.chain)

    def __call__(self, name, *a, **kw):
        c = self
        for k in name.split("."):
            c = c[k]
        if c is self:
            raise RuntimeError("Empty code names don't make sense")
        return c(*a, **kw)


class CodeEntry(ClientEntry):
    _code = None
    is_async = None

    @property
    def name(self):
        return ".".join(self.subpath)

    async def set_value(self, value):
        await super().set_value(value)
        if value is NotGiven:
            self._code = None
            return

        try:
            v = self.value
            c = v["code"]
            a = v.get("is_async", None)
            p = make_proc(c, v.get("vars", ()), *self.subpath, use_async=a)
        except Exception as exc:
            logger.warning("Could not compile @%r", self.subpath)
            await self.root.err.record_exc(
                "compile",
                *self.subpath,
                exc=exc,
                reason="compilation",
                message="compiler error"
            )
            self._code = None
        else:
            await self.root.err.record_working("compile", *self.subpath)
            self._code = p
            self.is_async = a

    def __call__(self, *a, **kw):
        if self._code is None:
            raise EmptyCode(self._path)
        if self.is_async is False:
            proc = self._code
            if kw:
                proc = partial(proc, **kw)
            return anyio.run_in_thread(proc, *a, **kw)
        return self._code(*a, **kw)

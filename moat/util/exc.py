"""
Exception handling helpers
"""

from __future__ import annotations

from contextlib import contextmanager

__all__ = ["exc_iter", "ungroup"]


def exc_iter(exc):
    """
    iterate over all non-exceptiongroup parts of an exception(group)
    """
    if isinstance(exc, BaseExceptionGroup):
        for e in exc.exceptions:
            yield from exc_iter(e)
    else:
        yield exc

class ungroup:
    def __call__(self):
        return self
    def __enter__(self):
        return self
    async def __aenter__(self):
        return self

    def __exit__(self, c,e,t):
        if e is None:
            return
        while isinstance(e, BaseExceptionGroup):
            if len(e.exceptions) == 1:
                e = e.exceptions[0]
        raise e from None

    async def __aexit__(self, c,e,t):
        return self.__exit__(c,e,t)

ungroup = ungroup()

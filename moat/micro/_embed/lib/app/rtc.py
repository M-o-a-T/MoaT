import sys
from moat.util import NotGiven

from moat.micro.cmd.base import BaseCmd
from moat.micro.cmd.util import enc_part, get_part
from moat.micro.compat import log

class NotGiven2:
    pass

class Cmd(BaseCmd):
    """
    Subsystem to handle config data.

    This app serves the config of the parent subcommand.
    """
    def __init__(self, cfg):
        if cfg.get("fake",False):
            from moat.micro.test.rtc import state
        else:
            from moat.micro.rtc import state
        self.st = state

        super().__init__(cfg)

    async def cmd_r(self, p=()):
        """
        Read (part of) the RTC data area.

        As data are frequently too clunky to transmit in one go, this code
        interrogates the state step-by-step.

        @p is the path. An empty path is the root.

        If the accessed item is a dict, return data consists of a dict
        (simple keys and their values) and a list (keys for complex
        values).

        Same for a list.
        """
        return enc_part(get_part(self.st.data, p))

    async def cmd_w(self, p=(), d=NotGiven2):
        """
        Write (part of) the RTC data area.

        As data are frequently too large to transmit in one go, this code
        updates the state step-by-step.

        @p is the path. It cannot be empty. Destination dicts are
        autogenerated.

        @d is the data replacing the destination. ``NotGiven``
        deletes the setting. Not passing @d in deletes the modifier.
        """
        if not p:
            raise ValueError("NoPath")
        if d is NotGiven2:
            del self.st[p]
        else:
            self.st[p] = d

    async def cmd_x(self, p=()):
        """
        Activate the possibly-mangled config.

        WARNING this doesn't clear other local changes.
        """
        dest = self._parent
        if self.st.update(dest.cfg) is not dest.cfg:
            raise RuntimeError("must be updated inplace")
        await dest.reload()


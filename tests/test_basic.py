import pytest
import anyio
import trio
import mock
from time import time

from trio_click.testing import CliRunner
from .mock_serf import mock_serf_client
from .run import run

# This is a basic Trio test which we keep around to check that
# (a) the autojump clock works as advertised
# (b) we can use anyio.
@pytest.mark.trio
async def test_00_anyio_clock(autojump_clock):
    assert trio.current_time() == 0
    t = time()

    for i in range(10):
        start_time = trio.current_time()
        await anyio.sleep(i)
        end_time = trio.current_time()

        assert end_time - start_time == i
    assert time()-t < 1

@pytest.mark.trio
async def test_00_runner(autojump_clock):
    with mock.patch("aioserf.serf_client", new=mock_serf_client):
        with pytest.raises(AssertionError):
            await run('--doesnotexist')
        await run('--doesnotexist', expect_exit=2)
        #await run('pdb','pdb')  # used for verifying that debugging works


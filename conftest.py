import pytest
from mock import sentinel
import mock


class MockSock(object):

    def __init__(self, sequence):
        self.sequence = sequence

    AF_INET = sentinel.AF_INET
    SOCK_STREAM = sentinel.SOCK_STREAM

    def socket(self, arg1, arg2):
        assert arg1 is self.AF_INET
        assert arg2 is self.SOCK_STREAM
        return self

    def connect_ex(self, ip):
        next = self.sequence[0]
        if next is None:
            return -1  # Loop forever with None
        self.sequence = self.sequence[1:]
        return next


@pytest.fixture(scope="module")
def MockSocket(request):
    return MockSock


class MockTimeClass(object):
    def __init__(self):
        self.wallclock = 42

    def sleep(self, shift):
        self.wallclock += shift

    def time(self):
        self.wallclock += 1
        return self.wallclock


@pytest.fixture(scope="module")
def MockTime(request):
    return MockTimeClass


@pytest.fixture
def quick_commands(MockSocket, MockTime):
    def full_read(ignore_self, filename):
        return open(filename, 'rb', buffering=65536).read()
    from dibctl import commands
    with mock.patch.object(commands.prepare_os, "time", MockTime()):
        with mock.patch.object(commands.prepare_os, "socket", MockSocket([0])):
            with mock.patch.object(
                commands.prepare_os.uuid,
                "uuid4",
                return_value='deadbeaf-4078-11e7-8228-000000000000'
            ):
                with mock.patch.object(
                    commands.do_tests.prepare_os.osclient.OSClient,
                    '_file_to_upload',
                    full_read
                ):
                    yield commands

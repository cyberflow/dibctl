#!/usr/bin/python
import mock
import pytest
import os
import inspect
import sys
from mock import sentinel


@pytest.fixture
def pytest_runner():
    from dibctl import pytest_runner
    return pytest_runner


@pytest.fixture
def dcp(pytest_runner):
    tos = mock.MagicMock()
    tos.ip = '192.168.0.1'
    tos.os_instance.interface_list.return_value = [sentinel.iface1, sentinel.iface2]
    tos.flavor.return_value.get_keys.return_value = {'name':'value'}
    tos.key_name = 'foo-key-name'
    tos.os_key_private_file = 'private-file'
    tos.ips.return_value = [sentinel.ip1, sentinel.ip2]
    env = {
        'ssh_username': 'root'
    }
    dcp = pytest_runner.DibCtlPlugin(tos, env)
    return dcp

@pytest.mark.parametrize("code, status",[
    [0, True],
    [-1, False],
    [1, False]
])
def test_runner_status(pytest_runner, code, status):
    with mock.patch.object(pytest_runner, "DibCtlPlugin"):
        with mock.patch.object(pytest_runner.pytest, "main", return_value = code):
            assert pytest_runner.runner(
                sentinel.path,
                sentinel.tos,
                sentinel.environment_variables,
                sentinel.timeout_val,
                False,
            ) == status


def test_runner_status_cont_on_fail_true(pytest_runner):
    with mock.patch.object(pytest_runner, "DibCtlPlugin"):
        with mock.patch.object(pytest_runner.pytest, "main", return_value = -1) as mock_main:
            pytest_runner.runner(
                sentinel.path,
                sentinel.tos,
                sentinel.environment_variables,
                sentinel.timeout_val,
                False,
            )
        assert '-x' in mock_main.call_args[0][0]


def test_runner_status_cont_on_fail_false(pytest_runner):
    with mock.patch.object(pytest_runner, "DibCtlPlugin"):
        with mock.patch.object(pytest_runner.pytest, "main", return_value = -1) as mock_main:
            pytest_runner.runner(
                sentinel.path,
                sentinel.tos,
                sentinel.environment_variables,
                sentinel.timeout_val,
                True
            )
        assert '-x'  not in mock_main.call_args[0][0]


def test_DibCtlPlugin_init_trivial(dcp):
    assert dcp.testinfra
    assert dcp.env_vars['ssh_username'] == 'root'


def test_DibCtlPlugin_init_no_testinfra(pytest_runner):
    with mock.patch.dict(sys.modules, {'testinfra':None}):
        dcp = pytest_runner.DibCtlPlugin(
            mock.MagicMock(),
            {'ssh_username':'root'}
        )
        assert dcp.testinfra == None
        with pytest.raises(ImportError):
            dcp.ssh_backend(mock.MagicMock())


def test_DibCtlPlugin_flavor_fixture(dcp):
    assert dcp.flavor(sentinel.request)


def test_DibCtlPlugin_flavor_meta_fixture(dcp):
    assert dcp.flavor_meta(sentinel.request) == {'name':'value'}


def test_DibCtlPlugin_instance_fixture(dcp):
    assert dcp.instance(sentinel.request)


def test_DibCtlPlugin_network_fixture(dcp):
    assert dcp.network(sentinel.request) == [sentinel.iface1, sentinel.iface2]


def test_DibCtlPlugin_wait_for_port_fixture(dcp):
    dcp.wait_for_port(sentinel.request)()
    assert dcp.tos.wait_for_port.call_args == mock.call(22, 60)


def test_DibCtlPlugin_ssh_backend_fixture(dcp):
    be = dcp.ssh_backend(sentinel.request)
    assert be.hostname == '192.168.0.1'
    assert 'tmp' in be.ssh_config

@pytest.mark.parametrize('required', [
    'Host 192.168.0.1',
    'User root',
    'StrictHostKeyChecking no',
    'PasswordAuthentication no',
    'UpdateHostKeys no',
    'UserKnownHostsFile /dev/null',
    'IdentityFile private-file'
])
def test_DibCtlPlugin_create_ssh_config(pytest_runner, dcp, required):
    name = dcp.create_ssh_config()
    config = map(str.strip, open(name, 'r').readlines())
    assert required in config


def test_DibCtlPlugin_ips_v4_fixture(dcp):
    assert dcp.ips_v4(sentinel.request) == [sentinel.ip1, sentinel.ip2]


def test_DibCtlPlugin_main_ip_fixture(dcp):
    assert dcp.main_ip(sentinel.request) == '192.168.0.1'

@pytest.mark.parametrize('key, value',[
    ['ip', '192.168.0.1'],
    ['private_key_file', 'private-file'],
    ['key_name', 'foo-key-name'],
    ['username', 'root']
])
def test_DibCtlPlugin_ssh_fixture(dcp, key, value):
    ssh = dcp.ssh(sentinel.request)
    assert ssh[key] == value



def test_DibCtlPlugin_environemnt_variables_fixture(dcp):
    e = dcp.environment_variables(sentinel.request)
    assert e['ssh_username'] == 'root'


if __name__ == "__main__":
    ourfilename = os.path.abspath(inspect.getfile(inspect.currentframe()))
    currentdir = os.path.dirname(ourfilename)
    parentdir = os.path.dirname(currentdir)
    file_to_test = os.path.join(
        parentdir,
        os.path.basename(parentdir),
        os.path.basename(ourfilename).replace("test_", '', 1)
    )
    pytest.main([
     "-vv",
     "--cov", file_to_test,
     "--cov-report", "term-missing"
     ] + sys.argv)
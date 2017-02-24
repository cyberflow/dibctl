import tempfile
import subprocess
import sys


class SSH(object):

    COMMAND_NAME = 'ssh'

    def __init__(self, ip, username, private_key, port=22):
        self.ip = ip
        self.username = username
        self.private_key = private_key
        self.port = port
        self.private_key_file = None
        self.config_file = None

    def user_host_and_port(self):
        if self.port == 22:
            return self.username + '@' + self.ip
        else:
            return "{user}@{host}:{port}".format(
                user=self.username,
                host=self.ip,
                port=str(self.port)
            )

    def key_file(self):
        '''
            creates file with private ssh key
            file exists until instance of SSH class
            is removed.
            Returns filename of that file
        '''
        if not self.private_key_file:
            self.private_key_file = tempfile.NamedTemporaryFile(
                prefix='dibctl_key_',
            )
            self.private_key_file.write(self.private_key)
            self.private_key_file.flush()
        return self.private_key_file.name

    def verbatim_key_file(self):
        '''saves file in persistent way'''
        f = tempfile.NamedTemporaryFile(prefix='saved_dibctl_key_', delete=False)
        f.write(self.private_key)
        f.close()
        return f.name

    def command_line(self):
        command_line = [
            self.COMMAND_NAME,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "UpdateHostKeys=no",
            "-o", "PasswordAuthentication=no",
            "-i", self.key_file(),
            self.user_host_and_port()
        ]
        return command_line

    def connector(self):
        return 'ssh://%s' % self.ip

    def config(self):
        '''
            creates file with ssh configuration
            file exists until instance of SSH class
            is removed.
            Returns filename of that config
        '''
        if not self.config_file:
            self.config_file = tempfile.NamedTemporaryFile(prefix="dibctl_config_")
            self.config_file.write('# Automatically generated by dibctl\n\n')
            self.config_file.write('Host %s\n' % self.ip)
            self.config_file.write('\tUser %s\n' % self.username)
            self.config_file.write('\tStrictHostKeyChecking no\n')
            self.config_file.write('\tUserKnownHostsFile /dev/null\n')
            self.config_file.write('\tUpdateHostKeys no\n')
            self.config_file.write('\tPasswordAuthentication no\n')
            self.config_file.write('\tIdentityFile %s\n' % self.key_file())
            self.config_file.write('\tPort %s\n' % self.port)
            self.config_file.flush()
        return self.config_file.name

    def env_vars(self, prefix):
        '''
            return list of env vars related to SSH with
            given prefix
        '''
        result = {
            prefix + 'SSH_IP': self.ip,
            prefix + 'SSH_USERNAME': self.username,
            prefix + 'SSH_PORT': str(self.port),
            prefix + 'SSH_CONFIG': self.config(),
            prefix + 'SSH_PRIVATE_KEY': self.key_file(),
            prefix + 'SSH': ' '.join(self.command_line())
        }
        return result

    def shell(self, env, message):
        '''Opens a user-accessible shell to machine'''
        command_line = self.command_line()
        print(message)
        print("Executing shell: %s" % " ".join(command_line))
        return subprocess.call(command_line, stdin=sys.stdin, stderr=sys.stderr, stdout=sys.stdout, env=env)

    def info(self):
        result = {
            'ip': self.ip,
            'private_key_file': self.key_file(),
            'username': self.username,
            'port': self.port,
            'config': self.config(),
            'command_line': self.command_line(),
            'connector': self.connector()
        }
        return result

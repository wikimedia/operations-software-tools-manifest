import os
import time
import pwd
import subprocess


class Tool(object):
    USER_NAME_PATTERN = 'tools.%s'

    def __init__(self, name, username, uid, home):
        self.name = name
        self.uid = uid
        self.username = username
        self.home = home

    @classmethod
    def from_name(cls, name):
        """
        Create a Tool instance from a tool name
        """
        username = Tool.USER_NAME_PATTERN % (name, )
        user_info = pwd.getpwnam(username)
        return cls(name, user_info.pw_name, user_info.pw_uid, user_info.pw_dir)

    def log(self, message):
        """
        Write to a log file in the tool's homedir
        """
        # use ugly sudo and whatnot here instead of 'proper' file stuff because unsure how to
        # preserve permissions in atomic way when writing to a file that may not exist already
        log_line = "%s %s" % (time.asctime(), message)
        log_path = os.path.join(self.home, 'services.log')
        # Ensure that the file exists already and is owned appropriately by the tool
        subprocess.check_output([
            '/usr/bin/sudo',
            '-i', '-u', self.username,
            '/usr/bin/touch', log_path
        ])
        with open(log_path, 'a') as f:
            f.write(log_line)

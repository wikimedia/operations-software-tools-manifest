import os
import datetime
import pwd

from .utils import effective_user


class Tool(object):
    USER_NAME_PATTERN = 'tools.%s'

    class InvalidToolException(Exception):
        pass

    def __init__(self, name, username, uid, gid, home):
        self.name = name
        self.uid = uid
        self.gid = gid
        self.username = username
        self.home = home

    @classmethod
    def from_name(cls, name):
        """
        Create a Tool instance from a tool name
        """
        username = Tool.USER_NAME_PATTERN % (name, )
        try:
            user_info = pwd.getpwnam(username)
        except KeyError:
            # No such user was found
            raise Tool.InvalidToolException("No tool with name %s" % (name, ))
        if user_info.pw_uid < 50000:
            raise Tool.InvalidToolException("uid of tools should be < 50000, %s has uid %s" % (name, user_info.pw_uid))
        return cls(name, user_info.pw_name, user_info.pw_uid, user_info.pw_gid, user_info.pw_dir)

    def log(self, message):
        """
        Write to a log file in the tool's homedir
        """
        log_line = "%s %s" % (datetime.datetime.now().isoformat(), message)
        log_path = os.path.join(self.home, 'service.log')

        with effective_user(self.uid, self.gid):
            with open(log_path, 'a') as f:
                f.write(log_line + '\n')

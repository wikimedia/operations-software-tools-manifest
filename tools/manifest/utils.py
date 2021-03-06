from contextlib import contextmanager
import os


@contextmanager
def effective_user(uid, gid):
    """A ContextManager that executes code in the with block with effective
    uid / gid given
    """
    original_uid = os.geteuid()
    original_gid = os.getegid()
    os.setegid(gid)
    os.seteuid(uid)
    try:
        yield
    finally:
        os.setegid(original_gid)
        os.setuid(original_uid)

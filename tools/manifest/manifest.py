import yaml  # Just for pretty printing
import datetime


class Manifest(object):
    """A service manifest!"""
    class InvalidManifestException(Exception):
        pass

    def __init__(self, tool, data):
        """
        Constructs a manifest object from manifest data.

        It will ignore extra keys, but throw exceptions on invalid values.

        :param tool: tools.Tool Tool object representing the tool this is a manifest for
        :param data: dict containing manifest structure. Currently supported keys are:
                     web: Type of webservice to run for this tool. Currently supported
                          values are lighttpd, lighttpd-precise, nodejs, uwsgi-python, tomcat
        """
        if data is None:
            data = {}  # Handle empty service manifests
        self.data = data
        self.tool = tool
        self.start_times = []
        if 'version' in data:
            self.version = data['version']
        else:
            self.version = 1

    def record_starting(self):
        """
        Marks the manifest object as starting, recording the attempt.
        """
        self.start_times.append(datetime.datetime.utcnow())

    def record_running(self):
        """
        Marks the manifest object as known running, resetting the record
        of attempts to start it.
        """
        self.start_times = []

    def starting_too_frequently(self, count, window):
        """
        Returns true if the manifest object has been started at least 'count' times
        in the past 'window' seconds.
        """
        return len(self.start_times) >= count and \
            (datetime.datetime.utcnow()-self.start_times[-count]).total_seconds() < window

    @property
    def webservice_server(self):
        if 'web' in self.data:
            # Special case lighttpd-precise as long as we support it
            if self.version < 2 and self.data['web'].startswith('lighttpd'):
                return 'lighttpd'
            return self.data['web']
        return None

    @property
    def webservice_release(self):
        if 'web' in self.data:
            if self.data['web'].endswith('-precise'):
                return 'precise'
            return 'trusty'
        return None

    def __str__(self):
        # Because yaml always does stupid ordering, and we wouldn't want that would we
        return "tool: %s\n%s" % (
            self.tool.name,
            yaml.dump({'manifest': self.data}, default_flow_style=False)
        )

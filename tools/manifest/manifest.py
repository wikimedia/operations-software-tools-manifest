import datetime

import yaml


class Manifest(object):
    """A service manifest!"""
    class InvalidManifestException(Exception):
        pass

    def __init__(self, tool, data, start_times):
        """Constructs a manifest object from manifest data.

        :param tool: tools.Tool The tool this is a manifest for
        :param data: dict containing manifest structure
        """
        self.data = data or {}
        self.tool = tool
        self.start_times = start_times
        self.version = data.get('version', 1)

    def record_starting(self):
        """Marks the manifest object as starting, recording the attempt."""
        self.start_times.append(datetime.datetime.utcnow())

    def record_running(self):
        """Marks the manifest object as known running, resetting the record of
        attempts to start it.
        """
        self.start_times = []

    def starting_too_frequently(self, count, window):
        """Returns true if the manifest object has been started at least
        'count' times in the past 'window' seconds.
        """
        if len(self.start_times) >= count:
            now = datetime.datetime.utcnow()
            first = self.start_times[-count]
            if (now - first).total_seconds() < window:
                return True
        return False

    @property
    def webservice_server(self):
        return self.data.get('web', None)

    def __str__(self):
        return "tool: %s\n%s" % (
            self.tool.name,
            yaml.dump({'manifest': self.data}, default_flow_style=False)
        )

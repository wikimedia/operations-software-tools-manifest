import yaml  # Just for pretty printing


class Manifest(object):
    """A service manifest!"""
    WEBSERVICE_TYPES =('lighttpd', 'lighttpd-precise', 'nodejs', 'uwsgi-python', 'tomcat')

    class InvalidManifestException(Exception):
        pass

    def __init__(self, toolname, data):
        """
        Constructs a manifest object from manifest data.

        It will ignore extra keys, but throw exceptions on invalid values.

        :param toolname: str Name of tool for which this is the manifest
        :param data: dict containing manifest structure. Currently supported keys are:
                     web: Type of webservice to run for this tool. Currently supported
                          values are lighttpd, lighttpd-precise, nodejs, uwsgi-python, tomcat
        """
        if data is None:
            data = {}  # Handle empty service manifests
        self.data = data
        self.toolname = toolname

        if 'web' in data and data['web'] not in Manifest.WEBSERVICE_TYPES:
            raise Manifest.InvalidManifestException('webservice type should be one of %s', Manifest.WEBSERVICE_TYPES)


    @property
    def webservice_server(self):
        if 'web' in self.data:
            # Special case lighttpd-precise as long as we support it
            if self.data['web'].startswith('lighttpd'):
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
            self.toolname,
            yaml.dump({'manifest': self.data}, default_flow_style=False)
        )

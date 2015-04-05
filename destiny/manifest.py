class Manifest(object):
    """A service manifest!"""
    WEBSERVICE_TYPES =('lighttpd', 'lighttpd-precise', 'nodejs', 'uwsgi-python', 'tomcat')

    class InvalidManifestException(Exception):
        pass

    def __init__(self, data):
        """
        Constructs a manifest object from manifest data.

        It will ignore extra keys, but throw exceptions on invalid values.

        :param data: dict containing manifest structure. Currently supported keys are:
                     web: Type of webservice to run for this tool. Currently supported
                          values are lighttpd, lighttpd-precise, nodejs, uwsgi-python, tomcat
        """
        self.data = data

        if 'web' in data and data['web'] not in Manifest.WEBSERVICE_TYPES:
            raise Manifest.InvalidManifestException('webservice type should be one of %s', Manifest.WEBSERVICE_TYPES)

    @property
    def webservice_type(self):
        if 'web' in self.data:
            return self.data['web']
        else:
            return None

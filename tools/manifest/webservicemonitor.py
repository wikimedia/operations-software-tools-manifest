from urllib.request import urlopen
import collections
import datetime
import glob
import json
import logging
import os
import platform
import pwd
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import statsd
import yaml

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
        """Create a Tool instance from a tool name"""
        username = Tool.USER_NAME_PATTERN % (name, )
        try:
            user_info = pwd.getpwnam(username)
        except KeyError:
            # No such user was found
            raise Tool.InvalidToolException(
                "No tool with name %s" % (name, ))
        if user_info.pw_uid < 50000:
            raise Tool.InvalidToolException(
                "uid of tools should be < 50000, %s has uid %s" % (
                    name, user_info.pw_uid))
        return cls(
            name, user_info.pw_name, user_info.pw_uid,
            user_info.pw_gid, user_info.pw_dir)

    def log(self, message):
        """
        Write to a log file in the tool's homedir
        """
        log_line = "%s %s" % (datetime.datetime.now().isoformat(), message)
        log_path = os.path.join(self.home, 'service.log')

        with effective_user(self.uid, self.gid):
            try:
                with open(log_path, 'a') as f:
                    f.write(log_line + '\n')
            except OSError:
                # Don't blow up if the user has messed about and made the file
                # impossible to write to
                pass


class Manifest(object):
    """A service manifest!"""
    def __init__(self, tool, data):
        """Constructs a manifest object from manifest data.

        :param tool: tools.Tool The tool this is a manifest for
        :param data: dict containing manifest structure
        """
        self.data = data or {}
        self.tool = tool
        self.version = self.data.get('version', 1)

    @property
    def webservice_server(self):
        return self.data.get('web', None)

    def __str__(self):
        return "tool: %s\n%s" % (
            self.tool.name,
            yaml.dump({'manifest': self.data}, default_flow_style=False)
        )


class WebServiceMonitor(object):
    MANIFEST_GLOB_PATTERN = '/data/project/*/service.manifest'

    def __init__(
        self,
        statsd_host='labmon1001.eqiad.wmnet',
        statsd_prefix='tools',
        sleep=60,
        max_tool_restarts=3,
        restart_window=3600,
    ):
        self.sleep = sleep
        self.distribution = platform.linux_distribution()[0]
        self.manifests = []
        self.restarts = collections.defaultdict(list)
        self.max_tool_restarts = max_tool_restarts
        self.restart_window = restart_window

        # Setup logging
        self.log = logging.getLogger(
            "manifestcollector.%s" % self.__class__.__name__)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        self.log.addHandler(handler)
        self.log.setLevel(logging.DEBUG)

        # Setup statsd client
        self.stats = statsd.StatsClient(
            statsd_host, 8125, prefix=statsd_prefix)

    def collect(self):
        """Collect all service manifests by scanning the file system

        Attempts to protect against security issues (currently, only symlink
        redirection)
        """
        manifest_files = glob.glob(WebServiceMonitor.MANIFEST_GLOB_PATTERN)
        self.log.info(
            "Collecting manifests with pattern %s",
            WebServiceMonitor.MANIFEST_GLOB_PATTERN)
        manifests = []
        for manifest_file in manifest_files:
            fileparts = manifest_file.split('/')
            # FIXME: Have extra validation to make sure this *is* a tool
            toolname = fileparts[3]

            with open(manifest_file) as f:
                try:
                    tool = Tool.from_name(toolname)
                except Tool.InvalidToolException:
                    self.log.exception(
                        "Exception trying to validate / load tool %s",
                        toolname)
                    self.stats.incr('invalidtool')
                    continue
                # Support files only if the owner of the file is the tool
                # itself. This should be ok protection against symlinks to
                # random places, I think
                if os.fstat(f.fileno()).st_uid != tool.uid:
                    # Something is amiss, error and don't process this!
                    self.log.warn(
                        "Ignoring manifest for tool %s, suspicious ownership",
                        toolname)
                    self.stats.incr('suspiciousmanifest')
                    continue
                manifest = Manifest(tool, yaml.safe_load(f))
                manifests.append(manifest)
        self.manifests = manifests
        self.log.info("Collected %s manifests", len(self.manifests))
        self.stats.incr('manifestscollected', len(self.manifests))

    def _get_registered_webservices(self):
        with open('/etc/active-proxy') as f:
            active_proxy = f.read().strip()
        list_url = 'http://%s:8081/list' % active_proxy
        webservices_json = urlopen(list_url).read().decode('utf-8')
        return json.loads(webservices_json)

    def _start_webservice(self, manifest):
        self.log.info('Starting webservice for tool %s', manifest.tool.name)

        command = [
            '/usr/bin/sudo',
            '-i', '-u', manifest.tool.username,
            '/usr/bin/webservice',
            # Restart instead of start so they get restarted even if they are
            # running in zombie state
            'restart',
        ]
        self.restarts[manifest.tool.name].append(datetime.datetime.utcnow())
        try:
            subprocess.check_output(command, timeout=15)  # 15 second timeout!
            self.log.info('Started webservice for %s', manifest.tool.name)
            return True
        except subprocess.CalledProcessError as e:
            self.log.exception(
                'Could not start webservice for tool %s', manifest.tool.name)
            self.stats.incr('startfailed')
            manifest.tool.log(
                'Could not start webservice - '
                'webservice tool exited with error code %s' % e.returncode)
        except subprocess.TimeoutExpired:
            self.log.exception(
                'Timed out attempting to start webservice for tool %s',
                manifest.tool.name)
            self.stats.incr('startfailed')
            manifest.tool.log('Timed out attempting to start webservice (15s)')

    def run(self):
        qstat_xml = ET.fromstring(
            subprocess.check_output(['/usr/bin/qstat', '-u', '*', '-xml']))
        registered_webservices = self._get_registered_webservices()
        restarts_count = 0
        for manifest in self.manifests:
            if manifest.webservice_server is None:
                continue
            if manifest.data.get('backend', 'gridengine') != 'gridengine':
                continue

            distribution = manifest.data.get('distribution', 'Ubuntu')
            if distribution != self.distribution:
                # T212390: Do not try to run across grids
                continue

            job = qstat_xml.find(
                './/job_list[JB_name="%s-%s"]' % (
                    manifest.webservice_server, manifest.tool.name))
            running = False

            if job:
                state = job.findtext('.//state')
                for flag in ['r', 's', 'w', 'h']:
                    if flag in state:
                        running = True
                        break

            if manifest.tool.name not in registered_webservices or not running:
                # Start webservice at most three times in an hour
                history = self.restarts[manifest.tool.name]
                now = datetime.datetime.utcnow()
                if len(history) >= self.max_tool_restarts:
                    first = history[-self.max_tool_restarts]
                    if (now - first).total_seconds() < self.restart_window:
                        manifest.tool.log(
                            'Throttled for %s restarts in last %s seconds',
                            self.max_tool_restarts,
                            self.restart_window,
                        )
                        self.log.warn('Throttled %s', manifest.tool.name)
                        self.stats.incr('throttled')
                        continue

                try:
                    manifest.tool.log(
                        'No running webservice job found, '
                        'attempting to start it')
                    if self._start_webservice(manifest):
                        restarts_count += 1
                except Exception:
                    # More specific exceptions are already caught elsewhere,
                    # so this should catch the rest
                    self.log.exception(
                        'Starting webservice for tool %s failed',
                        manifest.tool.name)
                    self.stats.incr('startfailed')

        self.log.info(
            'Service monitor run completed, %s webservices restarted',
            restarts_count)
        self.stats.incr('startsuccess', restarts_count)

    def main(self):
        while True:
            self.collect()
            self.run()
            # Prune our memory of restart attempts so that we don't have an
            # unbounded collection leak that sneaks up on us after a long
            # period of stable operation.
            now = datetime.datetime.utcnow()
            for tool, history in self.restarts.items():
                self.restarts[tool] = [
                    ts for ts in history
                    if (now - ts).total_seconds() < self.restart_window
                ]
            time.sleep(self.sleep)


if __name__ == '__main__':
    sm = WebServiceMonitor()
    sm.main()

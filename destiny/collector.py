import sys
import os
import glob
import yaml
import logging
import statsd
import socket

from .manifest import Manifest
from .tool import Tool


class ManifestCollector(object):
    """Abstract class that collects a bunch of manifests and performs operations on them"""
    MANIFEST_GLOB_PATTERN = '/data/project/*/service.manifest'

    def __init__(self):
        self.manifests = []

        # Setup logging
        self.log = logging.getLogger("manifestcollector.%s" % self.__class__.__name__)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        self.log.addHandler(handler)
        self.log.setLevel(logging.DEBUG)

        # Setup statsd client
        statsd_prefix = 'tools.%s.%s' % (socket.gethostname(), self.__class__.__name__)
        self.stats = statsd.StatsClient('labmon1001.eqiad.wmnet', 8125, prefix=statsd_prefix)

    def collect(self):
        """
        Collect all service manifests by scanning the file system

        Attempts to protect against security issues (currently, only symlink redirection)
        """
        manifest_files = glob.glob(ManifestCollector.MANIFEST_GLOB_PATTERN)
        self.log.info("Collecting manifests with pattern %s", ManifestCollector.MANIFEST_GLOB_PATTERN)
        manifests = []
        for manifest_file in manifest_files:
            fileparts = manifest_file.split('/')
            toolname = fileparts[3]  # FIXME: Have extra validation to make sure this *is* a tool

            with open(manifest_file) as f:
                try:
                    tool = Tool.from_name(toolname)
                except Tool.InvalidToolException:
                    self.log.exception("Exception trying to validate / load tool %s" % (toolname, ))
                    self.stats.incr('invalidtool')
                    continue
                # Support files only if the owner of the file is the tool itself
                # This should be ok protection against symlinks to random places, I think
                if os.fstat(f.fileno()).st_uid != tool.uid:
                    # Something is amiss, error and don't process this!
                    self.log.warn("Ignoring manifest for tool %s, suspicious ownership", toolname)
                    self.stats.incr('suspiciousmanifest')
                    continue
                manifest = Manifest(tool, yaml.safe_load(f))
                manifests.append(manifest)
        self.manifests = manifests
        self.log.info("Collected %s manifests", len(self.manifests))
        self.stats.incr('manifestscollected', len(self.manifests))

    def run(self):
        """This must be overriden in child classes and actually perform operations on the manifest"""
        raise NotImplementedError("run method not overridden in child class")

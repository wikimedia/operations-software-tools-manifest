import sys
import os
import glob
import yaml
import logging

from .manifest import Manifest
from .tool import Tool


class ManifestCollector(object):
    """Abstract class that collects a bunch of manifests and performs operations on them"""
    MANIFEST_GLOB_PATTERN = '/data/project/*/service.manifest'

    def __init__(self):
        self.manifests = []
        self.log = logging.getLogger("manifestcollector.%s" % self.__class__.__name__)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        self.log.addHandler(handler)
        self.log.setLevel(logging.DEBUG)

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

            # protect against symlink attacks - support symlinks but only if target and source have same owner
            if os.path.islink(manifest_file):
                realpath = os.path.realpath(manifest_file)
                if os.stat(realpath).st_uid != os.stat(manifest_file).st_uid:
                    # Something is amiss, error and don't process this!
                    self.log.warn("Ignoring manifest for tool %s, suspicious symlink", toolname)
                    continue

            with open(manifest_file) as f:
                tool = Tool.from_name(toolname)
                manifest = Manifest(tool, yaml.safe_load(f))
                manifests.append(manifest)
        self.manifests = manifests
        self.log.info("Collected %s manifests", len(self.manifests))

    def run(self):
        """This must be overriden in child classes and actually perform operations on the manifest"""
        raise NotImplementedError("run method not overridden in child class")

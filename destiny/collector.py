import os
import glob
import yaml

from .manifest import Manifest


class ManifestCollector(object):
    """Abstract class that collects a bunch of manifests and performs operations on them"""
    MANIFEST_GLOB_PATTERN = '/data/project/*/service.manifest'

    def __init__(self):
        self.manifests = []

    def collect(self):
        """
        Collect all service manifests by scanning the file system

        Attempts to protect against security issues (currently, only symlink redirection)
        """
        manifest_files = glob.glob(ManifestCollector.MANIFEST_GLOB_PATTERN)
        for manifest_file in manifest_files:
            # protect against symlink attacks - support symlinks but only if target and source have same owner
            if os.path.islink(manifest_file):
                realpath = os.path.realpath(manifest_file)
                if os.stat(realpath).st_uid != os.stat(manifest_file).st_uid:
                    # Something is amiss, error and don't process this!
                    continue
            with open(manifest_file) as f:
                fileparts = manifest_file.split('/')
                toolname = fileparts[3]  # FIXME: Have extra validation to make sure this *is* a tool
                manifest = Manifest(toolname, yaml.load(f))
                self.manifests.append(manifest)

    def run(self):
        """This must be overriden in child classes and actually perform operations on the manifest"""
        raise NotImplementedError("run method not overridden in child class")

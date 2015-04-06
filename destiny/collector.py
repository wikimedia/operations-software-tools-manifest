import sys
import os
import glob
import yaml
import logging
import time
import subprocess


from .manifest import Manifest


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

    def toollog(self, toolname, message):
        """
        Write to a log file in the tool's homedir
        :param toolname: validated tool name on whose homedir to write log in
        """
        # use ugly sudo and whatnot here instead of 'proper' file stuff because unsure how to
        # preserve permissions in atomic way when writing to a file that may not exist already
        log_line = "%s %s" % (time.asctime(), message)
        log_path = '/data/project/%s/services.log' % toolname
        # Ensure that the file exists already and is owned appropriately by the tool
        subprocess.check_output([
            '/usr/bin/sudo',
            '-i', '-u', 'tools.%s' % toolname,
            '/usr/bin/touch', log_path
        ])
        with open(log_path, 'w') as f:
            f.write(log_line)
            self.log.info('[%s] %s', toolname, message)

    def collect(self):
        """
        Collect all service manifests by scanning the file system

        Attempts to protect against security issues (currently, only symlink redirection)
        """
        manifest_files = glob.glob(ManifestCollector.MANIFEST_GLOB_PATTERN)
        self.log.info("Collecting manifests with pattern %s", ManifestCollector.MANIFEST_GLOB_PATTERN)
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
                manifest = Manifest(toolname, yaml.safe_load(f))
                self.manifests.append(manifest)
        self.log.info("Collected %s manifests", len(self.manifests))

    def run(self):
        """This must be overriden in child classes and actually perform operations on the manifest"""
        raise NotImplementedError("run method not overridden in child class")

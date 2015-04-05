import glob
import yaml

from .manifest import Manifest

manifest_files = glob.glob('/data/project/*/service.manifest')

for manifest_file in manifest_files:
    with open(manifest_file) as f:
        manifest = Manifest(yaml.load(f))
        print(manifest.webservice_type)

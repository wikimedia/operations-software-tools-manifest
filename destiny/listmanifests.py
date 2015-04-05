from .collector import ManifestCollector


class ListManifests(ManifestCollector):
    def run(self):
        for manifest in self.manifests:
            print(manifest)


if __name__ == '__main__':
    lister = ListManifests()
    lister.collect()
    lister.run()

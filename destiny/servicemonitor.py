import subprocess


from .collector import ManifestCollector
import xml.etree.ElementTree as ET


class ServiceMonitor(ManifestCollector):
    def _webjob_name(self, manifest):
        return '%s-%s' % (manifest.webservice_server, manifest.toolname)

    def _start_webservice(self, manifest):
        return subprocess.check_output([
            '/usr/bin/sudo',
            '-i', '-u', 'tools.%s' % manifest.toolname,
            '/usr/local/bin/webservice',
            '--release', manifest.webservice_release,
            manifest.webservice_server,
            'start',
        ])

    def run(self):
        qstat_xml = ET.fromstring(subprocess.check_output(['/usr/bin/qstat', '-u', '*', '-xml']))
        for manifest in self.manifests:
            if manifest.webservice_server is None:
                continue
            job = qstat_xml.find('.//job_list[JB_name="%s"]' % self._webjob_name(manifest))
            if job is None or 'r' not in job.findtext('.//state'):
                self._start_webservice(manifest)
            else:
                # All good
                print("%s all good" % manifest.toolname)


if __name__ == '__main__':
    sm = ServiceMonitor()
    sm.collect()
    sm.run()

import subprocess


from .collector import ManifestCollector
import xml.etree.ElementTree as ET


class ServiceMonitor(ManifestCollector):
    def _webjob_name(self, manifest):
        return '%s-%s' % (manifest.webservice_server, manifest.tool.name)

    def _start_webservice(self, manifest):
        self.log.info('Starting webservice for tool %s', manifest.tool.name)
        try:
            subprocess.check_output([
                '/usr/bin/sudo',
                '-i', '-u', manifest.tool.username,
                '/usr/local/bin/webservice',
                '--release', manifest.webservice_release,
                manifest.webservice_server,
                'start',
            ], timeout=15)  # 15 second timeout!
            self.log.info('Started webservice for %s', manifest.tool.name)
            return True
        except subprocess.CalledProcessError as e:
            self.log.exception('Could not start webservice for tool %s', manifest.tool.name)
            self.stats.incr('webservice_startfailed')
            manifest.tool.log('Could not start webservice - webservice tool exited with error code %s' % e.returncode)
        except subprocess.TimeoutExpired:
            self.log.exception('Timed out attempting to start webservice for tool %s', manifest.tool.name)
            self.stats.incr('webservice_startfailed')
            manifest.tool.log('Timed out attempting to start webservice (15s)')

    def run(self):
        qstat_xml = ET.fromstring(subprocess.check_output(['/usr/bin/qstat', '-u', '*', '-xml']))
        restarts_count = 0
        for manifest in self.manifests:
            if manifest.webservice_server is None:
                continue
            job = qstat_xml.find('.//job_list[JB_name="%s"]' % self._webjob_name(manifest))
            if job is None or 'r' not in job.findtext('.//state'):
                manifest.tool.log('No running webservice job found, starting it')
                if self._start_webservice(manifest):
                    restarts_count += 1
        self.log.info('Service monitor run completed, %s webservices restarted', restarts_count)
        self.stats.incr('webservices_restarted', restarts_count)


if __name__ == '__main__':
    sm = ServiceMonitor()
    sm.collect()
    sm.run()

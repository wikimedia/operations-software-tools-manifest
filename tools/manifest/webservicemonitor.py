import subprocess
import json
from urllib.request import urlopen
import xml.etree.ElementTree as ET

from .collector import ManifestCollector


class WebServiceMonitor(ManifestCollector):
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
            '/usr/bin/webservice'
        ]
        # Restart instead of start so they get restarted even if they are running in zombie state
        command.append('restart')
        manifest.record_starting()
        try:
            subprocess.check_output(command, timeout=15)  # 15 second timeout!
            self.log.info('Started webservice for %s', manifest.tool.name)
            return True
        except subprocess.CalledProcessError as e:
            self.log.exception('Could not start webservice for tool %s', manifest.tool.name)
            self.stats.incr('startfailed')
            manifest.tool.log('Could not start webservice - webservice tool exited with error code %s' % e.returncode)
        except subprocess.TimeoutExpired:
            self.log.exception('Timed out attempting to start webservice for tool %s', manifest.tool.name)
            self.stats.incr('startfailed')
            manifest.tool.log('Timed out attempting to start webservice (15s)')

    def run(self):
        qstat_xml = ET.fromstring(subprocess.check_output(['/usr/bin/qstat', '-u', '*', '-xml']))
        registered_webservices = self._get_registered_webservices()
        restarts_count = 0
        for manifest in self.manifests:
            if manifest.webservice_server is None:
                continue
            if manifest.data.get('backend', 'gridengine') != 'gridengine':
                continue
            if manifest.data.get('distribution', 'Ubuntu') != self.distribution:
                # T212390: Do not try to run across grids
                continue
            job = qstat_xml.find('.//job_list[JB_name="%s-%s"]' % (manifest.webservice_server, manifest.tool.name))
            running = False

            if job:
                state = job.findtext('.//state')
                if 'r' in state or 's' in state:
                    running = True
                    manifest.record_running()
                if 'w' in state or 'h' in state:
                    running = True

            if manifest.tool.name not in registered_webservices or not running:

                # Start webservice at most three times in an hour
                if manifest.starting_too_frequently(3, 3600):
                    manifest.tool.log('Tool %s starting to frequently - throttled' % manifest.tool.name)
                    continue

                try:
                    manifest.tool.log('No running webservice job found, attempting to start it')
                    if self._start_webservice(manifest):
                        restarts_count += 1
                except Exception:
                    # More specific exceptions are already caught elsewhere, so this should catch the rest
                    self.log.exception('Starting webservice for tool %s failed', manifest.tool.name)
                    self.stats.incr('startfailed')

        self.log.info('Service monitor run completed, %s webservices restarted', restarts_count)
        self.stats.incr('startsuccess', restarts_count)


if __name__ == '__main__':
    sm = WebServiceMonitor()
    sm.collect()
    sm.run()

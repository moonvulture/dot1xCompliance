# simple_ping_test.py

from pyats import aetest
import re
from unicon.core.errors import SubCommandFailure
from pyats.log.utils import banner

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_device(self, testbed):
        # Adjust device name as needed
        device = testbed.devices['Cat8K']
        device.connect(log_stdout=False)
        self.parent.parameters['device'] = device

class PingTestcase(aetest.Testcase):
    @aetest.test
    def ping_google(self):
        device = self.parameters['device']
        destination = '8.8.8.8'
        try:
            result = device.ping('8.8.8.8')
        except SubCommandFailure as e:
            # You can log or print details here
            self.failed(f"Ping to {destination} failed with error: {e}")
            return

        print(banner(f"Ping Output:\n{result}"))
        match = re.search(r'Success rate is (\d+) percent', result)
        if not match or int(match.group(1)) == 0:
            self.failed(f'Ping to {destination} failed or success rate was 0%')
        else:
            self.passed(f'Ping to 8.8.8.8 succeeded with {match.group(1)}% success rate')

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_device(self):
        device = self.parent.parameters.get('device')
        if device:
            device.disconnect()

if __name__ == '__main__':
    import argparse
    from pyats.topology import loader

    parser = argparse.ArgumentParser()
    parser.add_argument('--testbed', dest='testbed', type=loader.load)
    args, unknown = parser.parse_known_args()
    aetest.main(**vars(args))
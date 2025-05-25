import json
from pyats.topology import loader

# Load the testbed
testbed = loader.load('testbed.yml')

# Access the device by name
device = testbed.devices['Cat8K']

# Connect to the device
device.connect(log_stdout=False)

# Run a command
parsed = device.parse('show ip interface brief')
print(json.dumps(parsed, indent=2))

for intf, data in parsed['interface'].items():
    print(f"{intf}: {data.get('ip_address')} ({data.get('status')})")
from ttp import ttp

# Load your config as a string
with open('switch.cfg') as f:
    config_data = f.read()

# Load your TTP template as a string
with open('dot1x.ttp') as f:
    ttp_template = f.read()

# Parse the config
parser = ttp(data=config_data, template=ttp_template)
parser.parse()
results = parser.result()[0][0]['interfaces']

# Check for dot1x on each interface
for intf in results:
    has_dot1x = any('authentication port-control auto' in cmd for cmd in intf['command'])
    print(f"{intf['interface']}: {'dot1x enabled' if has_dot1x else 'dot1x NOT enabled'}")
import json
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
print(json.dumps(results))
# Check for dot1x on each interface
for intf in results:
    if intf.get('access'):
        dot1x_enabled = 'dot1x' in intf
        print(f"{intf['interface']}: access port, dot1x {'ENABLED' if dot1x_enabled else 'NOT enabled'}")
    else:
        print(f"{intf['interface']}: not access port")
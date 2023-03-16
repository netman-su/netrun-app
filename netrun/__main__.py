import argparse
from netrun import netrun

netrun = netrun()

function_map = {
    "file": netrun.scan_file,
    "scan": netrun.scan
}

parser = argparse.ArgumentParser(description='Run the netrun script')
parser.add_argument('-file', metavar=('[file_path]'), type=str, nargs=1, help='Scan against nodes in a csv. Used for quick additions of nodes.', required=False)
parser.add_argument('-scan', metavar=('[ip]', '[device_type]', '[track]'), type=str, nargs=3, help='Add a node or perform a scan on a specific node. Format is IP, device type and tracking status.', required=False)

args = parser.parse_args()

if all(value is None for value in vars(args).values()):
    netrun.scan()
else:
    for argument_name, argument_value in vars(args).items():
        if argument_value == None:
            continue
        for i, item in enumerate(argument_value):
            if item.lower() == "true":
                argument_value[i] = True
            if item.lower() == "false":
                argument_value[i] = False
        function = function_map.get(argument_name)
        fart = function(*argument_value)
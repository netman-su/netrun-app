import argparse
from netrun import netrun

netrun = netrun()

function_map = {
    "file": netrun.scan_file,
    "ip": netrun.scan
}

parser = argparse.ArgumentParser(description='Run the netrun script')
parser.add_argument('-file', metavar='<file_path>', type=str, nargs=1, help='Scan against nodes in a csv. Used for quick additions of nodes.', required=False)
parser.add_argument('-ip', metavar='<ip>', type=str, nargs=1, help='IP address to scan', required=False)

args = parser.parse_args()

if not any(vars(args).values()):
    netrun.scan()
else:
    for argument_name, argument_value in vars(args).items():
        if not argument_value:
            continue
        for i, item in enumerate(argument_value):
            if item.lower() == "true":
                argument_value[i] = True
            if item.lower() == "false":
                argument_value[i] = False
        function = function_map.get(argument_name)
        function(*argument_value)


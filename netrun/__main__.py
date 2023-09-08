import json
import argparse
import logging
from netrun import netrun
from utils.database import operations

netrun = netrun()

function_map = {
    "file": netrun.scan_file,
    "ip": netrun.scan,
    "get": lambda value:  print(operations.main_get(value)),
    "report": operations.main_report
}

parser = argparse.ArgumentParser(description='If no option is supplied, netrun deploys against all known nodes.')
parser.add_argument('-file', metavar='<file_path>', type=str, nargs=1, help='Scan against nodes in a CSV for quick additions of nodes.', required=False)
parser.add_argument('-ip', metavar='<ip>', type=str, nargs=1, help='Deploy netrun against a specific IP.', required=False)
parser.add_argument('-get', metavar='<value>', type=str, nargs=1, help='Return a node based on a given search term.', required=False)
parser.add_argument('-report', action='store_true', help='Generate a version report for each node.')

args = parser.parse_args()

if args.report:
    print(operations.main_report())
elif not any(vars(args).values()):
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
        if function:
            function(*argument_value)
        else:
            print(f"Function '{argument_name}' is not available.")
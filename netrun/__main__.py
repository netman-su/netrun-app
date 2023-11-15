import argparse
import netrun
from netrun.subsystems.database import operations

engine = netrun.engine()
database = netrun.database()

function_map = {
    "file": engine.scan_file,
    "ip": engine.scan,
    "get": lambda value:  print(database.main_get(value)),
    "report": database.main_report
}

parser = argparse.ArgumentParser(description='If no option is supplied, netrun deploys against all known nodes.')
parser.add_argument('-file', metavar='<file_path>', type=str, nargs=1, help='Scan against nodes in a CSV for quick additions of nodes.', required=False)
parser.add_argument('-ip', metavar='<ip>', type=str, nargs=1, help='Deploy netrun against a specific IP.', required=False)
parser.add_argument('-get', metavar='<value>', type=str, nargs=1, help='Return a node based on a given search term.', required=False)
parser.add_argument('-report', action='store_true', help='Generate a version report for each node.')

args = parser.parse_args()

if args.report:
    print(database.main_report())
elif not any(vars(args).values()):
    engine.scan()
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
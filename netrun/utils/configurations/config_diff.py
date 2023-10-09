from utils.database import operations
import re
from collections import namedtuple
from queue import Queue

class Compare(object):
    REGEX_METACHARACTERS = [".", "^", "$", "*", "+", "?", "{", "}", "[", "]", "\\", "|", "(", ")"]
    DELIMITER = r'{{[^{}]+}}'
    DELIMITER_START = '{{'
    DELIMITER_END = '}}'

    def __init__(self, baseline, comparison, ignore_lines=None, interface_re=None):
        """Initialize a diffios.Compare object with a baseline,
            a comparison and lines to ignore.

        Args:
            baseline (str|list|diffios.Config): Path to baseline
                config file, list containing lines of config,
                or diffios.Config object
            comparison (str|list|diffios.Config): Path to comparison
                config file, list containing lines of config,
                or diffios.Config object

        Kwargs:
            ignore_lines (str|list): Path to ignores file, or list
                containing lines to ignore. Defaults to ignores
                file in current working directory if it exists.

        """
        self._baseline = baseline
        self._comparison = comparison
        self._ignore_lines = ignore_lines

        self._interface_re = interface_re or re.compile(r"interface ([A-Za-z]+)((\S)+)")

        if isinstance(self._baseline, Config_Handler):
            self.baseline = self._baseline
        else:
            self.baseline = Config_Handler(self._baseline, self._ignore_lines, self._interface_re)
        if isinstance(self._comparison, Config_Handler):
            self.comparison = self._comparison
        else:
            self.comparison = Config_Handler(self._comparison, self._ignore_lines, self._interface_re)
            
        if self.baseline and self.comparison:
            self.ignore_lines = self.baseline.ignore_lines

    @staticmethod
    def _compare_lines(target, guess):
        delimiter_pattern = r'\{\{[^{}]*\}\}'
        target_replaced = re.sub(delimiter_pattern, '', target)
        target_sections = target_replaced.split()
        guess_sections = guess.split()

        # If any section in target is not in its equivalent place in guess, return False
        for i in range(min(len(target_sections), len(guess_sections))):
            if target_sections[i] and target_sections[i] != guess_sections[i]:
                return False

        return True

    def _baseline_queue(self):
        bq = Queue()
        [bq.put(el) for el in self.baseline.included()]
        return bq

    def _comparison_hash(self):
        return {group[0]: group[1:] for group in self.comparison.included()}

    @staticmethod
    def _child_lookup(baseline_parent, baseline_children, comparison_children):
        ChildComparison = namedtuple('ChildComparison', 'additional missing')
        missing = []
        for baseline_child in baseline_children:
            if baseline_child not in comparison_children and not missing:
                missing.append(baseline_parent)
                missing.append(baseline_child)
            elif baseline_child not in comparison_children:
                missing.append(baseline_child)
            elif baseline_child in comparison_children:
                comparison_children.remove(baseline_child)
        if comparison_children:
            additional = [baseline_parent] + comparison_children
        else:
            additional = []
        return ChildComparison(additional, missing)

    def _child_search(self, target_children, comparison_children):
        ChildComparison = namedtuple('ChildComparison', 'additional missing')
        missing = []
        while target_children:
            child_target = target_children.pop()
            child_search = self._binary_search(child_target,
                                               comparison_children)
            if child_search:
                comparison_children.remove(child_search)
            else:
                missing.append(child_target)
        return ChildComparison(comparison_children, sorted(missing))

    def _binary_search(self, target, search_array):
        if not search_array:
            return None
        sorted_array = sorted(search_array)
        low = 0
        high = len(sorted_array) - 1
        while low <= high:
            mid = (high + low) // 2
            guess = sorted_array[mid]
            compare_lines = self._compare_lines(target, guess)
            if compare_lines:
                return guess
            if target < guess:
                high = mid - 1
            else:
                low = mid + 1
        return None

    def _hash_lookup(self, baseline, comparison):
        missing, additional, with_vars = [], [], []
        while not baseline.empty():
            baseline_group = baseline.get()
            baseline_parent = baseline_group[0]
            baseline_children = baseline_group[1:]
            baseline_family = ' '.join(baseline_group)
            if self.DELIMITER_START in baseline_family:
                with_vars.append(baseline_group)
            else:
                comparison_children = comparison.pop(baseline_parent, -1)
                if comparison_children == -1:
                    missing.append(baseline_group)
                elif comparison_children:
                    child_lookup = self._child_lookup(baseline_parent,
                                                      baseline_children,
                                                      comparison_children)
                    if child_lookup.additional:
                        additional.append(child_lookup.additional)
                    if child_lookup.missing:
                        missing.append(child_lookup.missing)
        return (missing, additional, with_vars)

    def _with_vars_search(self, with_vars, comparison, missing, additional):
        while with_vars:
            target = with_vars.pop()
            target_parent = target[0]
            target_children = sorted(target[1:])
            parent_search = self._binary_search(target_parent,
                                                comparison.keys())
            if parent_search:
                comparison_children = sorted(comparison.pop(parent_search))
                child_search = self._child_search(target_children,
                                                  comparison_children)
                if child_search.additional:
                    additional.append([parent_search] +
                                      child_search.additional)
                if child_search.missing:
                    missing.append([target_parent] + child_search.missing)
            else:
                missing.append(target)
        return (missing, additional)

    def _search(self):
        baseline = self._baseline_queue()
        comparison = self._comparison_hash()
        missing, additional, with_vars = self._hash_lookup(baseline,
                                                           comparison)
        missing, additional = self._with_vars_search(with_vars, comparison,
                                                     missing, additional)
        additional = sorted([[k] + v
                             for k, v in comparison.items()] + additional)
        return {'missing': missing, 'additional': additional}

    def additional(self):
        """Lines in the comparison config not present in baseline config.

        Due to the hierarchical nature of Cisco configs,
        lines can be grouped with a parent and it's children.
        Therefore when child lines are additional their parent line
        will also be included here, whether they themselves are
        additional or not, so as to give context for the child line,
        specifying which grouping they belong to.

        Example Group:
            interface FastEthernet0/1               # Parent
             ip address 192.168.0.1 255.255.255.0   # Child
             no shutdown                            # Child

        Returns:
            list: Sorted lines additional to the comparison config.

        """
        return sorted(self._search()['additional'])

    def missing(self):
        """Lines in the baseline config not present in comparison config.

        Due to the hierarchical nature of Cisco configs,
        lines can be grouped with a parent and it's children.
        Therefore when child lines are missing their parent line
        will also be included here, whether they themselves are
        missing or not, so as to give context for the child line,
        specifying which grouping they belong to.

        Example Group:
            interface FastEthernet0/1               # Parent
             ip address 192.168.0.1 255.255.255.0   # Child
             no shutdown                            # Child

        Returns:
            list: Sorted lines missing from the comparison config.

        """
        return sorted(self._search()['missing'])

class Config_Handler:
    def __init__(self, config, ignore_lines=None, interface_re=None):
        self.config = self._check_data('config', config)
        if ignore_lines is None:
            ignore_lines = []
        self.ignore_lines = self._ignore(self._check_data('ignore_lines', ignore_lines))
        self.interface_re = interface_re or re.compile(r"interface ([A-Za-z]+)((\S)+)")

    def _valid_config(self):
        return [l.rstrip() for l in self.config if self._valid_line(l)]

    def _group_config(self):
        current_group, groups = [], []
        interface_matched = False
        for line in self._valid_config():
            matched = self.interface_re.match(line) if not line.startswith(' ') else None
            if matched:
                # If line matches to the 'interface_re', then this line is treated as interface starting line
                if current_group:
                    # If 'current_group' is not empty, then it should be added to 'groups'
                    groups.append(current_group)
                line = matched.group(1)  # Replace 'line' with matched group item
                current_group = [line]   # Start new group with this interface line
                interface_matched = True
            elif not line.startswith(' '):
                # For Non-interface lines
                if current_group:
                    # If 'current_group' is not empty, then it should be added to 'groups'
                    groups.append(current_group)
                current_group = [line]   # Start new group with this line
                interface_matched = False
            elif line.startswith(' '):
                if interface_matched:
                    # If previous line was interface line, add the subsequent indented lines to the current interface group
                    current_group.append(line)
        if current_group:
            groups.append(current_group)
        return sorted(groups)

    def _partition_group(self, group):
        Partition = namedtuple("Partition", "ignored included")
        ignored, included = [], []
        for i, line in enumerate(group):
            if self._ignore_line(line) and i == 0:
                return Partition(group, included)
            elif self._ignore_line(line):
                ignored.append(line)
            else:
                included.append(line)
        return Partition(ignored, included)

    def _partition_config(self):
        Partition = namedtuple("Partition", "ignored included")
        included, ignored = [], []
        for group in self._group_config():
            partition = self._partition_group(group)
            if partition.included:
                included.append(partition.included)
            if partition.ignored:
                ignored.append(partition.ignored)
        return Partition(ignored, included)

    def included(self):
        """Lines from the original config that are not ignored. """
        return self._partition_config().included

    def ignored(self):
        """Lines from the original config that are ignored. """
        return self._partition_config().ignored

    @staticmethod
    def _ignore(ignore):
        return [line.strip().lower() for line in ignore]

    @staticmethod
    def _check_data(name, data):
        invalid_arg = "Config_Handler() received an invalid argument: {}={}\n"
        unable_to_open = "Config_Handler() could not open '{}'"
        if isinstance(data, list):
            return data
        try:
            with open(data) as fin:
                return fin.read().splitlines()  # remove '\n' from lines
        except IOError:
            raise RuntimeError((unable_to_open.format(data)))
        except:
            raise RuntimeError(invalid_arg.format(name, data))

    @staticmethod
    def _valid_line(line):
        line = line.strip()
        return len(line) > 0 and not line.startswith("!") and line != '^' and line != '^C'

    def _ignore_line(self, line):
        for line_to_ignore in self.ignore_lines:
            for metacharacter in "\\ .^$*+?{}[]|()":  # This should remain constant as these are python's regex metacharacters. 
                if metacharacter in line_to_ignore:
                    line_to_ignore = line_to_ignore.replace(
                        metacharacter, '\\{}'.format(metacharacter))
            if re.search(line_to_ignore, line.lower()):
                return True
        return False

# model = 'C9300-48UN'
# net_obj = operations.main_get(model)
# net_list = []

# baseline_file = f"netrun\\utils\\configurations\\baselines\\{model}\\{model}.txt"
# output_file_path = f"netrun\\utils\\configurations\\results\\{model}\\baseline_vs_{{}}.txt"

# # get baseline
# with open(baseline_file, "r") as file:
#     baseline = file.readlines()

# for device in net_obj:
#     compare_dict = {'additional': [], 'missing': []}
#     decoded_config = operations.decompress_config(device['configuration'])
#     compare_obj = Compare(baseline, decoded_config.splitlines(), ignore_lines=f'netrun\\utils\\configurations\\baselines\\{model}\\ignore.txt')
#     missing_config = compare_obj.missing()
#     additional_config = compare_obj.additional()
#     for each in additional_config:
#         compare_dict['additional'].append(each)
#     for each in missing_config:
#         compare_dict['missing'].append(each)
    
#     print(compare_dict)
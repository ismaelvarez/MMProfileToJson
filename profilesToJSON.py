import argparse
import os
import json

HEIGHT = 'height'

WIDTH = "width"

TYPE_ = "type"

JSON_LOCATION = "."

DEVICE_LIST = ""
MODE = ""

HEADER_MARKER = "[ Header"

MAGNITUDE_MARKER = "[ Magnitude "

MONITOR_PROPERTIES = ["upper_limit", "lower_limit", "default_sampling_period", "default_storage_period"]

# Config

CONFIG = {
    "remove-time-unit": [],
    "remove-white-spaces": [],
    "remove-line-feed": []
}

CONFIG_PARSER = {
    "remove-time-unit": lambda s: s[:-1],
    "remove-white-spaces": lambda s: s.replace(" ", ""),
    "remove-line-feed": lambda s: s.replace("\\", "")
}


def to_double(item):
    try:
        return str(float(item))
    except ValueError:
        return item

# Property name - Lambda function to parse
MAGNITUDE_PROPERTIES = [
    ["description", None],
    ["units", None],
    ["type", None],
    ["upper_limit", None],
    ["lower_limit", None],
    ["default_sampling_period", to_double],
    ["default_storage_period", to_double]
]

LIMITS = ['upper_limit', 'lower_limit']

SPECIAL_CHARACTERS = ['\t', '\\', '\n']


# Search index of word in the array
def get_index_of(word, array, from_idx=0):
    for line in array[from_idx:]:
        if word in line:
            return array.index(line, from_idx)
    return -1


# Parse the header section of the profile
def profile_header_parser(lines):
    idx = get_index_of(HEADER_MARKER, lines)
    begin = lines[idx + 1].find('=')
    instance = lines[idx + 1][begin + 1:-1].strip()
    begin = lines[idx + 2].find('=')
    class_names = lines[idx + 2][begin + 1:-1].strip().split(",")
    class_name = class_names[0]
    return instance, class_name


# Check if the limit format is valid (arrays): [ 0.0, 0.0 ; 0.0, 0.0 ]
def check_limit_format(value, width, height=0):
    limit = value.replace("[", "").replace("]", "").strip()

    if height > 0:
        first_dimension = limit.split(";")
        if len(first_dimension) < height:
            return False

        for dimension in first_dimension:
            second = dimension.split(",")
            if len(second) < width:
                return False
    else:
        first_dimension = limit.split(",")

        # If dimensions are wrong in profiles, return true
        if len(first_dimension) > width:
            return True

        if len(first_dimension) != width:
            return False
    return True


# Expand the limits if only contains one value for all the elements of the array
def expand_limit(limit, width, height):
    value = float(limit.replace("[", "").replace("]", "").split(",")[0].strip())
    expanded_limit = ""
    if height > 0:
        for j in range(height):
            for i in range(width):
                expanded_limit += str(value) + ","
            expanded_limit = expanded_limit[:-1] + ";"
    return "[" + expanded_limit[:-1] + "]"


def limit_to_double(limit):
    limit = limit.replace("[", "").replace("]", "").strip()
    value = ""
    if limit.find(";") > 0:
        first_dimension = limit.split(";")
        for element in first_dimension:
            value += str(float(element)) + ","
        value = value[:-1] + ";"
        for dimension in first_dimension:
            second = dimension.split(",")
            for element in second:
                value += str(float(element)) + ","
    else:
        first_dimension = limit.split(",")
        for element in first_dimension:
            value += str(float(element)) + ","
    return "[" + value[:-1] + "]"


# Check and expands limits if needed
def expand_limits(monitor):
    height = monitor['height'] if "height" in monitor.keys() else 1
    try:
        for limit in LIMITS:
            is_format_expanded = check_limit_format(monitor[limit], int(monitor['width']), int(height))
            if not is_format_expanded:
                monitor[limit] = expand_limit(monitor[limit], int(monitor['width']), int(height))
            else:
                monitor[limit] = limit_to_double(monitor[limit])

    except ValueError:
        print("Error checking limits")


# Add array dimensions, width and height from type property
def if_array_add_dimensions(monitor):
    if "Array" in monitor[TYPE_] or "[" in monitor[TYPE_]:
        init = monitor[TYPE_].find("[")
        comma = monitor[TYPE_].find(",")
        end = monitor[TYPE_].find("]")

        typ = monitor[TYPE_][:init]

        if comma > 0:
            monitor[HEIGHT] = monitor[TYPE_][init + 1:comma]
            monitor[WIDTH] = monitor[TYPE_][comma + 1:end]

        else:
            monitor[WIDTH] = monitor[TYPE_][init + 1:end]

        monitor[TYPE_] = typ

        # Check limits
        expand_limits(monitor)


# Check config for value parser. Remove line feed, white spaces, etc
def value_parser_by_config(property_name, value):
    for config in CONFIG:
        if config in CONFIG_PARSER and property_name in CONFIG[config]:
            value = CONFIG_PARSER[config](value)

    return value


# Parse profile magnitudes
def profile_magnitudes_parser(lines):
    idx = get_index_of(MAGNITUDE_MARKER, lines)

    monitors = {}

    while 0 < idx:
        next_mag_idx = get_index_of(MAGNITUDE_MARKER, lines, idx + 1)

        if next_mag_idx < 0:
            next_mag_idx = len(lines)

        name = get_monitor_name(lines[idx])

        monitor = {}

        enum_type = ""

        for magnitude_property in MAGNITUDE_PROPERTIES:
            property_idx = get_index_of(magnitude_property[0], lines, idx)

            if property_idx < 0 or next_mag_idx < property_idx:
                continue

            idx, normalise_string = read_new_line_values(property_idx, lines)

            begin = normalise_string.find(':') + 1

            if begin <= 0:
                begin = normalise_string.find('=') + 1
            else:
                # The enum type is defined in the upper and lower limit
                if magnitude_property[0] == "lower_limit" or magnitude_property[0] == "upper_limit":
                    enum_type = normalise_string[normalise_string.find('=')+1:normalise_string.find(':')].strip()

            value = normalise_string[begin:].strip()

            monitor[magnitude_property[0]] = value_parser_by_config(magnitude_property[0], value)

            # Custom lambda function
            if magnitude_property[1]:
                monitor[magnitude_property[0]] = magnitude_property[1](monitor[magnitude_property[0]])

        if TYPE_ in monitor.keys():
            if_array_add_dimensions(monitor)

            # Append the enum type to the monitor type
            if monitor[TYPE_] == "enum":
                monitor[TYPE_] = monitor[TYPE_] + "_" + enum_type

        monitors[name] = monitor
        enum_type = ""
        idx = get_index_of(MAGNITUDE_MARKER, lines, idx)

    return monitors


# Parse monitor name
def get_monitor_name(line):
    begin = line.find('.')
    end = line.find(']')
    return line[begin + 1:end].strip()


# Normalise line from array, removing special characters
def read_new_line_values(idx, lines):
    normalise_string = replace_special_characters(lines[idx])
    while lines[idx][:-1].endswith('\\'):
        idx = idx + 1
        normalise_string += " " + replace_special_characters(lines[idx])
    return idx, normalise_string.strip()


# Replace special characters
def replace_special_characters(normalise_string):
    for character in SPECIAL_CHARACTERS:
        normalise_string = normalise_string.replace(character, '')
    return normalise_string.strip()


# From a profile file, generate a JSON file
def profile_to_json(profile):
    print("Parsing profile -> %s" % profile)
    with open(profile) as file:
        lines = file.readlines()
        instance, class_name = profile_header_parser(lines)
        monitors = profile_magnitudes_parser(lines)
        print("-->DONE")
        return {
            'instance': instance,
            'className': class_name,
            'monitors': monitors
        }


# Get profiles from a device path
def get_profiles_of(device):
    profiles = []
    for (dirpath, dirnames, files) in os.walk(device + "/profiles"):
        for profile in files:
            profiles.append(os.path.join(dirpath, profile))

    return profiles


# Get profiles paths from file
def read_lines_from(list_path):
    devices = []
    with open(list_path, "r") as file:
        lines = file.readlines()
        for line in lines:
            if not line.startswith("#"):
                devices.append(line.strip())
    return devices


# Save JSON result to file
def generate_json_file(profiles):
    if JSON_LOCATION != "":
        with open(os.path.join(JSON_LOCATION, "profiles.json"), "w") as file:
            json.dump(profiles, file, indent=4)


def start():
    profiles = []
    for profile in read_lines_from(PROFILE_LIST):
        if "extended" not in profile:
            profiles.append(profile_to_json(profile))
    generate_json_file(profiles)


def read_config(config):
    global CONFIG
    with open(config) as f:
        CONFIG = json.load(f)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Script to generate a JSON file '
                                                 'of device profiles. It saves the instance name, className and '
                                                 'magnitude properties (name, description, units, type, sampling '
                                                 'and storage periods, and dimensions)')
    parser.add_argument('-o', '--output', help='<Optional> Set location of output file', default="")
    parser.add_argument('-p', '--profiles', help='<Required> Set file location containing a list of profiles paths', required=True)
    parser.add_argument('-c', '--config', help='<Required> Set config file path', default=False)

    args = parser.parse_args()

    if args.profiles:
        MODE = "PROFILE"
        PROFILE_LIST = args.profiles

    if args.config:
        read_config(args.config)

    if args.output:
        JSON_LOCATION = args.output

    start()

import argparse
import os
import json

HEIGHT = 'height'

WIDTH = "width"

TYPE_ = "type"

JSON_LOCATION = ""

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

# Property name - Lambda function to parse
MAGNITUDE_PROPERTIES = [
    ["description", None],
    ["units", None],
    ["type", None],
    ["upper_limit", lambda s: s.replace(" ", "")],
    ["lower_limit", lambda s: s.replace(" ", "")],
    ["default_sampling_period", lambda s: s[:s.find("s")]],
    ["default_storage_period", lambda s: s[:s.find("s")]]
]

SPECIAL_CHARACTERS = ['\t', '\\', '\n']


def get_index_of(word, array, from_idx=0):
    for line in array[from_idx:]:
        if word in line:
            return array.index(line, from_idx)
    return -1


def profile_header_parser(lines):
    idx = get_index_of(HEADER_MARKER, lines)
    begin = lines[idx + 1].find('=')
    instance = lines[idx + 1][begin + 1:-1].strip()
    begin = lines[idx + 2].find('=')
    class_name = lines[idx + 2][begin + 1:-1].strip()
    return instance, class_name


def add_dimensions_if_array_type(monitor):

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


def to_enum_magnitude(monitor):
    for key in MONITOR_PROPERTIES:
        if key in monitor.keys():
            monitor.pop(key)


def value_parser_by_config(property_name, value):
    for config in CONFIG:
        if config in CONFIG_PARSER and property_name in CONFIG[config]:
            value = CONFIG_PARSER[config](value)

    # if property_name in CONFIG['remove-time-unit'] or "all" in CONFIG['remove-time-unit']:
    #     value = value[:-1]
    #
    # if property_name in CONFIG['remove-white-spaces'] or "all" in CONFIG['remove-white-spaces']:
    #     value = value.replace(" ", "")
    #
    # if property_name in CONFIG['remove-line-feed'] or "all" in CONFIG['remove-white-spaces']:
    #     value = value.replace("\\", "")

    return value


def profile_magnitudes_parser(lines):
    idx = get_index_of(MAGNITUDE_MARKER, lines)

    monitors = {}

    while 0 < idx:
        next_mag_idx = get_index_of(MAGNITUDE_MARKER, lines, idx + 1)

        if next_mag_idx < 0:
            next_mag_idx = len(lines)

        name = get_monitor_name(lines[idx])

        monitor = {}

        for magnitude_property in MAGNITUDE_PROPERTIES:
            property_idx = get_index_of(magnitude_property[0], lines, idx)

            if property_idx < 0 or next_mag_idx < property_idx:
                continue

            idx, normalise_string = read_new_line_values(property_idx, lines)

            begin = normalise_string.find(':') + 1
            if begin <= 0:
                begin = normalise_string.find('=') + 1

            value = normalise_string[begin:].strip()

            monitor[magnitude_property[0]] = value_parser_by_config(magnitude_property[0], value)

            # if magnitude_property[1] is not None:
            #     monitor[magnitude_property[0]] = magnitude_property[1](value)
            # else:
            #     monitor[magnitude_property[0]] = value

        if TYPE_ in monitor.keys():
            add_dimensions_if_array_type(monitor)
        #     if monitor[TYPE_] == "enum":
        #         to_enum_magnitude(monitor)
        #     else:

        monitors[name] = monitor

        idx = get_index_of(MAGNITUDE_MARKER, lines, idx)

    return monitors


def get_monitor_name(line):
    begin = line.find('.')
    end = line.find(']')
    return line[begin + 1:end].strip()


def read_new_line_values(idx, lines):
    normalise_string = replace_special_characters(lines[idx])
    while lines[idx][:-1].endswith('\\'):
        idx = idx + 1
        normalise_string += " " + replace_special_characters(lines[idx])
    return idx, normalise_string.strip()


def replace_special_characters(normalise_string):
    for character in SPECIAL_CHARACTERS:
        normalise_string = normalise_string.replace(character, '')
    return normalise_string.strip()


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


def get_profiles_of(device):
    profiles = []
    for (dirpath, dirnames, files) in os.walk(device + "/profiles"):
        for profile in files:
            profiles.append(os.path.join(dirpath, profile))

    return profiles


def read_lines_from(list_path):
    devices = []
    with open(list_path, "r") as file:
        lines = file.readlines()
        for line in lines:
            if not line.startswith("#"):
                devices.append(line.strip())
    return devices


def generate_json_file(profiles):
    with open(os.path.join(JSON_LOCATION, "output.json"), "w") as file:
        json.dump(profiles, file, indent=4)


def start():
    profiles = []
    if MODE == "DEVICES":
        for device in read_lines_from(DEVICE_LIST):
            for profile in get_profiles_of(device):
                profiles.append(profile_to_json(profile))
    else:
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
    parser.add_argument('-o', '--output', help='<Optional> Set location where the devices will be created', default="")
    parser.add_argument('-d', '--devices', help='<Optional> List of devices', default=False)
    parser.add_argument('-p', '--profiles', help='<Optional> List of profiles', default=False)
    parser.add_argument('-c', '--config', help='<Required> Config file', default=False)

    args = parser.parse_args()

    # args.b will be None if b is not provided
    if not args.devices and not args.profiles:
        raise RuntimeError("Neither devices or profiles was given")
    if not args.devices:
        MODE = "PROFILE"
        PROFILE_LIST = args.profiles
    else:
        MODE = "DEVICES"
        DEVICE_LIST = args.devices

    if args.config:
        read_config(args.config)

    JSON_LOCATION = args.output

    start()

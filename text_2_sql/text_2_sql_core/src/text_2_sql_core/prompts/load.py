# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
import yaml
import os


def load(file):
    # Get the directory containing this module
    package_dir = os.path.dirname(__file__)

    # Construct the absolute path to the file
    file_path = os.path.join(package_dir, f"{file}.yaml")
    with open(file_path, "r") as file:
        file = yaml.safe_load(file)

    return file

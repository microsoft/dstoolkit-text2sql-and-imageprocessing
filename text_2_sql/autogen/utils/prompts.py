import yaml


def load_system_message(name):
    with open(f"prompts/{name.lower()}.yaml", "r") as file:
        file = yaml.safe_load(file)

    return file["system_message"]


def load_description(name):
    with open(f"prompts/{name.lower()}.yaml", "r") as file:
        file = yaml.safe_load(file)

    return file["description"]

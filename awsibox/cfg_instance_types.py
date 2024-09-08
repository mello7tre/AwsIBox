INSTANCE_SIZES = [
    "nano",
    "micro",
    "small",
    "medium",
    "large",
    "xlarge",
    "2xlarge",
    "4xlarge",
    "8xlarge",
    "12xlarge",
    "16xlarge",
    "24xlarge",
    "32xlarge",
    "48xlarge",
]

INSTANCE_FAMILY = [
    {
        "Name": "t2",
        "Min": "nano",
        "Max": "2xlarge",
        "RDS": True,
    },
    {
        "Name": "m4",
        "Min": "large",
        "Max": "4xlarge",
        "RDS": True,
    },
    {
        "Name": "c4",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "r4",
        "Min": "large",
        "Max": "4xlarge",
        "RDS": True,
    },
    {
        "Name": "t3",
        "Min": "nano",
        "Max": "2xlarge",
        "RDS": True,
    },
    {
        "Name": "m5",
        "Min": "large",
        "Max": "4xlarge",
        "RDS": True,
    },
    {
        "Name": "c5",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "r5",
        "Min": "large",
        "Max": "4xlarge",
        "RDS": True,
    },
    {
        "Name": "t3a",
        "Min": "nano",
        "Max": "2xlarge",
    },
    {
        "Name": "t4g",
        "Min": "nano",
        "Max": "2xlarge",
        "RDS": True,
    },
    {
        "Name": "m5a",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "c5a",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "r5a",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "m6i",
        "Min": "large",
        "Max": "4xlarge",
        "RDS": True,
    },
    {
        "Name": "c6i",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "r6i",
        "Min": "large",
        "Max": "4xlarge",
        "RDS": True,
    },
    {
        "Name": "m6a",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "c6a",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "c7g",
        "Min": "large",
        "Max": "4xlarge",
    },
    {
        "Name": "m7g",
        "Min": "large",
        "Max": "4xlarge",
        "RDS": True,
    },
]

# currently nearly empty as no more used with newer generations instances
EPHEMERAL_MAP = {
    "InstaceEphemeral0": ["m3.medium", "m3.xlarge"],
    "InstaceEphemeral1": ["m3.xlarge"],
    "InstaceEphemeral2": [""],
}

# build instances list
def build_instance_list():
    family_instances_list = []
    family_instances_list_rds = []
    for family in INSTANCE_FAMILY:
        name = family["Name"]
        min_size = INSTANCE_SIZES.index(family["Min"])
        max_size = INSTANCE_SIZES.index(family["Max"])

        for s in INSTANCE_SIZES[min_size : max_size + 1]:
            family_instances_list.append(f"{name}.{s}")
            if family.get("RDS"):
                family_instances_list_rds.append(f"db.{name}.{s}")

    return ["default"] + family_instances_list, [""] + family_instances_list_rds


INSTANCE_LIST, INSTANCE_LIST_RDS = build_instance_list()

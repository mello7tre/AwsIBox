import troposphere.ecr as ecr

from .common import *
from .shared import (
    Parameter,
    get_endvalue,
    get_expvalue,
    get_subvalue,
    auto_get_props,
    get_condition,
    add_obj,
)


def ECRRepositoryPolicyStatementAccountPull(name):
    policy = {
        "Action": [
            "ecr:GetDownloadUrlForLayer",
            "ecr:BatchGetImage",
            "ecr:BatchCheckLayerAvailability",
            "ecr:ListImages",
            "ecr:DescribeRepositories",
            "ecr:DescribeImages",
        ],
        "Effect": "Allow",
        "Principal": {"AWS": [get_subvalue("arn:aws:iam::${1M}:root", name)]},
        "Sid": "AllowPull",
    }

    return policy


def ECRRepositoryPolicyStatementAccountPush(name):
    policy = {
        "Action": [
            "ecr:PutImage",
            "ecr:InitiateLayerUpload",
            "ecr:UploadLayerPart",
            "ecr:CompleteLayerUpload",
            "ecr:BatchCheckLayerAvailability",
        ],
        "Effect": "Allow",
        "Principal": {"AWS": [get_subvalue("arn:aws:iam::${1M}:root", name)]},
        "Sid": "AllowPush",
    }

    return policy


# ##########################################
# ### END STACK META CLASSES AND METHODS ###
# ##########################################


def ECR_Repositories(key):
    PolicyStatementAccounts = []
    for n, v in cfg.EcrAccount.items():
        mapname = f"EcrAccount{n}Id"  # Ex. EcrAccountPrdId
        # conditions
        add_obj(get_condition(mapname, "not_equals", "none"))

        if "Pull" in v["Policy"]:
            PolicyStatementAccount = ECRRepositoryPolicyStatementAccountPull(
                name=mapname
            )
            PolicyStatementAccounts.append(
                If(mapname, PolicyStatementAccount, Ref("AWS::NoValue"))
            )

        if "Push" in v["Policy"]:
            PolicyStatementAccount = ECRRepositoryPolicyStatementAccountPush(
                name=mapname
            )
            PolicyStatementAccounts.append(
                If(mapname, PolicyStatementAccount, Ref("AWS::NoValue"))
            )

    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"
        Repo = ecr.Repository(resname)
        auto_get_props(Repo, indexname=n)
        Repo.RepositoryPolicyText["Statement"].extend(PolicyStatementAccounts)

        add_obj(Repo)

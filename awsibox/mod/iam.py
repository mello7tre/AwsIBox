import troposphere.iam as iam

from ..common import *
from ..shared import (
    get_endvalue,
    auto_get_props,
    get_condition,
    add_obj,
)


def IAM_Users(key):
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"  # Ex. IAMUserPincoPalla
        if not v.get("IBOX_ENABLED", True):
            continue

        ManagedPolicyArns = []
        RoleGroups = []
        if "RoleGroups" in v:
            for m, w in v["RoleGroups"].items():
                condname = f"{resname}RoleGroups{m}"
                # conditions
                add_obj(get_condition(condname, "equals", "yes"))

                # resources
                RoleGroups.append(If(condname, m, Ref("AWS::NoValue")))

                try:
                    policy_arns = cfg.IAMGroup[m]["ManagedPolicyArns"]
                except Exception:
                    pass
                else:
                    for p in policy_arns:
                        ManagedPolicyArns.append(
                            If(
                                condname,
                                ImportValue(f"IAMPolicy{p}"),
                                Ref("AWS::NoValue"),
                            )
                        )

        # resources
        r_Role = iam.Role(f"IAMRole{n}", ManagedPolicyArns=ManagedPolicyArns)
        auto_get_props(
            r_Role,
            mapname="IAMRoleUser",
            linked_obj_name=resname,
            linked_obj_index=v["UserName"],
        )

        r_User = iam.User(resname, Groups=RoleGroups)
        auto_get_props(r_User, indexname=n, remapname=v["UserName"])

        add_obj([r_User, r_Role])

import troposphere.apigateway as agw
import troposphere.route53 as r53

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


def AGW_UsagePlans(key):
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"
        for m, w in v["ApiStages"].items():
            # parameters
            p_Stage = Parameter(f"{resname}ApiStages{m}Stage")
            p_Stage.Description = f"{m} Stage - empty for default based on env/role"

            add_obj(p_Stage)

        # resources
        r_UsagePlan = agw.UsagePlan(resname)
        auto_get_props(r_UsagePlan)

        # outputs
        o_UsagePlan = Output(resname)
        o_UsagePlan.Value = Ref(resname)
        o_UsagePlan.Export = Export(resname)

        add_obj([r_UsagePlan, o_UsagePlan])


def AGW_ApiKeys(key):
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"
        # parameters
        p_Enabled = Parameter(
            f"{resname}Enabled",
            Description=f"{resname}Enabled - empty for mapped value",
            AllowedValues=["", "yes", "no"],
        )

        p_UsagePlan = Parameter(
            f"{resname}UsagePlan",
            Description=f"{resname}UsagePlan - empty for default based on env/role",
        )

        add_obj([p_Enabled, p_UsagePlan])

        # resources
        r_ApiKey = agw.ApiKey(resname)
        auto_get_props(r_ApiKey)

        if "UsagePlan" in v:
            plankey_name = f"{resname}UsagePlan"
            r_UsagePlanKey = agw.UsagePlanKey(
                f"ApiGatewayUsagePlan{n}",
                KeyId=Ref(resname),
                KeyType="API_KEY",
                UsagePlanId=ImportValue(
                    get_subvalue("ApiGatewayUsagePlan${1M}", f"{resname}UsagePlan")
                ),
            )

            add_obj(r_UsagePlanKey)

        # outputs
        o_ApiKey = Output(resname, Value=Ref(resname))

        add_obj([r_ApiKey, o_ApiKey])

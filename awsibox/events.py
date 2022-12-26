import troposphere.events as eve

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


def EVE_EventRules(key):
    for n, v in getattr(cfg, key).items():
        if not v.get("IBOX_ENABLED", True):
            continue

        resname = f"{key}{n}"
        ibox_lo_cfg = v.get("IBOX_LINKED_OBJ", {})
        if isinstance(ibox_lo_cfg, str):
            ibox_lo_cfg = {"Base": ibox_lo_cfg}

        # resources
        Targets = []
        for m, w in v["Targets"].items():
            targetname = f"{resname}Targets{m}"
            Target = eve.Target(targetname)

            if m.startswith("Lambda"):
                permname = "%s%s" % (m.replace("Lambda", "LambdaPermission"), resname)
                # create ad hoc IBOX_LINKED_OBJ
                lo_cfg = {
                    "Key": "LambdaPermission",
                    "Type": "EventsRule",
                    "Name": f"LambdaPermission{m}{resname}",
                    "Conf": {
                        "IBOX_RESNAME": permname,
                        "IBOX_LINKED_OBJ_NAME": w["Arn"],
                        "IBOX_LINKED_OBJ_INDEX": f"GetAtt('{resname}', 'Arn')",
                    },
                }
                ibox_lo_cfg[m] = lo_cfg
            if m.startswith("ECSCluster"):
                # add common "fixed" props
                auto_get_props(
                    Target, mapname="EventsRuleTargetECSCluster", indexname=m, res_obj_type="AWS::Events::Rule")

            # add props found in yaml cfg
            auto_get_props(Target, res_obj_type="AWS::Events::Rule")
            Targets.append(Target)

        getattr(cfg, resname).update({"IBOX_LINKED_OBJ": ibox_lo_cfg})
        r_Rule = eve.Rule(resname)
        auto_get_props(r_Rule, indexname=n)
        r_Rule.Targets = Targets

        add_obj(r_Rule)

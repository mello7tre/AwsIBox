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
        resname = f"{key}{n}"

        # resources
        Targets = []
        for m, w in v["Targets"].items():
            targetname = f"{resname}Targets{m}"
            Target = eve.Target(targetname)

            if m.startswith("Lambda"):
                permname = "%s%s" % (m.replace("Lambda", "LambdaPermission"), resname)
                # create ad hoc IBOX_LINKED_OBJ
                ibox_lo_cfg = {
                    "IBOX_LINKED_OBJ": {
                        "Key": "LambdaPermission",
                        "Type": "EventsRule",
                        "Name": f"LambdaPermission{m}{resname}",
                        "Conf": {
                            "IBOX_RESNAME": permname,
                            "IBOX_LINKED_OBJ_NAME": w["Arn"],
                            "IBOX_LINKED_OBJ_INDEX": 'GetAtt("IBOX_RESNAME", "Arn")',
                        },
                    }
                }
                if "Condition" in v:
                    ibox_lo_cfg["IBOX_LINKED_OBJ"]["Conf"]["Condition"] = v["Condition"]
                getattr(cfg, targetname).update(ibox_lo_cfg)
            if m.startswith("ECSCluster"):
                # add common "fixed" props
                auto_get_props(Target, mapname="EventsRuleTargetECSCluster", indexname=m)

            # add props found in yaml cfg
            auto_get_props(Target)
            Targets.append(Target)

        r_Rule = eve.Rule(resname)
        auto_get_props(r_Rule, indexname=n)
        r_Rule.Targets = Targets

        add_obj(r_Rule)

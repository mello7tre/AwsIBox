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
        # parameters
        p_State = Parameter(
            f"{resname}State",
            Description="Events Rule State - empty for default based on env/role",
            AllowedValues=["", "DISABLED", "ENABLED"],
        )

        if "ScheduleExpression" in v:
            p_ScheduleExpression = Parameter(
                f"{resname}ScheduleExpression",
                Description="Events Rule Schedule - empty for default based on env/role",
            )

            add_obj(p_ScheduleExpression)

        add_obj([p_State])

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
        auto_get_props(r_Rule)
        r_Rule.Name = Sub("${AWS::StackName}-${EnvRole}-" f"Rule{n}")
        r_Rule.Targets = Targets

        # outputs
        o_State = Output(f"{resname}State", Value=get_endvalue(f"{resname}State"))

        if "ScheduleExpression" in v:
            o_ScheduleExpression = Output(
                f"{resname}ScheduleExpression",
                Value=get_endvalue(f"{resname}ScheduleExpression"),
            )

            add_obj(o_ScheduleExpression)

        add_obj([r_Rule, o_State])

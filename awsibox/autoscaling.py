import troposphere.autoscaling as asg
import troposphere.ec2 as ec2
import troposphere.cloudformation as cfm
import troposphere.policies as pol
import troposphere.applicationautoscaling as aas

from .common import *
from .shared import (
    Parameter,
    get_endvalue,
    get_expvalue,
    get_subvalue,
    auto_get_props,
    get_condition,
    add_obj,
    import_user_data,
)


def AS_LaunchTemplate():
    Tags_List = []

    # Resources
    R_LaunchTemplate = ec2.LaunchTemplate(
        "LaunchTemplate",
        LaunchTemplateName=Sub("${AWS::StackName}-${EnvRole}"),
    )

    LaunchTemplateData = ec2.LaunchTemplateData("LaunchTemplateData")
    auto_get_props(
        LaunchTemplateData,
        "LaunchTemplateData",
        res_obj_type="AWS::EC2::LaunchTemplate",
    )

    if getattr(cfg, "IBOX_LAUNCH_TEMPLATE_NO_SG_EXTRA", False):
        SecurityGroups = []
    else:
        SecurityGroups = cfg.SecurityGroupsImport
    LaunchTemplateData.NetworkInterfaces[0].Groups.extend(SecurityGroups)

    R_LaunchTemplate.LaunchTemplateData = LaunchTemplateData

    ud_envrole = getattr(cfg, "IBOX_ROLE_EX", getattr(cfg, "envrole"))
    # try to get a complete user-data conf in package or in Ext dir
    user_data = import_user_data(ud_envrole)

    if not user_data:
        # if not found build a dynamic one
        for user_data_section in [
            "INIT",
            "PACKAGE",
            "SETUP",
            "APPS",
            "SERVICE",
            "ELBCHECK",
            ud_envrole,
            "END",
        ]:
            user_data.extend(import_user_data(f"SCRIPTS/{user_data_section}"))

    user_data = Join("", user_data)
    LaunchTemplateData.UserData = Base64(user_data)

    if getattr(cfg, "BottleRocket", False):
        # use if condition with both bottlerocket custom and standard cfg
        LaunchTemplateData.UserData = Base64(
            If(
                "BottleRocket",
                Join(
                    "\n",
                    [
                        get_endvalue(f"BottleRocketUserData{n}Line")
                        for n in cfg.BottleRocketUserData
                    ],
                ),
                user_data,
            ),
        )

    add_obj(R_LaunchTemplate)

    Tags = asg.Tags()
    Tags.tags = Tags_List
    return Tags


def AS_Autoscaling(key):
    LoadBalancers = []
    TargetGroups = []
    if cfg.LoadBalancerType == "Classic":
        for n in cfg.LoadBalancer:
            LoadBalancers.append(Ref(f"LoadBalancerClassic{n}"))
            setattr(
                cfg,
                "EC2InstanceUserDataELBClassicCheckLoadBalancerName",
                Ref(f"LoadBalancerClassic{n}"),
            )
    if cfg.LoadBalancerType in ["Application", "Network"]:
        for n, v in getattr(cfg, "ElasticLoadBalancingV2TargetGroup", {}).items():
            # check for enabled only for EC2 ones
            if n.startswith("EC2") and v.get("IBOX_ENABLED", True):
                TargetGroups.append(
                    Ref(f"ElasticLoadBalancingV2TargetGroupEC2LoadBalancer{n}")
                )
                setattr(
                    cfg,
                    "EC2InstanceUserDataELBV2CheckTargetGroupArn",
                    Ref(f"ElasticLoadBalancingV2TargetGroupTargetGroupLoadBalancer{n}"),
                )

    # Resources
    LaunchTemplateTags = AS_LaunchTemplate()

    R_ASG = asg.AutoScalingGroup(
        "AutoScalingGroupBase",
        LoadBalancerNames=LoadBalancers,
    )

    auto_get_props(R_ASG)

    try:
        R_ASG.TargetGroupARNs
    except Exception:
        R_ASG.TargetGroupARNs = TargetGroups
    else:
        R_ASG.TargetGroupARNs.extend(TargetGroups)

    R_ASG.Tags += LaunchTemplateTags

    add_obj([R_ASG])

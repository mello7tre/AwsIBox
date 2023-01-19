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


def AS_ScalingPolicies(key):
    Out_String = []
    Out_Map = {}
    for n, v in getattr(cfg, key).items():
        if not v["IBOX_ENABLED"]:
            continue

        resname = f"{key}{n}"

        # resources
        if key == "AutoScalingScalingPolicy":
            r_Policy = asg.ScalingPolicy(resname)
        else:
            r_Policy = aas.ScalingPolicy(resname)

        auto_get_props(r_Policy)
        add_obj(r_Policy)

        # for tracking create output
        if v["PolicyType"] == "TargetTrackingScaling":
            # Autoscaling
            if "TargetTrackingConfiguration" in v:
                TargetTrackingConfigurationName = "TargetTrackingConfiguration"
            # Application Autoscaling
            elif "TargetTrackingScalingPolicyConfiguration" in v:
                TargetTrackingConfigurationName = (
                    "TargetTrackingScalingPolicyConfiguration"
                )

            basename = f"{resname}{TargetTrackingConfigurationName}"

            # outputs
            if v["Type"] == "Cpu" or (
                v["Type"] == "Custom"
                and v[TargetTrackingConfigurationName]["CustomizedMetricSpecification"][
                    "MetricName"
                ]
                == "CPUUtilization"
            ):
                # Use Cpu Metric
                Out_String.append("Cpu${Statistic}:${Cpu}")

                if v["Type"] == "Custom":
                    statistic = get_endvalue(
                        f"{basename}" "CustomizedMetricSpecificationStatistic"
                    )
                else:
                    statistic = ""

                Out_Map.update(
                    {
                        "Statistic": statistic,
                        "Cpu": get_endvalue(f"{basename}TargetValue"),
                    }
                )

    if Out_String:
        # Outputs
        O_Policy = Output(key, Value=Sub(",".join(Out_String), **Out_Map))

        add_obj(O_Policy)


def AS_LaunchTemplate():
    IBoxEnvApp = []
    Tags_List = []

    for n in cfg.Apps:
        name = f"Apps{n}"  # Ex. Apps1
        envname = f"EnvApp{n}Version"  # Ex EnvApp1Version
        reponame = f"{name}RepoName"  # Ex Apps1RepoName

        # parameters
        p_EnvAppVersion = Parameter(
            envname,
            Description=f"Application {n} version",
            AllowedPattern="^[a-zA-Z0-9-_.]*$",
        )

        p_AppsRepoName = Parameter(
            reponame,
            Description=f"App {n} Repo Name - empty for default based on env/role",
            AllowedPattern="^[a-zA-Z0-9-_.]*$",
        )

        add_obj(
            [
                p_EnvAppVersion,
                p_AppsRepoName,
            ]
        )

        # conditions
        add_obj(
            {
                name: And(
                    Not(Equals(Ref(envname), "")),
                    Not(get_condition("", "equals", "None", reponame)),
                )
            }
        )

        IBoxEnvApp.extend(
            [
                f"export EnvApp{n}Version=",
                Ref(envname),
                "\n",
                f"export EnvRepo{n}Name=",
                get_endvalue(reponame),
                "\n",
            ]
        )

        Tags_List.append(asg.Tag(envname, Ref(envname), True))

        # outputs
        Output_app = Output(envname, Value=Ref(envname))
        Output_repo = Output(reponame, Value=get_endvalue(reponame))

        add_obj([Output_app, Output_repo])

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
            if v.get("IBOX_ENABLED", True):
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

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
from .lambdas import LambdaPermissionApiGateway


class ApiGatewayResource(agw.Resource):
    def __init__(self, title, key, stage, **kwargs):
        super().__init__(title, **kwargs)
        mapname = f"ApiGatewayStage{stage}ApiGatewayResource"

        auto_get_props(self)
        self.RestApiId = Ref("ApiGatewayRestApi")

        # if stage override ApiGatewayResource specs, get it
        try:
            getattr(cfg, mapname)
        except Exception:
            pass
        else:
            auto_get_props(self, mapname)


class ApiGatewayMethod(agw.Method):
    def __init__(self, title, key, basename, name, stage, **kwargs):
        super().__init__(title, **kwargs)
        mapname = f"ApiGatewayStage{stage}" f"ApiGatewayResource{basename}Method{name}"

        try:
            getattr(cfg, mapname)
        except Exception:
            pass
        else:
            auto_get_props(self, mapname)

        auto_get_props(self)
        self.RestApiId = Ref("ApiGatewayRestApi")
        self.ResourceId = Ref(f"ApiGatewayResource{basename}")

        # If Uri is a lambda self.Integration.Uri will be like:
        # 'arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaName.Arn}/invocations'
        # i need to append stage version (Ex. v1) to the Lambda Name so that
        # ${LambdaName.Arn} -> ${LambdaNameV1.Arn}
        if ":lambda:" in self.Integration.Uri:
            iu = self.Integration.Uri
            dot_found = iu.rfind(".")
            before_dot = iu[0:dot_found]
            after_dot = iu[dot_found:]
            if after_dot.startswith(".Arn"):
                self.Integration.Uri = Sub(f"{before_dot}{stage}{after_dot}")


class ApiGatewayDeployment(agw.Deployment):
    def __init__(self, title, name, key, **kwargs):
        super().__init__(title, **kwargs)
        lastresource = next(reversed(list(cfg.ApiGatewayResource)))
        lastmethod = next(
            reversed(list(cfg.ApiGatewayResource[lastresource]["Method"]))
        )
        self.DependsOn = f"ApiGatewayResource{lastresource}Method{lastmethod}"
        self.Description = Ref(f"Deployment{name}Description")
        self.RestApiId = Ref("ApiGatewayRestApi")


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


def AGW_Stages(key):
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"
        depname = f"Deployment{n}"

        # resources
        r_Stage = agw.Stage(resname)
        auto_get_props(r_Stage, indexname=n)

        r_DeploymentA = ApiGatewayDeployment(
            f"ApiGatewayDeployment{n}A", name=n, key=v, Condition=f"{depname}A"
        )

        r_DeploymentB = ApiGatewayDeployment(
            f"ApiGatewayDeployment{n}B", name=n, key=v, Condition=f"{depname}B"
        )

        #add_obj([r_Stage, r_DeploymentA, r_DeploymentB])
        add_obj([r_Stage])


def AGW_RestApi(key):
    # Resources
    R_RestApi = agw.RestApi("ApiGatewayRestApi")
    auto_get_props(R_RestApi, f"{key}Base")

    try:
        condition = cfg.PolicyCondition
        R_RestApi.Policy["Statement"][0]["Condition"] = condition
    except Exception:
        pass

    add_obj(
        [
            R_RestApi,
        ]
    )

    for n, v in cfg.ApiGatewayResource.items():
        resname = f"ApiGatewayResource{n}"
        agw_stage = cfg.ApiGatewayRestApi["Base"]["Stage"]
        r_Resource = ApiGatewayResource(resname, key=v, stage=agw_stage)

        for m, w in v["Method"].items():
            r_Method = ApiGatewayMethod(
                f"{resname}Method{m}", key=w, basename=n, name=m, stage=agw_stage
            )

            add_obj([r_Resource, r_Method])

    for n, v in cfg.Lambda.items():
        r_LambdaPermission = LambdaPermissionApiGateway(
            f"LambdaPermission{n}",
            name=Ref(f"Lambda{n}"),
            source=Sub(
                "arn:aws:execute-api:${AWS::Region}:"
                "${AWS::AccountId}:${ApiGatewayRestApi}/*/*/*"
            ),
        )

        add_obj(r_LambdaPermission)

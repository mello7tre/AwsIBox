import troposphere.awslambda as lbd

from .common import *
from .shared import (
    Parameter,
    get_endvalue,
    get_expvalue,
    get_subvalue,
    auto_get_props,
    get_condition,
    add_obj,
    import_lambda,
    parse_ibox_key,
)


class LambdaPermission(lbd.Permission):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Action = "lambda:InvokeFunction"


class LambdaPermissionEvent(LambdaPermission):
    def __init__(self, title, key, source, **kwargs):
        super().__init__(title, **kwargs)
        self.Principal = "events.amazonaws.com"
        self.FunctionName = eval(key["Arn"])
        self.SourceArn = GetAtt(source, "Arn")


class LambdaPermissionS3(LambdaPermission):
    def __init__(self, title, key, source, **kwargs):
        super().__init__(title, **kwargs)
        self.Principal = "s3.amazonaws.com"
        self.FunctionName = key
        self.SourceArn = Sub("arn:aws:s3:::%s" % source)


def LBD_Lambdas(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"

        # resources
        r_Lambda = lbd.Function(resname)
        auto_get_props(r_Lambda, indexname=n) 
        ibox_source_obj = v.get("IBOX_SOURCE_OBJ")
        if ibox_source_obj:
            parse_ibox_key_conf = {"IBOX_INDEXNAME": n}
            ibox_source_obj = parse_ibox_key(ibox_source_obj, parse_ibox_key_conf)
            auto_get_props(r_Lambda, mapname=ibox_source_obj, indexname=n)

        if "Version" in v:
            versionname = f"{resname}Version"
            versionnameA = f"{versionname}A"
            versionnameB = f"{versionname}B"

            # parameters
            p_Version = Parameter(
                versionname,
                Description="LambdaVersion - change between A/B "
                "to force deploy new version",
                AllowedValues=["", "A", "B"],
                Default="",
            )

            add_obj(p_Version)

            # conditons
            c_VersionA = {
                versionnameA: And(
                    Condition(resname) if "Enabled" in v else Equals("1", "1"),
                    get_condition("", "equals", "A", versionname, nomap=True),
                )
            }

            c_VersionB = {
                versionnameB: And(
                    Condition(resname) if "Enabled" in v else Equals("1", "1"),
                    get_condition("", "equals", "B", versionname, nomap=True),
                )
            }

            c_Version = {
                versionname: Or(
                    Condition(versionnameA),
                    Condition(versionnameB),
                )
            }

            #add_obj([c_VersionA, c_VersionB, c_Version])

            # resources
            r_VersionA = lbd.Version(
                versionnameA, FunctionName=Ref(resname), Condition=versionnameA
            )

            r_VersionB = lbd.Version(
                versionnameB, FunctionName=Ref(resname), Condition=versionnameB
            )

            # outputs
            o_Version = Output(
                versionname,
                Value=If(versionnameA, Ref(versionnameA), Ref(versionnameB)),
                Condition=versionname,
            )

            #add_obj([r_VersionA, r_VersionB, o_Version])

        # if not v.get("SkipRole"):
        #    # Automatically setup a lambda Role with base permissions.
        #    r_Role = IAMRoleLambdaBase(f"Role{resname}", key=v)
        #    if hasattr(r_Lambda, "Condition"):
        #        r_Role.Condition = r_Lambda.Condition
        #    add_obj(r_Role)

        add_obj(r_Lambda)

        if v.get("Export"):
            O_Lambda = Output(
                resname, Value=GetAtt(resname, "Arn"), Export=Export(resname)
            )

            #add_obj(O_Lambda)


def LBD_LayerVersions(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"

        try:
            v["Content"]["S3Key"]
        except Exception:
            pass
        else:
            s3keyname = f"{resname}ContentS3Key"
            # parameters
            add_obj(
                Parameter(s3keyname, Description=f"S3Key Name for lambda {n} Content")
            )

            # outputs
            add_obj(Output(s3keyname, Value=get_endvalue(s3keyname)))

        # resources
        r_Layer = lbd.LayerVersion(resname)
        auto_get_props(r_Layer)
        r_LayerPermission = lbd.LayerVersionPermission(
            f"LambdaLayerPermission{n}",
            LayerVersionArn=Ref(resname),
            Action="lambda:GetLayerVersion",
            Principal=Ref("AWS::AccountId"),
        )

        # output
        o_Layer = Output(resname, Value=Ref(resname))

        add_obj([r_Layer, r_LayerPermission, o_Layer])

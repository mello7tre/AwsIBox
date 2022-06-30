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

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
)
from .iam import IAMRoleLambdaBase


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


class LambdaPermissionApiGateway(LambdaPermission):
    def __init__(self, title, name, source, **kwargs):
        super().__init__(title, **kwargs)
        self.Principal = "apigateway.amazonaws.com"
        self.FunctionName = name
        self.SourceArn = source


class LambdaPermissionLoadBalancing(LambdaPermission):
    def __init__(self, title, name, **kwargs):
        super().__init__(title, **kwargs)
        self.Principal = "elasticloadbalancing.amazonaws.com"
        self.FunctionName = name


class LambdaVersion(lbd.Version):
    def __init__(self, title, name, **kwargs):
        super().__init__(title, **kwargs)
        self.FunctionName = Ref(name)


class LambdaFunction(lbd.Function):
    def __init__(self, title, key, name, **kwargs):
        super().__init__(title, **kwargs)
        import_name = key.get("ImportName", name)
        if "Code" not in key:
            self.Code = lbd.Code()
            try:
                self.Code.ZipFile = Join("", import_lambda(import_name))
            except Exception:
                self.Code.ZipFile = (
                    'print("Use Code parameter in yaml '
                    f"or create file lib/lambas/{import_name}.code "
                    'with lambda code to execute.")'
                )

        if "Enabled" in key:
            # conditions
            add_obj(get_condition(title, "equals", "yes", f"{title}Enabled"))
            # Need to do it this way so that linked obj "see" the Condition key
            self.Condition = title
            getattr(cfg, title)["Condition"] = title
            getattr(cfg, "mappedvalues").append(f"{title}Condition")

        auto_get_props(self, indexname=name)
        self.FunctionName = Sub("${AWS::StackName}-${EnvRole}-%s" % name)

        if "Handler" not in key:
            self.Handler = "index.lambda_handler"
        try:
            getattr(self, "Role")
        except Exception:
            self.Role = GetAtt(f"RoleLambda{name}", "Arn")

        # Variables - skip if atEdge - always set Env, EnvRole
        try:
            key["AtEdge"]
        except Exception as e:
            self.Environment = lbd.Environment(
                Variables={
                    "Env": Ref("EnvShort"),
                    "EnvRole": Ref("EnvRole"),
                }
            )
            if "Variables" in key:
                self.Environment.Variables.update(
                    {
                        varname: get_endvalue(f"{self.title}Variables{varname}")
                        for varname in key["Variables"]
                    }
                )


class LambdaLayerVersionPermission(lbd.LayerVersionPermission):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Action = "lambda:GetLayerVersion"
        self.Principal = Ref("AWS::AccountId")


def LambdaLayers(value):
    # parameters
    p_Layer = Parameter(value, Description=value)

    add_obj(p_Layer)

    # condition
    add_obj(get_condition(value, "not_equals", ""))

    # output
    o_Layer = Output(value, Value=get_endvalue(value, condition=True))

    add_obj(o_Layer)

    return o_Layer.Value


##


def LBD_Lambdas(key):
    # Resources
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"

        try:
            v["Code"]["S3Key"]
        except Exception:
            pass
        else:
            s3keyname = f"{resname}CodeS3Key"
            # parameters
            add_obj(Parameter(s3keyname, Description=f"S3Key Name for lambda {n} Code"))

            # outputs
            add_obj(Output(s3keyname, Value=get_endvalue(s3keyname)))

        # resources
        r_Lambda = LambdaFunction(resname, key=v, name=n)

        if "Layers" in v:
            r_Lambda.Layers = []
            for i, j in enumerate(v["Layers"]):
                r_Lambda.Layers.append(LambdaLayers(j))

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

            add_obj([c_VersionA, c_VersionB, c_Version])

            # resources
            r_VersionA = LambdaVersion(
                versionnameA, name=resname, Condition=versionnameA
            )

            r_VersionB = LambdaVersion(
                versionnameB, name=resname, Condition=versionnameB
            )

            # outputs
            o_Version = Output(
                versionname,
                Value=If(versionnameA, Ref(versionnameA), Ref(versionnameB)),
                Condition=versionname,
            )

            add_obj([r_VersionA, r_VersionB, o_Version])

        #if not v.get("SkipRole"):
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

            add_obj(O_Lambda)


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
        r_LayerPermission = LambdaLayerVersionPermission(
            f"LambdaLayerPermission{n}", LayerVersionArn=Ref(resname)
        )

        # output
        o_Layer = Output(resname, Value=Ref(resname))

        add_obj([r_Layer, r_LayerPermission, o_Layer])

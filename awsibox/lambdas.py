import troposphere.awslambda as lbd

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition, add_obj, import_lambda)
from .iam import IAMRoleLambdaBase

class LambdaPermission(lbd.Permission):
    def setup(self):
        self.Action = 'lambda:InvokeFunction'


class LambdaPermissionEvent(LambdaPermission):
    def setup(self, key, source):
        super(LambdaPermissionEvent, self).setup()
        self.Principal = 'events.amazonaws.com'
        self.FunctionName = eval(key['Arn'])
        self.SourceArn = GetAtt(source, 'Arn')


class LambdaPermissionSNS(LambdaPermission):
    def setup(self, key, **kwargs):
        super(LambdaPermissionSNS, self).setup(**kwargs)
        auto_get_props(self, key)
        self.Principal = 'sns.amazonaws.com'
        self.FunctionName = eval(key['Endpoint'])
        self.SourceArn = eval(key['TopicArn'])


class LambdaPermissionApiGateway(LambdaPermission):
    def setup(self, name, source):
        super(LambdaPermissionApiGateway, self).setup()
        self.Principal = 'apigateway.amazonaws.com'
        self.FunctionName = name
        self.SourceArn = source


class LambdaVersion(lbd.Version):
    def __init__(self, title, name, **kwargs):
        super(LambdaVersion, self).__init__(title, **kwargs)
        self.FunctionName = Ref(name)


class LambdaFunction(lbd.Function):
    def setup(self, key, name):
        import_name = key['ImportName'] if 'ImportName' in key else name
        self.Code = lbd.Code(
            ZipFile=Join('', import_lambda(import_name))
        )
        auto_get_props(self, key)
        self.FunctionName = Sub('${AWS::StackName}-${EnvRole}-' + name)
        if 'Handler' not in key:
            self.Handler = 'index.lambda_handler'
        self.Role = GetAtt('RoleLambda' + name, 'Arn')

        if all(k in key for k in ['SecurityGroupIds', 'SubnetIds']):
            self.VpcConfig = lbd.VPCConfig('')
            auto_get_props(self.VpcConfig, key, mapname=self.title)

        if 'Variables' in key:
            self.Environment = lbd.Environment(
                Variables={
                    varname: get_endvalue(self.title + 'Variables' + varname) for varname in key['Variables']
                }
            )
##
##

class LBD_Lambdas(object):
    def __init__(self, key):
        # Resources
        for n, v in getattr(cfg, key).iteritems():
            resname = key + n
            r_Lambda = LambdaFunction(resname)
            r_Lambda.setup(key=v, name=n)

            if 'Enabled' in v:
                # conditions
                do_no_override(True)
                c_Lambda = {resname: Not(
                    Equals(get_endvalue(resname + 'Enabled'), 'None')
                )}

                add_obj(c_Lambda)
                do_no_override(False)

                r_Lambda.Condition = resname
            if 'Version' in v:
                versionname = resname + 'Version'
                # parameters
                p_Version = Parameter(versionname)
                p_Version.Description = 'LambdaVersion change between A/B to force deploy new version'
                p_Version.AllowedValues = ['', 'A', 'B']
                p_Version.Default = ''

                add_obj(p_Version)

                # conditons
                do_no_override(True)
                c_VersionA = {versionname + 'A': Equals(
                    Ref(resname + 'Version'), 'A'
                )}
                
                c_VersionB = {versionname + 'B': Equals(
                    Ref(resname + 'Version'), 'B'
                )}
                c_Version = {versionname: Or(
                    Condition(versionname + 'A'),
                    Condition(versionname + 'B'),
                )}
                

                add_obj([
                    c_VersionA,
                    c_VersionB,
                    c_Version,
                ])
                do_no_override(False)

                # resources
                r_VersionA = LambdaVersion(versionname + 'A', name=resname )
                r_VersionA.Condition = versionname + 'A'
                
                r_VersionB = LambdaVersion(versionname + 'B', name=resname )
                r_VersionB.Condition = versionname + 'B'

                add_obj([
                    r_VersionA,
                    r_VersionB,
                ])

                # output
                o_Version = Output(versionname)
                o_Version.Value = If(
                    versionname + 'A',
                    Ref(versionname + 'A'),
                    Ref(versionname + 'B')
                )
                o_Version.Condition = versionname
                
                add_obj([
                    o_Version,
                ])

            # Automatically setup a lambda Role with base permissions.
            r_Role = IAMRoleLambdaBase('Role' + resname)
            r_Role.setup(key=v)
            if hasattr(r_Lambda, 'Condition'):
            	r_Role.Condition = r_Lambda.Condition

            add_obj([
                r_Lambda,
                r_Role,
            ])

            if 'Export' in v and v['Export']:
                O_Lambda = Output(resname)
                O_Lambda.Value = GetAtt(resname, 'Arn')
                O_Lambda.Export = Export(resname)

                add_obj(O_Lambda)

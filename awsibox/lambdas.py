import troposphere.awslambda as lbd

from shared import *


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
        auto_get_props(self, key)
        import_name = key['ImportName'] if 'ImportName' in key else name
        self.Code = lbd.Code(
            ZipFile=Join('', import_lambda(import_name))
        )
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
                    varname: get_final_value(self.title + 'Variables' + varname) for varname in key['Variables']
                }
            )
##
##

class LBD_Lambdas(object):
    def __init__(self, key):
        # Resources
        for n, v in RP_cmm[key].iteritems():
            resname = key + n
            r_Lambda = LambdaFunction(resname)
            r_Lambda.setup(key=v, name=n)

            if 'Enabled' in v:
                # conditions
                do_no_override(True)
                c_Lambda = {resname: Not(
                    Equals(get_final_value(resname + 'Enabled'), 'None')
                )}

                cfg.Conditions.append(c_Lambda)
                do_no_override(False)

                r_Lambda.Condition = resname
            if 'Version' in v:
                versionname = resname + 'Version'
                # parameters
                p_Version = Parameter(versionname)
                p_Version.Description = 'LambdaVersion change between A/B to force deploy new version'
                p_Version.AllowedValues = ['', 'A', 'B']
                p_Version.Default = ''

                cfg.Parameters.append(p_Version)

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
                

                cfg.Conditions.extend([
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

                cfg.Resources.extend([
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
                
                cfg.Outputs.extend([
                    o_Version,
                ])

            r_Role = IAMRoleLambdaBase('Role' + resname)
            r_Role.setup(key=v)
            if hasattr(r_Lambda, 'Condition'):
            	r_Role.Condition = r_Lambda.Condition

            cfg.Resources.extend([
                r_Lambda,
                r_Role,
            ])

            if 'Export' in v and v['Export']:
                O_Lambda = Output(resname)
                O_Lambda.Value = GetAtt(resname, 'Arn')
                O_Lambda.Export = Export(resname)

                cfg.Outputs.append(O_Lambda)


# Need to stay as last lines
import_modules(globals())

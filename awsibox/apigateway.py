import troposphere.apigateway as agw

from shared import *
from collections import OrderedDict, Mapping

class ApiGatewayAccount(agw.Account):
    def setup(self):
        self.CloudWatchRoleArn = get_exported_value('RoleApiGatewayCloudWatch')


class ApiGatewayResource(agw.Resource):
    def setup(self, key, stage):
        mapname = 'ApiGatewayStage' + stage + 'ApiGatewayResource'
        stagekey = RP_cmm['ApiGatewayStage'][stage]['ApiGatewayResource']
        auto_get_props(self, key)
        self.RestApiId = Ref('ApiGatewayRestApi')
        auto_get_props(self, stagekey, mapname=mapname, recurse=True, rootkey=key, rootname=self.title)


class ApiGatewayMethod(agw.Method):
    def setup(self, key, basename, name, stage):
        mapname = 'ApiGatewayStage' + stage + 'ApiGatewayResource' + basename + 'Method' + name
        stagekey = RP_cmm['ApiGatewayStage'][stage]['ApiGatewayResource'][basename]['Method'][name] 
        auto_get_props(self, key, recurse=True)
        self.RestApiId = Ref('ApiGatewayRestApi')
        self.ResourceId = Ref('ApiGatewayResource' + basename)
        auto_get_props(self, stagekey, mapname=mapname, recurse=True, rootkey=key, rootname=self.title)
        # If Uri is a lambda get same stage version lambda name Ex. LambdaPaidApiv1
        if ':lambda:' in self.Integration.Uri:
            st = self.Integration.Uri
            l = st.rfind('.')
            self.Integration.Uri = Sub(st[0:l] + stage + st[l:])


class ApiGatewayStage(agw.Stage):
    def setup(self, name, key):
        self.StageName = name
        auto_get_props(self, key, recurse=True)
        self.RestApiId = Ref('ApiGatewayRestApi')
        self.DeploymentId = Ref('ApiGatewayDeployment' + name)


class ApiGatewayDeployment(agw.Deployment):
    def setup(self, name, key):
        lastresource = next(reversed(RP_cmm['ApiGatewayResource']))
        lastmethod = next(reversed(RP_cmm['ApiGatewayResource'][lastresource]['Method']))
        self.DependsOn = 'ApiGatewayResource' + lastresource + 'Method' + lastmethod
        self.Description = Ref('Deployment' + name + 'Description')
        self.RestApiId = Ref('ApiGatewayRestApi')


class AGW_Stages(object):
    def __init__(self, key):
        for n, v in RP_cmm[key].iteritems():
            # parameters
            p_DeploymentDescription = Parameter('Deployment' + n + 'Description')
            p_DeploymentDescription.Description = 'Deployment' + n + ' Description'
            p_DeploymentDescription.Default = n

            cfg.Parameters.extend([
                p_DeploymentDescription,
            ])

            # resources
            resname = key + n
            r_Stage = ApiGatewayStage(resname)
            r_Stage.setup(name=n, key=v)

            r_Deployment = ApiGatewayDeployment('ApiGatewayDeployment' + n)
            r_Deployment.setup(name=n, key=v)

            cfg.Resources.extend([
                r_Stage,
                r_Deployment,
            ])
       

class AGW_RestApi(object):
    def __init__(self, key):
        # Resources
        R_RestApi = agw.RestApi('ApiGatewayRestApi')
        auto_get_props(R_RestApi, RP_cmm, mapname='')

        R_Account = ApiGatewayAccount('ApiGatewayAccount')
        R_Account.setup()

        cfg.Resources.extend([
            R_RestApi,
            R_Account,
        ])

        for n, v in RP_cmm[key].iteritems():
            resname = key + n
            agw_stage = RP_cmm['Stage']
            r_Resource = ApiGatewayResource(resname)
            r_Resource.setup(key=v, stage=agw_stage)

            for m, w in v['Method'].iteritems():
                r_Method = ApiGatewayMethod(resname + 'Method' + m)
                r_Method.setup(key=w, basename=n, name=m, stage=agw_stage)

                cfg.Resources.extend([
                    r_Resource,
                    r_Method,
                ])

        for l, w in RP_cmm['Lambda'].iteritems():
            r_LambdaPermission = LambdaPermissionApiGateway('LambdaPermission' + l)
            r_LambdaPermission.setup(
                name=Ref('Lambda' + l),
                source=Sub('arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiGatewayRestApi}/*/*/*')
            )

            cfg.Resources.append(r_LambdaPermission)



# Need to stay as last lines
import_modules(globals())

import troposphere.codedeploy as cdd

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj)


class CDEc2TagFilters(cdd.Ec2TagFilters):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.Key = 'EnvStackName'
        self.Type = 'KEY_AND_VALUE'
        self.Value = Ref('AWS::StackName')


class CDDeploymentGroup(cdd.DeploymentGroup):
    def __init__(self, title, index, **kwargs):
        super().__init__(title, **kwargs)

        appreponame = f'Apps{index}RepoName'
        appenvname = f'EnvApp{index}Version'
        self.Condition = 'DeploymentGroup'
        self.ApplicationName = get_endvalue(appreponame)

        # Uncomment for old behaviour where codedeploy prepare at boot
        # autoscalinggroup's instances (do not work with autospot)
        # self.AutoScalingGroups = If(
        #    'DeployRevision',
        #    [Ref('AutoScalingGroup')],
        #    Ref('AWS::NoValue')
        # )

        # AUTOSPOT - Use Ec2TagFilters
        # to let it work with instances launched by autospot
        self.Ec2TagFilters = If(
            'DeployRevision',
            [CDEc2TagFilters('')],
            Ref('AWS::NoValue')
        )
        self.Deployment = If(
            'DeployRevision',
            cdd.Deployment(
                Revision=cdd.Revision(
                    RevisionType='S3',
                    S3Location=cdd.S3Location(
                        Bucket=Sub(cfg.BucketAppRepository),
                        BundleType='tgz',
                        Key=get_subvalue(
                            '${1M}/${1M}-${%s}.tar.gz'
                            % appenvname, appreponame)
                    )
                )
            ),
            Ref('AWS::NoValue')
        )
        self.DeploymentGroupName = Sub('${AWS::StackName}.${EnvRole}')
        self.ServiceRoleArn = get_expvalue('RoleCodeDeploy', '')


def CD_DeploymentGroup():
    # Conditions
    add_obj([
        {'DeploymentGroup': And(
            Condition('Apps1'),
            get_condition('', 'equals', True, 'DeploymentGroup')
        )},
        {'DeployRevision': Equals(Ref('UpdateMode'), 'CodeDeploy')}])

    # Resources
    # FOR SINGLEAPP CODEDEPLOY
    if len(cfg.Apps) == 1:
        R_DeploymentGroup = CDDeploymentGroup('DeploymentGroup', index=1)

        add_obj(R_DeploymentGroup)


def CD_Applications(key):
    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'
        App = cdd.Application(resname)
        App.ApplicationName = get_endvalue(resname)

        add_obj(App)

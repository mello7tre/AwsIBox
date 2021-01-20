import troposphere.s3 as s3

from .common import *
from .shared import (Parameter, get_endvalue, get_expvalue, get_subvalue,
                     auto_get_props, get_condition, add_obj, get_dictvalue)
from .iam import (IAMRoleBucketReplica, IAMPolicyBucketReplica,
                  IAMPolicyStatement)
from .cloudfront import CFOriginAccessIdentity
from .lambdas import LambdaPermissionS3


class S3Bucket(s3.Bucket):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)

        name = self.title  # Ex. BucketStatic
        # need to specify key cause there is a problem regarind Bucket Names
        # key in common.yml and Bucket dict (RP_to_cfg)
        auto_get_props(self, key=key)
        self.Condition = name
        self.BucketName = Sub(bucket_name)
        self.CorsConfiguration = If(
            f'{name}Cors',
            s3.CorsConfiguration(
                CorsRules=[
                    s3.CorsRules(
                        AllowedHeaders=['Authorization'],
                        AllowedMethods=['GET'],
                        AllowedOrigins=['*'],
                        MaxAge=3000
                    )
                ]
            ),
            Ref('AWS::NoValue')
        )

        self.VersioningConfiguration = If(
            f'{name}Versioning',
            s3.VersioningConfiguration(
                Status=get_endvalue(f'{name}Versioning')
            ),
            Ref('AWS::NoValue')
        )


class S3BucketPolicy(s3.BucketPolicy):
    def __init__(self, title, key, **kwargs):
        super().__init__(title, **kwargs)

        if 'Condition' in key:
            self.Condition = key['Condition']
        self.PolicyDocument = {
            'Version': '2012-10-17',
        }


def S3BucketPolicyStatementBase(bucket):
    statements = []
    statements.append({
        'Action': [
            's3:GetBucketLocation'
        ],
        'Effect': 'Allow',
        'Resource': Sub('arn:aws:s3:::%s' % bucket_name),
        'Principal': {
            'AWS': Sub('arn:aws:iam::${AWS::AccountId}:root')
        },
        'Sid': 'Base'
    })

    return statements


def S3BucketPolicyStatementReplica(bucket, resource):
    statements = []
    if_statements = []
    condition = f'{bucket}PolicyStatementReplicaPrincipal'
    statements.append({
        'Action': [
            's3:ReplicateObject',
            's3:ReplicateDelete',
            's3:ObjectOwnerOverrideToBucketOwner',
            ],
        'Effect': 'Allow',
        'Resource': resource,
        'Principal': {
            'AWS': [
                get_subvalue(
                    'arn:aws:iam::${1M}:root',
                    f'{bucket}PolicyStatementReplicaPrincipal')
            ]
        },
        'Sid': 'AllowReplica'
    })

    for s in statements:
        if_statements.append(
            If(
                condition,
                s,
                Ref('AWS::NoValue')
            )
        )

    return if_statements


def S3BucketPolicyStatementAllowGetObject(bucket, principal, sid):
    statements = []
    statements.append(
        {
            'Action': [
                's3:GetObject'
            ],
            'Effect': 'Allow',
            'Resource': [
                Sub('arn:aws:s3:::%s/*' % bucket_name)
            ],
            'Principal': {
                'AWS': principal
            },
            'Sid': sid
        },
    )

    return statements


def S3BucketPolicyStatementSes(bucket):
    statements = []
    statements.append(
        {
            'Action': [
                's3:PutObject'
            ],
            'Effect': 'Allow',
            'Resource': [
                Sub('arn:aws:s3:::%s/*' % bucket_name)
            ],
            'Principal': {
                'Service': 'ses.amazonaws.com'
            },
            'Condition': {
                'StringEquals': {
                    'aws:Referer': Ref('AWS::AccountId')
                },
            },
            'Sid': 'AllowSES'
        },
    )

    return statements


def S3BucketPolicyStatementRead(bucket, principal):
    statements = []
    if_statements = []
    condition = f'{bucket}PolicyRead'
    statements.append({
        'Action': [
            's3:ListBucket',
            's3:GetBucketLocation',
            's3:ListBucketMultipartUploads',
            's3:ListBucketVersions'
        ],
        'Effect': 'Allow',
        'Resource': [
            Sub('arn:aws:s3:::%s' % bucket_name)
        ],
        'Principal': {
            'AWS': principal
        },
        'Sid': 'AllowListBucket'
    })
    statements.append({
        'Action': [
            's3:GetObject',
            's3:ListMultipartUploadParts'
        ],
        'Effect': 'Allow',
        'Resource': [
            Sub('arn:aws:s3:::%s/*' % bucket_name)
        ],
        'Principal': {
            'AWS': principal
        },
        'Sid': 'AllowGetObject'
    })

    for s in statements:
        if_statements.append(
            If(
                condition,
                s,
                Ref('AWS::NoValue')
            )
        )

    return if_statements


def S3BucketPolicyStatementWrite(bucket, principal):
    statements = []
    if_statements = []
    condition = f'{bucket}PolicyWrite'
    statements.append({
        'Action': [
            's3:Put*',
        ],
        'Effect': 'Allow',
        'Resource': [
            Sub('arn:aws:s3:::%s/*' % bucket_name)
        ],
        'Principal': {
            'AWS': principal
        },
        'Sid': 'AllowPut'
    })

    for s in statements:
        if_statements.append(
            If(
                condition,
                s,
                Ref('AWS::NoValue')
            )
        )

    return if_statements


def S3_Buckets(key):
    global bucket_name

    for n, v in getattr(cfg, key).items():
        resname = f'{key}{n}'
        name = n
        bucket_name = getattr(cfg, resname)

        PolicyReadConditions = []
        PolicyReadPrincipal = []

        for m, w in v['AccountsRead'].items():
            accountread_name = f'{resname}AccountsRead{m}'
            # conditions
            add_obj(get_condition(accountread_name, 'not_equals', 'None'))

            PolicyReadConditions.append(Condition(accountread_name))
            PolicyReadPrincipal.append(If(
                accountread_name,
                get_subvalue('arn:aws:iam::${1M}:root', accountread_name),
                Ref('AWS::NoValue')
            ))

        # conditions
        if PolicyReadConditions:
            c_PolicyRead = {f'{resname}PolicyRead': Or(
                Equals('1', '0'),
                Equals('1', '0'),
                *PolicyReadConditions
            )}
        else:
            c_PolicyRead = {
                f'{resname}PolicyRead': Equals('True', 'False')}

        PolicyWriteConditions = []
        PolicyWritePrincipal = []

        for m, w in v['AccountsWrite'].items():
            accountwrite_name = f'{resname}AccountsWrite{m}'
            # conditions
            add_obj(get_condition(accountwrite_name, 'not_equals', 'None'))

            PolicyWriteConditions.append(Condition(accountwrite_name))
            PolicyWritePrincipal.append(If(
                accountwrite_name,
                get_subvalue('arn:aws:iam::${1M}:root', accountwrite_name),
                Ref('AWS::NoValue')
            ))

        # conditions
        if PolicyWriteConditions:
            c_PolicyWrite = {f'{resname}PolicyWrite': Or(
                Equals('1', '0'),
                Equals('1', '0'),
                *PolicyWriteConditions
            )}
        else:
            c_PolicyWrite = {
                f'{resname}PolicyWrite': Equals('True', 'False')}

        c_Create = get_condition(
            resname, 'not_equals', 'None', f'{resname}Create')

        c_Versioning = get_condition(
            f'{resname}Versioning', 'not_equals', 'None')

        c_Cors = get_condition(
            f'{resname}Cors', 'not_equals', 'None')

        c_Replica = {f'{resname}Replica': And(
            Condition(resname),
            get_condition(
                '', 'not_equals', 'None', f'{resname}ReplicationEnabled')
        )}
        c_ReplicaPolicyStatement = get_condition(
            f'{resname}PolicyStatementReplicaPrincipal',
            'not_equals', 'None')

        add_obj([
            c_PolicyRead,
            c_PolicyWrite,
            c_Create,
            c_Versioning,
            c_Cors,
            c_Replica,
            c_ReplicaPolicyStatement])

        # resources
        BucketPolicyStatement = []

        r_Bucket = S3Bucket(resname, key=v)

        Replica_Rules = []
        for m, w in v['Replication']['ConfigurationRules'].items():
            replica_name = f'{resname}ReplicationConfigurationRules{m}'

            # parameters
            p_replicabucket = Parameter(
                f'{replica_name}DestinationBucket')
            p_replicabucket.Description = ('Replica Destination Bucket '
                                           '- empty for default based on '
                                           'Env/Roles/Region')
            add_obj(p_replicabucket)

            # conditions
            add_obj([
                get_condition(f'{replica_name}DestinationBucket',
                              'not_equals', 'None')])

            # resources
            rule = s3.ReplicationConfigurationRules(replica_name)
            auto_get_props(rule)

            rule.Status = 'Enabled'
            Replica_Rules.append(If(
                f'{replica_name}DestinationBucket',
                rule,
                Ref('AWS::NoValue')
            ))

        if Replica_Rules:
            ReplicationConfiguration = s3.ReplicationConfiguration(
                '', Role=GetAtt(f'Role{resname}Replica', 'Arn'),
                Rules=Replica_Rules)
            r_Bucket.ReplicationConfiguration = If(
                f'{resname}Replica',
                ReplicationConfiguration,
                Ref('AWS::NoValue'))

        PolicyStatementReplicaResources = []
        for m, w in v['PolicyStatementReplica']['Resource'].items():
            polstatname = f'{resname}PolicyStatementReplicaResource{m}'
            # conditions
            add_obj(
                get_condition(
                    f'{polstatname}Prefix', 'not_equals', 'None'))

            PolicyStatementReplicaResources.append(If(
                f'{polstatname}Prefix',
                get_subvalue('arn:aws:s3:::%s/${1M}*' % bucket_name,
                             f'{polstatname}Prefix'),
                Ref('AWS::NoValue')
            ))

        r_Policy = S3BucketPolicy(f'BucketPolicy{name}', key=v)
        r_Policy.Condition = resname
        r_Policy.Bucket = Sub(bucket_name)
        r_Policy.PolicyDocument['Statement'] = BucketPolicyStatement

        # At least one statement must be always present,
        # create a simple one with no conditions
        BucketPolicyStatement.extend(
            S3BucketPolicyStatementBase(resname))

        BucketPolicyStatement.extend(
            S3BucketPolicyStatementReplica(
                resname, PolicyStatementReplicaResources))

        r_Role = IAMRoleBucketReplica(f'Role{resname}Replica')

        BucketPolicyStatement.extend(
            S3BucketPolicyStatementRead(resname, PolicyReadPrincipal))

        BucketPolicyStatement.extend(
            S3BucketPolicyStatementWrite(resname, PolicyWritePrincipal))

        r_IAMPolicyReplica = IAMPolicyBucketReplica(
            f'IAMPolicyReplicaBucket{name}',
            bucket=resname,
            bucket_name=bucket_name,
            mapname=f'{resname}ReplicationConfigurationRules',
            key=v['Replication']['ConfigurationRules'])

        try:
            lbd_confs = v['NotificationConfiguration']['LambdaConfigurations']
        except Exception:
            pass
        else:
            for lbd_n, lbd_v in lbd_confs.items():
                lambda_arn = eval(lbd_v['Function'])
                if 'Fn::GettAtt' in lambda_arn.data:
                    permname = '%s%s' % (
                        lambda_arn.data['Fn::GettAtt'].replace(
                            'Lambda', 'LambdaPermission'),
                        resname)
                else:
                    permname = 'LambdaPermission'

                r_LambdaPermission = LambdaPermissionS3(
                    permname, key=lambda_arn, source=resname)

                add_obj(r_LambdaPermission)

        try:
            bucket_policies = getattr(cfg, 'BucketPolicy')
        except Exception:
            pass
        else:
            for policy_name, policy_value in bucket_policies.items():
                BucketPolicyStatement.append(get_dictvalue(policy_value))

        if 'WebsiteConfiguration' in v:
            r_Bucket.WebsiteConfiguration = s3.WebsiteConfiguration(
                f'{resname}WebsiteConfiguration')
            auto_get_props(r_Bucket.WebsiteConfiguration)

        if 'PolicyStatement' in v:
            FixedStatements = []
            for fsn, fsv in v['PolicyStatement'].items():
                FixedStatement = IAMPolicyStatement(fsv)
                FixedStatement['Principal'] = {
                    'AWS': eval(fsv['Principal'])
                }
                FixedStatement['Sid'] = fsv['Sid']
                FixedStatements.append(FixedStatement)
            BucketPolicyStatement.extend(FixedStatements)

        if 'PolicyStatementExGetObjectPrincipal' in v:
            BucketPolicyStatement.extend(
                S3BucketPolicyStatementAllowGetObject(
                    resname,
                    get_endvalue(
                        f'{resname}PolicyStatementExGetObjectPrincipal'),
                    'AllowGetObjectExPrincipal'))

        PolicyCloudFrontOriginAccessIdentityPrincipal = []
        if 'CloudFrontOriginAccessIdentity' in v:
            identityname = v['CloudFrontOriginAccessIdentity']
            identityresname = (
                f'CloudFrontOriginAccessIdentity{identityname}')

            PolicyCloudFrontOriginAccessIdentityPrincipal.append(
                Sub('arn:aws:iam::cloudfront:user/'
                    'CloudFront Origin Access Identity ${%s}'
                    % identityresname)
            )

            for ixn, ixv in (
                    v['CloudFrontOriginAccessIdentityExtra'].items()):
                ixname = (
                    f'{resname}CloudFrontOriginAccessIdentityExtra{ixn}')
                # conditions
                add_obj(get_condition(ixname, 'not_equals', 'None'))

                PolicyCloudFrontOriginAccessIdentityPrincipal.append(If(
                    ixname,
                    get_subvalue(
                        'arn:aws:iam::cloudfront:user/'
                        'CloudFront Origin Access Identity ${1M}', ixname),
                    Ref('AWS::NoValue')
                ))

            # conditions
            identitycondname = f'{resname}CloudFrontOriginAccessIdentity'
            c_identity = get_condition(
                identitycondname, 'not_equals', 'None')

            add_obj(c_identity)

            # resources
            BucketPolicyStatement.extend(
                S3BucketPolicyStatementAllowGetObject(
                    resname,
                    PolicyCloudFrontOriginAccessIdentityPrincipal,
                    'AllowCFAccess'))

            r_OriginAccessIdentity = CFOriginAccessIdentity(
                identityresname, comment=identityname)
            r_OriginAccessIdentity.Condition = identitycondname

            add_obj([
                r_OriginAccessIdentity,
            ])

            # outputs
            o_OriginAccessIdentity = Output(identityresname)
            o_OriginAccessIdentity.Value = Ref(identityresname)
            o_OriginAccessIdentity.Condition = identitycondname

            add_obj(o_OriginAccessIdentity)

        add_obj([
            r_Bucket,
            r_Policy,
            r_IAMPolicyReplica,
            r_Role])

        # outputs
        outvaluebase = Sub(bucket_name)
        if 'OutputValueRegion' in v:
            condname = f'{resname}OutputValueRegion'
            # conditions
            add_obj(get_condition(condname, 'not_equals', 'AWSRegion'))

            outvaluebase = If(
                condname,
                Sub('${Region}-%s'
                    % bucket_name.replace('${AWS::Region}-', '', 1),
                    **{'Region': get_endvalue(condname)}),
                outvaluebase
            )

        o_Bucket = Output(resname)
        o_Bucket.Value = If(
            resname,
            Ref(resname),
            outvaluebase
        )
        if resname == 'BucketAppRepository':
            o_Bucket.Export = Export(resname)

        add_obj([
            o_Bucket])

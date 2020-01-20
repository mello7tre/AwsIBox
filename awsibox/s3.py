import troposphere.s3 as s3

from .common import *
from .shared import (Parameter, do_no_override, get_endvalue, get_expvalue,
    get_subvalue, auto_get_props, get_condition, add_obj)
from .iam import IAMRoleBucketReplica, IAMPolicyBucketReplica, IAMPolicyStatement
from .cloudfront import CFOriginAccessIdentity
from .lambdas import LambdaPermissionS3

class S3Bucket(s3.Bucket):
    def setup(self, key):
        name = self.title  # Ex. BucketPortalStatic
        auto_get_props(self, key, recurse=True)
        self.Condition = name
        self.BucketName = Sub(bucket_name)
        self.CorsConfiguration = If(
            name + 'Cors',
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
        self.ReplicationConfiguration = If(
            name + 'Replica',
            s3.ReplicationConfiguration(
                Role=GetAtt('Role' + name + 'Replica', 'Arn'),
                Rules=[
                    s3.ReplicationConfigurationRules(
                        Destination=s3.ReplicationConfigurationRulesDestination(
                            Bucket=get_subvalue(
                                'arn:aws:s3:::${1M}', '%sReplicaDstBucket' % name
                            ) if 'ReplicaDstBucket' in key else get_subvalue(
                                'arn:aws:s3:::${1M}-%s' % bucket_name.replace('${AWS::Region}-', '', 1),
                                '%sReplicaDstRegion' % name,
                            ),
                            AccessControlTranslation=If(
                                name + 'ReplicaDstOwner',
                                s3.AccessControlTranslation(
                                    Owner='Destination'
                                ),
                                Ref('AWS::NoValue')
                            ),
                            Account=If(
                                name + 'ReplicaDstOwner',
                                get_endvalue(name + 'ReplicaDstOwner'),
                                Ref('AWS::NoValue')
                            ),
                        ),
                        Prefix=get_endvalue(name + 'ReplicaDstPrefix') if 'ReplicaDstPrefix' in key else '',
                        Status='Enabled'
                    )
                ]
            ),
            Ref('AWS::NoValue')
        )
        self.VersioningConfiguration = If(
            name + 'Versioning',
            s3.VersioningConfiguration(
                Status=get_endvalue(name + 'Versioning')
            ),
            Ref('AWS::NoValue')
        )


class S3BucketPolicy(s3.BucketPolicy):
    def setup(self, key):
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


def S3BucketPolicyStatementReplica(bucket, key):
    statements = []
    if_statements = []
    condition = bucket  + 'ReplicaSrcAccount'
    statements.append({
        'Action': [
            's3:ReplicateObject',
            's3:ReplicateDelete',
            's3:ObjectOwnerOverrideToBucketOwner',
            ],
        'Effect': 'Allow',
        'Resource': [
            get_subvalue(
                'arn:aws:s3:::%s/${1M}*' % bucket_name,
                bucket + 'ReplicaSrcPrefix'
            ) if 'ReplicaSrcPrefix' in key else Sub('arn:aws:s3:::%s/*' % bucket_name),
        ],
        'Principal': {
            'AWS': [
                get_subvalue('arn:aws:iam::${1M}:root', '%sReplicaSrcAccount' % bucket)
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


def S3BucketPolicyStatementCFOriginAccessIdentity(bucket, principal):
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
            'Sid': 'AllowCFAccess'
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


def S3BucketPolicyStatementRO(bucket, principal):
    statements = []
    if_statements = []
    condition = bucket  + 'PolicyRO'
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


# #################################
# ### START STACK INFRA CLASSES ###
# #################################

class S3_Buckets(object):

    def __init__(self, key):
        global bucket_name

        for n, v in getattr(cfg, key).items():
            if not ('Enabled' in v and v['Enabled'] is True):
                continue
            name = n  # Ex. AppData
            resname = key + name  # Ex. BucketAppData
            bucket_name = getattr(cfg, resname)
            # parameters
            p_ReplicaDstRegion = Parameter(resname + 'ReplicaDstRegion')
            p_ReplicaDstRegion.Description = 'Region to Replicate Bucket - None to disable - empty for default based on env/role'
            p_ReplicaDstRegion.AllowedValues = ['', 'None'] + cfg.regions

            add_obj(p_ReplicaDstRegion)

            PolicyROConditions = []
            PolicyROPrincipal = []

            for m, w in v['AccountsRO'].items():
                accountro_name = resname + 'AccountsRO' + m 
                # conditions
                add_obj(get_condition(accountro_name, 'not_equals', 'None'))

                PolicyROConditions.append(Condition(accountro_name))
                PolicyROPrincipal.append(If(
                    accountro_name,
                    get_subvalue('arn:aws:iam::${1M}:root', accountro_name),
                    Ref('AWS::NoValue')
                ))

            # conditions
            if PolicyROConditions:
                c_PolicyRO = {resname + 'PolicyRO': Or(
                    Equals('1', '0'),
                    Equals('1', '0'),
                    *PolicyROConditions
                )}
            else:
                c_PolicyRO = {resname + 'PolicyRO': Equals('True', 'False')}

            add_obj([
                c_PolicyRO,
                get_condition(resname, 'not_equals', 'None', resname + 'Create'),
                get_condition(resname + 'Versioning', 'not_equals', 'None'),
                get_condition(resname + 'Cors', 'not_equals', 'None'),
                get_condition(resname + 'ReplicaSrcAccount', 'not_equals', 'None'),
                get_condition(resname + 'ReplicaDstOwner', 'not_equals', 'None'),
                #get_condition(resname + 'AccountRO', 'not_equals', 'None'),
                {resname + 'Replica': And(
                    Condition(resname),
                    get_condition('', 'not_equals', 'None', resname + 'ReplicaDstRegion')
                )},
            ])
 
            # resources
            BucketPolicyStatement = []

            r_Bucket = S3Bucket(resname)
            r_Bucket.setup(key=v)

            r_Policy = S3BucketPolicy('BucketPolicy%s' % name)
            r_Policy.setup(key=v)
            r_Policy.Condition = resname
            r_Policy.Bucket = Sub(bucket_name)
            r_Policy.PolicyDocument['Statement'] = BucketPolicyStatement

            # At least one statement must be always present, create a simple one with no conditions
            BucketPolicyStatement.extend(S3BucketPolicyStatementBase(resname))

            BucketPolicyStatement.extend(S3BucketPolicyStatementReplica(resname, v))

            #r_PolicyReplica = S3BucketPolicyStatementReplica('BucketPolicy' + name)
            #r_PolicyReplica.setup(bucket=resname)

            r_Role = IAMRoleBucketReplica('Role' + resname + 'Replica')
            r_Role.setup()

            BucketPolicyStatement.extend(S3BucketPolicyStatementRO(resname, PolicyROPrincipal))

            #r_PolicyRO = S3BucketPolicyRO('BucketPolicy' + name + 'AccountRO')
            #r_PolicyRO.setup(bucket=resname, principal=PolicyROPrincipal)

            r_IAMPolicyReplica = IAMPolicyBucketReplica('IAMPolicyReplicaBucket' + name)
            r_IAMPolicyReplica.setup(bucket=resname, bucket_name=bucket_name, key=v)

            try:
                lambda_arn = eval(
                    v['NotificationConfiguration']['LambdaConfigurations']['Trigger']['Function']
                )
            except:
                pass
            else:
                if 'Fn::GettAtt' in lambda_arn.data:
                    permname = lambda_arn.data['Fn::GettAtt'].replace('Lambda', 'LambdaPermission') + resname
                else:
                    permname = 'LambdaPermission'
                r_LambdaPermission = LambdaPermissionS3(permname)
                r_LambdaPermission.setup(key=lambda_arn, source=resname)

                add_obj(r_LambdaPermission)

                BucketPolicyStatement.extend(S3BucketPolicyStatementSes(resname))

            if 'WebsiteConfiguration' in v:
                r_Bucket.WebsiteConfiguration = s3.WebsiteConfiguration(resname + 'WebsiteConfiguration')
                auto_get_props(r_Bucket.WebsiteConfiguration, v['WebsiteConfiguration'], recurse=True)

            if 'PolicyStatement' in v:
                FixedStatements = []
                for fsn, fsv  in v['PolicyStatement'].items():
                    FixedStatement = IAMPolicyStatement(fsv)
                    FixedStatement['Principal'] = {
                        'AWS': eval(fsv['Principal'])
                    }
                    FixedStatement['Sid'] = fsv['Sid']
                    FixedStatements.append(FixedStatement)
                BucketPolicyStatement.extend(FixedStatements)

            PolicyCloudFrontOriginAccessIdentityPrincipal = []
            if 'CloudFrontOriginAccessIdentity' in v:
                identityname = v['CloudFrontOriginAccessIdentity']  # Ex. Tile
                identityresname = 'CloudFrontOriginAccessIdentity' + identityname
                
                PolicyCloudFrontOriginAccessIdentityPrincipal.append(
                    Sub('arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity ${%s}' % identityresname)
                )

                for ixn, ixv in v['CloudFrontOriginAccessIdentityExtra'].items():
                    ixname = resname + 'CloudFrontOriginAccessIdentityExtra' + ixn
                    # conditions
                    add_obj(get_condition(ixname, 'not_equals', 'None'))

                    PolicyCloudFrontOriginAccessIdentityPrincipal.append(If(
                        ixname,
                        get_subvalue('arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity ${1M}', ixname),
                        Ref('AWS::NoValue')
                    ))

                # resources
                BucketPolicyStatement.extend(
                        S3BucketPolicyStatementCFOriginAccessIdentity(resname, PolicyCloudFrontOriginAccessIdentityPrincipal)
                )

                r_OriginAccessIdentity = CFOriginAccessIdentity(identityresname)
                r_OriginAccessIdentity.setup(comment=identityname)

                #r_PolicyOriginAccess = S3BucketPolicyCFOriginAccessIdentity('BucketPolicyCFOriginAccessIdentity' + identityname)
                #r_PolicyOriginAccess.setup(bucket=resname, identity=identityresname)

                add_obj([
                    r_OriginAccessIdentity,
                    #r_PolicyOriginAccess,
                ])

                # outputs
                o_OriginAccessIdentity = Output(identityresname)
                o_OriginAccessIdentity.Value = Ref(identityresname)

                add_obj(o_OriginAccessIdentity)

            add_obj([
                r_Bucket,
                r_Policy,
                #r_PolicyReplica,
                #r_PolicyRO,
                r_IAMPolicyReplica,
                r_Role
            ])

            # outputs
            outvaluebase = Sub(bucket_name)
            if 'OutputValueRegion' in v:
                condname = resname + 'OutputValueRegion'
                # conditions
                add_obj(get_condition(condname, 'not_equals', 'AWSRegion'))

                outvaluebase = If(
                    condname,
                    Sub('${Region}-%s' % bucket_name.replace('${AWS::Region}-', '', 1), **{'Region': get_endvalue(condname)}),
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
                o_Bucket,
            ])


# no more used
class S3_BucketPolicies(object):
    def __init__(self, key):
        for n, v in getattr(cfg, key).items():
            resname = key + n
            Statements = []
            for m, w  in v['Statement'].items():
                Statement = IAMPolicyStatement(w)
                Statement['Principal'] = {
                    'AWS': eval(w['Principal'])
                }
                Statements.append(Statement)

            r_Policy = S3BucketPolicy(resname)
            r_Policy.setup(key=v)
            r_Policy.Bucket = get_endvalue(resname + 'Bucket')
            r_Policy.PolicyDocument['Statement'] = Statement            

            add_obj(r_Policy)

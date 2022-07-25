import troposphere.s3 as s3

from .common import *
from .shared import (
    Parameter,
    get_endvalue,
    get_expvalue,
    get_subvalue,
    auto_get_props,
    get_condition,
    add_obj,
    get_dictvalue,
)
from .iam import IAMPolicyBucketReplica, IAMPolicyStatement
from .cloudfront import CFOriginAccessIdentity


def S3BucketPolicyStatementAllowGetObject(bucket, principal, sid):
    statement = {
        "Action": ["s3:GetObject"],
        "Effect": "Allow",
        "Resource": [Sub("arn:aws:s3:::%s/*" % bucket_name)],
        "Principal": {"AWS": principal},
        "Sid": sid,
    }

    return statement


def S3_Buckets(key):
    global bucket_name

    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"
        name = n
        bucket_name = getattr(cfg, f"{key}Name{n}")

        ## Policy Read
        PolicyReadConditions = []
        PolicyReadPrincipal = []
        for m, w in v["AccountsRead"].items():
            accountread_name = f"{resname}AccountsRead{m}"
            # conditions
            add_obj(get_condition(accountread_name, "not_equals", "none"))

            PolicyReadConditions.append(Condition(accountread_name))
            PolicyReadPrincipal.append(
                If(
                    accountread_name,
                    get_subvalue("arn:aws:iam::${1M}:root", accountread_name),
                    Ref("AWS::NoValue"),
                )
            )
        # conditions
        if PolicyReadConditions:
            c_PolicyRead = {
                f"{resname}PolicyRead": Or(
                    Equals("1", "0"), Equals("1", "0"), *PolicyReadConditions
                )
            }
        else:
            c_PolicyRead = {f"{resname}PolicyRead": Equals("True", "False")}

        ## Policy Write
        PolicyWriteConditions = []
        PolicyWritePrincipal = []
        for m, w in v["AccountsWrite"].items():
            accountwrite_name = f"{resname}AccountsWrite{m}"
            # conditions
            add_obj(get_condition(accountwrite_name, "not_equals", "none"))

            PolicyWriteConditions.append(Condition(accountwrite_name))
            PolicyWritePrincipal.append(
                If(
                    accountwrite_name,
                    get_subvalue("arn:aws:iam::${1M}:root", accountwrite_name),
                    Ref("AWS::NoValue"),
                )
            )
        # conditions
        if PolicyWriteConditions:
            c_PolicyWrite = {
                f"{resname}PolicyWrite": Or(
                    Equals("1", "0"), Equals("1", "0"), *PolicyWriteConditions
                )
            }
        else:
            c_PolicyWrite = {f"{resname}PolicyWrite": Equals("True", "False")}

        ## Policy Delete
        PolicyDeleteConditions = []
        PolicyDeletePrincipal = []
        for m, w in v["AccountsDelete"].items():
            accountwrite_name = f"{resname}AccountsDelete{m}"
            # conditions
            add_obj(get_condition(accountwrite_name, "not_equals", "none"))

            PolicyDeleteConditions.append(Condition(accountwrite_name))
            PolicyDeletePrincipal.append(
                If(
                    accountwrite_name,
                    get_subvalue("arn:aws:iam::${1M}:root", accountwrite_name),
                    Ref("AWS::NoValue"),
                )
            )
        # conditions
        if PolicyDeleteConditions:
            c_PolicyDelete = {
                f"{resname}PolicyDelete": Or(
                    Equals("1", "0"), Equals("1", "0"), *PolicyDeleteConditions
                )
            }
        else:
            c_PolicyDelete = {f"{resname}PolicyDelete": Equals("True", "False")}

        c_Create = get_condition(resname, "equals", "yes", f"{resname}Create")

        c_Versioning = get_condition(f"{resname}Versioning", "equals", "Enabled")

        c_Cors = get_condition(f"{resname}Cors", "equals", "yes")

        c_Replica = {
            f"{resname}Replica": And(
                Condition(resname),
                get_condition("", "equals", "yes", f"{resname}ReplicationEnabled"),
            )
        }
        c_ReplicaPolicyStatement = get_condition(
            f"{resname}PolicyStatementReplicaPrincipal", "not_equals", "none"
        )

        add_obj(
            [
                c_PolicyRead,
                c_PolicyWrite,
                c_PolicyDelete,
                c_Create,
                c_Versioning,
                c_Cors,
                c_Replica,
                c_ReplicaPolicyStatement,
            ]
        )

        # resources
        r_Bucket = s3.Bucket(resname, BucketName=Sub(bucket_name))
        auto_get_props(r_Bucket)

        Replica_Rules = []
        for m, w in v["Replication"]["ConfigurationRules"].items():
            replica_name = f"{resname}ReplicationConfigurationRules{m}"

            # parameters
            p_replicabucket = Parameter(
                f"{replica_name}DestinationBucket",
                Description="Replica Destination Bucket - empty for default based on Env/Roles/Region",
            )
            add_obj(p_replicabucket)

            # conditions
            add_obj(
                [
                    get_condition(
                        f"{replica_name}DestinationBucket", "not_equals", "none"
                    )
                ]
            )

            # resources
            rule = s3.ReplicationConfigurationRules(replica_name, Status="Enabled")
            auto_get_props(rule)

            Replica_Rules.append(
                If(f"{replica_name}DestinationBucket", rule, Ref("AWS::NoValue"))
            )

        if Replica_Rules:
            ReplicationConfiguration = s3.ReplicationConfiguration(
                "", Role=GetAtt(f"Role{resname}Replica", "Arn"), Rules=Replica_Rules
            )
            r_Bucket.ReplicationConfiguration = If(
                f"{resname}Replica", ReplicationConfiguration, Ref("AWS::NoValue")
            )

        PolicyStatementReplicaResources = []
        for m, w in v["PolicyStatementReplica"]["Resource"].items():
            polstatname = f"{resname}PolicyStatementReplicaResource{m}"
            # conditions
            add_obj(get_condition(f"{polstatname}Prefix", "not_equals", "none"))

            PolicyStatementReplicaResources.append(
                If(
                    f"{polstatname}Prefix",
                    get_subvalue(
                        "arn:aws:s3:::%s/${1M}*" % bucket_name, f"{polstatname}Prefix"
                    ),
                    Ref("AWS::NoValue"),
                )
            )

        r_Policy = s3.BucketPolicy(
            f"BucketPolicy{name}",
            Condition=resname,
            Bucket=Ref(resname),
        )
        # BucketPolicy Statements are read from yaml cfg, so update it with dynamic data
        base_statements = cfg.S3BucketPolicyBasePolicyDocumentStatement
        # At least one statement must be always present, create a simple one with no conditions
        base_statements["AllowReplica"]["Resource"] = PolicyStatementReplicaResources
        base_statements["AllowListBucketGetObject"]["Principal"][
            "AWS"
        ] = PolicyReadPrincipal
        base_statements["AllowPut"]["Principal"]["AWS"] = PolicyWritePrincipal
        base_statements["AllowDelete"]["Principal"]["AWS"] = PolicyDeletePrincipal
        auto_get_props(
            r_Policy,
            mapname="S3BucketPolicyBase",
            linked_obj_name=bucket_name,
            linked_obj_index=resname,
        )

        BucketPolicyStatement = r_Policy.PolicyDocument["Statement"]

        r_IAMPolicyReplica = IAMPolicyBucketReplica(
            f"IAMPolicyReplicaBucket{name}",
            bucket=resname,
            bucket_name=bucket_name,
            mapname=f"{resname}ReplicationConfigurationRules",
            key=v["Replication"]["ConfigurationRules"],
        )

        try:
            bucket_policies = getattr(cfg, "BucketPolicy")
        except Exception:
            pass
        else:
            for policy_name, policy_value in bucket_policies.items():
                BucketPolicyStatement.append(get_dictvalue(policy_value))

        if "WebsiteConfiguration" in v:
            r_Bucket.WebsiteConfiguration = s3.WebsiteConfiguration(
                f"{resname}WebsiteConfiguration"
            )
            auto_get_props(r_Bucket.WebsiteConfiguration)

        if "PolicyStatement" in v:
            FixedStatements = []
            for fsn, fsv in v["PolicyStatement"].items():
                FixedStatement = IAMPolicyStatement(fsv)
                FixedStatement["Principal"] = {"AWS": eval(fsv["Principal"])}
                FixedStatement["Sid"] = fsv["Sid"]
                FixedStatements.append(FixedStatement)
            BucketPolicyStatement.extend(FixedStatements)

        if "PolicyStatementExGetObjectPrincipal" in v:
            BucketPolicyStatement.append(
                S3BucketPolicyStatementAllowGetObject(
                    resname,
                    get_endvalue(f"{resname}PolicyStatementExGetObjectPrincipal"),
                    "AllowGetObjectExPrincipal",
                )
            )

        PolicyCloudFrontOriginAccessIdentityPrincipal = []
        if "CloudFrontOriginAccessIdentity" in v:
            identityname = v["CloudFrontOriginAccessIdentity"]
            identityresname = f"CloudFrontOriginAccessIdentity{identityname}"

            PolicyCloudFrontOriginAccessIdentityPrincipal.append(
                Sub(
                    "arn:aws:iam::cloudfront:user/"
                    "CloudFront Origin Access Identity ${%s}" % identityresname
                )
            )

            for ixn, ixv in v["CloudFrontOriginAccessIdentityExtra"].items():
                ixname = f"{resname}CloudFrontOriginAccessIdentityExtra{ixn}"
                # conditions
                add_obj(get_condition(ixname, "not_equals", "none"))

                PolicyCloudFrontOriginAccessIdentityPrincipal.append(
                    If(
                        ixname,
                        get_subvalue(
                            "arn:aws:iam::cloudfront:user/"
                            "CloudFront Origin Access Identity ${1M}",
                            ixname,
                        ),
                        Ref("AWS::NoValue"),
                    )
                )

            # conditions
            identitycondname = f"{resname}CloudFrontOriginAccessIdentity"
            c_identity = {
                identitycondname: And(
                    Condition(resname),
                    get_condition("", "not_equals", "none", identitycondname),
                )
            }

            add_obj(c_identity)

            # resources
            BucketPolicyStatement.append(
                S3BucketPolicyStatementAllowGetObject(
                    resname,
                    PolicyCloudFrontOriginAccessIdentityPrincipal,
                    "AllowCFAccess",
                )
            )

            r_OriginAccessIdentity = CFOriginAccessIdentity(
                identityresname, comment=identityname, Condition=identitycondname
            )

            add_obj(r_OriginAccessIdentity)

            # outputs
            o_OriginAccessIdentity = Output(
                identityresname, Value=Ref(identityresname), Condition=identitycondname
            )

            add_obj(o_OriginAccessIdentity)

        add_obj([r_Bucket, r_Policy, r_IAMPolicyReplica])

        # outputs
        o_Bucket = Output(resname)
        outvalue = If(resname, Ref(resname), Sub(bucket_name))
        if "OutputValueRegion" in v:
            condname = f"{resname}OutputValueRegion"
            # conditions
            add_obj(get_condition(condname, "not_equals", "AWSRegion"))

            outvalue = If(
                condname,
                Sub(
                    "${Region}-%s" % bucket_name.replace("${AWS::Region}-", "", 1),
                    **{"Region": get_endvalue(condname)},
                ),
                outvalue,
            )
            o_Bucket.Export = Export(resname)
        else:
            o_Bucket.Condition = resname

        o_Bucket.Value = outvalue

        add_obj([o_Bucket])

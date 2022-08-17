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
from .cloudfront import CFOriginAccessIdentity


def S3_Buckets(key):
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"
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

        add_obj([c_PolicyRead, c_PolicyWrite, c_PolicyDelete])

        # resources
        r_Bucket = s3.Bucket(resname)
        auto_get_props(r_Bucket, remapname=bucket_name, indexname=n)

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
            f"BucketPolicy{n}",
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

        # BucketPolicy key
        if "BucketPolicy" in v:
            for _, bp in v["BucketPolicy"].items():
                BucketPolicyStatement.append(get_dictvalue(bp))

        # Policy CloudFrontOriginAccessIdentity
        PolicyStatementCloudFrontOriginAccessIdentityPrincipal = getattr(
            cfg,
            f"{resname}PolicyStatementCloudFrontOriginAccessIdentityPrincipal",
            None,
        )
        if isinstance(PolicyStatementCloudFrontOriginAccessIdentityPrincipal, list):
            # resources
            BucketPolicyStatement.append(
                {
                    "Action": ["s3:GetObject"],
                    "Effect": "Allow",
                    "Resource": [Sub("arn:aws:s3:::%s/*" % bucket_name)],
                    "Principal": {
                        "AWS": PolicyStatementCloudFrontOriginAccessIdentityPrincipal
                    },
                    "Sid": "AllowCFAccess",
                }
            )

        PolicyCloudFrontOriginAccessIdentityPrincipal = []
        if "CloudFrontOriginAccessIdentity_NO" in v:
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

            r_OriginAccessIdentity = CFOriginAccessIdentity(
                identityresname, comment=identityname, Condition=identitycondname
            )

            add_obj(r_OriginAccessIdentity)

            # outputs
            o_OriginAccessIdentity = Output(
                identityresname, Value=Ref(identityresname), Condition=identitycondname
            )

            add_obj(o_OriginAccessIdentity)

        add_obj([r_Bucket, r_Policy])

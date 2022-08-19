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


def S3_Buckets(key):
    for n, v in getattr(cfg, key).items():
        resname = f"{key}{n}"
        bucket_name = getattr(cfg, f"{key}Name{n}")

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
        base_statements["AllowListBucketGetObject"]["Principal"]["AWS"] = getattr(
            cfg, f"{resname}PolicyStatementAccountsReadPrincipal"
        )
        base_statements["AllowPut"]["Principal"]["AWS"] = getattr(
            cfg, f"{resname}PolicyStatementAccountsWritePrincipal"
        )
        base_statements["AllowDelete"]["Principal"]["AWS"] = getattr(
            cfg, f"{resname}PolicyStatementAccountsDeletePrincipal"
        )
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

        add_obj([r_Bucket, r_Policy])

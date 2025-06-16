#!/bin/bash -eux
ENV=_IBOX_CODE_Ref('Env')_IBOX_CODE_
ENVABBR=_IBOX_CODE_Ref('EnvShort')_IBOX_CODE_
ENVACCOUNTID=_IBOX_CODE_Ref("AWS::AccountId")_IBOX_CODE_
ENVROLE=_IBOX_CODE_Ref('EnvRole')_IBOX_CODE_
ENVBRAND=_IBOX_CODE_str(cfg.BrandDomain)_IBOX_CODE_
STACKNAME=_IBOX_CODE_Ref('AWS::StackName')_IBOX_CODE_
REGION=_IBOX_CODE_Ref('AWS::Region')_IBOX_CODE_
SIGNAL=_IBOX_CODE_If('DoNotSignal', '', 'yes')_IBOX_CODE_

IMDSV2_TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -H "X-aws-ec2-metadata-token: $IMDSV2_TOKEN" -s http://169.254.169.254/latest/meta-data/instance-id)


SIGNAL(){
  case $? in
    0)
     status=SUCCESS
     ;;
    *)
     status=FAILURE
     ;;
  esac
  # avoid exiting with error if stack is in UPDATE_COMPLETE state and cannot be signaled
  aws --region $REGION cloudformation signal-resource --stack-name $STACKNAME --logical-resource-id AutoScalingGroup --unique-id $INSTANCE_ID --status $status || :
  if [ "$status" = "FAILURE" ];then
    shutdown -h now
  fi

}

if [ -n "$SIGNAL" ];then
  trap SIGNAL EXIT ERR
fi

cat > /etc/profile.d/ibox_env.sh << EOF
#setup ibox environment variables
export Env=${ENV}
export EnvAbbr=${ENVABBR}
export EnvRegion=${REGION}
export EnvAccountId=${ENVACCOUNTID}
export EnvRole=${ENVROLE}
export EnvBrand=${ENVBRAND}
export EnvStackName=${STACKNAME}
EOF
export BASH_ENV=/etc/profile.d/ibox_env.sh
export ENV=$BASH_ENV

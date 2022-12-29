#!/bin/bash -eu
ENV=_IBOX_CODE_Ref('Env')_IBOX_CODE_
ENVABBR=IBOX_CODE_Ref('EnvShort')_IBOX_CODE_
ENVACCOUNTID=IBOX_CODE_Ref('AccountId')_IBOX_CODE_
ENVROLE=IBOX_CODE_Ref('EnvRole')_IBOX_CODE_
ENVBRAND=_IBOX_CODE_str(cfg.BrandDomain)_IBOX_CODE_
STACKNAME=_IBOX_CODE_Ref('AWS::StackName')_IBOX_CODE_
REGION=_IBOX_CODE_Ref('AWS::Region')_IBOX_CODE_
ADDITIONALSTORAGEMOUNT=_IBOX_CODE_If('LaunchTemplateDataBlockDeviceMappingsAdditionalStorageMount', 'yes', '')_IBOX_CODE_
ADDITIONALSTORAGEDEVICENAME=_IBOX_CODE_get_endvalue('LaunchTemplateDataBlockDeviceMappingsAdditionalStorageDeviceName')_IBOX_CODE_
ADDITIONALSTORAGEEBSVOLUMESIZE=_IBOX_CODE_get_endvalue('LaunchTemplateDataBlockDeviceMappingsAdditionalStorageEbsVolumeSize')_IBOX_CODE_
DOEFSMOUNTS=_IBOX_CODE_If('EfsMounts', 'yes', '')_IBOX_CODE_
EFSMOUNTS=_IBOX_CODE_Join(' ', Ref('EfsMounts'))_IBOX_CODE_
HOSTEDZONENAMEPRIVATE=_IBOX_CODE_str(cfg.HostedZoneNamePrivate)_IBOX_CODE_

SETUP(){
  cat >> /etc/profile.d/ibox_env.sh << EOF
#setup ibox environment variables
export Env=${ENV}
export EnvAbbr=${ENVABBR}
export EnvRegion=${REGION}
export EnvAccountId=${ENVACCOUNTID}
export EnvRole=${ENVROLE}
export EnvBrand=${ENVBRAND}
export EnvStackName=${STACKNAME}
EOF

  # setup main disk
  n=0
  for disk in /dev/xvd[b-d]; do
    [ -b "$disk" ] || continue
    file -s "$disk" | grep -q "ext[34] filesystem" || { mkfs.ext4 $disk || continue; }
    mkdir -p /media/ephemeral${n} && mount $disk /media/ephemeral${n}
    n=$(($n+1))
  done

  # setup additional disk
  if [ -n "$ADDITIONALSTORAGEMOUNT" ];then
    file -s ${ADDITIONALSTORAGEDEVICENAME}1 | grep -q "ext[34] filesystem" || \
      { parted -s ${ADDITIONALSTORAGEDEVICENAME} mklabel gpt && \
      parted -s ${ADDITIONALSTORAGEDEVICENAME} mkpart primary ext2 1 ${ADDITIONALSTORAGEEBSVOLUMESIZE}G && \
      mkfs.ext4 ${ADDITIONALSTORAGEDEVICENAME}1 || continue; }
    mkdir -p /data && mount ${ADDITIONALSTORAGEDEVICENAME}1 /data
  fi

  # setup efs mount
  if [ -n "$DOEFSMOUNTS" ];then
    mount_opt="nfsvers=4,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2"
    for mounts in $EFSMOUNTS ;do
      mkdir -p "/media/${mounts}"
      mountpoint -q "/media/${mounts}" || \
        mount -t nfs4 -o $mount_opt "efs-${mounts}.${HOSTEDZONENAMEPRIVATE}:/" /media/${mounts}
    done
  fi

  # clean up
  rm -fr /tmp/ibox
}

SETUP(){
  ADDITIONALSTORAGEMOUNT=_IBOX_CODE_If('LaunchTemplateDataBlockDeviceMappingsAdditionalStorageMount', 'yes', '')_IBOX_CODE_
  ADDITIONALSTORAGEDEVICENAME=_IBOX_CODE_get_endvalue('LaunchTemplateDataBlockDeviceMappingsAdditionalStorageDeviceName')_IBOX_CODE_
  ADDITIONALSTORAGEVOLUMESIZE=_IBOX_CODE_get_endvalue('LaunchTemplateDataBlockDeviceMappingsAdditionalStorageEbsVolumeSize')_IBOX_CODE_
  EFSMOUNTS=_IBOX_CODE_If('EfsMounts', Join(' ', Ref('EfsMounts')), '')_IBOX_CODE_
  HOSTEDZONENAMEPRIVATE=_IBOX_CODE_str(cfg.HostedZoneNamePrivate)_IBOX_CODE_

  # setup main disk - currently disabled
  if [ "${EC2INSTANCEAUTOFORMATEXT4:-no}" = "yes" ];then
    n=0
    for disk in /dev/xvd[b-d]; do
      [ -b "$disk" ] || continue
      file -s "$disk" | grep -q "ext[34] filesystem" || { mkfs.ext4 $disk || continue; }
      mkdir -p /media/ephemeral${n} && mount $disk /media/ephemeral${n}
      n=$(($n+1))
    done
  fi

  # setup additional disk
  if [ -n "$ADDITIONALSTORAGEMOUNT" ];then
    file -s ${ADDITIONALSTORAGEDEVICENAME}1 | grep -q "ext[34] filesystem" || \
      { parted -s ${ADDITIONALSTORAGEDEVICENAME} mklabel gpt && \
      parted -s ${ADDITIONALSTORAGEDEVICENAME} mkpart primary ext2 1 ${ADDITIONALSTORAGEVOLUMESIZE}G && \
      mkfs.ext4 ${ADDITIONALSTORAGEDEVICENAME}1 || continue; }
    mkdir -p /data && mount ${ADDITIONALSTORAGEDEVICENAME}1 /data
  fi

  # setup efs mount
  if [ -n "$EFSMOUNTS" ];then
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

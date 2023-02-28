LOADBALANCERTYPE=_IBOX_CODE_getattr(cfg, 'LoadBalancerType')_IBOX_CODE_
#### IBOX USER-DATA END ####
PACKAGE
if [ "$(type -t PACKAGE_EXT)" = "function" ];then
  PACKAGE_EXT
fi

SETUP

if [ "$(type -t APP_EXT)" = "function" ];then
  APP_EXT
fi

SERVICE
if [ "$(type -t SERVICE_EXT)" = "function" ];then
  SERVICE_EXT
elif [ "$(type -t SERVICE_ROLE)" = "function" ];then
  SERVICE_ROLE
fi

if [ "${ELBCHECK:-yes}" = "yes" ];then
  if [ "$LOADBALANCERTYPE" = "Classic" ];then
    ELBCLASSIC
  else
    ELBV2
  fi
fi

if [ "$(type -t FINAL_EXT)" = "function" ];then
  FINAL_EXT
fi
# Uncomment to re-execute user-data if instance reboot
# rm /var/lib/cloud/instance/sem/config_scripts_user

HELPER_INSTALL(){
  PKGS=$@
  INSTALLED=$(yum list installed | egrep -o "^($(echo $PKGS | tr " " "|"))\." | tr -d "." | tr "\n" "|")
  if [ -n "$INSTALLED" ];then
    TO_INSTALL=$(echo "$PKGS" | tr " " "\n" | egrep -v "${INSTALLED%?}") || :
  else
    TO_INSTALL=$PKGS
  fi
  if [ -n "$TO_INSTALL" ];then
    yum install -y $TO_INSTALL
  fi
}

PACKAGE(){
  CLOUDWATCH=_IBOX_CODE_If('CloudWatchAgent', 'CWAGENT', '')_IBOX_CODE_
  CODEDEPLOY=_IBOX_CODE_Join("", [If('DeploymentGroup', 'yes', '')] if getattr(cfg, 'DeploymentGroup', False) else [''])_IBOX_CODE_

  if [ -n "$CLOUDWATCH" ];then
    HELPER_INSTALL amazon-cloudwatch-agent
  fi

  if [ -n "$CODEDEPLOY" ];then
    curl "https://aws-codedeploy-${REGION}.s3.amazonaws.com/latest/install" -o /tmp/codedeployinstall.sh && \
      chmod +x /tmp/codedeployinstall.sh && /tmp/codedeployinstall.sh auto && \
      service codedeploy-agent disable
  fi
}

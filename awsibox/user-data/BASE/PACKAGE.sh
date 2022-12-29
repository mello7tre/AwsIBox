HELPER_INSTALL(){
  PKGS=$@
  INSTALLED=$(yum list installed | egrep -o "^($(echo $PKGS | tr " " "|"))\." | tr -d "." | tr "\n" "|")
  if [ -n "$INSTALLED" ];then
    TO_INSTALL=$(echo "$PKGS" | tr " " "\n" | egrep -v "${INSTALLED%?}")
  else
    TO_INSTALL=$PKGS
  fi
  if [ -n "$TO_INSTALL" ];then
    yum install -y $TO_INSTALL
  fi
}

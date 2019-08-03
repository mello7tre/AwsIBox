#!/bin/bash
BRAND_GENERATE=ALL
GENERATE_PRG='ibox_generate_template.py'
CFG_DIR_BASE="$(pip show awsibox|grep -Po "Location: \K.*")/awsibox/cfg"
CFG_DIR_EXT='cfg'
BRANDS="$(ls ${CFG_DIR_EXT}/|egrep -v "^BASE$")"
BRANDS_HELP=$(echo "$BRANDS"|tr "\n" "|"|sed 's#|$##')
EGREP_OPTS="-Rl --exclude *.swp --exclude-dir UNUSED"
BRAND_ACCOUNT=$(echo "${AWS_DEFAULT_PROFILE:-$AWS_PROFILE}" | grep -Po "ibox-\K.+(?=-.*)")
BRAND_UPLOAD=$BRAND_ACCOUNT

myopts(){
  usage="Usage: `basename $0` [options]
  		-r Double Quoted Space Separeted Role/s or 'all'
		-t Double Quoted Space Separeted StackTypes based on which build relative role templates
		-b Brand Upload ($BRANDS_HELP) [default=${BRAND_ACCOUNT}]
		-B Brand Generate (ALL|$BRANDS_HELP) [default=ALL]
		-g Double Quoted git comment to automatically commit
		-u Upload git commit
		-T Tag to build [latest]
		-c Compress jsons before upload - need jq
		-s Show only Tag on S3
		-h help
"
   while getopts ":hcug:r:t:b:B:T:s" opt; do
     case $opt in
       h) echo "$usage"
         exit 0
       ;;
       u)
	  UPLOAD=1
       ;;
       c)
	  which jq &>/dev/null || { echo "Need jq" && exit 1; }
	  COMPRESS="-c"
       ;;
       b)
	  BRAND_UPLOAD="$OPTARG"
       ;;
       B)
	  BRAND_GENERATE="$OPTARG"
       ;;
       r)
	  ENVROLES="$OPTARG"
       ;;
       t)
	  STACKTYPES="$OPTARG"
       ;;
       g)
	  COMMIT="$OPTARG"
       ;;
       s)
          SHOWONLY=1
       ;;
       T)
  	  TAG="$OPTARG"
       ;;	  
       \?)
          echo "Invalid option: -$OPTARG"
          echo "$usage"
          exit 1
       ;;
       :)
          echo "Option -$OPTARG requires an argument."
          echo "$usage"
          exit 1
       ;;
     esac 
   done   
}

show_repo() {
  get_upload_params
  echo ""
  while read template; do
    echo "${s3_url}/${template}"
  done << EOF
$(aws s3 ls ${S3Uri}/ --recursive|cut -d "/" -f 4)
EOF
}


get_brand_suffix(){
  local status=$(git status -s)
  local brands=$(echo "$status"|grep -Po "templates/\K[^/]+"|sort|uniq)
  local brand="ALL"
  if [ "$(echo "$brands"|wc -l)" = "1" ];then
    brand=$brands
  fi
  BRAND_SUFFIX="[G:$(echo "$brand"|tr [a-z] [A-Z])] --- "
}

git_commit(){
  if [ -n "$COMMIT" ];then
    get_brand_suffix
    [ -n "$UPLOAD" ] && COMMIT_SUFFIX=" --- [U:$BRAND_UPLOAD]"
    GITOUTPUT=$(git commit -am"${BRAND_SUFFIX}${COMMIT}${COMMIT_SUFFIX}")
    if [ "$?" != "0" ];then
      echo "Git Error: $GITOUTPUT"
      exit 1
    fi
  fi
}

compress_jsons(){
  while read file; do
    OUTPUT=$(jq -c . "$file")
    if [ "$?" = "0" ] && [ -n "$OUTPUT" ];then
      echo "$OUTPUT" > "$file"
    else
      echo "Error $file" && exit 1
    fi
  done < <(ls ${DIST_DIR}/templates/*.json)
}

build(){
  TEMPLATEDIR="templates/${BRAND_UPLOAD}"
  DIST_DIR="dist/${branch}-${tag}"
  [ -d "$DIST_DIR" ] && rm  -fr "$DIST_DIR"
  mkdir -p "$DIST_DIR" "$TEMPLATEDIR"
  echo "Creating build ${branch}-$tag"
  git archive --format=tar "$tag" "$TEMPLATEDIR" | (cd ${DIST_DIR}/ && tar xf - --transform='s/templates\/'${BRAND_UPLOAD}'/templates/')
  if [ -n "$COMPRESS" ];then
    compress_jsons
  fi
}

get_git_params(){
  reponame=$(basename $(git rev-parse --show-toplevel))
  if [ "$?" != 0 ] || [ -z "$reponame" ];then
    echo "You are not in a git repository."
    exit 1
  fi
  branch=$(git branch --no-color | egrep '^\*' | cut -d' ' -f2)
  tag=${TAG:-$(git describe --always master)}
}

get_upload_params(){
  get_git_params
  local REGION=${AWS_DEFAULT_REGION:-$AWS_REGION}
  eval $(grep "AppRepository: " "${CFG_DIR_EXT}/$BRAND_UPLOAD/common.yml"|tr -d " " | tr ":" "=")
  bucket="${REGION}-${AppRepository#*-}"
  if [ -z "$bucket" ];then
    echo "Error retriving bucketname"
  fi
  #S3Key="${reponame}/${branch}-${tag}"
  S3Key="ibox/${branch}-${tag}"
  S3Uri="s3://${bucket}/${S3Key}"
  s3_url="https://${bucket}.s3.amazonaws.com/$S3Key/templates"
}


upload(){
  if [ -n "$UPLOAD" ];then
    get_upload_params
    build
    aws s3 cp $DIST_DIR $S3Uri --recursive --only-show-errors && echo "$s3_url"
  fi
}

generate_template(){
  local brand=$1
  local TEMPLATEDIR="templates/${brand}"
  local outfile="${TEMPLATEDIR}/${envrole}.json"
 
  mkdir -p "$TEMPLATEDIR"

  OUTPUT=$($GENERATE_PRG --Brand $brand --EnvRole $envrole)

  if [ "$?" = "0" ] && [ -n "$OUTPUT" ]; then
    echo "$OUTPUT" > "$outfile"
    [ -n "$COMMIT" ] && git add "$outfile"
    return 0
  else
    echo "Error $brand $envrole"
    exit 1
  fi
}

generate_templates(){
  envrole=${cfg##*/}
  envrole=${envrole%.*}
  if [ "$brand" = "BASE" ];then
    for b in $BRANDS;do
      generate_template $b $envrole
    done
  else
    generate_template $brand $envrole
  fi
}


myopts "$@"

if [ -z "$CFG_DIR_BASE" ];then
  echo "Missing python module awsibox"
  exit 1
fi

if [ "$BRAND_GENERATE" != "ALL" ];then
  BRANDS=$BRAND_GENERATE
fi

[ -n "${SHOWONLY}" ] && show_repo && exit 0

for brand in $BRANDS BASE;do
  if [ -n "$STACKTYPES" ];then
    for stack in $STACKTYPES;do
      for cfg in $(egrep -s $EGREP_OPTS "^[[:space:]]+StackType: $stack$" ${CFG_DIR_BASE}/$brand ${CFG_DIR_EXT}/$brand);do
	generate_templates
      done
    done
  fi
  if [ -n "$ENVROLES" ];then
    for role in $ENVROLES;do
      if [ "$role" != "all" ];then
	cfg_file_base="${CFG_DIR_BASE}/${brand}/${role}.yml"
	cfg_file_ext="${CFG_DIR_EXT}/${brand}/${role}.yml"
      else
	cfg_file_base="${CFG_DIR_BASE}/${brand}"
	cfg_file_ext="${CFG_DIR_EXT}/${brand}"
      fi
      if [ -a "$cfg_file_base" ] || [ -a "$cfg_file_ext" ];then
	for cfg in $(egrep -s $EGREP_OPTS "^[[:space:]]+StackType: " "$cfg_file_base" "$cfg_file_ext");do
	  generate_templates
	done
      fi
    done
  fi
done

git_commit
upload

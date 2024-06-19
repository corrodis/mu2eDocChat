BASEDIR=$(dirname "$BASH_SOURCE")
PWD=`pwd`
if [[ $BASEDIR == $PWD* ]]; then
    export MU2E=$BASEDIR;
    export PYTHONPATH=$PYTHONPATH:$BASEDIR/;
else  
    export MU2E=$PWD/$BASEDIR;
    export PYTHONPATH=$PYTHONPATH:$PWD/$BASEDIR/;
  fi

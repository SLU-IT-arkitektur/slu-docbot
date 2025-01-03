#!/bin/sh
# ANSII Colors
RED='\033[0;31m'
BLUE='\033[0;34m'
RESET='\033[0m'

skaffold_files=$(find . -name 'skaffold.*.yaml')
skaffold_files="$skaffold_files skaffold.yaml"
echo "this will run the following skaffold delete commands:"
for file in $skaffold_files
do
    echo "skaffold delete -f $BLUE$file$RESET"
done
current_k8s_env=$(kubectl config current-context)
echo "you are currently targetting the kubectl context $RED$current_k8s_env$RESET"
echo 'are you sure you want to continue? (y/n)'
read answer
if [ "$answer" = "Y" ] || [ "$answer" = "y" ]; then
    echo "continuing.."
    for file in $skaffold_files
    do
        echo "running skaffold delete -f $file"
        skaffold delete -f $file
    done
    echo 'done'
else
    echo "ok, exiting.."
    exit 1
fi



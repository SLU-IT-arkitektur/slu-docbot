#!/bin/sh
skaffold_files=$(find . -name 'skaffold.*.yaml')
skaffold_files="$skaffold_files skaffold.yaml"
echo "this will run the following skaffold delete commands:"
for file in $skaffold_files
do
    echo "skaffold delete -f $file"
done
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



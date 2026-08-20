#!/bin/bash
# Create a datalad (sub)dataset for every "folder" (common prefix) in an S3
# bucket, and save them all into the current dataset.
#
# Usage:  s3_create_subdatasets.sh [-n] BUCKET[/PREFIX] [DATALAD CREATE OPTIONS...]
#
#   -n    dry run: just print what would be done
#
# Example:
#   datalad create mydataset && cd mydataset
#   ../tools/s3_create_subdatasets.sh openneuro.org -c text2git -d .

set -eu

dry=
if [ "${1:-}" = "-n" ]; then dry=echo; shift; fi

if [ $# -lt 1 ]; then
    sed -n '2,12p' "$0"
    exit 1
fi

bucket="${1%/}"; shift    # everything else is passed to `datalad create`

# collect the "folders" (S3 common prefixes)
folders=()
while read -r pre folder; do
    [ "$pre" = "PRE" ] || continue
    folders+=("${folder%/}")
done < <(aws s3 ls "s3://$bucket/")

if [ ${#folders[@]} -eq 0 ]; then
    echo "No folders found under s3://$bucket/" >&2
    exit 1
fi

echo "Found ${#folders[@]} folder(s) under s3://$bucket/" >&2

for folder in "${folders[@]}"; do
    if [ -e "$folder" ]; then
        echo "Skipping existing $folder" >&2
        continue
    fi
    $dry datalad create "$@" "$folder"
done

$dry datalad save -d . -m "Add ${#folders[@]} subdataset(s) from s3://$bucket/" "${folders[@]}"

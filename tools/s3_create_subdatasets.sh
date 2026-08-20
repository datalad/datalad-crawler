#!/bin/bash
# Create a datalad (sub)dataset for every "folder" (common prefix) in an S3
# bucket, initialize an "importtree" S3 special remote in each of them, and
# save them all into the current dataset.
#
# Usage:  s3_create_subdatasets.sh [-n] [-i] BUCKET[/PREFIX] [DATALAD CREATE OPTIONS...]
#
#   -n    dry run: just print what would be done
#   -i    also `git annex import` the current branch from the new remote
#
# Bucket region and versioning are sensed via the s3api, so the remote gets
# the right host/datacenter and versioning=yes only if it truly is versioned.
#
# Example:
#   datalad create mydataset && cd mydataset
#   ../tools/s3_create_subdatasets.sh openneuro.org -c text2git -d .

set -eu

dry=
do_import=
while [ $# -gt 0 ]; do
    case "$1" in
        -n) dry=echo; shift;;
        -i) do_import=1; shift;;
        *)  break;;
    esac
done
[ $# -ge 1 ] || { sed -n '2,15p' "$0"; exit 1; }

bucket="${1%/}"; shift          # everything else is passed to `datalad create`
bucket_name="${bucket%%/*}"     # bucket without the optional prefix
prefix=                         # optional prefix, with trailing /
[ "$bucket" != "$bucket_name" ] && prefix="${bucket#*/}/"

# region: LocationConstraint is None/empty for us-east-1
region=$(aws s3api get-bucket-location --bucket "$bucket_name" \
             --output text --query LocationConstraint 2>/dev/null) \
    || { echo "Failed to get location of $bucket_name" >&2; exit 1; }
case "$region" in
    None|"") region=us-east-1; datacenter=US;;
    *)       datacenter="$region";;
esac
host="s3.$region.amazonaws.com"
# path-style URL: works also for buckets with dots in the name
publicurl="https://$host/$bucket_name/"

# is the bucket versioned?  Suspended still means old versions might be
# around, but new uploads are not versioned, so treat it as not versioned.
status=$(aws s3api get-bucket-versioning --bucket "$bucket_name" \
             --output text --query Status 2>/dev/null) || status=UNKNOWN
case "$status" in
    Enabled) versioning=yes;;
    *)       versioning=no;;
esac
echo "s3://$bucket_name/ region=$region versioning=$status" >&2

# collect the "folders" (S3 common prefixes)
folders=()
while read -r pre folder; do
    [ "$pre" = "PRE" ] || continue
    folders+=("${folder%/}")
done < <(aws s3 ls "s3://$bucket/")

[ ${#folders[@]} -gt 0 ] || { echo "No folders under s3://$bucket/" >&2; exit 1; }
echo "Found ${#folders[@]} folder(s) under s3://$bucket/" >&2

for folder in "${folders[@]}"; do
    if [ -e "$folder" ]; then
        echo "Skipping existing $folder" >&2
        continue
    fi
    $dry datalad create "$@" "$folder"
    $dry git -C "$folder" annex initremote s3-bucket type=S3 \
        bucket="$bucket_name" fileprefix="$prefix$folder/" \
        host="$host" port=443 datacenter="$datacenter" publicurl="$publicurl" \
        versioning="$versioning" \
        importtree=yes signature=anonymous encryption=none autoenable=yes
    if [ -n "$do_import" ]; then
        branch=$(git -C "$folder" symbolic-ref --short HEAD 2>/dev/null || echo BRANCH)
        $dry git -C "$folder" annex import "$branch" --from s3-bucket
        $dry datalad save -d "$folder" -m "Import tree from s3://$bucket_name/$prefix$folder/"
    fi
done

$dry datalad save -d . \
    -m "Add ${#folders[@]} subdataset(s) from s3://$bucket/ (versioning: $status)" \
    "${folders[@]}"

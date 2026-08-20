#!/bin/bash
# Create a datalad (sub)dataset for every "folder" (common prefix) in an S3
# bucket, and save them all into the current dataset.
#
# Usage:  s3_create_subdatasets.sh [-n] BUCKET[/PREFIX] [DATALAD CREATE OPTIONS...]
#
#   -n    dry run: just print what would be done
#
# Whether the bucket is versioned (aws s3api get-bucket-versioning) is sensed
# and reported, and made available to `datalad create` via S3_VERSIONING
# ("Enabled", "Suspended", "UNKNOWN" or empty if never versioned).
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
bucket_name="${bucket%%/*}"    # without the optional prefix

# sense either the bucket is versioned: "Enabled", "Suspended" or empty
# (never versioned).  Might fail if we lack s3:GetBucketVersioning permission.
versioning=$(aws s3api get-bucket-versioning --bucket "$bucket_name" \
                 --output text --query Status 2>/dev/null) || versioning='UNKNOWN'
[ "$versioning" = "None" ] && versioning=''    # --query prints None for absent Status
case "$versioning" in
    Enabled)   echo "Bucket $bucket_name is versioned" >&2;;
    Suspended) echo "Bucket $bucket_name has versioning suspended (old versions might still be there)" >&2;;
    UNKNOWN)   echo "Could not determine versioning of $bucket_name (no permission?)" >&2;;
    *)         echo "Bucket $bucket_name is not versioned" >&2;;
esac

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

export S3_VERSIONING="$versioning"

for folder in "${folders[@]}"; do
    if [ -e "$folder" ]; then
        echo "Skipping existing $folder" >&2
        continue
    fi
    $dry datalad create "$@" "$folder"
done

msg="Add ${#folders[@]} subdataset(s) from s3://$bucket/"
[ -n "$versioning" ] && msg="$msg (versioning: $versioning)"
$dry datalad save -d . -m "$msg" "${folders[@]}"

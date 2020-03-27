#!/bin/bash

set -e   # stop the script if something fails

#optional arguments:
#  --geojson GEOJSON    GeoJSON file of region to search.
#  --date DATE          Fire date in format YYYYMMDD
#  --work_dir WORK_DIR  Directory to place files.


SRC=$HOME/code/sentinelfire_test
WORK_DIR=$HOME/data/sentinelfire_test/
DATE='20180130'


for GEOJSON in $WORK_DIR/*.geojson; do
  python $SRC/download.py --geojson "$GEOJSON" --date "$DATE" --work_dir "$WORK_DIR"
done

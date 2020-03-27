#!/bin/bash
set -e

SRC=$HOME/code/sentinelfire/
WORK_DIR=$HOME/data/sentinelfire/valparaiso/

num_procs=$1

function max_bg_procs {
    if [[ $# -eq 0 ]] ; then
            echo "Usage: max_bg_procs NUM_PROCS.  Will wait until the number of background (&)"
            echo "           bash processes (as determined by 'jobs -pr') falls below NUM_PROCS"
            return
    fi
    local max_number=$((0 + ${1:-0}))
    while true; do
            local current_number=$(jobs -pr | wc -l)
            if [[ $current_number -lt $max_number ]]; then
                    break
            fi
            sleep 1
    done
}

for TILEID in $WORK_DIR/*; do
  max_bg_procs $num_procs

  python buildmaps.py --tileid "$TILEID" & 

done



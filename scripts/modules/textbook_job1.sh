#!/bin/bash

#SBATCH --job-name=textbook
#SBATCH --output=logs/%x/prepare.log
#SBATCH --time=4:00:00
#SBATCH --partition=preempt

#SBATCH --mem=32G
#SBATCH --cpus-per-task=8

source devconfig.sh
source devsecret.sh

python3 -m sources.textbook.populate \
    --model $MODEL \
    --read-prefix $GCP_PREFIX/$DATASET/textfiles \
    --save-prefix $GCP_PREFIX/$DATASET-textbook/$MODEL/textfiles

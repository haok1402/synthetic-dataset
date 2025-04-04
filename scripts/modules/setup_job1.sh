#!/bin/bash

#SBATCH --job-name=setup
#SBATCH --output=logs/%x.log
#SBATCH --time=4:00:00
#SBATCH --partition=preempt

#SBATCH --mem=32G
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1

source ~/miniconda3/etc/profile.d/conda.sh
conda create -n synthetic-dataset python=3.12 -y
conda activate synthetic-dataset
pip install -r requirements.txt

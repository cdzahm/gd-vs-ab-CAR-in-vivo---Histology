#!/bin/bash
#SBATCH --job-name=czi_to_ometiff
#SBATCH --account=provenza
#SBATCH --partition=amdsmall
#SBATCH --time=4-00:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32gb
#SBATCH --output=/scratch.global/zahm0007/gdCAR Histology/Histology/Scripts/czi_convert_%j.log
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user=zahm0007@umn.edu

# Load Java (required by bioformats2raw and raw2ometiff)
module load java/openjdk-21.0.2

# Run the conversion script
python "/scratch.global/zahm0007/gdCAR Histology/Histology/Scripts/convert_czi_to_ometiff_msi.py"

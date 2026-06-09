# Per-mouse median normalized CD3+ cell distance from tumor edge
# Output: one row per mouse, ready for Prism

import pandas as pd
import numpy as np

# Load the exported CSV
input_path = "/Users/cdz/PPP Lab Files/Experiments/gdCAR T cells/2025-07-12 In vivo - ab vs gd w Aspc1/Histology/cd3_distances.csv"
output_path = "/Users/cdz/PPP Lab Files/Experiments/gdCAR T cells/2025-07-12 In vivo - ab vs gd w Aspc1/Histology/cd3_distances_summary.csv"

df = pd.read_csv(input_path)

# Assign treatment groups based on mouse number
def get_treatment(mouse_id):
    # Extract the number after the last dash e.g. "25-256-13" -> 13
    num = int(mouse_id.split("-")[-1])
    if num <= 4:
        return "Control"
    elif num <= 9:
        return "abCAR"
    else:
        return "gdCAR"

df["treatment"] = df["mouse_id"].apply(get_treatment)

# Drop rows with NaN normalized distance
df = df.dropna(subset=["normalized_distance"])

# Summarize per mouse
summary = df.groupby(["mouse_id", "treatment"]).agg(
    cell_count=("normalized_distance", "count"),
    median_normalized_distance=("normalized_distance", "median"),
    mean_normalized_distance=("normalized_distance", "mean"),
    median_raw_distance_um=("raw_distance_um", "median"),
    mean_raw_distance_um=("raw_distance_um", "mean")
).reset_index()

# Sort by mouse number for clean output
summary["mouse_num"] = summary["mouse_id"].apply(lambda x: int(x.split("-")[-1]))
summary = summary.sort_values("mouse_num").drop(columns="mouse_num")

print(summary.to_string(index=False))
summary.to_csv(output_path, index=False)
print(f"\nSaved to: {output_path}")
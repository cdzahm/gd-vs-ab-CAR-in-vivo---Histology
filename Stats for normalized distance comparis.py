# Stats for normalized distance comparison across treatment groups

import pandas as pd
from scipy import stats

df = pd.read_csv("/Users/cdz/PPP Lab Files/Experiments/gdCAR T cells/2025-07-12 In vivo - ab vs gd w Aspc1/Histology/cd3_distances_summary.csv")

# Split by group
control = df[df["treatment"] == "Control"]["median_normalized_distance"]
abcar = df[df["treatment"] == "abCAR"]["median_normalized_distance"]
gdcar = df[df["treatment"] == "gdCAR"]["median_normalized_distance"]

# Kruskal-Wallis
stat, p = stats.kruskal(control, abcar, gdcar)
print(f"Kruskal-Wallis: H={stat:.3f}, p={p:.4f}")

# Pairwise Mann-Whitney
pairs = [("Control", control, "abCAR", abcar),
         ("Control", control, "gdCAR", gdcar),
         ("abCAR", abcar, "gdCAR", gdcar)]

print("\nMann-Whitney pairwise:")
for name1, g1, name2, g2 in pairs:
    u, p = stats.mannwhitneyu(g1, g2, alternative="two-sided")
    print(f"  {name1} vs {name2}: U={u:.1f}, p={p:.4f}")
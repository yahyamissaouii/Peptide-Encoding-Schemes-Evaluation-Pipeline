# save as scripts/plot_error_sweep.py or run inline with python3 - <<'PY'
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

df = pd.read_csv("reports/error_sweep.csv")

# Aggregate error level (works for grid or equal mode)
df["error_level"] = df[["loss_prob", "mutation_prob", "insertion_prob", "shuffle_prob"]].sum(axis=1)

agg = (
    df.groupby(["error_level", "ecc_profile"])
      .agg(success_rate=("success", "mean"),
           ber=("bit_error_rate", "mean"))
      .reset_index()
)

# Plot success rate vs total error rate
plt.figure(figsize=(8, 5))
for profile, grp in agg.groupby("ecc_profile"):
    grp = grp.sort_values("error_level")
    plt.plot(grp["error_level"] * 100, grp["success_rate"] * 100, marker="o", label=profile)

plt.xlabel("Total error rate (%)")
plt.ylabel("Success rate (%)")
plt.title("Success Rate vs Error Rate")
plt.legend()
plt.tight_layout()
plt.savefig("reports/success_rate_by_profile.png", dpi=200)

# Plot BER vs total error rate
plt.figure(figsize=(8, 5))
for profile, grp in agg.groupby("ecc_profile"):
    grp = grp.sort_values("error_level")
    plt.plot(grp["error_level"] * 100, grp["ber"], marker="o", label=profile)

plt.xlabel("Total error rate (%)")
plt.ylabel("Bit error rate")
plt.title("BER vs Error Rate")
plt.legend()
plt.tight_layout()
plt.savefig("reports/ber_by_profile.png", dpi=200)

print("Saved plots in reports/")

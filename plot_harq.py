import re
import matplotlib.pyplot as plt
# Parse log file
data = {0: [], 1: [], 2: [], 3: []}
with open('/home/oai72_su/oai_mp_f_ming_develop_latest/openairinterface5g/cmake_targets/ran_build/build/harq_timing.txt', 'r') as f:
    for line in f:
        if 'HARQ_SUCCESS' in line:
            round_match = re.search(r'round=(\d+)', line)
            elapsed_match = re.search(r'elapsed_us=(\d+)', line)
            if round_match and elapsed_match:
                r = int(round_match.group(1))
                elapsed = int(elapsed_match.group(1))
                if r in data:
                    data[r].append(elapsed)
# Plot histograms
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
for i, ax in enumerate(axes.flatten()):
    if data[i]:
        ax.hist(data[i], bins=50)
        ax.set_title(f'Round {i} (n={len(data[i])})')
        ax.set_xlabel('Elapsed Time (μs)')
        ax.set_ylabel('Count')
plt.tight_layout()
plt.savefig('harq_timing_distribution.png')

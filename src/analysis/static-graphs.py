# generated from other tools

import matplotlib.pyplot as plt
import numpy as np

species = ("DeepSeek-V3", "GPT-4o", "Qwen3", "Gemini-2.5-Flash", "O1/GPT-4")
weight_counts = {
    "Planner":  [0.5909,    0.1293, 0.3539, 0.5840, 0.5850],
    "Executor": [0.1538,    0.1088, 0.6128, 0.1975, 0.1459],
    "Commands": [0.2553,     0.7619, 0.0333, 0.2185, 0.2692],
}
width = 0.5

fig, ax = plt.subplots()
bottom = np.zeros(5)

for boolean, weight_count in weight_counts.items():
    p = ax.bar(species, weight_count, width, label=boolean, bottom=bottom)
    bottom += weight_count

ax.set_title("Time spent in different ")
ax.legend(loc="upper right")

plt.savefig('time_spent_areas.png')
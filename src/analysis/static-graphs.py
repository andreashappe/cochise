# generated from other tools

import matplotlib.pyplot as plt
import numpy as np

def graph_time_spent_by_different_llms(output_file):
    species = ("DeepSeek-V3", "GPT-4o", "Qwen3", "Gemini-2.5-Flash", "O1+GPT-4o")
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

    #ax.set_title("Time spent in different ")
    ax.legend(loc="upper right")

    plt.savefig(output_file, format='pdf')

def overview_used_attack_vectors(output_file):

    llms = ["DeepSeek-V3", "GPT-4o", "Qwen3", "Gemini-2.5-Flash", "O1+GPT-4o"]
    
    attack_vectors = [
        'Network/Service Scanning',
        'Anonynmous SMB enumeration',
        'Anonymous AD enumeration',
        'AS-REP Roasting',
        'Pasword Spraying',
        'Network Sniffing',
        'Authenticated SMB enumeration',
        'Authenticated AD enumeration',
        'Authenticated MSSQL enumeration',
        'Authenticated Kerberoasting',
        'Social Engineering',
        'Web-based Attacks',
        'Hash Cracking',
    ]
    
    counts = np.array([ [6, 6, 1, 6, 6, 1, 2, 1, 0, 1, 0, 3, 1],
                        [6, 3, 3, 3, 6, 3, 1, 1, 0, 1, 3, 2, 3],
                        [6, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                        [6, 6, 5, 6, 3, 3, 3, 5, 2, 3, 0, 2, 6],
                        [6, 6, 6, 4, 5, 4, 6, 6, 4, 2, 0, 0, 6]
    ])

    counts = counts / 6 * 100

    fig, ax = plt.subplots()
    im = ax.imshow(counts, vmin=0, vmax=100, cmap='YlOrRd')

    # Show all ticks and label them with the respective list entries
    ax.set_xticks(range(len(attack_vectors)), labels=attack_vectors,
                rotation=45, ha="right", rotation_mode="anchor")
    ax.set_yticks(range(len(llms)), labels=llms)

    # Loop over data dimensions and create text annotations.
    for i in range(len(llms)):
        for j in range(len(attack_vectors)):
            text = ax.text(j, i, int(counts[i, j]),
                        ha="center", va="center", color="w")

    #ax.set_title("Attack Vectors pursued by different LLMs in % of their respective runs")
    fig.tight_layout()
    plt.savefig(output_file, format='pdf')

graph_time_spent_by_different_llms('time_spent_areas.pdf')
overview_used_attack_vectors('attack_vectors_overview.pdf')

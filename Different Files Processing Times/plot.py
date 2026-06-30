import matplotlib.pyplot as plt
import numpy as np

categories = ['Datasheets\n(PDF)', 'CAD models\n(STP/STEP)', 'PLC programs\n(PLCOpenXML)', 'SysML models\n(UML)', 'MATLAB/Simulink\nmodels (SLX)', 'Bills Of Materials\n(CSV)', 'Technical Reports\n(PDF)']
automatic = [7.47291176470588, 14.77388, 343.495, 798.092, 33.999, 1.725, 0]
manual_actual = [0, 0, 0, 0, 3600, 7200, 7200]
manual_display = [man if man > 0 else 0 for man in manual_actual]
x = np.arange(len(categories))
width = 0.6
base = 0.1

fig, ax = plt.subplots(figsize=(14, 7))
bars_auto = ax.bar(x, automatic, width, bottom=[base]*len(categories), label='automatic', color='gray', edgecolor='black', linewidth=1.5)
white_bottom = [base + a for a in automatic]
bars_man = ax.bar(x, manual_display, width, bottom=white_bottom, label='manual', color='white', edgecolor='black', linewidth=1.5)

ax.set_yscale('log')
max_total = max([base + a + m for a, m in zip(automatic, manual_display)])
ax.set_ylim(0.09, max_total * 1.2)
ax.yaxis.set_major_formatter(plt.ScalarFormatter())
ax.yaxis.set_major_locator(plt.FixedLocator([0.1, 1, 10, 100, 1000, 10000]))
ax.tick_params(axis='both', labelsize=11)

for i, (auto, wh) in enumerate(zip(automatic, manual_display)):
    if auto > 0:
        y_pos = base + auto / 2
        ax.text(i, y_pos, f'{auto:.2f}', ha='center', va='center', color='black', fontsize=10, fontweight='bold')
    if wh > 0:
        y_pos = base + auto + wh / 2
        ax.text(i, y_pos, f'{wh:.0f}', ha='center', va='center', color='black', fontsize=10, fontweight='bold')

ax.set_ylabel('time in s', fontsize=13)
ax.set_xticks(x)
ax.set_xticklabels(categories, fontsize=10)
ax.legend(loc='center left', bbox_to_anchor=(1.0, 0.5), fontsize=12)
plt.subplots_adjust(right=0.85)
ax.grid(True, which='major', axis='y', linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

def create_architecture_diagram():
    fig, ax = plt.subplots(figsize=(12, 8))

    # Adding components to the diagram
    ax.add_patch(mpatches.Rectangle((0.1, 0.7), 0.8, 0.2, edgecolor='blue', facecolor='lightblue', lw=2))
    ax.text(0.5, 0.8, 'MediSense AI v2 System', ha='center', fontsize=14, weight='bold')

    ax.add_patch(mpatches.Rectangle((0.1, 0.5), 0.3, 0.15, edgecolor='green', facecolor='lightgreen', lw=2))
    ax.text(0.25, 0.575, 'Data Collection', ha='center', fontsize=12)

    ax.add_patch(mpatches.Rectangle((0.1, 0.35), 0.3, 0.15, edgecolor='orange', facecolor='lightyellow', lw=2))
    ax.text(0.25, 0.425, 'Data Processing', ha='center', fontsize=12)

    ax.add_patch(mpatches.Rectangle((0.1, 0.2), 0.3, 0.15, edgecolor='red', facecolor='lightcoral', lw=2))
    ax.text(0.25, 0.275, 'Database', ha='center', fontsize=12)

    ax.add_patch(mpatches.Rectangle((0.5, 0.5), 0.3, 0.15, edgecolor='purple', facecolor='plum', lw=2))
    ax.text(0.65, 0.575, 'Model Training', ha='center', fontsize=12)

    ax.add_patch(mpatches.Rectangle((0.5, 0.35), 0.3, 0.15, edgecolor='brown', facecolor='peachpuff', lw=2))
    ax.text(0.65, 0.425, 'Prediction & Inference', ha='center', fontsize=12)

    ax.add_patch(mpatches.Rectangle((0.5, 0.2), 0.3, 0.15, edgecolor='grey', facecolor='lightgrey', lw=2))
    ax.text(0.65, 0.275, 'User Interface', ha='center', fontsize=12)

    # Adding arrows for data flow
    ax.annotate('', xy=(0.4, 0.575), xytext=(0.1, 0.575),
                arrowprops=dict(arrowstyle='->', lw=2, color='black'))

    ax.annotate('', xy=(0.45, 0.425), xytext=(0.1, 0.425),
                arrowprops=dict(arrowstyle='->', lw=2, color='black'))

    ax.annotate('', xy=(0.4, 0.275), xytext=(0.1, 0.275),
                arrowprops=dict(arrowstyle='->', lw=2, color='black'))

    ax.annotate('', xy=(0.8, 0.575), xytext=(0.5, 0.575),
                arrowprops=dict(arrowstyle='->', lw=2, color='black'))

    ax.annotate('', xy=(0.8, 0.425), xytext=(0.5, 0.425),
                arrowprops=dict(arrowstyle='->', lw=2, color='black'))

    ax.annotate('', xy=(0.8, 0.275), xytext=(0.5, 0.275),
                arrowprops=dict(arrowstyle='->', lw=2, color='black'))

    plt.axis('off')
    plt.title('Architecture Diagram for MediSense AI v2', fontsize=16, weight='bold')
    plt.savefig('mediSense_architecture_diagram.pdf', format='pdf')
    plt.show()

if __name__ == "__main__":
    create_architecture_diagram()
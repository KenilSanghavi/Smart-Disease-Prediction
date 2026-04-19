import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

def create_architecture_diagram():
    fig, ax = plt.subplots(figsize=(10, 8))

    # Example components
    components = {
        'User Interface': (1, 8),
        'Web Server': (1, 6),
        'Model': (1, 4),
        'Database': (1, 2),
        'Prediction Output': (1, 0)
    }

    # Create boxes
    for component, (x, y) in components.items():
        ax.add_patch(mpatches.Rectangle((x - 0.4, y - 0.4), 0.8, 0.8, fill=True, edgecolor='black', color='lightblue'))
        ax.text(x, y, component, horizontalalignment='center', verticalalignment='center')

    # Add arrows (flow direction)
    ax.arrow(1, 7.5, 0, -1.5, head_width=0.15, head_length=0.2, fc='black', ec='black')
    ax.arrow(1, 5.5, 0, -1.5, head_width=0.15, head_length=0.2, fc='black', ec='black')
    ax.arrow(1, 3.5, 0, -1.5, head_width=0.15, head_length=0.2, fc='black', ec='black')

    plt.title('Smart Disease Prediction System Architecture')
    plt.axis('off')
    plt.savefig('architecture_diagram.pdf')
    plt.close()

if __name__ == '__main__':
    create_architecture_diagram()
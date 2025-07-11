import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import ListedColormap
import matplotlib.style as mpl_style
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict
import re
import argparse
import json
import boto3

# Define the Run class to represent each hydrologic modeling run
@dataclass
class Run:
    folder_name: str
    profile_data: Dict[str, datetime]

    def get_step_durations(self) -> List[float]:
        """Calculate durations for individual steps in seconds."""
        step_pairs = [
            ('DATASTREAM_START', 'DATASTREAM_END'),
            ('GET_RESOURCES_START', 'GET_RESOURCES_END'),
            ('DATASTREAMCONFGEN_START', 'DATASTREAMCONFGEN_END'),
            ('NGENCONFGEN_START', 'NGENCONFGEN_END'),
            ('FORCINGPROCESSOR_START', 'FORCINGPROCESSOR_END'),
            ('VALIDATION_START', 'VALIDATION_END'),
            ('NGEN_START', 'NGEN_END'),
            ('MERKLE_START', 'MERKLE_END'),
            ('TAR_START', 'TAR_END'),
        ]
        durations = []
        for start, end in step_pairs:
            if end is None or start not in self.profile_data or end not in self.profile_data:
                durations.append(0.0)
            else:
                duration = (self.profile_data[end] - self.profile_data[start]).total_seconds()
                durations.append(duration)
        return durations

    def get_step_labels(self) -> List[str]:
        """Return labels for individual steps."""
        return [
            'DATASTREAM TOTAL', 'GET_RESOURCES', 'DATASTREAMCONFGEN',
            'NGENCONFGEN', 'FORCINGPROCESSOR', 'VALIDATION',
            'NGEN', 'MERKLE', 'TAR'
        ]

def parse_profile_file(file_path: Path) -> Dict[str, datetime]:
    """Parse profile.txt into a dictionary of step names and timestamps."""
    profile_data = {}
    timestamp_pattern = r'(\w+): (\d{14})'
    try:
        with open(file_path, 'r') as f:
            for line in f:
                match = re.match(timestamp_pattern, line.strip())
                if match:
                    step, timestamp = match.groups()
                    profile_data[step] = datetime.strptime(timestamp, '%Y%m%d%H%M%S')
    except FileNotFoundError:
        print(f"Profile file not found: {file_path}")
    return profile_data

def load_runs(top_level_path: str) -> List[Run]:
    """Load all runs from the top-level directory."""
    runs = []
    top_dir = Path(top_level_path)
    for folder in top_dir.iterdir():
        if folder.is_dir():
            profile_path = folder / 'datastream-metadata' / 'profile.txt'
            if profile_path.exists():
                profile_data = parse_profile_file(profile_path)
                if profile_data:
                    runs.append(Run(folder_name=folder.name, profile_data=profile_data))
    return runs

# Cache for EC2 instance costs
_instance_cost_cache = {}

def get_ec2_cost_per_hour(instance_type: str) -> str:
    """Query AWS Pricing API for EC2 instance cost per hour (USD). Return 'N/A' on failure."""
    if instance_type in _instance_cost_cache:
        return _instance_cost_cache[instance_type]
    
    try:
        client = boto3.client('pricing', region_name='us-east-1')
        response = client.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': 'US East (N. Virginia)'},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
            ],
            MaxResults=1
        )
        for product in response['PriceList']:
            product = json.loads(product)
            price_terms = product['terms']['OnDemand']
            for term in price_terms.values():
                for price_dim in term['priceDimensions'].values():
                    cost_per_hour = float(price_dim['pricePerUnit']['USD'])
                    _instance_cost_cache[instance_type] = cost_per_hour
                    return cost_per_hour
        return 'N/A'
    except Exception:
        return 'N/A'

class HydrologicGUI:
    def __init__(self, root: tk.Tk, data_path: str):
        self.root = root
        self.data_path = data_path  # Store data_path as instance attribute
        self.root.title("Hydrologic Modeling Visualization")
        self.root.configure(bg='#2e2e2e')  # Dark background
        self.runs = load_runs(data_path)

        # Set dark theme for Matplotlib
        mpl_style.use('dark_background')
        plt.rcParams['text.color'] = 'white'
        plt.rcParams['axes.labelcolor'] = 'white'
        plt.rcParams['xtick.color'] = 'white'
        plt.rcParams['ytick.color'] = 'white'

        # Define distinct color map
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD',
                '#D4A5A5', '#9B59B6', '#3498DB', '#E74C3C', '#2ECC71']
        self.cmap = ListedColormap(colors[:len(self.runs)])

        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.main_frame.configure(style='Dark.TFrame')

        # Configure style for dark theme
        style = ttk.Style()
        style.configure('Dark.TFrame', background='#2e2e2e')
        style.configure('Dark.TLabel', background='#2e2e2e', foreground='white')
        style.configure('Dark.TButton', background='#3a3a3a', foreground='white')

        # Set initial window size
        self.root.geometry("1400x900")  # Increased to fit larger plot

        # Create plot
        self.fig, self.ax = plt.subplots(figsize=(12, 6))  # Increased figure size
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_frame)
        self.canvas.get_tk_widget().grid(row=0, column=1, rowspan=2, padx=5, pady=5, sticky=(tk.N, tk.E, tk.W, tk.S))

        # Create run selection listbox
        self.run_listbox = tk.Listbox(
            self.main_frame, selectmode=tk.MULTIPLE, width=20, height=10,
            bg='#3a3a3a', fg='white', selectbackground='#4a4a4a'
        )
        self.run_listbox.grid(row=0, column=0, padx=5, pady=5, sticky=tk.N)
        for run in self.runs:
            self.run_listbox.insert(tk.END, run.folder_name)
        self.run_listbox.bind('<<ListboxSelect>>', self.on_listbox_select)

        # Create scrollable canvas for tables
        self.table_canvas = tk.Canvas(self.main_frame, bg='#2e2e2e')
        self.table_canvas.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.table_scrollbar = tk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.table_canvas.yview)
        self.table_scrollbar.grid(row=2, column=2, sticky=(tk.N, tk.S))
        self.table_canvas.configure(yscrollcommand=self.table_scrollbar.set)

        # Create frame inside canvas for tables
        self.table_frame = ttk.Frame(self.table_canvas)
        self.table_canvas.create_window((0, 0), window=self.table_frame, anchor=tk.NW)

        # Create table for displaying bar values
        self.table = ttk.Treeview(self.table_frame, columns=('Run', 'Step', 'Duration', 'Cost'), show='headings')
        self.table.heading('Run', text='Run', command=lambda: self.sort_column('Run', False))
        self.table.heading('Step', text='Step', command=lambda: self.sort_column('Step', False))
        self.table.heading('Duration', text='Duration (seconds)', command=lambda: self.sort_column('Duration', False))
        self.table.heading('Cost', text='Cost ($)', command=lambda: self.sort_column('Cost', False))
        self.table.column('Run', width=200, stretch=True)
        self.table.column('Step', width=250, stretch=True)
        self.table.column('Duration', width=150, stretch=True)
        self.table.column('Cost', width=150, stretch=True)
        self.table.grid(row=0, column=0, pady=5)

        # Track sorting state
        self.sort_column_name = None
        self.sort_reverse = False

        # Create a frame for per-run metadata tables
        self.metadata_frame = ttk.Frame(self.table_frame)
        self.metadata_frame.grid(row=0, column=1, pady=5, sticky=(tk.W, tk.E))

        # List to store per-run metadata tables
        self.metadata_tables = []

        # Update canvas scroll region when table_frame size changes
        def update_scroll_region(event=None):
            self.table_canvas.configure(scrollregion=self.table_canvas.bbox("all"))

        self.table_frame.bind("<Configure>", update_scroll_region)

        # Bind window close event
        def on_closing():
            plt.close('all')  # Close all Matplotlib figures
            self.root.destroy()  # Destroy Tkinter window
            self.root.quit()  # Quit Tkinter event loop

        self.root.protocol("WM_DELETE_WINDOW", on_closing)

        # Initial plot
        self.plot_runs()

    def on_listbox_select(self, event):
        """Update plot and table when listbox selection changes."""
        self.plot_runs()
        self.canvas.draw()  # Force canvas redraw

    def plot_runs(self):
        """Plot the durations of selected runs as a bar chart and display values and metadata in tables."""
        self.ax.clear()
        self.ax.set_yscale('log')  # Set y-axis to logarithmic scale
        
        # Clear the durations table
        for item in self.table.get_children():
            self.table.delete(item)
        
        # Clear existing metadata tables
        for table in self.metadata_tables:
            table.destroy()
        self.metadata_tables.clear()
        
        selected_indices = self.run_listbox.curselection()
        selected_runs = [self.runs[i] for i in selected_indices] if selected_indices else self.runs

        if not selected_runs:
            self.ax.set_title("No Runs Selected")
            self.canvas.draw()
            return

        # Get step labels from the first run
        step_labels = selected_runs[0].get_step_labels()
        num_steps = len(step_labels)
        num_runs = len(selected_runs)

        # Set bar width and offsets to avoid overlap
        bar_width = 0.8 / num_runs  # Divide space among runs
        x = range(num_steps)  # Base x positions for steps

        # Plot bars, populate durations table, and create metadata tables
        for i, run in enumerate(selected_runs):
            durations = run.get_step_durations()
            # Replace 0.0 with a small value for log scale
            durations = [max(d, 1e-3) for d in durations]  # Use 0.001 as minimum
            # Offset x positions for this run's bars
            x_offset = [pos + i * bar_width - (num_runs * bar_width) / 2 for pos in x]
            self.ax.bar(x_offset, durations, width=bar_width, color=self.cmap(i), label=run.folder_name)
            
            # Get EC2 instance cost
            cost_per_hour = 'N/A'
            execution_file = Path(self.data_path) / run.folder_name / 'datastream-metadata' / 'execution.json'
            if execution_file.exists():
                try:
                    with open(execution_file, 'r') as f:
                        data = json.load(f)
                    instance_type = data['instance_parameters']['InstanceType']
                    cost_per_hour = get_ec2_cost_per_hour(instance_type)
                except (KeyError, ValueError, json.JSONDecodeError):
                    cost_per_hour = 'N/A'
            
            # Add durations and costs to table
            for j, duration in enumerate(durations):
                cost = 'N/A'
                if isinstance(cost_per_hour, (int, float)):
                    cost = (duration / 3600) * cost_per_hour  # Convert seconds to hours and multiply by cost/hour
                    cost = f"{cost:.4f}"  # Format to 4 decimal places
                self.table.insert('', 'end', values=(run.folder_name, step_labels[j], f"{duration:.2f}", cost))
            
            # Gather metadata
            run_path = Path(self.data_path) / run.folder_name
            config_path = run_path / 'ngen-run' / 'config'
            
            # Find geopackage
            geopackage = 'N/A'
            for file in config_path.glob('*.gpkg'):
                geopackage = file.name
                break
            
            # Compute number of time steps
            time_steps = 'N/A'
            realization_file = config_path / 'realization.json'
            if realization_file.exists():
                try:
                    with open(realization_file, 'r') as f:
                        data = json.load(f)
                    start_time = datetime.strptime(data['time']['start_time'], '%Y-%m-%d %H:%M:%S')
                    end_time = datetime.strptime(data['time']['end_time'], '%Y-%m-%d %H:%M:%S')
                    output_interval = data['time']['output_interval']
                    time_diff = (end_time - start_time).total_seconds()
                    time_steps = int(time_diff / output_interval) + 1  # Number of hours
                except (KeyError, ValueError, json.JSONDecodeError):
                    pass
            
            # Count catchments
            catchments = 'N/A'
            cfe_path = config_path / 'cat-config' / 'CFE'
            if cfe_path.exists():
                catchments = len(list(cfe_path.glob('*')))
            
            # Create metadata table for this run
            metadata_table = ttk.Treeview(
                self.metadata_frame,
                columns=('Field', 'Value'),
                show='headings',
                height=4  # Fixed height for 4 rows
            )
            metadata_table.heading('Field', text='Field')
            metadata_table.heading('Value', text='Value')
            metadata_table.column('Field', width=200)
            metadata_table.column('Value', width=400)
            metadata_table.grid(row=i, column=0, pady=5, sticky=(tk.W, tk.E))
            self.metadata_tables.append(metadata_table)
            
            # Populate metadata table
            metadata_table.insert('', 'end', values=('Run Name', run.folder_name))
            metadata_table.insert('', 'end', values=('Geopackage', geopackage))
            metadata_table.insert('', 'end', values=('Time Steps', time_steps))
            metadata_table.insert('', 'end', values=('Catchments', catchments))

        # Customize plot
        self.ax.set_title("Step Durations for Hydrologic Modeling Runs")
        self.ax.set_xlabel("Workflow Steps")
        self.ax.set_ylabel("Duration (seconds)")
        self.ax.set_xticks(range(num_steps))
        self.ax.set_xticklabels(step_labels, rotation=45)
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)

        # Adjust layout to prevent label cutoff
        self.fig.tight_layout()
        self.canvas.draw()
        self.canvas.flush_events()
        self.root.update_idletasks()

    def sort_column(self, col, reverse):
        """Sort table by the specified column."""
        # Get all table data
        data = [(self.table.set(item, col), item) for item in self.table.get_children()]
        
        # Convert Duration and Cost to float for numeric sorting, handle 'N/A'
        if col in ('Duration', 'Cost'):
            data = [(float(val) if val != 'N/A' else -float('inf'), item) for val, item in data]
        else:
            data = [(val.lower() if val != 'N/A' else '', item) for val, item in data]  # Case-insensitive for strings
        
        # Determine sort order
        if self.sort_column_name == col:
            reverse = not self.sort_reverse  # Toggle if same column
        else:
            reverse = False  # Default to ascending for new column
        
        # Sort data
        data.sort(reverse=reverse)
        
        # Rearrange items in table
        for index, (val, item) in enumerate(data):
            self.table.move(item, '', index)
        
        # Update sorting state
        self.sort_column_name = col
        self.sort_reverse = reverse
        
        # Update header commands to reflect new sort direction
        self.table.heading(col, command=lambda: self.sort_column(col, not reverse))

def main():
    import signal
    import sys

    def signal_handler(sig, frame):
        print("Exiting gracefully...")
        plt.close('all')
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        parser = argparse.ArgumentParser(description="Visualize hydrologic modeling runs")
        parser.add_argument('--data-path', type=str, default="/home/jlaser/code/CIROH/ngen-datastream/data",
                           help="Path to the data directory containing run folders")
        args = parser.parse_args()
        DATA_PATH = args.data_path
        
        print(f"Using data path: {DATA_PATH}")
        if not Path(DATA_PATH).exists():
            print(f"Error: Data path {DATA_PATH} does not exist")
            sys.exit(1)
        
        print("Starting app")
        root = tk.Tk()
        print("Tk window created")
        app = HydrologicGUI(root, DATA_PATH)
        print("App initialized")
        try:
            print("Entering mainloop")
            root.mainloop()
        except KeyboardInterrupt:
            print("Caught KeyboardInterrupt, destroying root")
            root.destroy()
        except Exception as e:
            print(f"Error in mainloop: {e}")
            root.destroy()
        finally:
            print("Mainloop exited")
            try:
                plt.close('all')
                root.destroy()
                root.quit()
            except tk.TclError:
                pass
    except Exception as e:
        print(f"Error during initialization: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
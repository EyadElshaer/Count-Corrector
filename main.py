import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import shutil
from difflib import SequenceMatcher
import threading
import time
import random
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileChangeHandler(FileSystemEventHandler):
    """Watches for file system events and triggers scanning when files change"""
    def __init__(self, parent, directory):
        super().__init__()
        self.parent = parent
        self.directory = directory
        self.pending_scan = False
        self.last_scan_time = 0
        self.min_scan_interval = 3  # Reduced from 10 seconds to 3 seconds for better responsiveness
        self.changes_detected = False
        self.throttle_timer = None

    def on_any_event(self, event):
        # Ignore directory events and .tmp files
        if event.is_directory or (hasattr(event, 'src_path') and event.src_path.endswith('.tmp')):
            return
            
        current_time = time.time()
        print(f"File system event: {event.event_type} {getattr(event, 'src_path', '')}")
        
        # Mark that changes have been detected
        self.changes_detected = True
        
        # Cancel existing timer if it exists
        if self.throttle_timer:
            self.parent.root.after_cancel(self.throttle_timer)
        
        # If we recently scanned, schedule the scan for later
        time_since_last_scan = current_time - self.last_scan_time
        if time_since_last_scan < self.min_scan_interval:
            # Set timer for throttled scan
            self.throttle_timer = self.parent.root.after(
                int((self.min_scan_interval - time_since_last_scan) * 1000), 
                self.trigger_scan
            )
            self.pending_scan = True
            print(f"Throttling scan, will execute in {int(self.min_scan_interval - time_since_last_scan)} seconds")
        else:
            # Trigger scan immediately
            self.trigger_scan()
    
    def trigger_scan(self):
        """Actually trigger the scan after throttling"""
        if self.changes_detected:
            print("File system changes detected")
            self.last_scan_time = time.time()
            self.changes_detected = False
            self.pending_scan = False
            # Only update UI if auto-update is enabled
            if self.parent.auto_update_var.get():
                print("Triggering UI update due to file system changes")
                self.parent.scan_for_similar()
            else:
                print("Auto-update disabled - not updating UI for file changes")

class SimilarFolderFinder:
    def __init__(self, root):
        self.root = root
        self.root.title("Count Corrector")
        self.root.geometry("1000x600")  # Wider window to accommodate filter panel
        self.root.minsize(800, 400)
        
        # Variables
        self.scan_directory = tk.StringVar()
        self.similarity_threshold = 0.35  # Lowered from 0.4 to catch more similar items
        self.status_var = tk.StringVar(value="Ready")
        self.auto_update_var = tk.BooleanVar(value=True)  # Auto-update enabled by default
        
        # Files and filters
        self.all_file_types = set()  # All file types in the directory
        self.file_type_extensions = {}  # Store file types with their extensions
        self.file_type_filters = {}  # Checkbuttons for each file type
        self.filter_vars = {}  # Variables for filter checkboxes
        self.showing_all = True  # Whether all filters are selected
        
        # Setup UI
        self.setup_ui()
        
        # Data storage
        self.similar_groups = []
        self.excluded_items = set()  # Store excluded items
        
        # File system observer
        self.observer = None
        self.event_handler = None
        
        # Auto scan timer
        self.auto_scan_timer = None
        
        # Define file types mapping
        self.file_types = {
            '.txt': 'Text Document',
            '.doc': 'Word Document',
            '.docx': 'Word Document',
            '.pdf': 'PDF Document',
            '.jpg': 'JPEG Image',
            '.jpeg': 'JPEG Image',
            '.png': 'PNG Image',
            '.gif': 'GIF Image',
            '.mp3': 'MP3 Audio',
            '.mp4': 'MP4 Video',
            '.avi': 'AVI Video',
            '.mov': 'QuickTime Video',
            '.zip': 'ZIP Archive',
            '.rar': 'RAR Archive',
            '.7z': '7-Zip Archive',
            '.exe': 'Executable',
            '.msi': 'Windows Installer',
            '.html': 'HTML Document',
            '.css': 'CSS Document',
            '.js': 'JavaScript File',
            '.py': 'Python Script',
            '.c': 'C Source File',
            '.cpp': 'C++ Source File',
            '.java': 'Java Source File',
            '.xls': 'Excel Spreadsheet',
            '.xlsx': 'Excel Spreadsheet',
            '.ppt': 'PowerPoint Presentation',
            '.pptx': 'PowerPoint Presentation',
        }
        
        # Set up a timer for periodic directory scanning
        self.setup_periodic_scan()
        
        # Initialize with default directory (Downloads folder)
        self.initialize_default_directory()
    
    def initialize_default_directory(self):
        """Initialize with prompt to select a directory"""
        # Show a dialog to select directory on startup instead of using a default
        self.status_var.set("Please select a directory to scan")
        self.root.update_idletasks()
        
        # Show directory selection dialog
        directory = filedialog.askdirectory(title="Select Directory to Monitor")
        
        if directory:
            self.scan_directory.set(directory)
            # Start file system watcher
            self.start_watching_directory(directory)
            # Initial scan
            self.scan_for_similar()
            self.status_var.set(f"Monitoring directory: {directory} (Auto-update is {('ON' if self.auto_update_var.get() else 'OFF')})")
        else:
            # User canceled directory selection
            self.status_var.set("No directory selected. Please use 'Browse' to select a directory.")
    
    def setup_periodic_scan(self):
        """
        Set up a periodic scan that checks for directory changes every 5 minutes.
        This is to catch any changes that might have been missed by the file system watcher.
        """
        def periodic_scan():
            # Always check directory, but only update UI based on auto_update setting
            directory = self.scan_directory.get()
            if os.path.isdir(directory):
                if self.auto_update_var.get():
                    self.status_var.set("Performing periodic scan...")
                    self.scan_for_similar()
                    self.status_var.set("Periodic scan complete")
                else:
                    # Still scan but don't update UI
                    print("Periodic check completed - auto update disabled")
            
            # Schedule the next scan 
            self.root.after(300000, periodic_scan)  # 300,000 ms = 5 minutes
        
        # Start the first scan after 5 minutes
        self.root.after(300000, periodic_scan)
    
    def ensure_watcher_running(self):
        """Ensure the file system watcher is running correctly"""
        directory = self.scan_directory.get()
        if directory and os.path.isdir(directory):
            if not self.observer or not self.observer.is_alive():
                self.start_watching_directory(directory)
                self.status_var.set(f"Restarted file monitoring for: {directory}")
                print("Restarted file system watcher")
        
    def toggle_auto_update(self):
        """Update status based on auto-update checkbox state"""
        if self.auto_update_var.get():
            self.status_var.set("Auto-update ON - UI will update automatically when files change")
            # Ensure watcher is running
            self.ensure_watcher_running()
        else:
            self.status_var.set("Auto-update OFF - UI will NOT update when files change")
            # File system watcher remains active but won't update UI
    
    def get_file_type(self, file_path):
        """Get a descriptive file type based on extension"""
        if os.path.isdir(file_path):
            return "Folder"
            
        # Get the file extension
        _, ext = os.path.splitext(file_path.lower())
        
        # Return the descriptive type or a generic one
        return self.file_types.get(ext, f"{ext[1:].upper()} File" if ext else "File")
    
    def get_file_ext(self, file_path):
        """Get just the file extension for display"""
        if os.path.isdir(file_path):
            return ""
        
        _, ext = os.path.splitext(file_path.lower())
        return ext
        
    def setup_ui(self):
        # Main layout - create a paned window to hold results and filter panels
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create style for normal elements (removing the small font style)
        style = ttk.Style()
        # style.configure("Small.TCheckbutton", font=("", 7))  # Removing smaller font
        
        # Frame for directory selection
        dir_frame = ttk.LabelFrame(main_frame, text="Directory Selection", padding="10")
        dir_frame.pack(fill=tk.X, pady=5)
        
        # Directory selection with Browse button
        dir_selection_frame = ttk.Frame(dir_frame)
        dir_selection_frame.pack(fill=tk.X)
        ttk.Label(dir_selection_frame, text="Directory to scan:").pack(side=tk.LEFT)
        ttk.Entry(dir_selection_frame, textvariable=self.scan_directory, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(dir_selection_frame, text="Browse", command=self.browse_directory).pack(side=tk.LEFT)
        
        # Auto-update checkbox
        auto_update_frame = ttk.Frame(dir_frame)
        auto_update_frame.pack(fill=tk.X, pady=(5, 0))
        auto_update_cb = ttk.Checkbutton(
            auto_update_frame,
            text="Auto update UI when files change",
            variable=self.auto_update_var,
            command=self.toggle_auto_update
        )
        auto_update_cb.pack(side=tk.LEFT, padx=5)
        
        # Create a horizontal paned window for filter and results panels
        self.paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Left side - Filter panel (wider to show extensions)
        filter_panel = ttk.Frame(self.paned_window)
        self.paned_window.add(filter_panel, weight=3)  # Filter takes 3/20 of the space
        
        # Right side - Results panel
        results_panel = ttk.Frame(self.paned_window)
        self.paned_window.add(results_panel, weight=17)  # Results take 17/20 of the space
        
        # Setup Filter Panel (now on the left)
        filter_label = ttk.Label(filter_panel, text="Filters")
        filter_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Frame for Select All / Deselect All button
        self.select_all_frame = ttk.Frame(filter_panel)
        self.select_all_frame.pack(fill=tk.X, pady=5)
        
        # Initially show Select All button
        self.select_all_btn = ttk.Button(
            self.select_all_frame, 
            text="Select All", 
            command=self.select_all_types
        )
        self.select_all_btn.pack(fill=tk.X, padx=5)
        
        # Create a scrollable frame for file type filters
        filter_canvas_frame = ttk.Frame(filter_panel)
        filter_canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        filter_scrollbar = ttk.Scrollbar(filter_canvas_frame)
        filter_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.filter_canvas = tk.Canvas(
            filter_canvas_frame, 
            yscrollcommand=filter_scrollbar.set,
            background="#F0F0F0", 
            highlightthickness=0
        )
        self.filter_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        filter_scrollbar.config(command=self.filter_canvas.yview)
        
        # Create frame for checkboxes
        self.filter_checkboxes_frame = ttk.Frame(self.filter_canvas)
        self.filter_canvas.create_window((0, 0), window=self.filter_checkboxes_frame, anchor=tk.NW)
        
        # Configure filter canvas scroll region
        self.filter_checkboxes_frame.bind(
            "<Configure>", 
            lambda e: self.filter_canvas.configure(scrollregion=self.filter_canvas.bbox("all"))
        )
        
        # Add hover-based scrolling for the filter panel
        def _on_enter_filter(event):
            self.filter_canvas.bind_all("<MouseWheel>", _on_filter_mousewheel)
            
        def _on_leave_filter(event):
            self.filter_canvas.unbind_all("<MouseWheel>")
            
        def _on_filter_mousewheel(event):
            self.filter_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind hover events for the filter scrolling
        self.filter_canvas.bind("<Enter>", _on_enter_filter)
        self.filter_canvas.bind("<Leave>", _on_leave_filter)
        
        # Results area in a scrollable canvas
        results_label = ttk.Label(results_panel, text="Similar Items Found")
        results_label.pack(anchor=tk.W, pady=(10, 0))
        
        # Create a frame with canvas and scrollbar for results
        self.canvas_frame = ttk.Frame(results_panel)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Add scrollbar
        self.scrollbar = ttk.Scrollbar(self.canvas_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create canvas with scrolling capabilities
        self.canvas = tk.Canvas(self.canvas_frame, yscrollcommand=self.scrollbar.set, 
                              background="#F0F0F0", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbar
        self.scrollbar.config(command=self.canvas.yview)
        
        # Create a frame inside canvas to hold all the group frames
        self.results_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.results_frame, anchor=tk.NW, width=self.canvas.winfo_width())
        
        # Configure canvas to resize inner frame when the canvas changes size
        def configure_canvas(event):
            self.canvas.itemconfig(1, width=event.width)
        self.canvas.bind('<Configure>', configure_canvas)
        
        # Update scroll region when the size of the results frame changes
        self.results_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        # Add mousewheel scrolling for results only when hovering
        def _on_enter_results(event):
            self.canvas.bind_all("<MouseWheel>", _on_results_mousewheel)
            
        def _on_leave_results(event):
            self.canvas.unbind_all("<MouseWheel>")
            
        def _on_results_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind hover events for the results scrolling
        self.canvas.bind("<Enter>", _on_enter_results)
        self.canvas.bind("<Leave>", _on_leave_results)
        
        # Status label at bottom
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)
    
    def select_all_types(self):
        """Select all file type filters"""
        self.showing_all = True
        
        # Update all checkboxes to checked state
        for var in self.filter_vars.values():
            var.set(True)
        
        # Change button to Deselect All
        self.select_all_btn.config(text="Deselect All", command=self.deselect_all_types)
        
        # Apply filters
        self.apply_filters()
    
    def deselect_all_types(self):
        """Deselect all file type filters"""
        self.showing_all = False
        
        # Update all checkboxes to unchecked state
        for var in self.filter_vars.values():
            var.set(False)
        
        # Change button to Select All
        self.select_all_btn.config(text="Select All", command=self.select_all_types)
        
        # Apply filters
        self.apply_filters()
    
    def apply_filters(self):
        """Apply file type filters to the displayed results"""
        # Get selected file types
        selected_types = {file_type for file_type, var in self.filter_vars.items() if var.get()}
        
        # Debug information
        print(f"Selected filters: {selected_types}")
        
        # If no types are selected, hide everything
        if len(selected_types) == 0:
            for group_frame in self.results_frame.winfo_children():
                group_frame.pack_forget()
            return
        
        # Show all groups if all types are selected
        all_selected = len(selected_types) == len(self.filter_vars)
        
        # Hide/show items based on their file type
        for group_frame in self.results_frame.winfo_children():
            visible_items = 0
            
            # Check label frames inside the group frame (which contain actual items)
            for border_frame in group_frame.winfo_children():
                if not isinstance(border_frame, ttk.LabelFrame):
                    continue
                    
                # Process each item in the group
                for widget in border_frame.winfo_children():
                    if isinstance(widget, ttk.Frame) and widget.winfo_class() == "TFrame":
                        # Skip merge buttons and other non-item frames
                        if len(widget.winfo_children()) < 2:
                            continue
                            
                        # Get the file type from the second label
                        item_type = None
                        labels = [w for w in widget.winfo_children() if isinstance(w, tk.Label)]
                        
                        if len(labels) >= 2:
                            # The second label has the file type information
                            type_text = labels[1].cget("text")
                            if "(" in type_text and ")" in type_text:
                                # Extract just the file type part
                                type_text = type_text.strip("()")
                                for filter_type in selected_types:
                                    if filter_type in type_text:
                                        item_type = filter_type
                                        break
                        
                        # Show if this type is selected or all types are selected
                        if all_selected or item_type in selected_types:
                            widget.pack(fill=tk.X, expand=True, pady=2)
                            visible_items += 1
                        else:
                            widget.pack_forget()
            
            # Hide the group entirely if it has no visible items
            if visible_items == 0:
                group_frame.pack_forget()
            else:
                group_frame.pack(fill=tk.X, expand=True, padx=5, pady=5)
    
    def update_file_type_filters(self, file_types):
        """Update the file type filter checkboxes based on found extensions"""
        # Clear existing checkboxes
        for widget in self.filter_checkboxes_frame.winfo_children():
            widget.destroy()
            
        # Create checkbox for each file type
        self.filter_vars = {}
        
        # Sort file types alphabetically
        sorted_types = sorted(file_types)
        
        # Create checkboxes with proper layout and full extension names
        for idx, file_type in enumerate(sorted_types):
            # Create a nice display name that shows the full extension
            display_name = file_type
            if file_type == "":
                display_name = "Files with no extension"
            elif file_type.startswith("."):
                display_name = file_type  # Show full extension name
                
            var = tk.BooleanVar(value=True)
            self.filter_vars[file_type] = var
            
            # Create frame for each checkbox with proper padding
            cb_frame = ttk.Frame(self.filter_checkboxes_frame)
            cb_frame.pack(fill="x", padx=3, pady=3, anchor="w")
            
            # Create checkbox with full width to show entire extension
            cb = ttk.Checkbutton(cb_frame, text=display_name, variable=var, 
                                command=self.apply_filters, width=20)
            cb.pack(side="left", fill="x", expand=True)
    
    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.scan_directory.set(directory)
            # Always start monitoring the directory
            self.start_watching_directory(directory)
            # Initial scan to display results
            self.scan_for_similar()
            # Update status
            self.status_var.set(f"Monitoring directory: {directory} (Auto-update is {('ON' if self.auto_update_var.get() else 'OFF')})")
    
    def start_watching_directory(self, directory):
        """Set up file system monitoring for auto-updates"""
        # Stop existing observer if any
        if self.observer:
            self.observer.stop()
            self.observer.join()
            
        # Create new observer
        self.event_handler = FileChangeHandler(self, directory)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, directory, recursive=True)
        self.observer.start()
        print(f"Started monitoring directory: {directory}")
    
    def calculate_similarity(self, str1, str2):
        """
        Calculate similarity between two strings with improved algorithm.
        Focus on letter-by-letter similarity rather than loose pattern matching.
        Optimized for speed and accuracy for cases like "wow" and "wow01".
        """
        # Convert to lowercase for case-insensitive comparison
        s1, s2 = str1.lower(), str2.lower()
        
        # Special case: Check if one string is a prefix of another plus numbers
        # This handles cases like "wow" and "wow01"
        def is_prefix_plus_numbers(a, b):
            # Find which string might be the prefix
            shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
            
            # Check if longer starts with shorter
            if longer.startswith(shorter):
                # Check if the remaining part is just digits
                suffix = longer[len(shorter):]
                if suffix and suffix.isdigit():
                    return True
            return False
        
        # If one string is a prefix of another plus numbers, consider them very similar
        if is_prefix_plus_numbers(s1, s2):
            return 0.9  # High similarity score
        
        # Quick rejection for very different lengths (except for prefix+number case which we already handled)
        if abs(len(s1) - len(s2)) > min(len(s1), len(s2)) // 2:
            return 0.0
        
        # Get the basic similarity ratio
        basic_ratio = SequenceMatcher(None, s1, s2).ratio()
        
        # Quick acceptance for very similar strings
        if basic_ratio > 0.8:
            return basic_ratio
        
        # Calculate letter position similarity
        min_len = min(len(s1), len(s2))
        max_len = max(len(s1), len(s2))
        
        # If lengths are very different, reduce similarity
        length_difference = abs(len(s1) - len(s2))
        if length_difference > min_len // 2:
            return basic_ratio * 0.7  # Penalize significantly different lengths
        
        # Count matching characters in the same positions
        position_matches = sum(1 for i in range(min_len) if i < len(s1) and i < len(s2) and s1[i] == s2[i])
        position_ratio = position_matches / max_len if max_len > 0 else 0
        
        # Calculate normalized edit distance (0-1 range)
        # Use direct comparison for short strings, otherwise use edit distance
        if max_len < 10:  # For short strings, we can do simple comparison
            diff_chars = sum(1 for i in range(min_len) if s1[i] != s2[i])
            edit_ratio = 1.0 - (diff_chars + length_difference) / max(max_len, 1)
        else:
            # Calculate edit distance (Levenshtein distance)
            # This measures how many single-character edits are needed to change one string into the other
            def levenshtein(a, b):
                # More efficient iterative implementation
                if a == b: return 0
                if not a: return len(b)
                if not b: return len(a)
                
                # Initialize matrix
                matrix = [[0 for _ in range(len(b) + 1)] for _ in range(len(a) + 1)]
                
                # Fill first row and column
                for i in range(len(a) + 1):
                    matrix[i][0] = i
                for j in range(len(b) + 1):
                    matrix[0][j] = j
                
                # Fill rest of the matrix
                for i in range(1, len(a) + 1):
                    for j in range(1, len(b) + 1):
                        cost = 0 if a[i-1] == b[j-1] else 1
                        matrix[i][j] = min(
                            matrix[i-1][j] + 1,      # deletion
                            matrix[i][j-1] + 1,      # insertion
                            matrix[i-1][j-1] + cost  # substitution
                        )
                
                return matrix[len(a)][len(b)]
            
            try:
                edit_distance = levenshtein(s1, s2)
                edit_ratio = 1 - (edit_distance / max(len(s1), len(s2)))
            except Exception:  # Fall back if there's any issue
                edit_ratio = basic_ratio
        
        # Special case: Exact same string with just a few characters different
        if len(s1) == len(s2):
            diff_chars = sum(1 for i in range(len(s1)) if s1[i] != s2[i])
            # Only boost if just 1-2 character differences in reasonably sized strings
            if diff_chars <= 2 and len(s1) >= 4:
                return max(basic_ratio, 0.7)
                
        # Special case: One string is almost a complete substring of the other
        # This helps with cases like "filename" and "filename1" or "file" and "file_old"
        if len(s1) < len(s2) and s2.startswith(s1) and len(s2) - len(s1) <= 5:
            return max(0.7, basic_ratio)
        elif len(s2) < len(s1) and s1.startswith(s2) and len(s1) - len(s2) <= 5:
            return max(0.7, basic_ratio)
        
        # Weigh the different metrics (experimentally determined)
        # Give more weight to edit distance which catches cursor/kursor type matches better
        final_ratio = (basic_ratio * 0.3) + (position_ratio * 0.3) + (edit_ratio * 0.4)
        
        # The threshold should filter out matches like "Cursor" and "Curolos"
        return final_ratio
    
    def exclude_item(self, item_path, item_frame, group_items):
        """Exclude an item when its Exclude button is clicked"""
        self.excluded_items.add(item_path)
        
        # Remove from group's non-excluded items
        if item_path in group_items:
            group_items.remove(item_path)
        
        # Visual indication - gray out the item
        for widget in item_frame.winfo_children():
            if isinstance(widget, tk.Label):
                widget.configure(foreground="gray")
            elif isinstance(widget, ttk.Button) and widget["text"] == "Exclude":
                # Remove the exclude button
                widget.destroy()
                
                # Add the include button
                include_btn = ttk.Button(
                    item_frame, 
                    text="Include", 
                    style="TButton",
                    command=lambda p=item_path, f=item_frame, items=group_items: 
                        self.include_item(p, f, items)
                )
                include_btn.pack(side=tk.RIGHT, padx=5)
        
        self.status_var.set(f"Item excluded from merging: {os.path.basename(item_path)}")
    
    def include_item(self, item_path, item_frame, group_items):
        """Include an item that was previously excluded"""
        # Remove from excluded set
        if item_path in self.excluded_items:
            self.excluded_items.remove(item_path)
        
        # Add back to the non-excluded items list
        if item_path not in group_items:
            group_items.append(item_path)
        
        # Restore normal appearance
        for widget in item_frame.winfo_children():
            if isinstance(widget, tk.Label):
                widget.configure(foreground="black")
            elif isinstance(widget, ttk.Button) and widget["text"] == "Include":
                # Remove the include button
                widget.destroy()
                
                # Add back the exclude button
                exclude_btn = ttk.Button(
                    item_frame, 
                    text="Exclude", 
                    style="TButton",
                    command=lambda p=item_path, f=item_frame, items=group_items: 
                        self.exclude_item(p, f, items)
                )
                exclude_btn.pack(side=tk.RIGHT, padx=5)
        
        self.status_var.set(f"Item included for merging: {os.path.basename(item_path)}")
    
    def merge_group(self, group_items):
        """Merge a group when its Merge Group button is clicked"""
        if len(group_items) < 2:
            messagebox.showinfo("Info", "Selected group has less than 2 non-excluded items to merge.")
            return
        
        # Create merge dialog
        merge_window = tk.Toplevel(self.root)
        merge_window.title("Merge Items")
        merge_window.geometry("400x300")
        merge_window.resizable(False, False)
        merge_window.transient(self.root)
        merge_window.grab_set()
        
        # Center the window
        merge_window.update_idletasks()
        width = merge_window.winfo_width()
        height = merge_window.winfo_height()
        x = (self.root.winfo_width() // 2) - (width // 2) + self.root.winfo_x()
        y = (self.root.winfo_height() // 2) - (height // 2) + self.root.winfo_y()
        merge_window.geometry(f"+{x}+{y}")
        
        ttk.Label(merge_window, text="Select the name to use for the merged folder:", 
                font=('', 10, 'bold')).pack(pady=10)
        
        # Frame for radio buttons with scrollbar if needed
        radio_frame = ttk.Frame(merge_window)
        radio_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        selected_name = tk.StringVar()
        for item in group_items:
            ttk.Radiobutton(radio_frame, text=os.path.basename(item), 
                          variable=selected_name, value=os.path.basename(item)).pack(anchor=tk.W, pady=2)
        
        # Custom name option
        ttk.Separator(merge_window).pack(fill=tk.X, padx=20, pady=5)
        custom_frame = ttk.Frame(merge_window)
        custom_frame.pack(fill=tk.X, padx=20, pady=5)
        
        ttk.Radiobutton(custom_frame, text="Custom name:", variable=selected_name, value="__custom__").pack(side=tk.LEFT)
        custom_entry = ttk.Entry(custom_frame, width=25)
        custom_entry.pack(side=tk.LEFT, padx=5)
        
        def perform_merge():
            new_name = selected_name.get()
            if not new_name:
                messagebox.showwarning("Warning", "Please select a name for the merged folder.")
                return
            
            if new_name == "__custom__":
                new_name = custom_entry.get().strip()
                if not new_name:
                    messagebox.showwarning("Warning", "Please enter a custom name.")
                    return
            
            # Add period to the new folder name to identify it as merged
            new_name = f"{new_name}."
            
            directory = self.scan_directory.get()
            new_folder_path = os.path.join(directory, new_name)
            
            # If folder with this name already exists, modify the name but keep the period
            if os.path.exists(new_folder_path):
                # Instead of adding numbers, add "_merged" before the period
                base_name = new_name.rstrip(".")
                new_name = f"{base_name}_merged."
                new_folder_path = os.path.join(directory, new_name)
                
                # If that still exists, add a random suffix
                if os.path.exists(new_folder_path):
                    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=4))
                    new_name = f"{base_name}_{random_suffix}."
                    new_folder_path = os.path.join(directory, new_name)
            
            # Create the new folder
            try:
                os.makedirs(new_folder_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create folder: {str(e)}")
                return
            
            # Move ALL original items as subfolders - preserving both folders
            errors = []
            
            for item in group_items:
                source_path = item
                basename = os.path.basename(source_path)
                dest_path = os.path.join(new_folder_path, basename)
                
                try:
                    # Check if destination already exists (should not happen with a new folder)
                    if os.path.exists(dest_path):
                        # Add a suffix to avoid name conflicts
                        counter = 1
                        base_name = basename
                        new_item_name = f"{base_name}_copy"
                        while os.path.exists(os.path.join(new_folder_path, new_item_name)):
                            new_item_name = f"{base_name}_copy{counter}"
                            counter += 1
                        dest_path = os.path.join(new_folder_path, new_item_name)
                    
                    # Copy the entire folder/file to the destination
                    if os.path.exists(source_path):  # Double check it exists
                        if os.path.isdir(source_path):
                            # Copy directory
                            shutil.copytree(source_path, dest_path)
                        else:  # It's a file
                            shutil.copy2(source_path, dest_path)
                except Exception as e:
                    errors.append(f"Error copying {basename}: {str(e)}")
            
            # Only after all items are copied successfully, remove the originals
            for item in group_items:
                try:
                    if os.path.exists(item):
                        if os.path.isdir(item):
                            shutil.rmtree(item)
                        else:
                            os.remove(item)
                except Exception as e:
                    errors.append(f"Error removing {os.path.basename(item)}: {str(e)}")
            
            merge_window.destroy()
            
            # Report any errors
            if errors:
                messagebox.showwarning("Warning", f"Merged with {len(errors)} errors:\n" + "\n".join(errors[:3]) + 
                                     ("..." if len(errors) > 3 else ""))
            
            # Update the results
            self.scan_for_similar()
            
            messagebox.showinfo("Success", f"Items have been merged into '{new_name}'")
        
        # Button frame
        button_frame = ttk.Frame(merge_window)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Cancel", command=merge_window.destroy).pack(side=tk.RIGHT, padx=10)
        ttk.Button(button_frame, text="Merge", command=perform_merge).pack(side=tk.RIGHT, padx=5)
    
    def scan_for_similar(self):
        try:
            directory = self.scan_directory.get()
            if not directory or not os.path.isdir(directory):
                self.status_var.set("Please select a valid directory to scan")
                return
            
            threshold = self.similarity_threshold
            
            # Clear previous results
            for widget in self.results_frame.winfo_children():
                widget.destroy()
            
            self.similar_groups = []
            
            # Reset file types
            self.all_file_types = set()
            self.file_type_extensions = {}  # Store file types with their extensions
            
            # Get all folders and files in the directory
            items = [item for item in os.listdir(directory) 
                   if os.path.isdir(os.path.join(directory, item)) or 
                      os.path.isfile(os.path.join(directory, item))]
            
            # Find similar items
            processed = set()
            for i, item1 in enumerate(items):
                # Update status
                self.status_var.set(f"Scanning: {i+1}/{len(items)} - {item1}")
                
                # Allow UI to update
                self.root.update_idletasks()
                
                if item1 in processed:
                    continue
                    
                group = [item1]
                for j, item2 in enumerate(items):
                    if i != j and item2 not in processed:
                        similarity = self.calculate_similarity(item1, item2)
                        if similarity >= threshold:
                            group.append(item2)
                            processed.add(item2)
                
                if len(group) > 1:  # Only add groups with multiple similar items
                    self.similar_groups.append(group)
                    processed.add(item1)
                    
                    # Create a frame for the group with a border and light gray background
                    group_frame = ttk.Frame(self.results_frame, padding=10)
                    group_frame.pack(fill=tk.X, expand=True, padx=5, pady=5)
                    
                    # Add a thin border around the group using a ttk.LabelFrame
                    border_frame = ttk.LabelFrame(group_frame, text=f"Similar to '{item1}'", padding=10)
                    border_frame.pack(fill=tk.X, expand=True)
                    
                    # List to keep track of non-excluded items
                    non_excluded_items = []
                    
                    # Add each item in the group
                    for item in group:
                        item_path = os.path.join(directory, item)
                        item_type = self.get_file_type(item_path)
                        item_ext = self.get_file_ext(item_path)
                        
                        # Add file type to our set (only those in similar groups)
                        # Store file types with their extensions for filtering
                        self.all_file_types.add(item_type)
                        
                        # Keep track of extension for each file type
                        if item_type not in self.file_type_extensions:
                            self.file_type_extensions[item_type] = item_ext
                        
                        # Create a frame for each item with the item and exclude button
                        item_frame = ttk.Frame(border_frame)
                        item_frame.pack(fill=tk.X, expand=True, pady=2)
                        
                        # Item name and type
                        tk.Label(item_frame, text=item, anchor=tk.W, width=20).pack(side=tk.LEFT, padx=(0, 10))
                        
                        # Show file type with extension
                        if item_ext:
                            item_type_display = f"({item_type} {item_ext})"
                        else:
                            item_type_display = f"({item_type})"
                            
                        tk.Label(item_frame, text=item_type_display, anchor=tk.W, width=25).pack(side=tk.LEFT, padx=(0, 10))
                        
                        # Check if this item is already excluded and show the appropriate button
                        if item_path in self.excluded_items:
                            # Apply gray color to text for excluded items
                            for widget in item_frame.winfo_children():
                                if isinstance(widget, tk.Label):
                                    widget.configure(foreground="gray")
                                    
                            # Show Include button
                            include_btn = ttk.Button(
                                item_frame, 
                                text="Include", 
                                style="TButton",
                                command=lambda p=item_path, f=item_frame, items=non_excluded_items: 
                                    self.include_item(p, f, items)
                            )
                            include_btn.pack(side=tk.RIGHT, padx=5)
                        else:
                            # Show Exclude button
                            exclude_btn = ttk.Button(
                                item_frame, 
                                text="Exclude", 
                                style="TButton",
                                command=lambda p=item_path, f=item_frame, items=non_excluded_items: 
                                    self.exclude_item(p, f, items)
                            )
                            exclude_btn.pack(side=tk.RIGHT, padx=5)
                            
                            # Add to list of items if not excluded
                            non_excluded_items.append(item_path)
                    
                    # Add Merge Group button at the bottom of each group - CENTERED
                    merge_frame = ttk.Frame(border_frame)
                    merge_frame.pack(fill=tk.X, expand=True, pady=(10, 0))
                    
                    # Create Merge Group button in the center
                    merge_btn = ttk.Button(
                        merge_frame, 
                        text="Merge Group",
                        style="TButton",
                        command=lambda items=non_excluded_items.copy(): self.merge_group(items)
                    )
                    merge_btn.pack(pady=5, padx=5, anchor=tk.CENTER)
            
            # Print detected file types for debugging
            print(f"Detected file types: {self.all_file_types}")
            print(f"File type extensions: {self.file_type_extensions}")
            
            # Update canvas scroll region
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            # Update filter panel with only the file types found in similar groups
            self.update_file_type_filters(self.all_file_types)
            
            # Apply initial filters
            self.apply_filters()
            
            if len(self.similar_groups) == 0:
                self.status_var.set("No similar items found")
            else:
                groups = len(self.similar_groups)
                items = sum(len(group) for group in self.similar_groups)
                self.status_var.set(f"Found {groups} groups with {items} similar items")
        
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during scanning: {str(e)}")
            self.status_var.set("Error during scan")

    def __del__(self):
        """Clean up resources when the application is closed"""
        # Stop file system observer
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=1.0)  # Wait up to 1 second for the observer to stop
            except Exception as e:
                print(f"Error stopping observer: {e}")
            
        # Cancel any pending auto-scan timer
        if self.auto_scan_timer:
            try:
                self.root.after_cancel(self.auto_scan_timer)
            except Exception as e:
                print(f"Error canceling timer: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = SimilarFolderFinder(root)
    root.mainloop() 
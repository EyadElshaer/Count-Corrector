import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import shutil
from difflib import SequenceMatcher
import threading
import time
import random

class SimilarFolderFinder:
    def __init__(self, root):
        self.root = root
        self.root.title("Count Corrector")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Variables
        self.scan_directory = tk.StringVar()
        self.similarity_threshold = 0.4  # Most sensitive setting - fixed value
        self.status_var = tk.StringVar(value="Ready")
        
        # Setup UI
        self.setup_ui()
        
        # Data storage
        self.similar_groups = []
        self.excluded_items = set()  # Store excluded items
        
        # Load icons
        self.folder_icon = tk.PhotoImage(data="""
            R0lGODlhEAAQAIIAAPwCBAQCBPz+/Pz6/Pz2/PT2/PT+/PT+9CH5BAEAAAAALAAAAAAQABAA
            AANJCLrc/jDKSau9OOsth/9gKI5kaZ5oqq5s675wLM90bd94ru987//AoHBILBqPyKRyyWw6
            n9CodEqtWq/YrHbL7Xq/4LB4TC6bz58CADs=
        """)
        self.file_icon = tk.PhotoImage(data="""
            R0lGODlhEAAQAIIAAJmZmfz+/Pz6/Pz2/PT2/PT+/PT+9CH5BAEAAAAALAAAAAAQABAAAANJ
            CLrc/jDKSau9OOsth/9gKI5kaZ5oqq5s675wLM90bd94ru987//AoHBILBqPyKRyyWw6n9Co
            dEqtWq/YrHbL7Xq/4LB4TC6bz58CADs=
        """)
        
    def setup_ui(self):
        # Main layout
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Frame for directory selection
        dir_frame = ttk.LabelFrame(main_frame, text="Directory Selection", padding="10")
        dir_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(dir_frame, text="Directory to scan:").pack(side=tk.LEFT)
        ttk.Entry(dir_frame, textvariable=self.scan_directory, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(dir_frame, text="Browse", command=self.browse_directory).pack(side=tk.LEFT)
        
        # Scan button
        scan_frame = ttk.Frame(main_frame)
        scan_frame.pack(fill=tk.X, pady=5)
        ttk.Button(scan_frame, text="Scan for Similar Items", command=self.start_scan_thread).pack(pady=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(scan_frame, variable=self.progress_var, mode="determinate")
        self.progress.pack(fill=tk.X, pady=5)
        
        # Status label
        status_label = ttk.Label(scan_frame, textvariable=self.status_var)
        status_label.pack(anchor=tk.W, pady=5)
        
        # Results area
        results_frame = ttk.LabelFrame(main_frame, text="Similar Items Found", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Treeview with scrollbar
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.results_tree = ttk.Treeview(tree_frame, columns=("path", "type", "status"), show="tree", 
                                        yscrollcommand=tree_scroll.set)
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.results_tree.yview)
        
        # Configure treeview columns
        self.results_tree.column("#0", width=250)
        self.results_tree.column("path", width=300)
        self.results_tree.column("type", width=60)
        self.results_tree.column("status", width=80)
        self.results_tree.heading("path", text="Path")
        self.results_tree.heading("type", text="Type")
        self.results_tree.heading("status", text="Status")
        
        # Buttons for actions
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(action_frame, text="Merge Selected Group", command=self.merge_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Exclude from Merge", command=self.exclude_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Include in Merge", command=self.include_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Refresh Results", command=self.scan_for_similar).pack(side=tk.LEFT, padx=5)
    
    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.scan_directory.set(directory)
    
    def calculate_similarity(self, str1, str2):
        # Enhanced similarity calculation for better detection of small differences
        ratio = SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
        
        # Add special case for strings that differ by only one character
        if len(str1) == len(str2) and sum(c1 != c2 for c1, c2 in zip(str1.lower(), str2.lower())) <= 1:
            ratio = max(ratio, 0.7)  # Boost similarity for one-letter differences
            
        # Special case for prefix/suffix matches
        if str1.lower().startswith(str2.lower()) or str2.lower().startswith(str1.lower()):
            ratio = max(ratio, 0.6)  # Boost similarity for prefix matches
            
        return ratio
    
    def start_scan_thread(self):
        # Start the scan in a separate thread to keep UI responsive
        self.status_var.set("Scanning...")
        self.progress_var.set(0)
        scan_thread = threading.Thread(target=self.scan_for_similar)
        scan_thread.daemon = True
        scan_thread.start()
    
    def exclude_selected(self):
        """Exclude selected item(s) from merging"""
        selected = self.results_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select item(s) to exclude.")
            return
        
        # Process each selected item
        for item_id in selected:
            # Don't exclude group headers
            if not self.results_tree.parent(item_id):
                continue
                
            # Add to excluded set
            item_text = self.results_tree.item(item_id, "text")
            item_path = self.results_tree.item(item_id, "values")[0]
            self.excluded_items.add(item_path)
            
            # Update status in treeview
            self.results_tree.set(item_id, "status", "Excluded")
            # Visual indication - gray out the item
            self.results_tree.item(item_id, tags=("excluded",))
        
        # Configure tag appearance
        self.results_tree.tag_configure("excluded", foreground="gray")
        
        self.status_var.set(f"{len(selected)} item(s) excluded from merging")
    
    def include_selected(self):
        """Re-include previously excluded item(s) for merging"""
        selected = self.results_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select item(s) to include.")
            return
        
        count = 0
        # Process each selected item
        for item_id in selected:
            # Only process items, not groups
            if not self.results_tree.parent(item_id):
                continue
                
            # Remove from excluded set
            item_path = self.results_tree.item(item_id, "values")[0]
            if item_path in self.excluded_items:
                self.excluded_items.remove(item_path)
                count += 1
                
                # Update status in treeview
                self.results_tree.set(item_id, "status", "")
                # Remove visual indication
                self.results_tree.item(item_id, tags=())
        
        self.status_var.set(f"{count} item(s) included for merging")
    
    def scan_for_similar(self):
        try:
            # Clear excluded items when starting a new scan
            self.excluded_items.clear()
            
            directory = self.scan_directory.get()
            if not directory or not os.path.isdir(directory):
                messagebox.showerror("Error", "Please select a valid directory to scan.")
                self.status_var.set("Ready")
                return
            
            threshold = self.similarity_threshold
            
            # Clear previous results
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            self.similar_groups = []
            
            # Get all folders and files in the directory
            items = [item for item in os.listdir(directory) 
                   if os.path.isdir(os.path.join(directory, item)) or 
                      os.path.isfile(os.path.join(directory, item))]
            
            # Update progress based on total items
            total_items = len(items)
            if total_items == 0:
                self.status_var.set("No items found in the directory")
                self.progress_var.set(100)
                return
            
            # Find similar items
            processed = set()
            for i, item1 in enumerate(items):
                # Update progress
                self.progress_var.set((i / total_items) * 100)
                self.status_var.set(f"Scanning: {i+1}/{total_items} - {item1}")
                
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
                    
                    # Add to treeview
                    group_id = self.results_tree.insert("", "end", text=f"Group {len(self.similar_groups)}", 
                                                      open=True, image='')
                    for item in group:
                        item_path = os.path.join(directory, item)
                        item_type = "Folder" if os.path.isdir(item_path) else "File"
                        icon = self.folder_icon if item_type == "Folder" else self.file_icon
                        self.results_tree.insert(group_id, "end", text=item, 
                                               values=(item_path, item_type, ""),
                                               image=icon)
            
            # Final progress update
            self.progress_var.set(100)
            
            if len(self.similar_groups) == 0:
                self.status_var.set(f"No similar items found (most sensitive setting)")
            else:
                groups = len(self.similar_groups)
                items = sum(len(group) for group in self.similar_groups)
                self.status_var.set(f"Found {groups} groups with {items} similar items")
        
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during scanning: {str(e)}")
            self.status_var.set("Error during scan")
            self.progress_var.set(0)
    
    def merge_selected(self):
        try:
            selected = self.results_tree.selection()
            if not selected:
                messagebox.showinfo("Info", "Please select a group or an item to merge.")
                return
            
            # Get the parent (group) of the selected item
            parent = self.results_tree.parent(selected[0])
            if parent:  # If parent exists, the selection is an item in a group
                group_id = parent
            else:  # Otherwise, the selection is already a group
                group_id = selected[0]
            
            # Get all items in the group EXCLUDING those that are marked to exclude
            group_items = self.results_tree.get_children(group_id)
            items = []
            for item_id in group_items:
                item_path = self.results_tree.item(item_id, "values")[0]
                if item_path not in self.excluded_items:
                    items.append(self.results_tree.item(item_id, "text"))
            
            if len(items) < 2:
                messagebox.showinfo("Info", "Selected group has less than 2 non-excluded items to merge.")
                return
            
            # Ask user which name to use
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
            for item in items:
                ttk.Radiobutton(radio_frame, text=item, variable=selected_name, value=item).pack(anchor=tk.W, pady=2)
            
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
                
                for item in items:
                    source_path = os.path.join(directory, item)
                    dest_path = os.path.join(new_folder_path, item)
                    
                    try:
                        # Check if destination already exists (should not happen with a new folder)
                        if os.path.exists(dest_path):
                            # Add a suffix to avoid name conflicts
                            counter = 1
                            base_name = item
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
                        errors.append(f"Error copying {item}: {str(e)}")
                
                # Only after all items are copied successfully, remove the originals
                for item in items:
                    source_path = os.path.join(directory, item)
                    try:
                        if os.path.exists(source_path):
                            if os.path.isdir(source_path):
                                shutil.rmtree(source_path)
                            else:
                                os.remove(source_path)
                    except Exception as e:
                        errors.append(f"Error removing {source_path}: {str(e)}")
                
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
        
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during the merge operation: {str(e)}")
            self.status_var.set("Error during merge")

if __name__ == "__main__":
    root = tk.Tk()
    app = SimilarFolderFinder(root)
    root.mainloop() 
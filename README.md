# Count Corrector (Under Development)

A Windows application that helps you identify and merge similar folders and files, reducing clutter and ensuring accurate file counts.

## Features

- Scan any directory for similar folder and file names
- Adjustable similarity levels with convenient preset options
- Visual display of similar items grouped together with folder/file icons
- Easy merging interface that preserves folder structure
- **NEW: Keeps original folders as subfolders** instead of just moving their contents
- Proper handling of both files and folders
- Conflict resolution for duplicate file names
- Progress indicator and status updates during scanning
- Multi-threaded operation for smooth UI experience

## How to Use

1. **Install Python**: Make sure you have Python 3.6+ installed on your Windows system.

2. **Run the Application**:
   - Double-click the `run_app.bat` file to launch the application
   - Or run from command line: `python main.py`

3. **Select a directory**: Click the "Browse" button to choose the folder you want to scan.

4. **Choose a similarity level**: Use the dropdown to select how similar names must be to be grouped:
   - "Very similar" - Only matches highly similar names (fewer results)
   - "Somewhat similar" - Balanced matching (default)
   - "Minimal similarity" - Matches more distantly related names (more results)

5. **Scan for similar items**: Click "Scan for Similar Items" to analyze the directory.

6. **Review results**: Similar items will be grouped in the results area.

7. **Merge similar items**:
   - Select a group or an item within a group
   - Click "Merge Selected Group"
   - Choose which name to keep for the parent folder, or enter a custom name
   - Confirm the merge - this will move all the original folders as subfolders into the new parent folder

## Examples

- "Cursor" and "Kursor" might be identified as similar
- "Documents" and "My Documents" could be grouped together
- "Project1" and "Project 1" would likely be matched

## How Merging Works

When you merge folders/files:

1. A new parent folder with your chosen name is created
2. The original folders/files are moved into this new parent folder as-is
3. The application preserves the entire folder structure
4. If there are naming conflicts, items will be renamed with "_copy" suffixes

This means that after merging "Cursor" and "Kursor", you'll have a folder structure like:
```
NewFolderName/
  ├── Cursor/
  │   └── (original contents of Cursor)
  └── Kursor/
      └── (original contents of Kursor)
```

## Troubleshooting

If you encounter any issues:

1. Make sure Python 3.6 or higher is installed and available in your system PATH
2. Try running the application from the command line to see any error messages
3. For permission errors, try running the application as administrator
4. If you're not seeing enough matches, try a lower similarity level from the dropdown menu 

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from tkinter import filedialog, simpledialog
from tkinter.scrolledtext import ScrolledText
import csv
import tkinter as tk
import sqlite3
import os
from FileOrganizer import (
    initialize_db,
    get_video_files,
    store_video_files_in_db,
    update_device_metadata,
    dump_all_video_files,
    dump_all_device_metadata,
    delete_video_files_by_device_id,
    DEVICE_METADATA_TABLE
)

def graphical_user_interface():
    """
    Provides a graphical user interface for interacting with the video file database.
    Allows users to scan folders, dump records, and manage the database through a modern GUI.
    """
    # Initialize the database
    try:
        db_connection = initialize_db()
    except Exception as e:
        Messagebox.show_error(f"Failed to initialize database: {e}", "Database Error")
        return

    # Create the main window with a modern theme
    root = ttk.Window(themename="cosmo")
    root.title("Files Manager")
    root.geometry("1200x800")
    root.minsize(800, 600)
    
    # Set light gray background
    root.configure(bg="#f0f0f0")
    
    # Configure the style for the Treeview headings and frames
    style = ttk.Style()
    style.configure("Treeview.Heading", font=("Helvetica", 11, "bold"))
    style.configure("Light.TFrame", background="#f0f0f0")
    style.configure("Treeview", 
                   background="#ffffff",  # White background for the table
                   fieldbackground="#ffffff",  # White background for the fields
                   foreground="black",  # Black text
                   rowheight=25)  # Slightly taller rows for better readability
    style.map('Treeview',
              background=[('selected', '#0078D7')],  # Blue highlight for selected items
              foreground=[('selected', 'white')])  # White text for selected items
    
    # Configure transparent label style
    style.configure("Transparent.TLabel", background="#f0f0f0")
    style.configure("LightIcon.TLabel", background="#f0f0f0", foreground="#666666")  # Light gray color for icons

    # Configure milder button styles
    style.configure("MildPrimary.TButton", 
                   background="#4a90e2",  # Softer blue
                   foreground="white")
    style.map("MildPrimary.TButton",
              background=[('active', '#357abd')])  # Darker blue on hover
    
    style.configure("MildDanger.TButton", 
                   background="#e25c5c",  # Softer red
                   foreground="white")
    style.map("MildDanger.TButton",
              background=[('active', '#c44c4c')])  # Darker red on hover

    # Store all video items for filtering
    all_video_items = []

    def format_size(size_bytes):
        """Format file size in human readable format"""
        try:
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024
            return f"{size_bytes:.1f} TB"
        except Exception:
            return "N/A"

    def filter_video_list():
        """Filter the video list based on search text"""
        try:
            search_text = search_var.get().lower()
            
            # Clear current items
            for item in video_tree.get_children():
                video_tree.delete(item)
            
            # Filter and show matching items
            for item in all_video_items:
                if search_text in item['filename'].lower():
                    video_tree.insert("", END, values=(
                        item['volume_name'],
                        item['filename'],
                        item['filesize'],
                        item['created_date'],
                        item['modified_date']
                    ))
        except Exception as e:
            print(f"Error filtering video list: {e}")

    def refresh_video_list(device_id=None):
        """Refresh the video files list"""
        try:
            # Clear the search
            search_var.set("")
            
            # Clear current items
            for item in video_tree.get_children():
                video_tree.delete(item)
            
            # Clear stored items
            all_video_items.clear()
            
            videos = dump_all_video_files(db_connection, device_id)
            
            # Get device volume names
            cursor = db_connection.cursor()
            try:
                device_volumes = {}
                cursor.execute(f"SELECT deviceid, volumename FROM {DEVICE_METADATA_TABLE}")
                for device in cursor.fetchall():
                    device_volumes[device[0]] = device[1]
                
                for video in videos:
                    # Get volume name for the device
                    volume_name = device_volumes.get(video['device_DUID'], "Unknown")
                    
                    # Store the item for filtering
                    all_video_items.append({
                        'deviceid': video['device_DUID'],
                        'volume_name': volume_name,
                        'filename': video['filename'],
                        'fullpath': video['fullpath'],  # Store the full path
                        'filesize': format_size(video['filesize']),
                        'created_date': video['created_date'],
                        'modified_date': video['modified_date']
                    })
                    
                    # Insert into treeview
                    video_tree.insert("", END, values=(
                        volume_name,
                        video['filename'],
                        format_size(video['filesize']),
                        video['created_date'],
                        video['modified_date']
                    ))
            finally:
                cursor.close()
        except sqlite3.Error as e:
            Messagebox.show_error(f"Database error: {e}", "Error")
        except Exception as e:
            Messagebox.show_error(f"Error refreshing video list: {e}", "Error")

    def refresh_device_list():
        """Refresh the device list"""
        for item in device_tree.get_children():
            device_tree.delete(item)
        
        try:
            devices = dump_all_device_metadata(db_connection)
            for device in devices:
                # Format sizes in GB
                total_size = f"{device['total_volume_size'] / (1024**3):.1f} GB" if device.get('total_volume_size') else "N/A"
                free_space = f"{device['remaining_free_space'] / (1024**3):.1f} GB" if device.get('remaining_free_space') else "N/A"
                
                # Store device ID as a tag for the item
                item = device_tree.insert("", END, values=(
                    device['volumename'],
                    total_size,
                    free_space
                ))
                # Store device ID as a tag
                device_tree.item(item, tags=(str(device['deviceid']),))
        except sqlite3.Error as e:
            Messagebox.show_error(f"Database error: {e}", "Error")
        except Exception as e:
            Messagebox.show_error(f"Error refreshing device list: {e}", "Error")

    def update_device_info(device_id):
        """Update the device information labels with the selected device's details"""
        try:
            cursor = db_connection.cursor()
            cursor.execute(f"SELECT * FROM {DEVICE_METADATA_TABLE} WHERE deviceid = ?", (device_id,))
            device = cursor.fetchone()
            if device:
                device_id_label.configure(text=f"Device ID: {device[0]}")
                volume_label.configure(text=f"Volume: {device[3]}")
                total_size = f"{device[5] / (1024**3):.1f} GB" if device[5] else "N/A"
                total_size_label.configure(text=f"Total Size: {total_size}")
                free_space = f"{device[6] / (1024**3):.1f} GB" if device[6] else "N/A"
                free_space_label.configure(text=f"Free Space: {free_space}")
                last_scanned_label.configure(text=f"Last Scanned: {device[4]}")
            else:
                # Clear labels if no device is found
                device_id_label.configure(text="Device ID: ")
                volume_label.configure(text="Volume: ")
                total_size_label.configure(text="Total Size: ")
                free_space_label.configure(text="Free Space: ")
                last_scanned_label.configure(text="Last Scanned: ")
        except Exception as e:
            print(f"Error updating device info: {e}")
        finally:
            cursor.close()

    def on_device_select(event):
        """Handle device selection"""
        try:
            selection = device_tree.selection()
            if selection:
                # Get device ID from the item's tag
                device_id = int(device_tree.item(selection[0])['tags'][0])
                refresh_video_list(device_id)
                update_device_info(device_id)
            else:
                # Clear device info if no device is selected
                update_device_info(None)
        except Exception as e:
            Messagebox.show_error(f"Error selecting device: {e}", "Error")

    def scan_folder():
        """Handle folder scanning"""
        try:
            folder_path = filedialog.askdirectory(title="Select Folder to Scan")
            if folder_path:
                video_files = get_video_files(folder_path)
                if video_files:
                    store_video_files_in_db(video_files, db_connection)
                    update_device_metadata(folder_path, db_connection)
                    refresh_device_list()
                    refresh_video_list()
                    Messagebox.show_info("Database updated successfully.", "Success")
                else:
                    Messagebox.show_warning("No video files found in the specified folder.", "Warning")
        except sqlite3.Error as e:
            Messagebox.show_error(f"Database error: {e}", "Error")
        except Exception as e:
            Messagebox.show_error(f"Error scanning folder: {e}", "Error")

    def delete_device_records():
        """Handle deleting device records"""
        try:
            selection = device_tree.selection()
            if not selection:
                Messagebox.show_warning("Please select a device to delete.", "Warning")
                return

            device_id = int(device_tree.item(selection[0])['tags'][0])
            if Messagebox.show_question(
                f"Are you sure you want to delete all records for device {device_id}?",
                "Confirm Deletion"
            ):
                delete_video_files_by_device_id(device_id, db_connection)
                refresh_device_list()
                refresh_video_list()
                Messagebox.show_info("Records deleted successfully.", "Success")
        except sqlite3.Error as e:
            Messagebox.show_error(f"Database error: {e}", "Error")
        except Exception as e:
            Messagebox.show_error(f"Error deleting device records: {e}", "Error")

    def on_closing():
        """Handle window closing"""
        try:
            db_connection.close()
        except Exception as e:
            print(f"Error closing database connection: {e}")
        root.destroy()

    # Create title bar
    title_frame = ttk.Frame(root, padding=10, style="Light.TFrame")
    title_frame.pack(fill=X)
    
    # Create a frame for the title and search bar
    title_content_frame = ttk.Frame(title_frame, style="Light.TFrame")
    title_content_frame.pack(fill=X)
    
    title_label = ttk.Label(
        title_content_frame,
        text="Files Manager",
        font=("Helvetica", 18, "bold"),
        style="Transparent.TLabel"
    )
    title_label.pack(side=LEFT)

    # Add search bar to title area
    search_var = tk.StringVar()
    search_var.trace('w', lambda name, index, mode: filter_video_list())
    
    search_frame = ttk.Frame(title_content_frame, style="Light.TFrame")
    search_frame.pack(side=RIGHT)
    
    # Use a lens icon (🔍) instead of "Search:" text with light gray color
    ttk.Label(search_frame, text="🔍", style="LightIcon.TLabel").pack(side=LEFT, padx=(0, 5))
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=20)
    search_entry.pack(side=LEFT)

    # Create main content area
    content_frame = ttk.Frame(root, style="Light.TFrame")
    content_frame.pack(fill=BOTH, expand=YES, padx=10, pady=5)

    # Create left column (1/6 of screen)
    left_frame = ttk.Frame(content_frame, width=300, height=400, style="Light.TFrame")  # Added height constraint
    left_frame.pack(side=LEFT, fill=Y, padx=(0, 5))
    left_frame.pack_propagate(False)  # Prevent frame from shrinking to fit contents

    # Storage Media section
    storage_header_frame = ttk.Frame(left_frame, style="Light.TFrame")
    storage_header_frame.pack(fill=X, pady=(0, 5))

    storage_label = ttk.Label(
        storage_header_frame,
        text="Storage Media",
        font=("Helvetica", 12, "bold"),
        style="Transparent.TLabel"
    )
    storage_label.pack(anchor=CENTER)

    # Create Treeview for devices
    device_tree = ttk.Treeview(
        left_frame,
        columns=("volumename", "totalsize", "freespace"),
        show="headings",
        height=5,  # Reduced height from 10 to 5
        style="Treeview"
    )
    
    device_tree.heading("volumename", text="Volume")
    device_tree.heading("totalsize", text="Size")
    device_tree.heading("freespace", text="Free")
    
    device_tree.column("volumename", width=120)
    device_tree.column("totalsize", width=80)
    device_tree.column("freespace", width=80)
    device_tree.pack(fill=BOTH, expand=YES)

    # Create button frame at the bottom of left column
    button_frame = ttk.Frame(left_frame, padding=5, style="Light.TFrame")
    button_frame.pack(fill=X, pady=(5, 0))

    ttk.Button(
        button_frame,
        text="Scan Folder",
        command=scan_folder,
        style="MildPrimary.TButton",
        width=15
    ).pack(side=LEFT, padx=2)

    ttk.Button(
        button_frame,
        text="Delete Device",
        command=delete_device_records,
        style="MildDanger.TButton",
        width=15
    ).pack(side=LEFT, padx=2)

    # Create additional frame below buttons
    additional_frame = ttk.Frame(left_frame, padding=5, style="Light.TFrame")
    additional_frame.pack(fill=BOTH, expand=YES, pady=(5, 0))

    # Add a label to the additional frame
    additional_label = ttk.Label(
        additional_frame,
        text="Device Information",
        font=("Helvetica", 12, "bold"),
        style="Transparent.TLabel"
    )
    additional_label.pack(anchor=CENTER, pady=(0, 5))

    # Create labels for device details
    device_info_frame = ttk.Frame(additional_frame, style="Light.TFrame")
    device_info_frame.pack(fill=BOTH, expand=YES)

    # Create labels for each piece of information
    device_id_label = ttk.Label(device_info_frame, text="Device ID: ", style="Transparent.TLabel")
    device_id_label.pack(anchor=W, pady=2)
    
    volume_label = ttk.Label(device_info_frame, text="Volume: ", style="Transparent.TLabel")
    volume_label.pack(anchor=W, pady=2)
    
    total_size_label = ttk.Label(device_info_frame, text="Total Size: ", style="Transparent.TLabel")
    total_size_label.pack(anchor=W, pady=2)
    
    free_space_label = ttk.Label(device_info_frame, text="Free Space: ", style="Transparent.TLabel")
    free_space_label.pack(anchor=W, pady=2)
    
    last_scanned_label = ttk.Label(device_info_frame, text="Last Scanned: ", style="Transparent.TLabel")
    last_scanned_label.pack(anchor=W, pady=2)

    # Create right column (5/6 of screen)
    right_frame = ttk.Frame(content_frame, style="Light.TFrame")
    right_frame.pack(side=LEFT, fill=BOTH, expand=YES)

    # Media Files section
    media_header_frame = ttk.Frame(right_frame, style="Light.TFrame")
    media_header_frame.pack(fill=X, pady=(0, 5))

    media_label = ttk.Label(
        media_header_frame,
        text="Media Files",
        font=("Helvetica", 12, "bold"),
        style="Transparent.TLabel"
    )
    media_label.pack(anchor=CENTER)  # Center align the Media Files title

    # Create Treeview for video files
    video_tree = ttk.Treeview(
        right_frame,
        columns=("devicevolume", "filename", "filesize", "created_date", "modified_date"),
        show="headings",
        height=20,
        style="Treeview"
    )
    
    video_tree.heading("devicevolume", text="Device Volume")
    video_tree.heading("filename", text="Filename")
    video_tree.heading("filesize", text="Size")
    video_tree.heading("created_date", text="Created")
    video_tree.heading("modified_date", text="Modified")
    
    video_tree.column("devicevolume", width=120)
    video_tree.column("filename", width=300)
    video_tree.column("filesize", width=100)
    video_tree.column("created_date", width=150)
    video_tree.column("modified_date", width=150)
    video_tree.pack(fill=BOTH, expand=YES)

    # Create status frame below video tree
    status_frame = ttk.Frame(right_frame, style="Light.TFrame")
    status_frame.pack(fill=X, pady=(5, 0))

    # Create label for file path
    file_path_label = ttk.Label(status_frame, text="File Path: ", style="Transparent.TLabel")
    file_path_label.pack(side=LEFT, padx=5, fill=X, expand=YES)

    def on_video_select(event):
        """Handle video file selection"""
        try:
            selection = video_tree.selection()
            if selection:
                # Get the selected item's values
                item = video_tree.item(selection[0])
                values = item['values']
                
                # Get the full path from the stored items
                selected_filename = values[1]  # filename is at index 1
                for stored_item in all_video_items:
                    if stored_item['filename'] == selected_filename:
                        file_path_label.configure(text=f"File Path: {stored_item['full_pathname']}")
                        break
            else:
                # Clear status if no file is selected
                file_path_label.configure(text="File Path: ")
        except Exception as e:
            print(f"Error updating file status: {e}")
            file_path_label.configure(text="File Path: Error updating status")

    # Bind video selection event
    video_tree.bind('<<TreeviewSelect>>', on_video_select)

    # Bind device selection event
    device_tree.bind('<<TreeviewSelect>>', on_device_select)

    # Set up window closing protocol
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Initial data load
    try:
        refresh_device_list()
        refresh_video_list()
    except Exception as e:
        Messagebox.show_error(f"Error loading initial data: {e}", "Error")

    # Start the GUI event loop
    root.mainloop()

if __name__ == "__main__":
    graphical_user_interface() 
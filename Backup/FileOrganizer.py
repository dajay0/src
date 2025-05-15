import os
from datetime import datetime
import sqlite3
import win32api
import csv
import re

# Global variables for database table names
VIDEO_FILES_TABLE = "app_video_files_metadata"
DEVICE_METADATA_TABLE = "app_device_metadata"

def normalize_filename(filename):
    """
    Normalizes a filename by replacing all non-letter non-digit characters with spaces.
    
    Args:
        filename (str): The original filename
        
    Returns:
        str: The normalized filename
    """
    # Remove file extension first
    name, ext = os.path.splitext(filename)
    # Replace all non-alphanumeric characters with spaces
    normalized = re.sub(r'[^a-zA-Z0-9]', ' ', name)
    # Remove extra spaces and trim
    normalized = ' '.join(normalized.split())
    # Add back the extension
    return normalized + ext

def get_video_files(folder_name):
    """
    Takes a folder name as input and returns a list of dictionaries containing details of all video files in the folder.
    Each dictionary includes: partitionID, full pathname, filename, normalized_filename, filesize, created date, and modified date.
    """
    # Define common video file extensions
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    video_files = []

    # Check if the folder exists
    if not os.path.isdir(folder_name):
        raise ValueError(f"The folder '{folder_name}' does not exist.")

    # Iterate through files in the folder
    for root, _, files in os.walk(folder_name):
        for file in files:
            # Check if the file has a video extension
            if os.path.splitext(file)[1].lower() in video_extensions:
                full_path = os.path.join(root, file)
                try:
                    stats = os.stat(full_path)
                    video_files.append({
                        "partitionID": os.path.splitdrive(full_path)[0],
                        "full_pathname": full_path,
                        "filename": file,
                        "normalized_filename": normalize_filename(file),
                        "filesize": stats.st_size,
                        "created_date": datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                        "modified_date": datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        "device_DUID": int(stats.st_dev)
                    })
                except (PermissionError, OSError) as e:
                    print(f"Error accessing file '{full_path}': {e}")
                    continue

    return video_files

def store_video_files_in_db(video_files, db_connection):
    """
    Stores the list of video files into an SQLite database.
    
    Args:
        video_files (list): List of dictionaries containing video file details.
        db_connection (sqlite3.Connection): SQLite database connection.
    """
    cursor = db_connection.cursor()

    # Insert video file details into the table
    for video in video_files:
        try:
            cursor.execute(f"""
                INSERT INTO {VIDEO_FILES_TABLE} (partitionID, full_pathname, filename, normalized_filename, filesize, created_date, modified_date, device_DUID)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                video["partitionID"],
                video["full_pathname"],
                video["filename"],
                video["normalized_filename"],
                video["filesize"],
                video["created_date"],
                video["modified_date"],
                video["device_DUID"]
            ))
        except sqlite3.IntegrityError as e:
            print(f"Failed to insert record for file '{video['filename']}': {e}")

    # Commit the changes to the database
    db_connection.commit()

def initialize_db(db_path="video_files.db"):
    """
    Creates the video_files table in the SQLite database if it doesn't already exist and returns the connection.
    
    Args:
        db_path (str): Path to the SQLite database file. Defaults to 'video_files.db'.
    
    Returns:
        sqlite3.Connection: The SQLite connection object.
    """
    # Connect to the SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the table if it doesn't exist
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {VIDEO_FILES_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partitionID TEXT NOT NULL,
            full_pathname TEXT NOT NULL,
            filename TEXT NOT NULL,
            normalized_filename TEXT NOT NULL,
            filesize INTEGER NOT NULL,
            created_date TEXT NOT NULL,
            modified_date TEXT NOT NULL,
            device_DUID INTEGER NOT NULL,
            UNIQUE(device_DUID, full_pathname)
        )
    """)
    # Create the device_metadata table if it doesn't exist
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {DEVICE_METADATA_TABLE} (
            deviceid INTEGER PRIMARY KEY UNIQUE,
            partitionid TEXT NOT NULL,
            pathname TEXT NOT NULL,
            volumename TEXT NOT NULL,
            last_scanned DATETIME NOT NULL,
            total_volume_size INTEGER,
            remaining_free_space INTEGER
        )
    """)

    # Return the connection
    return conn

def update_device_metadata(folder_name, db_connection):
    """
    Updates the device_metadata table with the folder's details, including volume information and total volume size.
    
    Args:
        folder_name (str): The folder path to update metadata for.
        db_connection (sqlite3.Connection): SQLite database connection.
    """
    if not os.path.isdir(folder_name):
        raise ValueError(f"The folder '{folder_name}' does not exist.")
    
    partition_id = os.path.splitdrive(folder_name)[0]
    last_scanned = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Get volume information using win32api
    try:
        volume_info = win32api.GetVolumeInformation(partition_id)
        volume_name = volume_info[0]  # Volume name
        serial_number = volume_info[1]  # Volume serial number
        total_volume_size = win32api.GetDiskFreeSpaceEx(partition_id)[1]  # Total size of the volume
        remaining_free_space = win32api.GetDiskFreeSpaceEx(partition_id)[0]  # Free space on the volume
    except Exception as e:
        print(f"Unable to retrieve volume information for --{partition_id}--. Using Unknown. Error: {e}")
        volume_name = "Unknown"
        serial_number = 0
        total_volume_size = 0
        remaining_free_space = 0

    cursor = db_connection.cursor()
    try:
        cursor.execute(f"""
            INSERT INTO {DEVICE_METADATA_TABLE} (deviceid, partitionid, pathname, volumename, last_scanned, total_volume_size, remaining_free_space)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(deviceid) DO UPDATE SET
            partitionid=excluded.partitionid,
            pathname=excluded.pathname,
            volumename=excluded.volumename,
            last_scanned=excluded.last_scanned,
            total_volume_size=excluded.total_volume_size,
            remaining_free_space=excluded.remaining_free_space
        """, (os.stat(folder_name).st_dev, f"{partition_id} ({volume_name}, {serial_number})", folder_name, volume_name, last_scanned, total_volume_size, remaining_free_space))
        db_connection.commit()
    except sqlite3.Error as e:
        print(f"Failed to update device metadata: {e}")


def dump_all_device_metadata(db_connection):
    """
    Dumps all records from the device_metadata table.
    
    Args:
        db_connection (sqlite3.Connection): SQLite database connection.
    
    Returns:
        list: List of dictionaries containing all device metadata records.
    """
    cursor = db_connection.cursor()
    cursor.execute(f"SELECT * FROM {DEVICE_METADATA_TABLE}")
    rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

def dump_all_video_files(db_connection, device_id=None):
    """
    Dumps all records from the video_files table.
    
    Args:
        db_connection (sqlite3.Connection): SQLite database connection.
        device_id (int, optional): If provided, only returns video files from this device ID.
    
    Returns:
        list: List of dictionaries containing all video file records.
    """
    cursor = db_connection.cursor()
    if device_id is not None:
        cursor.execute(f"SELECT * FROM {VIDEO_FILES_TABLE} WHERE device_DUID = ? ORDER BY filesize", (device_id,))
    else:
        cursor.execute(f"SELECT * FROM {VIDEO_FILES_TABLE} ORDER BY filesize")
    rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def delete_video_files_by_device_id(device_id, db_connection):
    """
    Deletes all records from the video_files_metadata table for a given deviceID.
    
    Args:
        device_id (int): The deviceID for which records should be deleted.
        db_connection (sqlite3.Connection): SQLite database connection.
    """
    cursor = db_connection.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {VIDEO_FILES_TABLE} WHERE device_DUID = ?", (device_id,))
        count = cursor.fetchone()[0]
        if count == 0:
            print(f"No records found for deviceID {device_id}.")
            return
        
        cursor.execute(f"DELETE FROM {VIDEO_FILES_TABLE} WHERE device_DUID = ?", (device_id,))
        db_connection.commit()
        print(f"{count} video file record(s) for deviceID {device_id} have been deleted.")
    except sqlite3.Error as e:
        print(f"Failed to delete video file records for deviceID {device_id}: {e}")
   

def scan_folder_and_update_db(db_connection, folder_to_scan):
    """
    Scans a folder for video files and updates the database with the results.
    
    Args:
        db_connection (sqlite3.Connection): SQLite database connection.
        folder_to_scan (str): The folder path to scan for video files.
    """
    if not folder_to_scan:
        print("Folder path cannot be empty.")
        return
        
    # Remove quotes if present
    folder_to_scan = folder_to_scan.strip('"\'')
    
    # Convert to lowercase on Windows since case doesn't matter
    if os.name == 'nt':  # Windows
        folder_to_scan = folder_to_scan.lower() 
    
    try:
        video_files = get_video_files(folder_to_scan)
        if video_files:
            print(f"Found {len(video_files)} video file(s).")
            store_video_files_in_db(video_files, db_connection)
            update_device_metadata(folder_to_scan, db_connection)
            print("Database updated successfully.")
        else:
            print("No video files found in the specified folder.")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def commandline_user_interface():
    """
    Provides a command-line interface for interacting with the video file database.
    Allows users to scan folders, dump records, and manage the database through a menu-driven interface.
    """
    # Initialize the database
    try:
        db_connection = initialize_db()
    except sqlite3.Error as e:
        print(f"Failed to initialize database: {e}")
        return

    try:
        while True:
            print("\nChoose an option:")
            print("1. Scan a folder for video files and update in the database")
            print("2. Dump all video file records to a CSV file")
            print("3. Dump all device metadata from the database")
            print("4. Delete all records for a given deviceID")
            print("5. Exit the program")
            
            choice = input("Enter your choice (1/2/3/4/5): ").strip()
            
            if choice == "1":
                folder_to_scan = input("Enter the folder path to scan for video files: ").strip()
                scan_folder_and_update_db(db_connection, folder_to_scan)
            elif choice == "2":
                try:
                    # Dump all video files from the database and print them
                    all_video_files = dump_all_video_files(db_connection)
                    if all_video_files:
                        output_file = "output_videos_list.csv"
                        try:
                            with open(output_file, mode="w", newline="", encoding="utf-8") as csvfile:
                                writer = csv.DictWriter(csvfile, fieldnames=all_video_files[0].keys())
                                writer.writeheader()
                                writer.writerows(all_video_files)
                            print(f"{len(all_video_files)} file records written to '{output_file}'.")
                        except (IOError, PermissionError) as e:
                            print(f"Error writing to CSV file: {e}")
                    else:
                        print("No video files found in the database.")
                except sqlite3.Error as e:
                    print(f"Database error while dumping video files: {e}")
            elif choice == "3":
                try:
                    # Dump all device metadata from the database and print them
                    all_device_metadata = dump_all_device_metadata(db_connection)
                    if all_device_metadata:
                        for device in all_device_metadata:
                            # Create a copy of the device dict to modify
                            device_display = device.copy()
                            # Convert total_volume_size from bytes to GB if it exists
                            if device_display.get('total_volume_size'):
                                device_display['total_volume_size'] = f"{device_display['total_volume_size'] / (1024**3):.2f} GB"
                            # Convert remaining_free_space from bytes to GB if it exists
                            if device_display.get('remaining_free_space'):
                                device_display['remaining_free_space'] = f"{device_display['remaining_free_space'] / (1024**3):.2f} GB"
                            print(device_display)
                        print(f"Total records found: {len(all_device_metadata)}")
                    else:
                        print("No device metadata found in the database.")
                except sqlite3.Error as e:
                    print(f"Database error while dumping device metadata: {e}")
            elif choice == "4":
                # Delete all records for a given deviceID
                try:
                    device_id = int(input("Enter the deviceID to delete all records for: ").strip())
                    delete_video_files_by_device_id(device_id, db_connection)
                except ValueError:
                    print("Invalid deviceID. Please enter a valid integer.")
                except sqlite3.Error as e:
                    print(f"Database error while deleting records: {e}")
            elif choice == "5":
                print("Exiting the program.")
                break
            else:
                print("Invalid choice. Please enter 1, 2, 3, 4, or 5.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        try:
            # Ensure the database connection is closed
            db_connection.close()
        except Exception as e:
            print(f"Error closing database connection: {e}")

if __name__ == "__main__":
    # Add a simple command-line argument parser to choose between CLI and GUI
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        from gui_interface import graphical_user_interface
        graphical_user_interface()
    else:
        commandline_user_interface()


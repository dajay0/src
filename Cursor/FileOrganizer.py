import os
from datetime import datetime
import sqlite3
import win32api
import csv

# Global variables for database table names
VIDEO_FILES_TABLE = "app_video_files_metadata"
DEVICE_METADATA_TABLE = "app_device_metadata"

def get_video_files(folder_name):
    """
    Takes a folder name as input and returns a list of dictionaries containing details of all video files in the folder.
    Each dictionary includes: partitionID, full pathname, filename, filesize, created date, and modified date.
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
                stats = os.stat(full_path)
                video_files.append({
                    "partitionID": os.path.splitdrive(full_path)[0],
                    "full_pathname": full_path,
                    "filename": file,
                    "filesize": stats.st_size,
                    "created_date": datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    "modified_date": datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    "device_DUID": int(stats.st_dev)
                })

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
                INSERT INTO {VIDEO_FILES_TABLE} (partitionID, full_pathname, filename, filesize, created_date, modified_date, device_DUID)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                video["partitionID"],
                video["full_pathname"],
                video["filename"],
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
            total_volume_size INTEGER NOT NULL
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
    except Exception as e:
        print(f"Unable to retrieve volume information for --{partition_id}--. Using Unknown. Error: {e}")
        volume_name = "Unknown"
        serial_number = 0
        total_volume_size = 0

    cursor = db_connection.cursor()
    try:
        cursor.execute(f"""
            INSERT INTO {DEVICE_METADATA_TABLE} (deviceid, partitionid, pathname, volumename, last_scanned, total_volume_size)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(deviceid) DO UPDATE SET
            partitionid=excluded.partitionid,
            pathname=excluded.pathname,
            volumename=excluded.volumename,
            last_scanned=excluded.last_scanned,
            total_volume_size=excluded.total_volume_size
        """, (os.stat(folder_name).st_dev, f"{partition_id} ({volume_name}, {serial_number})", folder_name, volume_name, last_scanned, total_volume_size))
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

def dump_all_video_files(db_connection):
    """
    Dumps all records from the video_files table.
    
    Args:
        db_connection (sqlite3.Connection): SQLite database connection.
    
    Returns:
        list: List of dictionaries containing all video file records.
    """
    cursor = db_connection.cursor()
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
   

######################################################################################
# Main function to execute the script
#
#

# Initialize the database
db_connection = initialize_db()

video_files = []  # Initialize video_files to avoid referencing before assignment

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
        video_files = []  # Initialize video_files to avoid referencing before assignment
        try:
            video_files = get_video_files(folder_to_scan)
            if video_files:
                print(f"Found {len(video_files)} video file(s).")
            else:
                print("No video files found in the specified folder.")
            # Store video files in the database
            store_video_files_in_db(video_files, db_connection)
            # Update device metadata in the database
            update_device_metadata(folder_to_scan, db_connection)
        except ValueError as e:
            print(e)
    elif choice == "2":
        # Dump all video files from the database and print them
        all_video_files = dump_all_video_files(db_connection)
        if all_video_files:
            output_file = "output_videos_list.csv"
            with open(output_file, mode="w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=all_video_files[0].keys())
                writer.writeheader()
                writer.writerows(all_video_files)
            print(f"{len(all_video_files)} file records written to '{output_file}'.")
        else:
            print("No video files found in the database.")
    elif choice == "3":
        # Dump all device metadata from the database and print them
        all_device_metadata = dump_all_device_metadata(db_connection)
        if all_device_metadata:
            for device in all_device_metadata:
                print(device)
            print(f"Total records found: {len(all_device_metadata)}")
        else:
            print("No device metadata found in the database.")
    elif choice == "4":
        # Delete all records for a given deviceID
        try:
            device_id = int(input("Enter the deviceID to delete all records for: ").strip())
            delete_video_files_by_device_id(device_id, db_connection)
        except ValueError:
            print("Invalid deviceID. Please enter a valid integer.")
    elif choice == "5":
        print("Exiting the program.")
        break
    else:
        print("Invalid choice. Please enter 1, 2, 3, 4, or 5.")


print("File organization complete.")


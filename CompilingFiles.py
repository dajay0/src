# Suppose you have:
from FileOrganizer import get_video_files

files = get_video_files("C:/SomeFolder")
names = [f["normalized_filename"] for f in files]

clusters = cluster_by_levenshtein_dbscan(names, max_dist=2) # levenshtein + dbscan
for i, grp in enumerate(clusters, 1):
    print(f"Cluster {i}:")
    for name in grp:
        print("  ", name)


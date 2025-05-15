from sklearn.cluster import DBSCAN
from rapidfuzz.distance import Levenshtein
import numpy as np

def cluster_by_levenshtein_dbscan(filenames, max_dist=3):
    """
    Cluster filenames with DBSCAN using Levenshtein distance.
    - filenames: list of str
    - max_dist: maximum edit distance to consider as neighbors
    Returns: list of clusters (each a list of filenames)
    """
    n = len(filenames)
    # build condensed distance matrix
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(i+1, n):
            d = Levenshtein.distance(filenames[i], filenames[j])
            D[i, j] = D[j, i] = d
    # DBSCAN with precomputed distances
    db = DBSCAN(eps=max_dist, min_samples=1, metric='precomputed')
    labels = db.fit_predict(D)
    # collect clusters
    clusters = {}
    for label, name in zip(labels, filenames):
        clusters.setdefault(label, []).append(name)
    return list(clusters.values())

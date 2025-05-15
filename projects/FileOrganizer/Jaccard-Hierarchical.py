from sklearn.cluster import AgglomerativeClustering
from itertools import combinations

def jaccard(a, b):
    set_a = set(a[i:i+3] for i in range(len(a)-2))
    set_b = set(b[i:i+3] for i in range(len(b)-2))
    if not set_a or not set_b: return 1.0
    return 1 - len(set_a & set_b) / len(set_a | set_b)

def cluster_by_jaccard_agglomerative(filenames, threshold=0.4):
    """
    - filenames: list of str
    - threshold: max Jaccard distance to join clusters
    """
    n = len(filenames)
    # build condensed distance matrix
    D = [[jaccard(filenames[i], filenames[j]) for j in range(n)] for i in range(n)]
    model = AgglomerativeClustering(
        n_clusters=None,
        affinity='precomputed',
        linkage='average',
        distance_threshold=threshold
    )
    labels = model.fit_predict(D)
    clusters = {}
    for lbl, name in zip(labels, filenames):
        clusters.setdefault(lbl, []).append(name)
    return list(clusters.values())

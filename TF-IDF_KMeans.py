from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

def cluster_by_tfidf_kmeans(filenames, k=10):
    """
    Cluster filenames with KMeans on TF-IDF features.
    - filenames: list of str
    - k: number of clusters
    Returns: list of clusters (each a list of filenames)
    """
    # vectorize with char- and word-level n-grams
    vec = TfidfVectorizer(analyzer='char', ngram_range=(2,5))
    X = vec.fit_transform(filenames)
    km = KMeans(n_clusters=k, random_state=42)
    labels = km.fit_predict(X)
    clusters = {}
    for lbl, name in zip(labels, filenames):
        clusters.setdefault(lbl, []).append(name)
    return list(clusters.values())

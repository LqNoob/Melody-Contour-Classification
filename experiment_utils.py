""" Helper functions for experiments """

from contour_classification.ShuffleLabelsOut import ShuffleLabelsOut
import contour_classification.contour_utils as cc
import json
from sklearn import metrics
import numpy as np
import os
import sys
import matplotlib.pyplot as plt
import seaborn as sns
sns.set()


def create_splits(test_size=0.15):
    """ Split MedleyDB into train/test splits.

    Returns
    -------
    mdb_files : list
        List of sorted medleydb files.
    splitter : iterator
        iterator of train/test indices.
    """
    index = json.load(open('medley_artist_index.json'))

    mdb_files = []
    keys = []

    for k, v in sorted(index.items()):
        mdb_files.append(k)
        keys.append(v)

    keys = np.asarray(keys)
    mdb_files = np.asarray(mdb_files)
    splitter = ShuffleLabelsOut(keys, random_state=1, test_size=test_size)

    return mdb_files, splitter


def get_data_files(track, meltype=1):
    """ Load all necessary data for a given track and melody type.

    Parameters
    ----------
    track : str
        Track identifier.
    meltype : int
        Melody annotation type. One of [1, 2, 3]

    Returns
    -------
    cdat : DataFrame
        Pandas DataFrame of contour data.
    adat : DataFrame
        Pandas DataFrame of annotation data.
    """
    contour_suffix = \
        "MIX_vamp_melodia-contours_melodia-contours_contoursall.csv"
    contours_path = "melodia_contours"
    annot_suffix = "MELODY%s.csv" % str(meltype)
    mel_dir = "MELODY%s" % str(meltype)
    annot_path = os.path.join(os.environ['MEDLEYDB_PATH'], 'Annotations',
                              'Melody_Annotations', mel_dir)

    contour_fname = "%s_%s" % (track, contour_suffix)
    contour_fpath = os.path.join(contours_path, contour_fname)
    annot_fname = "%s_%s" % (track, annot_suffix)
    annot_fpath = os.path.join(annot_path, annot_fname)

    cdat = cc.load_contour_data(contour_fpath, normalize=True)
    adat = cc.load_annotation(annot_fpath)

    return cdat, adat


def compute_all_overlaps(train_tracks, valid_tracks, test_tracks, meltype):
    """ Compute each contour's overlap with annotation.

    Parameters
    ----------
    train_tracks : list
        List of trackids in training set
    valid_tracks : list
        List of trackids in validation set
    test_tracks : list
        List of trackids in test set
    meltype : int
        One of [1,2,3]

    Returns
    -------
    train_contour_dict : dict of DataFrames
        Dict of train dataframes keyed by trackid
    valid_contour_dict : dict of DataFrames
        Dict of validation dataframes keyed by trackid
    test_contour_dict : dict of DataFrames
        Dict of test dataframes keyed by trackid
    """

    train_contour_dict = {}

    msg = "Generating training features..."
    train_len = len(train_tracks)
    num_spaces = train_len - len(msg)
    print msg + ' '*num_spaces + '|'

    for track in train_tracks:
        cdat, adat = get_data_files(track, meltype=meltype)
        train_contour_dict[track] = cc.compute_overlap(cdat, adat)
        sys.stdout.write('.')

    print ""
    print "-"*30

    valid_contour_dict = {}
    valid_annot_dict = {}

    msg = "Generating validation features..."
    valid_len = len(valid_tracks)
    num_spaces = valid_len - len(msg)
    print msg + ' '*num_spaces + '|'

    for track in valid_tracks:
        cdat, adat = get_data_files(track, meltype=meltype)
        valid_annot_dict[track] = adat.copy()
        valid_contour_dict[track] = cc.compute_overlap(cdat, adat)
        sys.stdout.write('.')

    print ""
    print "-"*30

    test_contour_dict = {}
    test_annot_dict = {}

    msg = "Generating testing features..."
    test_len = len(test_tracks)
    num_spaces = test_len - len(msg)
    print msg + ' '*num_spaces + '|'

    for track in test_tracks:
        cdat, adat = get_data_files(track, meltype=meltype)
        test_annot_dict[track] = adat.copy()
        test_contour_dict[track] = cc.compute_overlap(cdat, adat)
        sys.stdout.write('.')

    return train_contour_dict, valid_contour_dict, valid_annot_dict, \
           test_contour_dict, test_annot_dict


def olap_stats(train_contour_dict):
    """ Compute overlap statistics.

    Parameters
    ----------
    train_contour_dict : dict of DataFrames
        Dict of train contour data frames

    Returns
    -------
    partial_olap_stats : DataFrames
        Description of overlap data.
    zero_olap_stats : DataFrames
        Description of non-overlap data.
    """
    # reduce for speed and memory
    red_list = []
    for cdat in train_contour_dict.values():
        red_list.append(cdat['overlap'])

    overlap_dat = cc.join_contours(red_list)
    non_zero_olap = overlap_dat[overlap_dat > 0]
    zero_olap = overlap_dat[overlap_dat == 0]
    partial_olap_stats = non_zero_olap.describe()
    zero_olap_stats = zero_olap.describe()

    return partial_olap_stats, zero_olap_stats


def label_all_contours(train_contour_dict, valid_contour_dict,
                       test_contour_dict, olap_thresh):
    """ Add labels to contours based on overlap_thresh.

    Parameters
    ----------
    train_contour_dict : dict of DataFrames
        dict of train contour data frames
    valid_contour_dict : dict of DataFrames
        dict of validation contour data frames
    test_contour_dict : dict of DataFrames
        dict of test contour data frames
    olap_thresh : float
        Value in [0, 1). Min overlap to be labeled as melody.

    Returns
    -------
    train_contour_dict : dict of DataFrames
        dict of train contour data frames
    test_contour_dict : dict of DataFrames
        dict of test contour data frames
    """
    for key in train_contour_dict.keys():
        train_contour_dict[key] = cc.label_contours(train_contour_dict[key],
                                                    olap_thresh=olap_thresh)

    for key in valid_contour_dict.keys():
        valid_contour_dict[key] = cc.label_contours(valid_contour_dict[key],
                                                    olap_thresh=olap_thresh)

    for key in test_contour_dict.keys():
        test_contour_dict[key] = cc.label_contours(test_contour_dict[key],
                                                   olap_thresh=olap_thresh)
    return train_contour_dict, valid_contour_dict, test_contour_dict


def contour_probs(clf, contour_data):
    """ Compute classifier probabilities for contours.

    Parameters
    ----------
    clf : scikit-learn classifier
        Binary classifier.
    contour_data : DataFrame
        DataFrame with contour information.

    Returns
    -------
    contour_data : DataFrame
        DataFrame with contour information and predicted probabilities.
    """
    contour_data['mel prob'] = -1
    X, _ = cc.pd_to_sklearn(contour_data)
    probs = clf.predict_proba(X)
    mel_probs = [p[1] for p in probs]
    contour_data['mel prob'] = mel_probs
    return contour_data


def get_best_threshold(Y_ref, Y_pred_score, plot=True):
    fpr, tpr, thresholds = \
            metrics.roc_curve(Y_ref, Y_pred_score, pos_label=1)

    P = 1 - fpr
    R = tpr

    f_scores = 2*(P*R)/(P+R)

    max_fscore = f_scores[np.argmax(f_scores)]
    best_threshold =  thresholds[np.argmax(f_scores)]

    if plot:
        plt.plot(fpr, tpr, 'b', label='ROC curve')
        plt.plot([0, 1], [0, 1], 'k--')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.0])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Melodiness Receiver operating characteristic')
        plt.legend(loc="lower right")
        plt.show()

    return best_threshold, max_fscore

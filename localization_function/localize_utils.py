########################################################################
# File: localize_utils.py                                              #
# Created Date: Sat Nov 27 2021                                        #
# Author: Isaac Perper                                                 #
# Contact: isaac.perper@gmail.com                                      #
# -----                                                                #
# Last Modified: Wed Jan 19 2022                                       #
# Modified By: iperper                                                 #
# -----                                                                #
# Copyright (c) 2021 Isaac Perper                                      #
########################################################################

import sys
import pathlib
import pickle
import json

import numpy as np
import scipy.constants
import scipy.spatial.transform

from backtrack.localization import multi_fusion as mf

def preprocess_queue(data_queue):
    """
    Process each measurement in the queue
    """
    return [preprocess_data(data) for data in data_queue]

def preprocess_data(data):
    """
    Convert stored SQL data into arrays
    """
    out_data = {}
    for key, val in data.items():
        if key == "distance_candidates":
            fmt_val= np.array(json.loads(val))
        elif key == "channel_estimate":
            fmt_val = pickle.loads(val)
        else:
            fmt_val = val
        out_data[key] = fmt_val
    return out_data

def localize(clusters, tx_poses, rx_poses, bound_min, bound_max):
    """
    Localize a set of clusters and poses.  The poses are the TX antenna
    location, and tx_rx_offset should represent the offset from TX ant
    to the RX ant in the TX ant frame.

    TX ant frame is x right, z back, y up, the same as the T265 camera
    """

    multi_fusion = mf.MultiFusion(bound_min=bound_min, bound_max=bound_max)
    for (cluster, tx_pose, rx_pose) in zip(clusters, tx_poses, rx_poses):
        multi_fusion.process_new_measurement(cluster, rx_pose[:3], tx_pose[:3])
    locations = multi_fusion.get_all_locations()
    # print(f"Returning all locations: {len(locations)}")

    return locations

def antenna_array_channels(calibrated_channels, cal_dist, wavelengths):
    """
    Convert calibrated channel estimates to antenna array channels

    This is done by adding back the distance, so calibration of HW
    still done, but full phase change of path included.
    """

    cal_phases = cal_dist * 2 * np.pi / wavelengths
    # Note that cal_phases is (n_hops, ) and
    # calibrated_channels = (n_tags, 1, n_hops).  Multiplying this way
    # properly applies the phase across the hops on the channels
    return calibrated_channels * np.exp(-1j*cal_phases)

def self_localize_queue(data_queue, ref_locs, config):
    processed_data = preprocess_queue(data_queue)

    n_shuffle = config["shuffle"]
    min_bounds = np.array(config["min_bounds"])
    max_bounds = np.array(config["max_bounds"])
    tx_rx_offset = np.array(config["tx_rx_offset"])

    freqs = np.array([770e6 + 27e6*i for i in range(14)])
    wavelengths = scipy.constants.c/freqs
    n_tags = len(data_queue)

    clusters = []
    tag_locs = []
    channels = []
    for i in range(len(processed_data)):
        clusters.append(processed_data[i]["distance_candidates"])
        tag_locs.append(ref_locs[processed_data[i]["epc"]])
        channels.append(processed_data[i]["channel_estimate"][0])
    clusters = np.array(clusters)
    tag_locs = np.array(tag_locs)
    channels = np.array(channels)
    arr_channels = antenna_array_channels(
        channels, config["cal_dist"], wavelengths)


    # --------------- Multi fusion possible locations ---------------- #
    possible_locs = []
    for i in range(n_shuffle):
        shuffler = np.random.permutation(n_tags)
        shuffled_locs = tag_locs[shuffler]
        shuffled_clusters = clusters[shuffler]
        # BUG fix tx_rx_offset order with new localize function
        loc_guesses = localize(shuffled_clusters,
                               shuffled_locs,
                               tx_rx_offset,
                               min_bounds,
                               max_bounds)
        if loc_guesses:
            possible_locs += [guess["location"] for guess in loc_guesses]
    # TODO (Isaac) investigate no results from multifusion

    # ----------------------- AoA Tiebreaker ------------------------- #
    # print("Multi Done")
    # print(np.mean(np.array(possible_locs),axis=0))
    # print(len(possible_locs))
    
    # TODO (Isaac) put into function
    # print("Starting Tiebreaker")
    best_power = None
    best_loc = None
    n_freqs = len(wavelengths)
    for loc in possible_locs:
        power = 0
        for i in range(n_tags):
            dist = (np.linalg.norm(loc - tag_locs[i])
                    + np.linalg.norm(loc - tag_locs[i] - tx_rx_offset))
            for j in range(n_freqs):
                power += (arr_channels[i, j]
                            * np.exp(1j * 2 * np.pi * dist / wavelengths[j]))
        power = np.abs(power)
        if best_power is None or power > best_power:
            best_power = power
            best_loc = loc
    # print("Ended tiebreaker")
    # print(best_loc)
    # print()
    return best_loc

def target_localize_queue(data_queue, self_loc_poses, config):
    """
    Computes target tag locations based on measurement data and self-
    localization positions.

    data_queue: [
        {distance_cancidates: [cluster1], channel_estimate: [ch_est1]},
        {distance_cancidates: [cluster2], channel_estimate: [ch_est2]},
    ]
    self_loc_poses: [
        [x1,y1,z1,qx1,qy1,qz1,qw1],
        [x2,y2,z2,qx2,qy2,qz2,qw2]
    ]
    config: {
        shuffle: # of shuffles
        min_bounds: [min_x, min_y, min_z]
        max_bounds: [max_x, max_y, max_z]
        tx_rx_offset: [x,y,z] shift from TX antenna to RX antenna in TX
            frame
        cal_dist: calibration_distance
    }
    """

    # Load data from queue into proper format.  This can be removed if
    # the data is already in the right format
    processed_data = preprocess_queue(data_queue)

    n_shuffle = config["shuffle"]
    min_bounds = np.array(config["min_bounds"])
    max_bounds = np.array(config["max_bounds"])
    tx_rx_offset = np.array(config["tx_rx_offset"])

    freqs = np.array([770e6 + 27e6*i for i in range(14)])
    wavelengths = scipy.constants.c/freqs
    n_tags = len(data_queue)

    clusters = []
    channels = []
    for data in processed_data:
        clusters.append(data["distance_candidates"][0])
        channels.append(data["channel_estimate"][0])
    clusters = np.array(clusters)
    channels = np.array(channels)
    tx_self_loc_poses = np.array(self_loc_poses)

    # Calculate the RX antenna poses based on the TX antenna poses
    # and the TX RX offset
    rx_self_loc_poses = []
    for tx_pose in tx_self_loc_poses:
        tx_loc = tx_pose[:3]
        # This is just a cleaner way of doing pose math. This can be 
        # written with standard vector / matrix math
        rot = scipy.spatial.transform.Rotation.from_quat(tx_pose[3:])
        rx_self_loc_poses.append(rot.apply(tx_rx_offset) + tx_loc)
    rx_self_loc_poses = np.array(rx_self_loc_poses)

    arr_channels = antenna_array_channels(
        channels, config["cal_dist"], wavelengths)

    # --------------- Multi fusion possible locations ---------------- #
    possible_locs = []
    residuals = []
    for i in range(n_shuffle):
        # Run the algorithm in different orders because currently the
        # order is an issue (BUG)
        shuffler = np.random.permutation(n_tags)
        tx_shuffled_poses = tx_self_loc_poses[shuffler]
        rx_shuffled_poses = rx_self_loc_poses[shuffler]
        shuffled_clusters = clusters[shuffler]

        # To reuse the localize function, since offset get's added 
        # to the tx locs. # TODO (Isaac) fix this, since confusing
        # shuffled_locs = shuffled_locs - tx_rx_offset

        loc_guesses = localize(shuffled_clusters,
                               tx_shuffled_poses,
                               rx_shuffled_poses,
                               min_bounds,
                               max_bounds)
        if loc_guesses:
            # print(len(loc_guesses))
            # print([guess["location"] for guess in loc_guesses])
            # print([guess["residual_cost"] for guess in loc_guesses])
            residuals += [guess["residual_cost"] for guess in loc_guesses]
            possible_locs += [guess["location"] for guess in loc_guesses]
    # TODO (Isaac) investigate no results from multifusion

    possible_locs = np.array(possible_locs)
    # gt = np.array([ 0.,    -0.677, -0.165])
    # err = np.linalg.norm(possible_locs - gt, axis=-1)
    # min_err_idx = np.argmin(err)
    # best_res_loc = np.array(possible_locs)[np.argsort(residuals)[-3:]]
    # best_res = np.sort(residuals)[-3:]
    # print(len(possible_locs))
    # print(f"Min Err: {possible_locs[min_err_idx]}, Min Res: {residuals[min_err_idx]} Best Res: {min(residuals)}")
    # print("\tBest Residual Locs: ", best_res_loc, " Res: ", best_res)

    # ----------------------- AoA Tiebreaker ------------------------- #
    # print("Multi Done")
    # print(np.mean(np.array(possible_locs),axis=0))
    # print(len(possible_locs))
    
    # TODO (Isaac) put into function
    # print("Starting Tiebreaker")
    best_power = None
    best_loc = None
    n_freqs = len(wavelengths)
    for t, loc in enumerate(possible_locs):
        power = 0
        for i in range(n_tags):
            dist = (np.linalg.norm(loc - tx_self_loc_poses[i][:3])
                    + np.linalg.norm(loc - rx_self_loc_poses[i][:3]))
            # TODO (Isaac) tx_rx_offset should apply to which? Same as self loc
            # in this case, which is opposite of in the localize() call
            # FIXED: changed from - to + (since - is sort of in parentheses)
            # and this fixed issue.  However, should still fix naming 
            # convention and clean up the code.
            for j in range(n_freqs):
                power += (arr_channels[i, j]
                            * np.exp(1j * 2 * np.pi * dist / wavelengths[j]))
        power = np.abs(power)
        # if t == min_err_idx:
        #     print(f"Min Power: {power}")
        # if best_power is not None and power < best_power and np.abs(best_power - power) < 0.01*np.abs(best_power):
        #     print(f"Close: {power} {best_power} {loc}")
        if best_power is None or power > best_power:
            best_power = power
            best_loc = loc
    # print("Best Power: ", best_power)
    # print("Ended tiebreaker")
    # print(best_loc)
    # print()
    return best_loc
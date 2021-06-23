#!/usr/bin/env python3
# Copyright lowRISC contributors.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Test Vector Leakage Assessment



Typical usage:

To run the analysis without loading or saving the histograms:
>>> ./tvla.py

To save histograms in the OUTPUT_FILE for later use:
>>> ./tvla.py -o OUTPUT_FILE

To load histograms from the INPUT_FILE
>>> ./tvla.py -i INPUT_FILE

"""

import argparse
import chipwhisperer as cw
from chipwhisperer.analyzer import aes_funcs
from math import sqrt
import matplotlib.pyplot as plt
import numpy as np


def bit_count(int_no):
    """Computes Hamming weight of a number."""
    c = 0
    while int_no:
        int_no &= int_no - 1
        c += 1
    return c


# A set of functions for working with histograms.
# Each distribution should be stored as two vectors x and y.
# x - A vector of  values.
# y - A vector of probabilities.


def mean_hist_xy(x, y):
    """Computes mean value of a distribution."""
    return np.dot(x, y) / sum(y)


def var_hist_xy(x, y):
    """Computes variance of a distribution."""
    mu = mean_hist_xy(x, y)
    new_x = (x - mu)**2
    return mean_hist_xy(new_x, y)


def ttest1_hist_xy(x_a, y_a, x_b, y_b):
    """
    Basic first-order t-test.
    """
    mu1 = mean_hist_xy(x_a, y_a)
    mu2 = mean_hist_xy(x_b, y_b)
    var1 = var_hist_xy(x_a, y_a)
    var2 = var_hist_xy(x_b, y_b)
    N1 = sum(y_a)
    N2 = sum(y_b)
    num = sqrt(var1 / N1 + var2 / N2)
    diff_flag = 0 if (mu1 == mu2) else 100
    return (mu1 - mu2) / num if num > 0 else diff_flag


def ttest_hist_xy(x_a, y_a, x_b, y_b, order):
    """ General t-test of any order.

    For more details see: Reparaz et. al. "Fast Leakage Assessment", CHES 2017.
    available at: https://eprint.iacr.org/2017/624.pdf
    """
    mu_a = mean_hist_xy(x_a, y_a)
    mu_b = mean_hist_xy(x_b, y_b)
    var_a = var_hist_xy(x_a, y_a)
    var_b = var_hist_xy(x_b, y_b)
    sigma_a = sqrt(var_a)
    sigma_b = sqrt(var_b)

    if order == 1:
        new_x_a = x_a
        new_x_b = x_b
    elif order == 2:
        new_x_a = (x_a - mu_a)**2
        new_x_b = (x_b - mu_b)**2
    else:
        if sigma_a == 0:
            new_x_a = 0
        else:
            new_x_a = (((x_a - mu_a) / sigma_a)**order)
        if sigma_b == 0:
            new_x_b = 0
        else:
            new_x_b = (((x_b - mu_b) / sigma_b)**order)

    return ttest1_hist_xy(new_x_a, y_a, new_x_b, y_b)


def compute_leakage_aes(keylist, plaintext, leakage_model):
    """
    Sensitive variable is always byte-sized.

    Two leakage models are available:
    HAMMING_WEIGHT - based on the hamming weight of the state register byte.
    HAMMING_DISTANCE - based on the hamming distance between the curent and previous state
                       for a specified byte.
    """
    n_traces = len(keylist)
    leakage = np.zeros((11, 16, n_traces), dtype=np.uint8)

    # Checks if all keys in the list are the same.
    key_fixed = np.all(keylist == keylist[0])
    subkey = np.zeros((11, 16))

    if key_fixed:
        for j in range(11):
            subkey[j] = np.asarray(
                aes_funcs.key_schedule_rounds(keylist[0], 0, j))
        subkey = subkey.astype(int)

    for i in range(n_traces):

        if not key_fixed:
            for j in range(11):
                subkey[j] = np.asarray(
                    aes_funcs.key_schedule_rounds(keylist[i], 0, j))
            subkey = subkey.astype(int)

        # Init
        state = plaintext[i]

        # Round 0
        old_state = state
        state = np.bitwise_xor(state, subkey[0])
        for k in range(16):
            if leakage_model == 'HAMMING_DISTANCE':
                leakage[0][k][i] = bit_count(
                    np.bitwise_xor(state[k], old_state[k]))
            else:
                leakage[0][k][i] = bit_count(state[k])

        # Round 1 - 10
        for j in range(1, 11):
            old_state = state
            state = aes_funcs.subbytes(state)
            state = aes_funcs.shiftrows(state)
            if (j < 10):
                state = aes_funcs.mixcolumns(state)
            state = np.bitwise_xor(state, subkey[j])
            for k in range(16):
                if leakage_model == 'HAMMING_DISTANCE':
                    leakage[j][k][i] = bit_count(
                        np.bitwise_xor(state[k], old_state[k]))
                else:
                    leakage[j][k][i] = bit_count(state[k])

    return leakage


def parse_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description=
        """A histogram-based TVLA described in "Fast Leakage Assessment"
        by O. Reparaz, B. Gierlichs and I. Verbauwhede (https://eprint.iacr.org/2017/624.pdf)."""
    )

    parser.add_argument(
        "-l",
        "--leakage-file",
        help="""Name of the leakage file containing the numpy array with the leakage model for all
        rounds, all bytes, and all traces. Not required. If not provided, the leakage is computed
        from the data in the ChipWhisperer project file.""",
    )
    parser.add_argument(
        "-i",
        "--input-file",
        help=
        """Name of the input file containing the histograms. Not Required.""",
    )
    parser.add_argument(
        "-o",
        "--output-file",
        help=
        """Name of the output file to store generated histograms. Not Required.""",
    )
    return parser.parse_args()


def main():

    args = parse_args()

    if args.input_file is None:
        # relative path to project, modify accordingly
        project_file = "projects/opentitan_simple_aes.cwp"
        project = cw.open_project(project_file)
        """The default num_traces is set as the total number of traces in a project.
         For quick checks and debugs set it to something smaller (e.g. 50000)
         To use only some traces from the project set trace_start to the number of the
         first trace you want to extract.
        """
        num_traces = len(project.waves)
        # num_traces = 50000
        trace_start = 0
        trace_end = trace_start + num_traces

        num_samples = len(project.waves[0])

        # Converting traces from floating point to integer.
        adc_bits = 10
        trace_resolution = 2**adc_bits
        traces = np.empty((num_traces, num_samples), np.double)
        for i_trace in range(num_traces):
            traces[i_trace] = project.waves[i_trace +
                                            trace_start] * trace_resolution
        offset = traces.min().astype('uint16')
        traces = traces.astype('uint16') - offset

        # The round and byte number of the sensitive variable.
        # If differential model is used, the sensitive variable is the xor of n_round state and the
        # previous round state.
        n_round = 10
        n_byte = 1

        if args.leakage_file is None:
            # leakage models: HAMMING_WEIGHT (default), HAMMING_DISTANCE
            print("Computing Leakage")
            leakage = compute_leakage_aes(project.keys[trace_start:trace_end],
                                          project.textins[trace_start:trace_end],
                                          'HAMMING_WEIGHT')
            np.save('leakage.npy', leakage)
        else:
            leakage = np.load(args.leakage_file)
            assert num_traces == leakage.shape[2]

        # Building histograms. For each time sample we make nine histograms, one for each possible
        # Hamming weight of the sensitive variable.
        # Value stored in histograms[x][y][z] shows how many traces have value z at time y, given
        # that HW(sensitive_variable) = x.
        print("Building Histograms")
        histograms = np.zeros((9, num_samples, trace_resolution))
        for trace_index in range(num_traces):
            x = leakage[n_round][n_byte][trace_index]
            for time_index in range(num_samples):
                y = time_index
                z = traces[trace_index][time_index]
                histograms[x][y][z] += 1

        # Histograms can be saved for later use if output file name is passed.
        if args.output_file is not None:
            print("Saving Histograms")
            with open(args.output_file, 'wb') as f:
                np.save(f, histograms)
    else:
        histograms = np.load(args.input_file)
        num_samples = histograms.shape[1]
        trace_resolution = histograms.shape[2]

    # Computing the ttest statistics vs time.
    # By default, the first four moments are computed. This can be modified to any order.
    print("Computing t_test statistics")
    ttest1_trace = np.zeros(num_samples)
    ttest2_trace = np.zeros(num_samples)
    ttest3_trace = np.zeros(num_samples)
    ttest4_trace = np.zeros(num_samples)

    for i in range(num_samples):
        fixed_set = histograms[0][i][:]
        S = sum(histograms)
        random_set = S[i][:]

        x_axis = range(trace_resolution)
        ttest1_trace[i] = ttest_hist_xy(x_axis, fixed_set, x_axis, random_set,
                                        1)
        ttest2_trace[i] = ttest_hist_xy(x_axis, fixed_set, x_axis, random_set,
                                        2)
        ttest3_trace[i] = ttest_hist_xy(x_axis, fixed_set, x_axis, random_set,
                                        3)
        ttest4_trace[i] = ttest_hist_xy(x_axis, fixed_set, x_axis, random_set,
                                        4)

    # Plotting figures for t_test statistics vs time.
    # By default the figure is saved as MyFigure.png.
    c = np.ones(num_samples)
    fig, axs = plt.subplots(1, 4, figsize=(16, 5), sharey=True)
    threshold = 4.5

    axs[0].plot(ttest1_trace, 'k')
    axs[0].plot(c * threshold, 'r')
    axs[0].plot(-threshold * c, 'r')
    axs[0].set_xlabel('time')
    axs[0].set_ylabel('t-test 1')

    axs[1].plot(ttest2_trace, 'k')
    axs[1].plot(c * threshold, 'r')
    axs[1].plot(-threshold * c, 'r')
    axs[1].set_xlabel('time')
    axs[1].set_ylabel('t-test 2')

    axs[2].plot(ttest3_trace, 'k')
    axs[2].plot(c * threshold, 'r')
    axs[2].plot(-threshold * c, 'r')
    axs[2].set_xlabel('time')
    axs[2].set_ylabel('t-test 3')

    axs[3].plot(ttest4_trace, 'k')
    axs[3].plot(c * threshold, 'r')
    axs[3].plot(-threshold * c, 'r')
    axs[3].set_xlabel('time')
    axs[3].set_ylabel('t-test 4')

    plt.savefig('MyFigure.png')
    plt.show()


if __name__ == "__main__":
    main()
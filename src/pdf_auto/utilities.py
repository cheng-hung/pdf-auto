import os

import numpy as np
import pandas as pd
from scipy import integrate
from scipy.optimize import minimize


class ServerState:
    def __init__(self):
        self.color_str = ""
        self.do_process = False


def azim_to_q(theta, wavelength):
    return (4 * np.pi / wavelength) * np.sin(theta / 2)


def q_to_azim(q, wavelength):
    ## q: the input unit is A-1
    ## wavelength: the input unit is m
    t1 = q / (4 * np.pi / (wavelength * 10**10))
    return 2 * np.arcsin(t1)


def circle_coords(center=(0.0, 0.0), radius=1.0, total_points=1000):
    theta = np.linspace(
        0, 2 * np.pi, total_points
    )  # total_points from 0 to 2*pi radians
    center_x = center[0]
    center_y = center[1]
    x_coords = center_x + radius * np.cos(theta)
    y_coords = center_y + radius * np.sin(theta)
    # x = np.arange(0, radius, radius/r_divider)
    # y = np.sqrt(radius**2 - x**2)

    return np.asarray([x_coords, y_coords])


def find_nearest(array, value):
    """find the nearest value in a given array

    Args:
        array (array_like): input array
        value (float): target value

    Returns:
        int: index of the nearest value in the array
        float: the nearest value in the array
    """
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx, array[idx]


def data_to_numpy(data, sep=" "):
    """return data as np.ndarray where data.shape[0] == 2

    Args:
        data (ndarray, pd.Dataframe, list, fn_path): data source


    Returns:
        np.ndarray: if data can be transformed into an array where array.shape[0] == 2
        None      : if data cannot be transformed into an array
    """

    if (type(data) is np.ndarray) and (data.shape[0] == 2):
        pass

    elif type(data) is pd.core.frame.DataFrame:
        x = data.iloc[:, 0].to_numpy()
        y = data.iloc[:, 1].to_numpy()
        data = np.asarray([x, y])

    elif (type(data) is str) and (os.path.exists(data)):
        r = get_header_rows(data, sep=sep)
        df = pd.read_csv(data, sep=sep, names=["x", "y"], skiprows=r)
        x = df.iloc[:, 0].to_numpy()
        y = df.iloc[:, 1].to_numpy()
        data = np.asarray([x, y])

    elif (type(data) is list) and (len(data) == 2):
        data = np.asarray(data)

    else:
        data = None

    return data


# https://github.com/NSLS2/fxi-profile-collection/blob/main/startup/90-image_util.py
def bin_ndarray(ndarray, new_shape=None, operation="mean"):
    """
    Bins an ndarray in all axes based on the target shape, by summing or
        averaging.

    Number of output dimensions must match number of input dimensions and
        new axes must divide old ones.

    Example
    -------
    >>> m = np.arange(0,100,1).reshape((10,10))
    >>> n = bin_ndarray(m, new_shape=(5,5), operation='sum')
    >>> print(n)

    [[ 22  30  38  46  54]
     [102 110 118 126 134]
     [182 190 198 206 214]
     [262 270 278 286 294]
     [342 350 358 366 374]]

    """
    if new_shape is None:
        s = np.array(ndarray.shape)
        s1 = np.int32(s / 2)
        new_shape = tuple(s1)
    operation = operation.lower()
    if operation not in ["sum", "mean"]:
        raise ValueError("Operation not supported.")
    if ndarray.ndim != len(new_shape):
        raise ValueError(f"Shape mismatch: {ndarray.shape} -> {new_shape}")
    compression_pairs = [
        (d, c // d) for d, c in zip(new_shape, ndarray.shape, strict=True)
    ]
    flattened = [item for pair in compression_pairs for item in pair]
    ndarray = ndarray.reshape(flattened)
    for i in range(len(new_shape)):
        op = getattr(ndarray, operation)
        ndarray = op(-1 * (i + 1))
    return ndarray


def random_color(previous_color=None):

    color_list = [
        "tab:blue",
        "tab:orange",
        "tab:green",
        "tab:red",
        "tab:purple",
        "tab:brown",
        "tab:pink",
        "tab:gray",
        "tab:olive",
        "tab:cyan",
    ]

    random_int = np.random.randint(len(color_list))
    new_color = color_list[random_int]

    is_str = type(previous_color) is str
    in_color_list = previous_color in color_list

    if is_str and in_color_list:
        while new_color == previous_color:
            random_int = np.random.randint(len(color_list))
            new_color = color_list[random_int]
        return new_color

    return new_color


def get_header_rows(fn, sep=" ", num_data_column=2, check_range=100, check_float=True):

    cont_01 = []
    with open(fn) as f:
        cont = f.readlines()
        f.close()

    for line in cont:
        new_line = line.strip("\n").split(sep)
        cont_01.append(new_line)

    i = 0
    while i < len(cont_01):
        c0 = len(cont_01[i]) == num_data_column
        c1 = all(len(row) == num_data_column for row in cont_01[i : i + check_range])
        c2 = is_float(cont_01[i][0]) and is_float(cont_01[i][1])

        if check_float:
            if c0 and c1 and c2:
                # print(f'Num of rows of header is {i}.')
                break
        else:
            if c0 and c1:
                # print(f'Num of rows of header is {i}.')
                break

        i += 1

    return i


def is_float(s):
    """
    Checks if a string can be successfully converted to a float.

    Args:
    s: The string to check.

    Returns:
    True if the string can be converted to a float, False otherwise.
    """
    try:
        float(s)
        return True
    except ValueError:
        return False


class AutoBackground:
    def __init__(self):
        self.data_fn = None
        self.bkg_fn = None
        self.bkg_scale = 1.0
        self.data_df = None
        self.bkg_df = None
        self.bkg_opt = None
        self.min_res = None

    def pdload_data(self, data_fn, **kwargs):
        self.data_fn = data_fn
        data_df = pd.read_csv(data_fn, **kwargs)
        self.data_df = data_df
        return data_df

    def pdload_bkg(self, bkg_fn, **kwargs):
        self.bkg_fn = bkg_fn
        bkg_df = pd.read_csv(bkg_fn, **kwargs)
        self.bkg_df = bkg_df
        return bkg_df

    def data_sub(self, scale):
        return self.data_df.iloc[:, 1] - scale * self.bkg_df.iloc[:, 1]

    def data_sub2(self, scale):
        return (
            self.data_df.iloc[:, 1][:3000]
            - scale * self.bkg_df.iloc[:, 1][:3000]
            - 0.01
        )

    def guess_01(self, update_scale=True):
        bkg_max_val = self.bkg_df.iloc[:, 1].max()
        bkg_max_idx = self.bkg_df.iloc[:, 1].idxmax()

        data_cor_val = self.data_df.iloc[bkg_max_idx, 1]
        scale_01 = data_cor_val / bkg_max_val

        if update_scale:
            self.bkg_scale = scale_01

        return scale_01

    def integral_sub(self, scale):
        # return integrate.simpson(self.data_sub(scale))
        return integrate.simpson(self.data_sub2(scale))

    def min_integral(self):
        # Define a constraint where 0 <= x[0] + x[1] <= 1
        # nlc = NonlinearConstraint(self.data_sub, 0, 50)

        nlc = [
            {"type": "ineq", "fun": self.data_sub2}  # 1 - x0^2 - x1 >= 0
        ]

        a0 = self.guess_01()

        result = minimize(
            self.integral_sub,
            [a0],
            method="COBYLA",
            constraints=nlc,
            tol=1e-7,
            # options={'verbose': 3,
            #          'barrier_tol':1e-5,
            #          'maxiter': 1000, }
        )

        self.min_res = result

        if result.success:
            print("Found the bkg scale to minimize the integral")
            self.bkg_opt = result.x

        else:
            print("Unable to Found the bkg scale")

        return result

    def plot_sub(self):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)

        ax[0].plot(self.data_df.iloc[:, 0], self.data_df.iloc[:, 1], label="data")

        try:
            ax[0].plot(
                self.bkg_df.iloc[:, 0],
                self.bkg_df.iloc[:, 1] * self.bkg_opt,
                "g.",
                label="scaled_bkg",
            )
            ax[1].plot(
                self.data_df.iloc[:, 0], self.data_sub(self.bkg_opt), label="data_sub"
            )

        except TypeError:
            ax[0].plot(
                self.bkg_df.iloc[:, 0],
                self.bkg_df.iloc[:, 1] * self.guess_01(),
                "r.",
                label="scaled_bkg",
            )
            ax[1].plot(
                self.data_df.iloc[:, 0],
                self.data_sub(self.guess_01()),
                label="data_sub",
            )

        ax[0].legend()
        ax[1].legend()


# Backward-compatible names used by earlier beamline scripts.
server_log = ServerState
get_HeaderRows = get_header_rows
auto_bkg = AutoBackground

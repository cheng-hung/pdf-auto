import matplotlib.pyplot as plt
import numpy as np
import numpy.ma as ma
import pandas as pd

from ..core.utilities import bin_ndarray, get_header_rows, random_color
from .plot_widgets import HistogramTuner, ThreeSubTuner


class OpenFigures:
    def __init__(self, figure_labels: list | str):
        self.fig_dict = {}
        for name in figure_labels:
            self.fig_dict[name] = plt.figure(num=name, figsize=(8, 6))
        plt.ion()


class ImagePlotter(OpenFigures):
    def __init__(
        self,
        sample_name,
        figure_labels=(
            "tiff & Histogram",
            "I(Q)",
            "S(Q)",
            "f(Q)",
            "g(r)",
        ),
        color_str="",
    ):
        self.fig = figure_labels
        # self.uid = metadata_dic['uid']
        self.sample_name = sample_name
        # self.fontsize = 14
        self.labelsize = 14
        self.legend_prop = {"weight": "regular", "size": 14}
        self.title_prop = {"weight": "regular", "size": 12}
        self.xylabel_prop = {"weight": "regular", "size": 14}
        self.color_str = random_color(previous_color=color_str)
        self.spine_width = 2
        # self.date, self.time = _readable_time(metadata_dic['time'])
        super().__init__(figure_labels)

    def plot_tiff3(self, img, mask, use_mask=False, histogram=False, aspect=None):
        plt.ion()

        try:
            # f = plt.figure(self.fig[0])
            # f = plt.figure('tiff & Histogram')
            f = self.fig_dict["tiff & Histogram"]
        except (IndexError, KeyError):
            f = plt.figure(self.fig[-1])

        f.clear()
        # plt.clf()

        if type(mask) is str:
            mask_array = np.load(mask)

        elif type(mask) is np.ndarray:
            mask_array = mask

        # mask_array = np.float32(mask_array)
        masked_ = ma.masked_array(img, mask=mask_array)
        masked_img = masked_.filled(fill_value=np.nan)

        if use_mask:
            img_tuner = HistogramTuner(
                f, masked_img, histogram=histogram, aspect=aspect
            )
        else:
            img_tuner = HistogramTuner(f, img, histogram=histogram, aspect=aspect)

        # for spine in ax.spines.values():
        #     spine.set_linewidth(self.spine_width)

        # ax.tick_params(axis='both', labelsize=self.labelsize)
        # ax.legend(prop=self.legend_prop)

        f.canvas.manager.show()
        f.canvas.flush_events()
        # f.canvas.draw_idle()

        return img_tuner

    def plot_maskImg_iq(
        self,
        img,
        mask,
        unrolled_array,
        iq_fn,
        poni_fn,
        aspect=None,
        binning=1,
        iq_df=None,
    ):
        plt.ion()

        try:
            # f = plt.figure(self.fig[1])
            f = self.fig_dict["I(Q)"]
        except (IndexError, KeyError):
            f = plt.figure(self.fig[-1])

        # Prefer an in-memory dataframe (from the reduced stream) over reading
        # the .iq file back; fall back to the file for the legacy callers.
        if iq_df is None:
            iq_df = pd.read_csv(
                iq_fn, names=["q", "I(q)"], sep=" ", skiprows=get_header_rows(iq_fn)
            )

        f.clear()
        # plt.clf()

        if type(mask) is str:
            mask_array = np.load(mask)

        elif type(mask) is np.ndarray:
            mask_array = mask

        # mask_array = np.float32(mask_array)
        masked_ = ma.masked_array(img, mask=mask_array)
        masked_img = masked_.filled(fill_value=np.nan)

        new_shape = (
            int(unrolled_array.shape[0] / binning),
            int(unrolled_array.shape[1] / binning),
        )
        bin_unrolled = bin_ndarray(unrolled_array, new_shape=new_shape)

        img_tuner = ThreeSubTuner(
            f,
            masked_img,
            unrolled_array=bin_unrolled,
            aspect=aspect,
            data=iq_df,
            poni_fn=poni_fn,
            color_str=self.color_str,
            sample_name=self.sample_name,
        )

        # if title != None:
        #     ax.set_title(title, prop=self.title_prop)
        # else:
        #     pass

        for spine in img_tuner.ax2.spines.values():
            spine.set_linewidth(self.spine_width)

        img_tuner.ax2.set_xlabel("Q (A-1)", fontdict=self.xylabel_prop)
        img_tuner.ax2.set_ylabel("I(Q)", fontdict=self.xylabel_prop)
        img_tuner.ax2.legend(prop=self.legend_prop)

        # img_tuner.fig.subplots_adjust(left=0.08, right=0.97, top=0.97, bottom=0.1)

        f.canvas.manager.show()
        f.canvas.flush_events()
        # f.canvas.draw_idle()

        return img_tuner

    def plot_sqfqgr(self, sqfqgr_path, bkg_scale, bkg_fn, title=None):
        plt.ion()

        # try:
        #     f = plt.figure(self.fig[1])
        # except (IndexError):
        #     f = plt.figure(self.fig[-1])

        # bkg_exist = os.path.exists(bkg_fn)
        # if bkg_exist:
        #     rows = get_HeaderRows(bkg_fn, sep=' ', num_data_column=2,
        #                 check_range=100, check_float=True)
        #     bkg_df = pd.read_csv(bkg_fn, names=['x', 'y'], sep=' ', skiprows=rows)

        #     ax = f.gca()
        #     ax.plot(bkg_df['x'], bkg_df['y']*bkg_scale, label='background', marker='.', color='green')
        #     ax.legend(prop=self.legend_prop)

        keys = ["sq", "fq", "gr"]
        xlabel = ["q (A-1)", "q (A-1)", "r (A)"]
        ylabel = ["S(q)", "f(q)", "g(r)"]

        for i in range(len(sqfqgr_path)):
            try:
                # f = plt.figure(self.fig[i+2])
                f = self.fig_dict[self.fig[i + 2]]
            except (IndexError, KeyError):
                f = plt.figure(self.fig[-1])

            rows = get_header_rows(
                sqfqgr_path[keys[i]],
                sep=" ",
                num_data_column=2,
                check_range=100,
                check_float=True,
            )

            # df = pd.read_csv(sqfqgr_path[keys[i]], names=['x', 'y'], sep=' ', skiprows=27)
            df = pd.read_csv(
                sqfqgr_path[keys[i]], names=["x", "y"], sep=" ", skiprows=rows
            )

            ax = f.gca()
            ax.clear()

            for spine in ax.spines.values():
                spine.set_linewidth(self.spine_width)

            ax.plot(df["x"], df["y"], label=self.sample_name, color=self.color_str)

            if title is not None:
                ax.set_title(title, prop=self.title_prop)
            else:
                pass

            ax.set_xlabel(xlabel[i], fontdict=self.xylabel_prop)
            ax.set_ylabel(ylabel[i], fontdict=self.xylabel_prop)
            ax.legend(prop=self.legend_prop)

            f.canvas.manager.show()
            f.canvas.flush_events()
            # f.canvas.draw_idle()

    def plot_sqfqgr_arrays(self, pdf_arrays, title=None):
        """Plot S(Q)/F(Q)/G(r) from inline ``{out_type: (2, N) array}`` data.

        Array-based sibling of :meth:`plot_sqfqgr` for the plotting callback:
        it takes the reduced arrays already in memory (no file read / no race
        with SaveData). ``pdf_arrays`` maps ``"sq"``/``"fq"``/``"gr"`` to a
        ``(2, N)`` array of ``[x, y]``.
        """
        plt.ion()

        keys = ["sq", "fq", "gr"]
        xlabel = ["q (A-1)", "q (A-1)", "r (A)"]
        ylabel = ["S(q)", "f(q)", "g(r)"]

        for i, key in enumerate(keys):
            xy = pdf_arrays.get(key)
            if xy is None:
                continue

            try:
                f = self.fig_dict[self.fig[i + 2]]
            except (IndexError, KeyError):
                f = plt.figure(self.fig[-1])

            xy = np.asarray(xy)
            ax = f.gca()
            ax.clear()

            for spine in ax.spines.values():
                spine.set_linewidth(self.spine_width)

            ax.plot(xy[0], xy[1], label=self.sample_name, color=self.color_str)

            if title is not None:
                ax.set_title(title, prop=self.title_prop)

            ax.set_xlabel(xlabel[i], fontdict=self.xylabel_prop)
            ax.set_ylabel(ylabel[i], fontdict=self.xylabel_prop)
            ax.legend(prop=self.legend_prop)

            f.canvas.manager.show()
            f.canvas.flush_events()

    def clear_sqfqgr(self):

        for i in range(len(self.fig[2:])):
            try:
                # f = plt.figure(self.fig[i+2])
                f = self.fig_dict[self.fig[i + 2]]
            except (IndexError, KeyError):
                f = plt.figure(self.fig[-1])

            ax = f.gca()
            ax.clear()

    # def plot_tiff(self, img, title=None):

    #     try:
    #         f = plt.figure(self.fig[0])
    #     except (IndexError):
    #         f = plt.figure(self.fig[-1])

    #     plt.clf()
    #     ax = f.gca()

    #     for spine in ax.spines.values():
    #         spine.set_linewidth(self.spine_width)

    #     vmax = np.nanpercentile(img, 98)
    #     # vmax = 10000
    #     if vmax==np.nan:
    #        vmax = 10000

    #     vmin = np.nanpercentile(img, 10)
    #     if vmin==np.nan:
    #        vmin = 0

    #     im = ax.imshow(img, label=self.sample_name,
    #                    vmin=vmin, vmax=vmax)
    #     f.colorbar(im)

    #     if title != None:
    #         ax.set_title(title, prop=self.title_prop)
    #     else:
    #         pass

    #     ax.tick_params(axis='both', labelsize=self.labelsize)
    #     ax.legend(prop=self.legend_prop)

    #     f.canvas.manager.show()
    #     f.canvas.flush_events()


# Backward-compatible names used by earlier beamline scripts.
open_figures = OpenFigures
img_plotter = ImagePlotter

# def plot_tiff2(self, img, mask_img, title=None):

#     try:
#         f = plt.figure(self.fig[0])
#     except (IndexError):
#         f = plt.figure(self.fig[-1])

#     plt.clf()
#     # ax = f.gca()
#     ax1 = f.add_subplot(1, 2, 1)
#     ax2 = f.add_subplot(1, 2, 2)

#     mask_img = np.invert(mask_img.astype(bool))
#     masked_img = img * mask_img
#     masked_img[masked_img==0] = np.nan

#     img_list = [img, masked_img]
#     ax = [ax1, ax2]

#     for i in range(len(ax)):

#         for spine in ax[i].spines.values():
#             spine.set_linewidth(self.spine_width)

#         vmax = np.nanpercentile(img_list[i], 98)
#         # vmax = 10000
#         if vmax==np.nan:
#             vmax = 10000

#         vmin = np.nanpercentile(img_list[i], 10)
#         if vmin==np.nan:
#             vmin = 0

#         im = ax[i].imshow(img_list[i], label=self.sample_name,
#                         vmin=vmin, vmax=vmax)

#         f.colorbar(im, shrink=0.75)
#         # f.colorbar(im2, shrink=0.5)

#         if title != None:
#             ax[i].set_title(title, prop=self.title_prop)
#             # ax2.set_title(title, prop=self.title_prop)
#         else:
#             pass

#         ax[i].tick_params(axis='both', labelsize=self.labelsize)
#         ax[i].legend(prop=self.legend_prop)

#         # ax2.tick_params(axis='both', labelsize=self.labelsize)
#         # ax2.legend(prop=self.legend_prop)

#     f.canvas.manager.show()
#     f.canvas.flush_events()

# def plot_tiff4(self, unrolled_array, q_array, binned=True, aspect='auto'):

#     try:
#         # f = plt.figure(self.fig[0])
#         f = plt.figure('Unroll masked pct-filtered tiff', figsize=(8,6))
#     except (IndexError):
#         f = plt.figure(self.fig[-1])

#     plt.clf()
#     # ax = f.gca()

#     img = unrolled_array.filled(fill_value=np.nan)

#     if binned:
#         img = bin_ndarray(img)

#     img_tuner = color_tuner(f, img, q_array=q_array, histogram=False, aspect=aspect)

#     # ax.tick_params(axis='both', labelsize=self.labelsize)
#     # ax.legend(prop=self.legend_prop)

#     f.canvas.manager.show()
#     f.canvas.flush_events()

#     return img_tuner

# def plot_iq(self, iq_fn, skip_rows, title=None,):

#     try:
#         f = plt.figure(self.fig[1])
#     except (IndexError):
#         f = plt.figure(self.fig[-1])

#     iq_df = pd.read_csv(iq_fn, names=['q', 'I(q)'], sep=' ', skiprows=skip_rows)

#     plt.clf()
#     ax = f.gca()

#     for spine in ax.spines.values():
#         spine.set_linewidth(self.spine_width)

#     ax.plot(iq_df['q'], iq_df['I(q)'], label=self.sample_name, color=self.color_str)

#     if title != None:
#         ax.set_title(title, prop=self.title_prop)
#     else:
#         pass

#     ax.set_xlabel('Q (A-1)', fontdict=self.xylabel_prop)
#     ax.set_ylabel('I(Q)', fontdict=self.xylabel_prop)
#     ax.legend(prop=self.legend_prop)

#     f.canvas.manager.show()
#     f.canvas.flush_events()

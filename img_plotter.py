import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import numpy.ma as ma
import os

import importlib
get_HeaderRows = importlib.import_module("kafka_uti").get_HeaderRows
random_color = importlib.import_module("kafka_uti").random_color
histogram_tuner = importlib.import_module("subplot_tuner").histogram_tuner
ThreeSub_tuner = importlib.import_module("subplot_tuner").ThreeSub_tuner
bin_ndarray = importlib.import_module("kafka_uti").bin_ndarray
# Pilatus_getpdf = importlib.import_module("pilatus_getpdf_v2.2").Pilatus_Int

class open_figures():
    def __init__(self, figure_labels):
        for i in figure_labels:
            plt.figure(num=i, figsize=(8,6))


class img_plotter(open_figures):
    
    def __init__(self, sample_name, 
                 figure_labels = ['tiff & Histogram', 'I(Q)', 'S(Q)', 'f(Q)', 'g(r)', ], 
                 color_str = '',
                ):
        self.fig = figure_labels
        # self.uid = metadata_dic['uid']
        self.sample_name = sample_name
        # self.fontsize = 14
        self.labelsize = 14
        self.legend_prop = {'weight':'regular', 'size':14}
        self.title_prop = {'weight':'regular', 'size':12}
        self.xylabel_prop = {'weight':'regular', 'size':14}
        self.color_str = random_color(previous_color=color_str)
        self.spine_width = 2
        # self.date, self.time = _readable_time(metadata_dic['time'])
        super().__init__(figure_labels)



    def plot_tiff3(self, img, mask, use_mask=False, histogram=False, aspect=None):
        
        try:
            f = plt.figure(self.fig[0])
            # f = plt.figure('test')
        except (IndexError): 
            f = plt.figure(self.fig[-1])

        plt.clf()
        # ax = f.gca()

        if type(mask) is str:
            mask_array = np.load(mask)

        elif type(mask) is np.ndarray:
            mask_array = mask
        
        # mask_array = np.float32(mask_array)
        masked_ = ma.masked_array(img, mask=mask_array)
        masked_img = masked_.filled(fill_value=np.nan)

        if use_mask:
            img_tuner = histogram_tuner(f, masked_img, histogram=histogram, aspect=aspect)
        else:
            img_tuner = histogram_tuner(f, img, histogram=histogram, aspect=aspect)

        # for spine in ax.spines.values():
        #     spine.set_linewidth(self.spine_width)

        # ax.tick_params(axis='both', labelsize=self.labelsize)
        # ax.legend(prop=self.legend_prop)

        f.canvas.manager.show()
        f.canvas.flush_events()

        return img_tuner

        

    def plot_maskImg_iq(self, img, mask, unrolled_array, iq_fn, poni_fn, aspect=None, binning=1):
        
        try: 
            f = plt.figure(self.fig[1])
        except (IndexError): 
            f = plt.figure(self.fig[-1])
        
        iq_df = pd.read_csv(iq_fn, names=['q', 'I(q)'], sep=' ', skiprows=get_HeaderRows(iq_fn))

        plt.clf()

        if type(mask) is str:
            mask_array = np.load(mask)

        elif type(mask) is np.ndarray:
            mask_array = mask
        
        # mask_array = np.float32(mask_array)
        masked_ = ma.masked_array(img, mask=mask_array)
        masked_img = masked_.filled(fill_value=np.nan)
        
        new_shape = (int(unrolled_array.shape[0]/binning), int(unrolled_array.shape[1]/binning))
        bin_unrolled = bin_ndarray(unrolled_array, new_shape=new_shape)

        img_tuner = ThreeSub_tuner(f, masked_img, 
                                   unrolled_array=bin_unrolled, 
                                   aspect=aspect, 
                                   data=iq_df, 
                                   poni_fn=poni_fn, 
                                   color_str=self.color_str, 
                                   sample_name = self.sample_name, 
                                   )

        # if title != None:
        #     ax.set_title(title, prop=self.title_prop)
        # else:
        #     pass

        for spine in img_tuner.ax2.spines.values():
                spine.set_linewidth(self.spine_width)

        img_tuner.ax2.set_xlabel('Q (A-1)', fontdict=self.xylabel_prop)
        img_tuner.ax2.set_ylabel('I(Q)', fontdict=self.xylabel_prop)
        img_tuner.ax2.legend(prop=self.legend_prop)

        # img_tuner.fig.subplots_adjust(left=0.08, right=0.97, top=0.97, bottom=0.1)

        f.canvas.manager.show()
        f.canvas.flush_events()

        return img_tuner

        

    def plot_sqfqgr(self, sqfqgr_path, bkg_scale, bkg_fn, title=None):

        try: 
            f = plt.figure(self.fig[1])
        except (IndexError): 
            f = plt.figure(self.fig[-1])

        bkg_exist = os.path.exists(bkg_fn)
        if bkg_exist:
            rows = get_HeaderRows(bkg_fn, sep=' ', num_data_column=2, 
                        check_range=100, check_float=True)
            bkg_df = pd.read_csv(bkg_fn, names=['x', 'y'], sep=' ', skiprows=rows)
            
            ax = f.gca()
            ax.plot(bkg_df['x'], bkg_df['y']*bkg_scale, label='background', marker='.', color='green')
            ax.legend(prop=self.legend_prop)
        
        keys = ['sq', 'fq', 'gr']
        xlabel = ['q (A-1)', 'q (A-1)', 'r (A)']
        ylabel = ['S(q)', 'f(q)', 'g(r)']

        for i in range(len(sqfqgr_path)):

            try: 
                f = plt.figure(self.fig[i+2])
            except (IndexError): 
                f = plt.figure(self.fig[-1])
        
            rows = get_HeaderRows(sqfqgr_path[keys[i]], sep=' ', num_data_column=2, 
                        check_range=100, check_float=True)

            # df = pd.read_csv(sqfqgr_path[keys[i]], names=['x', 'y'], sep=' ', skiprows=27)
            df = pd.read_csv(sqfqgr_path[keys[i]], names=['x', 'y'], sep=' ', skiprows=rows)


            plt.clf()
            ax = f.gca()

            for spine in ax.spines.values():
                spine.set_linewidth(self.spine_width)
            
            ax.plot(df['x'], df['y'], label=self.sample_name, color=self.color_str)

            if title != None:
                ax.set_title(title, prop=self.title_prop)
            else:
                pass

            ax.set_xlabel(xlabel[i], fontdict=self.xylabel_prop)
            ax.set_ylabel(ylabel[i], fontdict=self.xylabel_prop)
            ax.legend(prop=self.legend_prop)

            f.canvas.manager.show()
            f.canvas.flush_events()
        


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



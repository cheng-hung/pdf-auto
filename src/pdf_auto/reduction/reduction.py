import os

from diffpy.pdfgetx import PDFConfig
from pdfstream.transformation.main import get_pdf

# from diffpy.pdfgetx.pdfgetter import PDFConfigError
from ..core.utilities import AutoBackground, get_header_rows
from . import integration


class PDFReducer(integration.ImageIntegrator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bgscale = self.getfloat("pdfgetx3", "bgscale", fallback=0.98)
        self._backgroundfile = self.get("pdfgetx3", "backgroundfile", fallback="")
        self.auto_bkg = 1.0

    @property
    def use_auto_bkg(self):
        return self.getboolean("pdfgetx3", "use_auto_bkg", fallback=False)

    @property
    def do_reduction(self):
        return self.getboolean("pdfgetx3", "do_reduction", fallback=True)

    @property
    def bgscale(self):
        return self._bgscale

    @bgscale.setter
    def bgscale(self, scale):
        self._bgscale = scale

    @property
    def backgroundfile(self):
        return self._backgroundfile

    @backgroundfile.setter
    def backgroundfile(self, fn):
        self._backgroundfile = fn

    @property
    def pdfconfig_dict(self):
        return {
            "dataformat": self.get("pdfgetx3", "dataformat", fallback="QA"),
            "outputtype": self.get("pdfgetx3", "outputtype", fallback="gr"),
            "backgroundfile": self.backgroundfile,
            "plot": self.get("pdfgetx3", "plot", fallback="none"),
            # 'bgscale':          self.getfloat('pdfgetx3', 'bgscale', fallback=0.98),
            "bgscale": self.bgscale,
            "rpoly": self.getfloat("pdfgetx3", "rpoly", fallback=1.0),
            "qmaxinst": self.getfloat("pdfgetx3", "qmaxinst", fallback=27.0),
            "qmin": self.getfloat("pdfgetx3", "qmin", fallback=0.6),
            "qmax": self.getfloat("pdfgetx3", "qmax", fallback=25.0),
            "rmin": self.getfloat("pdfgetx3", "rmin", fallback=0.0),
            "rmax": self.getfloat("pdfgetx3", "rmax", fallback=100.0),
            "rstep": self.getfloat("pdfgetx3", "rstep", fallback=0.1),
            "composition": self.run.start["composition_string"],
            "temperature_K": self.temperature,
        }

    def pdfconfig(self):

        p = PDFConfig()
        for key, value in self.pdfconfig_dict.items():
            setattr(p, key, value)

        return p

    @property
    def pdfgetter_prefix(self):
        """Filename prefix (with treatment suffix) for the PDFgetX products.

        Mirrors the suffix logic of
        :meth:`pdf_auto.reduction.image_processing.ImageData2D.output_data_path`:
        ``_sum`` for stitched pilatus, ``_flat`` for flat-fielded pe1c, and
        ``_sub`` otherwise. Returned as a plain string so the value can be
        published and used by :class:`pdf_auto.callbacks.save_data.SaveData`.
        """
        if "pilatus" in self.detector:
            return f"{self.file_name_prefix}_sum"

        if "pe1" in self.detector and self.use_flat_field_pe1c:
            return f"{self.file_name_prefix}_flat"

        return f"{self.file_name_prefix}_sub"

    @staticmethod
    def pdfgetter_arrays(pdfgetter) -> dict:
        """Extract the (x, y) output arrays from a diffpy ``PDFGetter``.

        Returns ``{out_type: numpy.ndarray of shape (2, N)}`` for each type in
        ``pdfgetter.config.outputtypes`` (a subset of ``iq``/``sq``/``fq``/
        ``gr``). These plain numpy arrays are picklable and survive ZMQ, unlike
        the ``PDFGetter`` object itself, which may hold non-picklable state and
        silently break :class:`bluesky.callbacks.zmq.RemoteDispatcher`
        deserialization. :class:`pdf_auto.callbacks.save_data.SaveData` writes the files
        from these arrays.
        """
        import numpy as np

        arrays: dict = {}
        for out_type in pdfgetter.config.outputtypes:
            x, y = getattr(pdfgetter, out_type)
            arrays[out_type] = np.vstack([np.asarray(x), np.asarray(y)])
        return arrays

    ## Modified from https://github.com/NSLS2/xpd-profile-collection-ldrd20-31/blob/main/scripts/_get_pdf.py
    def compute_pdfgetter(self, iq_df):
        """Run the PDFgetX transformation and return picklable output arrays.

        Returns ``(pdf_arrays, process_det_dir, pdfgetter_prefix)`` where
        ``pdf_arrays`` is ``{out_type: (2, N) ndarray}`` (see
        :meth:`pdfgetter_arrays`). :class:`pdf_auto.callbacks.save_data.SaveData` writes
        the ``.sq``/``.fq``/``.gr`` files from these arrays. This method
        performs no file I/O and never returns the live ``PDFGetter`` object, so
        the published ``reduced`` event stays fully picklable across ZMQ.
        """

        try:
            # self.pdfconfig().composition = self.run.start['composition_string']
            print(f"\nFound composition as {self.run.start["composition_string"] = }\n")

        except KeyError:
            # self.pdfconfig().composition = 'Ni1.0'
            print(
                '\nCan not find sample composition in run.start. Use "Ni1.0" instead.\n'
            )
            self.run.start["composition_string"] = "Ni1.0"

        print(f"\n{self.pdfconfig_dict = }\n")
        # print(self.pdfconfig())

        pdfgetter = get_pdf(self.pdfconfig(), iq_df, plot_setting="OFF")

        return (
            self.pdfgetter_arrays(pdfgetter),
            self.process_det_dir,
            self.pdfgetter_prefix,
        )

    def get_gr(self, iq_df):

        # try:
        #     # self.pdfconfig().composition = self.run.start['composition_string']
        #     print(f'\nFound composition as {self.run.start["composition_string"] = }\n')

        # except (KeyError):
        #     # self.pdfconfig().composition = 'Ni1.0'
        #     print(f'\nCan not find sample composition in run.start. Use "Ni1.0" instead.\n')
        #     self.run.start['composition_string'] = 'Ni1.0'

        bkg_exist = os.path.exists(self.pdfconfig_dict["backgroundfile"])
        ## Use auto_bkg to repalce the bkg in pdfconfig
        if self.use_auto_bkg and bkg_exist:
            a_bkg = AutoBackground()
            a_bkg.data_df = iq_df

            rows = get_header_rows(
                self.pdfconfig_dict["backgroundfile"],
                sep=" ",
                num_data_column=2,
                check_range=100,
                check_float=True,
            )

            a_bkg.pdload_bkg(
                self.pdfconfig_dict["backgroundfile"],
                #  skiprows=self.num_rows_header,
                skiprows=rows,
                sep=" ",
                names=["Q", "I"],
            )
            res = a_bkg.min_integral()
            print(f"{res.x = }")
            self.bgscale = float(res.x)
            print(f"{self.pdfconfig().bgscale[0] = }")
            self.auto_bkg = res.x
            print(f"\nUpdate {self.pdfconfig().bgscales[0] = } by auto_bkg\n")
            # a_bkg.plot_sub()

        elif bkg_exist is False:
            print(
                f"\n{self.pdfconfig_dict['backgroundfile']} doesn't exist.\n"
                f"Use a dummy background for gr transformation.\n"
            )
            # self.backgroundfile = '/home/xf28id1/Documents/chenghung/B_Empty_Kapton_last_PDF_20250730-053726_6070e6_primary-1_mean_q.chi'

        iq_array = iq_df.to_numpy().T
        # Compute the pdfgetter and return it with its target dir + prefix.
        # Writing S(Q)/F(Q)/G(r) is deferred to pdf_auto.callbacks.save_data.SaveData.
        return self.compute_pdfgetter(iq_array)


# Backward-compatible name used by earlier beamline scripts.
img_getpdf = PDFReducer

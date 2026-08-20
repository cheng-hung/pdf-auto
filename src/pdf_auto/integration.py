import os

import numpy as np
import numpy.ma as ma
import pandas as pd
import pyFAI

from . import image_processing


def iq_saver(fn, df, md, header=("#q_A^-1", "I(q)")):

    with open(fn, mode="w", encoding="utf-8") as f:
        f.write("# pyFai_poni_information_28ID1_NSLS2_BNL\n")
        num_row = 1
        for key, value in md.items():
            f.write(f"# {key} {value}\n")
            num_row += 1

    ## Now append the dataframe
    df.to_csv(
        fn,
        encoding="utf-8",
        mode="a",
        header=header,
        index=False,
        float_format="{:.8e}".format,
        sep=" ",
    )

    ## return the number of rows of the header
    return num_row


def q_to_twotheta(q_array, wavelength):
    twotheta_radian = 2 * np.arcsin(q_array * wavelength / (4 * np.pi))
    return np.degrees(twotheta_radian)


class ImageIntegrator(image_processing.ImageData2D):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.num_rows_header = 1
        self.ai = None

    @property
    def merged_poin(self):
        n = self.get("PATH", "merged_poin", fallback="merged.poni")

        if self.acq_mode == "PDF":
            n_folder = self.pilatus_PDF

        elif self.acq_mode == "XRD":
            n_folder = self.pilatus_XRD

        else:
            n_folder = self.pilatus_PDF

        return os.path.join(n_folder, n)

    @property
    def stitched_mask(self):
        n = self.get("PATH", "stitched_mask", fallback="stitched_mask.npy")

        if self.acq_mode == "PDF":
            n_folder = self.pilatus_PDF

        elif self.acq_mode == "XRD":
            n_folder = self.pilatus_XRD

        else:
            n_folder = self.pilatus_PDF

        return os.path.join(n_folder, n)

    @property
    def pe1c_PDF(self):
        n = self.get("PATH", "pe1c_PDF", fallback="pe1c_PDF")
        return os.path.join(self.config_base, n)

    @property
    def pe1c_XRD(self):
        n = self.get("PATH", "pe1c_XRD", fallback="pe1c_XRD")
        return os.path.join(self.config_base, n)

    @property
    def pe2c_SAXS(self):
        n = self.get("PATH", "pe2c_SAXS", fallback="pe2c_SAXS")
        return os.path.join(self.config_base, n)

    @property
    def lambda_SAXS(self):
        n = self.get("PATH", "lambda_SAXS", fallback="lambda_SAXS")
        return os.path.join(self.config_base, n)

    @property
    def poni_pilatus(self):
        n = self.get("PATH", "poni_pilatus", fallback="xpdAcq_calib_info.poni")

        if self.acq_mode == "PDF":
            n_folder = self.pilatus_PDF

        elif self.acq_mode == "XRD":
            n_folder = self.pilatus_XRD

        else:
            n_folder = self.pilatus_PDF

        return os.path.join(n_folder, n)

    @property
    def mask_pilatus(self):
        n = self.get("PATH", "mask_pilatus", fallback="Mask.npy")

        if self.acq_mode == "PDF":
            n_folder = self.pilatus_PDF

        elif self.acq_mode == "XRD":
            n_folder = self.pilatus_XRD

        else:
            n_folder = self.pilatus_PDF

        return os.path.join(n_folder, n)

    @property
    def poni_pe1c(self):
        n = self.get("PATH", "poni_pe1c", fallback="xpdAcq_calib_info.poni")

        if self.acq_mode == "PDF":
            n_folder = self.pe1c_PDF

        elif self.acq_mode == "XRD":
            n_folder = self.pe1c_XRD

        else:
            n_folder = self.pe1c_PDF

        return os.path.join(n_folder, n)

    @property
    def mask_pe1c(self):
        n = self.get("PATH", "mask_pe1c", fallback="Mask.npy")

        if self.acq_mode == "PDF":
            n_folder = self.pe1c_PDF

        elif self.acq_mode == "XRD":
            n_folder = self.pe1c_XRD

        else:
            n_folder = self.pe1c_PDF

        return os.path.join(n_folder, n)

    @property
    def poni_pe2c(self):
        n = self.get("PATH", "poni_pe2c", fallback="xpdAcq_calib_info.poni")
        return os.path.join(self.pe2c_SAXS, n)

    @property
    def mask_pe2c(self):
        n = self.get("PATH", "mask_pe2c", fallback="Mask.npy")
        return os.path.join(self.pe2c_SAXS, n)

    @property
    def poni_lambda(self):
        n = self.get("PATH", "poni_lambda", fallback="xpdAcq_calib_info.poni")
        return os.path.join(self.lambda_SAXS, n)

    @property
    def mask_lambda(self):
        n = self.get("PATH", "mask_lambda", fallback="Mask.npy")
        return os.path.join(self.lambda_SAXS, n)

    @property
    def poni_mask_fn(self):

        if self.stream_length == self.num_positions:
            return self.merged_poin, self.stitched_mask

        else:
            if "pilatus" in self.detector:
                return self.poni_pilatus, self.mask_pilatus

            elif "pe1" in self.detector:
                return self.poni_pe1c, self.mask_pe1c

            elif "pe2" in self.detector:
                return self.poni_pe2c, self.mask_pe2c

            elif "lambda" in self.detector:
                return self.poni_lambda, self.mask_lambda

            else:
                return self.poni_pe1c, self.mask_pe1c

    @property
    def mask_array(self):

        if self.stream_length == self.num_positions:
            return np.load(self.stitched_mask)

        else:
            if "pilatus" in self.detector:
                return np.load(self.mask_pilatus)

            elif "pe1" in self.detector:
                return np.load(self.mask_pe1c)

            elif "pe2" in self.detector:
                return np.load(self.mask_pe2c)

            elif "lambda" in self.detector:
                return np.load(self.mask_lambda)

            else:
                return np.load(self.mask_pe1c)

    @property
    def npt_rad(self):
        # equivalent to binning
        return self.getint("INTEGRATION", "npt_rad", fallback=4096)

    @property
    def npt_azim(self):
        return self.getint("INTEGRATION", "npt_azim", fallback=3600)

    @property
    def polarization(self):
        return self.getfloat("INTEGRATION", "polarization", fallback=0.99)

    @property
    def UNIT(self):
        return self.get("INTEGRATION", "UNIT", fallback="q_A^-1")

    @property
    def ll(self):
        return self.getfloat("INTEGRATION", "low_limit_pcfilter", fallback=1.0)

    @property
    def ul(self):
        return self.getfloat("INTEGRATION", "up_limit_pcfilter", fallback=99.0)

    def pct_integration(self):

        poni, _ = self.poni_mask_fn
        self.ai = pyFAI.load(poni)

        ## perform azimuthalintegration on one image to retain 2D information
        ## i2d.shape is (self.npt_azim, self.npt_rad) which corresponds the intensity of 2D image cake
        ## q1d.shape is (self.npt_rad, )
        i2d, q1d, chi1d = self.ai.integrate2d(
            self.process_img,
            self.npt_rad,
            unit=self.UNIT,
            npt_azim=self.npt_azim,
            polarization_factor=self.polarization,
        )
        #  mask=self.mask_array)

        ## trasnform self.mask_array (base mask) to the same coordinate space and cast it as type bool
        intrinsic_mask_unrolled, _, _ = self.ai.integrate2d(
            self.mask_array,
            self.npt_rad,
            unit=self.UNIT,
            npt_azim=self.npt_azim,
            polarization_factor=self.polarization,
        )
        #    mask=self.mask_array)
        # intrinsic_mask_unrolled = intrinsic_mask_unrolled.astype(bool)

        ## Create an array to hold outlier mask
        outlier_mask_2d = np.zeros_like(i2d)
        mask1 = np.array(i2d < 1) * 1

        ## Apply percentile filter along radial direction (axis=0)
        for ii, dd in enumerate(i2d.T):
            low_limit, high_limit = np.percentile(dd, (self.ll, self.ul))
            outlier_mask_2d[:, ii] = np.any(
                [dd < low_limit, dd > high_limit, intrinsic_mask_unrolled[:, ii]],
                axis=0,
            )

        outlier_mask_2d_masked = ma.masked_array(i2d, mask=outlier_mask_2d + mask1)
        # outlier_mask_2d_masked = ma.masked_array(i2d, mask=outlier_mask_2d)

        ## calculate mean values along radial direction (axis=0) to make i1d.shape is (self.npt_rad, )
        i1d = ma.mean(outlier_mask_2d_masked, axis=0)

        iq_df0 = pd.DataFrame()
        iq_df0["q"] = q1d
        iq_df0["I"] = i1d
        # iq_df = iq_df0.dropna()
        iq_df = iq_df0.fillna(0)

        ## export two theta data
        iq_df1 = pd.DataFrame()
        iq_df1["tth"] = q_to_twotheta(q1d, self.wavelength)
        iq_df1["I"] = i1d
        # iq_df = iq_df0.dropna()
        iq_df10 = iq_df1.fillna(0)

        # md = self.ai.getPyFAI()
        md = self.ai.get_config()
        _md = {
            "detector": self.run.start["detectors"][0],
            "uid": self.full_uid,
            "time": self.run.start["time"],
            "wavelength": f"{self.wavelength} (A)",
            "readable_time": self.readable_time,
            "percentile_low_limit": self.ll,
            "percentile_up_limit": self.ul,
            self.T_controller: f"{self.temperature} {self.T_unit}",
            f"Temp ({self.T_unit}) = ": f"{self.temperature}",
            "sample_name": self.sample_name,
            "composition": self.run.start["composition_string"],
        }

        md.update(_md)

        if type(self.temperature) is float:
            md.update({"temperature": f"{self.temperature:.2f} {self.T_unit}"})
        else:
            md.update({"temperature": "None"})

        if "flow_cell_thermocouple" in self.run.start:
            flow_cell_thermocouple = float(self.run.start["flow_cell_thermocouple"])
            md.update({"flow_cell_thermocouple": f"{flow_cell_thermocouple:.2f} C"})

        iq_fn = self.output_data_path(sub_name="iq", file_type="iq")
        tth_fn = self.output_data_path(sub_name="tth", file_type="xy")

        # File I/O is deferred to :class:`pdf_auto.save_data.SaveData`. Record
        # the number of header rows the saver will write so downstream code
        # (e.g. auto-background) can skip them consistently.
        self.num_rows_header = 1 + len(md)

        # Return everything SaveData needs to write the .iq/.xy files plus the
        # in-memory results used for reduction and publishing:
        #   iq_df   - q/I dataframe (used by get_gr and published)
        #   tth_df  - two-theta/I dataframe (published + written to .xy)
        #   md      - header metadata dict shared by both files
        #   iq_fn   - target path for the I(Q) file
        #   tth_fn  - target path for the two-theta file
        #   masked  - the percentile-filtered 2D cake (published for plotting)
        return iq_df, iq_df10, md, iq_fn, tth_fn, outlier_mask_2d_masked


# Backward-compatible name used by earlier beamline scripts.
img_integrate = ImageIntegrator

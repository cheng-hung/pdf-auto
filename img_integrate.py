import pyFAI
import os
import numpy as np
import numpy.ma as ma
import pandas as pd

import importlib
imgData_2D = importlib.import_module("imgData_2D")


def iq_saver(fn, df, md, header=['q_A^-1', 'I(q)']):
    
    with open(fn, mode='w', encoding='utf-8') as f:
        f.write('pyFai_poni_information_28ID1_NSLS2_BNL\n')
        num_row = 1
        for key, value in md.items():
            f.write(f'{key} {value}\n')
            num_row += 1
    
    ## Now append the dataframe
    df.to_csv(fn, encoding='utf-8', mode='a', header=header, index=False, float_format='{:.8e}'.format, sep=' ')

    ## return the number of rows of the header
    return num_row


def q_to_twotheta(q_array, wavelength):
    twotheta_radian = 2 * np.arcsin(q_array*wavelength/(4*np.pi))
    return np.degrees(twotheta_radian)


class img_integrate(imgData_2D.imgData_2D):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.num_rows_header = 1
        self.ai = None


    @property
    def merged_poin(self):
        n = self.get('PATH', 'merged_poin', fallback='merged.poni')

        if self.acq_mode() == 'PDF':
            n_folder = self.pilatus_PDF

        elif self.acq_mode() == 'XRD':
            n_folder = self.pilatus_XRD

        else:
            n_folder = self.pilatus_PDF

        return os.path.join(n_folder, n)
    

    @property
    def stitched_mask(self):
        n = self.get('PATH', 'stitched_mask', fallback='stitched_mask.npy')

        if self.acq_mode() == 'PDF':
            n_folder = self.pilatus_PDF

        elif self.acq_mode() == 'XRD':
            n_folder = self.pilatus_XRD

        else:
            n_folder = self.pilatus_PDF

        return os.path.join(n_folder, n)
    

    @property
    def pe1c_PDF(self):
        n = self.get('PATH', 'pe1c_PDF', fallback='pe1c_PDF')
        return os.path.join(self.config_base, n)
    
    @property
    def pe1c_XRD(self):
        n = self.get('PATH', 'pe1c_XRD', fallback='pe1c_XRD')
        return os.path.join(self.config_base, n)

    @property
    def pe2c_SAXS(self):
        n = self.get('PATH', 'pe2c_PDF', fallback='pe2c_SAXS')
        return os.path.join(self.config_base, n)
    

    @property
    def poni_pe1c(self):
        n = self.get('PATH', 'poni_pe1c', fallback='xpdAcq_calib_info.poni')

        if self.acq_mode() == 'PDF':
            n_folder = self.pe1c_PDF

        elif self.acq_mode() == 'XRD':
            n_folder = self.pe1c_XRD
        
        else:
            n_folder = self.pe1c_PDF

        return os.path.join(n_folder, n)
    

    @property
    def mask_pe1c(self):
        n = self.get('PATH', 'mask_pe1c', fallback='Mask.npy')

        if self.acq_mode() == 'PDF':
            n_folder = self.pe1c_PDF
        
        elif self.acq_mode() == 'XRD':
            n_folder = self.pe1c_XRD
        
        else:
            n_folder = self.pe1c_PDF

        return os.path.join(n_folder, n)


    @property
    def poni_pe2c(self):
        n = self.get('PATH', 'poni_pe2c', fallback='xpdAcq_calib_info.poni')
        return os.path.join(self.pe2c_SAXS, n)
    

    @property
    def mask_pe2c(self):
        n = self.get('PATH', 'mask_pe2c', fallback='Mask.npy')
        return os.path.join(self.pe2c_SAXS, n)


    @property
    def poni_fn(self):
        if 'pilatus' in self.detector:
            return self.merged_poin
            

        elif 'pe1' in self.detector:
            return self.poni_pe1c
            

        elif 'pe2' in self.detector:
            return self.poni_pe2c

        else:
            return self.poni_pe1c


    @property
    def mask_array(self):
        if 'pilatus' in self.detector:
            return np.load(self.stitched_mask)
            

        elif 'pe1' in self.detector:
            return np.load(self.mask_pe1c)
            

        elif 'pe2' in self.detector:
            return np.load(self.mask_pe2c)

        else:
            return np.load(self.mask_pe1c)



    @property
    def npt_rad(self):
        # equivalent to binning
        return self.getint('INTEGRATION', 'npt_rad', fallback=4096)
    
    @property
    def npt_azim(self):
        return self.getint('INTEGRATION', 'npt_azim', fallback=3600)
    
    @property
    def polarization(self):
        return self.getfloat('INTEGRATION', 'polarization', fallback=0.99)
    
    @property
    def UNIT(self):
        return self.get('INTEGRATION', 'UNIT', fallback="q_A^-1")
    
    @property
    def ll(self):
        return self.getfloat('INTEGRATION', 'low_limit_pcfilter', fallback=1.0)
    
    @property
    def ul(self):
        return self.getfloat('INTEGRATION', 'up_limit_pcfilter', fallback=99.0) 

            


    
    def pct_integration(self):

        self.ai = pyFAI.load(self.poni_fn)
        
        ## perform azimuthalintegration on one image to retain 2D information
        ## i2d.shape is (self.npt_azim, self.npt_rad) which corresponds the intensity of 2D image cake
        ## q1d.shape is (self.npt_rad, )
        i2d, q1d, chi1d = self.ai.integrate2d(self.process_img, self.npt_rad, 
                                         unit=self.UNIT, npt_azim=self.npt_azim, 
                                         polarization_factor=self.polarization, )
                                        #  mask=self.mask_array) 
        
        ## trasnform self.mask_array (base mask) to the same coordinate space and cast it as type bool
        intrinsic_mask_unrolled, _, _ = self.ai.integrate2d(self.mask_array, self.npt_rad, 
                                                       unit=self.UNIT, npt_azim=self.npt_azim, 
                                                       polarization_factor=self.polarization, )
                                                    #    mask=self.mask_array)
        #intrinsic_mask_unrolled = intrinsic_mask_unrolled.astype(bool) 
        
        ## Create an array to hold outlier mask
        outlier_mask_2d = np.zeros_like(i2d)     
        mask1 = np.array(i2d<1)*1
        
        ## Apply percentile filter along radial direction (axis=0)
        for ii, dd in enumerate(i2d.T):
            low_limit, high_limit = np.percentile(dd, (self.ll, self.ul))
            outlier_mask_2d[:,ii] = np.any([dd<low_limit, dd>high_limit, intrinsic_mask_unrolled[:,ii]], axis=0)
          
        outlier_mask_2d_masked = ma.masked_array(i2d, mask=outlier_mask_2d + mask1)
        # outlier_mask_2d_masked = ma.masked_array(i2d, mask=outlier_mask_2d)
        
        ## calculate mean values along radial direction (axis=0) to make i1d.shape is (self.npt_rad, )
        i1d = ma.mean(outlier_mask_2d_masked, axis=0)
        
        iq_df0 = pd.DataFrame()
        iq_df0['q'] = q1d
        iq_df0['I'] = i1d
        # iq_df = iq_df0.dropna()
        iq_df = iq_df0.fillna(0)

        ## export two theta data
        iq_df1 = pd.DataFrame()
        iq_df1['tth'] = q_to_twotheta(q1d, self.wavelength) 
        iq_df1['I'] = i1d
        # iq_df = iq_df0.dropna()
        iq_df10 = iq_df1.fillna(0)
        
        # md = self.ai.getPyFAI()
        md = self.ai.get_config()
        _md = {'detector': self.run.start['detectors'][0], 
               'uid':self.full_uid, 
               'time': self.run.start['time'], 
               'wavelength': f'{self.wavelength} (A)', 
               'readable_time': self.readable_time, 
               'percentile_low_limit': self.ll, 
               'percentile_up_limit': self.ul, 
               self.T_controller: f'{self.temperature} {self.T_unit}', 
        }
        md.update(_md)

        if type(self.temperature) is float:
            md.update({'temperature': f'{self.temperature:.2f} K'})

        os.makedirs(self.process_iq_dir, exist_ok=True)  # Create process_iq_dir directory if it doesn't exis
        os.makedirs(self.process_tth_dir, exist_ok=True)  # Create process_tth_dir directory if it doesn't exis

        if 'pilatus' in self.detector:
            iq_fn = os.path.join(self.process_iq_dir, f'{self.file_name_prefix}_sum.iq')
            tth_fn = os.path.join(self.process_tth_dir, f'{self.file_name_prefix}_sum.xy')

        elif 'pe1' in self.detector:
            if (self.use_flat_field_pe1c) and ('pe1' in self.detector):
                iq_fn = os.path.join(self.process_iq_dir, f'{self.file_name_prefix}_flat.iq')
                tth_fn = os.path.join(self.process_tth_dir, f'{self.file_name_prefix}_flat.xy')
            else:
                iq_fn = os.path.join(self.process_iq_dir, f'{self.file_name_prefix}_sub.iq')
                tth_fn = os.path.join(self.process_tth_dir, f'{self.file_name_prefix}_sub.xy')


        elif 'pe2' in self.detector:
            iq_fn = os.path.join(self.process_iq_dir, f'{self.file_name_prefix}_SAXS.iq')
            tth_fn = os.path.join(self.process_tth_dir, f'{self.file_name_prefix}_SAXS.xy')

        else:
            iq_fn = os.path.join(self.process_iq_dir, f'{self.file_name_prefix}_sub.iq')
            tth_fn = os.path.join(self.process_tth_dir, f'{self.file_name_prefix}_sub.xy')

        
        ## num_row will be the number of rows of the header in saved iq data file
        self.num_rows_header = iq_saver(iq_fn, iq_df, md)
        iq_saver(tth_fn, iq_df10, md, header=['tth', 'I(q)'])
        print(f'\n*** {os.path.basename(iq_fn)} saved!! ***\n')
        print(f'\n*** {os.path.basename(tth_fn)} saved!! ***\n')

        return iq_df, iq_fn, outlier_mask_2d_masked
import os
import numpy as np
import tifffile
from configparser import ConfigParser
from tiled.client import from_profile
import datetime
import pprint

tiled_client = from_profile('pdf')



def _readable_time(unix_time):
    from datetime import datetime
    dt = datetime.fromtimestamp(unix_time)
    # print(f'{dt.year}{dt.month:02d}{dt.day:02d},{dt.hour:02d}{dt.minute:02d}{dt.second:02d}')
    return (f'{dt.year}{dt.month:02d}{dt.day:02d}'), (f'{dt.hour:02d}{dt.minute:02d}{dt.second:02d}')



class imgData_config(ConfigParser):
    """The configuration for the server."""

    def __init__(self, config_fn, **kwargs):
        # self.uid = uid
        self.config_fn = config_fn
        super().__init__(**kwargs)


    def read(self, **kwargs):
        return super().read(self.config_fn, **kwargs)
        



class imgData_2D(imgData_config):

    def __init__(self, uid, tiled_client, config_fn, sandbox_tiled=None, **kwargs):
        self.uid = uid
        super().__init__(config_fn, **kwargs)
        self.read(**kwargs)

        self.tiled_client = tiled_client
        self.sandbox_tiled = sandbox_tiled
        self.run = tiled_client[uid]
        
        self.raw_db = self.get('topics', 'raw_db', fallback='pdf')
        self.an_db = self.get('topics', 'an_db', fallback='pdf-analysis')

        self.full_uid = self.run.start['uid']

        self.sample_name = self.run.start['sample_name']  ## update at start doc
        self.dksub_uid = None   ## update at event doc
        self.stream_name = []  ## update at stop doc

        self.process_img = None


    @property
    def detector(self):
        return self.run.start['detectors'][0]
    

    @property
    def wavelength(self):  ## unit: angstrom
        return self.run.start['calibration_md']['Wavelength']*(10**10)
    

    @property
    def img_key(self):
        data_keys = list(self.run[self.stream_name[0]].read().keys())
        k = [key for key in data_keys if 'image' in key][0]
        return k
        # return f'{self.detector}_image'


    @property
    def stream_length(self):
        return len(self.stream_name)

    @property
    def user_data(self):
        fallback = '/nsls2/data/pdf/pdfhack/legacy/processed/xpdacq_data/user_data'
        return self.get('PATH', 'user_data', fallback=fallback)
    
    @property
    def tiff_base(self):
        n = self.get('PATH', 'tiff_base', fallback='tiff_base')
        return os.path.join(self.user_data, n)
    
    @property
    def config_base(self):
        n = self.get('PATH', 'config_base', fallback='config_base')
        return os.path.join(self.user_data, n)     

    @property
    def pilatus_PDF(self):
        n = self.get('PATH', 'pilatus_PDF', fallback='pilatus_PDF')
        return os.path.join(self.config_base, n)
    
    @property
    def pilatus_XRD(self):
        n = self.get('PATH', 'pilatus_XRD', fallback='pilatus_XRD')
        return os.path.join(self.config_base, n)
    

    @property
    def masks_pos_flist(self):
        m1 = self.get('PATH', 'mask_01', fallback='Mask_pos1_ext_BS.npy')
        m2 = self.get('PATH', 'mask_02', fallback='Mask_pos2_ext_BS.npy')
        m3 = self.get('PATH', 'mask_03', fallback='Mask_pos3_ext_BS.npy')
        return [m1, m2, m3]
    
    @property
    def osetx(self):
        return self.getint('SUM', 'osetx', fallback=27)
    
    @property
    def osety(self):
        return self.getint('SUM', 'osety', fallback=27)
    
    @property
    def num_positions(self):
        return self.getint('SUM', 'num_positions', fallback=3)
    
    @property
    def pixel_size(self):
        return self.getfloat('SUM', 'pixel_size', fallback=0.172)
    
    @property
    def detector_Xmotor(self):
        return self.get('SUM', 'detector_Xmotor', fallback='Grid_X')
    
    @property
    def detector_Ymotor(self):
        return self.get('SUM', 'detector_Ymotor', fallback='Grid_Y')
    
    @property
    def use_flat_field_pila(self):
        return self.getboolean('SUM', 'use_flat_field_pila', fallback=False)
    
    @property
    def flat_field_pila(self):
        n_folder = self.get('PATH', 'flat_filed', fallback='flat_filed')
        n = self.get('PATH', 'flat_field_pila', fallback='flat_field_pila.tiff')
        return os.path.join(self.config_base, n_folder, n)
    
    @property
    def use_flat_field_pe1c(self):
        return self.getboolean('SUM', 'use_flat_field_pe1c', fallback=False)
    
    @property
    def flat_field_pe1c(self):
        n_folder = self.get('PATH', 'flat_filed', fallback='flat_filed')
        n = self.get('PATH', 'flat_field_pe1c', fallback='flat_field_pe1c.tiff')
        return os.path.join(self.config_base, n_folder, n)

    @property
    def use_flat_field_pe2c(self):
        return self.getboolean('SUM', 'use_flat_field_pe2c', fallback=False)

    @property
    def flat_field_pe2c(self):
        n_folder = self.get('PATH', 'flat_filed', fallback='flat_filed')
        n = self.get('PATH', 'flat_field_pe2c', fallback='flat_field_pe2c.tiff')
        return os.path.join(self.config_base, n_folder, n)
    
    @property
    def use_flat_field_lambda(self):
        return self.getboolean('SUM', 'use_flat_field_lambda', fallback=False)

    @property
    def flat_field_lambda(self):
        n_folder = self.get('PATH', 'flat_filed', fallback='flat_filed')
        n = self.get('PATH', 'flat_field_lambda', fallback='flat_field_lambda.tiff')
        return os.path.join(self.config_base, n_folder, n)

    @property
    def use_flat_field(self):
        is_use = [self.use_flat_field_pe1c, 
                  self.use_flat_field_pe2c, 
                  self.use_flat_field_pila, 
                  self.use_flat_field_lambda, 
                  ]
        return any(is_use)
    
    @property
    def T_controller(self):
        return self.get('TEMPERATURE', 'temp_controller', fallback='No_temp_controller')
    
    @property
    def temperature(self):
        try:
            # temp_controller = self.get('TEMPERATURE', 'temp_controller', fallback='No_temp_controller')
            T = float(self.run.start['more_info'][self.T_controller])

        except (KeyError, IndexError, TypeError):
            T = 'None'

        return T

    @property
    def T_unit(self):
        if 'cryo' in self.T_controller:
            return 'K'
        else:
            return 'C'

    @property
    def readable_time(self):
        t = _readable_time(self.run.start['time'])
        return f'{t[0]}-{t[1]}'
    
    @property
    def file_name_prefix(self):
        T = self.temperature

        if type(T) is float:
            return f'{self.sample_name}_{self.readable_time}_{self.full_uid:6.6}_{T:.0f}_{self.T_unit}'

        else:
            return f'{self.sample_name}_{self.readable_time}_{self.full_uid:6.6}'


    @property
    def data_dir(self):
        return os.path.join(self.tiff_base, self.sample_name)


    @property
    def process_det_dir(self):
        if 'pilatus' in self.detector:
            return os.path.join(self.data_dir, f'{self.detector}')

        elif 'pe1' in self.detector:
            return os.path.join(self.data_dir, f'{self.detector}')

        elif 'pe2' in self.detector:
            return os.path.join(self.data_dir, f'{self.detector}')

        elif 'lambda' in self.detector:
            return os.path.join(self.data_dir, f'{self.detector}')

        else:
            return os.path.join(self.data_dir, 'unkown_det')

    

    def process_sub_dir(self, sub_name:str):
        sub_dir = os.path.join(self.process_det_dir, sub_name)
        # Create process_sub_dir directory if it doesn't exis
        os.makedirs(sub_dir, exist_ok=True)
        return sub_dir


    def output_data_path(self, sub_name:str ='img', file_type:str ='tiff'):
        if self.use_flat_field:
            fn = os.path.join(self.process_sub_dir(sub_name), 
                              f'{self.file_name_prefix}_flat.{file_type}')
            
        else:
            if self.stream_length==self.num_positions:
                fn = os.path.join(self.process_sub_dir(sub_name), 
                                  f'{self.file_name_prefix}_sum.{file_type}')
            else:
                fn = os.path.join(self.process_sub_dir(sub_name), 
                                  f'{self.file_name_prefix}_sub.{file_type}')
                
        return fn


    @property
    def PDF_limit(self):
        return self.getfloat('SUM', 'PDF_limit', fallback=0.6)


    @property
    def SAXS_limit(self):
        return self.getfloat('SUM', 'SAXS_limit', fallback=2.5)


    @property
    def acq_mode(self):
        try:
            distance = self.run.start['calibration_md']['Distance']
            acq_mode = ''

            if distance < self.PDF_limit:
                acq_mode = 'PDF'

            elif (distance > self.PDF_limit) and (distance < self.SAXS_limit):
                acq_mode = 'XRD'

            elif distance > self.SAXS_limit:
                acq_mode = 'SAXS'

            else:
                acq_mode = 'Unknown'

        except KeyError:
            print('\nCannot find distance in metadata in start doc\n')
            acq_mode = 'NoDistance'

        return acq_mode
    


    def sum_pilatus2(self):
        """ Sum the images accroding to relative detector postions"""

        if self.acq_mode == 'PDF':
            mask_dir = self.pilatus_PDF

        elif self.acq_mode == 'XRD':
            mask_dir = self.pilatus_XRD

        else:
            mask_dir = self.pilatus_PDF

        my_im1 = np.float32(getattr(self.run, self.stream_name[0]).read()[self.img_key].to_numpy()[0][0])
        x_size = my_im1.shape[0]  ## pixels
        y_size = my_im1.shape[1]  ## pixels
        my_im  = np.zeros([x_size, y_size, self.num_positions])

        user_mask = np.zeros([x_size, y_size, self.num_positions])

        ## Read image data, motor positions, and masks into np arrays
        for i in range(self.num_positions):
            ## Read detector motor positions into pos_x, pos_y
            x = self.run[self.stream_name[i]].read()[self.detector_Xmotor[0]].to_numpy()[0]
            y = self.run[self.stream_name[i]].read()[self.detector_Ymotor[1]].to_numpy()[0]
            
            ## Image xy and motor xy are reversed since python is row first which in image is y.
            pos_x.append(float(y))
            pos_y.append(float(x))
            
            ## Read different position images into zeros array
            img =  np.float32(self.run[self.stream_name[i]].read()[self.img_key].to_numpy()[0][0])
            my_im[:,:,i] = img
            
            ## Apply flat field if True
            if self.use_flat_field_pila:
                flat_field = tifffile.imread(self.flat_field_pila)
                my_im[:,:,i] = img / flat_field

            ## Read mask file into zeros array
            m_path = os.path.join(mask_dir, self.masks_pos_flist[i])
            mask = np.load(m_path)
            user_mask[:,:,i] = mask

        pos_x = np.round(pos_x, decimals=3)  ## mm
        pos_y = np.round(pos_y, decimals=3)  ## mm

        ## sort order according to the detector x position
        sort_idx = np.argsort(pos_x)
        sort_pos_x = pos_x[sort_idx]
        sort_pos_y = pos_y[sort_idx]
        sort_my_im = my_im[:,:,sort_idx]
        sort_user_mask = user_mask[:,:,sort_idx]

        ## Calculate the total offset pixel numbers in x, y
        osetx_total = abs(round((sort_pos_x[-1]-sort_pos_x[0])/self.pixel_size))  ## pixels
        osety_total = abs(round((sort_pos_y[-1]-sort_pos_y[0])/self.pixel_size))  ## pixels

        ## Find the center positions of x, y
        center_x = (sort_pos_x[0]+sort_pos_x[-1])/2  ## mm
        center_y = (sort_pos_y[0]+sort_pos_y[-1])/2  ## mm

        ## Define an empty array for stitch image
        my_imsum = np.ones((x_size+osetx_total, y_size+osety_total, self.num_positions))*np.nan
        x_sum_size = my_imsum.shape[0] ## pixels
        y_sum_size = my_imsum.shape[1] ## pixels

        ## Find the center pixel values of stitch image
        x_sum_center = round((x_sum_size+1)/2)  ## pixel
        y_sum_center = round((y_sum_size+1)/2)  ## pixel

        ## Stitch images according to the motor positions and relative offsets
        for i in range(self.num_positions):
            
            ## Find the x, y offset from center in pixel values for each motor position
            x_offset = round((sort_pos_x[i] - center_x)/self.pixel_size)  ## pixels
            y_offset = round((sort_pos_y[i] - center_y)/self.pixel_size)  ## pixels

            ## Define the broadcast range for x
            start_x = int(x_sum_center - x_size/2) + x_offset  ## pixel
            end_x = int(x_sum_center + x_size/2) + x_offset    ## pixel

            ## Define the broadcast range for y
            start_y = int(y_sum_center - y_size/2) + y_offset  ## pixel
            end_y = int(y_sum_center + y_size/2) + y_offset    ## pixel

            my_imsum[start_x:end_x, start_y:end_y, i] = sort_my_im[:,:,i]
            my_imsum[start_x:end_x, start_y:end_y, i][sort_user_mask[:,:,i]==1] = np.nan

        return np.nanmean(my_imsum, axis=2, dtype=np.float32)
        


    def sub_dk_img(self):

        raw_img = np.float32(getattr(self.run, self.stream_name[0]).read()[self.img_key].to_numpy()[0][0])

        try:
            dk_uid = self.run.start['sc_dk_field_uid']
            dk_run = self.tiled_client[dk_uid]
            dk_img = np.float32(getattr(dk_run, 'primary').read()[self.img_key].to_numpy()[0][0])
            # dk_img = 0.0

            sub_img = raw_img-dk_img

        except KeyError:
            sub_img = raw_img
            print('\n******* No dark uid found. Export image without dark subtraction. *******\n')

        return sub_img



    def save_processed_img(self):

        if self.stream_length==self.num_positions:
            self.process_img = self.sum_pilatus2()

        else:
            if 'pe' in self.detector:
                self.process_img = self.sub_dk_img()

            else:
                self.process_img = np.float32(getattr(self.run, self.stream_name[0]).read()[self.img_key].to_numpy()[0][0])
        
        tiff_fn = self.output_data_path(sub_name='img', file_type='tiff')
        tifffile.imwrite(tiff_fn, self.process_img)
        print(f'\n*** {os.path.basename(tiff_fn)} saved!! ***\n')

        # return self.process_img


    
    def start_process(self, doc: dict):
        message = doc
        if 'dark' in message['sp_plan_name']:
                print(f"\n***** This is a DARK scan skip process data. *****\n")
                return False
        else:
            return True
        

    # def __call__(self, doc: dict, *args, **kwds):
    #     name, message = doc

    #     if (name == 'start') and self.start_process(doc):
    #         print(
    #             "\n*********************************************************\n"
    #             f"\n\n{datetime.datetime.now().isoformat()} documents {name}\n"
    #             f"document keys: {list(message.keys())}\n"
    #             f"\n{message['uid'] = }\n")
                  
    #         print(f"\nThis is a data scan not dark scan. Start to process data.\n")

    #         uid = message['uid']
    #         meta = tiled_client[uid].start

    #         print(f"\n{meta['calibration_md']['Distance'] = }\n")




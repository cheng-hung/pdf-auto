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

    def __init__(self, uid, tiled_client, sandbox_tiled, config_fn, **kwargs):
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
    def wavelength(self):
        return self.run.start['calibration_md']['Wavelength']*(10**10)
    

    @property
    def img_key(self):
        data_keys = list(self.run[self.stream_name[0]].read().keys())
        k = [key for key in data_keys if 'image' in key][0]
        return k
        # return f'{self.detector}_image'


    # @property
    # def stream_length(self):
    #     return len(self.stream_name)

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
    def use_flat_field_pe2c(self):
        return self.getboolean('SUM', 'use_flat_field_pe2c', fallback=False)

    @property
    def flat_field_pe1c(self):
        n_folder = self.get('PATH', 'flat_filed', fallback='flat_filed')
        n = self.get('PATH', 'flat_field_pe1c', fallback='flat_field_pe1c.tiff')
        return os.path.join(self.config_base, n_folder, n)
    
    @property
    def flat_field_pe2c(self):
        n_folder = self.get('PATH', 'flat_filed', fallback='flat_filed')
        n = self.get('PATH', 'flat_field_pe2c', fallback='flat_field_pe2c.tiff')
        return os.path.join(self.config_base, n_folder, n)
    
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
        

    @property
    def process_img_dir(self):
        return os.path.join(self.process_det_dir, 'img')
    

    @property
    def process_iq_dir(self):
        return os.path.join(self.process_det_dir, 'iq')


    @property
    def process_tth_dir(self):
        return os.path.join(self.process_det_dir, 'tth')
    

    # @property
    # def process_sq_dir(self):
    #     return os.path.join(self.process_det_dir, 'sq')
    

    # @property
    # def process_fq_dir(self):
    #     return os.path.join(self.process_det_dir, 'fq')
    

    # @property
    # def process_gr_dir(self):
    #     return os.path.join(self.process_det_dir, 'gr')



    def acq_mode(self, PDF_limit=0.6, SAXS_limit=2.5, ):

        try:
            distance = self.run.start['calibration_md']['Distance']
            acq_mode = ''

            if distance < PDF_limit:
                acq_mode = 'PDF'

            elif (distance > PDF_limit) and (distance < SAXS_limit):
                acq_mode = 'XRD'

            elif distance > SAXS_limit:
                acq_mode = 'SAXS'

            else:
                acq_mode = 'Unknown'

        except KeyError:
            print('\nCannot find distance in metadata in start doc\n')
            acq_mode = 'NoDistance'

        return acq_mode


    def sum_pilatus(self):
        """ Assuming im2 offset by -osetx, -osety, and im3 offset by +osetx, +osety """
        
        # run = tiled_client[uid]
        my_im1 = np.float32(getattr(self.run, self.stream_name[0]).read()[self.img_key].to_numpy()[0][0])
        my_im2 = np.float32(getattr(self.run, self.stream_name[1]).read()[self.img_key].to_numpy()[0][0])
        my_im3 = np.float32(getattr(self.run, self.stream_name[2]).read()[self.img_key].to_numpy()[0][0])

        if self.use_flat_field_pila:
            flat_field = tifffile.imread(self.flat_field_pila)
            my_im3 = my_im3 / flat_field
            my_im2 = my_im2 / flat_field
            my_im1 = my_im1 / flat_field

        if self.acq_mode() == 'PDF':
            mask_dir = self.pilatus_PDF

        elif self.acq_mode() == 'XRD':
            mask_dir = self.pilatus_XRD

        else:
            mask_dir = self.pilatus_PDF

        # masks_pos_fn = ['Mask_pos1_ext_BS.npy', 'Mask_pos2_ext_BS.npy', 'Mask_pos3_ext_BS.npy']
        m1_path = os.path.join(mask_dir, self.masks_pos_flist[0])
        m2_path = os.path.join(mask_dir, self.masks_pos_flist[1])
        m3_path = os.path.join(mask_dir, self.masks_pos_flist[2])
        use_mask_1= np.load(m1_path)  # This is mask we are applying befor mergin images
        use_mask_2 = np.load(m2_path) # This is mask we are applying befor mergin images
        use_mask_3 = np.load(m3_path) # This is mask we are applying befor mergin images

        my_imsum = np.ones((my_im1.shape[0]+int(2*self.osetx), my_im2.shape[1]+int(2*self.osety),3))*np.nan

        my_imsum[self.osetx:-self.osetx,self.osety:-self.osety,0] = my_im3
        my_imsum[self.osetx:-self.osetx,self.osety:-self.osety,0][use_mask_3==1] = np.nan  ##order of mask updated by CHL on 2025/11/03

        my_imsum[:-int(2*self.osetx),:-int(2*self.osety):,1] = my_im2
        my_imsum[:-int(2*self.osetx),:-int(2*self.osety):,1][use_mask_2==1] = np.nan

        my_imsum[int(2*self.osetx):,int(2*self.osety):,2] = my_im1
        my_imsum[int(2*self.osetx):,int(2*self.osety):,2][use_mask_1==1] = np.nan  ##order of mask updated by CHL on 2025/11/03

        # ## Stitching sequence for SAXS setup with lambda
        # my_imsum[self.osetx:-self.osetx,self.osety:-self.osety,0] = my_im2
        # my_imsum[self.osetx:-self.osetx,self.osety:-self.osety,0][use_mask_2==1] = np.nan  ##order of mask updated by CHL on 2025/11/03

        # my_imsum[int(2*self.osetx):,:-int(2*self.osety),1] = my_im3
        # my_imsum[int(2*self.osetx):,:-int(2*self.osety),1][use_mask_3==1] = np.nan

        # my_imsum[:-int(2*self.osetx),int(2*self.osety):,2] = my_im1
        # my_imsum[:-int(2*self.osetx),int(2*self.osety):,2][use_mask_1==1] = np.nan  ##order of mask updated by CHL on 2025/11        return np.nanmean(my_imsum, axis=2, dtype=np.float32)

        return np.nanmean(my_imsum, axis=2, dtype=np.float32)


    def sum_pilatus2(self):
        """ Sum the images accroding to relative detector postions"""

        if self.acq_mode() == 'PDF':
            mask_dir = self.pilatus_PDF

        elif self.acq_mode() == 'XRD':
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


    def save_img_pilatus(self):

        # self.process_img = self.sum_pilatus()
        self.process_img = self.sum_pilatus2()
        
        os.makedirs(self.process_img_dir, exist_ok=True)  # Create process_img_dir directory if it doesn't exis

        tiff_fn = os.path.join(self.process_img_dir, f'{self.file_name_prefix}_sum.tiff')
        tifffile.imwrite(tiff_fn, self.process_img)
        print(f'\n*** {os.path.basename(tiff_fn)} saved!! ***\n')

        return self.process_img
    


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


    def save_img_perkin(self):

        # self.process_img = self.sandbox_tiled[self.dksub_uid].read()
        
        ## After data security, data transfer of pdfstream is done by 0MQ not Kafka 
        self.process_img = self.sub_dk_img()

        if self.use_flat_field_pe1c or self.use_flat_field_pe2c:
            if 'pe1' in self.detector:
                flat_field = tifffile.imread(self.flat_field_pe1c)
            elif 'pe2' in self.detector:
                flat_field = tifffile.imread(self.flat_field_pe2c)
            else:
                flat_field = tifffile.imread(self.flat_field_pe1c)

            self.process_img = self.process_img / flat_field

        os.makedirs(self.process_img_dir, exist_ok=True)  # Create process_img_dir directory if it doesn't exis
        
        if (self.use_flat_field_pe1c) and ('pe1' in self.detector):
            tiff_fn = os.path.join(self.process_img_dir, f'{self.file_name_prefix}_flat.tiff')
        
        elif (self.use_flat_field_pe2c) and ('pe2' in self.detector):
            tiff_fn = os.path.join(self.process_img_dir, f'{self.file_name_prefix}_flat.tiff')
        
        else:
            tiff_fn = os.path.join(self.process_img_dir, f'{self.file_name_prefix}_sub.tiff')
        
        tifffile.imwrite(tiff_fn, self.process_img)
        print(f'\n*** {os.path.basename(tiff_fn)} saved!! ***\n')

        return self.process_img



    def save_single_pilatus(self):

        self.process_img = np.float32(getattr(self.run, self.stream_name[0]).read()[self.img_key].to_numpy()[0][0])


        # # self.process_img = self.sandbox_tiled[self.dksub_uid].read()
        
        # ## After data security, data transfer of pdfstream is done by 0MQ not Kafka 
        # self.process_img = self.sub_dk_img()

        if self.use_flat_field_pe1c or self.use_flat_field_pe2c:
            if 'pe1' in self.detector:
                flat_field = tifffile.imread(self.flat_field_pe1c)
            elif 'pe2' in self.detector:
                flat_field = tifffile.imread(self.flat_field_pe2c)
            else:
                flat_field = tifffile.imread(self.flat_field_pe1c)

            self.process_img = self.process_img / flat_field

        os.makedirs(self.process_img_dir, exist_ok=True)  # Create process_img_dir directory if it doesn't exis
        
        if (self.use_flat_field_pe1c) and ('pe1' in self.detector):
            tiff_fn = os.path.join(self.process_img_dir, f'{self.file_name_prefix}_flat.tiff')
        
        elif (self.use_flat_field_pe2c) and ('pe2' in self.detector):
            tiff_fn = os.path.join(self.process_img_dir, f'{self.file_name_prefix}_flat.tiff')
        
        else:
            tiff_fn = os.path.join(self.process_img_dir, f'{self.file_name_prefix}_sub.tiff')
        
        tifffile.imwrite(tiff_fn, self.process_img)
        print(f'\n*** {os.path.basename(tiff_fn)} saved!! ***\n')

        return self.process_img
    

    def start_process(self, doc: dict):
        name, message = doc
        if 'dark' in message['sp_plan_name']:
                print(f"\n***** This is a DARK scan skip process data. *****\n")
                return False
        else:
            return True
        

    def __call__(self, doc: dict, *args, **kwds):
        name, message = doc

        if (name == 'start') and self.start_process(doc):
            print(
                "\n*********************************************************\n"
                f"\n\n{datetime.datetime.now().isoformat()} documents {name}\n"
                f"document keys: {list(message.keys())}\n"
                f"\n{message['uid'] = }\n")
                  
            print(f"\nThis is a data scan not dark scan. Start to process data.\n")

            uid = message['uid']
            meta = tiled_client[uid].start

            print(f"\n{meta['calibration_md']['Distance'] = }\n")




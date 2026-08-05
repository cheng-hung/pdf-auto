import datetime
import pprint
import uuid
# from bluesky_kafka import RemoteDispatcher
from bluesky_kafka.consume import BasicConsumer
from bluesky.callbacks.zmq import Publisher, RemoteDispatcher
from event_model import RunRouter
import matplotlib.pyplot as plt
import numpy as np
from tiled.client import from_profile, from_uri
import time
from pdfstream.vend.qt_kicker import install_qt_kicker


import importlib
img_getpdf = importlib.import_module("img_getpdf")
img_plotter = importlib.import_module("img_plotter")
server_log = importlib.import_module("utility").server_log
# bin_ndarray = importlib.import_module("utility").bin_ndarray

"--------------------------USER INPUTS------------------------------"
ini_config = '/home/xf28id1/src/pdf-auto/pilatus_zmq_config.ini'
# tiled_writing_client = from_uri('https://tiled.nsls2.bnl.gov', api_key=os.getenv("TILED_BLUESKY_WRITING_API_KEY_PDF", ""))["pdf"]["migration"]
# tiled_client = from_profile('pdf')
# sandbox_tiled = from_uri("https://tiled.nsls2.bnl.gov/api/v1/metadata/xpd/sandbox")
# factory_log = server_log()

"--------------DO NOT TOUCH BELOW!! Unless CHLin said OK!-----------"

try:
    from nslsii import _read_bluesky_kafka_config_file  # nslsii <0.7.0
except (ImportError, AttributeError):
    from nslsii.kafka_utils import _read_bluesky_kafka_config_file  # nslsii >=0.7.0

# these two lines allow a stale plot to remain interactive and prevent
# the current plot from stealing focus.  thanks to Tom:
# https://nsls2.slack.com/archives/C02D9V72QH1/p1674589090772499
plt.ion()
plt.rcParams["figure.raise_window"] = False



class plugin0_factory():

    def __init__(self, beamline_acronym:str, ini_config:str):
        # self.tiled_client = from_uri('https://tiled.nsls2.bnl.gov')[beamline_acronym]["migration"]
        self.tiled_client = from_profile(beamline_acronym)
        self.ini_config = ini_config
        self.img_analyzer = None 
        self.factory_log = server_log()

    
    # def __call__(self, name:str, doc:dict):
    #     message = doc
    def __call__(self, consumer, doctype, doc):
        name, message = doc

        # print(
        #     f"\n{datetime.datetime.now().isoformat()} document: {name}\n"
        #     f"\ndocument keys: {list(message.keys())}\n"
        #     # f"\ncontents: {pprint.pformat(message)}\n"
        # )

        try:
            # start_process = ('pe' in message['detectors'][0]) or ('pilatus' in message['detectors'][0])
            if 'dark' in message['sp_plan_name']:
                print(f"\n***** This is a DARK scan skip process data. *****\n")
                start_process = False
            
            elif 'original_run_uid' in message.keys():
                print(f"\n***** This is a analysis scan already processed by PDFstream. *****\n")
                start_process = False
                self.factory_log.do_process = False

            else:
                start_process = True
        
        except KeyError:
            start_process = False
        
        if (name == 'start') and start_process:
            print(
                "\n*********************************************************\n"
                f"\n\n{datetime.datetime.now().isoformat()} documents {name}\n"
                f"document keys: {list(message.keys())}\n"
                f"\n{message['uid'] = }\n")
                  
            print(f"\nThis is a data scan not dark scan. Start to process data.\n")

            uid = message['uid']
            meta = self.tiled_client[uid].start

            print(f"\n{meta['calibration_md']['Distance'] = }\n")

            # global img_analyzer
            self.img_analyzer = img_getpdf.img_getpdf(uid, self.tiled_client, self.ini_config)
            
            try:
                print(f"\n{message['sc_dk_field_uid'] = }\n")
            except KeyError:
                print(f"\nNo dark uid found. Using detector {message['detectors'][0]}.\n")


            print(f'\n{self.img_analyzer.acq_mode = }\n')
            
            ## a reminder to start data processing
            self.factory_log.do_process = True
            print(f'\n{self.factory_log.do_process = }\n')
        

        if (name == 'stop') and (self.factory_log.do_process):
            print(
                "\n*********************************************************\n"
                f"\n{datetime.datetime.now().isoformat()} documents {name}\n"
                f"\ndocument keys: {list(message.keys())}\n"
                f"\ncontents: {pprint.pformat(message['num_events'])}\n"
                )

            stream_name = list(message['num_events'].keys())
            self.img_analyzer.stream_name = stream_name
            print(f'\n{stream_name = }\n')

            ## Start plotter for visualization
            plotter = img_plotter.img_plotter(self.img_analyzer.sample_name, color_str=self.factory_log.color_str)

            ## Process image: stitchung or dark subtraction
            time.sleep(1) ## wait for data saved into data broker
            # print(f"\nStart to process {self.img_analyzer.run.start['sp_detector']} data: uid = {self.img_analyzer.uid}\n")
            print(f"\nStart to process {self.img_analyzer.run.start['detectors'][0]} data: uid = {self.img_analyzer.uid}\n")
            self.img_analyzer.save_processed_img()
            poni_name, mask_name = self.img_analyzer.poni_mask_fn
            print(f'\nApply {mask_name = }\n')

            ## Plot unmasked 2D image rings with histogram
            tiff3_tuner = plotter.plot_tiff3(self.img_analyzer.process_img, self.img_analyzer.mask_array, use_mask=False, histogram=True)
            tiff3_tuner()

            ## pyFai integration: 2D to 1Dcolor_str
            print(f"\nStart to do 2D integration: uid = {self.img_analyzer.uid}\n")
            iq_df, iq_fn, unrolled_array = self.img_analyzer.pct_integration()
            # img_tuner4 = plotter.plot_tiff4(unrolled_array, iq_df.iloc[:,0])
            
            ## Plot masked 2D image rings with iq data
            maskImg_iq_tuner = plotter.plot_maskImg_iq(self.img_analyzer.process_img,  
                                                        self.img_analyzer.mask_array, 
                                                        unrolled_array, 
                                                        iq_fn,
                                                        poni_name, 
                                                        binning=2, 
                                                        )
            maskImg_iq_tuner()

            ## Plot masked and unrolled image cake
            # tiff4_tuner4 = plotter.plot_tiff4(unrolled_array, None, binned=True)
            # tiff4_tuner4()

            ## Data reduction: I(Q) to G(r)
            if (self.img_analyzer.do_reduction) and (self.img_analyzer.acq_mode=='PDF'):
            # if img_analyzer.acq_mode=='PDF':
                print(f"\nStart to reduce sq, fq, gr: uid = {self.img_analyzer.uid}\n")
                # iq_array = iq_df.to_numpy().T
                sqfqgr_path = self.img_analyzer.get_gr(iq_df)
                bkg_scale = self.img_analyzer.pdfconfig().bgscale[0]
                bkg_fn = self.img_analyzer.pdfconfig_dict['backgroundfile']
                plotter.plot_sqfqgr(sqfqgr_path, bkg_scale, bkg_fn)
            
            else:
                plotter.clear_sqfqgr()
                print('This is an XRD scan. Skip gr transformation.')


            self.factory_log.colo_str = plotter.color_str
            
            # a reminder to finish data processing
            self.factory_log.do_process = False
            print(f'\n{self.factory_log.do_process = }\n')
            print('\n########### Events printing division ############\n')

        # return [], []



class plugin0_Router(RunRouter):
    """A router that contains the callbacks for the xpd data reduction."""

    def __init__(self, beamline_acronym:str, ini_config:str):
        factory = plugin0_factory(beamline_acronym, ini_config)
        super().__init__([factory])
        #     handler_registry=databroker.mongo_normalized.discover_handlers()
        # )




def plug0_server(beamline_acronym, ini_config=ini_config,):
    
    # factory = plugin0_factory(beamline_acronym, ini_config)
    # router = plugin0_Router(beamline_acronym, ini_config)
    def print_message(name, doc):
        message = doc
        print(
            f"\n{datetime.datetime.now().isoformat()} document: {name}\n"
            f"\ndocument keys: {list(message.keys())}\n"
            f"\ncontents: {pprint.pformat(message)}\n"
        )

        # fig, ax = plt.subplots()
        # x = np.arange(-10, 10, 0.1)
        # y = np.sin(x)
        # ax.plot(x,y)
        # fig.canvas.manager.show()
        # fig.canvas.flush_events()
    
    rd = RemoteDispatcher("ipc:///var/lib/bluesky-zmq-proxy/pdf-ipc-in-ipc-out/out.sock")
    install_qt_kicker(rd.loop)
    rd.subscribe(print_message)
    print('\n\n Subscribe to RemoteDispatcher and start the server \n\n')
    rd.start()


def plug0_kafka(beamline_acronym, ini_config=ini_config,):

    factory = plugin0_factory(beamline_acronym, ini_config)

    # def print_message(consumer, doctype, doc):
    #     name, message = doc
    #     print(
    #         f"\n{datetime.datetime.now().isoformat()} document: {name}\n"
    #         f"\ndocument keys: {list(message.keys())}\n"
    #         f"\ncontents: {pprint.pformat(message)}\n"
    #     )


    kafka_config = _read_bluesky_kafka_config_file(config_file_path="/etc/bluesky/kafka.yml")

    # this consumer should not be in a group with other consumers
    #   so generate a unique consumer group id for it
    unique_group_id = f"echo-{beamline_acronym}-{str(uuid.uuid4())[:8]}"

    kafka_consumer = BasicConsumer(
        topics=[f"{beamline_acronym}.bluesky.runengine.documents", 
                # f"{beamline_acronym_02}.bluesky.runengine.documents", 
                ],
        bootstrap_servers=kafka_config["bootstrap_servers"],
        group_id=unique_group_id,
        consumer_config=kafka_config["runengine_producer_config"],
        process_message = factory,
    )

    print('\n\n Subscribe to Kafka Consumer and start the server \n\n')

    try:
        kafka_consumer.start_polling(work_during_wait=lambda : plt.pause(.01))
    except KeyboardInterrupt:
        print('\nExiting Kafka consumer')
        return()

if __name__ == "__main__":
    import sys
    # print_kafka_messages(sys.argv[1], sys.argv[2])
    # plug0_server(sys.argv[1])
    plug0_kafka(sys.argv[1])

import datetime
import pprint
import time
import uuid

import matplotlib.pyplot as plt
from bluesky.callbacks.zmq import RemoteDispatcher
from bluesky_kafka.consume import BasicConsumer
from event_model import RunRouter
from pdfstream.vend.qt_kicker import install_qt_kicker
from tiled.client import from_profile

from . import plotting, reduction
from .config import DEFAULT_CONFIG_PATH
from .routing import is_dark_start, should_process_start
from .save_data import SaveData
from .utilities import ServerState

"--------------------------USER INPUTS------------------------------"
ini_config = str(DEFAULT_CONFIG_PATH)
# tiled_writing_client = from_uri('https://tiled.nsls2.bnl.gov', api_key=os.getenv("TILED_BLUESKY_WRITING_API_KEY_PDF", ""))["pdf"]["migration"]
# tiled_client = from_profile('pdf')
# sandbox_tiled = from_uri("https://tiled.nsls2.bnl.gov/api/v1/metadata/xpd/sandbox")

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


class ProcessingFactory:
    def __init__(self, beamline_acronym: str, ini_config: str):
        # self.tiled_client = from_uri('https://tiled.nsls2.bnl.gov')[beamline_acronym]["migration"]
        self.tiled_client = from_profile(beamline_acronym)
        self.ini_config = ini_config
        self.img_analyzer = None
        self.factory_log = ServerState()

    # def __call__(self, name:str, doc:dict):
    #     message = doc
    def __call__(self, consumer, doctype, doc):
        name, message = doc

        # print(
        #     f"\n{datetime.datetime.now().isoformat()} document: {name}\n"
        #     f"\ndocument keys: {list(message.keys())}\n"
        #     # f"\ncontents: {pprint.pformat(message)}\n"
        # )

        start_process = should_process_start(message)
        if is_dark_start(message):
            print("\n***** This is a DARK scan skip process data. *****\n")
        elif "original_run_uid" in message:
            print(
                "\n***** This is a analysis scan already processed by PDFstream. *****\n"
            )
            self.factory_log.do_process = False

        if (name == "start") and start_process:
            print(
                "\n*********************************************************\n"
                f"\n\n{datetime.datetime.now().isoformat()} documents {name}\n"
                f"document keys: {list(message.keys())}\n"
                f"\n{message['uid'] = }\n"
            )

            print("\nThis is a data scan not dark scan. Start to process data.\n")

            uid = message["uid"]
            meta = self.tiled_client[uid].start

            print(f"\n{meta['calibration_md']['Distance'] = }\n")

            # global img_analyzer
            self.img_analyzer = reduction.PDFReducer(
                uid, self.tiled_client, self.ini_config
            )

            try:
                print(f"\n{message['sc_dk_field_uid'] = }\n")
            except KeyError:
                print(
                    f"\nNo dark uid found. Using detector {message['detectors'][0]}.\n"
                )

            print(f"\n{self.img_analyzer.acq_mode = }\n")

            ## a reminder to start data processing
            self.factory_log.do_process = True
            print(f"\n{self.factory_log.do_process = }\n")

        if (name == "stop") and (self.factory_log.do_process):
            print(
                "\n*********************************************************\n"
                f"\n{datetime.datetime.now().isoformat()} documents {name}\n"
                f"\ndocument keys: {list(message.keys())}\n"
                f"\ncontents: {pprint.pformat(message['num_events'])}\n"
            )

            stream_name = list(message["num_events"].keys())
            self.img_analyzer.stream_name = stream_name
            print(f"\n{stream_name = }\n")

            ## Start plotter for visualization
            plotter = plotting.ImagePlotter(
                self.img_analyzer.sample_name, color_str=self.factory_log.color_str
            )

            ## Process image: stitchung or dark subtraction
            time.sleep(1)  ## wait for data saved into data broker
            # print(f"\nStart to process {self.img_analyzer.run.start['sp_detector']} data: uid = {self.img_analyzer.uid}\n")
            print(
                f"\nStart to process {self.img_analyzer.run.start['detectors'][0]} data: uid = {self.img_analyzer.uid}\n"
            )
            # The reducer is now compute-only; file writing is delegated to
            # SaveData so the Kafka path stays consistent with the analysis
            # stream. Build the same reduced payload and hand it to SaveData.
            process_img, tiff_fn = self.img_analyzer.compute_processed_image()
            poni_name, mask_name = self.img_analyzer.poni_mask_fn
            print(f"\nApply {mask_name = }\n")

            ## Plot unmasked 2D image rings with histogram
            tiff3_tuner = plotter.plot_tiff3(
                self.img_analyzer.process_img,
                self.img_analyzer.mask_array,
                use_mask=False,
                histogram=True,
            )
            tiff3_tuner()

            ## pyFai integration: 2D to 1Dcolor_str
            print(f"\nStart to do 2D integration: uid = {self.img_analyzer.uid}\n")
            iq_df, tth_df, integration_md, iq_fn, tth_fn, unrolled_array = (
                self.img_analyzer.pct_integration()
            )

            reduced_data = {
                "img_file": tiff_fn,
                "image": process_img,
                "iq_file": iq_fn,
                "tth_file": tth_fn,
                "q": iq_df["q"].to_numpy(),
                "iq": iq_df["I"].to_numpy(),
                "tth": tth_df["tth"].to_numpy(),
                "integration_md": integration_md,
            }

            ## Plot masked 2D image rings with iq data
            maskImg_iq_tuner = plotter.plot_maskImg_iq(
                self.img_analyzer.process_img,
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
            is_pdf = self.img_analyzer.do_reduction and (
                self.img_analyzer.acq_mode == "PDF"
            )
            if is_pdf:
                print(f"\nStart to reduce sq, fq, gr: uid = {self.img_analyzer.uid}\n")
                pdf_arrays, pdf_dir, pdf_prefix = self.img_analyzer.get_gr(iq_df)
                reduced_data["pdf_arrays"] = pdf_arrays
                reduced_data["pdfgetter_dir"] = pdf_dir
                reduced_data["pdfgetter_prefix"] = pdf_prefix
                bkg_scale = self.img_analyzer.pdfconfig().bgscale[0]
                bkg_fn = self.img_analyzer.pdfconfig_dict["backgroundfile"]
            else:
                print("This is an XRD scan. Skip gr transformation.")

            # Write all products (tiff/iq/tth/sq/fq/gr) via SaveData, which
            # returns the written S(Q)/F(Q)/G(r) paths for plotting.
            sqfqgr_path = SaveData().save(reduced_data)

            if is_pdf:
                plotter.plot_sqfqgr(sqfqgr_path, bkg_scale, bkg_fn)
            else:
                plotter.clear_sqfqgr()

            self.factory_log.color_str = plotter.color_str

            # a reminder to finish data processing
            self.factory_log.do_process = False
            print(f"\n{self.factory_log.do_process = }\n")
            print("\n########### Events printing division ############\n")

        # return [], []


class ProcessingRouter(RunRouter):
    """A router that contains the callbacks for the xpd data reduction."""

    def __init__(self, beamline_acronym: str, ini_config: str):
        factory = ProcessingFactory(beamline_acronym, ini_config)
        super().__init__([factory])
        #     handler_registry=databroker.mongo_normalized.discover_handlers()
        # )


def run_zmq_server(
    beamline_acronym,
    ini_config=ini_config,
):

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

    rd = RemoteDispatcher(
        "ipc:///var/lib/bluesky-zmq-proxy/pdf-ipc-in-ipc-out/out.sock"
    )
    install_qt_kicker(rd.loop)
    rd.subscribe(print_message)
    print("\n\n Subscribe to RemoteDispatcher and start the server \n\n")
    rd.start()


def run_kafka_consumer(
    beamline_acronym,
    ini_config=ini_config,
):

    factory = ProcessingFactory(beamline_acronym, ini_config)

    # def print_message(consumer, doctype, doc):
    #     name, message = doc
    #     print(
    #         f"\n{datetime.datetime.now().isoformat()} document: {name}\n"
    #         f"\ndocument keys: {list(message.keys())}\n"
    #         f"\ncontents: {pprint.pformat(message)}\n"
    #     )

    kafka_config = _read_bluesky_kafka_config_file(
        config_file_path="/etc/bluesky/kafka.yml"
    )

    # this consumer should not be in a group with other consumers
    #   so generate a unique consumer group id for it
    unique_group_id = f"echo-{beamline_acronym}-{str(uuid.uuid4())[:8]}"

    kafka_consumer = BasicConsumer(
        topics=[
            f"{beamline_acronym}.bluesky.runengine.documents",
            # f"{beamline_acronym_02}.bluesky.runengine.documents",
        ],
        bootstrap_servers=kafka_config["bootstrap_servers"],
        group_id=unique_group_id,
        consumer_config=kafka_config["runengine_producer_config"],
        process_message=factory,
    )

    print("\n\n Subscribe to Kafka Consumer and start the server \n\n")

    try:
        kafka_consumer.start_polling(work_during_wait=lambda: plt.pause(0.01))
    except KeyboardInterrupt:
        print("\nExiting Kafka consumer")
        return ()


# Backward-compatible names used by the previous workstation scripts.
plugin0_factory = ProcessingFactory
plugin0_Router = ProcessingRouter
plug0_server = run_zmq_server
plug0_kafka = run_kafka_consumer

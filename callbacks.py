from bluesky.callbacks.zmq import RemoteDispatcher
from bluesky.callbacks.stream import LiveDispatcher
from event_model import RunRouter

import importlib
img_getpdf = importlib.import_module("img_getpdf")
img_plotter = importlib.import_module("img_plotter")
server_log = importlib.import_module("utility").server_log
bin_ndarray = importlib.import_module("utility").bin_ndarray

class auto_img_gr(LiveDispatcher):
    # def __init__(self, uid, beamline_acronym, ini_config, *args, **kwargs):
    #     self.img_analyzer = img_getpdf.img_getpdf(uid, beamline_acronym, ini_config)
    #     super().__init__(*args, **kwargs)

    def __init__(self, img_analyzer, *args, **kwargs):
        self.img_analyzer = img_analyzer   ## class of img_getpdf.img_getpdf
        super().__init__(*args, **kwargs)


    def start(self, doc, _md=None):
        super().start(doc)


    def descriptor(self, doc):
        super().descriptor(doc)


    def event(self, doc, _md=None):
        io.server_message("Start processing the event {}.".format(doc["seq_num"]))
        data = self.process_data(doc)
        io.server_message("Finish processing the event {}.".format(doc["seq_num"]))
        return self.process_event(dict(data=data, descriptor=doc["descriptor"]))
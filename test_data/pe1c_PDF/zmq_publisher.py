from tiled.client import from_profile
from bluesky.callbacks.zmq import Publisher


''' Address
pass-319561 [32]: glbl['inbound_proxy_address']
Out[32]: 'ipc:///var/lib/bluesky-zmq-proxy/pdf-tcp-in-ipc-out/out.sock'
'''

''' defined in 95-zmq.py
pub = Publisher(glbl['inbound_proxy_address'], prefix=b'raw')
xrun.subscribe(pub)
RE.subscribe(pub)
'''

tiled_client = from_profile('pdf')

# 2026-1/pass-320158/Arava_20260209_318056_226d11b5/tiff_base/CeO2_01_PDF
uid = '56424bc9-4f66-4f90-ad4b-d8a608abc98c'

run = tiled_client[uid]

for name, doc in run.documents():
    pub(name, dict(doc))
from bluesky_kafka import Publisher as kapub
from tiled.client import from_profile

p = kapub(topic=res[1].beamline_topic, bootstrap_servers=res[1].bootstrap_servers, 
            key ="test", producer_config=res[1].producer_config)

tiled_client = from_profile('pdf')

# uids = ['699593ad-c210-4c53-8df5-9b08ccb8e025',
#  '74288b93-4e5c-40bb-a8cd-a9b25f68efbf',
#  '38729429-64b4-4f61-a07d-bcd7a70aa845',
#  'f9258402-470a-42d8-8493-a357f96a0885']

uid = '56424bc9-4f66-4f90-ad4b-d8a608abc98c'

run = tiled_client[uid]

for name, doc in run.documents():
    p(name, doc)


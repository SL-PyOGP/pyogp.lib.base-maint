"""
@file regiondomain.py
@date 2008-09-16
Contributors can be viewed at:
http://svn.secondlife.com/svn/linden/projects/2008/pyogp/CONTRIBUTORS.txt 

$LicenseInfo:firstyear=2008&license=apachev2$

Copyright 2008, Linden Research, Inc.

Licensed under the Apache License, Version 2.0 (the "License").
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0
or in 
http://svn.secondlife.com/svn/linden/projects/2008/pyogp/LICENSE.txt

$/LicenseInfo$
"""

# std lib
from logging import getLogger, CRITICAL, ERROR, WARNING, INFO, DEBUG
import re
from urllib import quote
from urlparse import urlparse, urljoin
import time
import uuid
import os

# eventlet
import sys
lib_dir = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), '..', 'src/lib'))
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

#from eventlet import api, coros

try:
    from eventlet import api, coros
except ImportError:
    print "Error importing eventlet"
    sys.exit()

# related
from indra.base import llsd

# pyogp
from pyogp.lib.base.caps import Capability, SeedCapability
from pyogp.lib.base.network.stdlib_client import StdLibClient, HTTPError
import pyogp.lib.base.exc
from pyogp.lib.base.settings import Settings

# messaging
from pyogp.lib.base.message.udpdispatcher import UDPDispatcher
from pyogp.lib.base.message.message import Message, Block
from pyogp.lib.base.message.circuit import Host
from pyogp.lib.base.message.types import MsgType
from pyogp.lib.base.message.packets import *

# initialize logging
logger = getLogger('pyogp.lib.base.regiondomain')
log = logger.log

class Region(object):
    """models a region endpoint"""

    def __init__(self, uri=None, regionname=None):
        """initialize the region with the region uri"""
        
        if (uri != None): self.region_uri = self.parse_region_uri(uri)
        self.regionname = regionname
        self.seed_cap_url = ''
        self.seed_cap = None
        self.settings = Settings()

        # details is currently a catchall for things that need to be split out...
        self.details = {}

        self._isUDPRunning = False
        self._isEventQueueRunning = False

        self.capabilities = {}
        self.region_caps_list = ['ChatSessionRequest',
                            'CopyInventoryFromNotecard',
                            'DispatchRegionInfo',
                            'EstateChangeInfo',
                            'EventQueueGet',
                            'FetchInventory',
                            'WebFetchInventoryDescendents',
                            'FetchLib',
                            'FetchLibDescendents',
                            'GroupProposalBallot',
                            'HomeLocation',
                            'MapLayer',
                            'MapLayerGod',
                            'NewFileAgentInventory',
                            'ParcelPropertiesUpdate',
                            'ParcelVoiceInfoRequest',
                            'ProvisionVoiceAccountRequest',
                            'RemoteParcelRequest',
                            'RequestTextureDownload',
                            'SearchStatRequest',
                            'SearchStatTracking',
                            'SendPostcard',
                            'SendUserReport',
                            'SendUserReportWithScreenshot',
                            'ServerReleaseNotes',
                            'StartGroupProposal',
                            'UpdateAgentLanguage',
                            'UpdateGestureAgentInventory',
                            'UpdateNotecardAgentInventory',
                            'UpdateScriptAgent',
                            'UpdateGestureTaskInventory',
                            'UpdateNotecardTaskInventory',
                            'UpdateScriptTask',
                            'ViewerStartAuction',
                            'UntrustedSimulatorMessage',
                            'ViewerStats'
        ]

        #self.actor = None

        log(DEBUG, 'initializing region domain: %s' %self)

    def set_seed_cap_url(self, url):
    
        self.seed_cap_url = url
        self.seed_cap = RegionSeedCapability('seed_cap', self.seed_cap_url)

        log(DEBUG, 'setting region domain seed cap: %s' % (self.seed_cap_url))

    def parse_region_uri(self, uri):     
        """ parse a region uri and returns one formatted appropriately """
 
        region_uri = urljoin(uri, quote(urlparse(uri)[2]))

        # test if it is a lindenlab.com domain name
        '''
        if (re.search('lindenlab', urlparse(uri)[1])):
            if (re.search('lindenlab\.com/public_seed$', uri)):
                region_uri = uri
            else:
                region_uri = uri + '/public_seed'
        else:
            # this is a crappy test to see if it's already been urlencoded, it only checkes for spaces
            if re.search('%20', urlparse(uri)[2]):
                region_uri = uri
            else:
                region_uri = urljoin(uri, quote(urlparse(uri)[2]))
        '''

        return region_uri

    def get_region_public_seed(self,custom_headers={'Accept' : 'application/llsd+xml'}):
        """call this capability, return the parsed result"""

        log(DEBUG, 'Getting region public_seed %s' %(self.region_uri))

        try:
            restclient = StdLibClient()
            response = restclient.GET(self.region_uri, custom_headers)
        except HTTPError, e:
            if e.code==404:
                raise exc.ResourceNotFound(self.region_uri)
            else:
                raise exc.ResourceError(self.region_uri, e.code, e.msg, e.fp.read(), method="GET")

        data = llsd.parse(response.body)

        log(DEBUG, 'Get of cap %s response is: %s' % (self.region_uri, data))        

        return data

    def get_region_capabilities(self):
        """ queries the region seed cap for capabilities """

        if (self.seed_cap == None):
            raise exc.RegionSeedCapNotAvailable("querying for agent capabilities")
            return
        else:

            log(INFO, 'Getting caps from region seed cap %s' % (self.seed_cap))

            # use self.region_caps.keys() to pass a list to be parsed into LLSD            
            self.capabilities = self.seed_cap.get(self.region_caps_list)

    def connect(self):
        """ connect to the udp circuit code and event queue"""

        self.messenger = UDPDispatcher()
        self.host = None

        self.host = Host((self.details['sim_ip'],
                    self.details['sim_port']))

        self.init_agent_in_region()


        self.last_ping = 0
        #self.start = time.time()
        #self.now = self.start
        self.packets = {}

        log(DEBUG, 'Spawning region UDP connection')
        api.spawn(self._processUDP)

        log(DEBUG, 'Spawning region event queue connection')
        self.get_region_capabilities()
        api.spawn(self._processEventQueue) 

    def logout(self):
        """ send a logout packet """

        # this should move to a handled method

        msg = Message('LogoutRequest',
                  Block('AgentData', AgentID=uuid.UUID(self.details['agent_id']),
                        SessionID=uuid.UUID(self.details['session_id'])
                        )
                  )
        self.messenger.send_message(msg, self.host)

    def init_agent_in_region(self):
        """ send a few packets to set things up """
        
        packet = UseCircuitCodePacket()
        packet.CircuitCode['Code'] = self.details['circuit_code']
        packet.CircuitCode['SessionID'] = uuid.UUID(self.details['session_id'])    # MVT_LLUUID
        packet.CircuitCode['ID'] = uuid.UUID(self.details['agent_id'])    # MVT_LLUUID
        
        msg = Message('UseCircuitCode',
                      Block('CircuitCode', Code=self.details['circuit_code'],
                            SessionID=uuid.UUID(self.details['session_id']),
                            ID=uuid.UUID(self.details['agent_id'])))
        self.messenger.send_reliable(packet(), self.host, 0)

        time.sleep(1)

        #SENDS CompleteAgentMovement
        msg = Message('CompleteAgentMovement',
                      Block('AgentData', AgentID=uuid.UUID(self.details['agent_id']),
                            SessionID=uuid.UUID(self.details['session_id']),
                            CircuitCode=self.details['circuit_code']))
        self.messenger.send_reliable(msg, self.host, 0)

        #SENDS UUIDNameRequest
        msg = Message('UUIDNameRequest',
                      Block('UUIDNameBlock', ID=uuid.UUID(self.details['agent_id'])
                            )
                      )
        self.messenger.send_message(msg, self.host)

        msg = Message('AgentUpdate',
              Block('AgentData', AgentID=uuid.UUID(self.details['agent_id']),
                    SessionID=uuid.UUID(self.details['session_id']),
                    BodyRotation=(0.0,0.0,0.0,0.0),
                    HeadRotation=(0.0,0.0,0.0,0.0),
                    State=0x00,
                    CameraCenter=(0.0,0.0,0.0),
                    CameraAtAxis=(0.0,0.0,0.0),
                    CameraLeftAxis=(0.0,0.0,0.0),
                    CameraUpAxis=(0.0,0.0,0.0),
                    Far=0,
                    ControlFlags=0x00,
                    Flags=0x00))

        self.messenger.send_message(msg, self.host)

    def _processUDP(self):

        self._isUDPRunning = True

        while self._isUDPRunning:

            # free up resources for other stuff to happen
            api.sleep(0)

            msg_buf, msg_size = self.messenger.udp_client.receive_packet(self.messenger.socket)
            packet = self.messenger.receive_check(self.messenger.udp_client.get_sender(),
                                            msg_buf, msg_size)
            if packet != None:
                #print 'Received: ' + packet.name + ' from  ' + self.messenger.udp_client.sender.ip + ":" + \
                                                  #str(self.messenger.udp_client.sender.port)

                #MESSAGE HANDLERS
                if packet.name == 'RegionHandshake':
                    # ToDo: move these guys elsewhere
                    log(WARNING, "MOVE ME NOW")

                    #msg = Message('RegionHandshakeReply',
                      #[Block('AgentData', AgentID=uuid.UUID(self.details['agent_id']),
                            #SessionID=uuid.UUID(self.details['session_id'])),
                       #Block('RegionInfo', RegionInfo=0x00)])

                    packet = RegionHandshakeReplyPacket()
                    packet.AgentData['SessionID'] = uuid.UUID(self.details['session_id'])    # MVT_LLUUID
                    packet.AgentData['AgentID'] = uuid.UUID(self.details['agent_id']) 
                    packet.RegionInfo['Flags'] = 0x00

                    for i in range(0,10):
                        self.messenger.send_reliable(packet(), self.host, 0)

                elif packet.name == 'StartPingCheck':
                    log(WARNING, "MOVE ME NOW")
                    msg = Message('CompletePingCheck',
                      Block('PingID', PingID=self.last_ping))

                    self.messenger.send_message(msg, self.host)
                    self.last_ping += 1

                # ToDo: REMOVE ME: self.packets will jsut grow and grow, this is here for testing purposes
                #if packet.name not in self.packets:
                    #self.packets[packet.name] = 1
                #else: 
                    #self.packets[packet.name] += 1                   

            else:
                #print 'No message'
                pass

            #self.now = time.time()

            if self.messenger.has_unacked():
                #print 'Acking'
                self.messenger.process_acks()
                msg = Message('AgentUpdate',
                      Block('AgentData', AgentID=uuid.UUID(self.details['agent_id']),
                            SessionID=uuid.UUID(self.details['session_id']),
                            BodyRotation=(0.0,0.0,0.0,0.0),
                            HeadRotation=(0.0,0.0,0.0,0.0),
                            State=0x00,
                            CameraCenter=(0.0,0.0,0.0),
                            CameraAtAxis=(0.0,0.0,0.0),
                            CameraLeftAxis=(0.0,0.0,0.0),
                            CameraUpAxis=(0.0,0.0,0.0),
                            Far=0,
                            ControlFlags=0x00,
                            Flags=0x00))

                self.messenger.send_message(msg, self.host)

    def _processEventQueue(self):

        self._isEventQueueRunning = True

        self.last_id = -1
        
        if self.capabilities['EventQueueGet'] == None:
            raise exc.RegionCapNotAvailable('EventQueueGet')
            # well then get it...
        else:
            while self._isEventQueueRunning:

                # need to be able to pull data from a queue somewhere
                data = {}
                api.sleep(self.settings.region_event_queue_interval)

                if self.last_id != -1:
                    data = {'ack':self.last_id, 'done':True}

                # ToDo: this is blocking, we need to break this
                result = self.capabilities['EventQueueGet'].POST(data)

                if result != None: self.last_id = result['id']

                #log(DEBUG, 'region event queue cap called, returned id: %s' % (self.last_id))

                log(DEBUG, 'Region EventQueueGet result: %s' % (result))


class RegionSeedCapability(Capability):
    """ a seed capability which is able to retrieve other capabilities """

    def get(self, names=[]):
        """if this is a seed cap we can retrieve other caps here"""

        #log(INFO, 'requesting from the region domain the following caps: %s' % (names))

        payload = names
        parsed_result = self.POST(payload)  #['caps']
        log(INFO, 'Request for caps returned: %s' % (parsed_result.keys()))

        caps = {}
        for name in names:
            # TODO: some caps might be seed caps, how do we know? 
            if parsed_result.has_key(name):
                caps[name]=Capability(name, parsed_result[name])
            else:
                log(DEBUG, 'Requested capability \'%s\' is not available' %  (name))
            #log(INFO, 'got cap: %s' % (name))

        return caps
                     
    def __repr__(self):
        return "<RegionSeedCapability for %s>" % (self.public_url)

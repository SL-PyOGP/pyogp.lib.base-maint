"""
@file mockup_net.py
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

import socket
import random

from zope.interface import implements
from pyogp.lib.base.message.interfaces import IHost

from pyogp.lib.base.network.interfaces import IUDPClient

class MockupUDPServer(object):
    def __init__(self):
        self.rec_buffer = ''
        self.ip = 'MockupUDPServer'
        self.port = 80
    def receive_message(self, client, receive_buffer):
        #print 'SERVER receive'
        self.rec_buffer = receive_buffer

    def send_message(self, client, send_message):
        #print 'SERVER send'
        client.rec = send_message
        client.sender = IHost((self, self.port))
        
#returns true if packet was sent successfully
class MockupUDPClient(object):
    implements(IUDPClient)

    def __init__(self):
        self.rec = ''
        self.sender = None

    def get_sender(self):
        return self.sender
    
    def set_response(self, socket, response):
        self.rec[socket] = response

    def send_packet(self, sock, send_buffer, host):
        #host is a mockup server
        #print 'CLIENT send'
        host.ip.receive_message(self, send_buffer)
        return True
    
    def receive_packet(self, socket):
        #print 'CLIENT receive'
        data = self.rec
        self.rec = ''
        
        if len(data) > 0:
            return data, len(data)
        
        return '', 0

    def start_udp_connection(self):
        """ Starts a udp connection, returning socket and port. """
        sock = random.randint(0,80)
        return sock

# standard python libs
from logging import getLogger, CRITICAL, ERROR, WARNING, INFO, DEBUG
import time
import struct

# related
from indra.base import llsd
from eventlet import api

# pyogp
from pyogp.lib.base.exc import DataParsingError, DeserializationFailed

# initialize loggin
logger = getLogger('...utilities.helpers')
log = logger.log

class Helpers(object):
    """ contains useful helper functions """

    def bytes_to_hex(self, data):
        """ converts bytes to hex format """

        #from binascii import hexlify
        #return hex_string
        #hex_string = hexlify(data)
        return ''.join(["%02X " % ord(x) for x in data]).strip()

    def bytes_to_ascii(self, data):
        " converts bytes to ascii format "

        from binascii import b2a_uu

        ascii_string = b2a_uu(data)

        return ascii_string

    def hex_to_ascii(self, data):
        " converts bytes to ascii format "

        from binascii import unhexlify

        try:
            ascii_string = unhexlify(data)
        except TypeError, error:
            raise DataParsingError('hex_to_ascii failure: \'%s\': processing data: \'%s\'' % (error, data))

        return ascii_string

    def bytes_to_base64(self, data):
        " converts bytes to ascii format "

        from binascii import b2a_base64

        base64_string = b2a_base64(data)

        return base64_string

    def int_to_bytes(self, data):
        """
        converts an int to a string of bytes
        """
        return struct.pack('BBBB',
                           data % 256,
                           (data >> 8) % 256,
                           (data >> 16) % 256,
                           (data >> 24) % 256)

    # ~~~~~~~~~
    # Callbacks
    # ~~~~~~~~~

    def log_packet(self, packet, _object):
        """ default logging function for packets  """

        log(INFO, "Object %s is monitoring packet type %s: \n%s" % (type(_object), packet.name, packet.data()))

    def log_event_queue_data(self, data, _object):
        """ default logging function for event queue data events  """

        log(INFO, "Object %s is monitoring event queue data event %s: \n%s" % (type(_object), data.name, data.__dict__))

    def null_packet_handler(self, packet, _object):
        """ just a null event handler for watching aka fully parsing specific packets """

        pass

class ListLLSDSerializer(object):
    """adapter for serializing a list to LLSD

    An example:
    >>> d=['ChatSessionRequest', 'CopyInventoryFromNotecard']
    >>> serializer = ListLLSDSerializer(d)
    >>> serializer.serialize()
    '<?xml version="1.0" ?><llsd><array><string>ChatSessionRequest</string><string>CopyInventoryFromNotecard</string></array></llsd>'
    >>> serializer.content_type
    'application/llsd+xml'

    """

    def __init__(self, context):
        self.context = context

    def serialize(self):
        """convert the payload to LLSD"""
        return llsd.format_xml(self.context)

    @property
    def content_type(self):
        """return the content type of this serializer"""
        return "application/llsd+xml"


class DictLLSDSerializer(object):
    """adapter for serializing a dictionary to LLSD

    An example:
    >>> d={'foo':'bar', 'test':1234}
    >>> serializer = DictLLSDSerializer(d)
    >>> serializer.serialize()
    '<?xml version="1.0" ?><llsd><map><key>test</key><integer>1234</integer><key>foo</key><string>bar</string></map></llsd>'
    >>> serializer.content_type
    'application/llsd+xml'

    """

    def __init__(self, context):
        self.context = context

    def serialize(self):
        """convert the payload to LLSD"""
        return llsd.format_xml(self.context)

    @property
    def content_type(self):
        """return the content type of this serializer"""
        return "application/llsd+xml"

class LLSDDeserializer(object):
    """utility for deserializing LLSD data

    The deserialization component is defined as a utility because the input
    data can be a string or a file. It might be possible to define this as 
    an adapter on a string but a string is too generic for this. So that's 
    why it is a utility.

    You can use it like this:

    >>> s='<?xml version="1.0" ?><llsd><map><key>test</key><integer>1234</integer><key>foo</key><string>bar</string></map></llsd>'

    We use queryUtility because this returns None instead of an exception
    when a utility is not registered. We use the content type we received
    as the name of the utility. Another option would of course be to subclas
    string to some LLSDString class and use an adapter. We then would need some
    factory for generating the LLSDString class from whatever came back from
    the HTTP call.

    So here is how you use that utility:
    >>> deserializer = LLSDDeserializer()
    >>> llsd = deserializer.deserialize(s)
    >>> llsd
    {'test': 1234, 'foo': 'bar'}

    We can also test this with some non-LLSD string:

    >>> llsd = deserializer.deserialize_string('mumpitz')   # this is not LLSD
    Traceback (most recent call last):
    ...
    DeserializationFailed: deserialization failed for 'mumpitz', reason: 'invalid token at index 0: 109'

    >>> llsd = deserializer.deserialize_string('barfoo') 
    Traceback (most recent call last):
    ...
    DeserializationFailed: deserialization failed for 'barfoo', reason: 'binary notation not yet supported'


    """

    def deserialize(self, data):
        """ convenience class to handle a variety of inputs """

        if type(data) == str:
            return self.deserialize_string(data)
        # won't handle another case until we need to

    def deserialize_string(self, data):
        """ deserialize a string """

        try:
            r = llsd.parse(data)
        except llsd.LLSDParseError, e:
            raise DeserializationFailed(data, str(e))
        if r==False:
            raise DeserializationFailed(data, 'result was False')
        return r

    def deserialize_file(self, fp):
        """ deserialize a file """
        data = fp.read()
        return self.deserialize_string(data)

class Wait(object):
    """ a simple timer that blocks a calling routine for the specified number of seconds

    done since we were writing timing loops in test scripts repeatedly
    returns True when it's done
     """

    def __init__(self, duration):

        self.duration = int(duration)

        # let's be nice and enabled a kill switch
        self.enabled = False

        self.run()

    def run(self):

        now = time.time()
        start = now
        self.enabled = True

        while self.enabled and now - start < self.duration:

            api.sleep()
            now = time.time()

        return True

    def stop(self):

        self.enabled = False

"""
Contributors can be viewed at:
http://svn.secondlife.com/svn/linden/projects/2008/pyogp/CONTRIBUTORS.txt 

$LicenseInfo:firstyear=2008&license=apachev2$

Copyright 2009, Linden Research, Inc.

Licensed under the Apache License, Version 2.0 (the "License").
You may obtain a copy of the License at:
    http://www.apache.org/licenses/LICENSE-2.0
or in 
    http://svn.secondlife.com/svn/linden/projects/2008/pyogp/LICENSE.txt

$/LicenseInfo$
"""


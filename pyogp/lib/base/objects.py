"""
@file object.py
@date 2009-03-03
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

# standard python libs
from logging import getLogger, CRITICAL, ERROR, WARNING, INFO, DEBUG
import uuid
import re
from binascii import hexlify
import struct
import math

# related

# pyogp
from pyogp.lib.base import *
from pyogp.lib.base.permissions import *

# pyogp message
from pyogp.lib.base.message.packethandler import PacketHandler
from pyogp.lib.base.message.packets import *
from pyogp.lib.base.datatypes import *

# pyogp utilities
from pyogp.lib.base.utilities.helpers import Helpers

# initialize logging
logger = getLogger('pyogp.lib.base.objects')
log = logger.log

class Objects(object):
    """ is an Object Manager

    Initialize the event queue client class
    >>> objects = Objects()

    Sample implementations: region.py
    Tests: tests/test_objects.py
    """

    def __init__(self, agent = None, region = None, settings = None, packet_handler = None):
        """ set up the inventory manager """

        # allow the settings to be passed in
        # otherwise, grab the defaults
        if settings != None:
            self.settings = settings
        else:
            from pyogp.lib.base.settings import Settings
            self.settings = Settings()

        self.agent = agent
        self.region = region

        # the object store consists of a list
        # of Object() instances
        self.object_store = []

        # the avatar store consists of a list
        # of Avatar() instances
        self.avatar_store = []

        # other useful things
        self.helpers = Helpers()

        # set up callbacks
        if self.settings.HANDLE_PACKETS:
            if packet_handler != None:
                self.packet_handler = packet_handler
            else:
                self.packet_handler = PacketHandler()

            onObjectUpdate_received = self.packet_handler._register('ObjectUpdate')
            onObjectUpdate_received.subscribe(onObjectUpdate, self)

            onObjectUpdateCached_received = self.packet_handler._register('ObjectUpdateCached')
            onObjectUpdateCached_received.subscribe(onObjectUpdateCached, self)

            onObjectUpdateCompressed_received= self.packet_handler._register('ObjectUpdateCompressed')
            onObjectUpdateCompressed_received.subscribe(onObjectUpdateCompressed, self)

            onObjectProperties_received = self.packet_handler._register('ObjectProperties')
            onObjectProperties_received.subscribe(onObjectProperties, self)

            onKillObject_received= self.packet_handler._register('KillObject')
            onKillObject_received.subscribe(onKillObject, self)

            # uncomment these to view packets sent back to simulator
            # onObjectName_sent = self.packet_handler._register('ObjectName')
            # onObjectName_sent.subscribe(self.helpers.log_packet, self)

            # onDeRezObject_sent = self.packet_handler._register('DeRezObject')
            # onDeRezObject_sent.subscribe(self.helpers.log_packet, self)

        if self.settings.LOG_VERBOSE: log(INFO, "Initializing object storage")

    def process_multiple_object_updates(self, objects):
        """ process a list of object updates """

        [self.process_object_update(_object) for _object in objects]

    def process_object_update(self, _object):
        """ append to or replace an object in self.objects """

        # this is an avatar
        if _object.PCode == 47:

            self.store_avatar(_object)

        # this is a Primitive
        elif _object.PCode == 9:

            self.store_object(_object)

        else:

            if self.settings.LOG_VERBOSE: log(DEBUG, "Not processing object update of type %s" % (PCode(PCode)))

    def store_object(self, _object):

        # replace an existing list member, else, append

        index = [self.object_store.index(_object_) for _object_ in self.object_store if _object_.LocalID == _object.LocalID]

        if index != []:

            self.object_store[index[0]] = _object

            #if self.settings.LOG_VERBOSE: log(DEBUG, 'Updating a stored object: %s in region \'%s\'' % (_object.FullID, self.region.SimName))

        else:

            self.object_store.append(_object)

            #if self.settings.LOG_VERBOSE: log(DEBUG, 'Stored a new object: %s in region \'%s\'' % (_object.LocalID, self.region.SimName))

    def store_avatar(self, _objectdata):

        # if the object data pertains to us, update our data!
        if str(_objectdata.FullID) == str(self.agent.agent_id):
            self.agent.Position = _objectdata.Position
            self.agent.FootCollisionPlane = _objectdata.FootCollisionPlane
            self.agent.Velocity = _objectdata.Velocity
            self.agent.Acceleration = _objectdata.Acceleration
            self.agent.Rotation = _objectdata.Rotation
            self.agent.AngularVelocity = _objectdata.AngularVelocity

        index = [self.avatar_store.index(_avatar_) for _avatar_ in self.avatar_store if _avatar_.LocalID == _objectdata.LocalID]

        if index != []:

            self.avatar_store[index[0]] = _objectdata

            #if self.settings.LOG_VERBOSE: log(DEBUG, 'Replacing a stored avatar: %s in region \'%s\'' % (_objectdata.LocalID, self.region.SimName))

        else:

            self.avatar_store.append(_objectdata)

            #if self.settings.LOG_VERBOSE: log(DEBUG, 'Stored a new avatar: %s in region \'%s\'' % (_objectdata.LocalID, self.region.SimName))

    def get_object_from_store(self, LocalID = None, FullID = None):
        """ searches the store and returns object if stored, None otherwise """

        _object = []

        if LocalID != None:
            _object = [_object for _object in self.object_store if _object.LocalID == LocalID]
        elif FullID != None:
            _object = [_object for _object in self.object_store if str(_object.FullID) == str(FullID)]

        if _object == []:
            return None
        else:
            return _object[0]

    def get_avatar_from_store(self, LocalID = None, FullID = None):
        """ searches the store and returns object if stored, None otherwise """

        if LocalID != None:
            _avatar = [_avatar for _avatar in self.avatar_store if _avatar.LocalID == LocalID]
        elif FullID != None:
            _avatar = [_avatar for _avatar in self.avatar_store if _avatar.FullID == FullID]

        if _avatar == []:
            return None
        else:
            return _avatar[0]

    def my_objects(self):
        """ returns a list of known objects where the calling client is the owner """

        matches = [_object for _object in self.object_store if str(_object.OwnerID) == str(self.agent.agent_id)]

        return matches

    def find_objects_by_name(self, Name):
        """ searches the store for known objects by name 

        returns a list of all such known objects
        """

        pattern = re.compile(Name)

        matches = [_object for _object in self.object_store if pattern.match(_object.Name)]

        return matches

    def find_objects_within_radius(self, radius):
        """ returns objects nearby. returns a list of objects """

        if type(radius) != float:
            radius = float(radius)

        objects_nearby = []

        for item in self.object_store:

            if item.Position == None: continue

            if math.sqrt(math.pow((item.Position.X - self.agent.Position.X),2) +  math.pow((item.Position.Y - self.agent.Position.Y),2) + math.pow((item.Position.Z - self.agent.Position.Z),2)) <= radius:
                objects_nearby.append(item)

        return objects_nearby

    def remove_object_from_store(self, ID = None):

        victim = self.get_object_from_store(LocalID = ID)
        if victim == None:
            victim = self.get_avatar_from_store(LocalID = ID)

        # this is an avatar
        if victim.PCode == 47:

            self.kill_stored_avatar(ID)

        # this is a Primitive
        elif victim.PCode == 9:

            self.kill_stored_object(ID)

        else:

            if self.settings.LOG_VERBOSE and self.settings.ENABLE_OBJECT_LOGGING: log(DEBUG, "Not processing kill of unstored object type %s" % (PCode(PCode)))

    def kill_stored_avatar(self, ID):

        index = [self.avatar_store.index(_avatar_) for _avatar_ in self.avatar_store if _avatar_.LocalID == ID]

        if index != []:
            del self.avatar_store[index[0]]
            if self.settings.LOG_VERBOSE and self.settings.ENABLE_OBJECT_LOGGING: log(DEBUG, "Kill on object data for avatar tracked as local id %s" % (ID))

    def kill_stored_object(self, ID):

        index = [self.object_store.index(_object_) for _object_ in self.object_store if _object_.LocalID == ID]

        if index != []:
            del self.object_store[index[0]]
            if self.settings.LOG_VERBOSE and self.settings.ENABLE_OBJECT_LOGGING: log(DEBUG, "Kill on object data for object tracked as local id %s" % (ID))

    def update_multiple_objects_properties(self, object_list):
        """ update the attributes of objects """

        #if self.settings.LOG_VERBOSE and self.settings.ENABLE_OBJECT_LOGGING: log(DEBUG, "Processing multiple object properties updates: %s" % (len(object_list)))


        for object_properties in object_list:

            self.update_object_properties(object_properties)

    def update_object_properties(self, object_properties):
        """ update the attributes of an object
        
        If the object is known, we update the properties. 
        If not, we create a new object
        """

        #if self.settings.LOG_VERBOSE and self.settings.ENABLE_OBJECT_LOGGING: log(DEBUG, "Processing object properties update for FullID: %s" % (object_properties['FullID']))

        if object_properties.has_key('PCode'):
            # this is an avatar
            if object_properties['PCode'] == 47:

                #if self.settings.LOG_VERBOSE and self.settings.ENABLE_OBJECT_LOGGING: log(DEBUG, "Creating a new avatar and storing their attributes. LocalID = %s" % (object_properties['LocalID']))

                _object = Object()
                _object.update_properties(object_properties)

                self.store_avatar(_object)

            else:

                self.update_prim_properties(object_properties)

        else:

                self.update_prim_properties(object_properties)

    def update_prim_properties(self, prim_properties):

            _object = self.get_object_from_store(FullID = prim_properties['FullID'])

            if _object == None:
                #if self.settings.LOG_VERBOSE and self.settings.ENABLE_OBJECT_LOGGING: log(DEBUG, "Creating a new object and storing it's attributes. LocalID = %s" % (object_properties['LocalID']))
                _object = Object()
                _object.update_properties(prim_properties)
                self.store_object(_object)
            else:
                #if self.settings.LOG_VERBOSE and self.settings.ENABLE_OBJECT_LOGGING: log(DEBUG, "Updating an object's attributes. LocalID = %s" % (object_properties['LocalID']))
                _object.update_properties(prim_properties)

    def request_object_update(self, ID = None, ID_list = None):
        """ requests object updates from the simulator

        accepts a tuple of (ID, CacheMissType), or a list of such tuples
        """

        packet = RequestMultipleObjectsPacket()
        packet.AgentData['AgentID'] = uuid.UUID(str(self.agent.agent_id))
        packet.AgentData['SessionID'] = uuid.UUID(str(self.agent.session_id))

        if ID != None:

            ObjectData = {}
            ObjectData['CacheMissType'] = ID[1]
            ObjectData['ID'] = ID[0]

            packet.ObjectDataBlocks.append(ObjectData)

        else:

            for ID in ID_list:

                ObjectData = {}
                ObjectData['CacheMissType'] = ID[1]
                ObjectData['ID'] = ID[0]

                packet.ObjectDataBlocks.append(ObjectData)

        # enqueue the message, send as reliable
        self.region.enqueue_message(packet(), True)

    def create_default_box(self, GroupID = uuid.UUID('00000000-0000-0000-0000-000000000000'), relative_position = (1, 0, 0)):
        """ creates the default box, defaulting as 1m to the east, with an option GroupID to set the prim to"""

        # self.agent.Position holds where we are. we need to add this tuple to the incoming tuple (vector to a vector)
        location_to_rez_x = self.agent.Position.X + relative_position[0]
        location_to_rez_y = self.agent.Position.Y + relative_position[1]
        location_to_rez_z = self.agent.Position.Z + relative_position[2]

        location_to_rez = (location_to_rez_x, location_to_rez_y, location_to_rez_z)

        # not sure what RayTargetID is, send as uuid of zeros
        RayTargetID = uuid.UUID('00000000-0000-0000-0000-000000000000')

        self.object_add(GroupID = GroupID, PCode = 9, Material = 3, AddFlags = 2, PathCurve = 16, ProfileCurve = 1, PathBegin = 0, PathEnd = 0, PathScaleX = 100, PathScaleY = 100, PathShearX = 0, PathShearY = 0, PathTwist = 0, PathTwistBegin = 0, PathRadiusOffset = 0, PathTaperX = 0, PathTaperY = 0, PathRevolutions = 0, PathSkew = 0, ProfileBegin = 0, ProfileEnd = 0, ProfileHollow = 0, BypassRaycast = 1, RayStart = location_to_rez, RayEnd = location_to_rez, RayTargetID = RayTargetID, RayEndIsIntersection = 0, Scale = (0.5, 0.5, 0.5), Rotation = (0, 0, 0, 1), State = 0)

    def object_add(self, PCode, Material, AddFlags, PathCurve, ProfileCurve, PathBegin, PathEnd, PathScaleX, PathScaleY, PathShearX, PathShearY, PathTwist, PathTwistBegin, PathRadiusOffset, PathTaperX, PathTaperY, PathRevolutions, PathSkew, ProfileBegin, ProfileEnd, ProfileHollow, BypassRaycast, RayStart, RayEnd, RayTargetID, RayEndIsIntersection, Scale, Rotation, State, GroupID = uuid.UUID('00000000-0000-0000-0000-000000000000')):
        '''
        ObjectAdd - create new object in the world
        Simulator will assign ID and send message back to signal
        object actually created.

        AddFlags (see also ObjectUpdate)
        0x01 - use physics
        0x02 - create selected

        GroupID defaults to (No group active)
        '''

        packet = ObjectAddPacket()

        # build the AgentData block
        packet.AgentData['AgentID'] = uuid.UUID(str(self.agent.agent_id))
        packet.AgentData['SessionID'] = uuid.UUID(str(self.agent.session_id))
        packet.AgentData['GroupID'] = uuid.UUID(str(GroupID))

        # build the ObjectData block (it's a Single)
        packet.ObjectData['PCode'] = PCode
        packet.ObjectData['Material'] = Material
        packet.ObjectData['AddFlags'] = AddFlags
        packet.ObjectData['PathCurve'] = PathCurve
        packet.ObjectData['ProfileCurve'] = ProfileCurve
        packet.ObjectData['PathBegin'] = PathBegin
        packet.ObjectData['PathEnd'] = PathEnd
        packet.ObjectData['PathScaleX'] = PathScaleX
        packet.ObjectData['PathScaleY'] = PathScaleY
        packet.ObjectData['PathShearX'] = PathShearX
        packet.ObjectData['PathShearY'] = PathShearY
        packet.ObjectData['PathTwist'] = PathTwist
        packet.ObjectData['PathTwistBegin'] = PathTwistBegin
        packet.ObjectData['PathRadiusOffset'] = PathRadiusOffset
        packet.ObjectData['PathTaperX'] = PathTaperX
        packet.ObjectData['PathTaperY'] = PathTaperY
        packet.ObjectData['PathRevolutions'] = PathRevolutions
        packet.ObjectData['PathSkew'] = PathSkew
        packet.ObjectData['ProfileBegin'] = ProfileBegin
        packet.ObjectData['ProfileEnd'] = ProfileEnd
        packet.ObjectData['ProfileHollow'] = ProfileHollow
        packet.ObjectData['BypassRaycast'] = BypassRaycast
        packet.ObjectData['RayStart'] = RayStart
        packet.ObjectData['RayEnd'] = RayEnd
        packet.ObjectData['RayTargetID'] = uuid.UUID(str(RayTargetID))
        packet.ObjectData['RayEndIsIntersection'] = RayEndIsIntersection
        packet.ObjectData['Scale'] = Scale
        packet.ObjectData['Rotation'] = Rotation
        packet.ObjectData['State'] = State

        self.region.enqueue_message(packet(), True)

class Object(object):
    """ represents an Object

    Initialize the Object class instance
    >>> object = Object()

    Sample implementations: objects.py
    Tests: tests/test_objects.py
    """

    def __init__(self, LocalID = None, State = None, FullID = None, CRC = None, PCode = None, Material = None, ClickAction = None, Scale = None, ObjectData = None, ParentID = None, UpdateFlags = None, PathCurve = None, ProfileCurve = None, PathBegin = None, PathEnd = None, PathScaleX = None, PathScaleY = None, PathShearX = None, PathShearY = None, PathTwist = None, PathTwistBegin = None, PathRadiusOffset = None, PathTaperX = None, PathTaperY = None, PathRevolutions = None, PathSkew = None, ProfileBegin = None, ProfileEnd = None, ProfileHollow = None, TextureEntry = None, TextureAnim = None, NameValue = None, Data = None, Text = None, TextColor = None, MediaURL = None, PSBlock = None, ExtraParams = None, Sound = None, OwnerID = None, Gain = None, Flags = None, Radius = None, JointType = None, JointPivot = None, JointAxisOrAnchor = None, FootCollisionPlane = None, Position = None, Velocity = None, Acceleration = None, Rotation = None, AngularVelocity = None):
        """ set up the object attributes """

        self.LocalID = LocalID                                 # U32
        self.State = State                           # U8
        self.FullID = FullID        # LLUUID
        self.CRC = CRC                               # U32 // TEMPORARY HACK FOR JAMES
        self.PCode = PCode                           # U8
        self.Material = Material                     # U8
        self.ClickAction = ClickAction               # U8
        self.Scale = Scale                           # LLVector3
        self.ObjectData = ObjectData                 # Variable 1
        self.ParentID = ParentID                     # U32
        self.UpdateFlags = UpdateFlags               # U32 // U32, see object_flags.h
        self.PathCurve = PathCurve                   # U8
        self.ProfileCurve = ProfileCurve             # U8
        self.PathBegin = PathBegin                   # U16 // 0 to 1, quanta = 0.01
        self.PathEnd = PathEnd                       # U16 // 0 to 1, quanta = 0.01
        self.PathScaleX = PathScaleX                 # U8 // 0 to 1, quanta = 0.01
        self.PathScaleY = PathScaleY                 # U8 // 0 to 1, quanta = 0.01
        self.PathShearX = PathShearX                 # U8 // -.5 to .5, quanta = 0.01
        self.PathShearY = PathShearY                 # U8 // -.5 to .5, quanta = 0.01
        self.PathTwist = PathTwist                   # S8 // -1 to 1, quanta = 0.01
        self.PathTwistBegin = PathTwistBegin         # S8 // -1 to 1, quanta = 0.01
        self.PathRadiusOffset = PathRadiusOffset     # S8 // -1 to 1, quanta = 0.01
        self.PathTaperX = PathTaperX                 # S8 // -1 to 1, quanta = 0.01
        self.PathTaperY = PathTaperY                 # S8 // -1 to 1, quanta = 0.01
        self.PathRevolutions = PathRevolutions       # U8 // 0 to 3, quanta = 0.015
        self.PathSkew = PathSkew                     # S8 // -1 to 1, quanta = 0.01
        self.ProfileBegin = ProfileBegin             # U16 // 0 to 1, quanta = 0.01
        self.ProfileEnd = ProfileEnd                 # U16 // 0 to 1, quanta = 0.01
        self.ProfileHollow = ProfileHollow           # U16 // 0 to 1, quanta = 0.01
        self.TextureEntry = TextureEntry             # Variable 2
        self.TextureAnim = TextureAnim               # Variable 1
        self.NameValue = NameValue                   # Variable 2
        self.Data = Data                             # Variable 2
        self.Text = Text                             # Variable 1 // llSetText() hovering text
        self.TextColor = TextColor                   # Fixed 4 // actually, a LLColor4U
        self.MediaURL = MediaURL                     # Variable 1 // URL for web page, movie, etc.
        self.PSBlock = PSBlock                       # Variable 1
        self.ExtraParams = ExtraParams               # Variable 1
        self.Sound = Sound                           # LLUUID
        self.OwnerID = OwnerID                       # LLUUID // HACK object's owner id, only set if non-null sound, for muting
        self.Gain = Gain                             # F32
        self.Flags = Flags                           # U8
        self.Radius = Radius                         # F32 // cutoff radius
        self.JointType = JointType                   # U8
        self.JointPivot = JointPivot                 # LLVector3
        self.JointAxisOrAnchor = JointAxisOrAnchor   # LLVector3

        # from ObjectUpdateCompressed
        self.FootCollisionPlane = FootCollisionPlane
        self.Position = Position
        self.Velocity = Velocity
        self.Acceleration = Acceleration
        self.Rotation = Rotation
        self.AngularVelocity = AngularVelocity

        # from ObjectProperties
        self.CreatorID = None
        self.GroupID = None
        self.CreationDate = None
        self.BaseMask = None
        self.OwnerMask = None
        self.GroupMask = None
        self.EveryoneMask = None
        self.NextOwnerMask = None
        self.OwnershipCost = None
        # TaxRate
        self.SaleType = None
        self.SalePrice = None
        self.AggregatePerms = None
        self.AggregatePermTextures = None
        self.AggregatePermTexturesOwner = None
        self.Category = None
        self.InventorySerial = None
        self.ItemID = None
        self.FolderID = None
        self.FromTaskID = None
        self.LastOwnerID = None
        self.Name = None
        self.Description = None
        self.TouchName = None
        self.SitName = None
        self.TextureID = None

    def update_object_permissions(self, agent, Field, Set, Mask, Override = False):
        """ update permissions for a list of objects

        This will update a specific bit to a specific value.
        """

        packet = ObjectPermissionsPacket()

        # build the AgentData block
        packet.AgentData['AgentID'] = uuid.UUID(str(agent.agent_id))
        packet.AgentData['SessionID'] = uuid.UUID(str(agent.session_id))

        packet.HeaderData['Override'] = Override # BOOL, God-bit.

        ObjectData = {}
        ObjectData['ObjectLocalID'] = self.LocalID
        ObjectData['Field'] = Field         # U32
        ObjectData['Set'] = Set             # U8
        ObjectData['Mask'] = Mask           # S32

        packet.ObjectDataBlocks.append(ObjectData)

        agent.region.enqueue_message(packet())

    def set_object_full_permissions(self, agent):
        """ 
        Set Next Owner Permissions Copy, Modify, Transfer 
        This is also called 'full permissions'.
        """

        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 1, PermissionsMask.Copy)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 1, PermissionsMask.Modify)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 1, PermissionsMask.Transfer)

    def set_object_copy_mod_permissions(self, agent):
        """ 
        Set Next Owner Permissions to Copy/Mod
        This is a common permission set for attachements.
        """

        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 1, PermissionsMask.Copy)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 1, PermissionsMask.Modify)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 0, PermissionsMask.Transfer)

    def set_object_mod_transfer_permissions(self, agent):
        """
        Set Next Owner Permissions to Mod/Transfer
        This is a common permission set for clothing.
        """

        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 0, PermissionsMask.Copy)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 1, PermissionsMask.Modify)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 1, PermissionsMask.Transfer)

    def set_object_transfer_only_permissions(self, agent):
        """
        Set Next Owner Permissions to Transfer Only
        This is the most restrictive set of permissions allowed.
        """

        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 0, PermissionsMask.Copy)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 0, PermissionsMask.Modify)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 1, PermissionsMask.Transfer)

    def set_object_copy_transfer_permissions(self, agent):
        """
        Set Next Owner Permissions to Copy/Transfer
        """

        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 1, PermissionsMask.Copy)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 0, PermissionsMask.Modify)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 1, PermissionsMask.Transfer)

    def set_object_copy_only_permissions(self, agent):
        """
        Set Next Owner Permissions to Copy Only
        """

        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 1, PermissionsMask.Copy)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 0, PermissionsMask.Modify)
        self.update_object_permissions(agent, PermissionsTarget.NextOwner, 0, PermissionsMask.Transfer)

    def set_object_name(self, agent, Name):
        """ update the name of an object 

        """

        packet = ObjectNamePacket()

        # build the AgentData block
        packet.AgentData['AgentID'] = uuid.UUID(str(agent.agent_id))
        packet.AgentData['SessionID'] = uuid.UUID(str(agent.session_id))

        ObjectData = {}
        ObjectData['LocalID'] = self.LocalID
        ObjectData['Name'] = Name

        packet.ObjectDataBlocks.append(ObjectData)

        agent.region.enqueue_message(packet())

    def set_object_description(self, agent, Description):
        """ update the description of an objects 

        """

        packet = ObjectDescriptionPacket()

        # build the AgentData block
        packet.AgentData['AgentID'] = uuid.UUID(str(agent.agent_id))
        packet.AgentData['SessionID'] = uuid.UUID(str(agent.session_id))

        ObjectData = {}
        ObjectData['LocalID'] = self.LocalID
        ObjectData['Description'] = Description

        packet.ObjectDataBlocks.append(ObjectData)

        agent.region.enqueue_message(packet())

    def derez(self, agent, destination, destinationID, transactionID, GroupID):
        """ derez an object, specifying the destination """

        packet = DeRezObjectPacket()

        # build the AgentData block
        packet.AgentData['AgentID'] = uuid.UUID(str(agent.agent_id))
        packet.AgentData['SessionID'] = uuid.UUID(str(agent.session_id))

        packet.AgentBlock['GroupID'] = uuid.UUID(str(GroupID))
        packet.AgentBlock['Destination'] = destination
        packet.AgentBlock['DestinationID'] = uuid.UUID(str(destinationID))
        packet.AgentBlock['TransactionID'] = uuid.UUID(str(transactionID))

        # fix me: faking these values
        packet.AgentBlock['PacketCount']   = 1
        packet.AgentBlock['PacketNumber']  = 0

        ObjectData = {}
        ObjectData['ObjectLocalID'] = self.LocalID

        packet.ObjectDataBlocks.append(ObjectData)

        agent.region.enqueue_message(packet())

    def take(self, agent):
        """ take object into inventory """

        parent_folder = self.FolderID

        # Check if we have inventory turned on
        if not(parent_folder and agent.settings.ENABLE_INVENTORY_MANAGEMENT):
            log(WARNING,"Inventory not available, please enable settings.ENABLE_INVENTORY_MANAGEMENT")
            return 

        if not(parent_folder):
            # locate Object folder
            objects_folder = [ folder for folder in agent.inventory.folders if folder.Name == 'Objects' ]
            if objects_folder:
                parent_folder = objects_folder[0].FolderID
            else:
                log(ERROR,"Unable to locate top-level Objects folder to take item into inventory.")
                return

        self.derez(agent, 4, parent_folder, uuid.uuid4(), agent.ActiveGroupID)

    def select(self, agent):
        """ select an object

        """

        packet = ObjectSelectPacket()

        # build the AgentData block
        packet.AgentData['AgentID'] = uuid.UUID(str(agent.agent_id))
        packet.AgentData['SessionID'] = uuid.UUID(str(agent.session_id))

        ObjectData = {}
        ObjectData['ObjectLocalID'] = self.LocalID

        packet.ObjectDataBlocks.append(ObjectData)

        agent.region.enqueue_message(packet())

    def deselect(self, agent):
        """ deselect an object

        """

        packet = ObjectDeselectPacket()

        # build the AgentData block
        packet.AgentData['AgentID'] = uuid.UUID(str(agent.agent_id))
        packet.AgentData['SessionID'] = uuid.UUID(str(agent.session_id))

        ObjectData = {}
        ObjectData['ObjectLocalID'] = self.LocalID

        packet.ObjectDataBlocks.append(ObjectData)

        agent.region.enqueue_message(packet())

    def update_properties(self, properties):
        """ takes a dictionary of attribute:value and makes it so """

        for attribute in properties:

            setattr(self, attribute, properties[attribute])

class PCode(object):
    """ classifying the PCode of objects """

    Primitive = 9          # 0x09
    Avatar = 47            # 0x2F
    Grass = 95             # 0x5F
    NewTree = 111          # 0x6F
    ParticleSystem = 143   # 0x8F
    Tree = 255             # 0xFF

class CompressedUpdateFlags(object):
    """ map of ObjectData.Flags """

    ScratchPad = 0x01
    Tree = 0x02
    contains_Text = 0x04
    contains_Particles = 0x08
    contains_Sound = 0x10
    contains_Parent = 0x20
    TextureAnim = 0x40
    contains_AngularVelocity = 0x80
    contains_NameValues = 0x100
    MediaURL = 0x200

class ExtraParam(object):
    """ extended Object attributes buried in some packets """

    Flexible = 0x10
    Light = 0x20
    Sculpt = 0x30

def onObjectUpdate(packet, objects):
    """ populates an Object instance and adds it to the Objects() store """

    object_list = []

    # ToDo: handle these 2 variables properly
    _RegionHandle = packet.message_data.blocks['RegionData'][0].get_variable('RegionHandle').data
    _TimeDilation = packet.message_data.blocks['RegionData'][0].get_variable('TimeDilation').data

    for ObjectData_block in packet.message_data.blocks['ObjectData']:

        object_properties = {}

        object_properties['LocalID'] = ObjectData_block.get_variable('ID').data
        object_properties['State'] = ObjectData_block.get_variable('State').data
        object_properties['FullID'] = ObjectData_block.get_variable('FullID').data
        object_properties['CRC'] = ObjectData_block.get_variable('CRC').data
        object_properties['PCode'] = ObjectData_block.get_variable('PCode').data
        object_properties['Material'] = ObjectData_block.get_variable('Material').data
        object_properties['ClickAction'] = ObjectData_block.get_variable('ClickAction').data
        object_properties['Scale'] = ObjectData_block.get_variable('Scale').data
        object_properties['ObjectData'] = ObjectData_block.get_variable('ObjectData').data
        object_properties['ParentID'] = ObjectData_block.get_variable('ParentID').data
        object_properties['UpdateFlags'] = ObjectData_block.get_variable('UpdateFlags').data
        object_properties['PathCurve'] = ObjectData_block.get_variable('PathCurve').data
        object_properties['ProfileCurve'] = ObjectData_block.get_variable('ProfileCurve').data
        object_properties['PathBegin'] = ObjectData_block.get_variable('PathBegin').data
        object_properties['PathEnd'] = ObjectData_block.get_variable('PathEnd').data
        object_properties['PathScaleX'] = ObjectData_block.get_variable('PathScaleX').data
        object_properties['PathScaleY'] = ObjectData_block.get_variable('PathScaleY').data
        object_properties['PathShearX'] = ObjectData_block.get_variable('PathShearX').data
        object_properties['PathShearY'] = ObjectData_block.get_variable('PathShearY').data
        object_properties['PathTwist'] = ObjectData_block.get_variable('PathTwist').data
        object_properties['PathTwistBegin'] = ObjectData_block.get_variable('PathTwistBegin').data
        object_properties['PathRadiusOffset'] = ObjectData_block.get_variable('PathRadiusOffset').data
        object_properties['PathTaperX'] = ObjectData_block.get_variable('PathTaperX').data
        object_properties['PathTaperY'] = ObjectData_block.get_variable('PathTaperY').data
        object_properties['PathRevolutions'] = ObjectData_block.get_variable('PathRevolutions').data
        object_properties['PathSkew'] = ObjectData_block.get_variable('PathSkew').data
        object_properties['ProfileBegin'] = ObjectData_block.get_variable('ProfileBegin').data
        object_properties['ProfileEnd'] = ObjectData_block.get_variable('ProfileEnd').data
        object_properties['ProfileHollow'] = ObjectData_block.get_variable('ProfileHollow').data
        object_properties['TextureEntry'] = ObjectData_block.get_variable('TextureEntry').data
        object_properties['TextureAnim'] = ObjectData_block.get_variable('TextureAnim').data
        object_properties['NameValue'] = ObjectData_block.get_variable('NameValue').data
        object_properties['Data'] = ObjectData_block.get_variable('Data').data
        object_properties['Text'] = ObjectData_block.get_variable('Text').data
        object_properties['TextColor'] = ObjectData_block.get_variable('TextColor').data
        object_properties['MediaURL'] = ObjectData_block.get_variable('MediaURL').data
        object_properties['PSBlock'] = ObjectData_block.get_variable('PSBlock').data
        object_properties['ExtraParams'] = ObjectData_block.get_variable('ExtraParams').data
        object_properties['Sound'] = ObjectData_block.get_variable('Sound').data
        object_properties['OwnerID'] = ObjectData_block.get_variable('OwnerID').data
        object_properties['Gain'] = ObjectData_block.get_variable('Gain').data
        object_properties['Flags'] = ObjectData_block.get_variable('Flags').data
        object_properties['Radius'] = ObjectData_block.get_variable('Radius').data
        object_properties['JointType'] = ObjectData_block.get_variable('JointType').data
        object_properties['JointPivot'] = ObjectData_block.get_variable('JointPivot').data
        object_properties['JointAxisOrAnchor'] = ObjectData_block.get_variable('JointAxisOrAnchor').data

        # deal with the data stored in _ObjectData
        # see http://wiki.secondlife.com/wiki/ObjectUpdate#ObjectData_Format for details

        object_properties['FootCollisionPlane'] = None 
        object_properties['Position'] = None
        object_properties['Velocity'] = None
        object_properties['Acceleration'] = None
        object_properties['Rotation'] = None
        object_properties['AngularVelocity'] = None

        if len(object_properties['ObjectData']) == 76:

            # Foot collision plane. LLVector4.
            # Angular velocity is ignored and set to 0. Falls through to 60 bytes parser. 

            object_properties['FootCollisionPlane'] = Quaternion(object_properties['ObjectData'], 0)
            object_properties['Position'] = Vector3(object_properties['ObjectData'], 16)
            object_properties['Velocity'] = Vector3(object_properties['ObjectData'], 28)
            object_properties['Acceleration'] = Vector3(object_properties['ObjectData'], 40)
            object_properties['Rotation'] = Vector3(object_properties['ObjectData'], 52)
            object_properties['AngularVelocity'] = Vector3(object_properties['ObjectData'], 60)

        elif len(object_properties['ObjectData']) == 60:

            # 32 bit precision update.

            object_properties['Position'] = Vector3(object_properties['ObjectData'], 0)
            object_properties['Velocity'] = Vector3(object_properties['ObjectData'], 12)
            object_properties['Acceleration'] = Vector3(object_properties['ObjectData'], 24)
            object_properties['Rotation'] = Vector3(object_properties['ObjectData'], 36)
            object_properties['AngularVelocity'] = Vector3(object_properties['ObjectData'], 48)

        elif len(object_properties['ObjectData']) == 48:

            # Foot collision plane. LLVector4 
            # Falls through to 32 bytes parser.

            log(WARNING, "48 bit ObjectData precision not implemented")

        elif len(object_properties['ObjectData']) == 32:

            # 32 bit precision update.

            # Position. U16Vec3.
            # Velocity. U16Vec3.
            # Acceleration. U16Vec3.
            # Rotation. U16Rot(4xU16).
            # Angular velocity. LLVector3.
            log(WARNING, "32 bit ObjectData precision not implemented")

        elif len(object_properties['ObjectData']) == 16:

            # 8 bit precision update.

            # Position. U8Vec3.
            # Velocity. U8Vec3.
            # Acceleration. U8Vec3.
            # Rotation. U8Rot(4xU8).
            # Angular velocity. U8Vec3
            log(WARNING, "16 bit ObjectData precision not implemented")

        object_list.append(object_properties)

    objects.update_multiple_objects_properties(object_list)

def onObjectUpdateCached(packet, objects):
    """ borrowing from libomv, we'll request object data for all data coming in via ObjectUpdateCached"""

    # ToDo: handle these 2 variables properly
    _RegionHandle = packet.message_data.blocks['RegionData'][0].get_variable('RegionHandle').data
    _TimeDilation = packet.message_data.blocks['RegionData'][0].get_variable('TimeDilation').data

    _request_list = []

    for ObjectData_block in packet.message_data.blocks['ObjectData']:

        LocalID = ObjectData_block.get_variable('ID').data
        _CRC = ObjectData_block.get_variable('CRC').data
        _UpdateFlags = ObjectData_block.get_variable('UpdateFlags').data

        # Objects.request_object_update() expects a tuple of (_ID, CacheMissType)

        # see if we have the object stored already
        _object = objects.get_object_from_store(LocalID = LocalID)

        if _object == None or _object == []:
            CacheMissType = 1
        else:
            CacheMissType = 0

        _request_list.append((LocalID, CacheMissType))

    # ask the simulator for updates
    objects.request_object_update(ID_list = _request_list)

def onObjectUpdateCompressed(packet, objects):

    object_list = []

    # ToDo: handle these 2 variables properly
    _RegionHandle = packet.message_data.blocks['RegionData'][0].get_variable('RegionHandle').data
    _TimeDilation = packet.message_data.blocks['RegionData'][0].get_variable('TimeDilation').data

    for ObjectData_block in packet.message_data.blocks['ObjectData']:

        object_properties = {}

        object_properties['UpdateFlags'] = ObjectData_block.get_variable('UpdateFlags').data
        object_properties['Data'] = ObjectData_block.get_variable('Data').data
        _Data = object_properties['Data']

        pos = 0         # position in the binary string
        object_properties['FullID'] = UUID(bytes = _Data, offset = 0)        # LLUUID
        pos += 16
        object_properties['LocalID'] = struct.unpack("<I", _Data[pos:pos+4])[0]
        pos += 4
        object_properties['PCode'] = struct.unpack(">B", _Data[pos:pos+1])[0]
        pos += 1

        if object_properties['PCode'] != 9:         # if it is not a prim, stop.
            log(WARNING, 'Fix Me!! Skipping parsing of ObjectUpdateCompressed packet when it is not a prim.')
            # we ought to parse it and make sense of the data...
            continue
        
        object_properties['State'] = struct.unpack(">B", _Data[pos:pos+1])[0]
        pos += 1
        object_properties['CRC'] = struct.unpack("<I", _Data[pos:pos+4])[0]
        pos += 4
        object_properties['Material'] = struct.unpack(">B", _Data[pos:pos+1])[0]
        pos += 1
        object_properties['ClickAction'] = struct.unpack(">B", _Data[pos:pos+1])[0]
        pos += 1
        object_properties['Scale'] = Vector3(_Data, pos)
        pos += 12
        object_properties['Position'] = Vector3(_Data, pos)
        pos += 12
        object_properties['Rotation'] = Vector3(_Data, pos)
        pos += 12
        object_properties['Flags'] = struct.unpack(">B", _Data[pos:pos+1])[0]
        pos += 1
        object_properties['OwnerID'] = UUID(_Data, pos)
        pos += 16

        # Placeholder vars, to be populated via flags if present
        object_properties['AngularVelocity'] = Vector3()
        object_properties['ParentID'] = UUID()
        object_properties['Text'] = ''
        object_properties['TextColor'] = None
        object_properties['MediaURL'] = ''
        object_properties['Sound'] = UUID()
        object_properties['Gain'] = 0
        object_properties['Flags'] = 0
        object_properties['Radius'] = 0
        object_properties['NameValue'] = ''
        object_properties['ExtraParams'] = None

        if object_properties['Flags'] != 0:

            log(WARNING, "FixMe! Quiting parsing an ObjectUpdateCompressed packet with flags due to incomplete implemention. Storing a partial representation of an object with uuid of %s" % (_FullID))
            
            # the commented code is not working right, we need to figure out why!
            # ExtraParams in particular seemed troublesome

            '''
            print 'Flags: ', Flags

            if (Flags & CompressedUpdateFlags.contains_AngularVelocity) != 0:
                _AngularVelocity = Vector3(_Data, pos)
                pos += 12
                print 'AngularVelocity: ', _AngularVelocity
            else:
                _AngularVelocity = None

            if (Flags & CompressedUpdateFlags.contains_Parent) != 0:
                _ParentID = UUID(_Data, pos)
                pos += 16
                print 'ParentID: ', _ParentID
            else:
                _ParentID = None

            if (Flags & CompressedUpdateFlags.Tree) != 0:
                # skip it, only iterate the position
                pos += 1
                print 'Tree'

            if (Flags & CompressedUpdateFlags.ScratchPad) != 0:
                # skip it, only iterate the position
                size = struct.unpack(">B", _Data[pos:pos+1])[0]
                pos += 1
                pos += size
                print 'Scratchpad size'

            if (Flags & CompressedUpdateFlags.contains_Text) != 0:
                # skip it, only iterate the position
                _Text = ''
                while struct.unpack(">B", _Data[pos:pos+1])[0] != 0:
                    pos += 1
                pos += 1
                _TextColor = struct.unpack("<I", _Data[pos:pos+4])[0]
                pos += 4
                print '_TextColor: ', _TextColor

            if (Flags & CompressedUpdateFlags.MediaURL) != 0:
                # skip it, only iterate the position
                _MediaURL = ''
                while struct.unpack(">B", _Data[pos:pos+1])[0] != 0:
                    pos += 1
                pos += 1
                print '_MediaURL: ', _MediaURL

            if (Flags & CompressedUpdateFlags.contains_Particles) != 0:
                # skip it, only iterate the position
                ParticleData = _Data[pos:pos+86]
                pos += 86
                print 'Particles'

            # parse ExtraParams
            # ToDo: finish this up, for now we are just incrementing the position and not dealing with the data

            _Flexible = None
            _Light = None
            _Sculpt = None

            num_extra_params =  struct.unpack(">b", _Data[pos:pos+1])[0]
            print 'Number of extra params: ', num_extra_params
            pos += 1

            for i in range(num_extra_params):
                
                # ExtraParam type
                extraparam_type = struct.unpack("<H", _Data[pos:pos+2])[0]
                pos += 2

                datalength = struct.unpack("<I", _Data[pos:pos+4])[0]
                print 'ExtraParams type: %s length: %s' % (extraparam_type, datalength)
                pos += 4

                pos += int(datalength)

            # ToDo: Deal with extra parameters
            #log(WARNING, "Incomplete implementation in onObjectUpdateCompressed when flags are present. Skipping parsing this object...")
            #continue

            if (Flags & CompressedUpdateFlags.contains_Sound) != 0:
                # skip it, only iterate the position
                #_Sound = uuid.UUID(bytes = _Data[pos:pos+16])
                pos += 16
                print 'Sound'

                #_Gain = struct.unpack(">f", _Data[pos:pos+4])[0]
                pos += 4

                #_Flags = stuct.unpack(">B", _Data[pos:pos+1])[0]
                pos += 1

                #_Radius = struct.unpack(">f", _Data[pos:pos+4])[0]
                pos += 4

            if (Flags & CompressedUpdateFlags.contains_NameValues) != 0:
                # skip it, only iterate the position
                _NameValue = ''

                while _Data[pos:pos+1] != 0:
                    #_NameValue += struct.unpack(">c", _Data[pos:pos+1])[0]
                    pos += 1
                pos += 1
            '''

            object_properties['PathCurve'] = None
            object_properties['PathBegin'] = None
            object_properties['PathEnd'] = None
            object_properties['PathScaleX'] = None
            object_properties['PathScaleY'] = None
            object_properties['PathShearX'] = None
            object_properties['PathShearY'] = None
            object_properties['PathTwist'] = None
            object_properties['PathTwistBegin'] = None
            object_properties['PathRadiusOffset'] = None
            object_properties['PathTaperX'] = None
            object_properties['PathTaperY'] = None
            object_properties['PathRevolutions'] = None
            object_properties['PathSkew'] = None
            object_properties['ProfileCurve'] = None
            object_properties['ProfileBegin'] = None
            object_properties['ProfileEnd'] = None
            object_properties['ProfileHollow'] = None
            object_properties['TextureEntry'] = None
            object_properties['TextureAnim'] = None
            object_properties['TextureAnim'] = None

        else:

            object_properties['PathCurve'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['PathBegin'] = struct.unpack("<H", _Data[pos:pos+2])[0]
            pos += 2
            object_properties['PathEnd'] = struct.unpack("<H", _Data[pos:pos+2])[0]
            pos += 2
            object_properties['PathScaleX'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['PathScaleY'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['PathShearX'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['PathShearY'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['PathTwist'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['PathTwistBegin'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['PathRadiusOffset'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['PathTaperX'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['PathTaperY'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['PathRevolutions'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['PathSkew'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['ProfileCurve'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['ProfileBegin'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['ProfileEnd'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1
            object_properties['ProfileHollow'] = struct.unpack(">B", _Data[pos:pos+1])[0]
            pos += 1 

            # Texture handling
            size = struct.unpack("<H", _Data[pos:pos+2])[0]
            pos += 2
            object_properties['TextureEntry'] = _Data[pos:pos+size]
            pos += size

            if (object_properties['Flags'] & CompressedUpdateFlags.TextureAnim) != 0:
                object_properties['TextureAnim'] = struct.unpack("<H", _Data[pos:pos+2])[0]
                pos += 2
            else:
                object_properties['TextureAnim'] = None

        object_list.append(object_properties)

    objects.update_multiple_objects_properties(object_list)

def onKillObject(packet, objects):

    _KillID = packet.message_data.blocks['ObjectData'][0].get_variable('ID').data

    objects.remove_object_from_store(_KillID)

def onObjectProperties(packet, objects):

    object_list = []

    for ObjectData_block in packet.message_data.blocks['ObjectData']:

        object_properties = {}

        object_properties['FullID'] = ObjectData_block.get_variable('ObjectID').data
        object_properties['CreatorID'] = ObjectData_block.get_variable('CreatorID').data
        object_properties['OwnerID'] = ObjectData_block.get_variable('OwnerID').data
        object_properties['GroupID'] = ObjectData_block.get_variable('GroupID').data
        object_properties['CreationDate'] = ObjectData_block.get_variable('CreationDate').data
        object_properties['BaseMask'] = ObjectData_block.get_variable('BaseMask').data
        object_properties['OwnerMask'] = ObjectData_block.get_variable('OwnerMask').data
        object_properties['GroupMask'] = ObjectData_block.get_variable('GroupMask').data
        object_properties['EveryoneMask'] = ObjectData_block.get_variable('EveryoneMask').data
        object_properties['NextOwnerMask'] = ObjectData_block.get_variable('NextOwnerMask').data
        object_properties['OwnershipCost'] = ObjectData_block.get_variable('OwnershipCost').data
        #object_properties['TaxRate'] = ObjectData_block.get_variable('TaxRate').data
        object_properties['SaleType'] = ObjectData_block.get_variable('SaleType').data
        object_properties['SalePrice'] = ObjectData_block.get_variable('SalePrice').data
        object_properties['AggregatePerms'] = ObjectData_block.get_variable('AggregatePerms').data
        object_properties['AggregatePermTextures'] = ObjectData_block.get_variable('AggregatePermTextures').data
        object_properties['AggregatePermTexturesOwner'] = ObjectData_block.get_variable('AggregatePermTexturesOwner').data
        object_properties['Category'] = ObjectData_block.get_variable('Category').data
        object_properties['InventorySerial'] = ObjectData_block.get_variable('InventorySerial').data
        object_properties['ItemID'] = ObjectData_block.get_variable('ItemID').data
        object_properties['FolderID'] = ObjectData_block.get_variable('FolderID').data
        object_properties['FromTaskID'] = ObjectData_block.get_variable('FromTaskID').data
        object_properties['LastOwnerID'] = ObjectData_block.get_variable('LastOwnerID').data
        object_properties['Name'] = ObjectData_block.get_variable('Name').data
        object_properties['Description'] = ObjectData_block.get_variable('Description').data
        object_properties['TouchName'] = ObjectData_block.get_variable('TouchName').data
        object_properties['SitName'] = ObjectData_block.get_variable('SitName').data
        object_properties['TextureID'] = ObjectData_block.get_variable('TextureID').data

        object_list.append(object_properties)

    objects.update_multiple_objects_properties(object_list)

        #objects.update_object_properties(object_properties)
    '''
    // ObjectProperties
    // Extended information such as creator, permissions, etc.
    // Medium because potentially driven by mouse hover events.
    {
    	ObjectProperties Medium 9 Trusted Zerocoded
    	{
    		ObjectData			Variable
    		{	ObjectID		LLUUID	}
    		{	CreatorID		LLUUID	}
    		{	OwnerID			LLUUID	}
    		{	GroupID			LLUUID	}
    		{	CreationDate	U64	}
    		{	BaseMask		U32	}
    		{	OwnerMask		U32	}
    		{	GroupMask		U32	}
    		{	EveryoneMask	U32	}
    		{	NextOwnerMask	U32	}
    		{	OwnershipCost	S32	}
    //		{	TaxRate			F32	}	// F32
    		{	SaleType		U8	}   // U8 -> EForSale
    		{	SalePrice		S32	}
    		{	AggregatePerms	U8	}
    		{	AggregatePermTextures		U8	}
    		{	AggregatePermTexturesOwner	U8	}
    		{	Category		U32	}	// LLCategory
    		{	InventorySerial	S16	}	// S16
    		{	ItemID			LLUUID	}
    		{	FolderID		LLUUID	}
    		{	FromTaskID		LLUUID	}
    		{	LastOwnerID		LLUUID	}
    		{	Name			Variable	1	}
    		{	Description		Variable	1	}
    		{	TouchName		Variable	1	}
    		{	SitName			Variable	1	}
    		{	TextureID		Variable	1	}
    	}
    }
    '''

'''
Object Related Messages


// ObjectAdd - create new object in the world
// Simulator will assign ID and send message back to signal
// object actually created.
//
// AddFlags (see also ObjectUpdate)
// 0x01 - use physics
// 0x02 - create selected
//
// If only one ImageID is sent for an object type that has more than
// one face, the same image is repeated on each subsequent face.
// 
// Data field is opaque type-specific data for this object
{
    ObjectAdd Medium 1 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
        {   GroupID         LLUUID  }
    }
    {
        ObjectData          Single
        {   PCode           U8  }
        {   Material        U8  }
        {   AddFlags        U32 }   // see object_flags.h

        {   PathCurve       U8  }
        {   ProfileCurve    U8  }
        {   PathBegin       U16 }   // 0 to 1, quanta = 0.01
        {   PathEnd         U16 }   // 0 to 1, quanta = 0.01
        {   PathScaleX      U8  }   // 0 to 1, quanta = 0.01
        {   PathScaleY      U8  }   // 0 to 1, quanta = 0.01
        {   PathShearX      U8  }   // -.5 to .5, quanta = 0.01
        {   PathShearY      U8  }   // -.5 to .5, quanta = 0.01
        {   PathTwist       S8  }   // -1 to 1, quanta = 0.01
        {   PathTwistBegin      S8  }   // -1 to 1, quanta = 0.01
        {   PathRadiusOffset    S8  }   // -1 to 1, quanta = 0.01
        {   PathTaperX      S8  }   // -1 to 1, quanta = 0.01
        {   PathTaperY      S8  }   // -1 to 1, quanta = 0.01
        {   PathRevolutions     U8  }   // 0 to 3, quanta = 0.015
        {   PathSkew        S8  }   // -1 to 1, quanta = 0.01
        {   ProfileBegin    U16 }   // 0 to 1, quanta = 0.01
        {   ProfileEnd      U16 }   // 0 to 1, quanta = 0.01
        {   ProfileHollow   U16 }   // 0 to 1, quanta = 0.01

        {   BypassRaycast   U8  }
        {   RayStart        LLVector3   }
        {   RayEnd          LLVector3   }
        {   RayTargetID     LLUUID  }
        {   RayEndIsIntersection    U8  }

        {   Scale           LLVector3   }
        {   Rotation        LLQuaternion    }

        {   State           U8  }
    }
}


// ObjectDelete
// viewer -> simulator
{
    ObjectDelete Low 89 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
        {   Force       BOOL    }   // BOOL, god trying to force delete
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32 }
    }
}


// ObjectDuplicate
// viewer -> simulator
// Makes a copy of a set of objects, offset by a given amount
{
    ObjectDuplicate Low 90 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
        {   GroupID     LLUUID  }
    }
    {
        SharedData          Single
        {   Offset          LLVector3   }
        {   DuplicateFlags  U32         }   // see object_flags.h
    }
    {
        ObjectData          Variable
        {   ObjectLocalID       U32     }
    }
}


// ObjectDuplicateOnRay
// viewer -> simulator
// Makes a copy of an object, using the add object raycast
// code to abut it to other objects.
{
    ObjectDuplicateOnRay Low 91 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID                 LLUUID  }
        {   SessionID               LLUUID  }
        {   GroupID                 LLUUID  }
        {   RayStart                LLVector3   }   // region local
        {   RayEnd                  LLVector3   }   // region local
        {   BypassRaycast           BOOL    }
        {   RayEndIsIntersection    BOOL    }
        {   CopyCenters             BOOL    }
        {   CopyRotates             BOOL    }
        {   RayTargetID             LLUUID  }
        {   DuplicateFlags          U32     }   // see object_flags.h
    }
    {
        ObjectData          Variable
        {   ObjectLocalID           U32     }
    }
}


// MultipleObjectUpdate
// viewer -> simulator
// updates position, rotation and scale in one message
// positions sent as region-local floats
{
    MultipleObjectUpdate Medium 2 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID         LLUUID  }
        {   SessionID       LLUUID  }
    }
    {
        ObjectData      Variable 
        {   ObjectLocalID   U32     }
        {   Type            U8      }
        {   Data            Variable    1   }   // custom type
    }
}

// RequestMultipleObjects
// viewer -> simulator
// reliable
//
// When the viewer gets a local_id/crc for an object that
// it either doesn't have, or doesn't have the current version
// of, it sends this upstream get get an update.
//
// CacheMissType 0 => full object (viewer doesn't have it)
// CacheMissType 1 => CRC mismatch only
{
    RequestMultipleObjects Medium 3 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID       LLUUID  }
    }
    {
        ObjectData  Variable 
        {   CacheMissType   U8  }
        {   ID              U32 }
    }
}


// DEPRECATED: ObjectPosition
// == Old Behavior ==
// Set the position on objects
//
// == Reason for deprecation ==
// Unused code path was removed in the move to Havok4
// Object position, scale and rotation messages were already unified
// to MultipleObjectUpdate and this message was unused cruft.
//
// == New Location ==
// MultipleObjectUpdate can be used instead.
{
    ObjectPosition Medium 4 NotTrusted Zerocoded Deprecated
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32         }
        {   Position        LLVector3   }   // region
    }
}


// DEPRECATED: ObjectScale
// == Old Behavior ==
// Set the scale on objects
//
// == Reason for deprecation ==
// Unused code path was removed in the move to Havok4
// Object position, scale and rotation messages were already unified
// to MultipleObjectUpdate and this message was unused cruft.
//
// == New Location ==
// MultipleObjectUpdate can be used instead.
{
    ObjectScale Low 92 NotTrusted Zerocoded Deprecated
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32         }
        {   Scale           LLVector3   }
    }
}


// ObjectRotation
// viewer -> simulator
{
    ObjectRotation Low 93 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32             }
        {   Rotation        LLQuaternion    }
    }
}


// ObjectFlagUpdate
// viewer -> simulator
{
    ObjectFlagUpdate Low 94 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
        {   ObjectLocalID   U32     }
        {   UsePhysics      BOOL    }
        {   IsTemporary     BOOL    }
        {   IsPhantom       BOOL    }
        {   CastsShadows    BOOL    }
    }
}


// ObjectClickAction
// viewer -> simulator
{
    ObjectClickAction Low 95 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32     }
        {   ClickAction     U8      }
    }
}


// ObjectImage
// viewer -> simulator
{
    ObjectImage Low 96 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData          Variable
        {   ObjectLocalID       U32             }
        {   MediaURL            Variable    1   }
        {   TextureEntry        Variable    2   }
    }
}


{
    ObjectMaterial Low 97 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32 }
        {   Material    U8  }
    }
}


{
    ObjectShape Low 98 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData          Variable
        {   ObjectLocalID   U32 }
        {   PathCurve       U8  }
        {   ProfileCurve    U8  }
        {   PathBegin       U16 }   // 0 to 1, quanta = 0.01
        {   PathEnd         U16 }   // 0 to 1, quanta = 0.01
        {   PathScaleX      U8  }   // 0 to 1, quanta = 0.01
        {   PathScaleY      U8  }   // 0 to 1, quanta = 0.01
        {   PathShearX      U8  }   // -.5 to .5, quanta = 0.01
        {   PathShearY      U8  }   // -.5 to .5, quanta = 0.01
        {   PathTwist       S8  }   // -1 to 1, quanta = 0.01
        {   PathTwistBegin      S8  }   // -1 to 1, quanta = 0.01
        {   PathRadiusOffset    S8  }   // -1 to 1, quanta = 0.01
        {   PathTaperX      S8  }   // -1 to 1, quanta = 0.01
        {   PathTaperY      S8  }   // -1 to 1, quanta = 0.01
        {   PathRevolutions     U8  }   // 0 to 3, quanta = 0.015
        {   PathSkew        S8  }   // -1 to 1, quanta = 0.01
        {   ProfileBegin    U16 }   // 0 to 1, quanta = 0.01
        {   ProfileEnd      U16 }   // 0 to 1, quanta = 0.01
        {   ProfileHollow   U16 }   // 0 to 1, quanta = 0.01
    }
}

{
    ObjectExtraParams Low 99 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData          Variable
        {   ObjectLocalID   U32             }
        {   ParamType       U16             }
        {   ParamInUse      BOOL            }
        {   ParamSize       U32             }
        {   ParamData       Variable    1   }
    }
}


// ObjectOwner
// To make public, set OwnerID to LLUUID::null.
// TODO: Eliminate god-bit. Maybe not. God-bit is ok, because it's
// known on the server.
{
    ObjectOwner Low 100 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        HeaderData      Single
        {   Override    BOOL    }   // BOOL, God-bit.
        {   OwnerID     LLUUID  }
        {   GroupID     LLUUID  }
    }
    {
        ObjectData  Variable
        {   ObjectLocalID   U32 }
    }
}

// ObjectGroup
// To make the object part of no group, set GroupID = LLUUID::null.
// This call only works if objectid.ownerid == agentid.
{
    ObjectGroup Low 101 NotTrusted Zerocoded
    {
        AgentData   Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
        {   GroupID     LLUUID  }
    }
    {
        ObjectData  Variable
        {   ObjectLocalID   U32 }
    }
}

// Attempt to buy an object. This will only pack root objects.
{
    ObjectBuy Low 102 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
        {   GroupID     LLUUID  }
        {   CategoryID  LLUUID  }   // folder where it goes (if derezed)
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32 }
        {   SaleType        U8  }   // U8 -> EForSale
        {   SalePrice       S32 }
    }
}

// viewer -> simulator

// buy object inventory. If the transaction succeeds, it will add
// inventory to the agent, and potentially remove the original.
{
    BuyObjectInventory  Low 103 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        Data    Single
        {   ObjectID    LLUUID  }
        {   ItemID      LLUUID  }
        {   FolderID    LLUUID  }
    }
}

// sim -> viewer
// Used to propperly handle buying asset containers
{
    DerezContainer      Low 104     Trusted Zerocoded
    {
        Data            Single
        {   ObjectID    LLUUID  }
        {   Delete      BOOL    }  // BOOL
    }
}

// ObjectPermissions
// Field - see llpermissionsflags.h
// If Set is true, tries to turn on bits in mask.
// If set is false, tries to turn off bits in mask.
// BUG: This just forces the permissions field.
{
    ObjectPermissions Low 105 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        HeaderData      Single
        {   Override    BOOL    }   // BOOL, God-bit.
    }
    {
        ObjectData  Variable
        {   ObjectLocalID   U32 }
        {   Field       U8  }
        {   Set         U8  }
        {   Mask        U32 }
    }
}

// set object sale information
{
    ObjectSaleInfo Low 106 NotTrusted Zerocoded
    {
        AgentData           Single
        {   AgentID         LLUUID  }
        {   SessionID       LLUUID  }
    }
    {
        ObjectData          Variable
        {   LocalID         U32 }
        {   SaleType        U8  }   // U8 -> EForSale
        {   SalePrice       S32 }
    }
}


// set object names
{
    ObjectName Low 107 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   LocalID     U32 }
        {   Name        Variable    1   }
    }
}

// set object descriptions
{
    ObjectDescription Low 108 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   LocalID     U32 }
        {   Description Variable    1   }
    }
}

// set object category
{
    ObjectCategory Low 109 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   LocalID     U32 }
        {   Category    U32 }
    }
}

// ObjectSelect
// Variable object data because rectangular selection can
// generate a large list very quickly.
{
    ObjectSelect Low 110 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32 }
    }

}


// ObjectDeselect
{
    ObjectDeselect Low 111 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32 }
    }

}

// ObjectAttach
{
    ObjectAttach Low 112 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
        {   AttachmentPoint U8  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32             }
        {   Rotation        LLQuaternion    }
    }
}

// ObjectDetach -- derezzes an attachment, marking its item in your inventory as not "(worn)"
{
    ObjectDetach Low 113 NotTrusted Unencoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32 }
    }
}


// ObjectDrop -- drops an attachment from your avatar onto the ground
{
    ObjectDrop Low 114 NotTrusted Unencoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32 }
    }
}


// ObjectLink
{
    ObjectLink Low 115 NotTrusted Unencoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32 }
    }
}

// ObjectDelink
{
    ObjectDelink Low 116 NotTrusted Unencoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData      Variable
        {   ObjectLocalID   U32 }
    }
}


// ObjectGrab
{
    ObjectGrab Low 117 NotTrusted Zerocoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData          Single
        {   LocalID             U32  }
        {   GrabOffset          LLVector3 }
    }
    {
        SurfaceInfo     Variable
        {   UVCoord     LLVector3 }
        {   STCoord     LLVector3 }
        {   FaceIndex   S32 }
        {   Position    LLVector3 }
        {   Normal      LLVector3 }
        {   Binormal    LLVector3 }
    }
}


// ObjectGrabUpdate
// TODO: Quantize this data, reduce message size.
// TimeSinceLast could go to 1 byte, since capped
// at 100 on sim.
{
    ObjectGrabUpdate Low 118 NotTrusted Zerocoded
    {
        AgentData   Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData  Single
        {   ObjectID            LLUUID  }
        {   GrabOffsetInitial   LLVector3   }   // LLVector3
        {   GrabPosition        LLVector3   }   // LLVector3, region local
        {   TimeSinceLast       U32 }
    }
    {
        SurfaceInfo     Variable
        {   UVCoord     LLVector3 }
        {   STCoord     LLVector3 }
        {   FaceIndex   S32 }
        {   Position    LLVector3 }
        {   Normal      LLVector3 }
        {   Binormal    LLVector3 }
    }

}


// ObjectDeGrab             
{
    ObjectDeGrab Low 119 NotTrusted Unencoded
    {
        AgentData       Single
        {   AgentID     LLUUID  }
        {   SessionID   LLUUID  }
    }
    {
        ObjectData          Single
        {   LocalID             U32  }
    }
    {
        SurfaceInfo     Variable
        {   UVCoord     LLVector3 }
        {   STCoord     LLVector3 }
        {   FaceIndex   S32 }
        {   Position    LLVector3 }
        {   Normal      LLVector3 }
        {   Binormal    LLVector3 }
    }
}


// ObjectSpinStart
{
    ObjectSpinStart Low 120 NotTrusted Zerocoded
    {
        AgentData           Single
        {   AgentID         LLUUID  }
        {   SessionID       LLUUID  }
    }
    {
        ObjectData          Single
        {   ObjectID        LLUUID  }
    }
}


// ObjectSpinUpdate
{
    ObjectSpinUpdate Low 121 NotTrusted Zerocoded
    {
        AgentData           Single
        {   AgentID         LLUUID  }
        {   SessionID       LLUUID  }
    }
    {
        ObjectData          Single
        {   ObjectID        LLUUID  }
        {   Rotation        LLQuaternion }
    }
}


// ObjectSpinStop
{
    ObjectSpinStop Low 122 NotTrusted Zerocoded
    {
        AgentData           Single
        {   AgentID         LLUUID  }
        {   SessionID       LLUUID  }
    }
    {
        ObjectData          Single
        {   ObjectID        LLUUID  }
    }
}

// Export selected objects
// viewer->sim
{
    ObjectExportSelected Low 123 NotTrusted Zerocoded
    {
        AgentData           Single
        {   AgentID         LLUUID  }
        {   RequestID       LLUUID  }
        {   VolumeDetail    S16     }
    }
    {
        ObjectData          Variable
        {   ObjectID        LLUUID  }
    }
}

'''

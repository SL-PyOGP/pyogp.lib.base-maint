"""
@file testDocTests.py
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

import unittest
import doctest

optionflags = doctest.REPORT_ONLY_FIRST_FAILURE | doctest.ELLIPSIS

# setup functions

def setUp(self):
    pass
    # override the default
    #from pyogp.lib.base.network.mockup_client import MockupClient
    #from pyogp.lib.base.network.stdlib_client import StdLibClient
    #from pyogp.lib.base.tests.base import AgentDomain
    
def tearDown(self):
    print "down"

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(
            doctest.DocFileSuite("basics.txt",
                package="pyogp.lib.base.network.tests",
                setUp = setUp,
                tearDown = tearDown,  
                )
            )
    return suite

# Copyright (c) 2012 James McCauley
# Copyright (c) 2013 Balazs Sonkoly
#
# This file is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This file is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.  If not, see <http://www.gnu.org/licenses/>.

"""
Host Controller for Allegra project and SIGCOMM Demo.  This is a
helper module providing the rpc functionaity for the tunproxy-auto.py
software.

  * Host requests available PLE nodes
  * Controller answer: PLE node list
  * Host requests connection to given PLE node
  * Connection parameters are given back (IP, port, name)

"""

from pox.core import core
#from jsonrpc import ServiceMethod
from pox.openflow.of_json import *
from pox.messenger import *
from pox.web.webcore import SplitRequestHandler, StaticContentHandler
from pox.web.jsonrpc import JSONRPCHandler, make_error

log = core.getLogger()

class HostController (object):
  def __init__ (self):
    log.info("HostController init...")
    # core.listen_to_dependencies(self)
    # core.openflow.addListeners(self)
    core.addListeners(self)
    log.info("Done.")

class HostRPCHandler (JSONRPCHandler):

  def _exec_echo(self, msg):
    err = None
    log.info("JSONRPC msg received...")
    log.info("%s", msg)
    return {'result':msg, 'error':err}

  # Get list of available PLE nodes
  def _exec_get_ple_list(self):
    err = None
    log.info("GET PLE list called...")
    # call greedy controller function...
    self._ple_list = core.Outband.get_ple_list()
    #self._ple_list = ["152.66.244.12", "127.0.0.1"]
    log.info("%s", self._ple_list)
    return {'result':self._ple_list, 'error':err}

  def _exec_connect_ple(self, ple_hostnames,
                        host_hostname, host_shortname=None):
    err = None
    args = [ple_hostnames, host_hostname, host_shortname]
    log.info("connect_ple called (%s, %s)" % (host_hostname, host_shortname))
    self._ple_connection = core.Outband.connect_to_ple_node(*args)
    log.info("%s", self._ple_connection)
    return {'result':self._ple_connection, 'error':err}

def launch (username='', password=''):
  def _launch ():
    cfg = {}
    if len(username) and len(password):
      cfg['auth'] = lambda u, p: (u == username) and (p == password)
    core.WebServer.set_handler("/hostconfig/", HostRPCHandler, cfg, True)

  core.registerNew(HostController) 
  core.call_when_ready(_launch, ["WebServer", "openflow"],
                       name = "allegra.host_controller")

# Copyright (c) 2013 Felician Nemeth
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
Similary to the tinytopo module, this one sends (to a poxdesk
application) the link utilization time series.  It is called "tiny"
because it sends every information at each update.
"""

from collections import deque
from pox.core import core
from pox.lib.util import dpidToStr
from pox.lib.recoco import Timer
import pox.messenger as messenger

log = core.getLogger()

class TinyLink (messenger.ChannelBot):
  def __init__ (self):
    core.listen_to_dependencies(self, components=['MessengerNexus', 'FlowStat'])
    #core.FlowStat.addListeners(self)
    self.pending = False
    self.keys  = ['n1-nl', 'n1-de']
    self.keys  = ['subflow 1', 'subflow 2']
    self.data = {}

  def _all_dependencies_met (self):
    self._startup("link_util")

  def get_key (self, dpid, port):
    try:
      node_a = core.Outband.t.dpid(dpid)
      node_b = core.Outband.t.dpid(node_a.neighbor(port=port))
      return '%s-%s' % (node_a.name, node_b.name)
    except AttributeError:
      return "%i:%i" % (dpid, port)

  def send_data (self):
    if self.pending: return
    self.pending = True
    Timer(.2, self._do_send_data, recurring=False)

  def _do_send_data (self):
    assert self.pending
    self.pending = False

    data = []
    keys = []
    for key, val in iter(sorted(self.data.items())):
      l = list(val)
      if sum(l) != 0:
        data.append(l)
        keys.append(key)
    if len(data) == 0:
      data = [[0] * 10]
      keys = ["no traffic"]

    self.send(data=data, keys=keys)

  def _handle_FlowStat_FlowStatEvent (self, event):
    util = event.bw
    key = self.get_key(event.dpid, event.port)
    if key not in self.data:
      self.data[key] = deque( [0] * 10, maxlen=10 );
    self.data[key].append(util)
    self.send_data()
    #log.debug('dpid:%s, port:%s, bw:%s' % (event.dpid, port, util))

def launch ():
  core.registerNew(TinyLink)

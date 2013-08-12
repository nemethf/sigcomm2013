# Copyright (c) 2012, 2013 Felician Nemeth
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


switch     ------*--------------------------------*-------------------------
                / \                              / \
               /   \                          ---   ---
              /     \                        /         \
controller --*-------*----------------------*-----------*------------------>
             A   B   C                      D     E     F               time

D-A == poll_period
C-A != F-D (round-trip time may vary)

We can calculate the data trasmitted between B and E, but we cannot
measure E-B, only estimate it by D-A or F-C.  This bias may or may not
be significant if poll_period is small.

Additionally, we assume that C < D, i.e., if a stat request packet is
eligible for sending and the previous stat reply hasn't arrived, then
we assume it was lost.  Therefore, poll_period can't smaller than RTT.

"""

from pox.core import core
from pox.lib.revent import *
from pox.lib.recoco import Timer
import pox.openflow.libopenflow_01 as of
import time

DEFAULT_POLL_PERIOD      = 3 # seconds

log = core.getLogger()

class LinkUtilEvent (Event):
  def __init__ (self, dpid_1, dpid_2, utilization, bw):
    Event.__init__(self)
    self.dpid_1 = dpid_1
    self.dpid_2 = dpid_2
    self.utilization = utilization
    self.bw = bw

class LinkUtil (EventMixin):
  """
  """

  _eventMixin_events = set([
    LinkUtilEvent,
  ])

  def __init__ (self, poll_period = DEFAULT_POLL_PERIOD):
    core.listen_to_dependencies(self, ['topology', 'openflow'])
    self.poll_period = poll_period
    self.switches = {}
    self.peak = 1 # bps
    core.openflow.addListeners(self)
    log.info("poll_period: %s", self.poll_period)

  def __str__ (self):
    return "poll_period:%s, peak:%s" % (self.poll_period, self.peak)

  def _handle_timer (self, dpid):
    sw = self.switches.get(dpid)
    if sw is None:
      return

    # send stat request
    body = of.ofp_port_stats_request()
    body.port_no = of.OFPP_NONE  # request all port statics
    msg = of.ofp_stats_request(body=body)
    core.openflow.sendToDPID(dpid, msg.pack())

    core.callDelayed(self.poll_period, self._handle_timer, dpid)

  def _get_neighbor (self, dpid, port):
    try:
      sw = core.topology.getEntityByID(dpid)
      neighbors = sw.ports[port].entities
      if len(neighbors) == 1:
        (neighbor,) = neighbors
        return neighbor
    except (KeyError, AttributeError):
      pass
    return None

  def _calculate_peak (self, bw):
    self.peak = max(self.peak, bw)
    return self.peak

  def _handle_PortStatsReceived (self, event): 
    dpid = event.connection.dpid
    sw = self.switches.get(dpid)
    if sw is None:
      return # we can be more clever here
    now = time.time()
    for stats in event.stats:
      current = [now, stats.rx_bytes, stats.tx_bytes]
      if sw.has_key(stats.port_no): # TODO: check XID
        prev = sw[stats.port_no]
        delta = map(lambda x:x[0]-x[1], zip(current, prev))
        bw = max([delta[1]/delta[0], delta[2]/delta[0]])
        peak = self._calculate_peak(bw)
        util = bw / peak
        neighbor = self._get_neighbor(dpid, stats.port_no)
        if neighbor:
          self.raiseEvent(LinkUtilEvent, dpid, neighbor.dpid, util, bw)
          #log.debug('%s %i %s->%s %s (%.2f%%)' % (now, stats.port_no, event.connection.dpid, neighbor.dpid, bw, util))
      sw[stats.port_no] = current

  def _handle_ConnectionUp (self, event):
    sw = self.switches.get(event.dpid)
    if sw is None:
      # New switch
      self.switches[event.dpid] = {}
      core.callDelayed(1, self._handle_timer, event.dpid)

  def _handle_ConnectionDown (self, event):
    try:
      self.switches.pop(event.dpid)
    except KeyError:
      pass

def launch ():
  core.registerNew(LinkUtil)

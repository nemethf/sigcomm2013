# Copyright (c) 2013 Felician Nemeth
#
# This file is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.  If not, see <http://www.gnu.org/licenses/>.
"""
This file started as a general flow statistics module, but somehow it
turned into a special port statistics module that estimates the TCP
traffic towards hosts on switch-host links.

It assumes that flow entries corresponding to port #n has priority of
OFP_DEFAULT_PRIORITY + n
"""

from collections import defaultdict
from pox.core import core
from pox.lib.revent import *
from pox.lib.recoco import Timer
import pox.openflow.libopenflow_01 as of
import time

DEFAULT_POLL_PERIOD      = 1 # seconds

log = core.getLogger()

class FlowStatEvent (Event):
  def __init__ (self, dpid, port, bw):
    Event.__init__(self)
    self.dpid = dpid
    self.port = port
    self.bw = bw

class FlowStat (EventMixin):
  """
  """

  _eventMixin_events = set([
    FlowStatEvent,
  ])

  def __init__ (self, poll_period = DEFAULT_POLL_PERIOD):
    core.listen_to_dependencies(self, ['openflow'])
    self.poll_period = poll_period
    self.switches = {}
    core.openflow.addListeners(self)
    log.info("poll_period: %s", self.poll_period)

  def __str__ (self):
    return "poll_period:%s" % (self.poll_period, )

  def _handle_timer (self, dpid):
    sw = self.switches.get(dpid)
    if sw is None:
      return

    # send stat request
    body = of.ofp_flow_stats_request()
    ## DAMN! stats can't be requested based on priority.
    #body.priority = of.OFP_DEFAULT_PRIORITY + 1
    msg = of.ofp_stats_request(body=body)
    core.openflow.sendToDPID(dpid, msg.pack())

    core.callDelayed(self.poll_period, self._handle_timer, dpid)

  def _handle_FlowStatsReceived (self, event): 
    dpid = event.connection.dpid
    sw = self.switches.get(dpid)
    if sw is None:
      return # we can be more clever here
    now = time.time()
    bytes = defaultdict(int)
    for stats in event.stats:
      if (stats.priority > of.OFP_DEFAULT_PRIORITY and
          stats.priority < of.OFP_DEFAULT_PRIORITY + 50):
        port = stats.priority - of.OFP_DEFAULT_PRIORITY - 1
        bytes[port] += stats.byte_count
    for port in bytes.keys():
      if len(sw) == 2:
        if port in sw['bytes']:
          delta_t = now - sw['time']
          delta_bytes = bytes[port] - sw['bytes'][port]
          if delta_bytes < 0:
            #counter overflow, 
            delta_bytes = 0 # FIXME: += MAX
          bw = delta_bytes / delta_t
          self.raiseEvent(FlowStatEvent, dpid, port, bw)
          log.debug('%s %s:%s %s' % (now, dpid, port, bw))
      else:
        sw['bytes'] = defaultdict(int)
      sw['bytes'][port] = bytes[port]
    sw['time'] = now

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
  core.registerNew(FlowStat)

# Copyright 2012 James McCauley
# Copyright (c) 2013 Felician Nemeth
#
# This file is NOT part of POX.
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
This module extends the tinytopo of poxdesk with
  - sending link utilization information,
  - listening to host_tracker events,

"""

from pox.core import core
from pox.lib.util import dpidToStr
import pox.messenger as messenger
import poxdesk.tinytopo as parent


log = core.getLogger()

class TinyUtilTopo (parent.TinyTopo):
  def __init__ (self):
    parent.TinyTopo.__init__(self)
    core.listen_to_dependencies(self, components=['LinkUtil'])
    core.LinkUtil.addListeners(self)
    self.util = {}
    self.node_type = {}
    self.min = None
    self.max = None

  def _add_position (self, d, switch):
    try:
      x, y = core.Outband.t.name(switch).position
    except AttributeError:
      pass
    pos = complex(x, y)
    if self.min == None:
      self.min = pos - 1 - 1j
      self.max = pos + 1 + 1j
    self.min = min(self.min.real, x) + 1j * min(self.min.imag, y)
    self.max = max(self.max.real, x) + 1j * max(self.max.imag, y)

    pos = complex(x, y)
    pos = pos - self.min
    pos = (       pos.real / (self.max - self.min).real +
               1j * (pos.imag / (self.max - self.min).imag) )
    pos = 10 * pos + complex(-5, -5)

    d['x'], d['y'] = (pos.real, pos.imag)
    #d['label'] = '%.1f,%.1f' % (d['x'], d['y'])

  def _add_geo_coord (self, d, switch):
    try:
      lat, lon = core.Outband.t.name(switch).geo_coords
    except AttributeError:
      return
    d['latitude'], d['longitude'] = lat, lon

  def _do_send_table (self):
    assert self.pending
    self.pending = False
    switches = {}
    for s in self.switches:
      d = {'label':s}
      if s in self.node_type:
        d['type'] = self.node_type[s]
      #self._add_position(d, s)
      self._add_geo_coord(d, s)
      switches[s] = d
    edges = []
    for e in self.links:
      if e[0] not in switches: continue
      if e[1] not in switches: continue
      util = max(self.util.get((e[0], e[1]), 0),
                 self.util.get((e[1], e[0]), 0))
      try:
        if core.Outband.t.link(e[0], e[1]).is_hidden():
          continue
      except AttributeError:
        pass
      edges.append(e + (util,))

    #print self.switches,switches
    #print self.links,edges

    self.send(topo={'links':edges,'switches':switches})

  def dpid_to_str (self, dpid):
    try:
      sw = core.Outband.t.dpid(dpid).name
    except AttributeError:
      sw = dpidToStr(dpid)
    return sw

  def _handle_LinkUtil_LinkUtilEvent (self, event):
    s1 = self.dpid_to_str(event.dpid_1)
    s2 = self.dpid_to_str(event.dpid_2)
    util = event.bw
    current = self.util.get((s1, s2), 0)
    self.util[(s1, s2)] = round(util, 3)
    if current:
      rel_diff = abs(current - util) / float(current)
      if rel_diff < 0.01:
        return
    else:
      if current == util:
        return
    self.send_table()

  def _handle_openflow_ConnectionUp (self, event):
    self.switches.add( self.dpid_to_str(event.dpid) )
    self.send_table()

  def _handle_openflow_ConnectionDown (self, event):
    try:
      key = self.dpid_to_str(event.dpid)
      self.switches.remove(key)
    except KeyError:
      return
    for link in [l for l in self.links if l[0]==key or l[1]==key]:
      self.links.remove(link)
    self.send_table()

  def _handle_openflow_discovery_LinkEvent (self, event):
    #print "LE"
    s1 = event.link.dpid1
    s2 = event.link.dpid2
    if s1 > s2: s1,s2 = s2,s1
    s1 = self.dpid_to_str(s1)
    s2 = self.dpid_to_str(s2)

    if event.added:
      self.links.add((s1,s2))
    elif event.removed and (s2,s2) in self.links:
      self.links.remove((s1,s2))

    self.send_table()

  def _get_link (self, a, b):
    if (a, b) in self.links:
      return (a, b)
    elif (b, a) in self.links:
      return (b, a)
    return None

  def _handle_host_tracker_HostEvent(self, event):
    host_mac  = str(event.entry.macaddr)
    host_dpid = str(event.entry.dpid)
    host_port = str(event.entry.port)
    # mac address of the switch to which the host is connected
    switch_of_host= self.dpid_to_str(event.entry.dpid)
    host_ipAddr = str(event.entry.ipAddrs) # this is a null string, i.e., ""

    hosts = dict()
    host_node = core.Outband.t.mac(host_mac)
    if host_node is not None:
      H = host_node.name
    else:
      H = "H-" + host_mac

    if event.leave:
      log.info("host (%s,%s) left" % (H, host_mac))
      if H in self.switches:
        # first check that link did exist in the set self.links
        if self._get_link(H, switch_of_host):
          log.debug("Removing link (" + H + " - " + switch_of_host + ")")
          self.links.remove(self._get_link(H, switch_of_host))
        else:
          log.warn("Link between " + H + " and " + switch_of_host +
                   " did not exist...nothing to remove")
        if not [True for a, b in self.links if a == H or b == H]:
          self.switches.remove(H)
          self.node_type.pop(H, None)
          log.debug("host (" + H + ") removed from switches")
      else:
        log.debug("host (" + H + ") was not in the switches")
    else:
      log.info("host (" + H + ") appeared")
      # creating a dictinary with hosts as key and the switch to which
      # they are connected as values
      hosts[H] = switch_of_host

      self.switches.add(H)
      self.node_type[H] = 'host'
      if host_node and host_node.qemu:
        self.node_type[H] = 'qemu'

      # connecting the host to the corresponding swich
      for h in hosts:
        s1 = h
        s2 = hosts[h]
        log.debug("Adding link from " + s1 + " to " + s2)
        self.links.add((s1,s2))

    log.debug("iterating links...")
    for i in self.links:
      log.debug(i)

    # refreshing poxdesk topoviewer
    self.send_table()

def launch ():
  core.registerNew(TinyUtilTopo)

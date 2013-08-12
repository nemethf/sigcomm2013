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
ASDF
"""

import time
import random
import inspect
from math import pow
from os import path, fsync
from random import choice

from pox.core import core
from pox.lib.util import dpid_to_str
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.packet.vlan import vlan
from pox.lib.packet.ipv4 import ipv4
from pox.lib.addresses import *
from pox.lib.revent import EventHalt, EventContinue
import pox.openflow.libopenflow_01 as of

# Timeout for flows
FLOW_IDLE_TIMEOUT = 10
FAILOVER_PRIORITY = of.OFP_DEFAULT_PRIORITY + 100
ETH_LABEL = EthAddr(b"\xee\xee\xee\xee\xee\xee")

log = core.getLogger()

class GreedyRouting (object):
  def __init__ (self):
    self.first = True
    core.openflow.addListeners(self)
    core.addListeners(self)
 
  def ip_to_coords (self, ipaddr):
    net = ipaddr.toUnsignedN()
    x = net / (256*256)
    y = net % (256*256)
    return [x, y]

  def distance (self, coords, dpid):
    n = core.Outband.t.dpid(dpid)
    [a_x, a_y] = [ int(n.x), int(n.y) ]
    [b_x, b_y] = coords
    d = pow(a_x - b_x, 2) + pow(a_y - b_y, 2)

    log.debug("distance %d = %d (%i,%i)<>(%i,%i)", dpid, d, b_x, b_y, a_x, a_y)
    return d

  def multipath_choice (self, distances, dpid, inport, ip, tcp):
    # TODO use hash key based on ip.srcip, ip.dstip, tcp.srcport tcp.dstport
    return choice(distances)[0]

  def _handle_PacketIn (self, event):
    dpid = event.connection.dpid
    inport = event.port
    packet = event.parsed
    if not packet.parsed:
      log.warn("%s %i ignoring unparsed packet", dpid_to_str(dpid), inport)
      return

    ip = packet.find('ipv4')
    if ip is None:
      log.warn("%s %i ignoring non-ipv4 packet", dpid_to_str(dpid), inport)
      return

    tcp = packet.find('tcp')

    node = core.Outband.t.dpid(dpid)
    if node is None:
      log.warn('%s unknown dpid %i', dpid_to_str(dpid), dpid)

    d = self.ip_to_coords(ip.dstip)
    current_distance = self.distance(d, dpid)
    neighbors = node.neighbors
    distances = [ [n, self.distance(d, n)] for n in neighbors ]

    distances = filter(lambda x: x[1] < current_distance, distances)
    distances = filter(lambda x:
                         node.port_num(core.Outband.t.dpid(x[0])) != inport,
                       distances)

    if distances == []:
      out_dpid = None
    elif tcp is None:
      distances.sort(lambda x, y: cmp(x[1], y[1]))
      out_dpid = distances[0][0]
    else:
      out_dpid = self.multipath_choice(distances, dpid, inport, ip, tcp)

    actions = []
    mac = None

    if tcp is None:
      str_flow = '%s:xxx => %s:xxx' % (ip.srcip, ip.dstip)
    else:
      str_flow = '%s:%d => %s:%d' % (ip.srcip, tcp.srcport, ip.dstip, tcp.dstport)
    if out_dpid:
      node_out = core.Outband.t.dpid(out_dpid)
      port_out = node.port(node_out)
      mac = port_out.mac
      str_out = '%i %i' % (out_dpid, port_out.num)
    else:
      str_out = 'dead end'
    log.info('%s %i %s %s', dpid_to_str(dpid), inport, str_flow, str_out)

    if mac:
      actions.append(of.ofp_action_dl_addr.set_dst(mac))
    if out_dpid:
      actions.append(of.ofp_action_output(port = port_out.num))

    match = of.ofp_match.from_packet(packet, inport)
    match.dl_src = None # Wildcard MAC addresses
    match.dl_dst = None

    msg = of.ofp_flow_mod(command=of.OFPFC_ADD,
                          idle_timeout=FLOW_IDLE_TIMEOUT,
                          hard_timeout=of.OFP_FLOW_PERMANENT,
                          buffer_id=event.ofp.buffer_id,
                          actions=actions,
                          match=match)
    event.connection.send(msg.pack())

    return

class RRRouting (GreedyRouting):
  """Round robin multipath greedy routing"""

  def __init__ (self):
    super( RRRouting, self ).__init__()
    self.past_choice = {}
    self.random = random.Random()

  def multipath_choice (self, distances, dpid, inport, ip, tcp):
    #log.debug('%s %s %s %s' % (dpid, inport, ip.srcip, tcp.srcport))
    #simple load balancer: current choice must be different from the previous one
    #key = '%s-%s-%s' % (dpid, inport, ip.dstip)
    key = '%s-%s' % (dpid, inport)
    l = len(distances)
    try:
      prev = self.past_choice[key]
    except KeyError:
      prev = self.random.randint(1, l)
    current = prev + 1
    self.past_choice[key] = current
    log.debug('key:%s,current:%s' % (key, current))
    return distances[current % l][0]

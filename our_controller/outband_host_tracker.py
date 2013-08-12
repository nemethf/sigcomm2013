# Copyright 2011 Dorgival Guedes
# Copyright 2013 James McCauley
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
Hosttracker is not very effective in our case, since there aren't many
packet-ins due to proactive routing.  Moreover, ARP pings tend to loss
on congested links.  Luckly, we know where the hosts supposed to be.

This module periodically sends ARP pings to the alleged
host-locations.  The replies are taken care of the normal host_tracker
module.  However, host_tracker doesn't register hosts into Topology,
so this module handles the registration.  (The "linkutil" module
expects the hosts to be part of the Topology.)

Somehow, sliver-openvswitch-1.9.90-3.onelab.i686 seems buggy,
but      sliver-openvswitch-1.9.90-2.onelab.i686 is OK.
(ple02.fc.univie.ac.at misunderstands ports in packet-outs. I set port
2 and packets are sent through port 1.)
"""
import time

from pox.core import core
from pox.lib.recoco import Timer
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.packet.arp import arp
from pox.lib.addresses import EthAddr, IPAddr
from pox.topology.topology import Host
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

class OutbandHostTracker (object):

  def __init__ (self, timeout = 10):
    self.timeout = timeout
    self._t = Timer(self.timeout, self._check_timeouts, recurring=True)
    core.addListeners(self)
    core.host_tracker.addListeners(self)

  def __str__ (self):
    return str(self.timeout)

  def _check_timeouts (self):
    for node in core.Outband.t.nodes:
      if node.external:
        for neighbor in node.neighbors:
          neighbor_port_num = core.Outband.t.dpid(neighbor).port_num(node)
          port = node.port(neighbor)
          if port.ip and port.mac:
            self._send_ping(neighbor, neighbor_port_num, port.mac, port.ip)

  def _send_ping (self, src_dpid, src_port, dst_mac, dst_ip):
    """
    Builds an ETH/IP any-to-any ARP packet (an "ARP ping")
    """
    if src_port < 0:
      return
    r = arp()
    r.opcode = arp.REQUEST
    r.hwdst = EthAddr(dst_mac)
    r.hwsrc = core.host_tracker.ping_src_mac
    r.protodst = IPAddr(dst_ip)
    # src is IP_ANY
    e = ethernet(type=ethernet.ARP_TYPE, src=r.hwsrc, dst=r.hwdst)
    e.payload = r
    log.debug("%i %i sending ARP REQ to %s %s",
              src_dpid, src_port, str(r.hwdst), str(r.protodst))
    msg = of.ofp_packet_out(data = e.pack(),
                            action = of.ofp_action_output(port=src_port))
    core.openflow.sendToDPID(src_dpid, msg.pack())

  def _handle_HostEvent (self, event):
    entry = event.entry
    if event.move:
      log.warn('cannot handle moving hosts (%s)' % entry)
      return
    host = core.topology.getEntityByID(entry.macaddr)
    if host is None:
      host = Host(entry.macaddr)
      core.topology.addEntity(host)
      if core.Outband.t.mac(entry.macaddr):
        host.dpid = core.Outband.t.mac(entry.macaddr).dpid
      else:
        log.debug('mac not found %s' % entry.macaddr)
        val = 0
        for i, v in enumerate(entry.macaddr.toTuple()):
          val += (256 ** (5 - i)) * v
        host.dpid = val

    sw = core.topology.getEntityByID(entry.dpid)
    if sw is None:
      log.warn('unknown host (%s)' % entry.dpid)
      return
    if event.entry.port not in sw.ports:
      log.warn('unknown port (%s, %s)' % (entry.dpid, entry.port))
      return
    if event.join:
      log.debug('join (%s %s)' % (sw, host.id))
      sw.ports[entry.port].addEntity(host, single=True)
    else:
      log.debug('leave (%s %s)' % (sw, host.id))
      sw.ports[entry.port].entities.discard(host)

def launch (timeout = 10):
  core.registerNew(OutbandHostTracker, timeout)

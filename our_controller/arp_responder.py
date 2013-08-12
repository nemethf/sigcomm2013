# Copyright 2011,2012 James McCauley
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
This module answers ARP request based on out-of-band information
provided by the outband module.
"""

from pox.core import core
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.packet.arp import arp
from pox.lib.addresses import EthAddr
from pox.lib.revent import EventHalt
from pox.lib.util import dpid_to_str
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

class ArpResponder (object):
  def __init__ (self):
    self.first = True
    core.openflow.addListeners(self)
    core.addListeners(self)

  def _dpid_to_mac (self, dpid):
    # Should maybe look at internal port MAC instead?
    return EthAddr("%012x" % (dpid & 0xffFFffFFffFF,))

  def _handle_PacketIn (self, event):
    dpid = event.connection.dpid
    inport = event.port
    packet = event.parsed
    a = packet.find('arp')
    if not a:
        return

    arp_type = {arp.REQUEST:"request",arp.REPLY:"reply"}.get(a.opcode,
                                                      'op:%i' % (a.opcode,))
    log_str = "%s ARP %s %s => %s" % (dpid_to_str(dpid), arp_type,
                                      str(a.protosrc), str(a.protodst))
    if arp_type == 'reply':
      log.debug(log_str)
    else:
      log.info(log_str)

    eat = False
    dst_mac = None
    dst_dpid = None
    dst_node, dst_port = core.Outband.t.ip_and_port(a.protodst)
    if dst_node is None:
      eat = True
    else:
      dst_dpid = dst_node.dpid
    if dst_dpid is None:
      eat = True
    else:
      dst_mac = dst_port.mac
    if dst_mac is None:
      eat = True

    if (not eat) and (a.prototype == arp.PROTO_TYPE_IP):
      if a.hwtype == arp.HW_TYPE_ETHERNET:
        if a.protosrc != 0:
          if a.opcode == arp.REQUEST:
            # we can answer everything
            r = arp()
            r.hwtype = a.hwtype
            r.prototype = a.prototype
            r.hwlen = a.hwlen
            r.protolen = a.protolen
            r.opcode = arp.REPLY
            r.hwdst = a.hwsrc
            r.protodst = a.protosrc
            r.protosrc = a.protodst
            #r.hwsrc = ETHER_BROADCAST
            r.hwsrc = dst_mac
            e = ethernet(type=ethernet.ARP_TYPE,
                         src=self._dpid_to_mac(dpid), dst=a.hwsrc)
            e.payload = r

            if packet.type == ethernet.VLAN_TYPE:
              v_rcv = packet.find('vlan')
              e.next = vlan(eth_type = e.type,
                            next = e.payload,
                            id = v_rcv.id,
                            pcp = v_rcv.pcp)
              e.type = ethernet.VLAN_TYPE

            log.info("%s answering ARP for %s" %
                     (dpid_to_str(dpid), str(r.protosrc)))
            msg = of.ofp_packet_out()
            msg.data = e.pack()
            msg.actions.append(of.ofp_action_output(port =
                                                    of.OFPP_IN_PORT))
            msg.in_port = inport
            event.connection.send(msg)
            return # EventHalt

    # Didn't know how to handle this ARP, so just ignoring it
    msg = "%s ignoring ARP %s %s => %s" % (dpid_to_str(dpid),
        {arp.REQUEST:"request",arp.REPLY:"reply"}.get(a.opcode,
        'op:%i' % (a.opcode,)), a.protosrc, a.protodst)
    log.debug(msg)

    return # EventHalt
 
def launch ():
  core.registerNew(ArpResponder)

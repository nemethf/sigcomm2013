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
This seems like an evolutionary dead-end.
"""

from pox.core import core
from pox.lib.util import dpid_to_str
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.addresses import *
from pox.lib.packet.ipv4 import ipv4
from pox.lib.revent import EventHalt, EventContinue
import pox.openflow.libopenflow_01 as of

from greedy import GreedyRouting

class PredefinedRouting (GreedyRouting):
  """Use predefined routes if found, greedy routing otherwise."""

  def __init__ (self):
    super( PredefinedRouting, self ).__init__()

  def _install_flow (self, event, p, c, n):
    """Install a flow entry at c to forward packet coming form p to n"""
    packet = event.parsed
    actions = []
    mac = None

    ip  = packet.find('ipv4')
    tcp = packet.find('tcp')
    str_flow = '%s:%d => %s:%d' % (ip.srcip, tcp.srcport, ip.dstip, tcp.dstport)

    node_p = core.Outband.t.name(p)
    node_c = core.Outband.t.name(c)
    node_n = core.Outband.t.name(n)

    inport  = node_c.port(node_p)
    outport = node_c.port(node_n)

    mac = node_n.port(node_c).mac
    str_out = '%i %i' % (n_dpid, outport.num)
    log.info('%s %i %s %s', dpid_to_str(c_dpid), inport.num, str_flow, str_out)

    if mac:
      actions.append(of.ofp_action_dl_addr.set_dst(mac))
    actions.append(of.ofp_action_output(port = outport.num))

    match = of.ofp_match.from_packet(packet, inport.num)
    match.dl_src = None # Wildcard MAC addresses
    match.dl_dst = None

    if event.connection.dpid == c_dpid:
      buffer_id = event.ofp.buffer_id
      time.sleep(0.1)           # we should use barriers instead
    else:
      buffer_id = None

    msg = of.ofp_flow_mod(command=of.OFPFC_ADD,
                          idle_timeout=FLOW_IDLE_TIMEOUT,
                          hard_timeout=of.OFP_FLOW_PERMANENT,
                          buffer_id=buffer_id,
                          actions=actions,
                          match=match)
    core.openflow.sendToDPID(c_dpid, msg.pack())
    return

  def _install_port_down (self, dpid, port_no, down = True, duration = 1):
    "Simulate port_down by dropping all incoming packets."
    con = core.openflow.getConnection(dpid)
    p = con.ports[port_no]
    if down:
      s = 'down'
      command = of.OFPFC_ADD
    else:
      s = 'up'
      command = of.OFPFC_DELETE_STRICT
    log.info('%s CHANGE_PORT( dpid:%s, port_no:%s, dir:%s )' % (time.time(), dpid, port_no, s))

    match = of.ofp_match(in_port = port_no)
    match.in_port = port_no
    #match.dl_type = ethernet.VLAN_TYPE
    actions = [] # Drop!

    msg = of.ofp_flow_mod(command=command,
                          hard_timeout=duration, # of.OFP_FLOW_PERMANENT,
                          actions=actions,
                          priority=0xffff, # maximal
                          match=match)
    
    con.send(msg.pack())
    return

  def _change_port (self, dpid, port_no, down):
    con = core.openflow.getConnection(dpid)
    p = con.ports[port_no]
    log.info('%s' % con.ports)
    if down:
      s = 'down'
    else:
      s = 'up'
    log.info('change_port( dpid:%s, port_no:%s, dir:%s )' % (dpid, port_no, s))

    new_state = down * of.OFPPC_PORT_DOWN
    new_state = of.OFPPC_PORT_DOWN \
        | of.OFPPC_NO_STP \
        | of.OFPPC_NO_RECV \
        | of.OFPPC_NO_RECV_STP \
        | of.OFPPC_NO_FLOOD \
        | of.OFPPC_NO_FWD \
        | of.OFPPC_NO_PACKET_IN
    log.info('change_port: new_state: %d %s ' % (new_state, con.info))

    pm = of.ofp_port_mod( port_no=p.port_no,
                          hw_addr=p.hw_addr,
                          config = new_state,
                          mask = new_state ) # of.OFPPC_PORT_DOWN )
    con.send(pm)

    body = of.ofp_port_stats_request()
    body.port_no = of.OFPP_NONE  # request all port statics
    msg = of.ofp_stats_request(body=body)
    con.send(msg.pack())


  def _handle_PortStatus (self, event):
    log.info('PortStatus: %s, dpid:%s, port:%s %s' %
             (time.time(), event.dpid, event.port, 
              event.ofp.desc.show()))

  def _handle_PacketIn (self, event):
    dpid = event.connection.dpid
    packet = event.parsed

    if not packet.parsed:
      log.warn("%s %i ignoring unparsed packet", dpid_to_str(dpid), inport.num)
      return

    if packet.find('lldp'):
      return

    ip = packet.find('ipv4')
    if ip and packet.find('tcp'):
      node_str = core.Outband.t.dpid(dpid).name
      src_str  = core.Outband.t.ip(ip.srcip).name
      dst_str  = core.Outband.t.ip(ip.dstip).name

      #log.info('%s.%s.%s', node_str, src_str, dst_str)
      route = None
      for i,r in enumerate(core.Outband.routes):
        #log.info('r-%s', r)
        if r[0] == src_str and r[1] == node_str and r[-1] == dst_str:
          route = r
          break
      if route:
        if not ('permanent' in core.Outband.route_properties[i]):
          del(core.Outband.routes[i])
        log.info('r-%s', route)

        if self.first:
          start = 10
          duration = 1
          core.callDelayed(start, self._install_port_down, 1, 1, 1, duration=0)
          core.callDelayed(start, self._install_port_down, 2, 3, 1, duration=0)
          core.callDelayed(start+duration, self._install_port_down, 1, 1, 0, duration=0)
          core.callDelayed(start+duration, self._install_port_down, 2, 3, 0, duration=0)
          self.first = False

        hops = zip(route[0:],route[1:],route[2:])
        hops.reverse()
        for p,c,n in hops:
          self._install_flow(event, p, c, n)
        return

    super( PredefinedRouting, self )._handle_PacketIn(event)

def launch ():
  core.register("routing", PredefinedRouting())

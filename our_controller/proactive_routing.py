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
Installs routes proactively.  Routes are taken from the outband module
in the from of [hostname, switchname, ..., switchname, hostname].
This module has a lots of extra stuff and hacks which we don't use
anymore.
"""

import time
import multiprocessing

from pox.core import core
from pox.lib.util import dpid_to_str
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.addresses import *
from pox.lib.packet.ipv4 import ipv4
from pox.lib.revent import EventHalt, EventContinue
import pox.openflow.libopenflow_01 as of

# Timeout for flows
FLOW_IDLE_TIMEOUT = 10
FAILOVER_PRIORITY = of.OFP_DEFAULT_PRIORITY + 100
ETH_LABEL = EthAddr(b"\xee\xee\xee\xee\xee\xee")

log = core.getLogger()
reset_lock = multiprocessing.Lock()

class ProactiveRouting (object):
  """Install routing tables proactively."""

  def __init__ (self):
    self.prev_change_port = None
    self.log_file = open("/tmp/pox_log", "w")
    self.barrier_log_file = open("/tmp/barrier_log", "w")
    self._pending_barriers = {}
    self._prev_barrier_arrived = {}
    self._xid_generator = of.xid_generator()
    core.openflow.addListeners(self)
    core.Outband.addListeners(self)
    core.addListeners(self)

    super( ProactiveRouting, self ).__init__()

  # def __str__ (self):
  #   return self.file_prefix

  def _install_flow (self, p, c, n, port_src, port_dst = None,
                     **kw):
    """Install a flow entry at c to forward packet coming form p to n"""

    node_p = core.Outband.t.name(p)
    node_c = core.Outband.t.name(c)
    node_n = core.Outband.t.name(n)
    inport  = node_c.port(node_p)
    outport = node_c.port(node_n)
    if not inport:
      log.error('%s->%s: not found' % (node_c.name, node_p.name))
      return
    if not outport:
      log.error('%s->%s: not found' % (node_c.name, node_n.name))
      return

    nw_src = nw_dst = None
    info_src = info_dst = ""
    if port_src:
      nw_src = port_src.ip
      info_src = "%s(%s) => " % (port_src.parent.name, nw_src)
    if port_dst:
      nw_dst = port_dst.ip
      info_dst = " => %s(%s)" % (port_dst.parent.name, nw_dst)

    backport = node_n.port(node_c)
    if backport:
      mac = backport.mac
    else:
      log.error('%s->%s: link not found' % (node_n.name, node_c.name))
      return

    str_from = "%s.%s" % (dpid_to_str(node_c.dpid), c)
    str_out  = "%s.%s" % (dpid_to_str(node_n.dpid), n)
    eth_in, eth_out = '', ''
    if mac:
      eth_out = '!'

    if not outport or outport < 0 or not inport.num or inport.num < 0:
      log.error('unknown port: %s %s->%s %s' %
                (str_from, inport.num, outport.num, str_out))
      return

    actions = []
    if not mac and 'add_eth_label' in kw:
      mac = ETH_LABEL
      eth_out = '+'
    if not mac and 'del_eth_label' in kw:
      mac = ETHER_BROADCAST
      eth_out = '-'
    if mac:
      actions.append(of.ofp_action_dl_addr.set_dst(mac))
    actions.append(of.ofp_action_output(port = outport.num))

    match = of.ofp_match(in_port = inport.num,
                         #nw_proto = ipv4.TCP_PROTOCOL,
                         #dl_vlan = 1301,
                         #dl_type = ethernet.VLAN_TYPE,
                         dl_type = ethernet.IP_TYPE,
                         nw_src = nw_src, #None,
                         nw_dst = nw_dst )
    match.adjust_wildcards = False
    if 'with_eth_label' in kw or 'del_eth_label' in kw:
      match.dl_dst = ETH_LABEL
      eth_in = '*'

    if port_src and port_src.mac:
      match.dl_src = port_src.mac
    else:
      #log.error('unknown port_src.mac')
      return

    priority = of.OFP_DEFAULT_PRIORITY
    if 'add_eth_label' in kw:
      priority = FAILOVER_PRIORITY
    if mac:
      priority = of.OFP_DEFAULT_PRIORITY + 1 + outport.num
    if 'priority' in kw:
      priority = kw['priority']

    if 'failover_entry' in kw:
      mark = '=>'
    else:
      mark = '->'

    if 'udp' in kw:
      match.nw_proto = ipv4.UDP_PROTOCOL

    log.info('%s%s %i%s%s%s%i %s%s',
             info_src, str_from, 
             inport.num, eth_in, mark, eth_out, outport.num,
             str_out, info_dst)

    msg = of.ofp_flow_mod(command=of.OFPFC_ADD,
                          idle_timeout=of.OFP_FLOW_PERMANENT,
                          hard_timeout=of.OFP_FLOW_PERMANENT,
                          actions=actions,
                          match=match,
                          priority=priority
                          )
    if 'failover_entry' in kw:
      self._add_failover_entry(c, msg)
    else:
      core.openflow.sendToDPID(node_c.dpid, msg.pack())

    if (not ('udp' in kw)) and outport.mac:
      #sending to destination, separte udp traffic 
      self._install_flow(p, c, n, port_src, port_dst,
                         udp = True, priority = of.OFP_DEFAULT_PRIORITY + 99,
                         **kw)

    return

  def _add_failover_entry (self, str_node, msg):
    if not hasattr(self, '_failover_entries'):
      self._failover_entries = {}
      self._failover_del_entries = {}
    if not str_node in self._failover_entries:
      self._failover_entries[str_node] = []
      self._failover_del_entries[str_node] = []

    self._failover_entries[str_node].append(msg.pack())
    msg.command=of.OFPFC_DELETE_STRICT
    self._failover_del_entries[str_node].append(msg.pack())


  def _install_failover_entries (self, str_node):
    dpid = core.Outband.t.name(str_node).dpid
    con = core.openflow.getConnection(dpid)
    for packed_msg in self._failover_entries[str_node]:
      con.send(packed_msg)

  def _delete_failover_entries (self, str_node):
    dpid = core.Outband.t.name(str_node).dpid
    con = core.openflow.getConnection(dpid)
    for packed_msg in self._failover_del_entries[str_node]:
      con.send(packed_msg)
    #log.warn('_delete_failover_entries %s' % str_node)

  def _clear_flowtable (self, dpid):
    msg = of.ofp_flow_mod(match=of.ofp_match(),command=of.OFPFC_DELETE)
    core.openflow.sendToDPID(dpid, msg.pack())

  def _install_port_down (self, dpid, port_no, down = True, duration = 60,
                          write_log = False):
    "Simulate port_down by dropping all incoming packets."
    con = core.openflow.getConnection(dpid)
    p = con.ports[port_no]
    if down:
      s = 'down'
      command = of.OFPFC_ADD
    else:
      s = 'up'
      command = of.OFPFC_DELETE_STRICT
    now = time.time()
    if self.prev_change_port is None:
      diff_str = "*"
    else:
      diff_str = now - self.prev_change_port
    self.prev_change_port = now
    #log.info('%s CHANGE_PORT( dpid:%s, port_no:%s, dir:%s ) %s' %
    #         (time.time(), dpid, port_no, s, diff_str))
    if write_log:
      self.log_file.write("%s\n" % diff_str)
      self.log_file_last.write("%s\n" % diff_str)

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
    self._send_barrier(con)
    return

  def _send_barrier (self, con):
    barrier_xid = self._xid_generator()
    self._pending_barriers[barrier_xid] = time.time()
    con.send(of.ofp_barrier_request(xid=barrier_xid))
    #log.info("barrier (%s) sent to %s" % (barrier_xid, con.dpid))

  def _handle_BarrierIn (self, barrier):
    xid = barrier.xid
    dpid = barrier.dpid
    if xid in self._pending_barriers:
      start = self._pending_barriers[xid]
      end = time.time()
      rtt = end - start
      #log.info('%s barrier arrived with %f, remaining: %i' %
      #         (dpid_to_str(dpid), rtt,
      #          len(self._pending_barriers)))
      del self._pending_barriers[xid]
      if dpid in self._prev_barrier_arrived:
        a = self._prev_barrier_arrived[dpid]
        #log.info("%s diff between barrier rtts: %f" % 
        #         (dpid_to_str(dpid), rtt2-rtt))
        self.barrier_log_file.write("%i %s\n" % (dpid, end-a))
        self.barrier_log_file_last.write("%i %s\n" % (dpid, end-a))

        del self._prev_barrier_arrived[dpid]
      else:
        self._prev_barrier_arrived[dpid] = end
      return EventHalt
    else:
      return EventContinue

  def _handle_PortStatus (self, event):
    log.info('PortStatus: %s, dpid:%s, port:%s %s' %
             (time.time(), event.dpid, event.port, 
              event.ofp.desc.show()))

  def _flush_logs (self):
    self.log_file.flush()
    self.barrier_log_file.flush()
    self.log_file_last.close()
    self.barrier_log_file_last.close()
    fsync(self.log_file)
    fsync(self.barrier_log_file)
    log.info('logs are flushed')

  def emulate_link_failure (self, start, duration = 0, link='nl-hr',
                            reroute = 0, restore_reroute = True):
      self.prev_change_port = None
      self.log_file_last = open("/tmp/pox_log_last", "w")
      self.barrier_log_file_last = open("/tmp/barrier_log_last", "w")

      n1, n2 = link.split('-')
      node_n1 = core.Outband.t.name(n1)
      node_n2 = core.Outband.t.name(n2)
      n1_dpid = node_n1.dpid
      n2_dpid = node_n2.dpid
      n1_port_to_n2 = node_n1.port_num(node_n2)
      n2_port_to_n1 = node_n2.port_num(node_n1)
      log.warn("Going down in %is, link:%ss, dur:%ss, reroute:%ss, restore after dur:%s" %
               (start, link, duration, reroute, restore_reroute))
      end = start + duration
      self._prev_barrier_arrived = {}
      f = self._install_port_down
      core.callDelayed(start, f, n1_dpid, n1_port_to_n2, 1, duration)
      core.callDelayed(start, f, n2_dpid, n2_port_to_n1, 1, duration)
      core.callDelayed(end,   f, n1_dpid, n1_port_to_n2, 0, duration, True)
      core.callDelayed(end,   f, n2_dpid, n2_port_to_n1, 0, duration)
      if reroute:
        core.callDelayed(start+reroute, self._install_failover_entries, n1)
        core.callDelayed(start+reroute, self._install_failover_entries, n2)
      if reroute and restore_reroute:
        core.callDelayed(end+reroute, self._delete_failover_entries, n1)
        core.callDelayed(end+reroute, self._delete_failover_entries, n2)
      core.callDelayed(end+reroute+1, self._flush_logs)

  def _handle_magic_packet (self, addr):


    if addr == "10.10.10.10":
      self.emulate_link_failure(3, 0.100)
    elif addr == "10.10.10.11":
      self.emulate_link_failure(3, 10, reroute = 0.200)
    elif addr == "10.10.10.12":
      self.emulate_link_failure(3, 10, reroute = 2)
    elif addr == "10.10.10.13":
      self.emulate_link_failure(3, 10)

    elif addr == "10.10.10.20":
      self.emulate_link_failure(10, 0.050)
    elif addr == "10.10.10.21":
      self.emulate_link_failure(10, 0.100)
    elif addr == "10.10.10.22":
      self.emulate_link_failure(5, 2, reroute=0.050, restore_reroute=False)
    elif addr == "10.10.10.23":
      self.emulate_link_failure(10, 2, reroute=0.100, restore_reroute=False)
    elif addr == "10.10.10.24":
      self.emulate_link_failure(5, 2, reroute=0.200, restore_reroute=False)
    elif addr == "10.10.10.25":
      self.emulate_link_failure(5, 2, reroute=1.000, restore_reroute=False)
    elif addr == "10.10.10.26":
      self.emulate_link_failure(5, 2, reroute=10.000, restore_reroute=False)
    elif addr == "10.10.10.27":
      self.emulate_link_failure(5, 30, reroute=0, restore_reroute=False)

    elif addr == "10.10.10.99":
      #self.cancel_timers()
      self.reset_flowtables()

  def _handle_PacketIn (self, event):
    dpid = event.connection.dpid
    packet = event.parsed
    inport = event.port

    if not packet.parsed:
      log.warn("%s %i ignoring unparsed packet", dpid_to_str(dpid), inport)
      return

    if packet.find('lldp'):
      return

    ip = packet.find('ipv4')

    try:
      ip_addr = str(IPAddr(ip.dstip))
    except:
      ip_addr = ''
    if ip_addr.startswith("10.10.10."):
      self._handle_magic_packet(str(IPAddr(ip.dstip)))
      return EventHalt

    if packet.find('arp'):
      return

    ignored_addr = [IPAddr("224.0.0.22"), IPAddr("224.0.0.251")]
    if packet.find('dns'):
      return
    if ip and (ip.srcip in ignored_addr or ip.dstip in ignored_addr):
      # find('dns') doesn't work if the packet-in is truncated
      return

    # Install temp drop action for unknown trafic.
    info = ip if ip else packet
    log.warn("%s.%s Dropping unknown packet %s" % (event.dpid, inport, info))
    match = of.ofp_match.from_packet(packet)
    match.dl_src = None # Wildcard MAC addresses
    match.dl_dst = None

    msg = of.ofp_flow_mod(command=of.OFPFC_ADD,
                          idle_timeout=FLOW_IDLE_TIMEOUT,
                          hard_timeout=5,
                          actions=[],
                          match=match)
    core.openflow.sendToDPID(event.dpid, msg.pack())

    return

  def reset_flowtables (self):
    for dpid in core.openflow.connections.iterkeys():
      self._reset_flowtable(dpid)
    log.info("reset_flowtables")

  def _drop_ipv6 (self, dpid):
    match = of.ofp_match(dl_type = ethernet.IPV6_TYPE)
    match.adjust_wildcards = False
    match.wildcards = of.OFPFW_ALL
    match.wildcards &= ~ of.ofp_match_data['dl_type'][1]
    msg = of.ofp_flow_mod(command=of.OFPFC_ADD,
                          hard_timeout=of.OFP_FLOW_PERMANENT,
                          priority=0xffff, # maximal
                          match=match)
    core.openflow.sendToDPID(dpid, msg.pack())

  def _reset_flowtable (self, dpid):
    with reset_lock:
      self._reset_flowtable_0(dpid)

  def _reset_flowtable_0 (self, dpid):
    node = core.Outband.t.dpid(dpid)
    if not node or not node.name:
      log.warn('reset_flowtable, unknown dpid: %s' % dpid)
      return
    str_node = core.Outband.t.dpid(dpid).name
    self._clear_flowtable(dpid)
    self._drop_ipv6(dpid)

    for r, prop in core.Outband.t.routes:
      port_src = core.Outband.t.get_port_to_name(r[0], r[1])
      port_dst = core.Outband.t.get_port_to_name(r[-1], r[-2])

      if 'protect' in prop:
        link = prop[-1]
        self._protect_link(link, str_node)
        continue
      for p, c, n in zip(r[:-2], r[1:-1], r[2:]):
        if c == str_node:
          self._install_flow(p, c, n, port_src, port_dst)

    return

  def _handle_ConnectionUp (self, event):
    try:
      str_node = core.Outband.t.dpid(event.dpid).name
    except AttributeError:
      log.warn('Unknown dpid: %s' % dpid_to_str(event.dpid))
      return
    log.debug("ConnectionUp: %s %s" % (event.connection, str_node))

    core.callDelayed(4, self._reset_flowtable, event.dpid)
    return

  def _handle_OutbandTopologyChanged (self, event):
    self.reset_flowtables()

  def _protect_link (self, link, str_node):
    n1, n2 = link.split('-')
    protection = None
    for r, prop in core.Outband.t.routes:
      if link in prop and 'protect' in prop:
        protection = r
        break
    if protection == None:
      log.error('No protection path found for %s' % link)
      return
    for r, prop in core.Outband.t.routes:
      if 'protect' in prop:
        continue
      try:
        start = r.index(n1)
        if r[start+1] != n2:
          continue
      except (ValueError, IndexError):
        continue
      port_src = core.Outband.t.get_port_to_name(r[0], r[1])
      port_dst = core.Outband.t.get_port_to_name(r[-1], r[-2])
      pp = protection
      if str_node == pp[0]:
        self._install_flow(r[start-1],pp[0],pp[1],port_src,port_dst,
                           add_eth_label = True, failover_entry = True)
      for p, c, n in zip(pp[:-2], pp[1:-1], pp[2:]):
        if str_node == c:
          self._install_flow(p, c, n, port_src, port_dst, with_eth_label = True)
      if str_node == pp[-1]:
        self._install_flow(pp[-2], pp[-1], r[start+2],
                           port_src, port_dst, del_eth_label = True)
      #log.info('%s=%s=%s' % (r[start-1], protection, r[start+2]))

    return

def launch ():
  core.register("routing", ProactiveRouting())

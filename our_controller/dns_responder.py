# Copyright 2011,2012 James McCauley
# Copyright 2008 (C) Nicira, Inc.
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
Dns_responder answers mDNS queries.  

Why?  Our routing modules might not handle multicast traffic.
Additionally, it is not practical to set up a DNS server either,
because hosts are connected to a non-OpenFlow network as well.

On the other hand, we might take care of the lookups using out-of-band
information.

It would be good if dns_responder relied on dns_spy, but the events of
dns_spy do not communicate where the query came from.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
import pox.lib.packet as pkt
#import pox.lib.packet.dns as pkt_dns
from pox.lib.packet.dns import dns as pkt_dns, rrtype_to_str, rrclass_to_str
from pox.lib.addresses import IPAddr, EthAddr

log = core.getLogger()

# #########################################################################
# we cannot access makeName and putName from dns.py, so let's just
# copy them.

def makeName (labels, term):
  o = '' #TODO: unicode
  for l in labels.split('.'):
    o += chr(len(l))
    o += l
  if term: o += '\x00'
  return o

def putName (s, name):
  pre = ''
  post = name
  while True:
    at = s.find(makeName(post, True))
    if at == -1:
      post = post.split('.', 1)
      if pre:
          pre = pre + "." + post[0]
      else:
          pre = post[0]
      if len(post) == 1:
        if len(pre) == 0:
          s += '\x00'
        else:
          s += makeName(pre, True)
        break
      post = post[1]
    else:
      if len(pre) > 0:
        s += makeName(pre, False)
      s += struct.pack("!H", at | 0xc0)
      break
  return s

# ###########################################################################

class DnsResponder (object):
  def __init__ (self, install_flow = True):
    self._install_flow = install_flow
    core.openflow.addListeners(self)
    log.debug('install_flow %s' % install_flow)

  def _handle_ConnectionUp (self, event):
    if self._install_flow:
      msg = of.ofp_flow_mod()
      msg.match = of.ofp_match()
      msg.match.dl_type = pkt.ethernet.IP_TYPE
      msg.match.nw_proto = pkt.ipv4.UDP_PROTOCOL
      msg.match.tp_src = 5353
      msg.actions.append(of.ofp_action_output(port = of.OFPP_CONTROLLER))
      event.connection.send(msg)

  def _answer_A (self, q):
    if not q.name.endswith('.local'):
      log.info('ignoring question: %s' % q)
      return None, None
    name = q.name[:-len('.local')]
    for node in core.Outband.t.nodes:
      if (node.name.lower() == name.lower()):
        # TODO multiple addresses in the response?
        port = node.ports[max(node.ports)]
        log.info('answering: %s %s' % (q.name, port.ip))
        ttl = 120 # 2 minutes
        addr = IPAddr(port.ip).toRaw() # byte-order ???
        r = pkt_dns.rr(q.name, q.qtype, q.qclass, ttl, 4, addr)
        return port, r
    return None, None

  def _answer_PTR (self, q):
    if not q.name.endswith('.in-addr.arpa'):
      log.info('ignoring question: %s' % q)
      return None, None
    name = q.name[:-len('.in-addr.arpa')]
    ip = name.split('.')
    ip.reverse()
    ip = '.'.join(ip)
    node, port = core.Outband.t.ip_and_port(ip)
    if not node:
      return None, None
    log.info('answering: %s %s' % (q.name, node.name))
    ttl = 120 # 2 minutes
    domain = putName('', node.name + '.local')
    domain = domain.encode('ascii', 'ignore')
    r = pkt_dns.rr(q.name, q.qtype, q.qclass, ttl, len(domain), domain)
    return port, r

  def _answer_unknown (self, q):
    log.debug('ignoring question: %s' % q)
    return None, None

  def _handle_PacketIn (self, event):
    if not event.parsed:
      return
    q_dns = event.parsed.find('dns')
    if q_dns is None:
      return
    if not event.parsed.find('ipv4'):
      return

    log.debug(q_dns)
    r_dns = pkt_dns()
    r_dns.qr = True
    r_dns.aa = True
    for q in q_dns.questions:
      if rrclass_to_str[q.qclass] != "IN":
        # Internet only
        continue 
      log.debug('q: (%s,%s)' % (q.name, q.qtype))
      attr = getattr(self, "_answer_" + rrtype_to_str[q.qtype],
                     self._answer_unknown)
      port, rr = attr(q)
      if port:
        r_dns.answers.append(rr)
        r_mac_src = EthAddr(port.mac)
        r_ip_src = IPAddr(port.ip)

    if not r_dns.answers:
      log.debug('cannot answer questions')
      return
    q_eth = event.parsed.find('ethernet')
    q_ip = event.parsed.find('ipv4')
    q_udp = event.parsed.find('udp')
    r_eth = pkt.ethernet(src=r_mac_src, dst=q_eth.dst)
    r_eth.type = pkt.ethernet.IP_TYPE
    r_ip = pkt.ipv4(srcip=r_ip_src, dstip=q_ip.dstip)
    r_ip.protocol = r_ip.UDP_PROTOCOL
    r_udp = pkt.udp()
    r_udp.srcport = q_udp.dstport
    r_udp.dstport = q_udp.srcport
    r_udp.payload = r_dns
    r_ip.payload = r_udp
    r_eth.payload = r_ip
    r_pkt = of.ofp_packet_out(data=r_eth.pack())
    r_pkt.actions.append(of.ofp_action_output(port=event.port))
    log.debug('response: %s' % r_dns)
    event.connection.send(r_pkt)

def launch (no_flow = False):
  core.registerNew(DnsResponder, not no_flow)

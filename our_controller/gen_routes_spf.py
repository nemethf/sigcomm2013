# Copyright (c) 1998, 2000, 2003 Python Software Foundation.
# Copyright (c) 2013 Felician Nemeth
# All rights reserved.
# Licensed under the PSF license.

import random
from pox.core import core
from pox.lib.addresses import IPAddr

log = core.getLogger()

class GenRoutesSpf (object):
  """Calculate routes among hosts.

     It is not efficient at all.  The goal here is to privide an
     initial configuration to the user.  Nevertheless, connectivity is
     a must.
  """

  def __init__ (self):
    log.debug('__init__')

  def generate_routes (self, topo):
    self.t = topo
    for src in self.t.nodes:
      if not src.ip:
        continue
      for dst in self.t.nodes:
        if src == dst or not dst.ip:
          continue
        route = self.find_shortest_path(src, dst)
        if not route:
          log.warn('no route between %s-%s' % (src.name, dst.name))
          continue
        route = [n.name for n in route]
        log.debug('new route: %s' % ('-'.join(route)))
        topo.add_route(route)

  def is_path_valid (self, path, prefix_len=24):
    "True iff source and destination ip addresses are in the same network."
    try:
      port_src = path[0].port(path[1])
      port_dst = path[-1].port(path[-2])
      ip_src = port_src.ip
      ip_dst = port_dst.ip
      network_src = IPAddr(ip_src).toUnsigned() & ~ ((1 << (32-prefix_len))-1)
      network_dst = IPAddr(ip_dst).toUnsigned() & ~ ((1 << (32-prefix_len))-1)
      return network_src == network_dst
    except (AttributeError, RuntimeError):
      return False

  # Adapted from: http://www.python.org/doc/essays/graphs.html
  # Copyright (c) 1998, 2000, 2003 Python Software Foundation.
  # All rights reserved.
  # Licensed under the PSF license.
  #
  # start, end: dpid
  def find_shortest_path(self, start, end, path=[]):
    path = path + [start]
    if start == end:
      if self.is_path_valid(path):
        return path
      else:
        return None
    shortest = None
    for dpid in start.neighbors:
      node = self.t.dpid(dpid)
      if node not in path:
        newpath = self.find_shortest_path(node, end, path)
        if newpath:
          if not shortest or len(newpath) < len(shortest):
            shortest = newpath
    return shortest

def launch ():
  core.register("gen_routes_spf", GenRoutesSpf())

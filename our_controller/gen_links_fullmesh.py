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

from pox.core import core

log = core.getLogger()

class GenLinksFullMesh (object):
  def __init__ (self):
    log.debug('__init__')

  def generate_links (self, topo):
    nodes = topo.nodes
    nodes = [n for n in nodes if not n.external]
    if len(nodes) < 2:
      log.debug('not enough nodes')
      return

    for i, node_a in enumerate(nodes[1:], 1):
      for node_b in nodes[:i]:
        log.debug('add_link %s-%s' % (node_a.name, node_b.name))
        topo.add_link(node_a, node_b)
        topo.add_link(node_b, node_a)

def launch ():
  core.register("gen_links_fullmesh", GenLinksFullMesh())

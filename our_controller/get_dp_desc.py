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
#

"""
Logs switches' datapath descriptions.  Similar module now exists in
POX's carp/carpe-diem branch.  This one has a type option, since we
are only interested in the version number of sliver-ovs (type=brief)
"""

from pox.core import core
from pox.lib.util import dpid_to_str
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

class GetDatapathDescription (object):
  """Query and log datapath descritions
     a little bit after receiving connection up event."""

  def __init__ (self, type='full'):
    self.type = type
    self.db = {}
    core.openflow.addListeners(self)
    core.addListeners(self)

  def __str__ (self):
    lines = []
    for dpid, val in self.db.iteritems():
      lines.append('%s:%s' % (dpid_to_str(dpid), val))
    return ' \n'.join(lines)

  def _send_SwitchDescReq (self, dpid):
    body = of.ofp_desc_stats_request()
    body._type = 0
    msg = of.ofp_stats_request(body=body)
    con = core.openflow.getConnection(dpid)
    con.send(msg.pack())

  def _handle_SwitchDescReceived (self, event):
    if self.type == 'full':
      log.info('SwitchDescReceived: \n dp_desc: connection: %s\n%s' %
               (event.connection, event.stats.show(prefix=' dp_desc: ')))
      self.db[event.connection.dpid] = event.stats.show()
    elif self.type == 'brief':
      log.info('%s %s %s' % (event.connection, event.stats.sw_desc,
                             event.connection.sock.getpeername()))
      self.db[event.connection.dpid] = event.stats.sw_desc
    else:
      log.error('unknown type: %s' % self.type)

  def _handle_ConnectionUp (self, event):
    core.callDelayed(1, self._send_SwitchDescReq, event.dpid)

def launch (**kw):
  core.registerNew(GetDatapathDescription, **kw)

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
Allows changing topologies using pox's webserver.  E.g., at
http://127.0.0.1:8000/poxdesk/topo_conf
"""

from os import path
from glob import glob

from pox.core import core
from pox.web.webcore import SplitRequestHandler, StaticContentHandler

log = core.getLogger()

class TopoConfHandler (SplitRequestHandler):
  def __init__ (self, *args, **kw):
    SplitRequestHandler.__init__(self, *args, **kw)
    self.topologies = self.args 

  def do_GET (self):
    """Serve a GET request."""
    self.log_message("%s", self.path)
    r = self.get_info(self.path)
    self.do_my_command(self.path)
    self.send_response(200)
    self.send_header("Content-type", "text/html")
    self.send_header("Content-Length", str(len(r)))
    self.end_headers()
    self.wfile.write(r)

  def get_topologies (self):
    if self.topologies:
      return self.topologies
    head, tail = path.split(core.Outband.get_topo_filename())
    files = glob(path.join(head, '*.json'))

    topos = []
    for f in files:
      head, tail  = path.split(f)
      tail = tail.rpartition('.json')[0]
      if len(tail) > 0:
        topos.append(tail)

    if len(topos) == 0:
      return ['--']
    return topos

  def get_info (self, path):
    r = "<html><body><ul>"
    r += "Available topologies:<br>\n"
    for topo in self.get_topologies():
      r += '<li><a href="' + topo + '">' + topo + "</a>\n"
    r += "</ul>"
    r += '<img src="/poxdesk/source/resource/poxdesk/system_quarter.png" '
    r += ' style="position:fixed; right:0; bottom:0;"/>'
    r += "</body></html>"
    return r

  def do_my_command (self, path):
    args = path.split('/')
    topo = None
    try:
      topo = args[1]
    except IndexError:
      pass
    self.log_message('topo:%s', topo)
    if topo in self.get_topologies():
      old = core.Outband.get_topo_filename()
      p = old.split('/')
      p[-1] = topo + '.json'
      new = '/'.join(p)
      if old != new:
        core.Outband.set_topo_filename(new)
        core.Outband.reload_topo()
      else:
        self.log_message('nothing to do')
    else:
      self.log_message('unknown command: %s', path)
 
def launch (prefix = '/topo_conf',
            gen_dir = '../../../tools/gen',
            topologies = ['k5', 'k3', 'r5']):
  def _launch ():
    core.WebServer.set_handler(prefix, TopoConfHandler, topologies)
    core.WebServer.add_static_dir("gen", gen_dir, relative=True)
  core.call_when_ready(_launch, ('WebServer', 'Outband'))

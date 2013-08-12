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
A POX application mainly interacts the network with help of the
OpenFlow protocol.  This module collects out-of-band information about
the network from PlanetLab and from configuration files, it also sets
up the silver-ovs overlay on the planetlab nodes, and shares the
out-of-band information with other modules.
"""

import sys
import copy
import time
import os
import subprocess
import re
import multiprocessing
import multiprocessing.dummy
import xmlrpclib
import json
import inspect
import socket
from ssl import SSLError

import pox.core
from pox.core import core
from pox.lib.addresses import *
from pox.lib.revent import *

log = core.getLogger()
config = {}
lock = multiprocessing.Lock()
rpc_lock = multiprocessing.Lock()

#############################################################################
# from: http://stackoverflow.com/questions/372365/set-timeout-for-xmlrpclib-serverproxy
import httplib

class TimeoutHTTPSConnection (httplib.HTTPSConnection):
  def connect (self):
    httplib.HTTPSConnection.connect(self)
    self.sock.settimeout(self.timeout)
  def set_timeout (self, timeout):
    self.timeout = timeout

class TimeoutTransport (xmlrpclib.SafeTransport):
  def __init__ (self, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, *args, **kwargs):
    xmlrpclib.SafeTransport.__init__(self, *args, **kwargs)
    self.timeout = timeout

  def make_connection (self, host):
    #return an existing connection if possible.  This allows
    #HTTP/1.1 keep-alive.
    if self._connection and host == self._connection[0]:
      return self._connection[1]

    # create a HTTP connection object from a host descriptor
    chost, self._extra_headers, x509 = self.get_host_info(host)
    #store the host argument along with the connection object
    conn = TimeoutHTTPSConnection(chost, None, **(x509 or {}))
    conn.set_timeout(self.timeout)
    self._connection = host, conn
    return self._connection[1]

class TimeoutServerProxy (xmlrpclib.ServerProxy):
  def __init__(self,uri,timeout=socket._GLOBAL_DEFAULT_TIMEOUT, *l, **kw):
    kw['transport']=TimeoutTransport(timeout=timeout,
                                     use_datetime=kw.get('use_datetime',0))
    xmlrpclib.ServerProxy.__init__(self, uri, *l, **kw)
#############################################################################

def make_dir_if_needed (path):
  try:
    os.makedirs(path)
  except OSError as e:
    if e.errno == 17:
      pass
    else:
      raise e

def read_var (filename, target_type = None, default=None):
  if not os.path.exists(filename) and default is not None:
    return default
  with open(filename) as f:
    if target_type == json:
      r = json.load(f)
    else:
      r = f.read().strip()
  return r

def write_var (var, filename, target_type = None):
  with open(filename, 'w') as f:
    if target_type == json:
      json.dump(var, f)
    else:
      f.write(var)

def call_make (*args, **kw):
  if 'conf_mk' in kw:
    conf_filename = kw['conf_mk']
  else:
    conf_filename = config['conf_mk']
  cmd = ['make', 'CONF=%s' % conf_filename]
  cmd.extend(args)
  proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
  output = ''
  if kw.get('log'):
    log.info(' '.join(cmd))
  for line in iter(proc.stdout.readline, ''):
    if kw.get('log'):
      log.info('%s' % line.rstrip())
    output += line
  return output.rstrip()

def ssh_cmd (hostname, identity_file, username, cmd, **kw):
  args = ['ssh', '-t']
  if config.get('ssh_options'):
    args += config.get('ssh_options').split(' ')
  else:
    identity_file = os.path.expanduser(identity_file)
    args += ['-l', username, '-i', identity_file]
  args += kw.get('extra_args', [])
  args.append(hostname)
  if type(cmd) == list:
    args = args + cmd
  else:
    args.append(cmd)
  f_stdin, f_stderr = None, None
  if kw.get('no_stdin'):
    f_stdin = open(os.path.devnull)
  if kw.get('capture_stderr'):
    f_stderr = subprocess.STDOUT

  output = subprocess.check_output(args, stdin=f_stdin, stderr=f_stderr)
  output = output.rstrip()

  if f_stdin:
    f_stdin.close()
  if kw.get('log'):
    log.info(output)
  return output

def pl_ssh_cmd (hostname, cmd, **kw):
  identity_file = config['IdentityFile']
  slice_name = config['slice_name']

  return ssh_cmd(hostname, identity_file, slice_name, cmd, **kw)

def check_node_availability (hostname):
  try:
    args = ['-o', 'ConnectTimeout=4',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ServerAliveInterval=4']
    output = pl_ssh_cmd(hostname, 'hostname', extra_args=args,
                        capture_stderr=True, no_stdin=True)
    args = ['-o', 'ConnectTimeout=4',
            '-o', 'ServerAliveInterval=4']
    output = pl_ssh_cmd(hostname, 'hostname', extra_args=args,
                        capture_stderr=True, no_stdin=True)
    lock.acquire()
    log.info("sucessful ssh connection to: %s" % hostname)
    lock.release()
    return True
  except subprocess.CalledProcessError as e:
    lock.acquire()
    log.error('cannot ssh into node: %s\n%s' % (hostname, e.output))
    lock.release()
    return False

class Downloader (object):
  def __init__ (self, url, filename):
    log.info('Downloading: %s' % url)
    self._url = url
    self._filename = filename
    self._start = time.time()
    self._last = None
    self.do()
    self.clean()

  def do (self):
    import urllib
    f, i = urllib.urlretrieve(self._url, self._filename, self.report_hook)

  def report_hook (self, block_count, block_size, total_size):
    now = time.time()
    if (now - (self._last or self._start)) < 1:
      return
    self._last = now
    total_kb = total_size/1024
    sys.stdout.write("\r%d KB of %d Kb downloaded, %ds" %
                     (block_count * (block_size/1024),
                      total_kb,
                      int(self._last - self._start)))
    sys.stdout.flush()

  def clean (self):
    if self._last:
      sys.stdout.write('\n')
      sys.stdout.flush()

##############################################################################

class Port (dict):
  def __init__ (self, parent, d):
    super(Port, self).__init__(**d)
    for name in ['ip', 'mac', 'num', 'dpid']:
      if name in d:
        self.__setattr__(name, d[name])
    self.__setattr__('parent', parent)

  def __getattr__ (self, name):
    if name in ['ip', 'mac', 'num', 'dpid', 'parent']:
      return self.get(name)
    else:
      raise AttributeError('%s' % name)

  def __setattr__ (self, name, value):
    if name == 'ip':
      value = IPAddr(value) if value else value
      return super(Port, self).__setitem__(name, value)
    if name == 'mac':
      value = EthAddr(value) if value else value
      return super(Port, self).__setitem__(name, value)
    if name in ['num', 'dpid', 'parent']:
      return super(Port, self).__setitem__(name, value)
    return super(Port, self).__setattr__(name, value)

  def json_dict (self):
    d = copy.deepcopy(self)
    for k in ['ip', 'mac']:
      if k in d:
        d[k] = str(d[k])
    for k in ['num', 'dpid', 'parent']:
      d.pop(k, None)
    return d

class Node (object):
  def __init__ (self, d):
    self._dict = {'ports': {}}
    self._dict.update(d)
    p = {}
    for k, v in self._dict['ports'].iteritems():
      p[int(k)] = Port(self, v)
    self._dict['ports'] = p

  def __getattribute__ (self, name):
    if name.startswith('_'):
      return object.__getattribute__(self, name)
    if name in dir(self):
      fun = object.__getattribute__(self, name)
      if len(inspect.getargspec(fun).args) == 1:
        return fun()
      else:
        return fun
    return self._dict.get(name)

  def __setattr__ (self, name, value):
    if name.startswith('_'):
      return object.__setattr__(self, name, value)
    self._dict[name] = value

  def __str__ (self):
    return ("N%s" % self._dict)

  def dpid (self):
    try:
      return int(self._dict[ 'DPID' ], 16)
    except KeyError:
      log.warn("node.dpid (%s) failed" % self.name)
      return None

  def ip (self):
    return [p.ip for p in self.ports.itervalues() if p.ip]

  def mac (self):
    return [p.mac for p in self.ports.itervalues() if p.mac]

  def hostname (self):
    if 'hostname' in self._dict:
      return self._dict['hostname']
    try:
      hn = socket.gethostbyaddr(str(self.management_ip))[0]
      self._dict['hostname'] = hn
      return hn
    except (socket.herror, socket.gaierror):
      return call_make('+HOST_%s' % self.name)

  def position (self):
    try:
      return (self.x, self.y)
    except (KeyError, AttributeError):
      return None, None

  def geo_coords (self):
    try:
      return (str(self.latitude), str(self.longitude))
    except (KeyError, AttributeError):
      return None, None

  def has_geo_coords (self):
    try:
      lat, lon = self.geo_coords
      lat, lon = float(lat), float(lon)
      return True
    except ValueError:
      return False

  def update_geo_coords (self, force = False):
    if self.longitude is None or force:
      filename = 'cache/geocode.%s' % self.name
      call_make(filename)
      geo = read_var(filename)
      geo = re.sub(r'^[^:]*:', '', geo)
      geo = json.loads(geo)
      pos = geo['position']
      if len(pos) == 2:
        lat, lon = pos
      else:
        lat, lon = None, None
      self._dict.update({'latitude': lat, 'longitude': lon})

  def add_neighbor (self, port_num, node_or_dpid):
    node_dpid = Node.get_dpid(node_or_dpid)

    old_port = self.port(node_dpid)
    if old_port:
      try:
        del old_port['dpid']
      except KeyError:
        pass
    if port_num in self.ports.keys():
      self.ports[port_num].dpid = node_dpid
      return
    if port_num < 1:
      unset = [num for num, p in self.ports.iteritems() if not p.dpid]
      if unset:
        self.ports[unset[0]].dpid = node_dpid
        return
    self.ports[port_num] = Port(self, {'dpid': node_dpid})

  def neighbors (self):
    '''return list of dpids of the node's neighbors'''
    return [p.dpid for p in self.ports.itervalues() if p.dpid]

  def neighbor (self, node = None, port = None):
    if node is None and port is None:
      return self.neighbors()
    if node and port:
      return self.ports.get(port, {}).get('dpid') == node.dpid
    if port:
      return self.ports.get(port, {}).get('dpid')
    if node:
      return self.port(node)

  @staticmethod
  def get_dpid (node_or_dpid):
    if type(node_or_dpid) == Node:
      return node_or_dpid.dpid
    return node_or_dpid

  def port (self, node_or_dpid):
    node_dpid = Node.get_dpid(node_or_dpid)

    for p_num, p in self._dict['ports'].iteritems():
      if p.dpid == node_dpid:
        p['num'] = p_num
        return p
    return None

  def port_num (self, node_or_dpid):
    node_dpid = Node.get_dpid(node_or_dpid)

    for p_num, p in self._dict['ports'].iteritems():
      if p.dpid == node_dpid:
        return p_num
    return None

  def get_port (self, port_num):
    p = self._dict['ports'].get(port_num)
    if p:
      p['num'] = port_num
    return p

  def generate_host_port (self, port_num):
    if port_num in self._dict['ports'] and self.ports[port_num].ip:
      log.warn('host(%s) has already got port_num(%s)' % (self.name, port_num))
      port = self._dict['ports'][port_num]
      port.num = port_num
      return port
    port = Port(self,
                {'ip': '10.%d.0.%d' % (port_num, self.dpid),
                 'mac': '22:{0:02x}:00:00:00:{1:02x}'.format(port_num,
                                                             self.dpid),
                 'num': port_num,
                 })
    self._dict['ports'][port_num] = port
    return port

  def json_dict (self):
    d = copy.deepcopy(self._dict)
    json_ports = {}
    for k, v in d.get('ports').iteritems():
      port = v.json_dict()
      if port:
        json_ports[k] = port
    if json_ports:
      d['ports'] = json_ports
    else:
      d.pop('ports', None)
    d.pop('qemu', None)
    d.pop('initialized', None)
    return d

class Link (object):
  def __init__ (self, node_a, node_b, d):
    self._dict = d
    self._node_a = node_a
    self._node_b = node_b

  def is_hidden (self):
    try:
      return self._dict['prop'] == 'hidden'
    except (KeyError, TypeError):
      return None

  def get_nodes (self):
    return (self._node_a, self._node_b)

  def json_dict (self):
    def name_and_port (node, port_num):
      if node.external and port_num:
        return '%s:%s' % (node.name, port_num)
      # we cannot contorol which port sliver-ovs will use, so it is
      # pointless to save the port numbers
      return '%s' % node.name
    d = copy.deepcopy(self._dict)
    d['name_a'] = self._node_a.name
    d['name_b'] = self._node_b.name
    port_a = d.pop('port_a', None)
    port_b = d.pop('port_b', None)
    if len(d) == 2:
      return '%s-%s' % (name_and_port(self._node_a, port_a),
                        name_and_port(self._node_b, port_b))
    return d

class Topo (object):
  def __init__ (self):
    self._nodes_dpid = {}
    self._nodes_name = {}
    self._links = {}
    self._ple_nodes = []
    self._working_ple_nodes = []
    self._routes = []
    self._gen_routes = True
    self._max_dpid = 0

  def __getattr__ (self, name):
    if name == 'nodes':
      return self._nodes_name.values()
    if name == 'links':
      return self._links.values()
    if name == 'routes':
      return self._routes
    raise AttributeError('%s' % name)

  def add_node (self, node):
    if self.dpid(node.dpid):
      log.warn('node already exists, dpid=%i' % node.dpid)

    self._nodes_dpid[node.dpid] = node
    self._nodes_name[node.name] = node
    self._max_dpid = max(self._max_dpid, node.dpid)

    if node.external is None:
      node.external = node.hostname not in self._ple_nodes
    node.qemu = node.external and node.hostname in self._ple_nodes

  def add_link (self, node_a, node_b = None, l = {}):
    if node_b is None:
      l = node_a                # dict of link properties
      node_a = self.name(l[ 'name_a' ])
      node_b = self.name(l[ 'name_b' ])

    dpid_1, dpid_2 = sorted([node_a.dpid, node_b.dpid])
    self._links[dpid_1, dpid_2] = Link(node_a, node_b, l)
    node_a.add_neighbor(int(l.get('port_a', -1 * node_b.dpid)), node_b.dpid)
    node_b.add_neighbor(int(l.get('port_b', -1 * node_a.dpid)), node_a.dpid)

  def set_link_port (self, name_a, name_b, port_num):
    node_a = self.name(name_a)
    node_b = self.name(name_b)
    if node_a is None:
      log.error('set_link_port: unknown node: %s' % name_a)
      return
    if node_b is None:
      log.error('set_link_port: unknown node: %s' % name_b)
      return

    link = self.link(node_a, node_b)
    if not link:
      return
    node_a.add_neighbor(int(port_num), node_b.dpid)

  def gen_dpid (self):
    return self._max_dpid + 1

  def add_route (self, route, prop = []):
    self._routes.append((route, prop))

  def get_port_to_name (self, name_a, name_b):
    'return the port of name_a connecting to name_b'
    node_a = self.name(name_a)
    node_b = self.name(name_b)
    return node_a.port(node_b)

  def get_link_params (self, node_a, node_b):
    link = '%s-%s' % (node_b.name, node_a.name)
    port_a = node_a.port(node_b)
    return {
      "tunmode": 'tap',         # 'tun' or 'tap'
      'link': link,
      'remote_ip': read_var('cache/host.%s' % node_b.name),
      'remote_port': read_var('cache/port.%s@1' % link),
      'local_port': read_var('cache/port.%s@2' % link),
      'prefix_len': str(24),
      'addr_ip':  str(port_a.ip),
      'addr_eth': str(port_a.mac),
      'port_num': str(port_a.num),
      'node_name': node_a.name,
      }

  def disable_gen_routes (self):
    self._gen_routes = False

  def gen_routes (self):
    if not self._gen_routes:
      return
    alg = config['gen_routes']
    attr = None
    try:
      mod = getattr(core, alg)
      attr = getattr(mod, 'generate_routes')
    except AttributeError:
      log.error('generate_routes: cannot find: %s', alg)
    if attr:
      self._routes = []
      attr(self)

  def write_external_info (self):
    for node_a in self.nodes:
      if not node_a.external:
        continue
      node_vars = {}
      hostnames = []
      for dpid_b in node_a.neighbors:
        node_b = self.dpid(dpid_b)
        params = self.get_link_params(node_a, node_b)
        dir = 'planetlab/%s/%s' % (node_a.hostname, node_b.name)
        make_dir_if_needed(dir)

        write_var(params, dir + '/vars.json', json)
        for var in params.keys():
          write_var(params[var], dir + '/' + var)

        node_vars[node_b.name] = params
        hostnames.append(node_b.name)

      dir =  'planetlab/%s' % node_a.hostname
      write_var(node_vars, dir + '/vars.json', json)

      with open(dir + '/neighbors', 'w') as f:
        for neighbor in hostnames:
          f.write('%s\n' % neighbor)

  def dpid (self, id):
    return self._nodes_dpid.get(id)

  def name (self, n):
    return self._nodes_name.get(n)

  def ip (self, ip):
    for node in self._nodes_name.values():
      for port in node.ports.itervalues():
        if str(port.ip) == str(ip):
          return node
    return None

  def ip_and_port (self, ip):
    for node in self._nodes_name.values():
      for port in node.ports.itervalues():
        if str(port.ip) == str(ip):
            return node, port
    return None, None

  def mac (self, mac):
    for node in self._nodes_name.values():
      for port in node.ports.itervalues():
        if str(port.mac) == str(mac):
          return node

  def hostname (self, hostname):
    for node in self._nodes_name.values():
      if node.hostname == hostname:
        return node

  def link (self, node_a, node_b):
    if not isinstance(node_a, Node):
      node_a = self.name(node_a)
    if not isinstance(node_b, Node):
      node_b = self.name(node_b)

    dpid_1, dpid_2 = sorted([node_a.dpid, node_b.dpid])
    return self._links.get((dpid_1, dpid_2))

  def json_dumps (self, **kw):
    routes = []
    for r, prop in self.routes:
      r = '-'.join(r)
      if prop:
        routes.append((r, prop))
      else:
        routes.append(r)
    var = {'nodes': [n.json_dict for n in self.nodes],
           'links': [l.json_dict() for l in self.links],
           'routes': routes}
    return json.dumps(var, **kw)

##############################################################################

class OutbandTopologyChanged (Event):
  def __init__ (self):
    Event.__init__(self)

class Outband (EventMixin):
  _eventMixin_events = set([
    OutbandTopologyChanged,
  ])

  def __init__ (self):
    self.ctrl_addr = None
    self.file_timestamp = -1
    self.install_poxdesk()
    self.check_for_updates()
 
  def __str__ (self):
    public_config = copy.deepcopy(config)
    del public_config['auth']
    return str(public_config)

  def get_topo_filename (self):
    return config['topo_filename']

  def set_topo_filename (self, filename):
    config['topo_filename'] = filename
    self.file_timestamp = self.get_file_timestamp(filename)

  def install_poxdesk (self):
    "run setup.py for poxdesk if necessary"
    import poxdesk
    dirname = os.path.dirname(poxdesk.__file__)
    install_script = os.path.join(dirname, 'poxdesk', 'generate.py')
    installed_file = os.path.join(dirname, 'poxdesk',
                                   'source', 'script' , 'poxdesk.js')
    if os.path.exists(installed_file):
      log.debug('poxdesk is already installed')
      return
    log.info('installing poxdesk ...')
    cmd = ['python', install_script]
    try:
      subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
      log.info('failed to run: %s' % ' '.join(cmd))
      return
    log.info('installing poxdesk ... done')
    return

  def query_links (self, node=None):
    if node:
      output = call_make('showports-%s' % node.name, log=False)
    else:
      output = call_make('showports', log=False)
    for line in output.split('\n'):
      m = re.match(r"PORT_(.*)_(.*)=(.*)", line)
      if m:
        self.t.set_link_port(m.group(1), m.group(2), m.group(3))
      else:
        if (re.search(r"\w", line)):
          log.error('query_links, unknown line:%s' % line)

  def download_qemu_files (self, image_file, overlay_file):
    if os.path.exists(image_file):
      return
    tgz_file = '/tmp/bin.tar.gz'
    for filename in [image_file, overlay_file, tgz_file]:
      bname = os.path.basename(filename)
      url = os.path.join(config['qemu_url'], bname)
      Downloader(url, filename)
    try:
      target_dir = os.path.dirname(os.path.abspath(image_file))
      cmd = ['tar', '-C', target_dir, '-zxf', tgz_file]
      subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
      log.error('failed to run: %s' % ' '.join(cmd))
      return
    return

  def init_node (self, node):
    if not node.external and node.neighbors:
      slice_name = config['slice_name']
      cmd=('%s sudo -A ovs-vsctl set bridge %s other-config:datapath-id=%s' %
           ('SUDO_ASKPASS=/bin/false', slice_name, '{0:016x}'.format(node.dpid)))
      if not node.hostname:
        log.error('cannot determine hostname for %s' % node.name)
        exit()
      pl_ssh_cmd(node.hostname, cmd, log=True)
    node.update_geo_coords()
    if node.external and node.qemu and not node.initialized:
      node.initialized = True
      pox_dir = os.path.dirname(pox.core.__file__)
      tools_dir = os.path.join(pox_dir, '..', '..', 'tools')
      script = os.path.join(tools_dir, 'qemu-setup')
      image_file = os.path.join(tools_dir, config['qemu_image'])
      overlay_file = os.path.join(tools_dir, config['qemu_overlay'])
      identity_file = os.path.expanduser(config['IdentityFile'])
      # port might be obtained form core.WebServer.server_port, but
      # WebServer will start much later.
      pox_url='http://%s:8000' % self.get_controller_ip_addr()
      if len(node.ports) > 0:
        num_if = str(len(node.ports))
      else:
        num_if = "2"
      self.download_qemu_files(image_file, overlay_file)
      cmd = [script, node.hostname, config['slice_name'],
             identity_file, node.name, image_file, overlay_file,
             pox_url, num_if]
      log.info('installing qemu onto %s' % node.name)
      subprocess.Popen(cmd)     # runs in the background

  def filter_available_nodes (self, hostnames):
    if not config['check_node_availability']:
      return hostnames
    pool =  multiprocessing.dummy.Pool(10)
    bool_list = pool.map(check_node_availability, hostnames)
    ok_hostnames = [n for n, b in zip(hostnames, bool_list) if b]
    return ok_hostnames

  def load_topo (self):
    filename = config['topo_filename']
    self.file_timestamp = self.get_file_timestamp(filename)
    self.t = Topo()
    self.get_planetlab_info()

    if not os.path.exists(filename):
      log.warn('file does not exist: %s' % filename)
    topo = read_var(filename, json, {})

    for n in topo.get('nodes', []):
      self.t.add_node(Node(n))
    if not self.t.nodes:
      #generate nodes
      for dpid, hostname in enumerate(self.t._working_ple_nodes, 1):
        n = { 'name': "N%d" % dpid,
              'DPID': '{0:016x}'.format(dpid),
              'hostname': hostname }
        self.t.add_node(Node(n))

    for l in topo.get('links', []):
      if type(l) == dict:
        self.t.add_link(l)
      else:
        #link format: name_a:port_a-name_b:port_b
        m = re.match(r"([^:-]*)(:([0-9]+))?-([^:-]*)(:([0-9]+))?", l)
        name_a, tmp_a, port_a, name_b, tmp_b, port_b = m.groups()
        d = {'name_a': name_a, 'name_b': name_b}
        if port_a: d['port_a'] = port_a
        if port_b: d['port_b'] = port_b
        self.t.add_link(d)
    if not self.t.links:
      alg = config['gen_links']
      attr = None
      try:
        mod = getattr(core, alg)
        attr = getattr(mod, 'generate_links')
      except AttributeError:
        log.error('generate_links: cannot find: %s', alg)
      if attr:
        attr(self.t)

    # set pre-defined routes
    for r in topo.get('routes', []):
      if type(r) == list:
        route = r[0]
        prop  = r[1:]
      else:
        route = r
        prop  = []
      self.t.add_route(route.split('-'), prop)
    if len(self.t.routes) == 0:
      self.t.gen_routes()
    else:
      self.t.disable_gen_routes()

    self.start_planetlab_overlay()
    self.save_topo()

    self.raiseEvent(OutbandTopologyChanged)

  def reload_topo (self):
    "first stops the planetlab overlay, then loads the new topology."
    # this is an overkill, probably
    call_make('-j', 'stop', log=True)
    call_make('-j', 'shutdown', log=True)
    call_make('clean', log=True)
    call_make('distclean', log=True)

    self.load_topo()

  def save_topo (self, filename='auto_topo.json'):
    with open(filename, 'w') as f:
      topo = self.t.json_dumps(sort_keys=True, indent=4,
                               separators=(',', ': '))
      emacs = ' -' + '*-'
      emacs = emacs + ' eval: (auto-revert-mode 1);' + emacs
      topo = topo.replace('{', '{   "emacs": "' + emacs + '",', 1)
      f.write(topo)

  def get_file_timestamp (self, filename):
    try:
      return time.ctime(os.path.getmtime(filename))
    except OSError:
      return 0

  def check_for_updates (self):
    filename = config['topo_filename']
    curr = self.get_file_timestamp(filename)
    prev = self.file_timestamp
    if curr != prev:
      self.load_topo()
    core.callDelayed(2, self.check_for_updates)

  def get_planetlab_info (self):
    plc_host='www.planet-lab.eu'
    api_url = "https://%s:443/PLCAPI/" % plc_host
    auth = config['auth']
    slice_name = config['slice_name']

    log.info('planetlab: trying to authenticate...')
    res = False
    try:
      plc_api = TimeoutServerProxy(api_url, allow_none=True, timeout=5)
      res = plc_api.AuthCheck(auth)
    except (socket.gaierror, socket.timeout, SSLError):
      pass
    if res:
      log.info('planetlab: we are authorized!')
    else:
      log.error('planetlab: not authorized')
      return

    # get 'vnet' of the slice
    try:
      filter = {'name': slice_name, 'tagname': 'vsys_vnet'}
      tags = plc_api.GetSliceTags(auth, filter, ['value'])
      vnet = tags[0]['value']
      self.t.vnet = vnet
    except SSLError as e:
      log.error('planetlab: %s' % e)
      return

    # get public ssh keys of slice's users
    dirname = os.path.dirname(pox.core.__file__)
    dir = os.path.join(dirname, '..', '..', 'tools', 'fat_dir')
    make_dir_if_needed(dir)
    user_keys = plc_api.GetSliceKeys(auth)
    user_keys = [k['key'] for k in user_keys if k['name'] == slice_name]
    with open(dir + '/ssh_key.pub', 'w') as f:
      f.write(''.join(user_keys))

    # the slice's node ids
    node_ids = plc_api.GetSlices(auth, slice_name, ['node_ids'])
    node_ids = node_ids[0]['node_ids']

    # get hostname for these nodes
    try:
      slice_nodes = plc_api.GetNodes(auth,node_ids,['hostname', 'run_level'])
    except Fault as e:
      log.error('planetlab: %s' % e)
      return

    nodes =   [n['hostname'] for n in slice_nodes if n['run_level'] == 'boot']
    skipped = [n['hostname'] for n in slice_nodes if n['run_level'] != 'boot']

    self.t._ple_nodes = [n['hostname'] for n in slice_nodes]
    self.t._working_ple_nodes = self.filter_available_nodes(nodes)

  def get_controller_ip_addr (self):
    if config.get('controller_ip_addr'):
      return config['controller_ip_addr']
    if self.ctrl_addr:
      return self.ctrl_addr

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    self.ctrl_addr = s.getsockname()[0]
    s.close()
    return self.ctrl_addr

  def write_makefile_config (self, filename):
    f = open(filename, 'w')
    vnet = re.sub(r'\.[0-9]/', '.%d/', self.t.vnet)
    port = core.of_01.port
    ip_addr = self.get_controller_ip_addr()

    s = ' -' + '*-'
    f.write('#' + ' ' * 19)
    f.write(s + ' mode: makefile-gmake; eval: (auto-revert-mode 1);' + s + '\n')
    f.write('# Automatically generated file.\n')
    f.write('#' * 78 + '\n')
    f.write('SLICE = %s\n' % config['slice_name'])
    f.write('CONTROLLER = tcp:%s:%d\n' % (ip_addr, port))
    if config.get('ssh_options'):
      f.write('SSH_OPTIONS := %s\n' % config['ssh_options'])
    else:
      f.write('SSH_KEY := %s\n' % config['IdentityFile'])
    f.write('EXTERNAL_PORT := 2222\n')
    f.write('EXTERNAL_HOSTS :=\n\n')

    for i, n in enumerate(sorted(self.t.nodes, key=lambda x: x.dpid), 1):
      f.write('HOST_%s=%s\n' % (n.name, n.hostname))
      if n.external:
        f.write('EXTERNAL_HOSTS += %s\n' % n.name)
      else:
        f.write('IP_%s=%s\n' % (n.name, vnet % i))

    f.write('\nLINKS :=\n')
    for link in self.t.links:
      node_a, node_b = link.get_nodes()
      if node_a.external:
        node_a, node_b = node_b, node_a
      f.write('LINKS += %s-%s\n' % (node_a.name, node_b.name))
      if node_b.external:
        make_dir_if_needed('cache')
        try:
          port_num = str(2221 + node_b.port_num(node_a))
        except TypeError:
          log.error("%s->%s: doesn't exist" % (node_b.name, node_a.name))
          continue
        write_var(port_num, 'cache/port.%s-%s@2' % (node_a.name, node_b.name))
    f.close()

  def start_planetlab_overlay (self):
    self.write_makefile_config('auto_conf.mk')
    call_make('init', log=True)
    call_make('-j', log=True)
    if filter(lambda x: not x, [n.has_geo_coords for n in self.t.nodes]):
      call_make('geocode.json', log=True)
    for node in self.t.nodes:
      self.init_node(node)
    call_make('-j', 'controllers')
    self.query_links()
    self.t.write_external_info()

  def get_ple_list (self):
    '''Return the list available PLE nodes that a host can connect to.'''
    l = []
    for hostname in self.t._working_ple_nodes:
      node = self.t.hostname(hostname)
      if node and not node.external and node.neighbors:
        l.append(hostname)
    log.debug('get_ple_list: %s' % l)
    return l

  def connect_to_ple_node (self, *args):
    with rpc_lock:
      return self.connect_to_ple_node_0(*args)

  def connect_to_ple_node_0 (self, ple_hostnames,
                             host_hostname, host_shortname=None):
    '''
    Initialize connection to requested PLE node or other available one
    return connection params
    '''
    node_host = self.t.hostname(host_hostname)
    if node_host is None or not node_host.external:
      dpid = self.t.gen_dpid()
      if dpid > 255:
        log.eror('dpid space is exhausted')
        return []
      shortname = 'H%d' % dpid
      if host_shortname and not self.t.name(host_shortname):
        shortname = host_shortname
      d = {'external': True,
           'hostname': host_hostname,
           'DPID': '{0:016x}'.format(dpid),
           'ports': {},
           'name': shortname,
           }
      node_host = Node(d)
      self.t.add_node(node_host)
    if host_shortname and node_host.name != host_shortname :
      log.warn('ignoring shortname (%s) when connecting %s to the network' %
               (host_shortname, host_hostname))

    params = []
    for port_num, ple_hostname in enumerate(ple_hostnames, 1):
      node_ple = self.t.hostname(ple_hostname)
      if node_ple is None:
        log.error('trying to connect %s to %s, but %s is unknown.' %
                  (node_host.hostname, ple_hostname, ple_hostname))
        return []
      host_port = node_host.get_port(port_num)
      if not host_port or not host_port.ip:
        host_port = node_host.generate_host_port(port_num)
      if (host_port.dpid and host_port.dpid != node_ple.dpid):
        new_node_ple = self.t.dpid(host_port.dpid)
        log.warn(('buliding connection: %s:%s-%s' +
                  ' instead of the requested %s:%s-%s') %
                 (node_host.name, port_num, new_node_ple.name,
                  node_host.name, port_num, node_ple.name))
        node_ple = new_node_ple
      else:
        log.debug('building connection: %s:%s-%s' %
                  (node_host.name, port_num, node_ple.name))

      link = '%s-%s' % (node_ple.name, node_host.name)
      link_param = {'port_b': host_port.num}
      if node_ple.port_num(node_host):
        link_param['port_a'] = node_ple.port_num(node_host)
      self.t.add_link(node_ple, node_host, link_param)
      self.write_makefile_config('auto_conf.mk')
      call_make('L/%s' % link, conf_mk='auto_conf.mk')
      for node in [node_ple, node_host]:
        self.init_node(node)
      self.query_links(node_ple)
      params.append(self.t.get_link_params(node_host, node_ple))

    call_make('controllers')
    self.t.write_external_info()
    self.t.gen_routes()
    self.save_topo()
    self.raiseEvent(OutbandTopologyChanged)

    return params

#############################################################################

def set_config (config_filename, **kw):
    global config

    config = {'check_node_availability': True,
              'controller_ip_addr': None,
              'topo_filename': 'topo.json',
              'IdentityFile': '~/.ssh/id_rsa',
              'qemu_url': 'http://sb.tmit.bme.hu/sigcomm2013',
              'qemu_image': 'debian_squeeze_i386_mptcp.qcow2',
              'qemu_overlay': 'overlay_debian_squeeze_i386_mptcp.qcow2',
              'gen_routes': 'gen_routes_spf',
              'gen_links': 'gen_links_ring',
              'conf_mk': 'auto_conf.mk'}
    try:
      with open(config_filename) as f:
        new_config = json.load(f)
        config.update(new_config)
    except ValueError as e:
      log.error('"%s": %s' % (config_filename, e))
      log.error('Check your config file here: http://jsonlint.com/')
      exit()
    except IOError:
      log.error('unable to load: %s' % filename)
      exit()
    if not os.path.exists(config['conf_mk']):
      config['conf_mk'] = 'auto_conf.mk'
    config.update(kw)

def launch (config = 'config', **kw):
  set_config(config, **kw)
  core.registerNew(Outband)

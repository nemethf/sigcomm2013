# Copyright (c) 2012, 2013 Felician Nemeth
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

import importlib
import logging
from pox.core import core

from greedy import *
from predefined_routing import PredefinedRouting
from proactive_routing import ProactiveRouting
from logging import DEBUG, INFO, WARN

import signal
import sys
def signal_handler(signal, frame):
  print 'You pressed Ctrl+C!'
  sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

def _start_planetlab (path = None):
  httpd = core.WebServer
  httpd.add_static_dir('planetlab')

def launch (alg='proactive', **outband_args):
  dependencies = ['openflow.of_01',
		  ['log.level', {'packet': WARN}],
		  'samples.pretty_log',
		  ['allegra.gen_routes_spf', {}, INFO],
		  'allegra.gen_links_ring',
		  ['allegra.outband', outband_args, INFO],
		  ['allegra.get_dp_desc', {'type': 'brief'}],
		  'allegra.arp_responder',

                  # because of proactive routing, no packets will
                  # reach the controller, hence it is pointless to
                  # differentiate between arpAware and arpSilent
		  ['host_tracker', {'eat_packets': False,
				    'install_flow': False,
				    'arpAware': 30,
				    'arpSilent': 30}, INFO],
		  ['allegra.outband_host_tracker', {'timeout': 10}, INFO],
		  ['allegra.topo_conf', {'topologies': None}],
		  'topology',
		  'openflow.discovery',
		  'openflow.topology',
		  'pox.messenger',
		  'messenger.log_service',
		  'allegra.linkutil',
		  'allegra.tinytopo',
                  'allegra.flowstat',
                  'allegra.tinylink',
		  'web',
		  'messenger.ajax_transport',
		  'openflow.of_service',
		  'poxdesk',
		  ['allegra.dns_responder', {'no_flow': True}, INFO],
                  ['allegra.host_controller', {}, INFO],
		  ]

  log_level_param = {}
  for mod in dependencies:
    if type(mod) == list and len(mod) == 3:
      log_level_param[mod[0]] = mod[2]
  for mod in dependencies:
    args = {}
    if type(mod) == list:
      mod, args = mod[:2]
    if mod == 'log.level':
      args.update(log_level_param)
    mod = importlib.import_module(mod)
    mod.launch(**args)


  d = { 'greedy': GreedyRouting,
        'predefined': PredefinedRouting,
	'proactive': ProactiveRouting,
        'None': None}

  a = d[ alg ]

  if a:
    core.register("routing", a())
  core.call_when_ready(_start_planetlab, ["WebServer",
                                         "MessengerNexus_of_service"])

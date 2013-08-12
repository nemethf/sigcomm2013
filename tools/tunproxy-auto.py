#! /usr/bin/env python

#############################################################################
##                                                                         ##
## tunproxy.py --- small demo program for tunneling over UDP with tun/tap  ##
##                                                                         ##
## Copyright (C) 2003  Philippe Biondi <phil@secdev.org>                   ##
## Copyright (C) 2013  Felician Nemeth <nemethf@tmit.bme.hu>               ##
## Copyright (C) 2013  Balazs Sonkoly <sonkoly@tmit.bme.hu>                ##
##                                                                         ##
## This program is free software; you can redistribute it and/or modify it ##
## under the terms of the GNU General Public License as published by the   ##
## Free Software Foundation; either version 3, or (at your option) any     ##
## later version.                                                          ##
##                                                                         ##
## This program is distributed in the hope that it will be useful, but     ##
## WITHOUT ANY WARRANTY; without even the implied warranty of              ##
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU       ##
## General Public License for more details.                                ##
##                                                                         ##
#############################################################################


import re
import os, sys, subprocess, time
from socket import *
from fcntl import ioctl
from select import select
import getopt, struct
import argparse
import urllib2
import json

from jsonrpc import ServiceProxy, JSONRPCException
import ping

#supporting parallel ping measurements
import multiprocessing.dummy

BASEURL = "http://allegra1.tmit.bme.hu:8000/planetlab/"
CONTROLLER = "http://152.66.244.43:8000/hostconfig/"

# number of RTT measurements for one node
PING_NO = 5

TUNSETIFF = 0x400454ca
IFF_TUN   = 0x0001
IFF_TAP   = 0x0002
IFF_NO_PI = 0x1000              # from: /usr/include/linux/if_tun.h

DEBUG = 0

class tunproxy (object):
    '''
    Class for handling tunproxy
    '''
    def __init__  (self):
        if DEBUG: print "Init tunproxy..."
        self._controller = CONTROLLER
        # available PLE nodes
        self._ple_list = []
        # number of PLE connections
        self._ple_conns = 0
        # dict for RTT measurments of PLE nodes
        self._delays = {}
        # PLE nodes' config params (which we are to connect)
        self._ple_config = []
        self._my_fqdn = None
        self._host_shortname = None
        self._qemu = False
        self._parse_args()
        # init JSONRPC proxy
        while 1:
            try:
                self._jsonrpc_proxy = ServiceProxy(self._controller)
                break
            except (JSONRPCException, IOError):
                print "Waiting for initializing JSONRPC Proxy..."
                self._ple_list = []
                time.sleep(2)
                continue

        if DEBUG: print "Done."

    def _parse_args (self):
        '''
        Parsing command line args
        '''
        global DEBUG
        self._parser = argparse.ArgumentParser(
            description='Automatically managing connections to PlanetLab Europe (PLE)')
        parser = self._parser
        parser.add_argument('-d', '--debug',  action='store_true', dest='debug',
                            help='run in debug mode')
        parser.add_argument('-p', '--ple-nodes',  action='store', dest='ple_list',
                            nargs='+',
                            help='PLE node candidates for connection')
        parser.add_argument('-c', '--conns',  action='store', dest='ple_conns',
                            type=int, nargs=1,
                            help='number of connections to PLE we want to use')
        parser.add_argument('-n', '--name',  action='store', dest='name',
                            nargs=1,
                            help='short name of the host')
        parser.add_argument('-C', '--controller',  action='store', dest='controller',
                            nargs=1,
                            help='url of the POX controller')
        parser.add_argument('-q', '--qemu',  action='store_true', dest='qemu',
                            help='generate config file for qemu VM instead of network setup')
        p = parser.parse_args()

        if p.debug:
            DEBUG = 1
        if p.ple_conns and p.ple_conns[0] > 0:
            self.set_ple_conns(p.ple_conns[0])
        if p.ple_list and len(p.ple_list) > 0:
            self.set_ple_list(p.ple_list)
        if p.name:
            self._host_shortname = ''.join(p.name)
        if p.controller:
            self._controller = ''.join(p.controller)
        if p.qemu:
            self._qemu = True

    def usage (self, status = 0):
        '''
        Print usage information on the program
        '''
        self._parser.print_help()
        sys.exit(status)

    def _read_args (self, opts):
        '''
        Old args reader
        '''
        # parse command line args
        self._config = { 'tunmode': IFF_TUN,
                         'remote_ip': None }
        for opt,optarg in opts[0]:
            if opt == "-h":
                self.usage_old()
            elif opt == "-d":
                global DEBUG
                DEBUG = 1
            elif opt == "-p":
                self.set_ple_list(str(optarg).split(","))
            # elif opt == "-p":
            #     self._config['local_port'] = int(optarg)
            elif opt == "-t":
                self._config['remote_ip'], remote_port = optarg.split(":")
                self._config['remote_port'] = int(remote_port)
            elif opt == "-e":
                self._config['tunmode'] = IFF_TAP
            elif opt == "-a":
                self._config['addr_ip'] = optarg
            elif opt == "-E":
                self._config['addr_eth'] = optarg
            else:
                self.usage_old(1)

    def usage_old (status = 0):
        print "Usage: tunproxy [-p local_port] [-t targetip:port] [-e]" 
        "[-a local_ip] [-E eth_adrr]"
        sys.exit(status)

    def get_ip_addr (self):
        s = socket(AF_INET, SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_addr = s.getsockname()[0]
        s.close()
        
        return ip_addr

    def get_my_fqdn (self):
        if self._my_fqdn:
            return self._my_fqdn

        #fqdn = subprocess.check_output(['hostname', '-A']) # python 2.7
        fqdn = subprocess.Popen(['hostname', '-A'],
                            stdout=subprocess.PIPE).communicate()[0]
        fqdn = fqdn.strip()
        fqdn = [n for n in fqdn.split(' ') if not n.endswith('.local')]
        if fqdn == [] or fqdn == ['']:
            fqdn = self.get_ip_addr()
        else:
            fqdn = fqdn[0]
        fqdn = fqdn.strip()

        self._my_fqdn = fqdn
        return self._my_fqdn

    def _download_config (self, baseurl):
        '''
        Use this if config.json is available at baseurl/hostname
        '''
        fqdn = self.get_my_fqdn()
        url = baseurl + fqdn + '/vars.json'
        print 'Downloading config from: %s' % url
        data = None
        while not data:
            try:
                data = urllib2.urlopen(url).read()
            except urllib2.URLError as err: 
                print '%s. Retrying after 2 sec' % err
                time.sleep(2)
        data = json.loads(data)
        return data

    def _configure_interface (self, ifname = None, addr_ip = None, addr_eth = None):
        '''
        Configure single interface
        '''
        if addr_ip is None or ifname is None:
            return

        cmd = 'ip addr add %s/24 dev %s' % (addr_ip, ifname)
        print cmd
        os.system(cmd)

        cmd = 'ip link set dev %s mtu 1400' % ifname
        print cmd
        os.system(cmd)

        if addr_eth:
            cmd = 'ip link set dev %s address %s' % (ifname, addr_eth)
            print cmd
            os.system(cmd)

        cmd = 'ip link set dev %s up' % ifname
        print cmd
        os.system(cmd)

        net = re.sub('\.[0-9]*$', '.0', addr_ip)
        cmd = 'ip route add %s/24 dev %s' % (net, ifname)
        print cmd
        os.system(cmd)

    def _start_service_single (self, config):
        '''
        Start single tunnel (connection with remote peer)
        '''
        f = os.open("/dev/net/tun", os.O_RDWR)
        tunmode = config['tunmode'] | IFF_NO_PI
        ifs = ioctl(f, TUNSETIFF, struct.pack("16sH", "allegra_%d", tunmode))
        ifname = ifs[:16].strip("\x00")

        print "Allocated interface %s. Configure it and use it" % ifname
        return 0
        self._configure_interface(ifname, config['addr_ip'], config['addr_eth'])

        s = socket(AF_INET, SOCK_DGRAM)

        if config['remote_ip'] is None or config['remote_port'] is None: 
            print 'Missing remote_ip or remote_port \n'
            self.usage(1)

        try:
            peer = (config['remote_ip'], int(config['remote_port']))
            s.bind(("", int(config['local_port'])))
            print "Connection with %s:%i established" % peer
    
            while 1:
                r = select([f,s],[],[])[0][0]
                if r == f:
                    if DEBUG: os.write(1, ">")
                    s.sendto(os.read(f,1500), peer)
                else:
                    buf, p = s.recvfrom(1500)
                    if p != peer:
                        print "Got packet from %s:%i instead of %s:%i" % (p + peer)
                        print '==================='
                        os.close(f)
                        return
                    if DEBUG: os.write(1, "<")
                    os.write(f, buf)
        except KeyboardInterrupt:
            print "Stopped by user."
            exit()

    def _start_service (self, config):
        '''
        Start tunnels. Parameters are given in config dict list.
        '''
        fd = []
        ifname = []
        sock = []
        peer = []
        
        for i in range(len(config)): 
            fd.append(os.open("/dev/net/tun", os.O_RDWR))
            if config[i]['tunmode'] == 'tun':
                tunmode = IFF_TUN | IFF_NO_PI
            else:
                tunmode = IFF_TAP | IFF_NO_PI
            ifs = ioctl(fd[i], TUNSETIFF, struct.pack("16sH", "allegra_%d", tunmode))
            ifname.append(ifs[:16].strip("\x00"))
            
            print "Allocated interface %s. Configure it and use it" % ifname[i]
            self._configure_interface(ifname[i], config[i]['addr_ip'], config[i]['addr_eth'])

            sock.append(socket(AF_INET, SOCK_DGRAM))

            if config[i]['remote_ip'] is None or config[i]['remote_port'] is None: 
                print 'Missing remote_ip or remote_port \n'
                self.usage(1)

            peer.append( (config[i]['remote_ip'], int(config[i]['remote_port'])) )
            sock[i].bind(("", int(config[i]['local_port'])))
            print "Connection with %s:%i established" % peer[i]

        try:        
            while 1:
                r_list = select(fd + sock, [], [])[0]
                for r in r_list:
                    if r in fd:
                        # read from tun/tap device and send to peer
                        i = fd.index(r)
                        if DEBUG: os.write(1, ">")
                        sock[i].sendto(os.read(fd[i], 1500), peer[i])
                    else:
                        # receive from peer and send to tun/tap device
                        i = sock.index(r)
                        buf, p = sock[i].recvfrom(1500)
                        if DEBUG: print "Pkt from %s:%i" % p
                        if p != peer[i]:
                            print "Got packet from %s:%i instead of %s:%i" % (p + peer[i])
                            print '==================='
                            for f in fd:
                                os.close(f)
                            return
                        if DEBUG: os.write(1, "<")
                        os.write(fd[i], buf)

        except KeyboardInterrupt:
            print "Stopped by user."
            exit()

    def set_ple_list (self, ple_list):
        '''
        Set potential PLE nodes to connect to
        '''
        self._ple_list = ple_list
        self.set_ple_conns()

        if DEBUG: print "Set ple_list: " + str(self._ple_list)

    def set_ple_conns (self, ple_conns = None):
        '''
        Set number of intended PLE connections to input parameter
        or command line arg (-c) if given
        or try to find a default value
        '''
        if ple_conns:
            self._ple_conns = ple_conns
        elif self._ple_conns == 0:
            # set default connection number to list len, max:2
            # if -c is not given as input
            if len(self._ple_list) < 3:
                self._ple_conns = len(ple_list)
            else:
                self._ple_conns = 2

        if DEBUG: print "Set ple_conns: " + str(self._ple_conns)

    def set_ple_config (self, ple_config):
        '''
        Set ple_config dict
        '''
        self._ple_config = ple_config

    def get_ple_config (self):
        '''
        Get current ple_config dict
        '''
        return self._ple_config

    def get_ple_list_from_controller (self):
        '''
        Available PLE nodes list is requested from CONTROLLER
        '''
        while 1:
            try:
                self._ple_list = self._jsonrpc_proxy.get_ple_list()
                break
            except (JSONRPCException, IOError):
                print "Waiting for JSONRPC connection..."
                self._ple_list = []
                time.sleep(2)
                continue

        # set number of connections to a default value if it is not set yet
        self.set_ple_conns()

        if DEBUG: print self._ple_list

    def sort_given_ple_nodes (self, ple_list):      
        '''
        Sort given PLE nodes based on RTT measurements
        Return: sorted list of PLE nodes, 1st: min
        '''
        for node in ple_list:
            # ignore first ping
            if (ping.Ping(node, timeout = 2000).do()) is None:
                # in case of timeout
                break

            self._delays[node] = 0
            for i in range(PING_NO):
                delay = ping.Ping(node, timeout = 2000).do()
                if delay is not None:
                    self._delays[node] += delay
                    if DEBUG: print self._delays[node]
                else:
                    # timeout occurs at least once:
                    # dont use the node
                    del self._delays[node]
                    break
            else:
                # calculate average
                self._delays[node] /= PING_NO

        if DEBUG: print "delays: " + str(self._delays)
        # ordered ple list, 1st: min
        return sorted(self._delays, key=self._delays.get)

    def sort_ple_nodes (self):
        '''
        Sort available PLE nodes based on RTT measurements
        Available nodes list is requested from CONTROLLER if it's empty
        '''
        self._delays = {}
        if len(self._ple_list) == 0:
            self.get_ple_list_from_controller()

        # Sort the list
        self._ple_list = self.sort_given_ple_nodes(self._ple_list)
        if DEBUG: print self._ple_list

    def sort_given_ple_nodes_multi (self, ple_list):      
        '''
        Sort given PLE nodes based on PARALLEL RTT measurements
        using multiprocess
        Return: sorted list of PLE nodes, 1st: min
        '''
        pool =  multiprocessing.dummy.Pool(len(ple_list))
        print "Starting RTT measurement..."
        delays = dict(pool.map(ping_measurement, ple_list))
        #filter out None values
        self._delays = dict(filter(lambda item: item[1] is not None, 
                                   delays.items()))

        if DEBUG: print self._delays
        # ordered ple list, 1st: min
        print "Sorted list:"
        for node in sorted(self._delays, key=self._delays.get):
            print "%s: %f ms" % (node, self._delays[node])
        # print sorted(self._delays, key=self._delays.get)
        print "Done."
        return sorted(self._delays, key=self._delays.get)

    def sort_ple_nodes_multi (self):
        '''
        Sort available PLE nodes based on PARALLEL RTT measurements
        using sort_given_ple_nodes_multi
        Available nodes list is requested from CONTROLLER if it's empty
        '''
        self._delays = {}
        if len(self._ple_list) == 0:
            self.get_ple_list_from_controller()

        # Sort the list
        self._ple_list = self.sort_given_ple_nodes_multi(self._ple_list)
        if DEBUG: print self._ple_list

    def req_connect_given_ple_nodes (self, ple_conns = None, ple_list = None, 
                                     host_shortname = None):
        '''
        Connection request to ple_conns No. of PLE nodes from ple_list.
        If params are not given self vars are used
        '''
        if ple_conns is None:
            ple_conns = self._ple_conns
        if ple_list is None:
            ple_list = self._ple_list
        if len(ple_list) < ple_conns:
            error(1)
        if host_shortname is None:
            host_shortname = self._host_shortname
        ple_config = []

        my_fqdn = self.get_my_fqdn()
        # for hostname in ple_list[:ple_conns]:
        #     try:
        #         ple_config.append(
        #             self._jsonrpc_proxy.connect_ple(hostname, my_fqdn))
        #     except JSONRPCException as e:
        #         print 'failed to get info of connection to %s' % hostname
        try:
            hostnames = ple_list[:ple_conns]
            ple_config = self._jsonrpc_proxy.connect_ple(hostnames, 
                                                         my_fqdn, 
                                                         host_shortname)
        except JSONRPCException as e:
            print 'failed to get info of connection to %s' % hostnames

        self._ple_config = ple_config
        if DEBUG: print self._ple_config

    def req_connect_ple_nodes (self, ple_conns = None, 
                               host_shortname = None):
        '''
        Connection request to closest PLE nodes (ple_conns No. of nodes)
        Get PLE node list and sort if necessary
        '''
        if len(self._ple_list) == 0:
            # get the list from controller
            self.get_ple_list_from_controller()

        # sort the list parallel
        self.sort_ple_nodes_multi()

        if ple_conns is None:
            ple_conns = self._ple_conns
        else:
            self._ple_conns = ple_conns

        self.req_connect_given_ple_nodes(ple_conns, self._ple_list, host_shortname)
        if DEBUG: print self._ple_config

    def connect_ple_nodes (self):
        '''
        Connect PLE nodes based on current _ple_config,
        configure peer interfaces
        '''
        self._start_service(self._ple_config)

    def dump_config (self, ple_config):
        '''
        Dump ple_config dict to be used by qemu startup scripts
        '''
        my_fqdn = self.get_my_fqdn()
        ports = []
        for conf in ple_config:
            dir = 'planetlab/%s/port%s' % (my_fqdn, conf['port_num'])
            make_dir_if_needed(dir)
            
            write_var(conf, dir + '/vars.json', json)
            for var in conf.keys():
                write_var(conf[var], dir + '/' + var)

            ports.append('port' + conf['port_num'])

        dir = 'planetlab/%s' % my_fqdn
        with open(dir + '/neighbors', 'w') as f:
            for neighbor in ports:
                f.write('%s\n' % neighbor)

    def dump_current_config (self):
        '''
        Dump current ple_config dict to be used by qemu startup scripts
        '''
        self.dump_config(self._ple_config)


################################################################################

def ping_measurement (node):
    '''
    Function for parallel ping measurements
    using with multiprocess
    Return: (node, average delay or None if timeout occurs)
    '''
    # ignore first ping
    if (ping.Ping(node, timeout = 2000).do()) is None:
        # in case of timeout
        return (node, None)
    
    delay_avg = 0
    for i in range(PING_NO):
        delay = ping.Ping(node, timeout = 2000).do()
        if delay is not None:
            delay_avg += delay
        else:
            # timeout occurs at least once:
            # dont use the node
            return (node, None)
    else:
        # calculate average
        delay_avg /= PING_NO
        
    return (node, delay_avg)

################################################################################

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


# running as script
if __name__ == "__main__":
    #opts = getopt.getopt(sys.argv[1:], "t:p:a:E:ehd")
    tp = tunproxy()

    if tp._qemu:
        # qemu mode
        tp.req_connect_ple_nodes()
        print "Dump config vars..."
        tp.dump_current_config()
        print "Done."
        exit(0)

    while 1:
        # # examples:
        
        # # manual setting
        # # add static PLE list for testing
        # ple_list = ['pl002.ece.upatras.gr', 'planetlab2.urv.cat']
        # if len(tp._ple_list) == 0:
        #     tp.set_ple_list(ple_list)
        # tp.req_connect_given_ple_nodes()

        # # auto setting
        # tp.get_ple_list_from_controller()
        # tp.sort_ple_nodes_multi()
        # tp.req_connect_ple_nodes(2, 'SB')

        # control from command line
        tp.req_connect_ple_nodes()
        tp.connect_ple_nodes()
        
        # reinit tunproxy because pox controller was restarted
        tp.__init__()

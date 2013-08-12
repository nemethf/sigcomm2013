#! /usr/bin/env python

#############################################################################
##                                                                         ##
## tunproxy.py --- small demo program for tunneling over UDP with tun/tap  ##
##                                                                         ##
## Copyright (C) 2003  Philippe Biondi <phil@secdev.org>                   ##
## Copyright (C) 2013  Felician Nemeth <nemethf@tmit.bme.hu>               ##
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
import urllib2
import json

BASEURL = "http://allegra1.tmit.bme.hu:8000/planetlab/"

TUNSETIFF = 0x400454ca
IFF_TUN   = 0x0001
IFF_TAP   = 0x0002
IFF_NO_PI = 0x1000              # from: /usr/include/linux/if_tun.h
TUN_MODE = {'tun': IFF_TUN, 'tap': IFF_TAP}

DEBUG = 0

def usage(status=0):
    print "Usage: tunproxy [-s port|-c targetip:port] [-e]"
    sys.exit(status)

def configure_interface(ifname = None, addr_ip = None, addr_eth = None):

    if addr_ip is None or ifname is None:
        return

    cmd = 'ip addr add %s dev %s' % (addr_ip, ifname)
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

def get_ip_addr ():
    s = socket(AF_INET, SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_addr = s.getsockname()[0]
    s.close()

    return ip_addr

def download_config (baseurl):
    #fqdn = subprocess.check_output(['hostname', '-A']) # python 2.7
    fqdn = subprocess.Popen(['hostname', '-A'],
                            stdout=subprocess.PIPE).communicate()[0]
    fqdn = fqdn.strip()
    fqdn = [n for n in fqdn.split(' ') if not n.endswith('.local')]
    if fqdn == []:
        fqdn = get_ip_addr()
    else:
        fqdn = fqdn[0]
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
    return data[min(data)]

def start_service (config):
    f = os.open("/dev/net/tun", os.O_RDWR)
    tunmode = TUN_MODE[config['tunmode']] | IFF_NO_PI
    ifs = ioctl(f, TUNSETIFF, struct.pack("16sH", "allegra_%d", tunmode))
    ifname = ifs[:16].strip("\x00")

    print "Allocated interface %s. Configure it and use it" % ifname
    configure_interface(ifname, config['addr_ip'], config['addr_eth'])

    s = socket(AF_INET, SOCK_DGRAM)

    if config['remote_ip'] is None or config['remote_port'] is None: 
        print 'Missing remote_ip or remote_port \n'
        usage(1)

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

opts = getopt.getopt(sys.argv[1:],"t:p:a:E:ehd")
config = { 'tunmode': IFF_TUN,
           'remote_ip': None }

for opt,optarg in opts[0]:
    if opt == "-h":
        usage()
    elif opt == "-d":
        DEBUG += 1
    elif opt == "-p":
        config['local_port'] = int(optarg)
    elif opt == "-t":
        config['remote_ip'], remote_port = optarg.split(":")
        config['remote_port'] = int(remote_port)
    elif opt == "-e":
        config['tunmode'] = IFF_TAP
    elif opt == "-a":
        config['addr_ip'] = optarg
    elif opt == "-E":
        config['addr_eth'] = optarg
    else:
        usage(1)

while 1:
    new_config = download_config(BASEURL)
    config.update(new_config)

    start_service(config)

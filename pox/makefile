# see README
# conf.mk is expected to define
# HOST_<id> and IP_<id> for all nodes involved, as well as 
# LINKS as a list of <node_id>-<node_id> elements

# should work with any shell, but we have only tested bash
SHELL=/bin/bash

.DELETE_ON_ERROR:

# run make CONF=anotherconfig.mk if you need several configs

CONF ?= auto_conf.mk
include $(CONF)

# if undefined in the conf file, use single dash
SEP?=-

# bridge name (XXX the same on all nodes)
BRIDGE?=$(SLICE)

### helper functions
# flip(1) = 2
# flip(2) = 1
flip=$(if $(findstring 1,$(1)),2,1)
# cutsep (x-y)-> x y
cutsep=$(subst $(SEP), ,$(1))
# leftnode (x-y) -> x
leftnode=$(word 1,$(call cutsep,$(1)))
# rightnode (x-y) -> y
rightnode=$(word 2,$(call cutsep,$(1)))
# linkpart(x@y) = x
linkpart=$(word 1,$(subst @, ,$(1)))
# endpart(x@y) = y
endpart=$(word 2,$(subst @, ,$(1)))
# get(x-y@1) = x
# get(x-y@2) = y
get=$(word $(call endpart,$(1)),$(call cutsep,$(call linkpart,$(1))))
# opp(x-y@1) = x-y@2
# opp(x-y@2) = x-y@1
opp=$(call linkpart,$(1))@$(call flip,$(call endpart,$(1)))
# rget(x-y@1) = y
# rget(x-y@2) = x
rget=$(call get,$(call opp,$(1)))
###
default=$(if $($(1)_$(2)),$($(1)_$(2)),$($(1)))
solve=$(HOST_$(1))
solve_ip=$(IP_$(1))
# can be redefined in conf.mk if that's not the expected behaviour
display?=host $(1) aka $(call solve,$(1))

# log file name
log=$(addprefix log/,$(notdir $(1)))

#################### set variables after conf.mk
ifeq "$(SSH_KEY)" ""
SSH_KEY_OPTION ?=
else
SSH_KEY_OPTION ?= -i $(SSH_KEY)
endif

SSH_OPTIONS ?= $(SSH_KEY_OPTION) -l $(SLICE)
SSH = ssh $(SSH_OPTIONS)

SUDO ?= sudo -S

ALL_NODE_IDS=$(sort $(foreach link,$(LINKS),$(call leftnode,$(link))) $(foreach link,$(LINKS),$(call rightnode,$(link))))
ALL_NODE_HOSTS=$(foreach id,$(ALL_NODE_IDS),$(call solve,$(id)))
ALL_LINK_IDS=$(addsuffix @1,$(LINKS)) $(addsuffix @2,$(LINKS))
CONF_NODE_IDS=$(subst HOST_,,$(filter HOST_%,$(.VARIABLES)))

####################
init_all: init all
init:
	@[ -d L ] || ( echo Creating tmp dir L; mkdir L)
	@[ -d log ] || (echo Creating tmp dir log; mkdir log)
	@[ -d cache ] || ( echo Creating tmp dir cache; mkdir cache)
.PHONY: init_all init


FORCE:

.SECONDARY:

LINKTARGETS=$(addprefix L/,$(LINKS))
all: $(LINKTARGETS)
.PHONY: all
# could also do make ++SLICE
showslice: ++SLICE FORCE

shownodes:
	@$(foreach id,$(ALL_NODE_IDS),echo $(id)=$(call display,$(id));)
showhostnames: ++ALL_NODE_HOSTS
# xxx missing: something that outputs raw python stuff like
# SEND_IP="10.0.16.1"
# that would belong in the export to OF
showips:
	@$(foreach id,$(ALL_NODE_IDS),echo $(id)=$(call display,$(id)) has ip/network set to $(IP_$(id));)
showlinks:
	@$(foreach link,$(LINKS), echo $(call display,$(call leftnode,$(link))) '====>' $(call display,$(call rightnode,$(link)));)
showcontrollers:
	@$(foreach id,$(ALL_NODE_IDS), echo $(call display,$(id)) has controller $(call default,CONTROLLER,$(id));)
.PHONY: shownodes showhostnames showips showlinks showcontrollers

sshchecks: $(foreach id,$(ALL_NODE_IDS),sshcheck-$(id))
.PHONY: sshchecks
ovsversions: $(foreach id,$(ALL_NODE_IDS),ovsversion-$(id))
.PHONY: ovsversions
# more general form; run with  make sshs SSH-COMMAND="bla bla bla"
sshs: $(foreach id,$(ALL_NODE_IDS),ssh-$(id))
.PHONY: sshs
showdpids: $(foreach id,$(ALL_NODE_IDS),showdpid-$(id))
.PHONY: showdpids
showmacs: $(foreach id,$(ALL_NODE_IDS),showmac-$(id))
.PHONY: showmacs
showports: $(foreach id,$(ALL_NODE_IDS),showports-$(id))
.PHONY: showports
showdescs: $(foreach id,$(ALL_NODE_IDS),showdesc-$(id))
.PHONY: showdescs

DBS=$(foreach id,$(ALL_NODE_IDS),cache/db.$(id))
dbs: $(DBS)
.PHONY: dbs

SWITCHS=$(foreach id,$(ALL_NODE_IDS),cache/switch.$(id))
switchs: $(SWITCHS)
.PHONY: switchs

start: dbs switchs
.PHONY: start

stop:$(foreach id,$(ALL_NODE_IDS),cache/stop.$(id))
.PHONY: stop

status:$(foreach id,$(ALL_NODE_IDS),cache/status.$(id))
.PHONY: status

BRIDGES=$(foreach id,$(ALL_NODE_IDS),cache/bridge.$(id))
bridges: $(BRIDGES)
.PHONY: bridges

CONTROLLERS=$(foreach id,$(ALL_NODE_IDS),cache/controller.$(id))
controllers: $(CONTROLLERS)
.PHONY: controllers

del-controllers: $(foreach id,$(ALL_NODE_IDS),del-controller-$(id))
.PHONY: del-controllers

### node-oriented targets
# check ssh connectivity
sshcheck-%: FORCE
	@if $(SSH) $(HOST_$*) hostname > /dev/null 2>&1; then echo "ssh on" $(call display,$*) "OK" ; \
	 else echo "ssh on" $(call display,$*) "KO !!!"; fi

ovsversion-%: FORCE
	@OVSVERSION=$$($(SSH) $(HOST_$*) rpm -q sliver-openvswitch); echo $(call display,$*) has $$OVSVERSION

ssh-%: FORCE
	@$(SSH) $(HOST_$*) $(SUDO) $(SSH-COMMAND)

showdpid-%: FORCE
	@echo $*_DPID=0x$$( $(SSH) $(HOST_$*) $(SUDO) ovs-vsctl get bridge $(BRIDGE) datapath_id | sed -e 's,",,g')

showmac-%: FORCE
	@echo $*_MAC=\"$$( $(SSH) $(HOST_$*) $(SUDO) sliver-ovs get-mac $(BRIDGE))\"

showports-%: FORCE
	@$(SSH) $(HOST_$*) $(SUDO) ovs-ofctl show $(BRIDGE) \
		| perl -nle '/(\d+)\(L(.*?)\Q$(SEP)\E(.*?)\):/ && \
			print "PORT_".("$$2" eq "$*" ? "$$2_$$3" : "$$3_$$2")."=$$1"'
showdesc-%: FORCE
	@$(SSH) $(HOST_$*) $(SUDO) ovs-ofctl dump-desc $(BRIDGE) \
		| sed -ne "s/^DP.Description:/$*: /p"
	@$(SSH) $(HOST_$*) $(SUDO) ovs-vsctl get bridge $(BRIDGE) \
		other-config:dp-desc

# should probably replace sshcheck
cache/status.%: FORCE
	@echo "=== DB and SWITCH processes on $(call display,$*)"
	@$(SSH) $(HOST_$*) $(SUDO) sliver-ovs status ||:

cache/host.%:
	@echo "IP lookup for $(call display,$*)"
	@host $(HOST_$*) | sed -n 's/^.*has address *//p' > $@
	@if test ! -s $@; then echo $(HOST_$*) > $@; fi

cache/db.%:
	@echo "Starting db server on $(call display,$*) - logs in $(call log,$@)"
	@$(SSH) $(HOST_$*) $(SUDO) sliver-ovs start-db > $(call log,$@) 2>&1
	@touch $@

cache/switch.%: | cache/db.%
	@echo "Starting vswitchd on $(call display,$*) - logs in $(call log,$@)"
	@$(SSH) $(HOST_$*) $(SUDO) sliver-ovs start-switch > $(call log,$@) 2>&1
	@touch $@

cache/bridge.%: | cache/db.%
	@echo "Creating bridge on $(call display,$*) - logs in $(call log,$@)"
	@$(SSH) $(HOST_$*) $(SUDO) \
		sliver-ovs create-bridge $(BRIDGE) $(IP_$*) $(call default,BROPTIONS,$*) > $(call log,$@) 2>&1
	@{ echo "IP_$*=$(IP_$*)"; echo "BROPTIONS_$*=$(call default,BROPTIONS,$*)"; } > $@
	@$(SSH) $(HOST_$*) $(SUDO) ovs-vsctl set bridge $(BRIDGE) \
		other-config:dp-desc="$*"

cache/controller.%: cache/bridge.%
	@echo "Setting controller $(call default,CONTROLLER,$*) on $(call display,$*) - logs in $(call log,$@)"
	@$(SSH) $(HOST_$*) $(SUDO) ovs-vsctl set-controller $(BRIDGE) $(call default,CONTROLLER,$*) > $(call log,$@) 2>&1
	@echo "CONTROLLER_$*=$(call default,CONTROLLER,$*)" > $@

# xxx this probably needs a more thorough cleanup in cache/
cache/stop.%: del-bridge.%
	@echo "Stopping switch & db on $(call display,$*)"
	@$(SSH) $(HOST_$*) $(SUDO) sliver-ovs stop && rm cache/switch.$* cache/db.$*

### link-oriented targets
# L/<nodeid1>-<node_id2>:
# 	Establish a link between nodes <node_id1> and <node_id2>
L/%: cache/endpoint.%@1 cache/endpoint.%@2
	@touch $@
	@echo "Link $* is up"

# U/<node_id1>-<node_id2>
# 	Tear down the link between nodes <node_id1> and <node_id2>
U/%: del-iface.%@1 del-iface.%@2
	@rm -f L/$*
	@echo "Deleted link $*"

# del-bridge.<node_id>: Delete the bridge on node <node_id>.
#
# We can do this only if the db on node <node_id> is running, but
# we don't need to re-delete if the db is restarted (hence the
# order-only dependency).
#
# Deleting a bridge also deletes all interfaces of the bridge
# as a side effect. This in turn invalidates local tunnel
# port numbers and endpoint info on both sides of each affected tunnel.
# The corresponding links obviously go down. 
# Controller information is also lost.
# We invalidate the cache accordingly.
del-bridge.%: | cache/db.%
	@echo "Deleting bridge on $(call display,$*)"
	@$(SSH) $(HOST_$*) $(SUDO) sliver-ovs del-bridge $(BRIDGE)
	@rm -f cache/bridge.$* \
	      cache/iface.$*$(SEP)*@1 cache/iface.*$(SEP)$*@2 \
	      cache/port.$*$(SEP)*@1  cache/port.*$(SEP)$*@2  \
	      cache/endpoint.$*$(SEP)*@?  cache/endpoint.*$(SEP)$*@?  \
	      L/$*$(SEP)*	      L/*$(SEP)$* \
	      cache/controller.$*

# del-switch.<node_id>: Stops the switch daemon on <node_id>.
#
# As a side effect, the local port numbers of the tunnels
# are no longer valid (they will change when the daemon is restarted)
# and, therefore, the endpoint info on the remote side of
# the tunnels must be invalidated. The links also go down.
# Controller information is also lost.
# We invalidate the cache accordingly.
del-switch.%:
	@echo "Shutting down switch on $(call display,$*)"
	@$(SSH) $(HOST_$*) $(SUDO) sliver-ovs stop-switch
	@rm -f cache/switch.$* \
	       cache/port.$*$(SEP)*@1  cache/port.*$(SEP)$*@2  \
	       cache/endpoint.$*$(SEP)*@2  cache/endpoint.*$(SEP)$*@1  \
	       L/$*$(SEP)*	      L/*$(SEP)$* \
	       cache/controller.$*

# del-db.<node_id>: Stops the db daemon on <node_id>.
#
# This has no additional side effects.
del-db.%:
	@echo "Shutting down db on $(call display,$*)"
	@$(SSH) $(HOST_$*) $(SUDO) sliver-ovs stop-db
	@rm -f cache/db.$*

# del-controller.<node_id>:
# 	Detaches <node_id> from the controller.
#
# This has no additional side effects.
del-controller-%: | cache/db.%
	@echo "Removing controller for $(call display,$*)"
	@$(SSH) $(HOST_$*) $(SUDO) sliver-ovs del-controller $(BRIDGE)
	@rm -f cache/controller.$*

# del-links: Shortcut to delete all currently up links.
del-links: $(addprefix U/,$(notdir $(wildcard L/*)))

# del-switchs: Shortcut to stop all currently running switch daemons.
del-switchs: $(addprefix del-,$(notdir $(wildcard cache/switch.*)))

# del-dbs: Shortcut to stop all currently running db daemona.s
del-dbs: $(addprefix del-,$(notdir $(wildcard cache/db.*)))

# shutdown: Shortcut to stop all currently running daemons.
shutdown: del-switchs del-dbs

.PHONY: del-links del-switchs del-dbs shutdown


### snapshots
snapshot:
	@echo BRIDGE=$(BRIDGE)
	@cat cache/bridge.* 2>/dev/null || :
	@cat cache/controller.* 2>/dev/null || :
	@ls L | sed 's/^/LINKS += /'

remote-snapshot: remote-snapshot-ips remote-snapshot-links
	@true

remote-snapshot-ips: $(addprefix cache/rsnap.ip.,$(CONF_NODE_IDS))
	@cat /dev/null $^

remote-snapshot-links: $(addprefix cache/rsnap.links.,$(CONF_NODE_IDS))
	@sort -u /dev/null $^

.PHONY: remote-snapshot remote-snapshot-ips remote-snapshot-links


cache/rsnap.ip.%: FORCE
	@$(SSH) $(HOST_$*) $(SUDO) \
		sliver-ovs get-local-ip $(BRIDGE) | sed 's/^/IP_$*=/' > $@ 

cache/rsnap.links.%: FORCE
	@$(SSH) $(HOST_$*) $(SUDO) \
		sliver-ovs get-local-links $(BRIDGE) | sed -n 's/^L/LINKS += /p' > $@

### update sliver-ovs
update: $(addprefix update-,$(CONF_NODE_IDS))
	@true

update-%: FORCE
	@[ -n "$(SLIVER_OVS)" ] || { echo "SLIVER_OVS not set" >&2; exit 1; }
	@[ -f "$(SLIVER_OVS)" ] || { echo "$(SLIVER_OVS) not found" >&2; exit 1; }
	@echo "Sending $(SLIVER_OVS) to $(call display,$*)"
	@scp $(SSH_KEY_OPTION) -q $(SLIVER_OVS) $(SLICE)@$(call solve,$*):
	@$(SSH) $(call solve,$*) $(SUDO) mv $(notdir $(SLIVER_OVS)) /usr/sbin/sliver-ovs

.SECONDEXPANSION:

# del-iface.<node_id>-<node_id>@<endpoint>:
# 	Deletes the interface of link <node_id1>-<node_id2> on either
# 	<node_id1> or <node_id2>, according to <endpoint>.
# 
# We need a running db daemon to do this, but we do not have to
# redo the delete if the db daemon is restarted.
#
# This also invalidates the local port of the tunnel and the endpoint
# info on both sides of the tunnel. The link goes down.
del-iface.%: | cache/db.$$(call get,%)
	@echo "Removing interface for link $(call linkpart,$*) from $(call get,$*)"
	@$(SSH) $(HOST_$(call get,$*)) \
		$(SUDO) sliver-ovs del-port L$(call linkpart,$*)
	@rm -f cache/iface.$* \
	       cache/port.$* cache/endpoint.$* cache/endpoint.$(call opp,$*) \
	       L/$(call linkpart,$*)


### '%' here is leftid-rightid@{1,2}
# we retrieve % as $(*F)
#linkid=$(call linkpart,%)
#nodeid=$(call get,%)
#bridgefile=cache/bridge.$(nodeid)

# cache/iface.<node_id1>-<node_id2>@<endpoint>:
# 	Creates the interface for link <node_id1>-<node_id2> on
# 	<node_id<endpoint>>. 
#
# The bridge of the local node must already exist, and we need to create
# the interface again if the bridge is re-created.
# We also need a running db daemon, but we do not need to do anything
# if the db daemon is restarted.
cache/iface.%: cache/bridge.$$(call get,%) | cache/db.$$(call get,%)
	@echo "Creating interface for link $(call linkpart,$(*F)) on $(call display,$(call get,$(*F))) - logs in $(call log,$@)"
	@$(SSH) $(call solve,$(call get,$(*F))) $(SUDO) sliver-ovs create-port $(BRIDGE) \
		L$(call linkpart,$(*F)) > $(call log,$@) 2>&1
	@touch $@

# cache/port.<node_id1>-<node_id2>@<endpoint>:
# 	Retrieves the local port of link <node_id1>-<node_id2> on
# 	node <node_id<endpoint>>.
#
# The local interface must have been created already and the
# switch daemon must be running. We need to retrieve the port
# number again if the interface is re-created, or the switch
# daemon is restarted.
cache/port.%: cache/iface.% cache/switch.$$(call get,%)
	@echo "Getting port number for link $(call linkpart,$(*F)) on $(call display,$(call get,$(*F))) - logs in $(call log,$@)"
	@$(SSH) $(call solve,$(call get,$(*F))) $(SUDO) \
		sliver-ovs get-local-endpoint L$(call linkpart,$(*F)) > $@ 2> $(call log,$@)


# linkid=$(call linkpart,%)
# nodeid=$(call get,%)
# iface1=cache/iface.%
# iface2=cache/iface.$(call opp,%)

# cache/endpoint.<node_id1>-<node_id2>@<endpoint>:
# 	Sets the other side (IP address, UDP port) info for link <node_id1>-<node_id2>
# 	on <node_id<endpoint>>.
#
# We need the IP address and the UDP port of the other side and the interace of this side.
# We need to set the info again if any of these change.
cache/endpoint.%: cache/host.$$(call rget,%) cache/port.$$(call opp,%) cache/iface.% | cache/db.$$(call get,%)
	@echo "Setting port number of link $(call linkpart,$(*F)) on $(call display,$(call get,$(*F))) - logs in $(call log,$@)"
	@$(SSH) $(call solve,$(call get,$(*F))) $(SUDO) sliver-ovs set-remote-endpoint L$(call linkpart,$(*F)) \
			$$(cat cache/host.$(call rget,$(*F))) \
			$$(cat cache/port.$(call opp,$(*F))) 2> $(call log,$@)
	@touch $@

####################
CLEANTARGETS=$(addprefix del-,$(notdir $(wildcard cache/bridge.*)))
clean: $(CLEANTARGETS)
distclean:
	rm -rf L log cache
.PHONY: clean distclean

####################
graph.dot:
	( echo "digraph $(SLICE) {"; ls L | sed 's/$(SEP)/->/;s/$$/;/'; echo "}" ) > $@
graph.ps: graph.dot
	dot -Tps < $^ > $@	

####################
# googlemap stuff
# Uses:
# GMAP_SERVER, the hostname that runs an ndnmap instance
# GMAP_PROBES, a list of tuples of the form
# <linkid>=<nodeid>=<internal_linkid>=<frequency>
# e.g.
# SENDER-MUX=SENDER=3=0.5
# which would mean, the link 'SENDER-MUX' should be monitored at the 'SENDER' node and is coded 
# in links.json with id=3, every half second
# sliver-ovs gmap-probe is designed to run in background,
# and so that a new run will kill any previously running instance
gprobes: $(foreach probe,$(GMAP_PROBES),gprobe-$(probe))

gprobe-%: FORCE
	$(SSH) -n $(call solve,$(word 2,$(subst @, ,$(*F)))) $(SUDO) \
	sliver-ovs gmap-probe L$(word 1,$(subst @, ,$(*F))) $(GMAP_SERVER) $(word 3,$(subst @, ,$(*F))) $(word 4,$(subst @, ,$(*F)))

jsons: routers.json links.json geocode.json
.PHONY: jsons

routers.json: $(CONF)
	@{  echo "[";   \
	    sep="  ";   \
	    for n in $(CONF_NODE_IDS); do \
	        echo "    $$sep\"$$n\"";  \
	        sep=", "; \
	    done; \
	    echo "]"; \
	  } > $@

links.json: $(foreach l,$(LINKS),cache/json.$(l))
	@{  echo "["; \
	    cat $^ | sed '2,$$s/^/, /'; \
	    echo "]"; \
	 } > $@

cache/json.%: $(CONF)
	@echo "{\"id\": $($*_linkid), \"start\": \"$(call get,$*@1)\", \"end\": \"$(call get,$*@2)\"}" > $@

geocode.json: $(foreach n,$(CONF_NODE_IDS),cache/geocode.$(n))
	@{  echo "{"; \
	    sep="  "; \
	    for f in $^; do \
	        echo -n "$$sep"; \
		cat $$f; \
		sep=", "; \
	    done; \
	    echo "}"; \
	 } > $@

cache/geocode.%: cache/loc.% $(CONF)
	@{  echo "\"$*\": {"; \
	    echo "    \"name\": \"$(HOST_$*)\","; \
	    echo "    \"shortname\": \"$*\","; \
	    echo "    \"site\": \"\","; \
	    echo "    \"backbone\": false,"; \
	    echo "    \"position\": [ $(shell cat cache/loc.$*) ]"; \
	    echo "   }"; \
	 } > $@

cache/loc.%: $(CONF)
	@wget -O - 'http://freegeoip.net/csv/$(HOST_$*)' | \
	    awk -F, '{ printf "%s, %s\n", $$8, $$9 }' > $@

####################
# 'virtual' targets in that there's no real file attached
define node_shortcuts
sshcheck.$(1): sshcheck-$(1) FORCE
db.$(1): cache/db.$(1) FORCE
switch.$(1): cache/switch.$(1) FORCE
start.$(1): cache/start.$(1) FORCE
stop.$(1): cache/stop.$(1) FORCE
status.$(1): cache/status.$(1) FORCE
bridge.$(1): cache/bridge.$(1) FORCE
host.$(1): cache/host.$(1) FORCE
controller.$(1): cache/controller.$(1) FORCE
# switch already depends on db, but well
cache/start.$(1): cache/db.$(1) cache/switch.$(1) FORCE
endef

$(foreach id,$(ALL_NODE_IDS), $(eval $(call node_shortcuts,$(id))))

define link_shortcuts
iface.%: cache/iface.%
endpoint.%: cache/endpoint.%
endef

$(foreach id,$(ALL_LINK_IDS), $(eval $(call link_shortcuts,$(id))))

help:
	@cat Makefile.help

#################### convenience, for debugging only
# make +foo : prints the value of $(foo)
# make ++foo : idem but verbose, i.e. foo=$(foo)
++%: varname=$(subst +,,$@)
++%:
	@echo "$(varname)=$($(varname))"
+%: varname=$(subst +,,$@)
+%:
	@echo "$($(varname))"

# external nodes and links
#
ALL_LINKS := $(LINKS) $(patsubst L/%,%,$(filter L/%,$(MAKECMDGOALS)))
EXTERNAL_LINKS := $(filter $(foreach host,$(EXTERNAL_HOSTS),%-$(host)),$(ALL_LINKS))

$(foreach host,$(EXTERNAL_HOSTS),sshcheck-$(host)): ;
$(foreach host,$(EXTERNAL_HOSTS),ovsversion-$(host)): ;
$(foreach host,$(EXTERNAL_HOSTS),showdpid-$(host)): ;
$(foreach host,$(EXTERNAL_HOSTS),showmac-$(host)): ;
$(foreach host,$(EXTERNAL_HOSTS),showports-$(host)): ;
$(foreach host,$(EXTERNAL_HOSTS),update-$(host)): ;
$(foreach host,$(EXTERNAL_HOSTS),del-controller-$(host)): ;
$(foreach host,$(EXTERNAL_HOSTS),cache/status.$(host)): ;
$(foreach host,$(EXTERNAL_HOSTS),cache/controller.$(host)): ;

$(foreach host,$(EXTERNAL_HOSTS),cache/rsnap.ip.$(host)): ;
	@touch $@

$(foreach host,$(EXTERNAL_HOSTS),cache/rsnap.links.$(host)): ;
	@touch $@

$(foreach host,$(EXTERNAL_HOSTS),cache/db.$(host)):
	@touch $@

$(foreach host,$(EXTERNAL_HOSTS),del-db.$(host)): del-db.%:
	@rm cache/db.$*

$(foreach host,$(EXTERNAL_HOSTS),cache/switch.$(host)): ;
	@touch $@

$(foreach host,$(EXTERNAL_HOSTS),del-switch.$(host)): del-switch.%:
	@rm -f cache/switch.$* \
	       cache/port.$*$(SEP)*@1  cache/port.*$(SEP)$*@2  \
	       cache/endpoint.$*$(SEP)*@2  cache/endpoint.*$(SEP)$*@1  \
	       L/$*$(SEP)*	      L/*$(SEP)$* \
	       cache/controller.$*

.SECONDEXPANSION:

$(foreach host,$(EXTERNAL_HOSTS),cache/bridge.$(host)): cache/bridge.%: | cache/db.%
	@echo "Creating fake bridge on external host $(call display,$*)"
	@touch $@

$(foreach host,$(EXTERNAL_HOSTS),cache/stop.$(host)): cache/stop.%: | del-bridge.%
	@echo "Stopping fake switch & db on $(call display,$*)"
	rm cache/switch.$* cache/db.$*

$(foreach link,$(EXTERNAL_LINKS),cache/iface.$(link)@2): cache/iface.%: cache/bridge.$$(call get,%) | cache/db.$$(call get,%)
	@echo "Creating fake interface for link $(call linkpart,$*) on external host $(call get,$*)"
	@touch $@

$(foreach link,$(EXTERNAL_LINKS),cache/port.$(link)@2): cache/port.%: cache/iface.% cache/switch.$$(call get,%)
	@echo "Getting port number for link $(call linkpart,$(*F)) on external host $(call display,$(call get,$(*F)))"
	@echo $(call default,EXTERNAL_PORT,$(call rightnode,$*)) > $@


$(foreach link,$(EXTERNAL_LINKS),del-iface.$(link)@2): del-iface.%: | cache/db.$$(call get,%)
	@echo "Removing fake interface for link $(call linkpart,$*) from external host $(call get,$*)"
	@rm -f cache/iface.$* \
	       cache/port.$* cache/endpoint.$* cache/endpoint.$(call opp,$*) \
	       L/$(call linkpart,$*)

$(foreach host,$(EXTERNAL_HOSTS),del-bridge.$(host)): del-bridge.%: | cache/db.%
	@echo "Deleting fake bridge on external host $(call display,$*)"
	@rm -f cache/bridge.$* \
	      cache/iface.$*$(SEP)*@1 cache/iface.*$(SEP)$*@2 \
	      cache/port.$*$(SEP)*@1  cache/port.*$(SEP)$*@2  \
	      cache/endpoint.$*$(SEP)*@?  cache/endpoint.*$(SEP)$*@?  \
	      L/$*$(SEP)*	      L/*$(SEP)$* \
	      cache/controller.$*

# we assume that a program called tunproxy is available on the
# external nodes.  
$(foreach link,$(EXTERNAL_LINKS),cache/endpoint.$(link)@2): cache/endpoint.%@2: cache/port.%@1 cache/host.$$(call leftnode,%)
	@#echo $* [$<] [$^] $(call rightnode,$*)
	@echo "===>" $(call rightnode,$*): \
	   ./tunproxy -t $$(cat cache/host.$(call leftnode,$*)):$$(cat cache/port.$*@1) \
           -p $(call default,EXTERNAL_PORT,$(call rightnode,$*)) -e -d


/*
#asset(qx/icon/Tango/16/apps/utilities-statistics.png)
  Copyright (c) 2013 Felician Nemeth, Levente Csikor
  This file may be used under the terms of either the

  * GNU Lesser General Public License (LGPL)
    http://www.gnu.org/licenses/lgpl.html

or the

  * Eclipse Public License (EPL)
    http://www.eclipse.org/org/documents/epl-v10.php
*/

qx.Class.define("poxdesk.Map",
{
  extend : qx.core.Object,
  
  events :
  {
  },
  
  properties :
  {    

  },
  
  construct : function()
  {
    this._container = new poxdesk.ui.window.Window("Map");
    this._container.addListener("close", this.dispose, this);
    this._container.set({
      icon: "icon/16/categories/internet.png",
      width: 380,
      height: 280,
      contentPadding : [ 0, 0, 0, 0 ],
      allowMaximize : true,
      showMaximize : true
    });
    this._container.setLayout(new qx.ui.layout.VBox());

      this._html = new qx.ui.embed.Html();
      this._container.add(this._html, {flex: 1});
      this._html.addListener("resize", this.on_resize, this);

      this._messenger = new poxdesk.Messenger();
      this._messenger.start();
      this._messenger.addListener("connected", function (e) {
	  var data = e.getData();
	  this.debug("CONNECTED session " + data.getSession());
	  var chan = "poxdesk_topo";//"openflow" + data.getSession() + "_" + data.toHashCode();
	  this._messenger.join(chan);
	  this._messenger.addChannelListener(chan, this._on_message, this);
      }, this);

      this._nodes = {};
      this._edges = {};
  },

  destruct : function() {
    this._disposeObjects("_messenger");
  },
  
    members :
    {
	_myGraph : 0,

    _get_color : function (i)
    {
	i = i * 8;  //bits;
	var rgb = [
	    [0.00, [0, 0, 0]],
	    [1000, [100, 100, 100]],
	    [5000, [115, 255, 000]],
	    [10000, [000, 255, 000]],
	    [500000, [000, 255, 255]],
	    [1000000, [000, 000, 255]],
	    [50000000, [255, 000, 255]],
	    [100000000, [255, 000, 000]],
	    [1000000000, [125, 000, 000]]
	];
        var a, b, a_i, b_i;
        var len = rgb.length;
        for (var j =0; j < len; j++) {
            if ( i < rgb[len - 1 - j][0] ) {
                b = rgb[len - 1 - j][1];
                b_i = rgb[len - 1 - j][0];
            }
            if ( i >= rgb[j][0] ) {
                a = rgb[j][1];
                a_i = rgb[j][0];
            }
        }
        var f = (i - a_i) / (b_i - a_i);
        var str = 'rgb('
            + Math.round(a[0]*(1-f) + b[0]*f) + ','
            + Math.round(a[1]*(1-f) + b[1]*f) + ','
            + Math.round(a[2]*(1-f) + b[2]*f) + ')';
        return str;
    },

    _get_load_str : function (load)
    {
	if (load <= 0) {
	    return load;
	}
	var units = [ '', 'K', 'M', 'G', 'T'];
	var bits = load * 8;
	var digits = Math.floor(Math.log(bits)/Math.log(10));
	var prec = 2 - (digits % 3);
	bits = bits / Math.pow(1000, Math.floor(digits/3));
	bits = bits.toFixed(prec);
	var unit = units[ Math.floor(digits/3) ];
	var load_str = bits + " " + unit + "bps";
	return load_str;
    },

	_create_map: function() {
	    // This creates the basic map and the layers
	    //cloudMade variables
	    var cloudmadeUrl = 'http://{s}.tile.cloudmade.com/4a7c0429db7c451a96d6f733f5b4a104/{styleId}/256/{z}/{x}/{y}.png';
	    var cloudmadeAttribution =  'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors, <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="http://cloudmade.com">CloudMade</a>';
	    //cloudMade styles
	    var minimalStyle = L.tileLayer(cloudmadeUrl, {styleId: 22677,
                               attribution: cloudmadeAttribution});
	    var ownStyle     = L.tileLayer(cloudmadeUrl, {styleId: 101946,
                               attribution: cloudmadeAttribution});
	    var defaultStyle = L.tileLayer(cloudmadeUrl, {styleId: 997,
			       attribution: cloudmadeAttribution});
	    //creating the map
	    var center = new L.LatLng(50.11, 8,68);
	    this.map = L.map('my_map', {
		center: center,
		zoom: 4,
		layers: [ownStyle]
	    });
	    //basic maps
	    var baseMaps = {
		"Pure": ownStyle,
		"Minimal":minimalStyle,
		"Default":defaultStyle
	    };
	    //adding different layers to the map
	    L.control.layers(baseMaps).addTo(this.map);
            this._topo = new MapTopo(this.map);
	},

	after_resize: function() {
	    var size = this._html.getInnerSize();
	    var my_map = document.getElementById('my_map');
	    my_map.style.width = size.width + 'px';
	    my_map.style.height = size.height + 'px';

	    if (this.map == undefined) {
		this._create_map();
	    } else {
		var my_map = document.getElementById('my_map');
		this.map.invalidateSize(false);
	    }
	},

	on_resize : function(e) {
	    var size = this._html.getInnerSize();

	    if (this.map == undefined) {
		var html_str = "<div id=\"my_map\">";
		html_str += "div:my_map</div>";
		this._html.setHtml(html_str);
	    }

	    qx.event.Timer.once(this.after_resize, this, 20);
	},

	_on_message : function (data) {
	  if (data.topo == undefined) {
	    return;
	  }
	  var ne = data.topo.links;
	  var nn = data.topo.switches;

	  var all_node_names = qx.lang.Object.clone(nn);
	  var old_names = this._topo.get_nodes();

          qx.lang.Object.mergeWith(all_node_names, old_names);

	  //this.warn("SW: " + JSON.stringify(all_node_names));

	  for (var node_name in all_node_names)
	    {
    	      var old_node = this._topo.get_node(node_name);
	      var new_node = nn[node_name];

	      if (old_node !== undefined && new_node !== undefined)
	      {
		// We're good.
		latlng = old_node.getLatLng();
		if (latlng.lat != new_node.latitude ||
		    latlng.lng != new_node.longitude) {
		  var title = new_node.label || node_name;
		  this._topo.update_node(title,
					 new_node.latitude,
					 new_node.longitude);
		}
	      }
	      else if (old_node === undefined)
	      {
		// New node
		var title = new_node.label || node_name;
		if (('type' in new_node) && new_node.type == 'host') {
		  this._topo.add_standalone_host(title, new_node.latitude,
						 new_node.longitude, false);
		} else if (('type' in new_node) && new_node.type == 'qemu') {
		  this._topo.add_standalone_host(title, new_node.latitude,
						 new_node.longitude, true);
		} else {
		  this._topo.add_switch(title,
					new_node.latitude, new_node.longitude);
		}
	      }
	      else
	      {
		// Remove node...
		var title = node_name;
		this.debug('remove ' + title);
		this._topo.remove_node(title);
	      }
	    }

	  var dead_edge_names = qx.lang.Object.clone(this._topo.get_links());
	  for (var i = 0; i < ne.length; i++)
	  {
	    var a = ne[i][0];
	    var b = ne[i][1];
	    var load = ne[i][2];
	    if (a > b) { var x = a; a = b; b = x; } // Swap
	    var en = a + " " + b;
	    if (this._topo.check_link_presence(en)) {
	      delete dead_edge_names[en];
	    }
	    var c = this._get_color(load);
	    var l = this._get_load_str(load);

	    this._topo.update_link_cost(a, b, l, c);
	  }

	  for (var edge_name in dead_edge_names) {
	    this._topo.remove_link(edge_name);
	  }
	}
    }

});

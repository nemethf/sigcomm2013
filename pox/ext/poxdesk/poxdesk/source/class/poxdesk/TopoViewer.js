/*
#asset(qx/icon/Tango/16/categories/internet.png)

 This is an extended version of Murphy McCauley's TopoViewer.
*/

qx.Class.define("poxdesk.TopoViewer",
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
    this._switches = {};
    this._container = new poxdesk.ui.window.Window("TopoViewer");
    this._container.addListener("close", this.dispose, this);
    this._container.set({
      icon: "icon/16/categories/internet.png",
      width: 400,
      height: 400,
      contentPadding : [ 0, 0, 0, 0 ],
      allowMaximize : true,
      showMaximize : true
    });
    this._container.setLayout(new qx.ui.layout.VBox());
   
    this._canvas = new qx.ui.embed.Canvas().set({
      syncDimension: true
    });

    //alert(this._canvas.getContentElement());//Context2d());

    this._container.add(this._canvas, {flex: 1});







this.graph = new Graph();
var graph = this.graph;

//var jessica = graph.newNode({label: 'Jessica'});
//var barbara = graph.newNode({label: 'Barbara'});
//var jb = graph.newEdge(jessica, barbara, {directional: false, color: '#EB6841', label:"jessica<->barbara"});

var springy;

this._canvas.addListenerOnce('appear', function(){
var canvas = this._canvas.getContentElement().getDomElement();
jQuery(function(){
	springy = jQuery(canvas).springy({
		graph: graph
	});
});
  }, this);

this._canvas.addListener('redraw', function () {
  this.graph.notify();
}, this);





    this._messenger = new poxdesk.Messenger();
    this._messenger.start();
    this._messenger.addListener("connected", function (e) {
      var data = e.getData();
      this.debug("CONNECTED session " + data.getSession());
      this.chan = "poxdesk_topo";
      this._messenger.join(this.chan);
      this._messenger.addChannelListener(this.chan, this._on_topo, this);
      this.refresh();
    }, this);



this._nodes = {};
this._edges = {};

  },
  
 
  members :
  {

    refresh : function ()
    {
      this._messenger.send({'cmd':'refresh'}, 'poxdesk_topo');
    },

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

    _on_topo : function (data)
    {
      this.debug("LOG:" + JSON.stringify(data));
      if (data.topo)
      {
        var ne = data.topo.links;
        var nn = data.topo.switches;

        var all_node_names = qx.lang.Object.clone(nn);
        qx.lang.Object.mergeWith(all_node_names, this._nodes);

        //this.warn("SW: " + JSON.stringify(all_node_names));
        

        for (var node_name in all_node_names)
        {
          var old_node = this._nodes[node_name];
          var new_node = nn[node_name];

          if (old_node !== undefined && new_node !== undefined)
          {
            // We're good.
	      if (new_node.x) {
		  old_node.data.x = new_node.x;
	      }
	      if (new_node.y) {
		  old_node.data.y = new_node.y;
	      }
          }
          else if (old_node === undefined)
          {
            // New node
            this.debug(new_node);
	    var color = '#000000';
	    if ('type' in new_node) {
	      if (new_node.type == 'host') {
		color = '#EB6841';
	      }
	      if (new_node.type == 'qemu') {
		color = '#00FFFF';
	      }
	    }
            var n = this.graph.newNode({color: color, label:new_node.label || node_name});
	      if (new_node.x) {
		  n.data.x = new_node.x;
	      }
	      if (new_node.y) {
		  n.data.y = new_node.y;
	      }
            this._nodes[node_name] = n;
          }
          else
          {
            // Remove node...
            this.graph.removeNode(old_node);
            delete this._nodes[node_name];
          }
        }

        var dead_edge_names = qx.lang.Object.clone(this._edges);
        for (var i = 0; i < ne.length; i++)
        {
          var a = ne[i][0];
          var b = ne[i][1];
	  var load = ne[i][2];
          if (a > b) { var x = a; a = b; b = x; } // Swap
          var en = a + " " + b;
          if (this._edges[en] === undefined)
          {
            // New edge
            var aa = this._nodes[a];
            var bb = this._nodes[b];
            if (!aa || !bb) continue;

            var c = this._get_color(load);
	      var l = this._get_load_str(load);
            var e = this.graph.newEdge(aa,bb, {directional:false, label: l, color: c});
            this._edges[en] = e;
          }
          else
          {
            delete dead_edge_names[en];

            var aa = this._nodes[a];
            var bb = this._nodes[b];
            if (!aa || !bb) continue;
            var e = this.graph.getEdges(aa,bb);
	    e[0].data['label'] = this._get_load_str(load);
	    e[0].data['color'] = this._get_color(load);
            this._edges[en] = e[0];
	    this.graph.notify();
          }
        }

        for (var edge_name in dead_edge_names)
        {
          var dead = dead_edge_names[edge_name];
          this.graph.removeEdge(dead);
          delete this._edges[edge_name];
        }

      }
    },





    _switches : null, // switches we know about
    _messenger : null,
    _container : null
    //_controls : null,
    //_timer : null
  },

  destruct : function() {
    this._messenger.leave(this.chan);
    this._disposeObjects("_messenger");
  }
});

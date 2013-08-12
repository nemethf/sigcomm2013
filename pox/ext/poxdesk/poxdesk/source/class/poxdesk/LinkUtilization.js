/*
#asset(qx/icon/Tango/16/apps/utilities-statistics.png)

  Copyright (c) 2013 Felician Nemeth
  This file may be used under the terms of either the

  * GNU Lesser General Public License (LGPL)
    http://www.gnu.org/licenses/lgpl.html

or the

  * Eclipse Public License (EPL)
    http://www.eclipse.org/org/documents/epl-v10.php

*/

function num_formatter_bps (obj, num) {
    var units = [ 'b', 'K', 'M', 'G', 'T'];
    var bits = num * 8;
    var digits = Math.floor(Math.log(bits)/Math.log(10));
    var prec = 2 - (digits % 3);
    bits = bits / Math.pow(1000, Math.floor(digits/3));
    bits = bits.toFixed(prec);
    var unit = units[ Math.floor(digits/3) ];
    var num_str = bits + " " + unit;
    return num_str;
}


qx.Class.define("poxdesk.LinkUtilization",
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
    this._container = new poxdesk.ui.window.Window("LinkUtilization");
    this._container.addListener("close", this.dispose, this);
    this._container.set({
      icon: "icon/16/apps/utilities-statistics.png",
      width: 400,
      height: 200,
      contentPadding : [ 0, 0, 0, 0 ],
      allowMaximize : true,
      showMaximize : true
    });
    this._container.setLayout(new qx.ui.layout.VBox());

      this._html = new qx.ui.embed.Html();
      this._container.add(this._html, {flex: 1});
      this._html.addListener("resize", this.on_resize, this);
      this.data = [[0,0,0,0,0,0,0,0,0,0]];
      this.keys = ['no traffic'];

      this._messenger = new poxdesk.Messenger();
      this._messenger.start();
      this._messenger.addListener("connected", function (e) {
	  var data = e.getData();
	  this.debug("CONNECTED session " + data.getSession());
	  var chan = "link_util";//"openflow" + data.getSession() + "_" + data.toHashCode();
	  this._messenger.join(chan);
	  this._messenger.addChannelListener(chan, this._on_message, this);
      }, this);

  },

  destruct : function() {
    this._disposeObjects("_messenger");
  },
  
    members :
    {
	_myGraph : 0,

	after_resize: function() {

	    this._myGraph = new RGraph.Line(this._rgraph_id_str, this.data);
	    this._myGraph.Set('chart.hmargin', 10);
	    this._myGraph.Set('chart.tickmarks', 'circle');
	    //this._myGraph.Set('chart.labels', ['Fred','John','Kev','Lou','Pete']);
	    this._myGraph.Set('chart.scale.formatter', num_formatter_bps)
	    this._myGraph.Set('chart.ylabels.inside', false);
	    this._myGraph.Set('chart.gutter.left', 50);
	    this._myGraph.Set('chart.key', this.keys);
	    this._myGraph.Set('chart.key.position', 'gutter');
	    // this._myGraph.Set('chart.key.shadow', true);
            // this._myGraph.Set('chart.key.shadow.offsetx', 0);
            // this._myGraph.Set('chart.key.shadow.offsety', 0);
            // this._myGraph.Set('chart.key.shadow.blur', 20);
            // this._myGraph.Set('chart.key.shadow.color', 'rgba(128,128,128,0.5)');
            // this._myGraph.Set('chart.key.background', 'white');
	    //this._myGraph.Set('chart.key.interactive', true);
	    this._myGraph.Draw();

	},

	on_resize : function(e) {
	    var size = this._html.getInnerSize();
	    this._rgraph_id_str = "rgraph-" + this._container.$$hash;
	    var html_str = "<canvas id=\"" + this._rgraph_id_str + "\" ";
	    html_str += "width=\"" + size.width + "\" ";
	    html_str += "height=\"" + size.height + "\">";
	    html_str += "[No canvas support]</canvas>";
	    this._html.setHtml(html_str);

	    qx.event.Timer.once(this.after_resize, this, 20);
	},

	_on_message : function (msg) {
	    this.data =  msg['data']
	    this.keys =  msg['keys']
	    this._myGraph.original_data = this.data;
	    this._myGraph.Set('chart.key', this.keys);
	    RGraph.Redraw();
	}

    }

});

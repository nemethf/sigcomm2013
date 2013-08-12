/*
#asset(qx/icon/Tango/16/categories/system.png)
  Copyright (c) 2013 Felician Nemeth
  This file may be used under the terms of either the

  * GNU Lesser General Public License (LGPL)
    http://www.gnu.org/licenses/lgpl.html

or the

  * Eclipse Public License (EPL)
    http://www.eclipse.org/org/documents/epl-v10.php
*/

qx.Class.define("poxdesk.TopoSelector",
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
    this._container = new poxdesk.ui.window.Window("TopoSelector");
    this._container.addListener("close", this.dispose, this);
    this._container.set({
      icon: "icon/16/categories/system.png",
      width: 200,
      height: 200,
      contentPadding : [ 0, 0, 0, 0 ],
      allowMaximize : true,
      showMaximize : true
    });
    this._container.setLayout(new qx.ui.layout.VBox());
   
    this._canvas = new qx.ui.embed.Canvas().set({
      syncDimension: true
    });

    //alert(this._canvas.getContentElement());//Context2d());
    //alert(window.location.href);

    this._container.add(this._canvas, {flex: 1});

      var base_url = window.location.href;
      base_url = base_url.replace('poxdesk/source', 'topo_conf');

    this.iframe = new qx.ui.embed.Iframe().set({
        width: 200,
        height: 250,
        minWidth: 100,
        minHeight: 150,
        source: (base_url),
        decorator : null
    });
    this._container.add(this.iframe, {flex: 1});
  },

  destruct : function() {
  }
});

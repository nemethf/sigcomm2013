/* ************************************************************************

   qooxdoo - the new era of web development

   http://qooxdoo.org

   Copyright:
     2007-2008 1&1 Internet AG, Germany, http://www.1und1.de

   License:
     LGPL: http://www.gnu.org/licenses/lgpl.html
     EPL: http://www.eclipse.org/org/documents/epl-v10.php
     See the LICENSE file in the project's top-level directory for details.

   Authors:
     * Thomas Herchenroeder (thron7)
     * Fabian Jakobs (fjakobs)
     * Jonathan Weiß (jonathan_rass)

************************************************************************ */

/* ************************************************************************

#asset(demobrowser/*)

************************************************************************ */

/**
 * The main application class.
 */
qx.Class.define("demobrowser.Application",
{
  extend : qx.application.Standalone,

  construct : function()
  {
    this.base(arguments);

    // Include CSS files
    var uri = qx.util.ResourceManager.getInstance().toUri("demobrowser/css/style.css");
    qx.bom.Stylesheet.includeFile(uri);
    uri = qx.util.ResourceManager.getInstance().toUri("demobrowser/css/sourceview.css");
    qx.bom.Stylesheet.includeFile(uri);
  },


  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members :
  {
    // overridden
    main : function()
    {
      this.base(arguments);

      // Enable logging in source (or debug build)
      if (qx.core.Environment.get("qx.debug"))
      {
        qx.log.appender.Native;
        qx.log.appender.Console;
      }

      // Initialize the viewer
      this.viewer = new demobrowser.DemoBrowser;
      this.getRoot().add(this.viewer, {edge:0});
    },

    // overridden
    finalize : function()
    {
      this.base(arguments);

      this.viewer.dataLoader("script/demodata.json");
    }
  },


  /*
  *****************************************************************************
     DESTRUCTOR
  *****************************************************************************
  */

  destruct : function() {
    this._disposeObjects("viewer");
  }
});

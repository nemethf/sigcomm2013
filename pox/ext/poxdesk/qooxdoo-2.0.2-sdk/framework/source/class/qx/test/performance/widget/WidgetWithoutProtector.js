qx.Class.define("qx.test.performance.widget.WidgetWithoutProtector",
{
  extend : qx.test.performance.widget.AbstractWidget,

  members :
  {
    CREATE_ITERATIONS : 100,
    RESIZE_ITERATIONS : 50,
    DISPOSE_ITERATIONS : 100,

    _createWidget : function() {
      return new qx.test.performance.mock.NoProtector().set({decorator: "window"});
    }
  }
});
/* ************************************************************************

   qooxdoo - the new era of web development

   http://qooxdoo.org

   Copyright:
     2004-2008 1&1 Internet AG, Germany, http://www.1und1.de

   License:
     LGPL: http://www.gnu.org/licenses/lgpl.html
     EPL: http://www.eclipse.org/org/documents/epl-v10.php
     See the LICENSE file in the project's top-level directory for details.

   Authors:
     * Sebastian Werner (wpbasti)
     * Fabian Jakobs (fjakobs)

************************************************************************ */

/**
 * @tag noPlayground
 * @tag test
 */
qx.Class.define("demobrowser.demo.test.Table_CellEditor",
{
  extend : qx.application.Standalone,
  include : [demobrowser.demo.table.MUtil],

  members :
  {
    main: function()
    {
      this.base(arguments);

      this._container = new qx.ui.container.Composite(new qx.ui.layout.VBox(15)).set({
        padding: 20
      })
      this.getRoot().add(this._container);

      this.testCheckBoxEditor();
      this.testComboBoxEditor();
      this.testSelectBoxEditor();
      this.testPasswordEditor();
      this.testTextfieldEditor();
      this.testTextfieldEditorDynamic();
    },

    _addEditor : function(editorFactory, cellInfo)
    {
      cellInfo = qx.lang.Object.clone(cellInfo);

      var box = new qx.ui.container.Composite(new qx.ui.layout.HBox(20));

      var editor = editorFactory.createCellEditor(cellInfo);

      var editorContainer = new qx.ui.container.Composite().set({
        width: 200,
        height: 20
      })
      editor.setUserBounds(0, 0, 200, 20);
      editorContainer.add(editor);

      box.add(editorContainer);

      var btnValue = new qx.ui.form.Button("Get value");
      box.add(btnValue);
      btnValue.addListener("execute", function() {
        label.setValue(editorFactory.getCellEditorValue(editor) + "");
      });

      var btnAddRemove = new qx.ui.form.Button("Add/Remove editor");
      box.add(btnAddRemove);
      btnAddRemove.addListener("execute", function()
      {
        editor.destroy();
        qx.ui.core.queue.Manager.flush();

        editor = editorFactory.createCellEditor(cellInfo);
        editor.setUserBounds(0, 0, 200, 20);
        editorContainer.add(editor);
        qx.ui.core.queue.Manager.flush();
      });

      var label = new qx.ui.basic.Label("");
      box.add(label);

      this._container.add(box);
      btnValue.execute();
    },

    testCheckBoxEditor : function()
    {
      var cellInfoOptions = {
        value : [true, false]
      }

      qx.util.Permutation.permute(cellInfoOptions, function(cellInfo) {
        this._addEditor(new qx.ui.table.celleditor.CheckBox(), cellInfo);
      }, this);
    },

    testComboBoxEditor : function()
    {
      var cellInfoOptions = {
        value : ["", "cat", "rat", 2],
        table : [this.getTableMock()]
      }

      var factory = new qx.ui.table.celleditor.ComboBox();
      factory.setListData([
        "dog",
        "cat",
        "mouse"
      ]);

      qx.util.Permutation.permute(cellInfoOptions, function(cellInfo) {
        this._addEditor(factory, cellInfo);
      }, this);
    },

    testSelectBoxEditor : function()
    {
      var cellInfoOptions = {
        value : ["", "cat"],
        table : [this.getTableMock()]
      }

      var factory = new qx.ui.table.celleditor.SelectBox();
      factory.setListData([
        "dog",
        "cat",
        "mouse"
      ]);

      qx.util.Permutation.permute(cellInfoOptions, function(cellInfo) {
        this._addEditor(factory, cellInfo);
      }, this);
    },

    testPasswordEditor : function()
    {
      var cellInfoOptions = {
        value : [null, 10, "Juhu"]
      }

      qx.util.Permutation.permute(cellInfoOptions, function(cellInfo) {
        this._addEditor(new qx.ui.table.celleditor.PasswordField(), cellInfo);
      }, this);
    },

    testTextfieldEditor : function()
    {
      var cellInfoOptions = {
        value : [null, 10, "Juhu"]
      }

      qx.util.Permutation.permute(cellInfoOptions, function(cellInfo) {
        this._addEditor(new qx.ui.table.celleditor.TextField(), cellInfo);
      }, this);
    },

    testTextfieldEditorDynamic : function()
    {
      var cellInfoOptions = {
        value : [true, "Juhu"]
      }

      var editorFactory = new qx.ui.table.celleditor.Dynamic();
      editorFactory.setCellEditorFactoryFunction(function(cellInfo)
      {
        if (typeof cellInfo.value == "boolean") {
          return new qx.ui.table.celleditor.CheckBox();
        } else {
          return new qx.ui.table.celleditor.TextField();
        }
      });

      qx.util.Permutation.permute(cellInfoOptions, function(cellInfo) {
        this._addEditor(editorFactory, cellInfo);
      }, this);
    }
  },

  destruct : function() {
    this._disposeObjects("_container");
  }
});

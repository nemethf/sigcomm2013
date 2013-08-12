/*
# Copyright (c) 2013 Levente Csikor
#
# This file is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This file is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.  If not, see <http://www.gnu.org/licenses/>.
*/

/**
 * This creates a link object
 * @param {string} node_name1 - the name of one of the endpoint of the link
 * @param {string} node_name2 - the name of the other endpoint of the link
 * @param {L.LatLng} latLngs  - the L.LatLng object array consisting the
 * LatLng coordinates of the endpoints
 * @param {string} color      - color of the link
 * @param {string} cost - the cost of the link
 */
var MapLink = Class.create({

  initialize : function(node_name1, node_name2, latLngs, color, cost)
  {
    this.node_name1 = node_name1;
    this.node_name2 = node_name2;
    this.latLngs = latLngs;
    this.color = color;
    this.cost = cost;

    var name1 = this.node_name1;
    var name2 = this.node_name2;
    if (name1 > name2) {
      var x = name1;
      name1 = name2;
      name2 = x;
    }
    this.connected_nodes = name1 + " " + name2;

    //creating polyline
    this.polyline = new L.polyline(this.latLngs, {color: this.color});
    this.polyline.bindLabel(this.cost);

  },

  myToString : function()
  {
    return this.connected_nodes + " (" + this.cost + ") -- color: " + this.color;
  },

  /**
   * Get the latLng array of the link
   * @returns {Array} L.Latlng array
   */
  getLatLngs: function()
  {
    return this.latLngs;
  },

  /**
   * Setting the new latitude and longitude coordinates of the link
   * @param {Array} - the array of the L.LatLngs
   */
  setLatLngs: function(latLngs)
  {
    this.latLngs = latLngs;
    this.polyline.setLatLngs(this.latLngs);
  },

  /**
   * Gets the link's color
   * @returns {string} the color of the link
   */
  getColor : function()
  {
    return this.color;
  },

  /**
   * Sets the link's color
   * @param {string} color - the desired color
   */
  setColor : function(color)
  {
    this.color = color;
    this.polyline.setStyle({color: this.color});
  },

  /**
   * Gets the link's cost (label)
   * @returns {string}  the cost (label) of the link
   */
  getCost : function()
  {
    return this.cost;
  },

  /**
   * Sets the cost of the link
   * @param {string} cost - desired cost
   */
  setCost : function(cost)
  {
    this.cost = cost;
    this.polyline.updateLabelContent(this.cost);
  },

  /**
   * Gets an endpoint name of the link
   * @param {int} index - the index of the link (1 or 2)
   * @returns {string} the name of the selected node
   */
  getNodeName : function(index)
  {
    switch (index)
    {
      case 1:
        return this.node_name1;
        break;
      case 2:
        return this.node_name2;
        break;
      default:
        console.error("A link only connects two nodes -> possible index can be 1 or 2");
        break;

    }
  },

  /**
   * Gets the connected nodes' names as a string with a space between them
   * @returns {string}
   */
  getConnectedNodesAsString : function()
  {
    return this.connected_nodes;
  },

  /**
   * Gets the connected nodes' names as an array
   * @returns {Array}
   */
  getConnectedNodesAsArray : function()
  {
    var array = new Array();
    array.push(this.node_name1);
    array.push(this.node_name2);

    return array;
  },

  /**
   * Gets the polyline object of the link
   * @returns {L.polyline} the polyline object of the link
   */
  getPolyline : function()
  {
    return this.polyline;
  }

});

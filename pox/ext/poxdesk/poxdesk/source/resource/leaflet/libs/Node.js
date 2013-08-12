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
 * This class represents a node
 * @param {string} sw_name - Name of the node
 * @param {float|int} lat_orig - original latitude
 * @param {float|int} lng_orig - original lng
 * @param {float|int} lat - Latitude coordinate of the node
 * @param {float|int} lng - Longitude coordinate of the node
 * @param {int} type - Type of the node (0 = switch, 1 = host)
 * @param {int} standalone - 0 = non-standalone, 1 = standalone
 * @param {boolean} virtual - is it virtual host or not?
 */
var MapNode = Class.create({
  initialize: function(sw_name,lat_orig,lng_orig,
		       lat,lng,type, standalone, virtual)
  {
    //setting up the parameters
    this.sw_name = sw_name;
    this.position = new L.LatLng(lat,lng);
    this.orig_position = new L.LatLng(lat_orig, lng_orig);
    this.type = type;
    this.res = "resource/leaflet/";
//    this is useful when adding  and removing links, and it is set from different
    //methods to indicate that when a host is added, is it a standalone host or not.
    //Since if it was not standalone, we need to delete as well, when the
    //corresponding switch node is going to be deleted;
    this.standalone = standalone;
    this.virtual = virtual;

    //defining different icons
    this._switch_icon = L.icon
    (
      {
        iconUrl: this.res+'router.png',
        shadowUrl: this.res+'shadow.png',


        iconSize: [64,64],    // size of the icon
        shadowSize: [64,64],  // size of the shadow
        iconAnchor: [31,62],  // point of the icon which will correspond to marker's location
//        iconAnchor: [0,0],  // point of the icon which will correspond to marker's location
        shadowAnchor: [31,62],// the same for the shadow
        popupAnchor: [0,-60]  // point from which the popup should open relative to the iconAnchor
      }
    );


    this._host_icon =  L.icon
    (
      {
        iconUrl: this.res+'host.png',
        shadowUrl: this.res+'shadow.png',

        iconSize: [64,64],    // size of the icon
        shadowSize: [64,64],  // size of the shadow
        iconAnchor: [31,62],  // point of the icon which will correspond to marker's location
        shadowAnchor: [31,62],// the same for the shadow
        popupAnchor: [0,-60]  // point from which the popup should open relative to the iconAnchor
      }
    );


    this._virtual_host_icon =  L.icon
    (
      {
        iconUrl: this.res+'virtual_host.png',
        shadowUrl: this.res+'shadow.png',

        iconSize: [64,64],    // size of the icon
        shadowSize: [64,64],  // size of the shadow
        iconAnchor: [31,62],  // point of the icon which will correspond to marker's location
        shadowAnchor: [31,62],// the same for the shadow
        popupAnchor: [0,-60]  // point from which the popup should open relative to the iconAnchor
      }
    );
    //------------------------

    //setting icons
    switch(this.type)
    {
      case 0:
        this.icon = this._switch_icon;
        this.ple_image = "<img src=\'"+ this.res + "planetlabeurope_icon.png\' " +
                         "alt=\'PLE icon\' style=\'height:20px;margin-right:1px;\'>";
        break;

      case 1:
        if(!this.virtual)
        {
          this.icon = this._host_icon;
        }
        else
        {
          this.icon = this._virtual_host_icon;
        }


        if(this.standalone == 1)
        {
          if(this.virtual)
          {
            this.ple_image = "<img src=\'" + this.res + "qemu.png\' " +
              "alt=\'PLE icon\' style=\'width:20px; margin-right:1px;\'>";
          }
          else
          {
            if(Math.random() < 0.5)
            {
              this.ple_image = "<img src=\'" + this.res + "user_boy.png\' " +
                "alt=\'PLE icon\' style=\'height:20px;margin-right:1px;\'>";
            }
            else
            {
              this.ple_image = "<img src=\'" + this.res + "user_girl.png\' " +
                "alt=\'PLE icon\' style=\'width:20px;margin-right:1px;\'>";
            }
          }
        }
        else
        {
          this.ple_image = "<img src=\'" + this.res + "qemu.png\' " +
            "alt=\'PLE icon\' style=\'width:20px; margin-right:1px;\'>";
        }
        break;
      default :
        console.error("Type error during creating a node");
        break;

    }

    //setting up the marker object
    this.marker = new L.marker([this.position.lat, this.position.lng],
      {icon: this.icon});
    this.marker.setZIndexOffset(-2);


    this.info =  "" +
      "<b style=\'font-size:12px;\'>" + this.sw_name + "</b>" +
      this.ple_image;

  },

  /**
   * Prints out the node data
   * @returns {string} Node data
   */
  myToString: function()
  {
    return this.sw_name + " (" + this.position.lat + ", " + this.position.lng + ") is a " + this.type;
  },

  /**
   * Gets the node's coordinates
   * @returns {L.LatLng} L.LatLng object (position)
   */
  getLatLng: function()
  {
    return this.position;
  },

  /**
   * Gets original (non-corrected) coordinates
   * @returns {L.LatLng} - L.LatLng object of the coordinates
   */
  getOrigLatLng: function()
  {
    return this.orig_position;
  },

  /**
   * Sets/updates the original coordinates
   * @param {L.LatLng} lat_lng - the new coordinates to set as original coords
   */
  setOrigLatLng: function(lat_lng)
  {
    this.orig_position = lat_lng;
  },

  /**
   * Sets the node's LatLng
   * @param {L.LatLng} lat_lng - the desired coordinates
   */
  setLatLng: function(lat_lng)
  {
    this.position = lat_lng;
    this.marker.setLatLng(this.position);
  },

  /**
   * Gets the node's name
   * @returns {string}  name of the node
   */
  getName: function()
  {
    return this.sw_name;
  },

  /**
   * Sets the node's name
   * @param {string} sw_name - the desired name
   */
  setName : function(sw_name)
  {
    this.sw_name = sw_name;
  },

  /**
   * Gets the node's type
   * @returns {number}  type of the node (0 = Switch, or 1 = Host)
   */
  getType: function()
  {
    return this.type;
  },

  /**
   * Sets the node's type
   * @param {int} type - desired type of the node (0 - switch, 1 - host)
   */
  setType: function(type)
  {
    switch(type)
    {
      case 0:
        this.type = "Switch";
        this.icon = this._switch_icon;
        this.marker.setIcon(this.icon);
        break;
      case 1:
        this.type = "Host";
        this.icon = this._host_icon;
        this.marker.setIcon(this.icon);
        break;
      default:
        console.error("Node type can only be 0 or 1 indicating switch or host ");
        break;
    }

  },

  /**
   * Gets the marker object if needed
   * @returns {L.Marker}  the marker object
   */
  getMarker : function()
  {
    return this.marker;
  },

  /**
   * Returns the node's id
   * @returns {int} the node's id
   */
  getStandalone : function()
  {
    return this.standalone;
  },

  /**
   * Sets standalone value
   * @param {int} standalone - 0 - not standalone, 1 - standalone
   */
  setStandalone : function(standalone)
  {
    this.standalone = standalone;
  }


});


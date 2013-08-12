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
 * This is the basic topo class
 * * @param {L.map} map -  the L.map object
 */
var MapTopo = Class.create({
  initialize : function(map)
  {

    this._map = map;
    //variable, which stores all the nodes
    this.nodes = {};

    //links will store the polyline object and the endpoints' name of the polyline

    this.links = {};
    //varible for storing which switch has already a host -->
    //this is useful for creating only one cirle around the switch
    //to indicate and place the corresponding hosts

    this.switches_with_hosts = new Array();

    this.host_circle_color = "#aa00aa";

    this.host_circle_fillColor = "#00aa00";

    this.host_circle_radius = "40000";

    this.active_host_circles = {};

    this.virtual_host = {};

  },

  //======================== FUNCTION =======================================
  /**
   * CHECKING WHETHER THE GIVEN NODE EXISTS
   * @param {string} sw_name  - the name of the node
   * @returns {boolean} - true if node exists, false if not
   */
  check_node_presence : function(sw_name)
  {

//    return this.nodes.sw_name;     // always returns undefined :)
    return sw_name in this.nodes;  //returns true or false
//    return this.nodes[sw_name];  // This returns the node, or undefined
  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * CHECKING LAT-LNG COLLISION
   * the coordinates, which have to be corrected if necessary
   * this means, that if some node has the same coordinates,
   * then some small random fraction is added to avoid
   * complete overlapping.
   * Otherwise, they remain unchanged
   * @param {float|int} lat - latitude
   * @param {float|int} lng - longitude
   * @returns {L.LatLng} - the corrected coordinates as L.LatLng object
   */
  get_corrected_coords : function(lat,lng)
  {
    var coordinates = new L.LatLng(lat,lng)


    for (var n in this.nodes)
    {

      if((this.nodes[n].position.lat == lat) &&
        (this.nodes[n].position.lng == lng))
      {
        var correction1 = (Math.random()).toFixed(3);
        var correction2 = (Math.random()).toFixed(3);
        coordinates = new L.LatLng(
          parseFloat(lat) + parseFloat(correction1),
          parseFloat(lng) + parseFloat(correction2));
        console.log("Coordinates ( " + lat + ", " + lng +") are corrected in order to avoid " +
          "complete overlapping ( " + coordinates.toString() + ")");
        break;
      }

    }
    return coordinates;
  },
  //-------------------------------------------------------------------------



  //======================== FUNCTION =======================================
  /**
   * CHECKING THAT NO NODE EXISTS ALREADY WITH THE GIVEN NAME
   * IT IS ALSO USEFUL FOR CHECKING THAT A GIVEN NODE NAME EXISTS AND ITS NAME
   * IS CORRECT, BUT IT PRINTS OUT MANY MESSAGES -- USE check_node_presence() instead
   * @param {string} sw_name - given name for the node
   * @returns {boolean}  false = Node already exists, true = Node could be added
   */
  check_node_name_collision : function(sw_name)
  {
    var printOut;
    var retVal = true;

    for(var n in this.nodes)
    {
      if(this.nodes[n].getName()	== sw_name)
      {
        printOut = "A node already exists with this name: " +
          sw_name + "--> Use a different, which does " +
          "not coincide with any of the following list";
        console.error(printOut);
        this.list_nodes();
        retVal = false;
        break;
      }
      else
      {
        //Node could be added
        retVal = true;
      }

    }

    return retVal;
  },
  //-------------------------------------------------------------------------

  //======================== FUNCTION =======================================
  /**
   * This function creates a node object and puts it onto the map
   * @param {string} sw_name  - desired name for the node
   * @param {number} lat      - latitude
   * @param {number} lng      - latitude
   * @param {int} type        - 0 = switch, 1 = host
   */
  create_node : function (sw_name,
			  lat_orig,lng_orig,
			  lat,lng,type, standalone, virtual)
  {
    var node = new MapNode(sw_name, lat_orig, lng_orig,
			   lat, lng, type, standalone, virtual);
    node.getMarker().bindPopup(node.info);
    node.getMarker().addTo(this._map);

    this.nodes[sw_name] = node;



  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * This function creates a link object and puts it onto the map
   * @param {string} node_name1 - the name of one of the endpoint of the link
   * @param {string} node_name2 - the name of the other endpoint of the link
   * @param {L.LatLng} latLngs  - the L.LatLng object array consisting the
   * LatLng coordinates of the endpoints
   * @param {string} color      - color of the link
   * @param {L.LatLng} labelPosition - the position of the label in L.LatLng format
   * @param {string} cost - the cost of the link
   */
  create_link : function (node_name1, node_name2, latLngs, color, labelPosition, cost)
  {
    var link = new MapLink(node_name1, node_name2, latLngs, color,  cost);
    link.getPolyline().addTo(this._map).showLabel(labelPosition);


    if(cost == " ")
    {
      link.getPolyline()._hideLabel();
    }
    else
    {
      link.getPolyline()._unhideLabel();
    }


    this.links[link.getConnectedNodesAsString()] = link;
//    console.log("=========== LabelPos between " + node_name1 + "-" + node_name2 + " = " + labelPosition);
  },
  //-------------------------------------------------------------------------

  //======================== FUNCTION =======================================
  /**
   * CREATING A SWITCH
   * @param {string} sw_name - name of the switch
   * @param {float}  lat     - latitude
   * @param {float}  lng     - longitude
   */
  add_switch : function(sw_name,lat,lng)
  {

    //console.log(sw_name);
    if(this.check_node_name_collision(sw_name))
    {
      var coords = this.get_corrected_coords(lat,lng);
      this.create_node(sw_name, lat, lng, coords.lat, coords.lng, 0, 1,false);
    }

  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * CREATING A STANDALONE HOST
   * @param {string} host_name - desired name
   * @param {float|int} lat - latitude
   * @param {float|int} lng - longitude
   */
  add_standalone_host : function(host_name, lat, lng, virtual)
  {
    if(arguments.length != 4)
    {
      console.error("Not enough arguments for add_standalone_host()!");
      return;
    }

    if(this.check_node_name_collision(host_name))
    {
      var coords = this.get_corrected_coords(lat,lng);
      this.create_node(host_name, lat, lng, coords.lat, coords.lng, 1 ,1, virtual);

    }
  },
  //-------------------------------------------------------------------------

  //======================== FUNCTION =======================================
  /**
   * CREATING A NON-STANADLONE HOST
   * @param {string} switch_name - the name of the switch to which the host is connected
   * @param {string} host_name   - the preferred name for host
   */
  add_non_standalone_host : function(switch_name, host_name)
  {
    //the node object, which will represent a created host node
    var node;
    if(arguments.length == 2)
    {
      //variable for storing the corresponding switch
      var found_switch;

      //it is useful when the corresponding switch will be deleted, since
      //we can identify whether the attached hosts should be deleted or not
      var standAloneHost;

      //checking that no node exists with the given name
      if(!this.check_node_name_collision(host_name))
      {
        console.error("This host_name is already exists!");
        return;
      }

      //host_name does not exist
      else
      {
        if(!(switch_name in this.nodes))
        {
          console.error("Corresponding switch not found!")
          return;
        }
        else
        {
          found_switch = this.nodes[switch_name];
        }


        //we need to put host close to the switch, since it will be a
        //non-standalone host

        //This host is not a standalone host
        standAloneHost = 0;
        //random shifting host coordinates to avoid overlapping
        var random_shift_coords = new Array();
        random_shift_coords[0] = (Math.random()/3).toFixed(3);
        random_shift_coords[1] = (Math.random()/3).toFixed(3);
        for (var i=0;i<random_shift_coords.length;i++)
        {
          if(Math.random() < 0.5)
          {
            random_shift_coords[i]= (-1)*random_shift_coords[i];
          }
        }

        //storing shifted coordinates
        var random_lat = parseFloat(found_switch.getLatLng().lat) + parseFloat(random_shift_coords[0]);
        var random_lng = parseFloat(found_switch.getLatLng().lng) + parseFloat(random_shift_coords[1]);
//                  console.log("adding non-standalone host " + host_name + " at " +
//                    random_lat + ", " +
//                    random_lng);
        var coordinates = this.get_corrected_coords(random_lat,random_lng);


        //adding host to nodes array
	var orig_latlng = found_switch.getLatLng();
        this.create_node(host_name,orig_latlng.lat, orig_latlng.lng,
			 coordinates.lat, coordinates.lng, 1, 0, true);
//        var switch_circle = new Array();
//        switch_circle.push(switch_name);
        this.draw_circle(found_switch);
        this.virtual_host[host_name] = switch_name;

        //-----------------------------------------------------

    }



  }
  //argument list was not properly set
  else
  {
    console.error("host's arguments are not properly set");
  }

  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * LIST SWITCHES THAT HAVE HOSTS ATTACHED TO IT
   */
  list_switches_with_hosts : function()
  {
    console.log("Listing switches with hosts");
    var len = this.switches_with_hosts.length;
    var n = 0;

    while (n < len)
    {
      console.log(this.switches_with_hosts[n].sw_name + " (" +
        this.switches_with_hosts[n].lat + ", " +
        this.switches_with_hosts[n].lng + ")" +
        " -- attached host: " + this.switches_with_hosts[n].host_name +
        " (standalone ?= " + this.switches_with_hosts[n].stand_alone_host +
        ")");

      n++;
    }
  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * CREATES A CIRCLE OBJECT FOR A NODE (DENOTING SWITCHES' HOST CIRCLE)
   * @param {node} node - the node object as the center of the circle
   * @returns {L.circle} the created circle object
   */
  draw_circle : function(node)
  {
    var circle = new L.circle([node.getLatLng().lat, node.getLatLng().lng], this.host_circle_radius,
      {
        color: this.host_circle_color,
        fillColor: this.host_circle_fillColor,
        fillOpacity: 0.5
      });



    if(node.getName() in this.active_host_circles)
    {
      return;
    }

    this.active_host_circles[node.getName()] = circle;
    circle.addTo(this._map);

  },
  //-------------------------------------------------------------------------



  //======================== FUNCTION =======================================
  /**
   * Removing one host circle from the map
   * @param {string} sw_name - the corresponding switch's name
   */
  remove_host_circle : function(sw_name)
  {
    console.log("removing host circle of " + sw_name);
    if(!(sw_name in this.active_host_circles))
    {
      console.error("Switch " + sw_name + " does not have any active host circle");
      return false;
    }

    //removing circle from the map
    this._map.removeLayer(this.active_host_circles[sw_name]);
    console.log("circle removed");
    //deleting the remaining element in the active_circle_host array
    delete this.active_host_circles[sw_name];

    return true;

  },
  //-------------------------------------------------------------------------



  //======================== FUNCTION =======================================
  /**
   * CHECKING THAT THE GIVEN COLOR IS RIGHT ACCORDING TO THE HTML CODES
   * @param {string} color_code - given color as string
   * @returns {boolean}  True = given color code was valid, False = otherwise
   */
  check_color_code : function(color_code)
  {
    var isValidHTMLColorCode = /^#[0-9a-f]{3}(?:[0-9a-f]{3})?$/i.test(color_code);

    var isValidRGBColorCode =
      /rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/i.test(color_code);

  //  console.log("isValidHTMLCode = " + isValidHTMLColorCode);
  //  console.log("isValidRGBCode = " + isValidRGBColorCode);

    if(isValidHTMLColorCode || isValidRGBColorCode)
    {
      return true;
    }
    else
    {
      return false;
    }
  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * ADDING LINKS BETWEEN SWITCHES
   * @param {string} switch1 - name of the first switch
   * @param {string} switch2 - name of the second switch
   * @param {number|string} cost - cost of the link
   * @param {string} color - color of the link -> it can only be HTML RGB codes,
   * (rgb(24,123,255) and HTML compatible color names (#ffaa00),
   * i.e.., red, black are not accepted
   */
  add_links : function(switch1, switch2, cost, color)
  {
    var link_cost;
    var c;
    var isOK = false;

    switch(arguments.length)
    {
      case 1:
        console.error("NOT ENOUGH ARGUMENTS");
        break;
      case 2:
        isOK = true;

        link_cost = "";
  //      console.log("Color was not set --> setting it to #0000ff");
        c = "#00f";

        break;
      case 3:
  //      console.log("Color was not set --> setting it to #0000ff");
        c = "#00f";

        if(cost != null && cost != "" && cost != undefined && cost != " ")
        {
          cost = cost.toString();
          link_cost = cost.replace(" ","&nbsp;");
        }
        else
        {
          link_cost = " ";
        }

        isOK = true;
        break;
      case 4:

  //      console.log("All params are set for add_links()");
        if(this.check_color_code(color))
        {
          c = color;
        }
        else
        {
          console.error("color attr.(" + color + ") was not compatible with " +
            "HTML RGB code(e.g., #00aabb) --> " +
            "Using color #000000 for color");
          c = "#000";
        }

        if(cost != null && cost != "" && cost != undefined && cost != " ")
        {
          cost = cost.toString();
          link_cost = cost.replace(" ", "&nbsp;");
        }
        else
        {
          link_cost = " ";
        }
        isOK = true;
        break;
      default:
        console.error("ILLEGAL ARGUMENT COUNT");
        break;
    }

    if(!isOK)
    {
      console.error("There was an error during add_link() function");
      return;
    }

    //looking for switches
    if (!(switch1 in this.nodes) || !(switch2 in this.nodes))
    {
      console.error("One of the given nodes does not exist!");
      return;
    }

    //variables for polylines
    var latLngs = new Array();

    var latLng1 = new L.LatLng(this.nodes[switch1].getLatLng().lat,
         this.nodes[switch1].getLatLng().lng);
    var latLng2 = new L.LatLng(this.nodes[switch2].getLatLng().lat,
         this.nodes[switch2].getLatLng().lng);

    latLngs.push(latLng1);
    latLngs.push(latLng2);


    //setting label position
//    var x,y;
//    x = (latLng1.lat + latLng2.lat)/2;
//    y = (latLng1.lng + latLng2.lng)/2;


    //converting latlngs more precisely
    var labelPosition = this.get_label_position(latLngs);


    //displaying links

      this.create_link(this.nodes[switch1].getName(),
                       this.nodes[switch2].getName(),
                       latLngs,
                       c,
                       labelPosition,
                       link_cost);

  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * LISTING ALL NODES
   */
  list_nodes : function()
  {
    console.log("# of nodes: " + Object.keys(this.nodes).length);

    for(var n in this.nodes)
    {
      console.log(this.nodes[n].getName() + " (" +
        this.nodes[n].getLatLng().lat + ", " +
        this.nodes[n].getLatLng().lng + ")" +
      " is standalone: " + this.nodes[n].getStandalone());

    }
  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * LISTING ALL SWITCHES
   */
  list_switches : function()
  {
    var number = 0;

    for(var n in this.nodes)
    {
      if(this.nodes[n].getType() == 0)
      {
        console.log(number + ": " +
          this.nodes[n].getName() + " (" +
          this.nodes[n].getLatLng().lat + ", " +
          this.nodes[n].getLatLng().lng + ")");
        number++;
      }
    }
    console.log("# of switches: " + number);
  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * LISTING ALL SWITCHES
   */
  list_hosts : function()
  {
    var number = 0;

    for(var n in this.nodes)
    {

      if(this.nodes[n].getType() == 1)
      {
        console.log(number + ": " +
          this.nodes[n].getName() + " (" +
          this.nodes[n].getLatLng().lat + ", " +
          this.nodes[n].getLatLng().lng + ")");
        number++;
      }

    }
    console.log("# of hosts: " + number);
  },
//-------------------------------------------------------------------------




  //======================== FUNCTION =======================================
  /**
   * LISTING ALL THE LINKS THAT HAVE BEEN ADDED
   */
  list_links : function()
  {
    console.log("# of links: " + Object.keys(this.links).length);

    for(var l in this.links)
    {
      console.log(this.links[l].myToString());
    }
  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * This function removes all the links that are added to the network
   * @returns {string} - message that every link was deleted
   */
  remove_links : function()
  {
    for(var l in this.links)
    {
      this.links[l].getPolyline().unbindLabel();
      this._map.removeLayer(this.links[l].getPolyline());
      delete this.links[l];
    }
//    var len = this.links.length;
//    while(len--)
//    {
//      //console.log(links[l][0] + " --- " + links[l][1] + ", " + links[l][2]);
//      this.links[len].getPolyline().unbindLabel();
//      this._map.removeLayer(this.links[len].getPolyline());
//      this.links.splice(len,1);
//    }
    return "All links are deleted with their labels";
  },
  //-------------------------------------------------------------------------




  //======================== FUNCTION =======================================
  /**
   * This function removes a particular link (order does not matter)
   * @param {string} switch1 - name of the switch
   * @param {string} switch2 - name of the switch
   * @returns {number} - status of the success
   */
  remove_particular_link : function(switch1, switch2)
  {
    var retVal = 0;

    for(var l in this.links)
    {
      //console.debug(links[l][1] + "-----" + links[l][2]);
      if((this.links[l].getNodeName(1) == switch1 && this.links[l].getNodeName(2) == switch2) ||
        (this.links[l].getNodeName(1) == switch2 && this.links[l].getNodeName(2) == switch1))
      {
        this.links[l].getPolyline().unbindLabel();
        this._map.removeLayer(this.links[l].getPolyline());
        retVal = "Link between " + switch1 + " and " + switch2 + " is deleted";
        console.log(retVal);
        this.links.splice(l,1);
        break;
      }
      else
      {
        retVal = "Switches (" + switch1 + ", " + switch2 + ") are not found";
        console.log(retVal);
      }
    }
    return retVal;
  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * Setting a particular link cost between two nodes (switch order does not matter)
   * @param {string} switch1 - one of the end of the link
   * @param {string} switch2 - other end of the link
   * @param {string} [cost]    - new cost
   * @param {string} [color]   - valid HTML color code for the link
   */
  update_link_cost : function(switch1, switch2, cost, color)
  {
    var link_cost = "";
    var c;
    var isOk = false;

    switch(arguments.length)
    {
      case 0:
        console.error("Missing at least one argument");
        break;
      case 1:
        console.error("Missing at least one argument");
        break;
      case 2:
        var randomCost = (Math.random()*100).toString().substring(0,5);

  //      console.log("Cost was not set between switches (" +
  //        switch1 + ", " + switch2 + ") ---> setting it randomly to "+
  //        randomCost +" Mbps");
        link_cost = randomCost + "&nbsp;Mbps";
  //      console.log("Color was not set for update_link_cost() --> " +
  //        "setting it to #0000ff");
        c = "#00f";
        isOk = true;
        break;
      case 3:
        if(cost != null && cost != "" && cost != undefined && cost != " ")
        {
          cost = cost.toString();
          link_cost = cost.replace(" ", "&nbsp;");
        }
        else
        {
          link_cost = " ";
        }

  //      console.log("Color was not set for update_link_cost() --> " +
  //        "setting it to #0000ff");
        c = "#00f";
        isOk = true;
        break;
      case 4:
        if(cost != null && cost != "" && cost != undefined && cost != " ")
        {
          cost = cost.toString();
          link_cost = cost.replace(" ","&nbsp;");
        }
        else
        {
          link_cost = " ";
        }


        if(!this.check_color_code(color))
        {
          console.error("color attr. was not compatible with " +
            "HTML or RGB code(e.g., #00aabb or rgb(42,24,111) --> " +
            "Using color #000000 for color");
          c = "#000";
        }
        else
        {
          c = color;
        }
        isOk = true;
        break;
      default :
        console.error("Too many parameters!");
        isOk = false;
        break;
    }

    if(isOk)
    {
      //chenking node presence
      if(this.check_node_presence(switch1) && this.check_node_presence(switch2))
      {
        var retVal = 0;

        for(var l in this.links)
        {
          if((this.links[l].getNodeName(1) == switch1 && this.links[l].getNodeName(2) == switch2) ||
            (this.links[l].getNodeName(1) == switch2 && this.links[l].getNodeName(2) == switch1))
          {
            retVal = "new cost ( " +
              link_cost + ") between " +
              this.links[l].getNodeName(1) + " and " +
              this.links[l].getNodeName(2);
//              console.log(retVal);

            this.links[l].setCost(link_cost);
            this.links[l].setColor(c);

            if(link_cost == " ")
            {
              this.links[l].getPolyline()._hideLabel();
            }
            else
            {
              this.links[l].getPolyline()._unhideLabel();
            }

            //updating current color for that polyline object
            this.links[l].color = c;
            break;
          }
        }
        if(retVal == 0)
        {
    //      console.log("Link not found between nodes " + switch1 + " and " + switch2);
    //      console.log("adding link");
          this.add_links(switch1,switch2, cost,c);
//          this.update_link_cost(switch1,switch2,cost,c);
        }
      }
      else
      {
        console.error("One of the given nodes (" +
          switch1 + ", " + switch2 + ") does not exists");
      }
    }
    else
    {
      console.error("Could not update link between " + switch1 + " and " + switch2);
    }
  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * Get a particular node from the network
   * @param {string} sw_name - the name of the node
   * @returns {Node} - the node element if found
   */
  get_node : function(sw_name)
  {
    for(var n in this.nodes)
    {
      if(this.nodes[n].sw_name == sw_name)
      {
        return this.nodes[n];
      }
    }

    return undefined;
  },
  //-------------------------------------------------------------------------


  //======================== FUNCTION =======================================
  /**
   * REMOVE A PARTICULAR NODE WITH ITS CORRESPONDING LINKS
   * @param {string} sw_name - the name of the node to delete
   * @returns {string} the status of success or failure
   */
  remove_node : function(sw_name)
  {
    var node_for_remove;
    var node_found = 0;

    if(sw_name === undefined || !sw_name in this.nodes)
    {
      console.error(sw_name + " not found!");
      return;
    }


      //removing marker
      this._map.removeLayer(this.nodes[sw_name].getMarker());

      //removing links from the map and deleting from  links array
      for(var l in this.links)
      {
        if((this.links[l].getNodeName(1) == sw_name) ||
          (this.links[l].getNodeName(2) == sw_name))
        {
  //				console.log("found link: " + links[len][1] + ", " + links[len][2]);
          //unbinding label
          this.links[l].getPolyline().unbindLabel();

          //removing layer
          this._map.removeLayer(this.links[l].getPolyline());

          //deleting from the array
          delete this.links[l];

        }
      }



      //This part checks whether the deleted node was a switch or only a host
      //In the former case, may other nodes,circle and markers should be deleted,
      //according to qemu hosts virtually run on the switch

      //variable to store the ids of the attached virtual hosts
      var attached_non_standalone_host = new Array();
      var node_of_the_circle_to_delete;
      if(this.nodes[sw_name].getType() == 0)
      {

        var hasVirtualHosts = false;
        for(var i in this.virtual_host)
        {
          if(this.virtual_host[i] == sw_name)
          {
            //removing virtualhosts
            this._map.removeLayer(this.get_node(i).getMarker());
            delete this.virtual_host[i];
            delete this.nodes[i];
            hasVirtualHosts = true;
          }
        }

        this._map.removeLayer(this.nodes[sw_name].getMarker());

        if(hasVirtualHosts)
        {
          //removing virtual host circle
          this.remove_host_circle(sw_name);
        }

        //removing node from nodes array
        delete this.nodes[sw_name];

        return;

      }

      //it was a standalone host
      //it could be simply deleted
      if(this.nodes[sw_name].getStandalone() == 1)
      {
        this._map.removeLayer(this.get_node(sw_name).getMarker());

        delete this.nodes[sw_name];
        return;
      }
      //it was a non-standalone host
      else
      {
        this._map.removeLayer(this.get_node(sw_name).getMarker());
        var iron = this.virtual_host[sw_name];
        delete this.virtual_host[sw_name];
        delete this.nodes[sw_name];
        var hasStillVirtualHosts = false;
        for(var j in this.virtual_host)
        {
          if(this.virtual_host[j] == iron)
          {
            //the main switch is still running a virtual host
            hasStillVirtualHosts = true;
            break;
          }
        }
        //nothing to do
        if(hasStillVirtualHosts)
        {
          return;
        }
        //ok we can now remove the circle
        this.remove_host_circle(iron);

      }

       console.log("Node (" + sw_name + ") and its corresponding links (and may attached non-standalone hosts) are deleted");

  },
  //-------------------------------------------------------------------------


  /**
   * Gets the names of all the nodes
   * @returns {Array}  an array of the nodes' name
   */
  get_nodes : function() {
    return this.nodes;
  },

  /**
   * Gets the names of all the links
   * @returns {Array}  an array of the links' connected_nodes variable
   */
  get_links : function () {
    return this.links;
  },

  /**
   * Checks whether a particular link exists or not
   * @param {string} name - name of the connected_nodes variable (i.e., n1 + " " + n2)
   * @returns {boolean}
   */
  check_link_presence : function (name) {
    return name in this.links;
  },

  /**
   * Remove link according to its connected_nodes variable
   * @param {string} name - the desired connected_nodes string (i.e., n1 + " " + n2)
   */
  remove_link : function (name)
  {
    if (name in this.links)
    {
      //getting endpoints as nodes
      var node1 = this.get_node(this.links[name].getNodeName(1));
      var node2 = this.get_node(this.links[name].getNodeName(2));


      this.links[name].getPolyline().unbindLabel();
      this._map.removeLayer(this.links[name].getPolyline());
      console.log("Link " + name + " deleted");
      delete this.links[name];

      //ok link is deleted, but what if now a host circle has to be destroyed?
      //we examine this case here
      //checking that the nodes were only switches or only hosts
      if(((node1.getType() == 0) && (node2.getType() == 0)) ||
        ((node1.getType() == 1) && (node2.getType() == 1)))
      {
        //nothing to do
        return;
      }

      //check that the hosts' standalone bit
      if((node1.getStandalone() == 1)  && node2.getStandalone() == 1)
      {
        //nothing to do
        return;
      }




      return true;
    }
    else
    {
      return false;
    }
  },

  /**
   * This procedure updates a node coordinates
   * @param {string} node_name - name of the node
   * @param {float|int} lat - new latitude
   * @param {float|int} lng - new longitude
   */
  update_node : function (node_name, lat, lng)
  {
    if (!node_name in this.nodes) {
      return;
    }
    var node = this.nodes[node_name];
    var pos = new L.LatLng(lat, lng);
    var old = node.getOrigLatLng();
    var actualPos = node.getLatLng();

    //during get_corrected_coords function it is possible that a coordinate
    //has been modified a bit, therefore if the corresponding node did not change
    //its position, we must not generate new coordinates for it
    if (pos.equals(old)) {
      return;
    }

    //we have to save the new changed position for the new original position
    node.setOrigLatLng(pos);
    var new_pos = this.get_corrected_coords(lat, lng);
    node.setLatLng(new_pos);

    //updating links as well
    var count = 0;
    var other_node_latlng;

    for(var l in this.links)
    {
      //for new latlng array for the polyline object
      var new_latlng_array = new Array();
      new_latlng_array.push(new_pos);

      //for new label pos
      var x,y;
      var labelPosition;
      if((this.links[l].getNodeName(1) == node_name) )
      {
        count++;
        console.log(count + " : Found the updating node: " + node_name);
        other_node_latlng = this.get_node(this.links[l].getNodeName(2)).getLatLng();
        new_latlng_array.push(other_node_latlng);
        this.links[l].setLatLngs(new_latlng_array);

        //setting label position
//        x = (new_pos.lat + other_node_latlng.lat)/2;
//        y = (new_pos.lng + other_node_latlng.lng)/2;

        labelPosition = this.get_label_position(new_latlng_array);
        this.links[l].getPolyline().showLabel(labelPosition);

      }
      else if(this.links[l].getNodeName(2) == node_name)
      {
        count++;
        console.log(count + " : Found the updating node: " + node_name);
        other_node_latlng = this.get_node(this.links[l].getNodeName(1)).getLatLng();
        new_latlng_array.push(other_node_latlng);
        this.links[l].setLatLngs(new_latlng_array);

        //setting label position
//        x = (new_pos.lat + other_node_latlng.lat)/2;
//        y = (new_pos.lng + other_node_latlng.lng)/2;

        labelPosition = this.get_label_position(new_latlng_array);
        this.links[l].getPolyline().showLabel(labelPosition);
      }
    }

  },

  /**
   * This will convert latlngs to layer points, then calculate the average
   * center between them, and returns that in converted LatLng object
   * @param {Array} latlng_array - latlng array consisting the latlngs of the two desired node
   * @return {L.LatLng} desired and converted correct LatLng for the label
   */
  get_label_position : function(latlng_array)
  {
    var coords_array = new Array();
    for(var i = 0;i<latlng_array.length; i++)
    {
      coords_array[i] = this._map.latLngToLayerPoint(latlng_array[i]);
    }

//    console.log(coords_array[0] + " =-=-=-=- " + coords_array[1]);

    var x = parseFloat((coords_array[0].x + coords_array[1].x)/2);
    var y = parseFloat((coords_array[0].y + coords_array[1].y)/2);

    var newLayerPoint = new L.Point(x,y);
    var newLatLng = this._map.layerPointToLatLng(newLayerPoint);

//    console.log("average layer point: " + newLayerPoint);
//    console.log("converted latLng: " + newLatLng);

    return newLatLng;
  }

});




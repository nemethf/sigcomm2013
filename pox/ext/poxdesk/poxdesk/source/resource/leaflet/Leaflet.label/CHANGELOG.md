Leaflet.draw Changelog
======================

## master

An in-progress version being developed on the master branch.

### Bug fixes

 * Fixed error in IE < 9 when trying to set the label z-index. (by [@arthur-e](https://github.com/arthur-e)). [#13](https://github.com/Leaflet/Leaflet.label/pull/25)
 * Fixed an issue when removing the click handler from the container to close labels in touch devices.

## 0.1.3 (May 02, 2013)

### Plugin improvements

 * Added method `L.Marker.setLabelNoHide()` to allow toggling of static marker labels. (inspired by [@kpwebb](https://github.com/kpwebb)). [#20](https://github.com/Leaflet/Leaflet.label/pull/20)
 * Non-static labels will now hide when map container is tapped on touch devices. (by [@snkashis](https://github.com/snkashis)). [#26](https://github.com/Leaflet/Leaflet.label/pull/26)
 * Added ability to set the opacity of the label along with the marker. (inspired by [@snkashis](https://github.com/snkashis)). [#20](https://github.com/Leaflet/Leaflet.label/pull/27)
 * Added support for mouse event to L.Label.
 * Added public getter to L.Marker to retrieve the label associated to a marker.

### Bug fixes

 * Fixed labels not updating position after being dragged. (by [@snkashis](https://github.com/snkashis)). [#13](https://github.com/Leaflet/Leaflet.label/pull/13)
 * Z-Index fixes aimed at static labels. This will ensure that label is shown at the same level as the marker.
 * Correctly remove event listeners in Marker.Label and Path.Label.

## 0.1.1 (December 10, 2012)

### Plugin improvements

 * FeatureGroup now supports label methods.

### Bug fixes

 * Fixed bug where label wouldn't hide when unbindLabel was called.
 * Fixed Multi-Poly support.
 * Fixed bug where a label's position wouldn't be updated when a marker moved.
 * Fixed bug where label wouldn't be removed from map when a marker was. 

## 0.1.0 (October 7, 2012)

Initial version of Leaflet.label

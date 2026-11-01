#!/bin/sh
# Local installed GIS runtime. All output paths are explicit; originals stay untouched.
export PROJ_DATA=/Applications/QGIS.app/Contents/Resources/qgis/proj
exec /Applications/QGIS.app/Contents/MacOS/python "$@"

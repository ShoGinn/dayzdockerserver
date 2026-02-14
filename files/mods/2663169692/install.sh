# Merge all the XML files into a single types.xml file in the run time mods directory:
source /files/bin/dz-common
cd /mods/221100/2663169692/files/types
xmlmerge -o /tmp/x *.xml
lint /tmp/x 2663169692 TYPES

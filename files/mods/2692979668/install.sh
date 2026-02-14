# Make helicopter parts, clothes, and accessories spawn on the map, as the default is for none to spawn.

echo "To make Red Falcon Helis parts and accessories spawn on the map, see files/mods/2692979668/install.sh"

# Comment out (or remove) the line below, and to apply, run: docker compose run --rm server dz x 2692979668
exit 0

echo "Adding Red Falcon Helis parts, clothes, and accessories to world spawns."

# Aviation fluid
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_hydraulic_fluid']/nominal" --value "20" /mods/221100/2692979668/types.xml

# Aviation tool box
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_aviation_toolbox']/nominal" --value "7" /mods/221100/2692979668/types.xml

# Aviation battery
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_aviation_battery']/nominal" --value "7" /mods/221100/2692979668/types.xml

# Hydraulic hoses
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_hydraulic_hoses']/nominal" --value "5" /mods/221100/2692979668/types.xml

# Igniter plug
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_igniter_plug']/nominal" --value "3" /mods/221100/2692979668/types.xml

# Wiring harness
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_wiring_harness']/nominal" --value "5" /mods/221100/2692979668/types.xml

# Flight case
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_flight_case']/nominal" --value "7" /mods/221100/2692979668/types.xml

# Flight case red
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_flight_case_red']/nominal" --value "3" /mods/221100/2692979668/types.xml

# Flight case blue
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_flight_case_blue']/nominal" --value "7" /mods/221100/2692979668/types.xml

# Aviation battery charger
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_batterycharger']/nominal" --value "5" /mods/221100/2692979668/types.xml

# Pilot helmet
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_PilotHelmet']/nominal" --value "1" /mods/221100/2692979668/types.xml

# Pilot helmet black
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_PilotHelmet_Black']/nominal" --value "1" /mods/221100/2692979668/types.xml

# Pilot helmet desert
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_PilotHelmet_Desert']/nominal" --value "1" /mods/221100/2692979668/types.xml

# Flag
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_Flag_RedFalcon']/nominal" --value "1" /mods/221100/2692979668/types.xml

# Hoodie
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_hoodie']/nominal" --value "1" /mods/221100/2692979668/types.xml

# RFFSHeli_hoodie_black
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_hoodie_black']/nominal" --value "1" /mods/221100/2692979668/types.xml

# RFFSHeli_PilotGloves
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_PilotGloves']/nominal" --value "1" /mods/221100/2692979668/types.xml

# RFFSHeli_PilotShirt
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_PilotShirt']/nominal" --value "1" /mods/221100/2692979668/types.xml

# RFFSHeli_PilotPants
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_PilotPants']/nominal" --value "1" /mods/221100/2692979668/types.xml

# RFFSHeli_PilotVest
xmlstarlet edit --inplace --update "/types/type[@name='RFFSHeli_PilotVest']/nominal" --value "1" /mods/221100/2692979668/types.xml


<!DOCTYPE qgis PUBLIC 'http://mapserver.org/qgis' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="verdict" forceraster="0"
               enableorderby="0" symbollevels="0">
    <categories>
      <category value="found" symbol="0" label="found (floor inside rim)" render="true"/>
      <category value="missed" symbol="1" label="MISSED" render="true"/>
    </categories>
    <symbols>
      <symbol type="fill" name="0" alpha="1" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <prop k="color" v="26,150,65,60"/><prop k="style" v="solid"/>
          <prop k="outline_color" v="26,150,65,255"/>
          <prop k="outline_style" v="solid"/><prop k="outline_width" v="0.5"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
      <symbol type="fill" name="1" alpha="1" clip_to_extent="1" force_rhr="0">
        <layer class="SimpleFill" enabled="1" locked="0" pass="0">
          <prop k="color" v="215,25,28,90"/><prop k="style" v="solid"/>
          <prop k="outline_color" v="215,25,28,255"/>
          <prop k="outline_style" v="solid"/><prop k="outline_width" v="1.2"/>
          <prop k="outline_width_unit" v="MM"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>

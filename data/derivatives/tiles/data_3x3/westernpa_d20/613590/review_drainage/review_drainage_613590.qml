<!DOCTYPE qgis>
<qgis version="3.34" styleCategories="Symbology|Fields|Forms|Default">
  <renderer-v2 type="categorizedSymbol" attr="status" forceraster="0" symbollevels="0" enableorderby="0">
    <categories>
      <category value="keep" symbol="0" label="keep (is drainage)" render="true"/>
      <category value="reject" symbol="1" label="reject (not drainage)" render="true"/>
      <category value="unsure" symbol="2" label="unsure" render="true"/>
      <category value="" symbol="3" label="(other)" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1">
          <Option type="Map">
            <Option name="line_color" type="QString" value="31,120,220,255"/>
            <Option name="line_width" type="QString" value="0.6"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
            <Option name="capstyle" type="QString" value="round"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="1" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1">
          <Option type="Map">
            <Option name="line_color" type="QString" value="227,26,28,255"/>
            <Option name="line_width" type="QString" value="0.9"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
            <Option name="capstyle" type="QString" value="round"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="2" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1">
          <Option type="Map">
            <Option name="line_color" type="QString" value="255,160,0,255"/>
            <Option name="line_width" type="QString" value="0.7"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
            <Option name="capstyle" type="QString" value="round"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="3" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1">
          <Option type="Map">
            <Option name="line_color" type="QString" value="150,150,150,255"/>
            <Option name="line_width" type="QString" value="0.4"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
            <Option name="capstyle" type="QString" value="round"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <fieldConfiguration>
    <field name="status">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option name="map" type="List">
              <Option type="Map"><Option name="keep" type="QString" value="keep"/></Option>
              <Option type="Map"><Option name="reject" type="QString" value="reject"/></Option>
              <Option type="Map"><Option name="unsure" type="QString" value="unsure"/></Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
  </fieldConfiguration>
  <defaults>
    <default field="status" expression="'keep'" applyOnUpdate="0"/>
  </defaults>
</qgis>

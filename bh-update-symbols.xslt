<?xml version="1.0"?>
<xsl:transform version="1.0"
               xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
               xmlns:svg="http://www.w3.org/2000/svg"
               xmlns:xlink="http://www.w3.org/1999/xlink"
               xmlns:set="http://exslt.org/sets"
               xmlns:exsl="http://exslt.org/common"
               extension-element-prefixes="set exsl">
  <xsl:output method="xml"
              indent="yes" />

  <xsl:param name="library"
             select="document('../symbols/bh-bits.svg')
                     | document('../symbols/bh-bales-48x24x18.svg')
                     | document('../symbols/bh-bales-42x18x16.svg')
                     | document('../symbols/bh-bales-36x18x15.svg')"/>
  <xsl:param name="verbose"/>

  <xsl:key name="uses"
           match="svg:use[starts-with(@xlink:href, '#')]"
           use="substring-after(@xlink:href, '#')"/>

  <xsl:key name="defs" match="/*/svg:defs/*[@id]" use="@id"/>

  <xsl:variable name="root-node" select="/*[1]"/>

  <xsl:template name="debug">
    <xsl:param name="elem" select="."/>
    <xsl:param name="message" select="''"/>
    <xsl:message>
      <xsl:value-of select="concat(name($elem), '#', $elem/@id)"/>
      <xsl:if test="$message">
        <xsl:value-of select="concat(': ', $message)"/>
      </xsl:if>
    </xsl:message>
  </xsl:template>


  <xsl:template name="update-or-add-def">
    <xsl:param name="id" select="@id"/>
    <xsl:for-each select="$root-node"> <!-- ensure context is source document -->
      <xsl:variable name="def-from-src" select="key('defs', $id)[1]"/>
      <xsl:variable name="search-lib">
        <xsl:for-each select="$library">
          <xsl:copy-of select="key('defs', $id)"/>
        </xsl:for-each>
      </xsl:variable>
      <xsl:variable name="defs-from-lib" select="exsl:node-set($search-lib)/*"/>
      <xsl:choose>
        <xsl:when test="count($defs-from-lib) > 0">
          <xsl:for-each select="$defs-from-lib[1]">
            <xsl:call-template name="debug">
              <xsl:with-param name="message">
                <xsl:choose>
                  <xsl:when test="$def-from-src">UPDATED</xsl:when>
                  <xsl:otherwise>ADDED</xsl:otherwise>
                </xsl:choose>
              </xsl:with-param>
            </xsl:call-template>
            <xsl:copy>
              <xsl:copy-of select="@*"/>
              <!-- strip @id from unreferenced children to prevent id conflicts -->
              <xsl:apply-templates select="node()" mode="strip-ids"/>
            </xsl:copy>
          </xsl:for-each>
        </xsl:when>
        <xsl:otherwise>
          <xsl:for-each select="$def-from-src">
            <xsl:if test="$verbose">
              <xsl:call-template name="debug">
                <xsl:with-param name="message">not in library</xsl:with-param>
              </xsl:call-template>
            </xsl:if>
            <xsl:apply-templates select="."/>
          </xsl:for-each>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:for-each>
  </xsl:template>

  <xsl:template match="*" mode="strip-ids">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()" mode="strip-ids"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="@*|comment()" mode="strip-ids">
    <xsl:copy-of select="."/>
  </xsl:template>

  <xsl:template match="@id" mode="strip-ids">
    <!-- Copy @id if it appears to be referenced -->
    <xsl:variable name="urlref" select="concat('url(#', ., ')')"/>
    <xsl:if test="key('uses', .)
                  | //@style[contains(., $urlref)]
                  | //@clip-path[contains(., $urlref)]">
      <xsl:copy-of select="."/>
    </xsl:if>
  </xsl:template>

  <xsl:template match="*">
    <xsl:copy>
      <xsl:copy-of select="@*"/>
      <xsl:apply-templates select="node()"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="comment()|processing-instruction()">
    <xsl:copy-of select="."/>
  </xsl:template>

  <xsl:template match="svg:defs">
    <xsl:copy>
      <xsl:copy-of select="@*"/>
      <xsl:for-each select="svg:symbol">
        <xsl:call-template name="update-or-add-def"/>
      </xsl:for-each>

      <xsl:variable
          name="all-defs"
          select="exsl:node-set($library)/*/svg:defs/* | /*/svg:defs/*"/>
      <xsl:for-each select="set:distinct($all-defs[not(self::svg:symbol)]/@id)">
        <xsl:call-template name="update-or-add-def">
          <xsl:with-param name="id" select="."/>
        </xsl:call-template>
      </xsl:for-each>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="/*">
    <xsl:copy>
      <xsl:copy-of select="@*"/>
      <!-- Add dummy attribute just to force namespace decl -->
      <xsl:attribute name="bh:placeholder"
                     namespace="http://dairiki.org/barnhunt/inkscape-extensions"
                     >dummy</xsl:attribute>
      <xsl:apply-templates select="node()"/>
    </xsl:copy>
  </xsl:template>

</xsl:transform>

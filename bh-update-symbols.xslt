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

  <xsl:key name="uses"
           match="svg:use[starts-with(@xlink:href, '#')]"
           use="substring-after(@xlink:href, '#')"/>

  <xsl:key name="ids" match="*[@id]" use="@id"/>
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


  <xsl:template name="emit-def">
    <xsl:param name="id" select="@id"/>
    <xsl:for-each select="$root-node"> <!-- ensure context is source document -->
      <xsl:variable name="orig" select="key('defs', $id)[1]"/>
      <xsl:variable name="defs-from-lib">
        <xsl:for-each select="$library">
          <xsl:copy-of select="key('defs', $id)"/>
        </xsl:for-each>
      </xsl:variable>
      <xsl:variable name="from-lib" select="exsl:node-set($defs-from-lib)/*"/>
      <xsl:choose>
        <xsl:when test="count($from-lib) > 0">
          <xsl:for-each select="$from-lib[1]">
            <xsl:call-template name="debug">
              <xsl:with-param name="message">
                <xsl:choose>
                  <xsl:when test="$orig">UPDATED</xsl:when>
                  <xsl:otherwise>ADDED</xsl:otherwise>
                </xsl:choose>
              </xsl:with-param>
            </xsl:call-template>
            <xsl:apply-templates mode="strip-child-ids"/>
          </xsl:for-each>
        </xsl:when>
        <xsl:otherwise>
          <xsl:for-each select="$orig">
            <!-- FIXME: only log message if verbose? -->
            <xsl:call-template name="debug">
              <xsl:with-param name="message">not in library</xsl:with-param>
            </xsl:call-template>
            <xsl:apply-templates/>
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

  <xsl:template match="@*" mode="strip-ids">
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

  <xsl:template match="*" mode="strip-child-ids">
    <xsl:copy>
      <xsl:copy-of select="@*"/>
      <xsl:apply-templates select="node()" mode="strip-ids"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="*" mode="delete-unused">
    <xsl:choose>
      <xsl:when test="not(key('uses', @id))">
        <xsl:call-template name="debug">
          <xsl:with-param name="message">unused symbol DELETED</xsl:with-param>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="emit-def"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="text()|comment()|processing-instruction()">
    <xsl:copy-of select="."/>
  </xsl:template>

  <xsl:template match="*" name="copy">
    <xsl:copy>
      <xsl:copy-of select="@*"/>
      <xsl:apply-templates select="node()"/>
    </xsl:copy>
  </xsl:template>


  <xsl:template match="svg:defs">
    <xsl:copy>
      <xsl:copy-of select="@*"/>
      <xsl:apply-templates select="svg:symbol" mode="delete-unused"/>

      <xsl:variable
          name="all-defs"
          select="exsl:node-set($library)//svg:defs/*
                  | /*/svg:defs/*"/>
      <xsl:for-each select="set:distinct($all-defs[not(self::svg:symbol)]/@id)">
        <xsl:call-template name="emit-def">
          <xsl:with-param name="id" select="."/>
        </xsl:call-template>
      </xsl:for-each>
    </xsl:copy>
  </xsl:template>

  <!-- Check for references to undefined symbols -->
  <xsl:template match="svg:use[starts-with(@xlink:href, '#')]">
    <xsl:variable name="use" select="substring-after(@xlink:href, '#')"/>
    <xsl:if test="not(key('ids', $use))">
      <xsl:message
          >Xlink to undefined target #<xsl:value-of select="$use"
          /></xsl:message>
    </xsl:if>
    <xsl:call-template name="copy"/>
  </xsl:template>


</xsl:transform>

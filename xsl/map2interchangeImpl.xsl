<?xml version="1.0" encoding="UTF-8"?>
<!--
  Preprocessed DITA map -> interchange site.json (see INTERCHANGE.md).
  Imported by map2interchange.xsl, followed by dita.xsl.interchange.map plug-ins.
-->
<xsl:stylesheet version="3.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:map="http://www.w3.org/2005/xpath-functions/map"
                xmlns:z="urn:x-dita-interchange"
                exclude-result-prefixes="xs map z">

  <!-- Folder of the map relative to content/, so page paths match the written fragments -->
  <xsl:param name="MAP_DIR" select="''"/>
  <xsl:param name="OUTEXT" select="'.html'"/>

  <xsl:variable name="map" select="/*[contains(@class, ' map/map ')]"/>

  <xsl:template match="/">
    <xsl:sequence select="map:merge((
        map { 'format': 'dita-interchange-site/1',
              'title': z:map-title($map),
              'source': string(($map/@xtrf, base-uri($map))[1]),
              'nav': array { $map/*[contains(@class, ' map/topicref ')] ! z:nav(.) } },
        (z:map-description($map)[. != ''] ! map { 'description': . }),
        ($map/@xml:lang ! map { 'language': string(.) }),
        z:site-metadata-extra($map)),
        map { 'duplicates': 'use-last' })"/>
  </xsl:template>

  <!-- Extension hook: return a map of extra site keys -->
  <xsl:function name="z:site-metadata-extra" as="map(*)?">
    <xsl:param name="map" as="element()"/>
    <xsl:sequence select="()"/>
  </xsl:function>

  <xsl:function name="z:map-title" as="xs:string">
    <xsl:param name="map" as="element()"/>
    <xsl:sequence select="normalize-space(string((
        $map/*[contains(@class, ' bookmap/booktitle ')]/*[contains(@class, ' bookmap/mainbooktitle ')],
        $map/*[contains(@class, ' topic/title ')],
        $map/@title)[1]))"/>
  </xsl:function>

  <xsl:function name="z:map-description" as="xs:string">
    <xsl:param name="map" as="element()"/>
    <xsl:sequence select="normalize-space(string(
        $map/*[contains(@class, ' map/topicmeta ')]/*[contains(@class, ' map/shortdesc ')]))"/>
  </xsl:function>

  <!-- Returns zero or more nav items (untitled groups are flattened) -->
  <xsl:function name="z:nav" as="map(*)*">
    <xsl:param name="ref" as="element()"/>
    <xsl:if test="not($ref/@toc = 'no' or $ref/@processing-role = 'resource-only')">
      <xsl:variable name="children" select="$ref/*[contains(@class, ' map/topicref ')] ! z:nav(.)"/>
      <xsl:variable name="title" select="z:navtitle($ref)"/>
      <xsl:variable name="target" as="map(*)?" select="
          if (z:is-topic($ref)) then map { 'page': z:page-path($ref) }
          else if (z:is-external($ref)) then map { 'url': string($ref/@href) }
          else ()"/>
      <xsl:choose>
        <xsl:when test="empty($target) and $title = ''">
          <xsl:sequence select="$children"/>
        </xsl:when>
        <xsl:when test="empty($target) and empty($children)"/>
        <xsl:otherwise>
          <xsl:sequence select="map:merge((
              $target,
              ($title[. != ''] ! map { 'title': . }),
              map { 'children': array { $children } }))"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:if>
  </xsl:function>

  <xsl:function name="z:navtitle" as="xs:string">
    <xsl:param name="ref" as="element()"/>
    <xsl:sequence select="normalize-space(string((
        $ref/*[contains(@class, ' map/topicmeta ')]/*[contains(@class, ' topic/navtitle ')],
        $ref/*[contains(@class, ' map/topicmeta ')]/*[contains(@class, ' map/linktext ')],
        $ref/@navtitle)[1]))"/>
  </xsl:function>

  <xsl:function name="z:is-external" as="xs:boolean">
    <xsl:param name="ref" as="element()"/>
    <xsl:sequence select="exists($ref/@href) and ($ref/@scope = 'external'
                          or matches($ref/@href, '^[a-zA-Z][a-zA-Z0-9+.\-]*:'))"/>
  </xsl:function>

  <xsl:function name="z:is-topic" as="xs:boolean">
    <xsl:param name="ref" as="element()"/>
    <xsl:sequence select="exists($ref/@href) and not(z:is-external($ref))
                          and (empty($ref/@format) or $ref/@format = 'dita')"/>
  </xsl:function>

  <!-- Path of the page fragment relative to content/ -->
  <xsl:function name="z:page-path" as="xs:string">
    <xsl:param name="ref" as="element()"/>
    <xsl:variable name="href" select="replace(substring-before($ref/@href || '#', '#'), '\.(dita|xml)$', $OUTEXT, 'i')"/>
    <xsl:variable name="decoded" select="replace(replace($href, '%20', ' '), '%25', '%')"/>
    <xsl:sequence select="z:normalize-path(string-join((tokenize($MAP_DIR, '/')[. != ''], tokenize($decoded, '/')), '/'))"/>
  </xsl:function>

  <xsl:function name="z:normalize-path" as="xs:string">
    <xsl:param name="path" as="xs:string"/>
    <xsl:iterate select="tokenize($path, '/')">
      <xsl:param name="out" as="xs:string*" select="()"/>
      <xsl:on-completion select="string-join($out, '/')"/>
      <xsl:next-iteration>
        <xsl:with-param name="out" select="
            if (. = ('', '.')) then $out
            else if (. = '..' and exists($out) and $out[last()] != '..') then $out[position() lt last()]
            else ($out, .)"/>
      </xsl:next-iteration>
    </xsl:iterate>
  </xsl:function>

</xsl:stylesheet>

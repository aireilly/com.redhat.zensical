<?xml version="1.0" encoding="UTF-8"?>
<!--
  Topic -> interchange page (see INTERCHANGE.md).

  Runs the stock org.dita.html5 topic transformation and keeps the <article> it
  produces. Principal output: that article as an XHTML5 fragment, otherwise
  unchanged apart from data-language / data-line-numbers on codeblocks.
  Secondary output: a JSON sidecar with the page metadata next to it.

  Nothing here knows about Zensical; publishing adapters read the result.
  Imported by topic2interchange.xsl, after which dita.xsl.interchange.topic
  plug-ins are imported, so they can override anything in this module.
-->
<xsl:stylesheet version="3.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:z="urn:x-dita-interchange"
                xmlns:dita="http://dita-ot.sourceforge.net"
                exclude-result-prefixes="xs z dita">

  <xsl:import href="plugin:org.dita.html5:xsl/dita2html5.xsl"/>

  <xsl:output name="z:json" method="json" encoding="UTF-8" indent="yes"/>

  <xsl:variable name="z:xhtml-ns" select="'http://www.w3.org/1999/xhtml'"/>

  <!-- html5 calls chapter-setup for the root /dita or topic; we replace <html><head><body> -->
  <xsl:template name="chapter-setup">
    <xsl:variable name="content" as="node()*">
      <xsl:apply-templates select="." mode="addContentToHtmlBodyElement"/>
    </xsl:variable>
    <xsl:variable name="article" as="element()?"
                  select="($content/descendant-or-self::*[local-name() = 'article'])[1]"/>
    <xsl:variable name="fragment" as="element()?">
      <xsl:apply-templates select="$article" mode="z:xhtml"/>
    </xsl:variable>

    <xsl:sequence select="$fragment"/>

    <xsl:result-document href="{replace(string(current-output-uri()), '\.[^./]+$', '') || '.json'}" format="z:json">
      <xsl:sequence select="z:page-metadata(., $fragment)"/>
    </xsl:result-document>
  </xsl:template>

  <!-- ============ Fragment: html5 output moved into the XHTML namespace ============ -->

  <xsl:template match="*" mode="z:xhtml">
    <xsl:element name="{local-name()}" namespace="{$z:xhtml-ns}">
      <xsl:apply-templates select="@*, node()" mode="z:xhtml"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="@* | text()" mode="z:xhtml">
    <xsl:copy/>
  </xsl:template>

  <xsl:template match="comment() | processing-instruction()" mode="z:xhtml"/>

  <xsl:template match="*[local-name() = 'pre'][tokenize(@class, '\s+') = 'codeblock']" mode="z:xhtml">
    <xsl:variable name="classes" select="tokenize(@class, '\s+')"/>
    <xsl:variable name="language" select="($classes[starts-with(., 'language-')] ! substring-after(., 'language-'))[. != ''][1]"/>
    <xsl:element name="pre" namespace="{$z:xhtml-ns}">
      <xsl:apply-templates select="@*" mode="z:xhtml"/>
      <xsl:if test="exists($language)">
        <xsl:attribute name="data-language" select="lower-case($language)"/>
      </xsl:if>
      <xsl:if test="$classes = 'show-line-numbers'">
        <xsl:attribute name="data-line-numbers" select="'true'"/>
      </xsl:if>
      <xsl:apply-templates select="node()" mode="z:xhtml"/>
    </xsl:element>
  </xsl:template>

  <!-- ============ Sidecar metadata (override z:page-metadata-extra to add keys) ============ -->

  <xsl:function name="z:page-metadata" as="map(*)">
    <xsl:param name="root" as="element()"/>
    <xsl:param name="fragment" as="element()?"/>
    <xsl:variable name="topic" select="($root/descendant-or-self::*[contains(@class, ' topic/topic ')])[1]"/>
    <xsl:variable name="h1" select="($fragment//*[local-name() = 'h1'])[1]"/>
    <xsl:variable name="desc" select="normalize-space(string-join(
        ($topic/*[contains(@class, ' topic/shortdesc ')],
         $topic/*[contains(@class, ' topic/abstract ')]/*[contains(@class, ' topic/shortdesc ')])[1]//text(), ''))"/>
    <xsl:variable name="keywords" select="distinct-values(
        $topic/*[contains(@class, ' topic/prolog ')]//*[contains(@class, ' topic/keyword ')]/normalize-space())[. != '']"/>
    <xsl:variable name="lang" select="($topic/ancestor-or-self::*/@xml:lang)[last()]"/>
    <xsl:variable name="type" select="substring-before((tokenize(normalize-space($topic/@class), ' ')[last()]), '/')"/>
    <xsl:sequence select="map:merge((
        map { 'format': 'dita-interchange-page/1',
              'title': normalize-space(string($h1)),
              'title_html': z:inner-xhtml($h1),
              'id': string($topic/@id),
              'type': $type,
              'source': string(($topic/@xtrf, base-uri($topic))[1]),
              'topics': array { $root/descendant-or-self::*[contains(@class, ' topic/topic ')] !
                  map { 'id': string(@id), 'source': string((@xtrf, base-uri(.))[1]) } },
              'headings': array { $fragment//*[matches(local-name(), '^h[1-6]$')] ! z:heading-entry(.) } },
        ($desc[. != ''] ! map { 'description': . }),
        (if (exists($keywords)) then map { 'keywords': array { $keywords } } else ()),
        ($lang ! map { 'language': string(.) }),
        ($topic/@outputclass ! map { 'outputclass': string(.) }),
        z:page-metadata-extra($root, $fragment)),
        map { 'duplicates': 'use-last' })"
        xmlns:map="http://www.w3.org/2005/xpath-functions/map"/>
  </xsl:function>

  <!-- Extension hook: return a map of extra sidecar keys -->
  <xsl:function name="z:page-metadata-extra" as="map(*)?">
    <xsl:param name="root" as="element()"/>
    <xsl:param name="fragment" as="element()?"/>
    <xsl:sequence select="()"/>
  </xsl:function>

  <xsl:function name="z:heading-entry" as="map(*)">
    <xsl:param name="h" as="element()"/>
    <xsl:variable name="anchor" select="(
        $h/@id,
        $h[empty(preceding-sibling::*)]/parent::*[local-name() = ('section', 'article', 'div')]/@id)[1]"/>
    <xsl:sequence select="map:merge((
        map { 'level': xs:integer(substring(local-name($h), 2)),
              'text': normalize-space(string($h)),
              'html': z:inner-xhtml($h),
              'classes': array { tokenize($h/@class, '\s+')[. != ''] } },
        ($anchor ! map { 'anchor': string(.) })))"
        xmlns:map="http://www.w3.org/2005/xpath-functions/map"/>
  </xsl:function>

  <xsl:function name="z:inner-xhtml" as="xs:string">
    <xsl:param name="e" as="element()?"/>
    <xsl:variable name="plain" as="node()*">
      <xsl:apply-templates select="$e/node()" mode="z:no-namespace"/>
    </xsl:variable>
    <xsl:sequence select="normalize-space(string-join($plain ! serialize(., map {
        'method': 'xhtml', 'html-version': 5.0, 'omit-xml-declaration': true(), 'indent': false() }), ''))"/>
  </xsl:function>

  <!-- Inline markup in the JSON is plain HTML, without namespace declarations -->
  <xsl:template match="*" mode="z:no-namespace">
    <xsl:element name="{local-name()}">
      <xsl:apply-templates select="@*, node()" mode="z:no-namespace"/>
    </xsl:element>
  </xsl:template>
  <xsl:template match="@* | text()" mode="z:no-namespace">
    <xsl:copy/>
  </xsl:template>
  <xsl:template match="comment() | processing-instruction()" mode="z:no-namespace"/>

</xsl:stylesheet>

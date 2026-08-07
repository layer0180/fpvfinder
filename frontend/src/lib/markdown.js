/**
 * Minimal Markdown renderer for the legal pages.
 *
 * Deliberately not a dependency: three operator-authored documents do not
 * justify pulling a parser plus a sanitiser into the bundle.
 *
 * Safety: the input comes from files the operator controls, not from visitors.
 * Even so, everything is HTML-escaped first and only a fixed set of tags is
 * emitted afterwards, so a stray "<script>" in a template can never execute.
 *
 * Supported: headings, paragraphs, bold, italic, inline code, links, bullet and
 * numbered lists, tables, horizontal rules, blockquotes. HTML comments (used
 * for the "fill this in" instructions in the templates) are stripped.
 */

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** Inline formatting, applied to already-escaped text. */
function inline(text) {
  return (
    text
      // `code`
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // [label](url) - only http(s) and mailto, so no javascript: URLs
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+|mailto:[^)\s]+|#[^)\s]*)\)/g, (m, label, href) => {
        const external = href.startsWith('http')
        const attrs = external ? ' target="_blank" rel="noreferrer noopener"' : ''
        return `<a href="${href}"${attrs}>${label}</a>`
      })
      // bare <https://...> autolinks
      .replace(/&lt;(https?:\/\/[^\s&]+)&gt;/g, '<a href="$1" target="_blank" rel="noreferrer noopener">$1</a>')
      // **bold** then *italic*
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
  )
}

function renderTableRow(line, cellTag) {
  const cells = line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => `<${cellTag}>${inline(c.trim())}</${cellTag}>`)
    .join('')
  return `<tr>${cells}</tr>`
}

export function renderMarkdown(source) {
  if (!source) return ''

  // Strip HTML comments (the template instructions) before escaping.
  const text = escapeHtml(source.replace(/<!--[\s\S]*?-->/g, ''))
  const lines = text.split('\n')
  const out = []

  let listType = null // 'ul' | 'ol' | null
  let inTable = false
  // Consecutive plain lines belong to one paragraph, as in real Markdown.
  // Without this, every source line became its own <p> (ugly spacing) and any
  // **bold** spanning a line break was never recognised.
  let paragraph = []

  const flushParagraph = () => {
    if (paragraph.length) {
      out.push(`<p>${inline(paragraph.join(' '))}</p>`)
      paragraph = []
    }
  }
  const closeList = () => {
    flushParagraph()
    if (listType) {
      out.push(`</${listType}>`)
      listType = null
    }
  }
  const closeTable = () => {
    if (inTable) {
      out.push('</tbody></table>')
      inTable = false
    }
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) {
      closeList()
      closeTable()
      continue
    }

    // Table: a header row followed by a |---|---| separator
    if (!inTable && trimmed.startsWith('|') && /^\|[\s:|-]+\|$/.test((lines[i + 1] || '').trim())) {
      closeList()
      out.push('<table><thead>', renderTableRow(trimmed, 'th'), '</thead><tbody>')
      inTable = true
      i += 1 // skip the separator row
      continue
    }
    if (inTable) {
      if (trimmed.startsWith('|')) {
        out.push(renderTableRow(trimmed, 'td'))
        continue
      }
      closeTable()
    }

    const heading = trimmed.match(/^(#{1,4})\s+(.*)$/)
    if (heading) {
      closeList()
      const level = Math.min(heading[1].length + 1, 5) // h1 in markdown -> h2 in the page
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`)
      continue
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      closeList()
      out.push('<hr />')
      continue
    }

    if (trimmed.startsWith('&gt; ')) {
      closeList()
      out.push(`<blockquote>${inline(trimmed.slice(5))}</blockquote>`)
      continue
    }

    const bullet = trimmed.match(/^[-*]\s+(.*)$/)
    if (bullet) {
      if (listType !== 'ul') {
        closeList()
        out.push('<ul>')
        listType = 'ul'
      }
      out.push(`<li>${inline(bullet[1])}</li>`)
      continue
    }

    const numbered = trimmed.match(/^\d+\.\s+(.*)$/)
    if (numbered) {
      if (listType !== 'ol') {
        closeList()
        out.push('<ol>')
        listType = 'ol'
      }
      out.push(`<li>${inline(numbered[1])}</li>`)
      continue
    }

    // Plain text: accumulate until a blank line or a block element ends it.
    paragraph.push(trimmed)
  }

  closeList()
  closeTable()
  return out.join('\n')
}

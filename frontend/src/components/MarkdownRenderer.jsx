import React, { useState } from 'react';

/**
 * Markdown renderer — handles **bold**, *italic*, `inline code`,
 * ```code blocks```, [links](url). Always renders visible content.
 */
export function MarkdownRenderer({ content, fallback }) {
    if (!content || typeof content !== 'string') {
        return fallback ? <span className="message-plain">{fallback}</span> : null;
    }

    const blocks = parseBlocks(content);
    if (!blocks || blocks.length === 0) {
        return <span className="message-plain">{content}</span>;
    }

    return (
        <div className="markdown-body">
            {blocks.map((block, i) => (
                <Block key={i} block={block} />
            ))}
        </div>
    );
}

function parseBlocks(text) {
    const blocks = [];
    const lines = text.split('\n');
    let i = 0;

    while (i < lines.length) {
        const line = lines[i];

        // Fenced code block
        if (line.trimStart().startsWith('```')) {
            const lang = line.trimStart().slice(3).trim();
            const codeLines = [];
            i++;
            while (i < lines.length && !lines[i].trimStart().startsWith('```')) {
                codeLines.push(lines[i]);
                i++;
            }
            i++; // skip closing ```
            blocks.push({ type: 'code', lang, content: codeLines.join('\n') });
            continue;
        }

        // Heading
        const headingMatch = line.match(/^(#{1,3})\s+(.+)$/);
        if (headingMatch) {
            blocks.push({ type: 'heading', level: headingMatch[1].length, content: headingMatch[2] });
            i++;
            continue;
        }

        // Unordered list item
        if (line.match(/^\s*[-*]\s+/)) {
            const items = [];
            while (i < lines.length && lines[i].match(/^\s*[-*]\s+/)) {
                items.push(lines[i].replace(/^\s*[-*]\s+/, ''));
                i++;
            }
            blocks.push({ type: 'ul', items });
            continue;
        }

        // Ordered list item
        if (line.match(/^\s*\d+\.\s+/)) {
            const items = [];
            while (i < lines.length && lines[i].match(/^\s*\d+\.\s+/)) {
                items.push(lines[i].replace(/^\s*\d+\.\s+/, ''));
                i++;
            }
            blocks.push({ type: 'ol', items });
            continue;
        }

        // Empty line
        if (line.trim() === '') {
            i++;
            continue;
        }

        // Paragraph: collect contiguous non-empty, non-special lines
        const paraLines = [];
        while (
            i < lines.length &&
            lines[i].trim() !== '' &&
            !lines[i].trimStart().startsWith('```') &&
            !lines[i].match(/^#{1,3}\s+/) &&
            !lines[i].match(/^\s*[-*]\s+/) &&
            !lines[i].match(/^\s*\d+\.\s+/)
        ) {
            paraLines.push(lines[i]);
            i++;
        }
        blocks.push({ type: 'paragraph', content: paraLines.join('\n') });
    }

    return blocks;
}

function Block({ block }) {
    switch (block.type) {
        case 'code':
            return <CodeBlock lang={block.lang} code={block.content} />;
        case 'heading':
            const Tag = `h${block.level}`;
            return <Tag className="md-heading">{renderInline(block.content)}</Tag>;
        case 'ul':
            return (
                <ul className="md-list">
                    {block.items.map((item, i) => (
                        <li key={i}>{renderInline(item)}</li>
                    ))}
                </ul>
            );
        case 'ol':
            return (
                <ol className="md-list">
                    {block.items.map((item, i) => (
                        <li key={i}>{renderInline(item)}</li>
                    ))}
                </ol>
            );
        case 'paragraph':
        default:
            return <p className="md-paragraph">{renderInline(block.content)}</p>;
    }
}

function renderInline(text) {
    if (!text) return null;

    // Tokenize inline markdown
    const parts = [];
    let remaining = text;
    let key = 0;

    while (remaining.length > 0) {
        // Inline code
        let match = remaining.match(/^`([^`]+)`/);
        if (match) {
            parts.push(<code key={key++} className="md-inline-code">{match[1]}</code>);
            remaining = remaining.slice(match[0].length);
            continue;
        }

        // Bold
        match = remaining.match(/^\*\*(.+?)\*\*/);
        if (match) {
            parts.push(<strong key={key++}>{match[1]}</strong>);
            remaining = remaining.slice(match[0].length);
            continue;
        }

        // Italic
        match = remaining.match(/^\*(.+?)\*/);
        if (match) {
            parts.push(<em key={key++}>{match[1]}</em>);
            remaining = remaining.slice(match[0].length);
            continue;
        }

        // Links
        match = remaining.match(/^\[([^\]]+)\]\(([^)]+)\)/);
        if (match) {
            parts.push(
                <a key={key++} href={match[2]} target="_blank" rel="noopener noreferrer" className="md-link">
                    {match[1]}
                </a>
            );
            remaining = remaining.slice(match[0].length);
            continue;
        }

        // Line break
        if (remaining.startsWith('\n')) {
            parts.push(<br key={key++} />);
            remaining = remaining.slice(1);
            continue;
        }

        // Normal text — consume until next special char
        const nextSpecial = remaining.slice(1).search(/[`*\[\n]/);
        if (nextSpecial === -1) {
            parts.push(remaining);
            break;
        }
        parts.push(remaining.slice(0, nextSpecial + 1));
        remaining = remaining.slice(nextSpecial + 1);
    }

    return parts;
}

function CodeBlock({ lang, code }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Copy failed:', err);
        }
    };

    return (
        <div className="md-code-block">
            <div className="md-code-header">
                <span className="md-code-lang">{lang || 'code'}</span>
                <button className="md-code-copy" onClick={handleCopy}>
                    {copied ? (
                        <>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12"></polyline>
                            </svg>
                            Copied
                        </>
                    ) : (
                        <>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                            </svg>
                            Copy
                        </>
                    )}
                </button>
            </div>
            <pre className="md-code-content"><code>{code}</code></pre>
        </div>
    );
}

export default MarkdownRenderer;

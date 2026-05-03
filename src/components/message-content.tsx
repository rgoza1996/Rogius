import React, { memo } from 'react';

interface MessageContentProps {
  content: string;
}

// ⚡ BOLT OPTIMIZATION: Memoize the expensive markdown regex parsing
// to prevent O(N) regex operations on every chunk during streaming responses.
const MessageContentComponent: React.FC<MessageContentProps> = ({ content }) => {
  // Parse markdown content to extract code blocks and text
  const parts: Array<{type: 'terminal' | 'code' | 'text', content: string, language?: string}> = []
  const codeBlockRegex = /```(\w*)\n?([\s\S]*?)\n?```/g
  let lastIndex = 0
  let match

  while ((match = codeBlockRegex.exec(content)) !== null) {
    // Add text before this code block
    if (match.index > lastIndex) {
      const textContent = content.slice(lastIndex, match.index).trim()
      if (textContent) {
        parts.push({ type: 'text', content: textContent })
      }
    }

    // Add the code block
    const language = match[1]
    const codeContent = match[2].trim()
    parts.push({
      type: language === 'terminal' ? 'terminal' : 'code',
      content: codeContent,
      language: language || 'text'
    })

    lastIndex = match.index + match[0].length
  }

  // Add remaining text after last code block
  if (lastIndex < content.length) {
    const remainingText = content.slice(lastIndex).trim()
    if (remainingText) {
      parts.push({ type: 'text', content: remainingText })
    }
  }

  // If no code blocks found, treat entire content as text
  if (parts.length === 0) {
    parts.push({ type: 'text', content: content })
  }

  return (
    <>
      {parts.map((part, idx) => {
        if (part.type === 'terminal') {
          const lines = part.content.split('\n')
          const command = lines[0].startsWith('$ ') ? lines[0].slice(2) : lines[0]
          const output = lines.slice(1).join('\n')
          return (
            <div key={idx} className="bg-black rounded-lg p-3 font-mono text-xs overflow-x-auto my-2 border border-gray-800">
              <div className="flex items-center gap-2 text-green-400 mb-1">
                <span className="text-muted-foreground">$</span>
                <span>{command}</span>
              </div>
              {output && <pre className="text-gray-300 whitespace-pre-wrap mt-2">{output}</pre>}
            </div>
          )
        } else if (part.type === 'code') {
          return (
            <div key={idx} className="bg-gray-900 rounded-lg p-3 font-mono text-xs overflow-x-auto my-2 border border-gray-800">
              <div className="text-gray-400 mb-1 text-xs">{part.language}</div>
              <pre className="text-gray-300 whitespace-pre-wrap">{part.content}</pre>
            </div>
          )
        } else {
          // Split text by double newlines for paragraph separation
          return part.content.split('\n\n').map((para, pIdx) => (
            <p key={`${idx}-${pIdx}`} className="whitespace-pre-wrap">{para}</p>
          ))
        }
      })}
    </>
  );
};

export const MessageContent = memo(MessageContentComponent);

## 2023-10-27 - Unoptimized Regex Markdown Rendering in Chat
**Learning:** Found that inline Regex parsing for markdown rendering in `page.tsx` was executed on every re-render (which happens frequently due to streaming). Since this is a React environment, not memoizing expensive pure-function components leads to poor performance.
**Action:** Always extract expensive string manipulations or Regex matching into separate, memoized components (`React.memo`) to prevent re-evaluation during parent re-renders.
